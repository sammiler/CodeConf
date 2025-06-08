import json
import os
import pathlib
import subprocess
import re
import shutil
import copy
import sys

# --- ANSI Color Codes ---
RED, YELLOW, GREEN, BLUE, MAGENTA, CYAN, RESET = "\033[91m", "\033[93m", "\033[92m", "\033[94m", "\033[95m", "\033[96m", "\033[0m"

# --- Constants ---
ACTIVE_ENV_INFO_FILENAME = "_active_environment_info.json"
DEFAULT_COMMON_EXECUTABLES = ["cl", "link", "nmake", "msbuild", "lib", "dumpbin", "editbin", "rc", "mt", "devenv"]
SCRIPT_DIR = pathlib.Path(__file__).parent.resolve()

# ==============================================================================
# 核心逻辑
# ==============================================================================

def load_initial_config():
    """
    修改点 1: 不再加载任何硬编码的默认条目。
    启动时返回一个干净的、空白的配置结构。
    """
    print(f"{BLUE}正在初始化一个全新的配置会话...{RESET}")
    return {
        "description": "用于为 GN 等构建系统生成 VS 环境垫片 (Shims)",
        "vswhere_path_override": None,
        "environment_scripts_directory": None,
        "removeScriptName": "cleanup_vs_shims",
        "extra_executables": [],
        "manual_entries": [],
        "current_active_environment_id": None,
        "common_executables_override": DEFAULT_COMMON_EXECUTABLES,
        "default_scan_architectures_override": ["x64", "x86"]
    }

def find_vswhere_executable(config):
    # (此函数保持不变)
    config_vswhere_path = config.get("vswhere_path_override")
    if config_vswhere_path and pathlib.Path(config_vswhere_path).is_file():
        return str(pathlib.Path(config_vswhere_path))
    prog_files_x86 = os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")
    default_vswhere_path = pathlib.Path(prog_files_x86) / "Microsoft Visual Studio/Installer/vswhere.exe"
    if default_vswhere_path.is_file(): return str(default_vswhere_path)
    vswhere_in_path = shutil.which("vswhere")
    if vswhere_in_path: return vswhere_in_path
    print(f"{RED}错误: 未能定位 vswhere.exe。{RESET}")
    return None

def get_msvc_toolset_versions(msvc_tools_dir: pathlib.Path):
    # (此函数保持不变)
    versions = set()
    if msvc_tools_dir.is_dir():
        for item in msvc_tools_dir.iterdir():
            if item.is_dir() and re.match(r"(\d{2}\.\d{2})", item.name):
                versions.add(re.match(r"(\d{2}\.\d{2})", item.name).group(1))
    return sorted(list(versions), reverse=True)

def get_cmake_generator_suggestion(vs_year):
    # (此函数保持不变)
    try:
        year_to_vs_version_map = { 2022: "17", 2019: "16", 2017: "15" }
        vs_version_number = year_to_vs_version_map.get(int(vs_year))
        return f"Visual Studio {vs_version_number} {vs_year}" if vs_version_number else None
    except (ValueError, TypeError): return None

def scan_and_update_environments(config):
    # (此函数保持不变)
    vswhere_exe = find_vswhere_executable(config)
    if not vswhere_exe: return False, False
    print(f"{BLUE}正在使用 {MAGENTA}{vswhere_exe}{BLUE} 扫描...{RESET}")
    try:
        cmd = [vswhere_exe, "-all", "-format", "json", "-utf8", "-products", "*", "-requires", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, encoding='utf-8', errors='replace')
        installations = json.loads(result.stdout)
    except Exception as e: print(f"{RED}vswhere.exe 执行失败: {e}{RESET}"); return False, False
    if "manual_entries" not in config: config["manual_entries"] = []
    existing_ids = {e.get("id") for e in config["manual_entries"]}
    newly_added_count = 0
    supported_architectures = config.get("default_scan_architectures_override", ["x64", "x86"])
    for inst in installations:
        install_path = pathlib.Path(inst.get("resolvedInstallationPath") or inst.get("installationPath", ""))
        vcvarsall_bat_path = install_path / "VC/Auxiliary/Build/vcvarsall.bat"
        if not vcvarsall_bat_path.exists(): continue
        vs_year_str = inst.get("catalog", {}).get("productLineVersion", "0")
        vs_year = int(vs_year_str) if vs_year_str.isdigit() else 0
        display_name = inst.get("displayName", f"Visual Studio {vs_year}")
        msvc_tools_dir = install_path / "VC/Tools/MSVC"
        for ts_ver in get_msvc_toolset_versions(msvc_tools_dir):
            for arch in supported_architectures:
                gen_id = f"vs{vs_year}_{arch}_{ts_ver.replace('.', '')}"
                if gen_id in existing_ids: continue
                entry = { "id": gen_id, "displayName": f"{display_name} ({arch}) - Tools v{ts_ver}", "vcvarsall_path": str(vcvarsall_bat_path), "vs_year": vs_year, "architecture": arch, "vcvars_ver_option": ts_ver, "cmake_generator": get_cmake_generator_suggestion(vs_year) }
                config["manual_entries"].append(entry)
                existing_ids.add(gen_id); newly_added_count += 1
                print(f"  {GREEN}已添加:{RESET} {entry['displayName']}")
    if newly_added_count > 0: print(f"{GREEN}成功添加 {newly_added_count} 个新环境。{RESET}"); return True, True
    else: print(f"{BLUE}没有新的环境被添加。{RESET}"); return True, False

def get_env_from_vcvars(vcvars_path_str, architecture, vcvars_ver_opt=None):
    """
    修改点 2: 使用差分方法捕获所有新增或改变的环境变量。
    """
    vcvars_path = pathlib.Path(vcvars_path_str)
    if not vcvars_path.exists(): print(f"{RED}错误: vcvarsall.bat 路径不存在。{RESET}"); return None
    
    separator = "---ENV_SEPARATOR---"
    cmd_parts = [f'"{str(vcvars_path)}"', architecture]
    if vcvars_ver_opt: cmd_parts.append(f"-vcvars_ver={vcvars_ver_opt}")
    
    # 1. 先打印原始环境, 2. 调用 vcvarsall, 3. 打印新环境
    temp_bat_content = f"@echo off\nchcp 65001 > nul\nset\necho {separator}\ncall {' '.join(cmd_parts)}\nset\n"
    temp_bat_file = pathlib.Path(os.getenv("TEMP", SCRIPT_DIR)) / f"vstemp_env_{os.getpid()}.bat"
    
    try:
        temp_bat_file.write_text(temp_bat_content, encoding='utf-8')
        proc = subprocess.run(['cmd.exe', '/C', str(temp_bat_file)], capture_output=True, text=False, timeout=60)
        
        if proc.returncode != 0: print(f"{RED}执行 vcvarsall 失败。{RESET}"); return None
        
        output_str = proc.stdout.decode('utf-8', errors='replace')
        before_str, after_str = output_str.split(separator, 1)

        def parse_env_block(block):
            env = {}
            for line in block.strip().splitlines():
                if '=' in line: key, value = line.split('=', 1); env[key.upper()] = value
            return env

        env_before = parse_env_block(before_str)
        env_after = parse_env_block(after_str)

        # 计算差异：所有在调用后出现或改变的变量都会被捕获
        diff_env = {key: value for key, value in env_after.items() if env_before.get(key) != value}
        
        if not diff_env: print(f"{YELLOW}警告: 未能提取出任何新的或已改变的环境变量。{RESET}")
        
        print(f"{BLUE}  已提取 {len(diff_env)} 个环境变量 (包括 PATH, INCLUDE, LIB, SDK-s...){RESET}")
        return diff_env

    except Exception as e:
        print(f"{RED}提取环境变量时出错: {e}{RESET}")
        return None
    finally:
        if temp_bat_file.exists(): temp_bat_file.unlink(missing_ok=True)


def generate_shim_script_content(env_vars, target_exe_full_path=None, common_exe_base_name=None):
    """
    统一的 shim 生成函数，现在它会设置所有传入的环境变量。
    """
    if not env_vars: return ""
    
    content = "@echo off\n"
    # 逐一设置所有从 vcvarsall 获取的环境变量
    for key, value in env_vars.items():
        # 对于包含特殊字符的 value，用引号包裹是安全的
        content += f"SET \"{key}={value}\"\n"
        
    # 决定最终要执行的命令
    if common_exe_base_name:
        # 对于 cl, link 等，我们假设它们在 vcvarsall 设置的 PATH 中
        content += f'"{common_exe_base_name}.exe" %*\n'
    elif target_exe_full_path:
        # 对于 cmake, clang-cl 等，我们使用其完整路径
        content += f'"{target_exe_full_path}" %*\n'
    
    content += "exit /b %ERRORLEVEL%\n"
    return content

def apply_active_environment(config):
    # (此函数的核心逻辑不变，但调用 generate_shim_script_content 的方式略有调整)
    active_id = config.get("current_active_environment_id")
    if not active_id: print(f"{YELLOW}提示: 未设置活动环境。{RESET}"); return False
    active_entry = next((e for e in config.get("manual_entries", []) if e.get("id") == active_id), None)
    if not active_entry: print(f"{RED}错误: 未找到ID为 '{active_id}' 的环境。{RESET}"); return False

    display_name = active_entry.get('displayName', active_id)
    print(f"\n{CYAN}--- 正在为环境 '{MAGENTA}{display_name}{CYAN}' 生成 Shims ---{RESET}")
    vcvars_path = active_entry.get("vcvarsall_path")
    arch = active_entry.get("architecture")
    ver_opt = active_entry.get("vcvars_ver_option")

    env_vars = get_env_from_vcvars(vcvars_path, arch, ver_opt)
    if not env_vars: print(f"{RED}未能提取环境变量，操作中止。{RESET}"); return False

    shim_dir_str = config.get("environment_scripts_directory")
    if not shim_dir_str: print(f"{RED}错误: 未配置 shims 目录。{RESET}"); return False
    shim_dir = pathlib.Path(shim_dir_str).resolve()
    shim_dir.mkdir(parents=True, exist_ok=True)
    print(f"{BLUE}  Shims 将被生成到: {shim_dir}{RESET}")

    # 清理旧的 .bat 文件
    for item in shim_dir.glob("*.bat"):
        # 保留清理脚本自身
        if config.get("removeScriptName") and item.name.lower() == f"{config['removeScriptName']}.bat".lower():
            continue
        item.unlink()

    # 生成新的 shims
    common_executables = config.get("common_executables_override", [])
    extra_executables = config.get("extra_executables", [])
    
    for exe_base in common_executables:
        shim_content = generate_shim_script_content(env_vars, common_exe_base_name=exe_base)
        (shim_dir / f"{exe_base}.bat").write_text(shim_content, encoding='utf-8')
        
    for extra in extra_executables:
        shim_content = generate_shim_script_content(env_vars, target_exe_full_path=extra.get("path"))
        (shim_dir / f"{extra.get('name')}.bat").write_text(shim_content, encoding='utf-8')

    print(f"{GREEN}  成功生成 {len(common_executables) + len(extra_executables)} 个 shim 脚本。{RESET}")
    
    # 记录激活信息
    active_info = { "active_id": active_id, "displayName": display_name, "shim_directory": str(shim_dir) }
    (shim_dir / ACTIVE_ENV_INFO_FILENAME).write_text(json.dumps(active_info, indent=2), encoding='utf-8')
    
    print(f"{CYAN}--- 环境 '{MAGENTA}{display_name}{CYAN}' 设置完成 ---{RESET}")
    print(f"{BLUE}请确保目录 '{MAGENTA}{shim_dir}{BLUE}' 在系统 PATH 中并具有高优先级。{RESET}")
    return True

# (handle_cleanup_active_shims 和 main 函数与你提供的版本基本一致，但 main 会调用新的 load_initial_config)
def handle_cleanup_active_shims(config):
    shim_dir_str = config.get("environment_scripts_directory")
    if not shim_dir_str: print(f"{RED}错误: 未配置 shims 目录。{RESET}"); return
    shim_dir = pathlib.Path(shim_dir_str)
    if not shim_dir.exists(): print(f"{YELLOW}目录 '{shim_dir}' 不存在, 无需清理。{RESET}"); return
    
    print(f"\n{CYAN}--- 开始清理 Shims 目录: {shim_dir} ---{RESET}")
    if input(f"{YELLOW}确定要删除该目录中所有 .bat 和 .json 文件吗? (y/N): {RESET}").lower() != 'y':
        print("操作已取消。"); return
        
    deleted_count = 0
    for ext in ["*.bat", "*.json"]:
        for file in shim_dir.glob(ext):
            try: file.unlink(); deleted_count += 1
            except OSError as e: print(f"{RED}删除 '{file}' 失败: {e}{RESET}")
            
    print(f"{GREEN}清理完成, 共删除 {deleted_count} 个文件。{RESET}")


def main():
    if os.name == 'nt': os.system('')
    print(f"{CYAN}欢迎使用 Visual Studio 环境垫片 (Shims) 生成工具!{RESET}")

    current_config = load_initial_config()

    while True:
        print("\n" + "="*15 + f"{MAGENTA} VS 环境 Shims 管理 {RESET}" + "="*15)
        active_id = current_config.get('current_active_environment_id')
        active_display = "未设置"
        if active_id:
            entry = next((e for e in current_config["manual_entries"] if e.get("id") == active_id), None)
            if entry: active_display = entry.get('displayName', active_id)
        print(f"{CYAN}当前选定环境: {MAGENTA}{active_display}{RESET}")

        menu = {
            "1": "选择并激活一个环境以生成 Shims",
            "2": "扫描系统中的VS环境",
            "3": "设置 Shims 目录",
            "4": "添加额外的可执行文件映射",
            "5": "清理已生成的 Shims",
            "6": "查看当前会话配置",
            "0": "退出"
        }
        for key, value in menu.items(): print(f"  {key}. {value}")
        choice = input(f"{CYAN}请输入选项: {RESET}").strip()

        try:
            if choice == "0": break
            elif choice == "1":
                if not current_config["manual_entries"]: print(f"{YELLOW}无可用环境, 请先扫描(2)。{RESET}"); continue
                print(f"\n{BLUE}可用的VS环境:{RESET}")
                for i, entry in enumerate(current_config["manual_entries"]): print(f"  {i+1}. {entry.get('displayName', '未知')}")
                sel_str = input(f"{CYAN}请选择要激活的环境序号 (0返回): {RESET}").strip()
                if sel_str and sel_str != '0':
                    sel_idx = int(sel_str) - 1
                    if 0 <= sel_idx < len(current_config["manual_entries"]):
                        current_config["current_active_environment_id"] = current_config["manual_entries"][sel_idx]["id"]
                        apply_active_environment(current_config)
                    else: print(f"{RED}无效选择。{RESET}")
            elif choice == "2": scan_and_update_environments(current_config)
            elif choice == "3":
                old_dir = current_config.get("environment_scripts_directory", "未设置")
                new_dir = input(f"{CYAN}当前目录: {old_dir}\n请输入新目录 (回车保持不变): {RESET}").strip()
                if new_dir: current_config["environment_scripts_directory"] = str(pathlib.Path(new_dir).resolve())
            elif choice == "4":
                exe_path = input(f"{CYAN}请输入可执行文件完整路径: {RESET}").strip('"')
                if not pathlib.Path(exe_path).is_file(): print(f"{RED}文件不存在。{RESET}"); continue
                shim_name = input(f"{CYAN}请输入 Shim 名称 (默认: {pathlib.Path(exe_path).stem}): {RESET}").strip() or pathlib.Path(exe_path).stem
                desc = input(f"{CYAN}请输入描述: {RESET}").strip()
                current_config["extra_executables"].append({"name": shim_name, "description": desc, "path": exe_path})
                print(f"{GREEN}已添加。{RESET}")
            elif choice == "5": handle_cleanup_active_shims(current_config)
            elif choice == "6": print(json.dumps(current_config, indent=2, ensure_ascii=False))
            else: print(f"{RED}无效选项。{RESET}")
        except (ValueError, IndexError): print(f"{RED}请输入有效数字。{RESET}")
        except KeyboardInterrupt: print(f"\n{YELLOW}操作已取消。{RESET}")
        except Exception as e:
            import traceback
            print(f"{RED}发生意外错误: {e}{RESET}"); traceback.print_exc()

if __name__ == "__main__":
    main()