import json
import os
import pathlib
import sys

# --- 常量 ---
PRESET_VERSION = 6
PRESET_CMAKE_MIN_MAJOR = 3
PRESET_CMAKE_MIN_MINOR = 25
PRESET_CMAKE_MIN_PATCH = 0
DEFAULT_BINARY_DIR_SUFFIX = "build"
DEFAULT_RUNTIME_OUTPUT_DIR_SUFFIX = "build/bin"
DEFAULT_BUILD_JOBS = 8
CMAKE_VAR_LINKER = "CMAKE_LINKER"
CMAKE_VAR_RC_COMPILER = "CMAKE_RC_COMPILER"
CMAKE_VAR_MT_COMPILER = "CMAKE_MT"
DEFAULT_TEST_TIMEOUT = 300


class PresetGenerator:
    def __init__(self, project_dir_str: str, template_path_str: str):
        self.project_dir = pathlib.Path(project_dir_str)
        self.template_path = pathlib.Path(template_path_str)
        self.template_data = self._load_template()
        if not self.template_data:
            sys.exit(1)
        self.presets = {}
        self.global_cmake_options_from_all_workflow_steps = self._collect_all_cmake_options_from_template()

    def _load_template(self):
        if not self.template_path.is_file():
            print(f"错误：模板文件未在路径 {self.template_path} 找到")
            sys.exit(1)
        try:
            with open(self.template_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            print(f"错误：解析模板文件 {self.template_path} 中的 JSON 失败: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"错误：加载模板文件 {self.template_path} 失败: {e}")
            sys.exit(1)
        return None

    def _cmake_bool_value(self, value):
        if isinstance(value, bool): return "ON" if value else "OFF"
        if isinstance(value, (int, float)): return "ON" if int(value) == 1 else "OFF"
        if isinstance(value, str):
            if value.upper() == "ON": return "ON"
            if value.upper() == "OFF": return "OFF"
        return "OFF"

    def _collect_all_cmake_options_from_template(self):
        collected_options = {}
        for workflow_group in self.template_data.get("workflows", []):
            for _, steps_list in workflow_group.items():
                if isinstance(steps_list, list):
                    for step_spec in steps_list:
                        step_options = step_spec.get("option", {})
                        for key, value in step_options.items():
                            cmake_value = self._cmake_bool_value(value)
                            if cmake_value == "ON":
                                collected_options[key] = "ON"
                            elif key not in collected_options:
                                collected_options[key] = "OFF"
        return collected_options

    def add_version_info(self):
        self.presets["version"] = PRESET_VERSION
        self.presets["cmakeMinimumRequired"] = {
            "major": PRESET_CMAKE_MIN_MAJOR, "minor": PRESET_CMAKE_MIN_MINOR, "patch": PRESET_CMAKE_MIN_PATCH
        }

    def add_configure_presets(self):
        global arch_value, arch_strategy, tool_strategy, tool_value
        self.presets["configurePresets"] = []
        for platform_spec in self.template_data.get("platform", []):
            os_name_template = platform_spec.get("os")
            if not os_name_template: continue
            os_preset_name_part = os_name_template.lower()
            display_os_name = os_name_template
            if os_name_template == "Darwin": os_preset_name_part, display_os_name = "mac", "macOS"
            base_preset_name = f"{os_preset_name_part}-base"
            current_cache_vars = {
                "CMAKE_C_COMPILER": platform_spec.get("C_COMPILER"),
                "CMAKE_CXX_COMPILER": platform_spec.get("CXX_COMPILER"),
                "CMAKE_CXX_STANDARD": str(platform_spec.get("CMAKE_CXX_STANDARD", "")),
                "CMAKE_TOOLCHAIN_FILE": platform_spec.get("toolchain"),
                "VCPKG_TARGET_TRIPLET": platform_spec.get("triplet")
            }
            architecture_spec = platform_spec.get("architecture")
            toolset_spec = platform_spec.get("toolset")
            if architecture_spec and toolset_spec:
                arch_value = architecture_spec.get("value")
                arch_strategy = architecture_spec.get("strategy")
                tool_value = toolset_spec.get("value")
                tool_strategy = toolset_spec.get("strategy")
                if tool_value and tool_strategy:
                    current_toolset_vars = {
                        "value": toolset_spec.get("value"),
                        "strategy": toolset_spec.get("strategy")
                    }
                if arch_value and arch_strategy:
                    current_architecture_vars = {
                        "value": arch_value,
                        "strategy": arch_strategy
                    }

            if os_name_template == "Windows":
                if "LINK" in platform_spec: current_cache_vars[CMAKE_VAR_LINKER] = platform_spec["LINK"]
                if "RC" in platform_spec: current_cache_vars[CMAKE_VAR_RC_COMPILER] = platform_spec["RC"]
                if "MT" in platform_spec: current_cache_vars[CMAKE_VAR_MT_COMPILER] = platform_spec["MT"]
            final_base_cache_vars = current_cache_vars.copy()
            final_base_cache_vars.update(self.global_cmake_options_from_all_workflow_steps)
            if os_name_template == "Windows":
                realGenerator = platform_spec.get("generator")
                if realGenerator == "Ninja":
                    base_configure_preset_obj = {
                        "name": base_preset_name, "hidden": True, "displayName": f"{display_os_name} Base",
                        "description": platform_spec.get("description", f"{display_os_name} 的基础配置"),
                        "generator": platform_spec.get("generator", "Ninja"),
                        "binaryDir": f"${{sourceDir}}/{DEFAULT_BINARY_DIR_SUFFIX}",
                        "cacheVariables": {k: v for k, v in final_base_cache_vars.items() if v is not None and v != ""},
                    }
                else:
                    base_configure_preset_obj = {
                        "name": base_preset_name, "hidden": True, "displayName": f"{display_os_name} Base",
                        "description": platform_spec.get("description", f"{display_os_name} 的基础配置"),
                        "generator": platform_spec.get("generator"),
                        "binaryDir": f"${{sourceDir}}/{DEFAULT_BINARY_DIR_SUFFIX}",
                        "architecture": {k: v for k, v in current_architecture_vars.items() if
                                         v is not None and v != ""},
                        "toolset": {k: v for k, v in current_toolset_vars.items() if v is not None and v != ""},
                        "cacheVariables": {k: v for k, v in final_base_cache_vars.items() if v is not None and v != ""},
                    }
            else:
                base_configure_preset_obj = {
                    "name": base_preset_name, "hidden": True, "displayName": f"{display_os_name} Base",
                    "description": platform_spec.get("description", f"{display_os_name} 的基础配置"),
                    "generator": platform_spec.get("generator", "Ninja"),
                    "binaryDir": f"${{sourceDir}}/{DEFAULT_BINARY_DIR_SUFFIX}",
                    "cacheVariables": {k: v for k, v in final_base_cache_vars.items() if v is not None and v != ""},
                }
            self.presets["configurePresets"].append(base_configure_preset_obj)
            for build_type in ["debug", "release"]:
                concrete_config_preset_name = f"{os_preset_name_part}-{build_type}"
                display_build_type = build_type.capitalize()
                flags_key = "debug_flag" if build_type == "debug" else "rel_flag"
                flags = platform_spec.get(flags_key, {})
                cfg_specific_cache_vars = {"CMAKE_BUILD_TYPE": display_build_type}
                if flags.get("CMAKE_CXX_FLAGS"): cfg_specific_cache_vars["CMAKE_CXX_FLAGS"] = flags.get(
                    "CMAKE_CXX_FLAGS")
                if flags.get("CMAKE_C_FLAGS"): cfg_specific_cache_vars["CMAKE_C_FLAGS"] = flags.get("CMAKE_C_FLAGS")
                cfg_specific_cache_vars[
                    "CMAKE_RUNTIME_OUTPUT_DIRECTORY"] = f"${{sourceDir}}/{DEFAULT_RUNTIME_OUTPUT_DIR_SUFFIX}"
                cfg_preset = {
                    "name": concrete_config_preset_name, "displayName": f"{display_os_name} {display_build_type}",
                    "inherits": base_preset_name,
                    "condition": {"type": "equals", "lhs": "${hostSystemName}", "rhs": os_name_template},
                    "binaryDir": f"${{sourceDir}}/{DEFAULT_BINARY_DIR_SUFFIX}",
                    "cacheVariables": cfg_specific_cache_vars
                }
                self.presets["configurePresets"].append(cfg_preset)

    def add_build_presets(self):
        self.presets["buildPresets"] = []
        all_build_step_targets = set()
        for workflow_group in self.template_data.get("workflows", []):
            for _, steps_list in workflow_group.items():
                if isinstance(steps_list, list):
                    for step_spec in steps_list:
                        if step_spec.get("type") == "build":
                            target_name = step_spec.get("target")
                            if target_name:
                                all_build_step_targets.add(target_name)
                            else:  # Fallback (not recommended, template should provide "target")
                                desc = step_spec.get("description", "").lower()
                                if "clang-format" in desc and "check" not in desc:
                                    all_build_step_targets.add("clang-format")
                                elif "clang-format-check" in desc:
                                    all_build_step_targets.add("clang-format-check")

        for platform_spec in self.template_data.get("platform", []):
            os_name_template = platform_spec.get("os")
            if not os_name_template: continue
            os_preset_name_part = os_name_template.lower()
            display_os_name = os_name_template
            if os_name_template == "Darwin": os_preset_name_part, display_os_name = "mac", "macOS"

            for build_type_suffix in ["debug", "release"]:
                configure_preset_ref = f"{os_preset_name_part}-{build_type_suffix}"
                display_build_type_name = build_type_suffix.capitalize()
                # Main build preset
                self.presets["buildPresets"].append({
                    "name": f"build-{configure_preset_ref}",
                    "configurePreset": configure_preset_ref, "jobs": DEFAULT_BUILD_JOBS,
                    "displayName": f"构建主项目 ({display_os_name} {display_build_type_name})"
                })
                # Build presets for specific targets collected from template
                for target_name in all_build_step_targets:
                    build_preset_name = f"build-{configure_preset_ref}-{target_name.replace(' ', '-').lower()}"
                    self.presets["buildPresets"].append({
                        "name": build_preset_name, "targets": [target_name],
                        "configurePreset": configure_preset_ref,
                        "displayName": f"构建目标 '{target_name}' ({display_os_name} {display_build_type_name})"
                    })

    def add_test_presets(self):
        self.presets["testPresets"] = []
        all_template_test_steps = []
        for workflow_group in self.template_data.get("workflows", []):
            for _, steps_list in workflow_group.items():
                if isinstance(steps_list, list):
                    for step_spec in steps_list:
                        if step_spec.get("type") == "test":
                            all_template_test_steps.append(step_spec)
        if not all_template_test_steps: return

        for platform_spec in self.template_data.get("platform", []):
            os_name_template = platform_spec.get("os")
            if not os_name_template: continue
            os_preset_name_part = os_name_template.lower()
            display_os_name = os_name_template
            if os_name_template == "Darwin": os_preset_name_part, display_os_name = "mac", "macOS"

            for build_type_suffix_for_tests in ["debug", "release"]:  # Iterate for both build types
                is_test_preset_needed_for_this_build_type = False
                for step_spec in all_template_test_steps:
                    # Check if any test step applies to the current build_type_suffix_for_tests
                    if build_type_suffix_for_tests in step_spec.get("args", {}).get("apply_to_build_types", ["debug"]):
                        is_test_preset_needed_for_this_build_type = True;
                        break
                if not is_test_preset_needed_for_this_build_type: continue

                configure_preset_ref = f"{os_preset_name_part}-{build_type_suffix_for_tests}"
                base_test_preset_name_for_type = f"{os_preset_name_part}-{build_type_suffix_for_tests}-tests"

                current_base_test_preset_obj = None
                # Ensure base test preset for this type (debug/release) is added only once
                if not any(tp["name"] == base_test_preset_name_for_type for tp in self.presets.get("testPresets", [])):
                    current_base_test_preset_obj = {
                        "name": base_test_preset_name_for_type,
                        "displayName": f"运行测试 ({display_os_name} {build_type_suffix_for_tests.capitalize()})",
                        "configurePreset": configure_preset_ref,
                        "configuration": build_type_suffix_for_tests.capitalize(),
                        "output": {"outputOnFailure": True, "verbosity": "default"},
                        "execution": {"jobs": 1, "timeout": DEFAULT_TEST_TIMEOUT}
                    }
                    self.presets["testPresets"].append(current_base_test_preset_obj)
                else:
                    current_base_test_preset_obj = next(
                        tp for tp in self.presets["testPresets"] if tp["name"] == base_test_preset_name_for_type)

    def add_workflow_presets(self):
        self.presets["workflowPresets"] = []
        template_workflow_groups = self.template_data.get("workflows", [])
        if not template_workflow_groups: return

        for platform_spec in self.template_data.get("platform", []):
            os_name_template = platform_spec.get("os")
            if not os_name_template: continue
            os_preset_name_part = os_name_template.lower()
            display_os_name = os_name_template
            if os_name_template == "Darwin": os_preset_name_part, display_os_name = "mac", "macOS"

            for build_type_suffix in ["debug", "release"]:  # Iterate for both build types
                base_configure_preset_ref = f"{os_preset_name_part}-{build_type_suffix}"
                display_build_type_name = build_type_suffix.capitalize()
                main_build_preset_ref = f"build-{base_configure_preset_ref}"

                for workflow_group in template_workflow_groups:
                    for template_wf_concept_name, template_steps_list in workflow_group.items():
                        if not isinstance(template_steps_list, list): continue

                        workflow_preset_name = f"{os_preset_name_part}-{build_type_suffix}-workflow-{template_wf_concept_name.replace(' ', '-').lower()}"

                        configure_step = {"type": "configure", "name": base_configure_preset_ref}
                        current_workflow_actual_steps = [configure_step]

                        # Add optional "build" type pre-steps
                        for step_spec in template_steps_list:
                            step_type = step_spec.get("type")
                            if step_type == "build":
                                step_options = step_spec.get("option", {})
                                execute_this_step = True
                                for option_key, option_template_value in step_options.items():
                                    if self._cmake_bool_value(option_template_value) == "OFF":
                                        execute_this_step = False;
                                        break
                                if not execute_this_step: continue

                                cmake_target_name = step_spec.get("target")
                                if not cmake_target_name:
                                    desc_lower = step_spec.get("description", "").lower()
                                    if "clang-format" in desc_lower and "check" not in desc_lower:
                                        cmake_target_name = "clang-format"
                                    elif "clang-format-check" in desc_lower:
                                        cmake_target_name = "clang-format-check"

                                if cmake_target_name:
                                    build_preset_for_step = f"build-{base_configure_preset_ref}-{cmake_target_name.replace(' ', '-').lower()}"
                                    if any(bp["name"] == build_preset_for_step for bp in
                                           self.presets.get("buildPresets", [])):
                                        current_workflow_actual_steps.append(
                                            {"type": "build", "name": build_preset_for_step})
                                    else:
                                        print(
                                            f"警告: 前置构建步骤 '{step_spec.get('description')}' 在工作流 '{workflow_preset_name}' 中找不到对应构建预设 '{build_preset_for_step}'。")
                                else:
                                    print(
                                        f"警告: 工作流 '{workflow_preset_name}' 的构建步骤 '{step_spec.get('description')}' 未能确定 CMake 目标名称。")

                        # Add main build step
                        if any(bp["name"] == main_build_preset_ref for bp in self.presets.get("buildPresets", [])):
                            current_workflow_actual_steps.append({"type": "build", "name": main_build_preset_ref})
                        else:
                            print(f"严重警告: 主构建预设 '{main_build_preset_ref}' 未找到！")

                        # Add optional "test" type post-steps
                        for step_spec in template_steps_list:
                            step_type = step_spec.get("type")
                            if step_type == "test":
                                step_options = step_spec.get("option", {})
                                execute_this_step = True
                                for option_key, option_template_value in step_options.items():
                                    if self._cmake_bool_value(option_template_value) == "OFF":
                                        execute_this_step = False;
                                        break
                                if not execute_this_step: continue

                                step_args = step_spec.get("args", {})
                                applicable_build_types = step_args.get("apply_to_build_types", ["debug"])

                                if build_type_suffix in applicable_build_types:
                                    test_preset_base_name_for_current_type = f"{os_preset_name_part}-{build_type_suffix}-tests"
                                    test_preset_to_ref = test_preset_base_name_for_current_type

                                    if step_args.get("use_launcher"):
                                        suffix = step_args.get("launcher_test_preset_suffix")
                                        if not suffix: suffix = "-" + step_spec.get("description", "launcher").replace(
                                            ' ', '-').lower()
                                        test_preset_to_ref = f"{test_preset_base_name_for_current_type}{suffix}"

                                    if any(tp["name"] == test_preset_to_ref for tp in
                                           self.presets.get("testPresets", [])):
                                        current_workflow_actual_steps.append(
                                            {"type": "test", "name": test_preset_to_ref})
                                    else:
                                        print(
                                            f"警告: 测试步骤 '{step_spec.get('description')}' 在工作流 '{workflow_preset_name}' 中尝试引用测试预设 '{test_preset_to_ref}' 但未找到。")

                        has_action_step = any(
                            s.get("type") in ["build", "test"] for s in current_workflow_actual_steps[1:])
                        if has_action_step:
                            self.presets["workflowPresets"].append({
                                "name": workflow_preset_name,
                                "displayName": f"工作流: {template_wf_concept_name} ({display_os_name} {display_build_type_name})",
                                "steps": current_workflow_actual_steps
                            })

    def generate(self):
        self.add_version_info()
        self.add_configure_presets()
        self.add_build_presets()
        self.add_test_presets()
        self.add_workflow_presets()
        self._write_presets()

    def _write_presets(self):
        output_path = self.project_dir / "CMakePresets.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(self.presets, f, indent=2, ensure_ascii=False)
            print(f"已在路径 {output_path} 生成 CMakePresets.json")
        except IOError as e:
            print(f"错误：写入 CMakePresets.json 到 {output_path} 失败: {e}")
            sys.exit(1)


def main():
    project_dir_env = os.environ.get("PROJECT_DIR")
    if not project_dir_env:
        print(f"警告：未设置 PROJECT_DIR 环境变量.")
        sys.exit(1)
    else:
        project_dir = pathlib.Path(project_dir_env)
    current_script_path = pathlib.Path(__file__).resolve()
    template_file_name = "presets.json"
    template_path = current_script_path.parent.parent / "template" / template_file_name
    if not template_path.is_file():
        print(f"关键错误: 模板文件 {template_path} 未找到。请创建该文件。脚本将退出。")
        sys.exit(1)

    generator = PresetGenerator(str(project_dir), str(template_path))
    generator.generate()


if __name__ == "__main__":
    main()
