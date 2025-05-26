import json
import os
import pathlib
import subprocess
import re
import shutil
import copy
import platform as pf
import sys

# --- ANSI Color Codes ---
RED = "\033[91m"
YELLOW = "\033[93m"
GREEN = "\033[92m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
RESET = "\033[0m"

# --- 内嵌的初始默认配置 ---
INITIAL_DEFAULT_CONFIG = {
    "description":"用于设置VS环境,提高environment_scripts_directory的优先级",
    "vswhere_path_override": "C:\\Program Files (x86)\\Microsoft Visual Studio\\Installer\\vswhere.exe",
    "environment_scripts_directory" : "C:\\Tools", # 示例路径
    "removeScriptName":"cleanup_vs_shims", # 清理脚本的 base name
    "extra_executables":[
        { "name" : "cmake", "description" : "CMake工具目录", "path" : "C:\\Program Files\\CMake\\bin\\cmake.exe" },
        { "name": "clang-cl", "description":  "Clang编译器", "path": "C:\\Program Files\\Microsoft Visual Studio\\2022\\Enterprise\\VC\\Tools\\Llvm\\x64\\bin\\clang-cl.exe" }
    ],
    "manual_entries": [
        {
            "id": "vs2022_x64_default", "displayName": "VS2022 x64 14.43 (Initial Default)",
            "vcvarsall_path": "C:\\Program Files\\Microsoft Visual Studio\\2022\\Enterprise\\VC\\Auxiliary\\Build\\vcvarsall.bat",
            "vs_year": 2022, "architecture": "x64", "vcvars_ver_option": "14.43",
            "cmake_generator": "Visual Studio 17 2022"
        }
    ],
    "current_active_environment_id": "vs2022_x64_default",
    "common_executables_override": ["cl", "link", "nmake", "msbuild", "lib", "dumpbin", "editbin", "rc", "mt", "devenv"],
    "default_scan_architectures_override": ["x64", "x86"]
}

# Constants for active environment tracking file
ACTIVE_ENV_INFO_FILENAME = "_active_environment_info.json"


DEFAULT_COMMON_EXECUTABLES = ["cl", "link", "nmake", "msbuild", "lib", "dumpbin", "editbin", "rc", "mt", "devenv"]
DEFAULT_SUPPORTED_ARCHITECTURES = ["x64", "x86"]

# --- Global SCRIPT_DIR definition ---
SCRIPT_DIR = pathlib.Path(__file__).parent.resolve()


def load_or_get_default_config():
    print(f"{BLUE}正在加载内嵌的默认配置...{RESET}")
    config_copy = copy.deepcopy(INITIAL_DEFAULT_CONFIG)
    config_copy.setdefault("description", "VS环境设置脚本")
    config_copy.setdefault("vswhere_path_override", None)
    config_copy.setdefault("environment_scripts_directory", None)
    config_copy.setdefault("removeScriptName", "remove_shims") # Default name for cleanup script
    config_copy.setdefault("extra_executables", [])
    config_copy.setdefault("manual_entries", [])
    config_copy.setdefault("current_active_environment_id", None)
    config_copy.setdefault("common_executables_override", DEFAULT_COMMON_EXECUTABLES)
    config_copy.setdefault("default_scan_architectures_override", DEFAULT_SUPPORTED_ARCHITECTURES)
    print(f"{GREEN}默认配置已加载到内存中。{RESET}")
    return config_copy

def save_config_stub(config_data):
    return True # Does nothing as config is in-memory

def find_vswhere_executable(config):
    config_vswhere_path = config.get("vswhere_path_override")
    if config_vswhere_path and pathlib.Path(config_vswhere_path).is_file():
        return str(pathlib.Path(config_vswhere_path))
    prog_files_x86 = os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")
    default_vswhere_path = pathlib.Path(prog_files_x86) / "Microsoft Visual Studio/Installer/vswhere.exe"
    if default_vswhere_path.is_file(): return str(default_vswhere_path)
    vswhere_in_path = shutil.which("vswhere")
    if vswhere_in_path: return vswhere_in_path
    print(f"{RED}错误: 未能定位 vswhere.exe。请在配置中通过 'vswhere_path_override' 指定，或确保其在 PATH 中。{RESET}")
    return None

def get_msvc_toolset_versions(msvc_tools_dir: pathlib.Path):
    versions = set()
    if msvc_tools_dir.is_dir():
        for item in msvc_tools_dir.iterdir():
            if item.is_dir():
                match = re.match(r"(\d{2}\.\d{2})(?:\.\d+)?", item.name)
                if match: versions.add(match.group(1))
    return sorted(list(versions), reverse=True)

def get_cmake_generator_suggestion(vs_year):
    if not vs_year: return None
    try: year_int = int(vs_year)
    except ValueError: return None
    year_to_vs_version_map = { 2022: "17", 2019: "16", 2017: "15", 2015: "14", 2013: "12", 2012: "11", 2010: "10" }
    vs_version_number = year_to_vs_version_map.get(year_int)
    return f"Visual Studio {vs_version_number} {year_int}" if vs_version_number else None

def scan_and_update_environments(config):
    vswhere_exe = find_vswhere_executable(config)
    if not vswhere_exe: return False, False
    print(f"{BLUE}正在使用 {MAGENTA}{vswhere_exe}{BLUE} 扫描系统中的 Visual Studio C++ 环境...{RESET}")
    try:
        cmd = [
            vswhere_exe, "-all", "-format", "json", "-utf8", "-products", "*",
            "-requires", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64" # Simpler, more common requirement
            # If this is too broad, add more specific ones like:
            # "-requires", "Microsoft.VisualStudio.Workload.VCTools"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, encoding='utf-8', errors='replace')
        installations = json.loads(result.stdout)
        print(f"{BLUE}  vswhere.exe 找到 {len(installations)} 个原始安装条目。正在处理...{RESET}")
    except subprocess.CalledProcessError as e:
        print(f"{RED}错误: vswhere.exe 执行失败 (返回码 {e.returncode})。{RESET}")
        try:
            vswhere_stdout = e.stdout.strip() if e.stdout else "(无 stdout)"
            vswhere_stderr = e.stderr.strip() if e.stderr else "(无 stderr)"
            print(f"{YELLOW}  vswhere stdout: {vswhere_stdout}{RESET}")
            print(f"{RED}  vswhere stderr: {vswhere_stderr}{RESET}")
        except Exception as decode_err: print(f"{RED}  (解码 vswhere 输出时发生错误: {decode_err}){RESET}")
        return False, False
    except Exception as e: print(f"{RED}错误: vswhere.exe 相关操作失败: {e}{RESET}"); return False, False

    if not installations: print(f"{YELLOW}通过 vswhere.exe 未发现任何安装了所需 C++ 组件的实例。{RESET}"); return True, False
    if "manual_entries" not in config: config["manual_entries"] = []
    existing_ids = {entry.get("id") for entry in config.get("manual_entries", []) if entry.get("id")}
    newly_added_count = 0
    supported_architectures = config.get("default_scan_architectures_override", DEFAULT_SUPPORTED_ARCHITECTURES)

    for inst in installations:
        install_path_str = inst.get("resolvedInstallationPath") or inst.get("installationPath")
        if not install_path_str: continue
        install_path = pathlib.Path(install_path_str)
        vcvarsall_bat_path = install_path / "VC/Auxiliary/Build/vcvarsall.bat"
        if not vcvarsall_bat_path.exists(): continue
        vs_year_str = inst.get("catalog", {}).get("productLineVersion")
        vs_year = 0
        if vs_year_str and vs_year_str.isdigit(): vs_year = int(vs_year_str)
        else:
            install_version_str = inst.get("installationVersion", "")
            if install_version_str.startswith("17."): vs_year = 2022
            elif install_version_str.startswith("16."): vs_year = 2019
            elif install_version_str.startswith("15."): vs_year = 2017
            else: continue
        display_name_from_vswhere = inst.get("displayName", f"Visual Studio {vs_year}")
        edition_match = re.search(r"(Enterprise|Professional|Community|BuildTools)", display_name_from_vswhere, re.IGNORECASE)
        edition_str = edition_match.group(1).lower() if edition_match else "vs"
        msvc_tools_dir = install_path / "VC/Tools/MSVC"
        toolset_versions_found = get_msvc_toolset_versions(msvc_tools_dir)
        if not toolset_versions_found: continue
        for arch in supported_architectures:
            for ts_ver_opt in toolset_versions_found:
                if not ts_ver_opt: continue
                ts_ver_suffix_for_id = ts_ver_opt.replace('.', '')
                generated_id = f"vs{vs_year}_{edition_str}_{arch}_{ts_ver_suffix_for_id}"
                if generated_id in existing_ids: continue
                auto_generated_display_name = f"{display_name_from_vswhere} ({arch}) - Tools v{ts_ver_opt}"
                entry = {"id": generated_id, "displayName": auto_generated_display_name,
                         "vcvarsall_path": str(vcvarsall_bat_path), "vs_year": vs_year,
                         "architecture": arch, "vcvars_ver_option": ts_ver_opt,
                         "cmake_generator": get_cmake_generator_suggestion(vs_year)}
                if entry["cmake_generator"] is None: del entry["cmake_generator"]
                config["manual_entries"].append(entry)
                existing_ids.add(generated_id); newly_added_count += 1
                print(f"    {GREEN}已添加:{RESET} {auto_generated_display_name} (ID: {MAGENTA}{generated_id}{RESET})")
    if newly_added_count > 0: print(f"{GREEN}成功添加 {newly_added_count} 个新环境。{RESET}"); return True, True
    else: print(f"{BLUE}没有新的环境被添加。{RESET}"); return True, False

def get_env_from_vcvars(vcvars_path_str, architecture, vcvars_ver_opt=None):
    vcvars_path = pathlib.Path(vcvars_path_str)
    if not vcvars_path.exists(): print(f"{RED}错误: vcvarsall.bat 路径 '{vcvars_path}' 不存在。{RESET}"); return None
    cmd_parts = [f'"{str(vcvars_path)}"', architecture]
    if vcvars_ver_opt: cmd_parts.append(f"-vcvars_ver={vcvars_ver_opt}")
    temp_bat_content = f"@echo off\nchcp 65001 > nul 2>&1\ncall {' '.join(cmd_parts)}\nset\n"
    temp_dir = pathlib.Path(os.getenv("TEMP", SCRIPT_DIR / "temp")).resolve()
    try: temp_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e_mkdir: print(f"{RED}错误: 无法创建临时目录 '{temp_dir}': {e_mkdir}{RESET}"); return None
    temp_bat_file = temp_dir / f"vstemp_env_{os.getpid()}.bat"
    extracted_env = {}
    try:
        with open(temp_bat_file, "w", encoding='utf-8') as f: f.write(temp_bat_content)
        proc = subprocess.run(['cmd.exe', '/C', str(temp_bat_file)], capture_output=True, text=False, timeout=45)
        if proc.returncode != 0:
            print(f"{RED}错误: 执行临时环境脚本 '{temp_bat_file}' 失败 (返回码: {proc.returncode})。{RESET}")
            try: stderr_decoded = proc.stderr.decode(sys.getfilesystemencoding(), errors='replace')
            except: stderr_decoded = "(无法解码 stderr)"
            print(f"{RED}  Stderr: {stderr_decoded.strip()}{RESET}"); return None
        output_lines = []
        try:
            try: output_str = proc.stdout.decode('utf-8', errors='strict')
            except UnicodeDecodeError: output_str = proc.stdout.decode(sys.getfilesystemencoding(), errors='replace')
            output_lines = output_str.splitlines()
        except Exception as e_decode: print(f"{RED}错误: 解码 vcvarsall.bat 输出失败: {e_decode}{RESET}"); return None
        for line in output_lines:
            if '=' in line:
                parts = line.split('=', 1)
                if len(parts) == 2:
                    key, value = parts; key_upper = key.strip().upper()
                    if key_upper in ["PATH", "INCLUDE", "LIB", "LIBPATH", "VCTOOLSINSTALLDIR",
                                     "VISUALSTUDIOVERSION", "VSINSTALLDIR", "WINDOWSSDKDIR",
                                     "WINDOWSSDKVERSION", "WINDOWSLIBPATH", "UNIVERSALCRTSDKDIR",
                                     "UCRTVERSION", "CL", "_CL_", "LINK", "_LINK_"]:
                        extracted_env[key_upper] = value.strip()
        if not all(k in extracted_env for k in ["PATH", "INCLUDE", "LIB"]):
            print(f"{YELLOW}警告: 未能从 vcvarsall.bat 完整提取 PATH, INCLUDE, LIB。{RESET}")
    except subprocess.TimeoutExpired: print(f"{RED}错误: 调用 vcvarsall.bat 超时。{RESET}"); return None
    except Exception as e: print(f"{RED}错误: 提取环境变量时发生意外错误: {e}{RESET}"); return None
    finally:
        if temp_bat_file.exists():
            try: temp_bat_file.unlink()
            except OSError: pass
    return extracted_env if extracted_env else None

def generate_shim_script_content_common(env_vars, common_exe_base_name):
    path_val = env_vars.get('PATH', os.environ.get('PATH',''))
    include_val = env_vars.get('INCLUDE', '')
    lib_val = env_vars.get('LIB', '')
    content = f"@echo off\nSET \"PATH={path_val}\"\nSET \"INCLUDE={include_val}\"\nSET \"LIB={lib_val}\"\n"
    for k in ["LIBPATH", "VCTOOLSINSTALLDIR", "VISUALSTUDIOVERSION", "WINDOWSSDKDIR", "WINDOWSSDKVERSION"]:
        if k in env_vars: content += f"SET \"{k}={env_vars[k]}\"\n"
    content += f'"{common_exe_base_name}.exe" %*\nexit /b %ERRORLEVEL%\n'
    return content

def generate_shim_script_content_extra(env_vars, full_path_to_target_exe):
    path_val = env_vars.get('PATH', os.environ.get('PATH',''))
    include_val = env_vars.get('INCLUDE', '')
    lib_val = env_vars.get('LIB', '')
    content = f"@echo off\nSET \"PATH={path_val}\"\nSET \"INCLUDE={include_val}\"\nSET \"LIB={lib_val}\"\n"
    for k in ["LIBPATH", "VCTOOLSINSTALLDIR", "VISUALSTUDIOVERSION", "WINDOWSSDKDIR", "WINDOWSSDKVERSION"]:
        if k in env_vars: content += f"SET \"{k}={env_vars[k]}\"\n"
    content += f'"{full_path_to_target_exe}" %*\nexit /b %ERRORLEVEL%\n'
    return content

def generate_remove_script_content(shim_dir_path_str, list_of_all_shim_base_names, self_script_name_with_ext):
    content = "@echo off\n"
    content += "chcp 65001 > nul\n" # <--- 添加这一行
    content += f"echo.\necho {MAGENTA}准备清理垫片脚本从目录: {shim_dir_path_str}{RESET}\necho.\n"
    shim_dir = pathlib.Path(shim_dir_path_str).resolve()
    for base_name in list_of_all_shim_base_names:
        shim_file_to_delete = shim_dir / f"{base_name}.bat"
        if self_script_name_with_ext and shim_file_to_delete.name.lower() == self_script_name_with_ext.lower():
            content += f"echo {BLUE}  跳过清理脚本自身: {shim_file_to_delete.name}{RESET}\n"; continue
        content += f"echo   正在尝试删除: {shim_file_to_delete}\n"
        content += f"if exist \"{shim_file_to_delete}\" (\n"
        content += f"  del /F /Q \"{shim_file_to_delete}\" > nul 2>&1\n"
        content += f"  if errorlevel 1 (echo     {RED}删除失败: {shim_file_to_delete}{RESET}) else (echo     {GREEN}已删除: {shim_file_to_delete}{RESET})\n"
        content += ") else (echo     {YELLOW}文件未找到: {shim_file_to_delete}{RESET})\n"
    content += f"echo.\necho {GREEN}垫片脚本清理过程结束。{RESET}\n"
    return content

def apply_active_environment(config):
    active_id = config.get("current_active_environment_id")
    if not active_id: print(f"{YELLOW}提示: 配置中未设置 'current_active_environment_id'。{RESET}"); return False
    active_entry = next((e for e in config.get("manual_entries", []) if e.get("id") == active_id), None)
    if not active_entry: print(f"{RED}错误: 未能在 'manual_entries' 中找到ID为 '{active_id}' 的环境。{RESET}"); return False

    display_name = active_entry.get('displayName', active_id)
    print(f"\n{CYAN}--- 正在为环境 '{MAGENTA}{display_name}{CYAN}' 应用设置 ---{RESET}")
    vcvars_path = active_entry.get("vcvarsall_path")
    arch = active_entry.get("architecture")
    ver_opt = active_entry.get("vcvars_ver_option")
    if not vcvars_path or not arch : print(f"{RED}错误: 环境配置不完整。{RESET}"); return False

    print(f"{BLUE}  使用 vcvarsall: {vcvars_path}, 架构: {arch}, 版本选项: {ver_opt or '默认'}{RESET}")
    env_vars = get_env_from_vcvars(vcvars_path, arch, ver_opt)
    if not env_vars: print(f"{RED}错误: 未能从vcvarsall.bat提取环境变量。{RESET}"); return False
    if not all(k_check in env_vars for k_check in ["PATH", "INCLUDE", "LIB"]):
        print(f"{YELLOW}警告: 提取的环境变量不完整。{RESET}")

    shim_dir_path_str = config.get("environment_scripts_directory")
    if not shim_dir_path_str: print(f"{RED}错误: 未配置 'environment_scripts_directory'。{RESET}"); return False
    shim_dir = pathlib.Path(shim_dir_path_str).resolve()
    try: shim_dir.mkdir(parents=True, exist_ok=True); print(f"{BLUE}  垫片脚本目录: {shim_dir}{RESET}")
    except Exception as e: print(f"{RED}错误: 创建垫片目录 '{shim_dir}' 失败: {e}{RESET}"); return False

    common_executables = config.get("common_executables_override", DEFAULT_COMMON_EXECUTABLES)
    extra_executables_config = config.get("extra_executables", [])
    all_shim_base_names_to_generate_for_current_env = set(common_executables)
    for item in extra_executables_config:
        name = item.get("name"); path_str = item.get("path")
        if name and path_str and pathlib.Path(path_str).is_file():
            all_shim_base_names_to_generate_for_current_env.add(name)

    remove_script_name_config = config.get("removeScriptName")
    remove_script_full_name = f"{remove_script_name_config}.bat" if remove_script_name_config else None

    # --- 清理现有垫片 (除了清理脚本自身 和 _active_environment_info.json) ---
    cleaned_count = 0
    if shim_dir.exists():
        for item in shim_dir.iterdir():
            if item.is_file():
                if item.name.lower() == ACTIVE_ENV_INFO_FILENAME.lower(): continue
                if remove_script_full_name and item.name.lower() == remove_script_full_name.lower(): continue
                if item.suffix.lower() == ".bat": # Only delete .bat files not matching above
                    try: item.unlink(); cleaned_count += 1
                    except OSError as e_del: print(f"{YELLOW}警告: 删除旧垫片 '{item}' 失败: {e_del}{RESET}")
    if cleaned_count > 0: print(f"{BLUE}  已清理 {cleaned_count} 个旧的 .bat 垫片脚本从 '{shim_dir}'。{RESET}")

    # --- 生成新的垫片 ---
    generated_common_count = 0
    for exe_base_name in common_executables:
        shim_content = generate_shim_script_content_common(env_vars, exe_base_name)
        shim_file_path = shim_dir / f"{exe_base_name}.bat"
        try:
            with open(shim_file_path, 'w', encoding='utf-8') as f: f.write(shim_content)
            generated_common_count +=1
        except Exception as e: print(f"{RED}错误: 创建通用垫片 '{shim_file_path}' 失败: {e}{RESET}")

    generated_extra_count = 0
    for extra_item in extra_executables_config:
        shim_base_name = extra_item.get("name"); target_exe_full_path = extra_item.get("path")
        if not shim_base_name or not target_exe_full_path or not pathlib.Path(target_exe_full_path).is_file(): continue
        shim_content = generate_shim_script_content_extra(env_vars, target_exe_full_path)
        shim_file_path = shim_dir / f"{shim_base_name}.bat"
        try:
            with open(shim_file_path, 'w', encoding='utf-8') as f: f.write(shim_content)
            generated_extra_count +=1
        except Exception as e: print(f"{RED}错误: 创建额外垫片 '{shim_file_path}' 失败: {e}{RESET}")

    if generated_common_count > 0 or generated_extra_count > 0 :
        print(f"{GREEN}  成功为 '{display_name}' 生成了 {generated_common_count} 通用和 {generated_extra_count} 额外垫片。{RESET}")
    else: print(f"{YELLOW}  未能为 '{display_name}' 生成任何垫片脚本。{RESET}")

    # --- 生成清理脚本 ---
    if remove_script_name_config and shim_dir_path_str:
        remove_script_file_path = shim_dir / remove_script_full_name
        # Pass ALL shims that *should* be generated for THIS environment to the remove script content
        remove_content = generate_remove_script_content(str(shim_dir), list(all_shim_base_names_to_generate_for_current_env), remove_script_full_name)
        try:
            with open(remove_script_file_path, 'w', encoding='utf-8') as f: f.write(remove_content)
            print(f"{GREEN}  已生成清理脚本: {MAGENTA}{remove_script_file_path}{RESET}")
        except Exception as e: print(f"{RED}错误: 生成清理脚本 '{remove_script_file_path}' 失败: {e}{RESET}")

    # --- 记录当前激活的环境信息到 shims 目录 ---
    active_env_info_path = shim_dir / ACTIVE_ENV_INFO_FILENAME
    env_info_to_write = {
        "active_id": active_id,
        "displayName": display_name,
        "vcvarsall_path": vcvars_path, # Store for reference
        "architecture": arch,
        "vcvars_ver_option": ver_opt,
        "generated_shims": [f"{name}.bat" for name in all_shim_base_names_to_generate_for_current_env],
        "remove_script_name": remove_script_full_name if remove_script_full_name else None
    }
    try:
        with open(active_env_info_path, 'w', encoding='utf-8') as f_info:
            json.dump(env_info_to_write, f_info, indent=2, ensure_ascii=False)
        print(f"{GREEN}  已记录激活的环境信息到: {MAGENTA}{active_env_info_path}{RESET}")
    except Exception as e_info:
        print(f"{RED}错误: 记录激活环境信息到 '{active_env_info_path}' 失败: {e_info}{RESET}")


    print(f"{CYAN}--- 环境 '{MAGENTA}{display_name}{CYAN}' 设置完成 ---{RESET}")
    print(f"{BLUE}请确保目录 '{MAGENTA}{shim_dir}{BLUE}' 在您的系统 PATH 中，并具有较高优先级。{RESET}")
    cmake_gen_display = active_entry.get('cmake_generator') or get_cmake_generator_suggestion(active_entry.get('vs_year'))
    if cmake_gen_display: print(f"{BLUE}此环境的 CMake 生成器建议: {MAGENTA}{cmake_gen_display}{RESET}")
    return True

def handle_cleanup_active_shims(config):
    """尝试清理当前激活环境的垫片脚本。"""
    shim_dir_path_str = config.get("environment_scripts_directory")
    if not shim_dir_path_str:
        print(f"{RED}错误: 未在配置中找到 'environment_scripts_directory'。无法执行清理。{RESET}")
        return

    shim_dir = pathlib.Path(shim_dir_path_str).resolve()
    active_env_info_file = shim_dir / ACTIVE_ENV_INFO_FILENAME

    if not shim_dir.exists():
        print(f"{YELLOW}垫片目录 '{shim_dir}' 不存在。无需清理。{RESET}")
        return

    print(f"\n{CYAN}--- 开始清理垫片目录: {shim_dir} ---{RESET}")

    files_to_delete = []
    active_env_display_name = "未知 (无记录文件)"
    remove_script_to_delete_explicitly = None

    if active_env_info_file.exists():
        try:
            with open(active_env_info_file, 'r', encoding='utf-8') as f_info:
                env_info = json.load(f_info)
            active_env_display_name = env_info.get("displayName", active_env_display_name)
            print(f"{BLUE}  找到激活环境记录: {MAGENTA}{active_env_display_name}{RESET}")

            # Add shims listed in the info file
            for shim_name in env_info.get("generated_shims", []):
                files_to_delete.append(shim_dir / shim_name)

            # Add the remove script listed in the info file
            if env_info.get("remove_script_name"):
                remove_script_to_delete_explicitly = shim_dir / env_info["remove_script_name"]
                if remove_script_to_delete_explicitly not in files_to_delete: # Avoid duplicates if already in generated_shims
                    files_to_delete.append(remove_script_to_delete_explicitly)

            # Add the info file itself to the list for deletion
            files_to_delete.append(active_env_info_file)

        except Exception as e_read_info:
            print(f"{RED}错误: 读取激活环境记录文件 '{active_env_info_file}' 失败: {e_read_info}{RESET}")
            print(f"{YELLOW}将尝试清理目录中的所有 .bat 文件作为后备方案。{RESET}")
            # Fallback: if reading info fails, revert to deleting all .bat files (except configured removeScriptName)
            files_to_delete = [] # Reset list
            remove_script_name_from_config = config.get("removeScriptName")
            configured_remove_script_full_name = f"{remove_script_name_from_config}.bat" if remove_script_name_from_config else None
            for item in shim_dir.iterdir():
                if item.is_file() and item.suffix.lower() == ".bat":
                    if configured_remove_script_full_name and item.name.lower() == configured_remove_script_full_name.lower():
                        # If we couldn't read the info file, be cautious about deleting the main remove script
                        # unless we are very sure. For now, let's keep it if info file fails.
                        print(f"{YELLOW}  由于无法读取记录文件，保留已配置的清理脚本: {item.name}{RESET}")
                        continue
                    files_to_delete.append(item)
    else:
        print(f"{YELLOW}未找到激活环境记录文件 ({ACTIVE_ENV_INFO_FILENAME})。{RESET}")
        print(f"{BLUE}将尝试清理目录中的所有 .bat 文件 (除了已配置的通用清理脚本)。{RESET}")
        remove_script_name_from_config = config.get("removeScriptName")
        configured_remove_script_full_name = f"{remove_script_name_from_config}.bat" if remove_script_name_from_config else None
        for item in shim_dir.iterdir():
            if item.is_file() and item.suffix.lower() == ".bat":
                if configured_remove_script_full_name and item.name.lower() == configured_remove_script_full_name.lower():
                    print(f"{BLUE}  保留已配置的通用清理脚本: {item.name}{RESET}") # Keep the main remove script
                    continue
                files_to_delete.append(item)
        # Also try to delete _active_environment_info.json if it somehow exists but we decided to clear all .bat
        if active_env_info_file.exists() and active_env_info_file not in files_to_delete:
            files_to_delete.append(active_env_info_file)


    if not files_to_delete:
        print(f"{BLUE}  没有找到需要删除的文件。{RESET}")
    else:
        confirm_delete = input(f"{YELLOW}确定要删除以上识别出的文件和/或与环境 '{active_env_display_name}' 相关的垫片吗? (yes/N): {RESET}").strip().lower()
        if confirm_delete == 'yes':
            deleted_count = 0
            for file_path in files_to_delete:
                if file_path.exists():
                    try:
                        file_path.unlink()
                        print(f"    {GREEN}已删除: {file_path.name}{RESET}")
                        deleted_count += 1
                    except OSError as e_del:
                        print(f"    {RED}删除文件 '{file_path}' 失败: {e_del}{RESET}")
            print(f"{GREEN}成功删除 {deleted_count} 个文件。{RESET}")
            # Optionally, try to remove the shim_dir if it's empty
            try:
                if not any(shim_dir.iterdir()): # Check if directory is empty
                    confirm_rmdir = input(f"{YELLOW}垫片目录 '{shim_dir}' 现在为空。是否删除该目录? (yes/N): {RESET}").strip().lower()
                    if confirm_rmdir == 'yes':
                        shim_dir.rmdir()
                        print(f"{GREEN}已删除空的垫片目录: {shim_dir}{RESET}")
            except Exception as e_rmdir: # Catch errors from iterdir or rmdir
                print(f"{YELLOW}处理垫片目录时发生错误: {e_rmdir}{RESET}")

        else:
            print(f"{YELLOW}清理操作已取消。{RESET}")

    print(f"{CYAN}--- 清理操作结束 ---{RESET}")


def main():
    if os.name == 'nt': os.system('')
    print(f"{CYAN}欢迎使用 Visual Studio 环境设置脚本!{RESET}")
    print(f"{YELLOW}提示: 此脚本使用内嵌的默认配置。如需永久更改默认设置，请直接修改脚本源码中的 'INITIAL_DEFAULT_CONFIG'。{RESET}")

    current_config = load_or_get_default_config()
    if current_config is None: print(f"{RED}脚本因无法初始化配置而退出。{RESET}"); return

    while True:
        print("\n" + "="*15 + f"{MAGENTA} Visual Studio 环境管理 {RESET}" + "="*15)
        active_id_display = current_config.get('current_active_environment_id', '未设置')
        active_env_display_name = active_id_display
        if active_id_display != '未设置':
            active_entry_preview = next((e for e in current_config.get("manual_entries", []) if e.get("id") == active_id_display), None)
            if active_entry_preview: active_env_display_name = active_entry_preview.get('displayName', active_id_display)
        print(f"{CYAN}当前选定环境: {MAGENTA}{active_env_display_name}{RESET} (ID: {active_id_display})")

        menu_options = {
            "1": "选择并激活一个手动/已扫描的VS环境",
            "2": "扫描系统中的VS环境 (结果添加到当前会话)",
            "3": "设置自定义环境脚本目录 (shims目录)",
            "4": "添加额外的可执行文件映射",
            "5": "清理已激活的环境 (删除 shims)", # 新增选项
            "6": "查看当前会话配置 (JSON)",
            "0": "退出脚本"
        }
        print(f"\n{BLUE}请选择操作:{RESET}")
        for key, value in menu_options.items(): print(f"  {key}. {value}")

        user_choice = input(f"{CYAN}请输入选项: {RESET}").strip()

        try:
            if user_choice == "0": print(f"{BLUE}脚本退出。{RESET}"); break
            elif user_choice == "1":
                manual_entries = current_config.get("manual_entries", [])
                if not manual_entries: print(f"{YELLOW}没有可用的环境条目。请先扫描。{RESET}"); continue
                print(f"\n{BLUE}可用的VS环境:{RESET}")
                for i, entry in enumerate(manual_entries): print(f"  {i+1}. {entry.get('displayName', entry.get('id', '未知条目'))} {MAGENTA}(ID: {entry.get('id')}){RESET}")
                print("  0. 返回")
                env_choice_str = input(f"{CYAN}请选择要激活的环境序号: {RESET}").strip()
                if not env_choice_str: continue
                env_choice_idx = int(env_choice_str)
                if env_choice_idx == 0: continue
                if 1 <= env_choice_idx <= len(manual_entries):
                    selected_entry = manual_entries[env_choice_idx - 1]
                    current_config["current_active_environment_id"] = selected_entry["id"]
                    print(f"{GREEN}已选择环境: {selected_entry.get('displayName')}{RESET}")
                    apply_active_environment(current_config)
                else: print(f"{RED}无效的选择。{RESET}")
            elif user_choice == "2":
                print(f"\n{BLUE}--- 开始扫描VS环境 ---{RESET}")
                scan_successful, config_was_modified = scan_and_update_environments(current_config)
                if scan_successful: print(f"{GREEN if config_was_modified else BLUE}扫描完成。{'新的环境已添加。' if config_was_modified else '没有发现新的环境或所有发现的已存在。'}{RESET}")
                else: print(f"{RED}扫描未能成功完成。{RESET}")
            elif user_choice == "3":
                old_dir = current_config.get("environment_scripts_directory", "未设置")
                print(f"当前自定义环境脚本目录: {MAGENTA}{old_dir}{RESET}")
                new_dir_str = input(f"{CYAN}请输入新的自定义环境脚本目录路径 (直接回车保持不变): {RESET}").strip()
                if new_dir_str:
                    current_config["environment_scripts_directory"] = str(pathlib.Path(new_dir_str).resolve())
                    print(f"{GREEN}自定义环境脚本目录已更新为: {current_config['environment_scripts_directory']}{RESET}")
                else: print(f"{BLUE}目录未更改。{RESET}")
            elif user_choice == "4":
                print(f"\n{BLUE}--- 添加额外的可执行文件映射 ---{RESET}")
                exe_path_str = input(f"{CYAN}请输入可执行文件的完整路径: {RESET}").strip()
                if not exe_path_str: print(f"{YELLOW}路径不能为空。{RESET}"); continue
                exe_path = pathlib.Path(exe_path_str).resolve()
                if not exe_path.is_file(): print(f"{RED}错误: '{exe_path}' 不是一个有效的文件。{RESET}"); continue
                default_exe_name = exe_path.stem
                exe_name = input(f"{CYAN}请输入此可执行文件的垫片名称 (默认: '{default_exe_name}'): {RESET}").strip() or default_exe_name
                description = input(f"{CYAN}请输入对此可执行文件的描述: {RESET}").strip()
                new_entry = {"name": exe_name, "description": description, "path": str(exe_path)}
                current_config.setdefault("extra_executables", []).append(new_entry)
                print(f"{GREEN}已添加新的可执行文件映射: {new_entry}{RESET}")
            elif user_choice == "5": # 新增：清理已激活环境的垫片
                handle_cleanup_active_shims(current_config)
            elif user_choice == "6": # 原来的查看配置，现在是选项6
                print(f"\n{CYAN}--- 当前会话配置数据 ---{RESET}")
                try: print(json.dumps(current_config, indent=2, ensure_ascii=False))
                except Exception as e_json_dump: print(f"{RED}无法显示配置: {e_json_dump}{RESET}")
                input(f"{BLUE}按回车键继续...{RESET}")
            else: print(f"{RED}无效的选项 '{user_choice}'。请重试。{RESET}")
        except ValueError: print(f"{RED}请输入有效的数字选项。{RESET}")
        except KeyboardInterrupt: print(f"\n{YELLOW}操作已取消，返回主菜单。{RESET}")
        except Exception as e: print(f"{RED}主菜单处理中发生意外错误: {e}{RESET}"); import traceback; traceback.print_exc()

if __name__ == "__main__":
    main()