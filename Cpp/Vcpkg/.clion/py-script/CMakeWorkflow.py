import json
import os
import platform
import subprocess
from pathlib import Path
import shlex
import re # 新增
import sys # 新增
import threading # 新增

# ANSI 转义码
RED = "\033[91m"
YELLOW = "\033[93m"
GREEN = "\033[92m" # 用于成功信息
BLUE = "\033[94m"  # 用于提示信息
RESET = "\033[0m"

# 获取当前环境变量（副本）
global_env = os.environ.copy()

def color_line(line):
    """根据行内容应用 ANSI 颜色转义码。"""
    # MSVC and GCC/Clang error/warning patterns
    # General "error" or "warning"
    if re.search(r'\berror\b', line, re.IGNORECASE) or \
            re.search(r'CMake Error', line): # CMake specific error
        return RED + line + RESET
    elif re.search(r'\bwarning\b', line, re.IGNORECASE) or \
            re.search(r'CMake Warning', line): # CMake specific warning
        return YELLOW + line + RESET
    return line

def stream_output(stream, color_func):
    """从流中读取数据，着色后输出到 sys.stdout。"""
    try:
        # 使用 text=True 时，stream 会是文本流，可以直接迭代 readline
        for line_str in iter(stream.readline, ''):
            sys.stdout.write(color_func(line_str))
            sys.stdout.flush() # 确保立即输出
        stream.close()
    except Exception as e:
        # 确保错误信息本身也被着色，如果可能的话
        sys.stdout.write(f"{RED}读取流时发生错误: {e}{RESET}\n")
        sys.stdout.flush()


def run_command(command_parts, env, cwd_path=None):
    """执行命令，实时着色其 stdout 和 stderr 输出。"""
    try:
        # 使用 shlex.join 来安全地将列表转换为适合打印的命令字符串
        # (注意：实际执行时 Popen 仍使用列表形式的 command_parts)
        command_to_display = ' '.join(shlex.quote(str(part)) for part in command_parts)
        print(f"\n{BLUE}▶️  执行命令:{RESET} {command_to_display}")
        if cwd_path:
            print(f"{BLUE}  (在目录:{RESET} {cwd_path})")

        process = subprocess.Popen(
            command_parts, # 应该是列表形式，shell=False
            env=env,
            cwd=cwd_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True, # 使 stdout/stderr 成为文本流
            encoding='utf-8',
            errors='replace', #替换无法解码的字符
            bufsize=1,        # 行缓冲
            shell=False       # 为了安全性和可预测性，使用 False
        )

        stdout_thread = threading.Thread(target=stream_output, args=(process.stdout, color_line))
        stderr_thread = threading.Thread(target=stream_output, args=(process.stderr, color_line))

        stdout_thread.start()
        stderr_thread.start()

        stdout_thread.join()
        stderr_thread.join()

        return_code = process.wait() # 等待进程结束并获取返回码

        if return_code == 0:
            print(f"{GREEN}✅ 命令成功执行 (返回码: {return_code})。{RESET}")
            return True
        else:
            print(f"{RED}❌ 命令执行失败 (返回码: {return_code})。{RESET}")
            return False

    except FileNotFoundError:
        print(f"{RED}❌ 错误: 命令 '{command_parts[0]}' 未找到。请确保它已安装并在系统 PATH 中。{RESET}")
        return False
    except Exception as e:
        print(f"{RED}❌ 执行命令时发生未知错误: {e}{RESET}")
        # import traceback # 可选，用于调试
        # traceback.print_exc() # 可选，用于调试
        return False

def load_presets_data(project_dir_str):
    """加载并解析 CMakePresets.json 文件。"""
    presets_file = Path(project_dir_str) / "CMakePresets.json"
    try:
        with open(presets_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"{RED}错误: CMakePresets.json 文件未在 '{presets_file}' 找到。{RESET}")
        return None
    except json.JSONDecodeError:
        print(f"{RED}错误: CMakePresets.json 文件 '{presets_file}' 格式无效。{RESET}")
        return None
    except Exception as e:
        print(f"{RED}加载 CMakePresets.json 文件 '{presets_file}' 时发生错误: {e}{RESET}")
        return None

def get_current_os_name():
    """获取当前操作系统的规范名称 (Windows, Linux, Darwin)。"""
    system = platform.system()
    if system == "Darwin": return "Darwin"  # macOS
    if system == "Windows": return "Windows"
    if system == "Linux": return "Linux"
    return system

def is_preset_condition_met(preset, current_os_name, debug_prefix=""):
    """检查预设的 'condition' 是否满足当前操作系统。"""
    preset_name = preset.get('name', "Unnamed")
    if 'condition' not in preset: return True
    condition = preset['condition']
    if isinstance(condition, bool): return condition
    if isinstance(condition, dict):
        cond_type = condition.get('type')
        cond_lhs = condition.get('lhs')
        cond_rhs = condition.get('rhs')
        if cond_lhs == '${hostSystemName}':
            if cond_type == 'equals': return cond_rhs == current_os_name
            if cond_type == 'notEquals': return cond_rhs != current_os_name
        if cond_type == 'always': return True
        if cond_type == 'never': return False
        return False
    return False

def get_all_presets_by_name(presets_data):
    """将所有类型的预设按名称存入字典，方便查找。"""
    all_presets = {}
    for preset_type_key in ['configurePresets', 'buildPresets', 'testPresets', 'packagePresets', 'workflowPresets']:
        for preset in presets_data.get(preset_type_key, []):
            if 'name' in preset:
                all_presets[preset['name']] = preset
    return all_presets

def is_preset_visible_and_valid(preset, current_os_name, debug_prefix=""):
    """检查预设是否可见 (非隐藏) 且其条件满足当前操作系统。"""
    if preset.get('hidden', False): return False
    return is_preset_condition_met(preset, current_os_name, debug_prefix)

def get_all_valid_configure_preset_names_for_os(presets_data, current_os_name, all_presets_map):
    """获取对当前操作系统其自身条件满足的配置预设 (configurePresets) 的名称集合。"""
    valid_names = set()
    for preset in presets_data.get('configurePresets', []):
        name = preset.get('name')
        if not name: continue
        if is_preset_condition_met(preset, current_os_name, debug_prefix=f"  CfgValid Check (direct for {name}): "):
            valid_names.add(name)
    return valid_names

def get_visible_configure_presets_for_os(presets_data, current_os_name, all_presets_map):
    """获取对当前操作系统可见 (非隐藏且条件满足) 的配置预设列表。"""
    visible_and_valid_presets = []
    for preset in presets_data.get('configurePresets', []):
        if is_preset_visible_and_valid(preset, current_os_name, debug_prefix="  VisibleCfgCheck: "):
            visible_and_valid_presets.append(preset)
    return visible_and_valid_presets

def get_dependent_presets(preset_list_key, presets_data, valid_cfg_names, current_os, all_presets_map):
    """获取特定类型 (构建、测试、打包) 的活动预设。"""
    active_presets = []
    for preset in presets_data.get(preset_list_key, []):
        name = preset.get('name', 'N/A_DepPreset')
        if not is_preset_visible_and_valid(preset, current_os, debug_prefix=f"    Dep Check '{name}': "):
            continue
        cfg_name = preset.get('configurePreset')
        if not cfg_name or cfg_name not in valid_cfg_names:
            continue
        active_presets.append(preset)
    return active_presets

def get_active_workflow_presets(presets_data, valid_cfg_names, current_os, all_presets_map):
    """获取活动的工作流预设。工作流预设及其所有步骤都必须满足条件。"""
    active_workflows = []
    for preset in presets_data.get('workflowPresets', []):
        wf_name = preset.get('name', "N/A_WF")
        if not is_preset_visible_and_valid(preset, current_os, debug_prefix=f"    WF Self Check '{wf_name}': "):
            continue
        steps_ok = True
        for step in preset.get("steps", []):
            step_name = step.get("name")
            step_type = step.get("type")
            step_preset_obj = all_presets_map.get(step_name)
            if not step_preset_obj or \
                    not is_preset_visible_and_valid(step_preset_obj, current_os, debug_prefix=f"      WF '{wf_name}', Step '{step_name}' Check: "):
                steps_ok = False; break
            if step_type in ["build", "test", "package"]:
                step_cfg_preset_name = step_preset_obj.get("configurePreset")
                if not step_cfg_preset_name or step_cfg_preset_name not in valid_cfg_names:
                    steps_ok = False; break
            if step_type == "configure" and step_name not in valid_cfg_names:
                steps_ok = False; break
        if steps_ok:
            active_workflows.append(preset)
    return active_workflows

def display_menu_and_get_choice(options_list, prompt_message="请选择一个选项:"):
    """显示菜单并获取用户选择。返回 (选择的数字, 选择项的实际名称) 或 (0, None)。"""
    print(f"\n{BLUE}{prompt_message}{RESET}")
    if not options_list:
        print(f"{YELLOW}没有可用选项。{RESET}")
        return 0, None

    menu_items = []
    first_item_is_dict = isinstance(options_list[0], dict) and 'name' in options_list[0]
    first_item_is_str = isinstance(options_list[0], str)

    if first_item_is_dict:
        menu_items = [(item.get('displayName', item['name']), item['name']) for item in options_list]
    elif first_item_is_str:
        menu_items = [(item, item) for item in options_list]
    else:
        print(f"{RED}错误: 菜单选项格式不支持。{RESET}")
        return 0, None

    if not menu_items:
        print(f"{YELLOW}没有可供显示的菜单项。{RESET}")
        return 0, None

    for i, (display_name, actual_name) in enumerate(menu_items):
        print(f"  {i + 1}. {display_name}" + (f" ({actual_name})" if display_name != actual_name else ""))
    print(f"  0. 返回/退出")

    while True:
        try:
            choice_str = input("请输入您的选择: ")
            choice = int(choice_str)
            if 0 <= choice <= len(menu_items):
                return choice, menu_items[choice - 1][1] if choice > 0 else None
            else:
                print(f"{YELLOW}无效的选择 '{choice_str}'。请输入 0 到 {len(menu_items)} 之间的数字。{RESET}")
        except ValueError:
            print(f"{YELLOW}无效的输入 '{choice_str}'。请输入一个数字。{RESET}")
        except KeyboardInterrupt:
            print(f"\n{YELLOW}操作已取消。{RESET}")
            raise

def handle_clean_action(presets_data, current_os, project_dir, global_env, cmake_exe):
    """处理 CMake 清理操作的逻辑。"""
    while True:
        all_presets_map = get_all_presets_by_name(presets_data)
        available_to_clean_presets = get_visible_configure_presets_for_os(presets_data, current_os, all_presets_map)

        if not available_to_clean_presets:
            print(f"{YELLOW}对于操作系统 '{current_os}'，没有找到可供清理的、可见的配置预设。{RESET}")
            return

        choice_idx, selected_preset_name = display_menu_and_get_choice(
            available_to_clean_presets,
            "请选择要清理其构建目录的配置预设 (将删除 CMakeCache.txt 并执行 clean 目标):"
        )

        if choice_idx == 0 or not selected_preset_name: return

        selected_preset_obj = next((p for p in available_to_clean_presets if p['name'] == selected_preset_name), None)
        if not selected_preset_obj:
            print(f"{RED}内部错误: 未能找到选定的预设对象 '{selected_preset_name}'。{RESET}")
            continue

        binary_dir_template = selected_preset_obj.get('binaryDir')
        display_name_for_msg = selected_preset_obj.get('displayName', selected_preset_name)
        if not binary_dir_template:
            print(f"{YELLOW}预设 '{selected_preset_name}' ('{display_name_for_msg}') 没有定义 'binaryDir'。无法清理。{RESET}")
            continue

        resolved_binary_dir_str = binary_dir_template.replace("${sourceDir}", str(project_dir))
        resolved_binary_dir_path = Path(resolved_binary_dir_str).resolve()

        print(f"\n{BLUE}准备清理预设 '{selected_preset_name}' ('{display_name_for_msg}'){RESET}")
        print(f"  目标构建目录: {resolved_binary_dir_path}")

        if resolved_binary_dir_path == project_dir:
            print(f"{YELLOW}⚠️ 警告: 解析的构建目录与项目源目录相同: {project_dir}{RESET}")
            confirm = input("  这可能会删除源目录中的 CMake 缓存和构建文件。确定要继续吗? (yes/no): ").strip().lower()
            if confirm != 'yes':
                print(f"{YELLOW}操作已取消。{RESET}"); continue


        if not resolved_binary_dir_path.is_dir():
            print(f"  {YELLOW}⚠️ 构建目录 '{resolved_binary_dir_path}' 不存在。{RESET}")
            proceed_q = input(f"  是否仍要尝试执行 'cmake --target clean' 命令 (它可能会失败或无效果)? (yes/no): ").strip().lower()
            if proceed_q != 'yes':
                print(f"  {YELLOW}已跳过 'cmake --target clean' 命令。{RESET}"); continue

        clean_command_parts = [cmake_exe, "--build", str(resolved_binary_dir_path), "--target", "clean"]
        command_succeeded = run_command(clean_command_parts, global_env, cwd_path=project_dir)

        if command_succeeded:
            print(f"{GREEN}✅ 预设 '{selected_preset_name}' 的清理操作已尝试执行。{RESET}")
            return
        else:
            print(f"{RED}❌ 预设 '{selected_preset_name}' 的清理操作失败或未完全成功。{RESET}")
            print("  您可以选择另一个预设进行清理，或返回主菜单。")

def main():
    # 在 Windows 上尝试启用 ANSI 转义序列支持
    if platform.system() == "Windows":
        os.system('') # 这个空命令可以激活某些终端的 ANSI 支持

    try:
        project_dir_env = os.environ.get("PROJECT_DIR")
        project_dir = Path(project_dir_env).resolve() if project_dir_env else Path(".").resolve()
        print(f"{BLUE}工作目录 (PROJECT_DIR):{RESET} {project_dir}")

        presets_data = load_presets_data(str(project_dir))
        if not presets_data:
            print(f"{RED}无法加载 CMakePresets.json，脚本将退出。{RESET}")
            return

        current_os = get_current_os_name()
        print(f"{BLUE}当前操作系统:{RESET} {current_os}")

        cmake_exe = "cmake.bat" if current_os == "Windows" else "cmake"
        ctest_exe = "ctest.exe" if current_os == "Windows" else "ctest"
        cpack_exe = "cpack.exe" if current_os == "Windows" else "cpack"

        all_presets_map = get_all_presets_by_name(presets_data)
        valid_cfg_names = get_all_valid_configure_preset_names_for_os(presets_data, current_os, all_presets_map)

        if not valid_cfg_names:
            print(f"{YELLOW}警告: 对于操作系统 '{current_os}'，没有找到有效的配置预设 (configurePresets)。{RESET}")
            print("这可能会导致后续的构建、测试或打包预设无法使用。")

        active_builds = get_dependent_presets('buildPresets', presets_data, valid_cfg_names, current_os, all_presets_map)
        active_tests = get_dependent_presets('testPresets', presets_data, valid_cfg_names, current_os, all_presets_map)
        active_packages = get_dependent_presets('packagePresets', presets_data, valid_cfg_names, current_os, all_presets_map)
        active_workflows = get_active_workflow_presets(presets_data, valid_cfg_names, current_os, all_presets_map)

        while True:
            main_menu_options = []
            if active_workflows: main_menu_options.append(("执行工作流 (Execute Workflow)", "workflow"))

            visible_configure_presets = get_visible_configure_presets_for_os(presets_data, current_os, all_presets_map)
            if visible_configure_presets:
                main_menu_options.append(("清理构建目录 (Clean Build Directory)", "clean"))

            if active_builds:
                main_menu_options.append(("执行构建预设 (Execute Build Preset)", "build"))
                if any(bp.get("targets") for bp in active_builds):
                    main_menu_options.append(("执行构建目标 (Execute Build Target)", "target"))
            if active_tests: main_menu_options.append(("执行测试预设 (Execute Test Preset)", "test"))
            if active_packages: main_menu_options.append(("执行打包预设 (Execute Package Preset)", "package"))

            if not main_menu_options:
                print(f"\n{YELLOW}对于您当前的操作系统或配置，没有可执行的操作。{RESET}")
                print("请检查 CMakePresets.json 中的 'condition' 和 'hidden' 字段，以及它们引用的配置预设的有效性。")
                break

            print(f"\n{BLUE}主菜单 - 请选择 CMake 操作:{RESET}")
            for i, (display_name, _) in enumerate(main_menu_options):
                print(f"  {i + 1}. {display_name}")
            print(f"  0. 退出 (Exit)")

            user_main_choice_idx_str = ""
            try:
                user_main_choice_idx_str = input("请输入您的选择: ")
                user_main_choice_idx = int(user_main_choice_idx_str)

                if user_main_choice_idx == 0: print(f"{BLUE}正在退出程序。{RESET}"); break
                if 1 <= user_main_choice_idx <= len(main_menu_options):
                    selected_action_key = main_menu_options[user_main_choice_idx - 1][1]
                else:
                    print(f"{YELLOW}无效的选择 '{user_main_choice_idx_str}'。请在 0 到 {len(main_menu_options)} 之间选择。{RESET}"); continue
            except ValueError:
                print(f"{YELLOW}无效的输入 '{user_main_choice_idx_str}'。请输入一个数字。{RESET}"); continue
            except KeyboardInterrupt: print(f"\n{YELLOW}操作已取消，正在退出程序。{RESET}"); break

            final_command_str = None
            chosen_presets_list_for_submenu = []
            prompt_msg_for_submenu = ""

            if selected_action_key == "clean":
                handle_clean_action(presets_data, current_os, project_dir, global_env, cmake_exe)
                continue
            elif selected_action_key == "workflow":
                chosen_presets_list_for_submenu, prompt_msg_for_submenu = active_workflows, "请选择要执行的工作流预设:"
            elif selected_action_key == "build":
                chosen_presets_list_for_submenu, prompt_msg_for_submenu = active_builds, "请选择要执行的构建预设:"
            elif selected_action_key == "target":
                build_presets_with_targets = [bp for bp in active_builds if bp.get("targets")]
                if not build_presets_with_targets: print(f"{YELLOW}没有找到定义了特定目标的活动构建预设。{RESET}"); continue

                choice_idx, sel_build_name = display_menu_and_get_choice(build_presets_with_targets, "首先，请选择一个构建预设以查看其目标:")
                if choice_idx > 0 and sel_build_name:
                    sel_build_obj = next((p for p in build_presets_with_targets if p['name'] == sel_build_name), None)
                    if sel_build_obj and sel_build_obj.get("targets"):
                        targets = sel_build_obj.get("targets", [])
                        if isinstance(targets, list) and all(isinstance(t, str) for t in targets):
                            target_choice_idx, sel_target_name = display_menu_and_get_choice(targets, f"请为构建预设 '{sel_build_name}' 选择一个目标:")
                            if target_choice_idx > 0 and sel_target_name:
                                final_command_str = f"{cmake_exe} --build --preset {sel_build_name} --target {sel_target_name}"
                        else: print(f"{YELLOW}构建预设 '{sel_build_name}' 的目标格式不正确。{RESET}")
                    else: print(f"{YELLOW}未能找到构建预设 '{sel_build_name}' 或其没有定义目标。{RESET}")
            elif selected_action_key == "test":
                chosen_presets_list_for_submenu, prompt_msg_for_submenu = active_tests, "请选择要执行的测试预设:"
            elif selected_action_key == "package":
                chosen_presets_list_for_submenu, prompt_msg_for_submenu = active_packages, "请选择要执行的打包预设:"

            if chosen_presets_list_for_submenu:
                choice_idx, sel_name = display_menu_and_get_choice(chosen_presets_list_for_submenu, prompt_msg_for_submenu)
                if choice_idx > 0 and sel_name:
                    if selected_action_key == "workflow": final_command_str = f"{cmake_exe} --workflow --preset {sel_name}"
                    elif selected_action_key == "build": final_command_str = f"{cmake_exe} --build --preset {sel_name}"
                    elif selected_action_key == "test": final_command_str = f"{ctest_exe} --preset {sel_name}"
                    elif selected_action_key == "package": final_command_str = f"{cpack_exe} --preset {sel_name}"

            if final_command_str:
                command_parts_to_run = shlex.split(final_command_str)
                run_command(command_parts_to_run, global_env, cwd_path=project_dir)

    except KeyboardInterrupt:
        print(f"\n{YELLOW}捕获到 KeyboardInterrupt，程序正在退出。{RESET}")
    except Exception as e:
        print(f"\n{RED}发生了一个未预料的严重错误: {e}{RESET}")
        import traceback
        traceback.print_exc()
    finally:
        print(f"{BLUE}脚本执行完毕。{RESET}")

if __name__ == "__main__":
    main()