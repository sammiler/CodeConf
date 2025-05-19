import json
import os
import pathlib
import subprocess
import re
import shutil

# --- 配置路径 ---
SCRIPT_DIR = pathlib.Path(__file__).parent
VSCODE_DIR = SCRIPT_DIR.parent
CONFIG_FILE_PATH = VSCODE_DIR / "template" / "vs_env.json"

# --- 默认值 (用于垫片生成和扫描，可被JSON覆盖，如果JSON中有相应字段) ---
DEFAULT_COMMON_EXECUTABLES = [
    "cl", "link", "nmake", "msbuild", "lib",
    "dumpbin", "editbin", "rc", "mt", "devenv"
]
DEFAULT_SUPPORTED_ARCHITECTURES = ["x64", "x86"]

def load_config():
    """
    加载 JSON 配置文件。
    如果不存在，则基于用户提供的 JSON 结构创建默认配置。
    """
    if not CONFIG_FILE_PATH.exists():
        print(f"配置文件 {CONFIG_FILE_PATH} 未找到，将创建默认配置。")
        # 使用您提供的 JSON 结构作为默认值
        default_config = {
            "description":"用于设置VS环境,提高environment_scripts_directory的优先级",
            "vswhere_path_override": "C:\\Program Files (x86)\\Microsoft Visual Studio\\Installer\\vswhere.exe",
            "environment_scripts_directory" : "C:\\Tools",
            "scan_on_demand" : True,
            "removeScriptName":"remove",
            "extra_executables":[
                {
                    "name" : "cmake",
                    "description" : "CMake工具目录",
                    "path" : "C:\\Program Files\\CMake\\bin\\cmake.exe"
                },
                {
                    "name": "clang-cl",
                    "description":  "Clang编译器",
                    "path": "C:\\Program Files\\Microsoft Visual Studio\\2022\\Enterprise\\VC\\Tools\\Llvm\\x64\\bin\\clang-cl.exe"
                }
            ],
            "manual_entries": [
                {
                  "id": "vs2022_x64", 
                  "displayName": "VS2022 x64 14.43 (Initial)", 
                  "vcvarsall_path": "C:\\Program Files\\Microsoft Visual Studio\\2022\\Enterprise\\VC\\Auxiliary\\Build\\vcvarsall.bat",
                  "vs_year": 2022,
                  "architecture": "x64",
                  "vcvars_ver_option": "14.43",
                  "cmake_generator": "Visual Studio 17 2022"
                }
            ],
            "current_active_environment_id": "vs2022_x64"
        }
        save_config(default_config)
        # 重新加载以应用所有 setdefault 逻辑
        try:
            with open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)
        except Exception as e:
            print(f"错误: 创建并重新加载默认配置文件失败: {e}")
            return None
    else: # 文件存在
        try:
            with open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)
        except json.JSONDecodeError as e:
            print(f"错误: 解析配置文件 {CONFIG_FILE_PATH} 失败: {e}")
            return None 
        except Exception as e:
            print(f"错误: 加载配置文件 {CONFIG_FILE_PATH} 时发生未知错误: {e}")
            return None

    # 确保关键字段存在，即使它们不在原始文件中
    loaded_config.setdefault("manual_entries", [])
    loaded_config.setdefault("scan_on_demand", False) 
    loaded_config.setdefault("extra_executables", []) 
    loaded_config.setdefault("removeScriptName", None) # 如果不存在，则为None

    return loaded_config

def save_config(config_data):
    """保存 JSON 配置文件"""
    try:
        CONFIG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        config_data.setdefault("extra_executables", []) 
        config_data.setdefault("removeScriptName", None)
        with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"错误: 保存配置文件到 {CONFIG_FILE_PATH} 失败: {e}")
        return False

def find_vswhere_executable(config):
    config_vswhere_path = config.get("vswhere_path_override")
    if config_vswhere_path and pathlib.Path(config_vswhere_path).is_file():
        return str(pathlib.Path(config_vswhere_path))
    prog_files_x86 = os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")
    default_vswhere_path = pathlib.Path(prog_files_x86) / "Microsoft Visual Studio/Installer/vswhere.exe"
    if default_vswhere_path.is_file(): return str(default_vswhere_path)
    vswhere_in_path = shutil.which("vswhere")
    if vswhere_in_path: return vswhere_in_path
    print("错误: 未能定位 vswhere.exe。")
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
    year_to_vs_version_map = { 2022: "17", 2019: "16", 2017: "15", 2015: "14", 2013: "12"}
    vs_version_number = year_to_vs_version_map.get(year_int)
    return f"Visual Studio {vs_version_number} {year_int}" if vs_version_number else None

def scan_and_update_environments(config):
    vswhere_exe = find_vswhere_executable(config)
    if not vswhere_exe: return False, False 
    print(f"正在使用 {vswhere_exe} 扫描系统中的 Visual Studio C++ 环境...")
    try:
        cmd = [vswhere_exe, "-all", "-format", "json", "-utf8", "-products", "*", "-requires", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, encoding='utf-8', errors='replace')
        installations = json.loads(result.stdout)
        print(f"  vswhere.exe 找到 {len(installations)} 个原始安装条目。")
    except Exception as e:
        print(f"错误: vswhere.exe 相关操作失败: {e}")
        return False, False 
    if not installations:
        print("通过 vswhere.exe 未发现任何安装了 C++ 工具的 Visual Studio 实例。")
        return True, False 
    existing_ids = {entry.get("id") for entry in config.get("manual_entries", []) if entry.get("id")}
    newly_added_count = 0
    supported_architectures = config.get("default_scan_architectures_override", DEFAULT_SUPPORTED_ARCHITECTURES)
    for inst_idx, inst in enumerate(installations):
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
        instance_id_full = inst.get("instanceId", f"unknown{inst_idx}_{vs_year}")
        instance_id_short = instance_id_full[-8:]
        display_name_from_vswhere = inst.get("displayName", "Visual Studio")
        edition_match = re.search(r"(Enterprise|Professional|Community|BuildTools)", display_name_from_vswhere, re.IGNORECASE)
        edition_str = edition_match.group(1).lower() if edition_match else "vs"
        msvc_tools_dir = install_path / "VC/Tools/MSVC"
        toolset_versions_found = get_msvc_toolset_versions(msvc_tools_dir)
        all_toolsets_to_consider = toolset_versions_found 
        if not all_toolsets_to_consider: continue
        for arch in supported_architectures:
            for ts_ver_opt in all_toolsets_to_consider: 
                if not ts_ver_opt: continue
                ts_ver_suffix_for_id = ts_ver_opt.replace('.', '')
                generated_id = f"vs{vs_year}_{edition_str}_{instance_id_short}_{arch}_{ts_ver_suffix_for_id}"
                if generated_id in existing_ids: continue
                ts_display_name_part = f"Tools v{ts_ver_opt}"
                auto_generated_display_name = f"{display_name_from_vswhere} / {arch} / {ts_display_name_part}"
                entry = {
                    "id": generated_id, "displayName": auto_generated_display_name,
                    "vcvarsall_path": str(vcvarsall_bat_path), "vs_year": vs_year,
                    "architecture": arch, "vcvars_ver_option": ts_ver_opt, 
                    "cmake_generator": get_cmake_generator_suggestion(vs_year)
                }
                if entry["cmake_generator"] is None: del entry["cmake_generator"]
                config.get("manual_entries", []).append(entry)
                existing_ids.add(generated_id)
                newly_added_count += 1
                print(f"    已添加新发现的环境: {auto_generated_display_name} (ID: {generated_id})")
    if newly_added_count > 0:
        print(f"成功添加 {newly_added_count} 个新发现的环境到 'manual_entries'。")
        return True, True 
    else:
        print("没有新的环境被添加到 'manual_entries'。")
        return True, False

def get_env_from_vcvars(vcvars_path, architecture, vcvars_ver_opt=None):
    if not pathlib.Path(vcvars_path).exists(): return None
    cmd_parts = [f'"{vcvars_path}"', architecture]
    if vcvars_ver_opt: cmd_parts.append(f"-vcvars_ver={vcvars_ver_opt}")
    temp_bat_content = f"@echo off\nchcp 65001>nul\ncall {' '.join(cmd_parts)}\nset\n"
    temp_dir = pathlib.Path(os.getenv("TEMP", "."))
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_bat_file = temp_dir / f"vstemp_{os.getpid()}.bat"
    extracted_env = {}
    try:
        with open(temp_bat_file, "w", encoding='utf-8') as f: f.write(temp_bat_content)
        proc = subprocess.run(['cmd.exe', '/c', str(temp_bat_file)], 
                              capture_output=True, text=True, encoding='mbcs', 
                              errors='replace', timeout=30) 
        if proc.returncode != 0: return None
        for line in proc.stdout.splitlines():
            if '=' in line:
                key, value = line.split('=', 1)
                key_upper = key.strip().upper()
                if key_upper in ["PATH", "INCLUDE", "LIB", "LIBPATH", 
                                 "VCTOOLSINSTALLDIR", "VISUALSTUDIOVERSION", 
                                 "WINDOWSSDKDIR", "WINDOWSSDKVERSION", 
                                 "UNIVERSALCRTSDKDIR", "UCRTVERSION"]:
                    extracted_env[key_upper] = value.strip()
        if not all(k in extracted_env for k in ["PATH", "INCLUDE", "LIB"]):
             print(f"警告: 未完整提取 PATH, INCLUDE, LIB. 提取到的键: {list(extracted_env.keys())}")
    except Exception: return None # Simplified error handling for brevity
    finally:
        if temp_bat_file.exists():
            try: temp_bat_file.unlink()
            except OSError: pass
    return extracted_env

def generate_shim_script_content_common(env_vars, common_exe_base_name):
    content = f"@echo off\nSET \"PATH={env_vars.get('PATH', '')}\"\nSET \"INCLUDE={env_vars.get('INCLUDE', '')}\"\nSET \"LIB={env_vars.get('LIB', '')}\"\n"
    content += f'"{common_exe_base_name}.exe" %*\nexit /b %ERRORLEVEL%\n'
    return content

def generate_shim_script_content_extra(env_vars, full_path_to_target_exe):
    content = f"@echo off\nSET \"PATH={env_vars.get('PATH', '')}\"\nSET \"INCLUDE={env_vars.get('INCLUDE', '')}\"\nSET \"LIB={env_vars.get('LIB', '')}\"\n"
    content += f'"{full_path_to_target_exe}" %*\nexit /b %ERRORLEVEL%\n'
    return content

def generate_remove_script_content(shim_dir_path_str, list_of_all_shim_base_names, self_script_name_with_ext):
    """
    生成用于删除所有垫片脚本的批处理脚本内容。
    shim_dir_path_str: 垫片脚本所在的目录路径字符串。
    list_of_all_shim_base_names: 所有已生成垫片的base name列表 (不含.bat)。
    self_script_name_with_ext: 清理脚本自身的文件名 (例如 "remove.bat")。
    """
    content = "@echo off\n"
    content += "echo."
    content += "echo Removing generated shim scripts...\n"
    content += "echo."
    
    # 使用 %~dp0 来引用脚本所在的目录，确保在任何位置运行都能正确找到要删除的文件
    # 但由于垫片目录是绝对路径，我们直接使用它
    shim_dir = pathlib.Path(shim_dir_path_str).resolve()

    for base_name in list_of_all_shim_base_names:
        shim_file_to_delete = shim_dir / f"{base_name}.bat"
        # 确保不会尝试删除清理脚本自身
        if shim_file_to_delete.name.lower() == self_script_name_with_ext.lower():
            content += f"echo Skipping self: {self_script_name_with_ext}\n"
            continue
        
        # 使用绝对路径进行删除，并检查文件是否存在
        content += f"echo Deleting: {shim_file_to_delete}\n"
        content += f"if exist \"{shim_file_to_delete}\" (\n"
        content += f"  del /F /Q \"{shim_file_to_delete}\"\n"
        content += ") else (\n"
        content += f"  echo   File not found: {shim_file_to_delete}\n"
        content += ")\n"
        content += "echo.\n"
        
    content += "echo."
    content += "echo Shim script removal process finished.\n"
    content += "pause\n" # 可选：暂停以便用户查看输出
    return content

def apply_active_environment(config):
    active_id = config.get("current_active_environment_id")
    if not active_id:
        print("提示: 配置文件中未设置 'current_active_environment_id'。")
        return False
    active_entry = next((e for e in config.get("manual_entries", []) if e.get("id") == active_id), None)
    if not active_entry:
        print(f"错误: 未能在 'manual_entries' 中找到ID为 '{active_id}' 的环境。")
        return False
    display_name = active_entry.get('displayName', active_id) 
    print(f"正在为环境 '{display_name}' 应用设置...")
    vcvars_path = active_entry.get("vcvarsall_path")
    arch = active_entry.get("architecture")
    ver_opt = active_entry.get("vcvars_ver_option")
    if not vcvars_path or not arch : 
        print(f"错误: 环境 '{display_name}' 的配置不完整。")
        return False
    env_vars = get_env_from_vcvars(vcvars_path, arch, ver_opt)
    if not env_vars or not all(k in env_vars for k in ["PATH", "INCLUDE", "LIB"]):
        print(f"错误: 未能从 vcvarsall.bat 成功提取所需的环境变量。")
        return False
    shim_dir_path_str = config.get("environment_scripts_directory")
    if not shim_dir_path_str:
        print("错误: 配置文件中未指定 'environment_scripts_directory'。")
        return False
    shim_dir = pathlib.Path(shim_dir_path_str).resolve()
    try: 
        shim_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"错误: 创建垫片目录 '{shim_dir}' 失败: {e}")
        return False

    common_executables = config.get("common_executables_override", DEFAULT_COMMON_EXECUTABLES)
    extra_executables_config = config.get("extra_executables", [])
    
    # --- 收集所有将要生成的垫片的基本名称 ---
    all_generated_shim_base_names = set(common_executables)
    valid_extra_items_for_removal_script = [] # 用于生成清理脚本
    for item in extra_executables_config:
        name = item.get("name")
        path_str = item.get("path")
        if name and path_str and pathlib.Path(path_str).is_file():
            all_generated_shim_base_names.add(name)
            valid_extra_items_for_removal_script.append(name) # 只添加有效的name

    # --- 清理阶段 ---
    cleaned_count = 0
    remove_script_name_config = config.get("removeScriptName") # e.g., "remove"
    remove_script_full_name = f"{remove_script_name_config}.bat" if remove_script_name_config else None

    for shim_base_name in all_generated_shim_base_names:
        shim_file = shim_dir / f"{shim_base_name}.bat"
        # 如果定义了清理脚本名，并且当前要删除的垫片就是清理脚本自身，则跳过
        if remove_script_full_name and shim_file.name.lower() == remove_script_full_name.lower():
            # print(f"  跳过清理脚本自身: {shim_file.name}")
            continue
        if shim_file.exists():
            try: 
                shim_file.unlink()
                cleaned_count += 1
            except OSError: pass 
    if cleaned_count > 0: print(f"  已清理 {cleaned_count} 个旧垫片脚本从 '{shim_dir}'。")

    # --- 生成阶段 ---
    generated_common_count = 0
    generated_extra_count = 0
    for exe_base_name in common_executables:
        shim_content = generate_shim_script_content_common(env_vars, exe_base_name)
        shim_file_path = shim_dir / f"{exe_base_name}.bat"
        try:
            with open(shim_file_path, 'w', encoding='utf-8') as f: f.write(shim_content)
            generated_common_count +=1
        except Exception as e: 
            print(f"错误: 创建通用垫片脚本 '{shim_file_path}' 失败: {e}")

    for extra_item in extra_executables_config: # 使用原始列表以打印警告
        shim_base_name = extra_item.get("name")
        target_exe_full_path = extra_item.get("path")
        if not shim_base_name or not target_exe_full_path:
            print(f"警告: 跳过 'extra_executables' 中的无效条目 (缺少 name 或 path): {extra_item}")
            continue
        target_exe_path_obj = pathlib.Path(target_exe_full_path)
        if not target_exe_path_obj.is_file():
            print(f"警告: 'extra_executables' 条目 '{shim_base_name}' 的路径 '{target_exe_full_path}' 不是有效文件。跳过。")
            continue
        shim_content = generate_shim_script_content_extra(env_vars, target_exe_full_path)
        shim_file_path = shim_dir / f"{shim_base_name}.bat"
        try:
            with open(shim_file_path, 'w', encoding='utf-8') as f: f.write(shim_content)
            generated_extra_count +=1
        except Exception as e: 
            print(f"错误: 创建额外垫片脚本 '{shim_file_path}' 失败: {e}")
    
    total_generated = generated_common_count + generated_extra_count
    if total_generated > 0:
        print(f"成功为环境 '{display_name}' 生成了 {generated_common_count} 个通用和 {generated_extra_count} 个额外垫片。")
    else:
        print(f"未能为环境 '{display_name}' 生成任何垫片脚本。")

    # --- 生成清理脚本 ---
    if remove_script_name_config and shim_dir_path_str: # 确保有名称且目录有效
        remove_script_file_path = shim_dir / remove_script_full_name
        # 传递所有实际会生成的垫片名称给清理脚本生成器
        current_all_shim_names_for_remove_script = set(common_executables)
        for name in valid_extra_items_for_removal_script: # 只用有效的
            current_all_shim_names_for_remove_script.add(name)

        remove_content = generate_remove_script_content(
            shim_dir_path_str, 
            list(current_all_shim_names_for_remove_script), # 传递所有实际生成垫片的名称
            remove_script_full_name
        )
        try:
            with open(remove_script_file_path, 'w', encoding='utf-8') as f:
                f.write(remove_content)
            print(f"已生成清理脚本: {remove_script_file_path}")
        except Exception as e:
            print(f"错误: 生成清理脚本 '{remove_script_file_path}' 失败: {e}")

    print(f"请确保目录 '{shim_dir}' 在您的系统 PATH 中。")
    cmake_gen_display = active_entry.get('cmake_generator') or get_cmake_generator_suggestion(active_entry.get('vs_year'))
    if cmake_gen_display: print(f"此环境的 CMake 生成器建议: {cmake_gen_display}")
    return True

def main():
    config = load_config()
    if config is None: 
        print("脚本因无法加载配置而退出。")
        return
    config_was_modified_by_scan = False
    if config.get("scan_on_demand", False): 
        print("JSON配置 'scan_on_demand' 为 true，执行扫描...")
        scan_successful, config_was_modified_by_scan = scan_and_update_environments(config)
        if not scan_successful:
            print("扫描操作未能成功执行。")
        elif config_was_modified_by_scan:
            print("扫描导致配置更改，正在保存...")
            if not save_config(config): 
                print("错误: 保存扫描后的配置失败！")
    print("\n尝试应用当前激活的环境...")
    apply_active_environment(config)

if __name__ == "__main__":
    main()