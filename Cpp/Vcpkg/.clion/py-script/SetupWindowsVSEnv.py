import json
import os
import pathlib
import subprocess
import re
import shutil
import copy
import sys
import ctypes
import winreg
import traceback

# --- ANSI Color Codes ---
RED, YELLOW, GREEN, BLUE, MAGENTA, CYAN, RESET = "\033[91m", "\033[93m", "\033[92m", "\033[94m", "\033[95m", "\033[96m", "\033[0m"

# --- 内嵌的 C# 包装器源码模板 (最终修正版) ---
CSHARP_WRAPPER_TEMPLATE = """
using System;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Linq;
using System.Collections.Generic;

public class GenericWrapper
{
    private static string EscapeArgument(string arg)
    {
        if (string.IsNullOrEmpty(arg)) return "";
        if (arg.Contains(" ") && !arg.StartsWith("\\""))
        {
            return $"\\"{arg}\\"";
        }
        return arg;
    }

    public static int Main(string[] cliArgs)
    {
        // ##PYTHON_REPLACE_REAL_EXECUTABLE_PATH##
        string realExecutablePath = @"__REAL_EXECUTABLE_PATH_PLACEHOLDER__";
        string argsFileName = @"__ARGS_FILENAME_PLACEHOLDER__";

        if (!File.Exists(realExecutablePath))
        {
            Console.Error.WriteLine($"[Wrapper FATAL] Real executable not found at: {realExecutablePath}");
            return -1;
        }

        ProcessStartInfo psi = new ProcessStartInfo();
        psi.FileName = realExecutablePath;
        psi.WorkingDirectory = Environment.CurrentDirectory;

        // ##PYTHON_REPLACE_ENVIRONMENT_VARIABLES##
        // --- Start of auto-generated environment variables ---
        // psi.EnvironmentVariables["PATH"] = @"...";
        // ---  End of auto-generated environment variables  ---

        List<string> allArguments = new List<string>();
        string exeLocation = Path.GetDirectoryName(System.Reflection.Assembly.GetExecutingAssembly().Location);
        string configTxtPath = Path.Combine(exeLocation ?? "", argsFileName); 
        
        if (File.Exists(configTxtPath))
        {
            try
            {
                string[] additionalArgs = File.ReadAllLines(configTxtPath, Encoding.UTF8);
                foreach (string arg in additionalArgs)
                {
                    string trimmedArg = arg.Trim();
                    if (!string.IsNullOrEmpty(trimmedArg) && !trimmedArg.StartsWith("#") && !trimmedArg.StartsWith(";"))
                    {
                        allArguments.Add(trimmedArg);
                    }
                }
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"[Wrapper WARNING] Could not read or parse '{configTxtPath}': {ex.Message}");
            }
        }
        
        allArguments.AddRange(cliArgs);
        psi.Arguments = string.Join(" ", allArguments.Select(EscapeArgument));
        
        // ==========================================================
        // =============  关键修改在这里 ============================
        // ==========================================================
        psi.UseShellExecute = false;
        // 1. 将重定向设置为 true，以便我们可以捕获输出
        psi.RedirectStandardOutput = true;
        psi.RedirectStandardError = true;
        psi.CreateNoWindow = true;

        try
        {
            // 2. 使用一个更完整的模式来启动进程并处理输出
            using (Process process = new Process())
            {
                process.StartInfo = psi;

                // 3. 设置事件处理程序来打印收到的每一行输出
                process.OutputDataReceived += (sender, e) => {
                    if (e.Data != null) Console.WriteLine(e.Data);
                };
                process.ErrorDataReceived += (sender, e) => {
                    if (e.Data != null) Console.Error.WriteLine(e.Data);
                };

                process.Start();

                // 4. 开始异步读取输出流
                process.BeginOutputReadLine();
                process.BeginErrorReadLine();

                process.WaitForExit();
                return process.ExitCode;
            }
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"[Wrapper FATAL] Failed to start real executable: {ex.Message}");
            return -99;
        }
    }
}
"""

# --- Global Constants ---
SCRIPT_DIR = pathlib.Path(__file__).parent.resolve()
WRAPPERS_CONFIG_FILE = SCRIPT_DIR / "wrappers_config.json"
WRAPPER_BACKUP_SUFFIX = "_real_py"

# ==============================================================================
# 权限和环境辅助函数
# ==============================================================================
def is_admin():
    try: return ctypes.windll.shell32.IsUserAnAdmin()
    except: return False

def run_as_admin():
    if not is_admin():
        print(f"{YELLOW}脚本需要管理员权限来修改系统文件和注册表。正在尝试重新启动...{RESET}")
        try: ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
        except Exception as e: print(f"{RED}自动提升权限失败: {e}{RESET}")
        sys.exit(0)

def set_permanent_env_var_reg(name, value):
    scope = 'system' if name.upper() == 'PATH' else 'user'
    try:
        root_key = winreg.HKEY_LOCAL_MACHINE if scope == 'system' else winreg.HKEY_CURRENT_USER
        sub_key_path = r'System\CurrentControlSet\Control\Session Manager\Environment' if scope == 'system' else 'Environment'
        with winreg.OpenKey(root_key, sub_key_path, 0, winreg.KEY_SET_VALUE) as key:
            var_type = winreg.REG_EXPAND_SZ if name.upper() == 'PATH' or '%' in value else winreg.REG_SZ
            winreg.SetValueEx(key, name, 0, var_type, value)
        return True, ""
    except Exception as e: return False, f"写入注册表失败: {e}"
    
def broadcast_env_change():
    try:
        SendMessageTimeoutW = ctypes.windll.user32.SendMessageTimeoutW
        SendMessageTimeoutW(0xFFFF, 0x001A, 0, "Environment", 0x0002, 5000, ctypes.byref(ctypes.c_long()))
        return True
    except: return False

def run_command_in_vs_env(command_to_run, vs_entry):
    vcvars_path_str, architecture, vcvars_ver_opt = vs_entry.get("vcvarsall_path"), vs_entry.get("architecture"), vs_entry.get("vcvars_ver_option")
    if not vcvars_path_str or not architecture: return False, "", "VS entry incomplete."
    vcvars_call_parts = [f'"{vcvars_path_str}"', architecture]
    if vcvars_ver_opt: vcvars_call_parts.append(f"-vcvars_ver={vcvars_ver_opt}")
    command_str = ' '.join(f'"{part}"' for part in command_to_run)
    temp_bat_content = f"@echo off\nchcp 65001 > nul\ncall {' '.join(vcvars_call_parts)}\n{command_str}\n"
    temp_bat_file = pathlib.Path(os.getenv("TEMP", SCRIPT_DIR)) / f"vs_cmd_runner_{os.getpid()}.bat"
    try:
        temp_bat_file.write_text(temp_bat_content, encoding='utf-8')
        proc = subprocess.run(['cmd.exe', '/C', str(temp_bat_file)], capture_output=True, check=True, timeout=60, text=True, encoding='utf-8', errors='replace')
        return True, proc.stdout, proc.stderr
    except subprocess.CalledProcessError as e: return False, e.stdout, e.stderr
    except Exception as e: return False, "", str(e)
    finally:
        if temp_bat_file.exists(): temp_bat_file.unlink(missing_ok=True)

# ==============================================================================
# VS 环境扫描 & 环境变量提取函数
# ==============================================================================
def find_vswhere_executable():
    prog_files_x86 = os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")
    default_vswhere_path = pathlib.Path(prog_files_x86) / "Microsoft Visual Studio/Installer/vswhere.exe"
    if default_vswhere_path.is_file(): return str(default_vswhere_path)
    vswhere_in_path = shutil.which("vswhere")
    if vswhere_in_path: return vswhere_in_path
    return None

def scan_and_update_environments(app_config):
    vswhere_exe = find_vswhere_executable()
    if not vswhere_exe: print(f"{RED}错误: 未能定位 vswhere.exe。{RESET}"); return
    print(f"{BLUE}正在使用 {MAGENTA}{vswhere_exe}{BLUE} 扫描...{RESET}")
    try:
        cmd = [vswhere_exe, "-all", "-format", "json", "-utf8", "-products", "*", "-requires", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, encoding='utf-8', errors='replace')
        installations = json.loads(result.stdout)
    except Exception as e: print(f"{RED}vswhere.exe 执行失败: {e}{RESET}"); return
        
    existing_ids = {e.get("id") for e in app_config["manual_entries"]}
    newly_added_count = 0
    for inst in installations:
        install_path = pathlib.Path(inst.get("resolvedInstallationPath") or inst.get("installationPath", ""))
        vcvarsall_bat_path = install_path / "VC/Auxiliary/Build/vcvarsall.bat"
        if not vcvarsall_bat_path.exists(): continue
        vs_year = inst.get("catalog", {}).get("productLineVersion")
        display_name = inst.get("displayName", f"Visual Studio {vs_year}")
        msvc_tools_dir = install_path / "VC/Tools/MSVC"
        toolset_versions = [v.name for v in msvc_tools_dir.iterdir() if v.is_dir() and re.match(r"\d{2}\.\d{2}", v.name)] if msvc_tools_dir.exists() else []
        for ts_ver in sorted(toolset_versions, reverse=True):
            for arch in ["x64", "x86"]:
                gen_id = f"vs{vs_year}_{arch}_{ts_ver.replace('.', '')}"
                if gen_id in existing_ids: continue
                entry = {"id": gen_id, "displayName": f"{display_name} ({arch}) - v{ts_ver}", "vcvarsall_path": str(vcvarsall_bat_path), "vs_year": int(vs_year), "architecture": arch, "vcvars_ver_option": ts_ver}
                app_config["manual_entries"].append(entry)
                existing_ids.add(gen_id); newly_added_count += 1
                print(f"  {GREEN}已添加:{RESET} {entry['displayName']}")
    if newly_added_count == 0: print(f"{BLUE}没有新的环境被添加。{RESET}")

def get_env_from_vcvars(vcvars_path_str, architecture, vcvars_ver_opt=None):
    vcvars_path = pathlib.Path(vcvars_path_str)
    if not vcvars_path.exists(): return None
    separator = "---ENV_SEPARATOR---"
    cmd_parts = [f'"{str(vcvars_path)}"', architecture]
    if vcvars_ver_opt: cmd_parts.append(f"-vcvars_ver={vcvars_ver_opt}")
    temp_bat_content = f"@echo off\nchcp 65001 > nul\nset\necho {separator}\ncall {' '.join(cmd_parts)}\nset\n"
    temp_bat_file = pathlib.Path(os.getenv("TEMP", SCRIPT_DIR)) / f"vstemp_env_{os.getpid()}.bat"
    try:
        temp_bat_file.write_text(temp_bat_content, encoding='utf-8')
        proc = subprocess.run(['cmd.exe', '/C', str(temp_bat_file)], capture_output=True, text=False, timeout=60)
        if proc.returncode != 0: return None
        output_str = proc.stdout.decode('utf-8', errors='replace')
        before_str, after_str = output_str.split(separator, 1)
        def parse_env_block(block):
            env = {}; 
            for line in block.strip().splitlines():
                if '=' in line: key, value = line.split('=', 1); env[key.upper()] = value
            return env
        env_before, env_after = parse_env_block(before_str), parse_env_block(after_str)
        final_env = {}
        for key, value_after in env_after.items():
            if env_before.get(key) != value_after:
                if key == 'PATH':
                    paths_before = {p.strip().lower() for p in env_before.get(key, "").split(';') if p.strip()}
                    new_paths_raw = [p.strip() for p in value_after.split(';') if p.strip() and p.strip().lower() not in paths_before]
                    sanitized_new_paths = [p for p in new_paths_raw if pathlib.Path(p).is_dir()]
                    try:
                        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'System\CurrentControlSet\Control\Session Manager\Environment') as reg_key:
                            system_path_str, _ = winreg.QueryValueEx(reg_key, 'Path')
                    except FileNotFoundError:
                        system_path_str = ""
                    combined_paths = sanitized_new_paths + system_path_str.split(';')
                    final_env[key] = ';'.join(list(dict.fromkeys([p for p in combined_paths if p])))
                else:
                    final_env[key] = value_after
        return final_env
    except Exception: return None
    finally:
        if temp_bat_file.exists(): temp_bat_file.unlink(missing_ok=True)
        
# ==============================================================================
# 主功能模块
# ==============================================================================

def load_or_create_config(path):
    if path.exists():
        try: return json.loads(path.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, IOError): return None
    return {}

def save_config(data, path):
    try:
        path.write_text(json.dumps(data, indent=4, ensure_ascii=False), encoding='utf-8')
        return True
    except IOError: return False

def handle_install_wrapper(app_config, wrappers_config):
    active_id = app_config.get("current_active_environment_id")
    if not active_id: print(f"{RED}错误: 请先选择一个VS环境。{RESET}"); return
    active_entry = next((e for e in app_config.get("manual_entries", []) if e.get("id") == active_id), None)
    if not active_entry: print(f"{RED}错误: 未找到环境配置。{RESET}"); return

    while True:
        print(f"\n{CYAN}--- 安装新包装器 (VS环境: {MAGENTA}{active_entry['displayName']}{CYAN}) ---{RESET}")
        target_exe_path_str = input(f"{CYAN}请输入要包装的EXE路径 (输入'q'退出): {RESET}").strip('"')
        if target_exe_path_str.lower() == 'q': break
        target_exe_path = pathlib.Path(target_exe_path_str)
        if not target_exe_path.is_file() or target_exe_path.suffix.lower() != ".exe":
            print(f"{RED}错误: 路径不是一个有效的 .exe 文件。{RESET}"); continue

        exe_dir, exe_name, exe_stem, exe_suffix = target_exe_path.parent, target_exe_path.name, target_exe_path.stem, target_exe_path.suffix
        wrapper_id = str(hash(target_exe_path_str.lower()))
        
        if wrapper_id in wrappers_config and input(f"{YELLOW}警告: '{exe_name}' 已有包装器, 是否覆盖? (y/N): {RESET}").lower() != 'y':
            continue
        elif wrapper_id in wrappers_config:
            _uninstall_wrapper_by_id(wrapper_id, wrappers_config, silent=True)

        backup_name = f"{exe_stem}{WRAPPER_BACKUP_SUFFIX}{exe_suffix}"
        backup_path = exe_dir / backup_name
        args_filename = f"{exe_stem}_wrapper_args.txt"
        extra_args_list = input(f"{CYAN}请输入为 '{exe_name}' 添加的额外参数(空格分隔): {RESET}").split()

        print(f"{BLUE}正在提取VS环境以注入包装器...{RESET}")
        env_vars = get_env_from_vcvars(active_entry["vcvarsall_path"], active_entry["architecture"], active_entry.get("vcvars_ver_option"))
        if not env_vars: print(f"{RED}无法获取VS环境, 中止。{RESET}"); continue
            
        print(f"{BLUE}正在生成并编译C#包装器...{RESET}")
        print(f"{YELLOW}提示: 若编译失败, 请修改脚本顶部的 'CSHARP_WRAPPER_TEMPLATE'。{RESET}")
        env_vars_code = [f'        psi.EnvironmentVariables["{k}"] = @"{v.replace("\\", "\\\\").replace("\"", "\\\"")}";' for k, v in env_vars.items()]
        final_cs_code = CSHARP_WRAPPER_TEMPLATE.replace("// ##PYTHON_REPLACE_ENVIRONMENT_VARIABLES##", "\n".join(env_vars_code)).replace("__REAL_EXECUTABLE_PATH_PLACEHOLDER__", str(backup_path).replace('\\', '\\\\')).replace("__ARGS_FILENAME_PLACEHOLDER__", args_filename)
        generated_cs_path = SCRIPT_DIR / "Wrapper.generated.cs"
        generated_cs_path.write_text(final_cs_code, encoding='utf-8')
        
        temp_wrapper_exe = SCRIPT_DIR / "Wrapper.temp.exe"
        compile_cmd = ["csc.exe", "/nologo", f"/out:{temp_wrapper_exe}", str(generated_cs_path)]
        success, stdout, stderr = run_command_in_vs_env(compile_cmd, active_entry)

        if not success:
            print(f"{RED}编译失败!{RESET}\nOutput: {stdout}\nError: {stderr}")
            if generated_cs_path.exists(): generated_cs_path.unlink(missing_ok=True)
            continue
        
        print(f"{BLUE}正在部署包装器...{RESET}")
        try:
            target_exe_path.rename(backup_path)
            shutil.move(temp_wrapper_exe, target_exe_path)
        except Exception as e:
            print(f"{RED}文件操作失败: {e}{RESET}"); 
            if backup_path.exists(): backup_path.rename(target_exe_path)
            continue

        (exe_dir / args_filename).write_text("\n".join(extra_args_list), encoding='utf-8')
        wrappers_config[wrapper_id] = { "original_path": target_exe_path_str, "wrapper_path": str(target_exe_path), "backup_path": str(backup_path), "args_file": str(exe_dir / args_filename) }
        save_config(wrappers_config, WRAPPERS_CONFIG_FILE)
        print(f"{GREEN}成功为 '{exe_name}' 安装了包装器! 此包装器现在内含指定的VS环境。{RESET}")

def _uninstall_wrapper_by_id(wrapper_id, wrappers_config, silent=False):
    info = wrappers_config.get(wrapper_id)
    if not info:
        if not silent: print(f"{RED}错误: 无效的ID。{RESET}")
        return False
    wrapper_path, backup_path, args_file = pathlib.Path(info["wrapper_path"]), pathlib.Path(info["backup_path"]), pathlib.Path(info["args_file"])
    try:
        if wrapper_path.exists(): wrapper_path.unlink(missing_ok=True)
        if args_file.exists(): args_file.unlink(missing_ok=True)
        if backup_path.exists(): backup_path.rename(wrapper_path)
        del wrappers_config[wrapper_id]
        save_config(wrappers_config, WRAPPERS_CONFIG_FILE)
        if not silent: print(f"{GREEN}成功卸载 '{wrapper_path.name}' 的包装器。{RESET}")
        return True
    except Exception as e:
        if not silent: print(f"{RED}卸载时发生错误: {e}{RESET}")
        return False

def handle_uninstall_wrapper(wrappers_config):
    if not wrappers_config: print(f"{YELLOW}当前没有已安装的包装器。{RESET}"); return
    while True:
        print(f"\n{CYAN}--- 选择要卸载的包装器 ---{RESET}")
        wrapper_list = list(wrappers_config.items())
        for i, (id, info) in enumerate(wrapper_list): print(f"  {i+1}. {info['original_path']}")
        print("  0. 返回主菜单")
        choice_str = input(f"{CYAN}请输入序号: {RESET}").strip()
        if not choice_str: continue
        try:
            choice_idx = int(choice_str)
            if choice_idx == 0: break
            if 1 <= choice_idx <= len(wrapper_list):
                _uninstall_wrapper_by_id(wrapper_list[choice_idx - 1][0], wrappers_config)
                if not wrappers_config: break
            else: print(f"{RED}无效的序号。{RESET}")
        except ValueError: print(f"{RED}请输入数字。{RESET}")

def handle_set_permanent_env(app_config):
    """新功能: 只设置永久环境变量，不创建包装器"""
    active_id = app_config.get("current_active_environment_id")
    if not active_id: print(f"{RED}错误: 请先选择一个VS环境。{RESET}"); return
    active_entry = next((e for e in app_config.get("manual_entries", []) if e.get("id") == active_id), None)
    if not active_entry: print(f"{RED}错误: 未找到环境配置。{RESET}"); return

    print(f"\n{CYAN}--- 将VS环境 '{MAGENTA}{active_entry['displayName']}{CYAN}' 设为永久 ---{RESET}")
    print(f"{BLUE}正在提取环境变量...{RESET}")
    env_vars = get_env_from_vcvars(active_entry["vcvarsall_path"], active_entry["architecture"], active_entry.get("vcvars_ver_option"))
    if not env_vars: print(f"{RED}无法获取VS环境, 中止。{RESET}"); return

    print(f"{BLUE}正在通过注册表写入环境变量...{RESET}")
    success_count = 0
    for key, value in env_vars.items():
        ok, err = set_permanent_env_var_reg(key, value)
        if ok: success_count += 1
        else: print(f"{RED}  设置变量 '{key}' 失败: {err}{RESET}")
    
    if success_count > 0:
        print(f"{BLUE}正在广播环境变量更改消息...{RESET}")
        broadcast_env_change()
    
    print(f"{GREEN}成功设置 {success_count} 个永久环境变量。{RESET}")
    print(f"{YELLOW}强烈建议重启计算机以确保更改在所有程序和后台服务中完全生效。{RESET}")

def main():
    run_as_admin()
    if os.name == 'nt': os.system('')
    print(f"{CYAN}欢迎使用通用VS环境注入包装器管理平台!{RESET}")
    app_config = {"manual_entries": [], "current_active_environment_id": None}
    wrappers_config = load_or_create_config(WRAPPERS_CONFIG_FILE)
    if wrappers_config is None: sys.exit(1)

    while True:
        print("\n" + "="*20 + f"{MAGENTA} 主菜单 {RESET}" + "="*20)
        active_id = app_config.get("current_active_environment_id")
        active_display = "未设置"
        if active_id:
            entry = next((e for e in app_config.get("manual_entries", []) if e.get("id") == active_id), None)
            if entry: active_display = entry.get('displayName', active_id)
        print(f"{CYAN}当前选定VS环境: {MAGENTA}{active_display}{RESET}")
        print(f"{CYAN}已安装的包装器 ({len(wrappers_config)}): {', '.join([pathlib.Path(info['original_path']).name for info in wrappers_config.values()]) if wrappers_config else '(无)'}{RESET}")
        
        menu = {"1": "扫描系统中的VS环境", "2": "选择一个VS环境", "3": "安装新的可执行文件包装器", "4.": "卸载已有的包装器", "5": "将选定VS环境设为永久", "0": "退出"}
        for k, v in menu.items(): print(f"  {k}. {v}")
        choice = input(f"{CYAN}请输入选项: {RESET}").strip()

        try:
            if choice == '0': break
            elif choice == '1': scan_and_update_environments(app_config)
            elif choice == '2':
                if not app_config["manual_entries"]: print(f"{YELLOW}请先扫描(1)。{RESET}"); continue
                for i, entry in enumerate(app_config["manual_entries"]): print(f"  {i+1}. {entry.get('displayName')}")
                sel = input(f"{CYAN}请选择序号(0返回): {RESET}").strip()
                if sel and sel != '0': app_config["current_active_environment_id"] = app_config["manual_entries"][int(sel)-1]["id"]
            elif choice == '3': handle_install_wrapper(app_config, wrappers_config)
            elif choice == '4': handle_uninstall_wrapper(wrappers_config)
            elif choice == '5': handle_set_permanent_env(app_config)
            else: print(f"{RED}无效选项。{RESET}")
        except (ValueError, IndexError): print(f"{RED}请输入有效的数字。{RESET}")
        except KeyboardInterrupt: print(f"\n{YELLOW}操作已取消。{RESET}")
        except Exception as e: print(f"{RED}发生意外错误: {e}{RESET}"); traceback.print_exc()

if __name__ == "__main__":
    main()