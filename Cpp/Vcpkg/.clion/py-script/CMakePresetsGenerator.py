import json
import os
import pathlib
import sys
import copy
import platform as pf # To avoid conflict with template_data['platform']
import tempfile # For creating a temporary template file

# --- ANSI Color Codes ---
RED = "\033[91m"
YELLOW = "\033[93m"
GREEN = "\033[92m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
RESET = "\033[0m"

# --- 常量 (from your original PresetGenerator) ---
PRESET_VERSION = 6
PRESET_CMAKE_MIN_MAJOR = 3
PRESET_CMAKE_MIN_MINOR = 25
PRESET_CMAKE_MIN_PATCH = 0
DEFAULT_BINARY_DIR_SUFFIX = "build"
DEFAULT_RUNTIME_OUTPUT_DIR_SUFFIX = "bin"
DEFAULT_BUILD_JOBS = 8
CMAKE_VAR_LINKER = "CMAKE_LINKER"
CMAKE_VAR_RC_COMPILER = "CMAKE_RC_COMPILER"
CMAKE_VAR_MT_COMPILER = "CMAKE_MT"
DEFAULT_TEST_TIMEOUT = 300

# --- Embedded Source Template Data ---
INITIAL_SOURCE_TEMPLATE_DATA = {
    "workflows": [
        {
            "Flow": [
                { "description": "ClangFormat", "type": "build", "target": "clang-format", "option": { "ENABLE_CLANG_FORMAT": True } },
                { "description": "ClangFormat Check", "type": "build", "target": "clang-format-check", "option": { "ENABLE_CLANG_FORMAT_CHECK": True } },
                { "description": "ClangTidy Export", "type": "build", "target": "clang-tidy-export-all", "option": { "ENABLE_CLANG_TIDY_FIX_EXPORT": False } },
                { "description": "ClangTidy Apply", "type": "build", "target": "clang-tidy-apply", "option": { "ENABLE_CLANG_TIDY_Apply_EXPORT": False } },
                { "description": "Standard Unit-Tests", "type": "test", "option": { "BUILD_TESTS": True }, "args": { "apply_to_build_types": ["debug", "release"] } }
            ]
        }
    ],
    "platform": [
        {
            "os": "Windows", "description": "Windows下envPath需要包含CMake所需要的环境", "generator": "Ninja",
            "CMAKE_CXX_STANDARD": "20", "C_COMPILER": "clang-cl", "CXX_COMPILER": "clang-cl",
            "LINK": "lld-link", "RC": "rc", "MT": "mt", "MC": "mc",
            "architecture": { "value": "x64", "strategy": "set" },
            "toolset": { "value": "ClangCL", "strategy": "set" },
            "debug_flag": {
                "CMAKE_CXX_FLAGS": "/EHsc /W3 /Zi /FS /MDd /D_ITERATOR_DEBUG_LEVEL=2 ",
                "CMAKE_C_FLAGS": "/EHsc /W3 /Zi /FS /MDd /D_ITERATOR_DEBUG_LEVEL=2 "
            },
            "rel_flag": {
                "CMAKE_CXX_FLAGS": "/EHsc /W3  /O2 /FS /MD",
                "CMAKE_C_FLAGS": "/EHsc /W3  /O2 /FS /MD"
            },
            "toolchain": "C:/vcpkg/scripts/buildsystems/vcpkg.cmake", "triplet": "x64-win-llvm"
        },
        {
            "os": "Linux", "description": "Linux下使用clang和ninja，vcpkg toolchain", "generator": "Ninja",
            "CMAKE_CXX_STANDARD": "20", "C_COMPILER": "/usr/bin/clang", "CXX_COMPILER": "/usr/bin/clang++",
            "debug_flag": {
                "CMAKE_CXX_FLAGS": "-g -O0 -Wall -Wextra -fPIC", "CMAKE_C_FLAGS": "-g -O0 -Wall -fPIC"
            },
            "rel_flag": {
                "CMAKE_CXX_FLAGS": "-O2 -DNDEBUG -fPIC", "CMAKE_C_FLAGS": "-O2 -DNDEBUG -fPIC"
            },
            "toolchain": "/home/sammiller/MyFile/vcpkg/scripts/buildsystems/vcpkg.cmake", "triplet": "x64-linux-llvm",
            "envPath": [ "/usr/local/bin", "/usr/bin" ]
        },
        {
            "os": "Darwin", "description": "macOS下使用clang和ninja，vcpkg toolchain", "generator": "Ninja",
            "CMAKE_CXX_STANDARD": "17", "C_COMPILER": "clang", "CXX_COMPILER": "clang++",
            "debug_flag": {
                "CMAKE_CXX_FLAGS": "-g -O0 -Wall -Wextra -fPIC", "CMAKE_C_FLAGS": "-g -O0 -Wall -fPIC"
            },
            "rel_flag": {
                "CMAKE_CXX_FLAGS": "-O2 -DNDEBUG -fPIC", "CMAKE_C_FLAGS": "-O2 -DNDEBUG -fPIC"
            },
            "toolchain": "/home/sammiller/APP/vcpkg/scripts/buildsystems/vcpkg.cmake", "triplet": "x64-osx-llvm",
            "envPath": [ "/usr/local/bin", "/opt/homebrew/bin" ]
        }
    ]
}

# --- Helper for menu display ---
def display_indexed_menu(items, prompt_message, item_formatter_func=None):
    print(f"\n{BLUE}{prompt_message}{RESET}")
    if not items:
        print(f"{YELLOW}没有可用选项。{RESET}")
        return -1
    for i, item in enumerate(items):
        display_text = item_formatter_func(i, item) if item_formatter_func else str(item)
        print(f"  {i + 1}. {display_text}")
    print(f"  0. 返回/取消")
    while True:
        try:
            choice_str = input(f"{CYAN}请输入您的选择: {RESET}").strip()
            if not choice_str: continue
            choice_idx = int(choice_str)
            if 0 <= choice_idx <= len(items):
                return choice_idx - 1
            else:
                print(f"{YELLOW}无效的选择 '{choice_str}'。请输入 0 到 {len(items)} 之间的数字。{RESET}")
        except ValueError:
            print(f"{YELLOW}无效的输入 '{choice_str}'。请输入一个数字。{RESET}")
        except KeyboardInterrupt:
            print(f"\n{YELLOW}操作已取消。{RESET}")
            return -1

# --- Your PresetGenerator Class (LOGIC UNCHANGED, only __init__ and _load_template are affected by how data is passed) ---
class PresetGenerator:
    def __init__(self, project_dir_str: str, template_path_str_or_data: str or dict): # Can now accept data directly
        self.project_dir = pathlib.Path(project_dir_str).resolve()

        # MODIFICATION: Load template from path OR use directly if dict
        if isinstance(template_path_str_or_data, dict):
            self.template_data = template_path_str_or_data
        elif isinstance(template_path_str_or_data, (str, pathlib.Path)):
            self.template_path = pathlib.Path(template_path_str_or_data)
            self.template_data = self._load_template_from_file() # Renamed
        else:
            print(f"{RED}错误：无效的模板源类型。{RESET}")
            sys.exit(1)

        if not self.template_data:
            sys.exit(1) # Error already printed by _load_template_from_file or check above

        self.presets = {}
        self.global_cmake_options_from_all_workflow_steps = self._collect_all_cmake_options_from_template()

    def _load_template_from_file(self): # This is your original _load_template
        if not self.template_path.is_file():
            print(f"{RED}错误：模板文件未在路径 {self.template_path} 找到{RESET}")
            return None # Return None to be checked by __init__
        try:
            with open(self.template_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            print(f"{RED}错误：解析模板文件 {self.template_path} 中的 JSON 失败: {e}{RESET}")
        except Exception as e:
            print(f"{RED}错误：加载模板文件 {self.template_path} 失败: {e}{RESET}")
        return None

    # --- All other methods of PresetGenerator remain UNCHANGED ---
    # _cmake_bool_value, _collect_all_cmake_options_from_template,
    # add_version_info, add_configure_presets, add_build_presets,
    # add_test_presets, add_workflow_presets, _write_presets

    def _cmake_bool_value(self, value):
        if isinstance(value, bool): return "ON" if value else "OFF"
        if isinstance(value, (int, float)): return "ON" if int(value) == 1 else "OFF"
        if isinstance(value, str):
            val_upper = value.upper()
            if val_upper == "ON": return "ON"
            if val_upper == "OFF": return "OFF"
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
        # global arch_value, arch_strategy, tool_strategy, tool_value # These were not consistently used or set as instance/class vars
        current_architecture_vars = {} # Define locally or pass if needed by other methods
        current_toolset_vars = {}    # Define locally or pass

        self.presets["configurePresets"] = []
        for platform_spec in self.template_data.get("platform", []):
            os_name_template = platform_spec.get("os")
            if not os_name_template: continue

            # Standardized naming from previous correction
            if os_name_template == "Darwin":
                os_preset_name_part = "mac"; display_os_name = "macOS"
            elif os_name_template == "Windows":
                os_preset_name_part = "windows"; display_os_name = "Windows"
            elif os_name_template == "Linux":
                os_preset_name_part = "linux"; display_os_name = "Linux"
            else:
                os_preset_name_part = os_name_template.lower().replace(" ", "-"); display_os_name = os_name_template

            base_preset_name = f"{os_preset_name_part}-base"

            current_cache_vars = {
                "CMAKE_C_COMPILER": platform_spec.get("C_COMPILER"),
                "CMAKE_CXX_COMPILER": platform_spec.get("CXX_COMPILER"),
                "CMAKE_CXX_STANDARD": str(platform_spec.get("CMAKE_CXX_STANDARD", "")),
                "CMAKE_TOOLCHAIN_FILE": platform_spec.get("toolchain"),
                "VCPKG_TARGET_TRIPLET": platform_spec.get("triplet")
            }

            # Architecture and Toolset (Specific to your original logic for non-Ninja on Windows)
            # These were declared global in your code, but should ideally be instance or local vars.
            # For simplicity, re-evaluating them here if needed by the non-Ninja Windows path.
            architecture_spec_val = platform_spec.get("architecture", {})
            toolset_spec_val = platform_spec.get("toolset", {})

            current_architecture_vars = {"value": architecture_spec_val.get("value"), "strategy": architecture_spec_val.get("strategy")}
            current_toolset_vars = {"value": toolset_spec_val.get("value"), "strategy": toolset_spec_val.get("strategy")}


            if os_name_template == "Windows":
                if "LINK" in platform_spec: current_cache_vars[CMAKE_VAR_LINKER] = platform_spec["LINK"]
                if "RC" in platform_spec: current_cache_vars[CMAKE_VAR_RC_COMPILER] = platform_spec["RC"]
                if "MT" in platform_spec: current_cache_vars[CMAKE_VAR_MT_COMPILER] = platform_spec["MT"]

            final_base_cache_vars = current_cache_vars.copy()
            final_base_cache_vars.update(self.global_cmake_options_from_all_workflow_steps)

            base_configure_preset_obj = {
                "name": base_preset_name, "hidden": True, "displayName": f"{display_os_name} Base",
                "description": platform_spec.get("description", f"{display_os_name} 的基础配置"),
                "generator": platform_spec.get("generator", "Ninja"), # Default to Ninja
                "binaryDir": f"${{sourceDir}}/{DEFAULT_BINARY_DIR_SUFFIX}",
                "cacheVariables": {k: v for k, v in final_base_cache_vars.items() if v is not None and v != ""},
            }

            # Your original logic for non-Ninja generator on Windows
            if os_name_template == "Windows" and platform_spec.get("generator") != "Ninja":
                if current_architecture_vars.get("value") and current_architecture_vars.get("strategy"):
                    base_configure_preset_obj["architecture"] = {k: v for k,v in current_architecture_vars.items() if v is not None and v != ""}
                if current_toolset_vars.get("value") and current_toolset_vars.get("strategy"):
                    base_configure_preset_obj["toolset"] =  {k: v for k,v in current_toolset_vars.items() if v is not None and v != ""}

            self.presets["configurePresets"].append(base_configure_preset_obj)

            for build_type in ["debug", "release"]:
                concrete_config_preset_name = f"{os_preset_name_part}-{build_type}"
                display_build_type = build_type.capitalize()
                flags_key = "debug_flag" if build_type == "debug" else "rel_flag"
                flags = platform_spec.get(flags_key, {})
                cfg_specific_cache_vars = {"CMAKE_BUILD_TYPE": display_build_type}
                if flags.get("CMAKE_CXX_FLAGS"): cfg_specific_cache_vars["CMAKE_CXX_FLAGS"] = flags.get("CMAKE_CXX_FLAGS")
                if flags.get("CMAKE_C_FLAGS"): cfg_specific_cache_vars["CMAKE_C_FLAGS"] = flags.get("CMAKE_C_FLAGS")

                # Corrected CMAKE_RUNTIME_OUTPUT_DIRECTORY based on previous discussion
                cfg_specific_cache_vars["CMAKE_RUNTIME_OUTPUT_DIRECTORY"] = f"${{binaryDir}}/{DEFAULT_RUNTIME_OUTPUT_DIR_SUFFIX}"

                cfg_preset = {
                    "name": concrete_config_preset_name, "displayName": f"{display_os_name} {display_build_type}",
                    "inherits": base_preset_name,
                    "condition": {"type": "equals", "lhs": "${hostSystemName}", "rhs": os_name_template}, # Original OS name for condition
                    # "binaryDir": f"${{sourceDir}}/{DEFAULT_BINARY_DIR_SUFFIX}", # Inherited
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
                            # Fallback logic from your original code (can be removed if targets are always present)
                            else:
                                desc = step_spec.get("description", "").lower()
                                if "clang-format" in desc and "check" not in desc: all_build_step_targets.add("clang-format")
                                elif "clang-format-check" in desc: all_build_step_targets.add("clang-format-check")

        for platform_spec in self.template_data.get("platform", []):
            os_name_template = platform_spec.get("os")
            if not os_name_template: continue

            if os_name_template == "Darwin": os_preset_name_part, display_os_name = "mac", "macOS"
            elif os_name_template == "Windows": os_preset_name_part = "windows"; display_os_name = "Windows"
            elif os_name_template == "Linux": os_preset_name_part = "linux"; display_os_name = "Linux"
            else: os_preset_name_part = os_name_template.lower().replace(" ", "-"); display_os_name = os_name_template


            for build_type_suffix in ["debug", "release"]:
                configure_preset_ref = f"{os_preset_name_part}-{build_type_suffix}" # e.g., mac-debug
                display_build_type_name = build_type_suffix.capitalize()

                self.presets["buildPresets"].append({
                    "name": f"build-{configure_preset_ref}", # e.g., build-mac-debug
                    "configurePreset": configure_preset_ref,
                    "jobs": DEFAULT_BUILD_JOBS,
                    "displayName": f"构建主项目 ({display_os_name} {display_build_type_name})"
                })
                for target_name in all_build_step_targets:
                    build_preset_name = f"build-{configure_preset_ref}-{target_name.replace(' ', '-').replace('_', '-').lower()}" # Sanitize target name for preset name
                    self.presets["buildPresets"].append({
                        "name": build_preset_name,
                        "targets": [target_name],
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

            if os_name_template == "Darwin": os_preset_name_part, display_os_name = "mac", "macOS"
            elif os_name_template == "Windows": os_preset_name_part = "windows"; display_os_name = "Windows"
            elif os_name_template == "Linux": os_preset_name_part = "linux"; display_os_name = "Linux"
            else: os_preset_name_part = os_name_template.lower().replace(" ", "-"); display_os_name = os_name_template

            for build_type_suffix_for_tests in ["debug", "release"]:
                is_test_preset_needed = any(
                    build_type_suffix_for_tests in step.get("args", {}).get("apply_to_build_types", ["debug", "release"]) # Default to both if not specified
                    for step in all_template_test_steps
                )
                if not is_test_preset_needed: continue

                configure_preset_ref = f"{os_preset_name_part}-{build_type_suffix_for_tests}" # e.g. mac-debug
                # Your original logic for base_test_preset_name_for_type, adapted for clarity
                test_preset_name = f"{os_preset_name_part}-{build_type_suffix_for_tests}-tests" # e.g. mac-debug-tests

                # Check if this exact test preset name was already added (it shouldn't if logic is per platform-build_type combo)
                if not any(tp["name"] == test_preset_name for tp in self.presets.get("testPresets", [])):
                    self.presets["testPresets"].append({
                        "name": test_preset_name,
                        "displayName": f"运行测试 ({display_os_name} {build_type_suffix_for_tests.capitalize()})",
                        "configurePreset": configure_preset_ref,
                        "configuration": build_type_suffix_for_tests.capitalize(),
                        "output": {"outputOnFailure": True, "verbosity": "default"},
                        "execution": {"jobs": 1, "timeout": DEFAULT_TEST_TIMEOUT}
                    })

    def add_workflow_presets(self):
        self.presets["workflowPresets"] = []
        template_workflow_groups = self.template_data.get("workflows", [])
        if not template_workflow_groups: return

        for platform_spec in self.template_data.get("platform", []):
            os_name_template = platform_spec.get("os")
            if not os_name_template: continue

            if os_name_template == "Darwin": os_preset_name_part, display_os_name = "mac", "macOS"
            elif os_name_template == "Windows": os_preset_name_part = "windows"; display_os_name = "Windows"
            elif os_name_template == "Linux": os_preset_name_part = "linux"; display_os_name = "Linux"
            else: os_preset_name_part = os_name_template.lower().replace(" ", "-"); display_os_name = os_name_template


            for build_type_suffix in ["debug", "release"]:
                base_configure_preset_ref = f"{os_preset_name_part}-{build_type_suffix}" # e.g. mac-debug
                display_build_type_name = build_type_suffix.capitalize()
                main_build_preset_ref = f"build-{base_configure_preset_ref}" # e.g. build-mac-debug

                for workflow_group in template_workflow_groups:
                    for template_wf_concept_name, template_steps_list in workflow_group.items(): # e.g. "Flow": [...]
                        if not isinstance(template_steps_list, list): continue

                        workflow_preset_name = f"{os_preset_name_part}-{build_type_suffix}-workflow-{template_wf_concept_name.replace(' ', '-').lower()}"
                        current_workflow_actual_steps = [{"type": "configure", "name": base_configure_preset_ref}]

                        for step_spec in template_steps_list:
                            step_type = step_spec.get("type")
                            step_options = step_spec.get("option", {})
                            # Original logic for execute_this_step based on options
                            execute_this_step = all(self._cmake_bool_value(opt_val) == "ON" for _, opt_val in step_options.items()) if step_options else True
                            if not execute_this_step: continue

                            if step_type == "build":
                                cmake_target_name = step_spec.get("target")
                                # Fallback for target name from your original code
                                if not cmake_target_name:
                                    desc_lower = step_spec.get("description", "").lower()
                                    if "clang-format" in desc_lower and "check" not in desc_lower: cmake_target_name = "clang-format"
                                    elif "clang-format-check" in desc_lower: cmake_target_name = "clang-format-check"

                                if cmake_target_name:
                                    build_preset_for_step = f"build-{base_configure_preset_ref}-{cmake_target_name.replace(' ', '-').replace('_', '-').lower()}"
                                    if any(bp["name"] == build_preset_for_step for bp in self.presets.get("buildPresets", [])):
                                        current_workflow_actual_steps.append({"type": "build", "name": build_preset_for_step})
                                    # else: print(f"警告: WF '{workflow_preset_name}' step '{step_spec.get('description')}' build preset '{build_preset_for_step}' not found.")
                                # else: print(f"警告: WF '{workflow_preset_name}' step '{step_spec.get('description')}' missing target.")

                            elif step_type == "test":
                                step_args = step_spec.get("args", {})
                                applicable_build_types = step_args.get("apply_to_build_types", ["debug", "release"])
                                if build_type_suffix in applicable_build_types:
                                    test_preset_ref = f"{os_preset_name_part}-{build_type_suffix}-tests" # e.g. mac-debug-tests
                                    # Your original logic for launcher_test_preset_suffix (simplified here)
                                    # if step_args.get("use_launcher"):
                                    #     launcher_suffix = step_args.get("launcher_test_preset_suffix", f"-{step_spec.get('description','launcher').replace(' ','-').lower()}")
                                    #     test_preset_ref += launcher_suffix

                                    if any(tp["name"] == test_preset_ref for tp in self.presets.get("testPresets", [])):
                                        current_workflow_actual_steps.append({"type": "test", "name": test_preset_ref})
                                    # else: print(f"警告: WF '{workflow_preset_name}' step '{step_spec.get('description')}' test preset '{test_preset_ref}' not found.")

                        # Add main build step after specific target builds
                        if any(bp["name"] == main_build_preset_ref for bp in self.presets.get("buildPresets", [])):
                            current_workflow_actual_steps.append({"type": "build", "name": main_build_preset_ref})
                        # else: print(f"警告: WF '{workflow_preset_name}' missing main build preset '{main_build_preset_ref}'.")

                        if len(current_workflow_actual_steps) > 1: # Has more than just configure
                            self.presets["workflowPresets"].append({
                                "name": workflow_preset_name,
                                "displayName": f"工作流: {template_wf_concept_name} ({display_os_name} {display_build_type_name})",
                                "steps": current_workflow_actual_steps
                            })

    def generate_and_write(self): # Combined generate and write as per your original structure
        self.presets = {} # Reset for a fresh generation
        self.add_version_info()
        self.add_configure_presets()
        self.add_build_presets()
        self.add_test_presets()
        self.add_workflow_presets()
        self._write_presets() # Original write method

    def _write_presets(self): # Your original _write_presets method
        output_path = self.project_dir / "CMakePresets.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(self.presets, f, indent=2, ensure_ascii=False)
            print(f"{GREEN}已在路径 {output_path} 生成 CMakePresets.json{RESET}")
        except IOError as e:
            print(f"{RED}错误：写入 CMakePresets.json 到 {output_path} 失败: {e}{RESET}")
            sys.exit(1) # Original script exits here

# --- Interactive Template Modification Functions (Simplified as per new request) ---
def modify_platform_template_interactive(current_template_data_copy):
    """Allows modification of top-level simple values in platform configurations."""
    platforms = current_template_data_copy.get("platform", [])
    if not platforms:
        print(f"{YELLOW}模板中没有定义平台配置。{RESET}")
        return

    platform_choices = [(i, p.get("os", f"未命名平台 {i}")) for i, p in enumerate(platforms)]

    def platform_formatter(idx, item_tuple):
        return f"{item_tuple[1]} (描述: {platforms[item_tuple[0]].get('description', 'N/A')})"

    chosen_platform_original_idx = display_indexed_menu(
        platform_choices, "请选择要修改其配置的平台:", item_formatter_func=platform_formatter
    )
    if chosen_platform_original_idx == -1: return

    platform_to_edit_idx = platform_choices[chosen_platform_original_idx][0]
    platform_obj = platforms[platform_to_edit_idx]
    platform_os_name = platform_obj.get("os", "未知平台")

    while True:
        print(f"\n{CYAN}当前正在修改平台 '{platform_os_name}' 的模板配置 (仅顶层简单值):{RESET}")
        modifiable_keys = [key for key, value in platform_obj.items() if isinstance(value, (str, int, float, bool))]

        if not modifiable_keys:
            print(f"{YELLOW}平台 '{platform_os_name}' 没有可直接修改的顶层简单类型配置项。{RESET}")
            return

        def key_formatter(idx, key_name): return f"{key_name}: {MAGENTA}{platform_obj.get(key_name)}{RESET}"
        chosen_key_idx = display_indexed_menu(modifiable_keys, f"为 '{platform_os_name}' 选择要修改的配置键:", item_formatter_func=key_formatter)
        if chosen_key_idx == -1: break

        key_to_modify = modifiable_keys[chosen_key_idx]
        old_value = platform_obj[key_to_modify]

        try:
            new_value_str = input(f"当前 '{key_to_modify}' 的值是 '{BLUE}{old_value}{RESET}'. {CYAN}请输入新值 (直接回车取消修改): {RESET}").strip()
            if not new_value_str: print(f"{YELLOW}未修改 '{key_to_modify}'。{RESET}"); continue

            new_value = new_value_str
            if isinstance(old_value, bool):
                if new_value_str.lower() in ['true', 't', 'yes', 'y', '1']: new_value = True
                elif new_value_str.lower() in ['false', 'f', 'no', 'n', '0']: new_value = False
                else: print(f"{YELLOW}布尔值请输入 true/false 等。未修改。{RESET}"); continue
            elif isinstance(old_value, int):
                try: new_value = int(new_value_str)
                except ValueError: print(f"{YELLOW}请输入整数。未修改。{RESET}"); continue
            elif isinstance(old_value, float):
                try: new_value = float(new_value_str)
                except ValueError: print(f"{YELLOW}请输入浮点数。未修改。{RESET}"); continue

            platform_obj[key_to_modify] = new_value
            print(f"{GREEN}模板中平台 '{platform_os_name}' 的配置项 '{key_to_modify}' 已从 '{old_value}' 临时更新为 '{new_value}'。{RESET}")
        except KeyboardInterrupt: print(f"\n{YELLOW}修改已取消。{RESET}"); continue
        except Exception as e: print(f"{RED}修改时发生错误: {e}{RESET}")

def delete_workflow_step_interactive(current_template_data_copy):
    """Allows deletion of entire workflow steps."""
    workflows = current_template_data_copy.get("workflows", [])
    if not workflows or "Flow" not in workflows[0] or not workflows[0].get("Flow"): # Assuming structure {"workflows": [{"Flow": [...]}]}
        print(f"{YELLOW}模板中没有工作流步骤可删除。{RESET}")
        return

    flow_steps = workflows[0]["Flow"]
    if not flow_steps: # Check if Flow list itself is empty
        print(f"{YELLOW}工作流 'Flow' 中没有步骤可删除。{RESET}")
        return

    while True: # Allow deleting multiple steps
        if not flow_steps: # Re-check after a deletion
            print(f"{YELLOW}工作流 'Flow' 中已没有步骤可删除。{RESET}")
            break

        def step_formatter(idx, step): return step.get('description', f'未命名步骤 {idx+1}')
        chosen_step_idx_to_delete = display_indexed_menu(flow_steps, "请选择要删除的工作流步骤 (整个子项将被删除):", item_formatter_func=step_formatter)

        if chosen_step_idx_to_delete == -1: break # User chose to go back

        try:
            removed_step = flow_steps.pop(chosen_step_idx_to_delete)
            print(f"{GREEN}已从模板中删除工作流步骤: '{removed_step.get('description')}'。{RESET}")
        except IndexError:
            print(f"{RED}选择的步骤索引无效。{RESET}")


# --- Main Script Logic ---
def main():
    if pf.system() == "Windows": os.system('')
    print(f"{CYAN}欢迎使用 CMakePresets.json 生成脚本!{RESET}")
    print(f"{YELLOW}提示: 对模板的修改仅影响本次生成，不会保存到脚本源码中的初始模板。{RESET}")

    project_dir_env = os.environ.get("PROJECT_DIR")
    project_dir_path = None
    if not project_dir_env:
        print(f"{YELLOW}警告：未设置 PROJECT_DIR 环境变量。{RESET}")
        while True:
            try:
                user_path_str = input(f"{CYAN}请输入您的项目根目录路径: {RESET}").strip()
                if not user_path_str: print(f"{YELLOW}路径不能为空。{RESET}"); continue
                temp_path = pathlib.Path(user_path_str).resolve()
                if temp_path.is_dir(): project_dir_path = temp_path; break
                else: print(f"{RED}路径 '{temp_path}' 不是一个有效的目录。请重试。{RESET}")
            except KeyboardInterrupt: print(f"\n{YELLOW}用户取消输入，脚本将退出。{RESET}"); sys.exit(0)
            except Exception as e: print(f"{RED}处理路径时发生错误: {e}{RESET}")
    else:
        project_dir_path = pathlib.Path(project_dir_env).resolve()
        if not project_dir_path.is_dir():
            print(f"{RED}错误: PROJECT_DIR ('{project_dir_env}') 指向的路径 '{project_dir_path}' 无效。脚本退出。{RESET}")
            sys.exit(1)
    print(f"{BLUE}项目根目录已设置为: {project_dir_path}{RESET}")

    # Make a mutable copy of the initial template for this session
    current_session_template_data = copy.deepcopy(INITIAL_SOURCE_TEMPLATE_DATA)

    while True:
        print("\n" + "="*15 + f"{MAGENTA} 主菜单 {RESET}" + "="*15)
        main_menu_options = [
            "1. 生成 CMakePresets.json (使用当前模板)",
            "2. 修改当前会话的模板 (仅限平台配置的顶层简单值)",
            "3. 删除当前会话的模板项 (仅限工作流步骤)",
            "4. 查看当前会话的模板数据 (JSON格式)",
            "0. 退出脚本"
        ]
        for opt in main_menu_options: print(opt)

        try:
            user_choice_str = input(f"{CYAN}请输入您的选择: {RESET}").strip()
            if not user_choice_str: continue

            if user_choice_str == "0":
                print(f"{BLUE}脚本退出。{RESET}")
                break
            elif user_choice_str == "1":
                print(f"\n{CYAN}准备使用当前会话的模板数据生成 CMakePresets.json...{RESET}")
                # Use a temporary file to pass the (potentially modified) template to PresetGenerator
                # This keeps PresetGenerator's _load_template logic intact.
                temp_template_file = None
                try:
                    # Create a named temporary file to write the current_session_template_data
                    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json", encoding="utf-8") as tmp_f:
                        json.dump(current_session_template_data, tmp_f, indent=2, ensure_ascii=False)
                        temp_template_file = tmp_f.name

                    # Now, instantiate PresetGenerator with the path to this temporary file
                    generator = PresetGenerator(str(project_dir_path), temp_template_file)
                    generator.generate_and_write() # This will call _load_template with temp_template_file

                except Exception as e:
                    print(f"{RED}在生成或写入预设时发生错误: {e}{RESET}")
                finally:
                    if temp_template_file and os.path.exists(temp_template_file):
                        try:
                            os.unlink(temp_template_file) # Clean up the temporary file
                        except OSError as e_unlink:
                            print(f"{YELLOW}警告: 未能删除临时模板文件 '{temp_template_file}': {e_unlink}{RESET}")
                # Loops back to main menu

            elif user_choice_str == "2":
                modify_platform_template_interactive(current_session_template_data)
            elif user_choice_str == "3":
                delete_workflow_step_interactive(current_session_template_data)
            elif user_choice_str == "4":
                print(f"\n{CYAN}--- 当前会话的模板数据 ---{RESET}")
                try: print(json.dumps(current_session_template_data, indent=2, ensure_ascii=False))
                except Exception as e: print(f"{RED}无法序列化当前模板数据进行显示: {e}{RESET}")
                print(f"{CYAN}--- 模板数据结束 ---{RESET}"); input(f"{BLUE}按回车键继续...{RESET}")
            else:
                print(f"{RED}未知的选择 '{user_choice_str}'。请重试。{RESET}")

        except KeyboardInterrupt:
            print(f"\n{YELLOW}操作已取消，返回主菜单。{RESET}")
            continue
        except Exception as e: # Catch any other unexpected error in the main loop
            print(f"{RED}主菜单处理中发生意外错误: {e}{RESET}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()