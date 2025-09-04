import json
import os
import pathlib
import sys
import copy
import platform as pf  # To avoid conflict with template_data['platform']
import tempfile  # For creating a temporary template file

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


# --- Embedded Source Template Data ---
INITIAL_SOURCE_TEMPLATE_DATA = {
    "platform": [
        {
            "os": "Windows",
            "description": "适用于 MSVC (cl.exe) 的 CMake + Ninja 构建环境配置",
            "generator": "Ninja",
            "CMAKE_CXX_STANDARD": "20",
            "C_COMPILER": "cl",
            "CXX_COMPILER": "cl",
            "debug_flag": {
                "CMAKE_CXX_FLAGS": "/EHsc /W3 /Z7 /FS /MDd /Od /D_ITERATOR_DEBUG_LEVEL=2",
                "CMAKE_C_FLAGS": "/EHsc /W3 /Z7 /FS /MDd  /Od /D_ITERATOR_DEBUG_LEVEL=2"
            },
            "rel_flag": {
                "CMAKE_CXX_FLAGS": "/EHsc /W3  /O2 /FS /MD",
                "CMAKE_C_FLAGS": "/EHsc /W3  /O2 /FS /MD"
            },
            "relwithdebug_flag": {
                "CMAKE_CXX_FLAGS": "/EHsc /W3 /Z7 /FS /MD /O2 /DNDEBUG",
                "CMAKE_C_FLAGS": "/EHsc /W3 /Z7 /FS /MD /O2 /DNDEBUG"
            }
        },

        {
            "os": "Linux",
            "description": "Linux下使用clang和ninja，vcpkg toolchain",
            "generator": "Ninja",
            "CMAKE_CXX_STANDARD": "20",
            "C_COMPILER": "/usr/bin/clang",
            "CXX_COMPILER": "/usr/bin/clang++",
            "debug_flag": {
                "CMAKE_CXX_FLAGS": "-g -O0 -Wall -Wextra -fPIC",
                "CMAKE_C_FLAGS": "-g -O0 -Wall -fPIC",
            },
            "rel_flag": {
                "CMAKE_CXX_FLAGS": "-O2 -DNDEBUG -fPIC",
                "CMAKE_C_FLAGS": "-O2 -DNDEBUG -fPIC",
            },
            "relwithdebug_flag": {
                "CMAKE_CXX_FLAGS": "-O2 -g -DNDEBUG",
                "CMAKE_C_FLAGS": "-O2 -g -DNDEBUG",
            },
        },
        {
            "os": "Darwin",
            "description": "macOS下使用clang和ninja，vcpkg toolchain",
            "generator": "Ninja",
            "CMAKE_CXX_STANDARD": "20",
            "C_COMPILER": "clang",
            "CXX_COMPILER": "clang++",
            "debug_flag": {
                "CMAKE_CXX_FLAGS": "-g -O0 -Wall -Wextra -fPIC",
                "CMAKE_C_FLAGS": "-g -O0 -Wall -fPIC",
            },
            "rel_flag": {
                "CMAKE_CXX_FLAGS": "-O2 -DNDEBUG -fPIC",
                "CMAKE_C_FLAGS": "-O2 -DNDEBUG -fPIC",
            },
            "relwithdebug_flag": {
                "CMAKE_CXX_FLAGS": "-O2 -g -DNDEBUG",
                "CMAKE_C_FLAGS": "-O2 -g -DNDEBUG",
            },
        },
    ],
}



# --- Your PresetGenerator Class (LOGIC UNCHANGED, only __init__ and _load_template are affected by how data is passed) ---
class PresetGenerator:
    def __init__(
        self, project_dir_str: str, template_path_str_or_data: str or dict
    ):  # Can now accept data directly
        self.project_dir = pathlib.Path(project_dir_str).resolve()

        # MODIFICATION: Load template from path OR use directly if dict
        if isinstance(template_path_str_or_data, dict):
            self.template_data = template_path_str_or_data
        elif isinstance(template_path_str_or_data, (str, pathlib.Path)):
            self.template_path = pathlib.Path(template_path_str_or_data)
            self.template_data = self._load_template_from_file()  # Renamed
        else:
            print(f"{RED}错误：无效的模板源类型。{RESET}")
            sys.exit(1)

        if not self.template_data:
            sys.exit(
                1
            )  # Error already printed by _load_template_from_file or check above

        self.presets = {}
    def add_version_info(self):
        self.presets["version"] = PRESET_VERSION
        self.presets["cmakeMinimumRequired"] = {
            "major": PRESET_CMAKE_MIN_MAJOR,
            "minor": PRESET_CMAKE_MIN_MINOR,
            "patch": PRESET_CMAKE_MIN_PATCH,
        }

    def add_configure_presets(self):
        global arch_value, arch_strategy, tool_strategy, tool_value
        self.presets["configurePresets"] = []
        sccache_cache = {
            "CMAKE_C_COMPILER_LAUNCHER": "sccache",
            "CMAKE_CXX_COMPILER_LAUNCHER": "sccache",
        }
        sccache_env = {"SCCACHE_IGNORE_SERVER_IO_ERROR": "1"}
        sccache = {
            "name": "sccache-launcher",
            "hidden": True,
            "cacheVariables": {
                k: v for k, v in sccache_cache.items() if v is not None and v != ""
            },
            "environment": {
                k: v for k, v in sccache_env.items() if v is not None and v != ""
            },
        }
        self.presets["configurePresets"].append(sccache)
        for platform_spec in self.template_data.get("platform", []):
            os_name_template = platform_spec.get("os")
            if not os_name_template:
                continue
            os_preset_name_part = os_name_template.lower()
            display_os_name = os_name_template
            if os_name_template == "Darwin":
                os_preset_name_part, display_os_name = "mac", "macOS"
            base_preset_name = f"{os_preset_name_part}-base"
            if os_name_template == "Windows" and platform_spec.get("C_COMPILER") == "cl":
                current_cache_vars = {
                "CMAKE_C_COMPILER": platform_spec.get("C_COMPILER"),
                "CMAKE_CXX_COMPILER": platform_spec.get("CXX_COMPILER"),
                "CMAKE_CXX_STANDARD": str(platform_spec.get("CMAKE_CXX_STANDARD", "")),
                "CMAKE_MSVC_DEBUG_INFORMATION_FORMAT": "Embedded",
                "CMAKE_POLICY_DEFAULT_CMP0141": "NEW" ,
                "CMAKE_EXPORT_COMPILE_COMMANDS": True,
                }
            else:
                current_cache_vars = {
                    "CMAKE_C_COMPILER": platform_spec.get("C_COMPILER"),
                    "CMAKE_CXX_COMPILER": platform_spec.get("CXX_COMPILER"),
                    "CMAKE_CXX_STANDARD": str(platform_spec.get("CMAKE_CXX_STANDARD", "")),
                    "CMAKE_EXPORT_COMPILE_COMMANDS": True,
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
                        "strategy": toolset_spec.get("strategy"),
                    }
                if arch_value and arch_strategy:
                    current_architecture_vars = {
                        "value": arch_value,
                        "strategy": arch_strategy,
                    }
            final_base_cache_vars = current_cache_vars.copy()
            if os_name_template == "Windows":
                realGenerator = platform_spec.get("generator")
                if realGenerator == "Ninja":
                    base_configure_preset_obj = {
                        "name": base_preset_name,
                        "hidden": True,
                        "displayName": f"{display_os_name} Base",
                        "description": platform_spec.get(
                            "description", f"{display_os_name} 的基础配置"
                        ),
                        "generator": platform_spec.get("generator", "Ninja"),
                        "binaryDir": f"${{sourceDir}}/{DEFAULT_BINARY_DIR_SUFFIX}",
                        "cacheVariables": {
                            k: v
                            for k, v in final_base_cache_vars.items()
                            if v is not None and v != ""
                        },
                    }
                else:
                    base_configure_preset_obj = {
                        "name": base_preset_name,
                        "hidden": True,
                        "displayName": f"{display_os_name} Base",
                        "description": platform_spec.get(
                            "description", f"{display_os_name} 的基础配置"
                        ),
                        "generator": platform_spec.get("generator"),
                        "binaryDir": f"${{sourceDir}}/{DEFAULT_BINARY_DIR_SUFFIX}",
                        "architecture": {
                            k: v
                            for k, v in current_architecture_vars.items()
                            if v is not None and v != ""
                        },
                        "toolset": {
                            k: v
                            for k, v in current_toolset_vars.items()
                            if v is not None and v != ""
                        },
                        "cacheVariables": {
                            k: v
                            for k, v in final_base_cache_vars.items()
                            if v is not None and v != ""
                        },
                    }
            else:
                base_configure_preset_obj = {
                    "name": base_preset_name,
                    "hidden": True,
                    "displayName": f"{display_os_name} Base",
                    "description": platform_spec.get(
                        "description", f"{display_os_name} 的基础配置"
                    ),
                    "generator": platform_spec.get("generator", "Ninja"),
                    "binaryDir": f"${{sourceDir}}/{DEFAULT_BINARY_DIR_SUFFIX}",
                    "cacheVariables": {
                        k: v
                        for k, v in final_base_cache_vars.items()
                        if v is not None and v != ""
                    },
                }
            self.presets["configurePresets"].append(base_configure_preset_obj)
            for build_type in ["Debug", "Release", "RelWithDebInfo"]:
                concrete_config_preset_name = (
                    f"{os_preset_name_part}-{build_type.lower()}"
                )
                display_build_type = build_type
                flag_map = {
                    "debug": "debug_flag",
                    "release": "rel_flag",
                    "relwithdebinfo": "relwithdebug_flag",
                }
                flags_key = flag_map.get(build_type.lower(), "relwithdebug_flag")
                flags = platform_spec.get(flags_key, {})
                cfg_specific_cache_vars = {"CMAKE_BUILD_TYPE": display_build_type}
                if flags.get("CMAKE_CXX_FLAGS"):
                    cfg_specific_cache_vars["CMAKE_CXX_FLAGS"] = flags.get(
                        "CMAKE_CXX_FLAGS"
                    )
                if flags.get("CMAKE_C_FLAGS"):
                    cfg_specific_cache_vars["CMAKE_C_FLAGS"] = flags.get(
                        "CMAKE_C_FLAGS"
                    )
                cfg_specific_cache_vars["CMAKE_RUNTIME_OUTPUT_DIRECTORY"] = (
                    f"${{sourceDir}}/{DEFAULT_BINARY_DIR_SUFFIX}/{DEFAULT_RUNTIME_OUTPUT_DIR_SUFFIX}"
                )
                cfg_inherits = [base_preset_name, "sccache-launcher"]
                cfg_preset = {
                    "name": concrete_config_preset_name,
                    "displayName": f"{display_os_name} {display_build_type}",
                    "inherits": cfg_inherits,
                    "condition": {
                        "type": "equals",
                        "lhs": "${hostSystemName}",
                        "rhs": os_name_template,
                    },
                    "binaryDir": f"${{sourceDir}}/{DEFAULT_BINARY_DIR_SUFFIX}",
                    "cacheVariables": cfg_specific_cache_vars,
                }
                self.presets["configurePresets"].append(cfg_preset)

    def add_build_presets(self):
        self.presets["buildPresets"] = []
        all_build_step_targets = set()

        for platform_spec in self.template_data.get("platform", []):
            os_name_template = platform_spec.get("os")
            if not os_name_template:
                continue
            os_preset_name_part = os_name_template.lower()
            display_os_name = os_name_template
            if os_name_template == "Darwin":
                os_preset_name_part, display_os_name = "mac", "macOS"

            for build_type_suffix in ["Debug", "Release", "RelWithDebInfo"]:
                configure_preset_ref = (
                    f"{os_preset_name_part}-{build_type_suffix.lower()}"
                )
                display_build_type_name = build_type_suffix
                # Main build preset
                self.presets["buildPresets"].append(
                    {
                        "name": f"build-{configure_preset_ref}",
                        "configurePreset": configure_preset_ref,
                        "jobs": DEFAULT_BUILD_JOBS,
                        "displayName": f"构建主项目 ({display_os_name} {display_build_type_name})",
                    }
                )
                # Build presets for specific targets collected from template
                for target_name in all_build_step_targets:
                    build_preset_name = f"build-{configure_preset_ref}-{target_name.replace(' ', '-').lower()}"
                    self.presets["buildPresets"].append(
                        {
                            "name": build_preset_name,
                            "targets": [target_name],
                            "configurePreset": configure_preset_ref,
                            "displayName": f"构建目标 '{target_name}' ({display_os_name} {display_build_type_name})",
                        }
                    )

    def generate_and_write(
        self,
    ):  # Combined generate and write as per your original structure
        self.presets = {}  # Reset for a fresh generation
        self.add_version_info()
        self.add_configure_presets()
        self.add_build_presets()
        self._write_presets()  # Original write method

    def _write_presets(self):  # Your original _write_presets method
        output_path = self.project_dir / "CMakePresets.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(self.presets, f, indent=2, ensure_ascii=False)
            print(f"{GREEN}已在路径 {output_path} 生成 CMakePresets.json{RESET}")
        except IOError as e:
            print(
                f"{RED}错误：写入 CMakePresets.json 到 {output_path} 失败: {e}{RESET}"
            )
            sys.exit(1)  # Original script exits here


def main():
    print(f"{BLUE}开始生成 CMakePresets.json...{RESET}")
    
    # 从脚本自身路径向上查找项目根目录
    try:
        # __file__ 在标准Python解释器中可用
        current_script_path = pathlib.Path(__file__).resolve()
    except NameError:
        # 在某些交互式环境（如Jupyter）中，__file__ 未定义
        current_script_path = pathlib.Path(os.getcwd()).resolve()

    project_dir_path = None
    path_iterator = current_script_path
    # 向上遍历目录，直到找到包含 .vscode 的目录或到达文件系统根目录
    while path_iterator.parent != path_iterator:
        if (path_iterator / ".vscode").is_dir():
            project_dir_path = path_iterator
            break
        path_iterator = path_iterator.parent
        
    if not project_dir_path:
        print(f"{RED}错误：无法从 '{current_script_path}' 向上找到包含 '.vscode' 的父目录。脚本退出。{RESET}")
        sys.exit(1)

    print(f"{BLUE}项目根目录已确定为: {project_dir_path}{RESET}")

    # 直接使用内置模板数据
    template_data = copy.deepcopy(INITIAL_SOURCE_TEMPLATE_DATA)

    # 实例化并生成文件
    try:
        generator = PresetGenerator(str(project_dir_path), template_data)
        generator.generate_and_write()
        print(f"{GREEN}脚本执行成功！{RESET}")
    except Exception as e:
        print(f"{RED}在生成过程中发生错误: {e}{RESET}")
        sys.exit(1)


if __name__ == "__main__":
    main()
