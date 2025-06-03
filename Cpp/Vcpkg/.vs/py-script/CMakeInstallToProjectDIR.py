import json
import os
import platform
import subprocess
from pathlib import Path
import shlex
import re
import sys
import threading
import shutil # For shutil.rmtree

# --- ANSI Color Codes ---
RED = "\033[91m"
YELLOW = "\033[93m"
GREEN = "\033[92m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
RESET = "\033[0m"

# --- Global Variables / State ---
global_env = os.environ.copy()
project_dir = None
presets_data = None
current_os = None
all_presets_map = None # For quick lookups by name

# State for the current session
selected_configure_preset_name = None
selected_configure_preset_obj = None # Store the actual preset object
current_build_dir = None
current_install_dir = None

# --- Core Helper Functions (largely from previous cmake_helper.py) ---

def color_line(line):
    if re.search(r'\berror\b', line, re.IGNORECASE) or \
            re.search(r'CMake Error', line) or \
            re.search(r'ninja: error:', line, re.IGNORECASE): # Ninja specific error
        return RED + line + RESET
    elif re.search(r'\bwarning\b', line, re.IGNORECASE) or \
            re.search(r'CMake Warning', line):
        return YELLOW + line + RESET
    return line

def stream_output(stream, color_func):
    try:
        for line_str in iter(stream.readline, ''):
            sys.stdout.write(color_func(line_str))
            sys.stdout.flush()
        stream.close()
    except Exception as e:
        sys.stdout.write(f"{RED}读取流时发生错误: {e}{RESET}\n")
        sys.stdout.flush()

def run_command_realtime_color(command_parts, env_vars, cwd_path=None, error_msg="命令执行失败"):
    try:
        command_to_display = ' '.join(shlex.quote(str(part)) for part in command_parts)
        print(f"\n{BLUE}▶️  执行命令:{RESET} {command_to_display}")
        if cwd_path:
            print(f"{BLUE}  (在目录:{RESET} {cwd_path})")

        process = subprocess.Popen(
            command_parts,
            env=env_vars,
            cwd=cwd_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='replace',
            bufsize=1,
            shell=False
        )
        stdout_thread = threading.Thread(target=stream_output, args=(process.stdout, color_line))
        stderr_thread = threading.Thread(target=stream_output, args=(process.stderr, color_line))
        stdout_thread.start()
        stderr_thread.start()
        stdout_thread.join()
        stderr_thread.join()
        return_code = process.wait()

        if return_code == 0:
            print(f"{GREEN}✅ 命令成功执行 (返回码: {return_code})。{RESET}")
            return True
        else:
            print(f"{RED}❌ {error_msg} (返回码: {return_code})。{RESET}")
            return False
    except FileNotFoundError:
        print(f"{RED}❌ 错误: 命令 '{command_parts[0]}' 未找到。请确保它已安装并在系统 PATH 中。{RESET}")
        return False
    except Exception as e:
        print(f"{RED}❌ 执行命令时发生未知错误: {e}{RESET}")
        return False

def load_presets_data_global(p_dir_str):
    global presets_data, all_presets_map
    presets_file = Path(p_dir_str) / "CMakePresets.json"
    try:
        with open(presets_file, 'r', encoding='utf-8') as f:
            presets_data = json.load(f)
            all_presets_map = get_all_presets_by_name_internal(presets_data) # Populate map
            return True
    except FileNotFoundError:
        print(f"{RED}错误: CMakePresets.json 文件未在 '{presets_file}' 找到。{RESET}")
    except json.JSONDecodeError:
        print(f"{RED}错误: CMakePresets.json 文件 '{presets_file}' 格式无效。{RESET}")
    except Exception as e:
        print(f"{RED}加载 CMakePresets.json 文件 '{presets_file}' 时发生错误: {e}{RESET}")
    presets_data = None
    all_presets_map = {}
    return False

def get_current_os_name_global():
    global current_os
    system = platform.system()
    if system == "Darwin": current_os = "Darwin"
    elif system == "Windows": current_os = "Windows"
    elif system == "Linux": current_os = "Linux"
    else: current_os = system
    return current_os

def is_preset_condition_met(preset, os_name):
    if 'condition' not in preset: return True
    condition = preset['condition']
    if isinstance(condition, bool): return condition
    if isinstance(condition, dict):
        cond_type, cond_lhs, cond_rhs = condition.get('type'), condition.get('lhs'), condition.get('rhs')
        if cond_lhs == '${hostSystemName}':
            if cond_type == 'equals': return cond_rhs == os_name
            if cond_type == 'notEquals': return cond_rhs != os_name
        if cond_type == 'always': return True
        if cond_type == 'never': return False
    return False

def get_all_presets_by_name_internal(p_data):
    _all_presets = {}
    for preset_type_key in ['configurePresets', 'buildPresets', 'testPresets', 'packagePresets', 'workflowPresets']:
        for preset in p_data.get(preset_type_key, []):
            if 'name' in preset:
                _all_presets[preset['name']] = preset
    return _all_presets

def is_preset_visible_and_valid(preset, os_name):
    if preset.get('hidden', False): return False
    return is_preset_condition_met(preset, os_name)

def get_visible_presets_by_type(preset_type_key, os_name):
    if not presets_data: return []
    visible_presets = []
    for preset in presets_data.get(preset_type_key, []):
        if is_preset_visible_and_valid(preset, os_name):
            visible_presets.append(preset)
    return visible_presets

def get_inherited_variable(preset_name, variable_name):
    """Recursively search for a variable in a preset and its inherited presets."""
    if not all_presets_map or preset_name not in all_presets_map:
        return None

    current_preset = all_presets_map[preset_name]

    # Check in current preset's cacheVariables
    if "cacheVariables" in current_preset and variable_name in current_preset["cacheVariables"]:
        return current_preset["cacheVariables"][variable_name]

    # Check in current preset directly (for things like binaryDir, not in cacheVariables)
    if variable_name in current_preset:
        return current_preset[variable_name]

    # Recurse up the inheritance chain (single inheritance for now)
    inherits_from = current_preset.get("inherits")
    if inherits_from:
        if isinstance(inherits_from, list): # CMakePresets v4+ allows multiple inheritance
            for inherited_preset_name in reversed(inherits_from): # Last one wins
                val = get_inherited_variable(inherited_preset_name, variable_name)
                if val is not None:
                    return val
        elif isinstance(inherits_from, str):
            return get_inherited_variable(inherits_from, variable_name)

    return None


def display_menu_and_get_choice(options_list, prompt_message="请选择一个选项:"):
    print(f"\n{BLUE}{prompt_message}{RESET}")
    if not options_list:
        print(f"{YELLOW}没有可用选项。{RESET}")
        return 0, None
    menu_items = [(item.get('displayName', item['name']), item['name']) for item in options_list]
    for i, (display_name, actual_name) in enumerate(menu_items):
        print(f"  {i + 1}. {display_name}" + (f" ({MAGENTA}{actual_name}{RESET})" if display_name != actual_name else ""))
    print(f"  0. 返回/退出")
    while True:
        try:
            choice_str = input("请输入您的选择: ")
            choice = int(choice_str)
            if 0 <= choice <= len(menu_items):
                return choice, menu_items[choice - 1][1] if choice > 0 else None
            else: print(f"{YELLOW}无效的选择。请重试。{RESET}")
        except ValueError: print(f"{YELLOW}无效的输入。请输入数字。{RESET}")
        except KeyboardInterrupt: print(f"\n{YELLOW}操作已取消。{RESET}"); raise

def get_cmake_exe_name():
    return "cmake.bat" if current_os == "Windows" else "cmake" # Assuming cmake.bat shim

# --- Action Handlers ---
def do_cleanup(target_dir, dir_description):
    print(f"{CYAN}正在清理旧的 {dir_description} 目录: {target_dir}{RESET}")
    if target_dir.exists():
        try:
            shutil.rmtree(target_dir)
            print(f"{GREEN}已删除: {target_dir}{RESET}")
        except OSError as e:
            print(f"{RED}错误：删除 {dir_description} {target_dir} 时出错: {e}{RESET}")
            return False
    else:
        print(f"{BLUE}{dir_description} {target_dir} 不存在，无需清理。{RESET}")
    return True

def handle_configure():
    global selected_configure_preset_name, selected_configure_preset_obj, current_build_dir, current_install_dir

    visible_cfg_presets = get_visible_presets_by_type('configurePresets', current_os)
    if not visible_cfg_presets:
        print(f"{YELLOW}对于操作系统 '{current_os}'，没有找到可见的配置预设。{RESET}")
        return False

    choice_idx, chosen_name = display_menu_and_get_choice(visible_cfg_presets, "请选择 CMake 配置预设:")
    if choice_idx == 0 or not chosen_name: return False

    selected_configure_preset_name = chosen_name
    selected_configure_preset_obj = all_presets_map.get(chosen_name) # Get the full object

    # Determine Build Directory from preset's binaryDir
    binary_dir_template = get_inherited_variable(selected_configure_preset_name, "binaryDir")
    if not binary_dir_template:
        print(f"{RED}错误: 配置预设 '{selected_configure_preset_name}' 未定义 'binaryDir'。{RESET}")
        selected_configure_preset_name = None # Reset state
        return False
    current_build_dir = Path(binary_dir_template.replace("${sourceDir}", str(project_dir))).resolve()
    print(f"{CYAN}构建目录将位于 (来自预设 '{selected_configure_preset_name}'): {current_build_dir}{RESET}")

    # Determine Install Directory
    install_prefix_from_preset = get_inherited_variable(selected_configure_preset_name, "CMAKE_INSTALL_PREFIX")
    install_dir_name_rel = None

    if install_prefix_from_preset:
        # If preset defines CMAKE_INSTALL_PREFIX, it might be absolute or relative to sourceDir
        if Path(install_prefix_from_preset).is_absolute():
            current_install_dir = Path(install_prefix_from_preset).resolve()
            print(f"{CYAN}安装目录将位于 (来自预设的绝对路径 CMAKE_INSTALL_PREFIX): {current_install_dir}{RESET}")
        else:
            # Assume relative to sourceDir if not absolute
            current_install_dir = (project_dir / install_prefix_from_preset).resolve()
            print(f"{CYAN}安装目录将位于 (来自预设的相对路径 CMAKE_INSTALL_PREFIX): {current_install_dir}{RESET}")
    else:
        while True:
            try:
                rel_install_path_str = input(f"{BLUE}预设 '{selected_configure_preset_name}' 未指定 CMAKE_INSTALL_PREFIX。\n请输入相对于项目根目录 ({project_dir}) 的安装目录名称 (例如 'installed_release'): {RESET}").strip()
                if not rel_install_path_str:
                    print(f"{YELLOW}安装目录名称不能为空。请重试。{RESET}")
                    continue
                if Path(rel_install_path_str).is_absolute():
                    print(f"{YELLOW}请输入相对路径。'{rel_install_path_str}' 是绝对路径。{RESET}")
                    continue
                current_install_dir = (project_dir / rel_install_path_str).resolve()
                break
            except KeyboardInterrupt: print(f"\n{YELLOW}输入已取消。{RESET}"); return False

    print(f"{CYAN}最终安装目录将是: {current_install_dir}{RESET}")

    # Optional: Clean build and install dirs before configure
    clean_opt = input(f"{BLUE}是否在配置前清理构建目录 ({current_build_dir}) 和安装目录 ({current_install_dir})? (y/N): {RESET}").strip().lower()
    if clean_opt == 'y':
        if not do_cleanup(current_build_dir, "构建目录"): return False # propagate failure
        if not do_cleanup(current_install_dir, "安装目录"): return False


    configure_cmd = [
        get_cmake_exe_name(),
        "--preset", selected_configure_preset_name,
        f"-DCMAKE_INSTALL_PREFIX={current_install_dir}", # Crucial override/set
    ]
    success = run_command_realtime_color(configure_cmd, global_env, cwd_path=project_dir, error_msg="CMake 配置失败")
    if not success:
        selected_configure_preset_name = None # Reset state on failure
        current_build_dir = None
        current_install_dir = None
    return success

def handle_build():
    if not selected_configure_preset_name or not current_build_dir:
        print(f"{YELLOW}请先成功运行配置步骤。{RESET}")
        return False

    # Filter build presets compatible with the selected configure preset
    compatible_build_presets = []
    for bp in get_visible_presets_by_type('buildPresets', current_os):
        if bp.get('configurePreset') == selected_configure_preset_name:
            compatible_build_presets.append(bp)

    if not compatible_build_presets:
        print(f"{YELLOW}没有找到与配置预设 '{selected_configure_preset_name}' 兼容的可见构建预设。{RESET}")
        return False

    choice_idx, chosen_build_preset_name = display_menu_and_get_choice(
        compatible_build_presets, f"为配置 '{selected_configure_preset_name}' 选择构建预设:"
    )
    if choice_idx == 0 or not chosen_build_preset_name: return False

    build_cmd = [
        get_cmake_exe_name(),
        "--build",
        "--preset", chosen_build_preset_name,
    ]
    return run_command_realtime_color(build_cmd, global_env, cwd_path=project_dir, error_msg="CMake 构建失败")

def handle_install():
    if not selected_configure_preset_name or not current_build_dir:
        print(f"{YELLOW}请先成功运行配置和构建步骤 (以确定构建目录)。{RESET}")
        return False
    if not current_install_dir : # Should be set during configure
        print(f"{YELLOW}安装目录未设定。请先运行配置步骤。{RESET}")
        return False

    if not current_build_dir.is_dir():
        print(f"{RED}错误：构建目录 {current_build_dir} 不存在。无法执行安装。{RESET}")
        return False

    # Determine build type for --config if necessary. Usually CMAKE_BUILD_TYPE is in configure preset.
    build_type = get_inherited_variable(selected_configure_preset_name, "CMAKE_BUILD_TYPE")

    install_cmd = [get_cmake_exe_name(), "--install", str(current_build_dir)]
    if build_type: # Add --config only if build_type is known (e.g. for multi-config generators)
        # For single-config generators like Ninja with presets, CMAKE_BUILD_TYPE is set at configure time
        # and --config for install might not be strictly needed or could conflict if preset implies a different type.
        # However, it's often harmless or beneficial for explicitness.
        is_multi_config_generator = selected_configure_preset_obj.get("generator", "").lower() in ["visual studio", "xcode"] # Simplistic check
        if is_multi_config_generator or "Ninja Multi-Config" in selected_configure_preset_obj.get("generator", ""):
            install_cmd.extend(["--config", build_type])


    print(f"{CYAN}将从 '{current_build_dir}' 安装到 '{current_install_dir}' (类型: {build_type or '未指定'}){RESET}")
    return run_command_realtime_color(install_cmd, global_env, cwd_path=project_dir, error_msg="CMake 安装失败")

def handle_clean_selected_build_dir():
    # This reuses the logic for cleaning based on a configure preset's binaryDir
    if not selected_configure_preset_name or not current_build_dir:
        print(f"{YELLOW}没有活动的配置预设或构建目录以供清理。请先配置。{RESET}")
        print(f"{BLUE}你可以从主菜单选择 '清理 (选择预设)' 来清理任意预设的构建目录。{RESET}")
        return False

    print(f"{CYAN}将清理当前活动配置预设 '{selected_configure_preset_name}' 的构建目录。{RESET}")
    return do_cleanup(current_build_dir, f"构建目录 ({selected_configure_preset_name})")


def handle_clean_any_build_dir(): # Similar to original cmake_helper
    visible_cfg_presets = get_visible_presets_by_type('configurePresets', current_os)
    if not visible_cfg_presets:
        print(f"{YELLOW}对于操作系统 '{current_os}'，没有找到可见的配置预设。{RESET}")
        return False

    choice_idx, chosen_name = display_menu_and_get_choice(visible_cfg_presets, "请选择要清理其构建目录的配置预设:")
    if choice_idx == 0 or not chosen_name: return False

    binary_dir_template = get_inherited_variable(chosen_name, "binaryDir")
    if not binary_dir_template:
        print(f"{RED}错误: 配置预设 '{chosen_name}' 未定义 'binaryDir'。{RESET}")
        return False

    dir_to_clean = Path(binary_dir_template.replace("${sourceDir}", str(project_dir))).resolve()

    # Delete CMakeCache.txt first
    cache_file = dir_to_clean / "CMakeCache.txt"
    if cache_file.exists():
        print(f"{CYAN}正在删除 CMakeCache.txt from {dir_to_clean}{RESET}")
        try:
            cache_file.unlink()
        except OSError as e:
            print(f"{RED}删除 CMakeCache.txt 失败: {e}{RESET}")
            # Continue to attempt cleaning targets

    # Then try `cmake --build <dir> --target clean`
    # This is often more thorough than just deleting the directory if a clean target exists
    clean_cmd = [get_cmake_exe_name(), "--build", str(dir_to_clean), "--target", "clean"]
    print(f"{CYAN}尝试执行 'target clean' for {dir_to_clean}{RESET}")
    run_command_realtime_color(clean_cmd, global_env, cwd_path=project_dir, error_msg=f"CMake 'target clean' for {chosen_name} 失败 (可能目标不存在)")
    # Regardless of target clean success, proceed to rmtree as a fallback or primary clean

    print(f"{CYAN}正在执行目录删除 for {dir_to_clean}{RESET}")
    return do_cleanup(dir_to_clean, f"构建目录 ({chosen_name})")


# --- Main Application Logic ---
def main_script_logic():
    global project_dir # Allow modification

    # 1. Get Project Directory
    project_dir_env = os.environ.get('PROJECT_DIR')
    if not project_dir_env:
        # Fallback: try to get from script argument if PROJECT_DIR is not set
        if len(sys.argv) > 1 and Path(sys.argv[1]).is_dir():
            project_dir_env = sys.argv[1]
            print(f"{BLUE}PROJECT_DIR 环境变量未设置，使用脚本参数: {project_dir_env}{RESET}")
        else:
            # Fallback: ask user for project directory
            while True:
                try:
                    user_path = input(f"{YELLOW}PROJECT_DIR 环境变量未设置。请输入项目根目录路径: {RESET}").strip()
                    if not user_path: print(f"{RED}路径不能为空。{RESET}"); continue
                    temp_path = Path(user_path).resolve()
                    if temp_path.is_dir():
                        project_dir_env = str(temp_path)
                        os.environ['PROJECT_DIR'] = project_dir_env # Set it for this session
                        print(f"{BLUE}项目目录设置为: {project_dir_env}{RESET}")
                        break
                    else:
                        print(f"{RED}路径 '{temp_path}' 不是一个有效的目录。请重试。{RESET}")
                except KeyboardInterrupt: print(f"\n{YELLOW}输入已取消。{RESET}"); return
                except Exception as e: print(f"{RED}输入路径时出错: {e}{RESET}")

    if not project_dir_env: # Still not set after prompts
        print(f"{RED}无法确定项目目录。脚本将退出。{RESET}")
        return

    project_dir = Path(project_dir_env).resolve()
    if not project_dir.is_dir():
        print(f"{RED}错误：PROJECT_DIR 指向的路径 '{project_dir}' 不是一个有效的目录。{RESET}")
        return

    print(f"{CYAN}项目根目录: {project_dir}{RESET}")

    # 2. Load Presets and OS
    if not load_presets_data_global(str(project_dir)): return
    get_current_os_name_global()
    print(f"{CYAN}当前操作系统: {current_os}{RESET}")

    # Main interaction loop
    while True:
        print("\n" + "="*15 + f"{MAGENTA} 主菜单 {RESET}" + "="*15)
        if selected_configure_preset_name:
            print(f"{CYAN}当前活动配置: {selected_configure_preset_name}{RESET}")
            print(f"{CYAN}  构建目录: {current_build_dir}{RESET}")
            print(f"{CYAN}  安装目录: {current_install_dir}{RESET}")

        menu_options_display = [
            "1. 配置 (选择预设并设置安装目录)",
            "2. 构建 (使用当前配置)",
            "3. 安装 (使用当前配置)",
            "4. 完整流程 (清理 -> 配置 -> 构建 -> 安装)",
            "5. 清理当前活动构建目录",
            "6. 清理 (选择预设的构建目录)",
            "0. 退出"
        ]
        for opt in menu_options_display: print(opt)

        try:
            choice_str = input(f"{BLUE}请输入您的选择: {RESET}").strip()
            if not choice_str: continue # Handle empty input

            if choice_str == '1': handle_configure()
            elif choice_str == '2': handle_build()
            elif choice_str == '3': handle_install()
            elif choice_str == '4':
                print(f"\n{CYAN}--- 开始完整流程 ---{RESET}")
                if handle_configure(): # Configure handles its own cleaning prompt
                    if handle_build():
                        handle_install()
                print(f"{CYAN}--- 完整流程结束 ---{RESET}")
            elif choice_str == '5': handle_clean_selected_build_dir()
            elif choice_str == '6': handle_clean_any_build_dir()
            elif choice_str == '0': print(f"{BLUE}正在退出脚本。{RESET}"); break
            else: print(f"{YELLOW}无效的选择 '{choice_str}'。请重试。{RESET}")
        except KeyboardInterrupt: print(f"\n{YELLOW}操作已取消，返回主菜单。{RESET}"); continue
        except Exception as e:
            print(f"{RED}主循环中发生意外错误: {e}{RESET}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    if platform.system() == "Windows":
        os.system('') # Attempt to enable ANSI on Windows
    main_script_logic()