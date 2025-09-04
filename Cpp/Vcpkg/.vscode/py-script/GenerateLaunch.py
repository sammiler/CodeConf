import json
import os
import pathlib
import platform
import sys
import stat # 用于检查文件权限
import copy
from collections import OrderedDict

# --- ANSI 颜色代码和辅助打印函数 ---
BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"
BOLD = "\033[1m"

def print_info(message): print(f"{BLUE}ℹ️  {message}{RESET}")
def print_success(message): print(f"{GREEN}✅ {message}{RESET}")
def print_warning(message): print(f"{YELLOW}⚠️  {message}{RESET}")
def print_error(message): print(f"{RED}❌ {message}{RESET}")
def print_action(command_to_display): print(f"\n{BLUE}▶️  {command_to_display}{RESET}")
def print_option(key, text): print(f"  {GREEN}{key}{RESET} - {text}")
def print_menu_header(title): print(f"\n{BOLD}--- {title} ---{RESET}")
def print_config_item(key, value_str): print(f"  {key}: {YELLOW}{value_str}{RESET}")

# --- 默认 Launch 配置相关 ---
DEFAULT_LAUNCH_VERSION = "0.2.0"

# ⬇️⬇️⬇️ 1. 在这里定义我们固定的 Python Attach 配置 ⬇️⬇️⬇️
FIXED_PYTHON_ATTACH_CONFIG = OrderedDict([
    ("name", "Python: Attach to C++ Process"),
    ("type", "debugpy"),
    ("request", "attach"),
    ("connect", OrderedDict([
        ("host", "127.0.0.1"),
        ("port", 5678)
    ])),
    ("justMyCode", False),
    ("pathMappings", [
        OrderedDict([
            ("localRoot", "${workspaceFolder}"),
            ("remoteRoot", "${workspaceFolder}")
        ])
    ])
])
# ⬆️⬆️⬆️ 1. 定义完毕 ⬆️⬆️⬆️

EDITABLE_LAUNCH_KEYS = OrderedDict([
    ("name", "配置名称"),
    ("type", "调试器类型 (e.g., cppvsdbg, cppdbg)"),
    ("request", "请求类型 (e.g., launch, attach)"),
    ("stopAtEntry", "程序启动时断点 (true/false)"),
    ("console", "控制台类型 (e.g., internalConsole, integratedTerminal)"),
    ("visualizerFile", "可视化工具文件路径 (.natvis)"),
    ("program", "程序路径 (通常自动填充，谨慎修改)"),
    ("cwd", "工作目录"),
    ("environment", "环境变量列表 (高级)"),
    ("logging", "日志配置 (高级)"),
    ("sourceFileMap", "源文件映射 (高级)"),
    ("MIMode", "MI 模式 (e.g., gdb, lldb)"),
    ("miDebuggerPath", "调试器路径 (e.g., /usr/bin/gdb)"),
    ("setupCommands", "调试器启动命令 (高级)")
])

NON_EXECUTABLE_SUFFIXES_NON_WINDOWS = ['.so', '.dylib', '.dll', '.a', '.lib', '.o', '.bundle']


class InteractiveLaunchConfigGenerator:
    def __init__(self, project_dir_path: pathlib.Path):
        self.project_dir = project_dir_path
        self.vscode_dir = self.project_dir / ".vscode"
        self.launch_file_path = self.vscode_dir / "launch.json"
        
        self.executables_dir_rel: str = "build/bin" 
        self.generated_launch_configs: list[OrderedDict] = []
        
        self.is_running = True
        self.current_os_platform = platform.system()
        print_info(f"当前检测到的操作系统: {self.current_os_platform}")

    def _save_to_file(self, data_to_save: OrderedDict, filename: str = "launch.json"):
        """将数据保存到 .vscode 目录下的指定文件。"""
        output_path = self.vscode_dir / filename
        print_action(f"正在保存配置到 {output_path}")
        try:
            self.vscode_dir.mkdir(parents=True, exist_ok=True) # 确保 .vscode 目录存在
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, indent=4, ensure_ascii=False)
            print_success(f"配置已成功保存到: {output_path}")
        except Exception as e:
            print_error(f"保存文件 '{output_path}' 失败: {e}")

    def _get_platform_specific_default_type(self) -> str:
        if self.current_os_platform == "Windows":
            return "cppvsdbg"
        return "cppdbg"

    def _is_likely_executable_non_windows(self, file_path: pathlib.Path) -> bool:
        if not file_path.is_file():
            return False
        if file_path.suffix.lower() in NON_EXECUTABLE_SUFFIXES_NON_WINDOWS:
            return False
        try:
            mode = file_path.stat().st_mode
            if not (mode & stat.S_IXUSR or mode & stat.S_IXGRP or mode & stat.S_IXOTH):
                return False 
        except Exception:
            pass 
        return True

    def scan_executables(self):
        print_action(f"扫描可执行文件于 '{self.project_dir / self.executables_dir_rel}'")
        target_dir = self.project_dir / self.executables_dir_rel
        
        if not target_dir.is_dir():
            print_warning(f"目录 '{target_dir}' 不存在或不是一个目录。无法扫描。")
            self.generated_launch_configs = []
            return

        discovered_exe_infos = []
        for item in target_dir.rglob("*"):
            if self.current_os_platform == "Windows":
                if item.is_file() and item.suffix.lower() == ".exe":
                    discovered_exe_infos.append({"name": item.stem, "path": str(item).replace("\\", "/")})
            else: 
                if self._is_likely_executable_non_windows(item):
                    discovered_exe_infos.append({"name": item.name, "path": str(item).replace("\\", "/")})
        
        if not discovered_exe_infos:
            print_info("未找到可执行文件。")
            self.generated_launch_configs = []
            return

        print_success(f"扫描到 {len(discovered_exe_infos)} 个潜在的可执行文件。正在生成默认启动配置...")
        
        new_launch_configs = []
        default_visualizer = "C:/Users/sammiler/MyFile/My Doc/Visual Studio 2022/Visualizers/qt5.natvis"

        for exe_info in discovered_exe_infos:
            config_name = f"Debug {exe_info['name']}"
            existing_config_for_exe = next((c for c in self.generated_launch_configs if c.get("program") == exe_info["path"]), None)

            if existing_config_for_exe:
                existing_config_for_exe["name"] = config_name
                new_launch_configs.append(existing_config_for_exe)
            else:
                default_block = OrderedDict([
                    ("name", config_name),
                    ("program", exe_info["path"]),
                    ("type", self._get_platform_specific_default_type()),
                    ("request", "launch"),
                    ("stopAtEntry", True),
                    ("cwd", str(target_dir).replace("\\", "/")),
                    ("environment", []),
                    ("console", "internalConsole"),
                    ("logging", OrderedDict([("moduleLoad", True), ("exceptions", True)])),
                    ("visualizerFile", default_visualizer if default_visualizer else ""),
                    ("sourceFileMap", OrderedDict())
                ])
                if self.current_os_platform != "Windows":
                    default_block["MIMode"] = "gdb" 
                    default_block["miDebuggerPath"] = "/usr/bin/gdb" 
                    default_block["setupCommands"] = [
                        OrderedDict([
                            ("description", "Enable pretty-printing for gdb"),
                            ("text", "-enable-pretty-printing"),
                            ("ignoreFailures", True)
                        ])
                    ]
                new_launch_configs.append(default_block)
        
        self.generated_launch_configs = new_launch_configs
        print_success(f"已为扫描到的文件生成/更新 {len(self.generated_launch_configs)} 条内存中的启动配置。")

    def _edit_list_or_obj_property(self, current_value_ref, prop_name: str, is_env_list: bool = False):
        temp_data = copy.deepcopy(current_value_ref) 
        
        print_menu_header(f"编辑 '{prop_name}' (复杂结构)")
        if is_env_list and isinstance(temp_data, list):
             while True:
                print_info("\nEnvironment 变量列表:")
                if not temp_data: print_info("列表为空。")
                else:
                    for i, env_item in enumerate(temp_data):
                        if isinstance(env_item, dict) and "name" in env_item and "value" in env_item:
                            print(f"  {i+1}: {env_item['name']} = {env_item['value']}")
                        else: print(f"  {i+1}: {str(env_item)} (格式可能不标准)")
                print_option("a", "添加环境变量")
                if temp_data: print_option("r", "移除环境变量")
                print_option("c", "确认更改")
                print_option("d", "放弃更改")
                choice = input(f"{BLUE}操作 > {RESET}").strip().lower()
                if choice == 'a':
                    name = input(f"{BLUE}变量名: {RESET}").strip()
                    value = input(f"{BLUE}变量值: {RESET}").strip()
                    if name: temp_data.append(OrderedDict([("name",name), ("value",value)])); print_success("已临时添加")
                elif choice == 'r' and temp_data:
                    try:
                        idx = int(input(f"{BLUE}编号: {RESET}").strip()) - 1
                        if 0 <= idx < len(temp_data): temp_data.pop(idx); print_success("已临时移除")
                        else: print_error("无效编号")
                    except ValueError: print_error("输入数字")
                elif choice == 'c': 
                    if isinstance(current_value_ref, list): current_value_ref[:] = temp_data 
                    elif isinstance(current_value_ref, dict): current_value_ref.clear(); current_value_ref.update(temp_data)
                    print_success("Environment已更新"); break
                elif choice == 'd': print_info("Environment更改已放弃"); break
                else: print_error("无效选择")
        else: 
            print_info("当前值 (JSON格式):")
            try: print(json.dumps(temp_data, indent=4))
            except TypeError: print(str(temp_data))
            replace = input(f"{BLUE}是否要粘贴新的JSON片段替换当前 '{prop_name}'? (y/N): {RESET}").strip().lower()
            if replace == 'y':
                print_info("请粘贴新的JSON内容。多行输入，结束后输入'EOF'然后回车。")
                new_json_lines = []
                while True:
                    line = sys.stdin.readline().rstrip('\n')
                    if line.strip().upper() == 'EOF': break
                    new_json_lines.append(line)
                new_json_str = "\n".join(new_json_lines)
                try:
                    new_data_from_json = json.loads(new_json_str, object_pairs_hook=OrderedDict)
                    if isinstance(current_value_ref, list): current_value_ref[:] = new_data_from_json
                    elif isinstance(current_value_ref, dict): current_value_ref.clear(); current_value_ref.update(new_data_from_json)
                    else: print_error("内部错误：尝试修改非容器类型的复杂属性。")
                    print_success(f"'{prop_name}' 已通过JSON更新。")
                except json.JSONDecodeError:
                    print_error("无效的JSON格式，未更新。")


    # ⬇️⬇️⬇️ 2. 修改这个核心方法 ⬇️⬇️⬇️
    def generate_and_save_launch_file(self):
        print_action("准备生成/更新 launch.json 文件")

        # 检查内存中的 C++ 启动配置
        if not self.generated_launch_configs:
            print_warning("内存中没有已生成的 C++ 启动配置。是否要先扫描可执行文件目录？")
            self.scan_executables()
        # 加载现有的 launch.json 文件内容
        file_data = self._load_existing_file_or_default_for_launch()
        existing_configurations_in_file = file_data.get("configurations", [])
        
        final_configurations_for_file = []
        
        # --- 阶段 A: 处理内存中的 C++ 配置 (扫描到的/编辑过的) ---
        processed_program_paths_from_file = set()

        # A.1: 更新或追加内存中的配置到最终列表
        for mem_config in self.generated_launch_configs:
            mem_program_path = mem_config.get("program")
            if not mem_program_path: 
                print_warning(f"内存中发现一个没有 'program' 路径的配置: '{mem_config.get('name', '未命名')}'，已跳过。")
                continue
            
            # 我们直接把内存中的版本作为最新版本加入
            print_info(f"添加/更新来自内存的 C++ 配置: '{mem_config.get('name')}'")
            final_configurations_for_file.append(copy.deepcopy(mem_config))
            processed_program_paths_from_file.add(mem_program_path)

        # A.2: 保留文件中那些未被内存中配置覆盖的用户自定义 C++ 配置
        for file_config_block in existing_configurations_in_file:
            # 只处理 C++ 相关的配置
            if isinstance(file_config_block, dict) and file_config_block.get("type") in ["cppvsdbg", "cppdbg"]:
                file_program_path = file_config_block.get("program")
                if file_program_path not in processed_program_paths_from_file:
                    print_info(f"保留文件中用户自定义的 C++ 配置: '{file_config_block.get('name', '未命名')}'")
                    final_configurations_for_file.append(copy.deepcopy(file_config_block))

        # --- 阶段 B: 处理固定的 Python Attach 配置 ---
        python_attach_config_name = FIXED_PYTHON_ATTACH_CONFIG.get("name")
        
        # 查找文件中是否已存在同名的 Python Attach 配置
        existing_python_attach_in_file = next((c for c in existing_configurations_in_file if isinstance(c, dict) and c.get("name") == python_attach_config_name), None)
        
        if existing_python_attach_in_file:
            # 如果存在，保留文件中的版本，因为用户可能修改过它 (比如端口号)
            print_info(f"保留文件中已有的 '{python_attach_config_name}' 配置。")
            final_configurations_for_file.append(copy.deepcopy(existing_python_attach_in_file))
        else:
            # 如果不存在，则添加我们预设的默认版本
            print_info(f"添加新的 '{python_attach_config_name}' 配置到文件。")
            final_configurations_for_file.append(copy.deepcopy(FIXED_PYTHON_ATTACH_CONFIG))

        # --- 阶段 C: 组合并保存 ---
        file_data_to_save = OrderedDict([
            ("version", DEFAULT_LAUNCH_VERSION),
            ("configurations", final_configurations_for_file)
        ])

        self._save_to_file(file_data_to_save, "launch.json")

    def _load_existing_file_or_default_for_launch(self) -> OrderedDict:
        if not self.launch_file_path.exists():
            return OrderedDict([("version", DEFAULT_LAUNCH_VERSION), ("configurations", [])])
        try:
            with open(self.launch_file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    return OrderedDict([("version", DEFAULT_LAUNCH_VERSION), ("configurations", [])])
                data = json.loads(content, object_pairs_hook=OrderedDict)
                if "configurations" not in data or not isinstance(data["configurations"], list):
                    data["configurations"] = []
                if "version" not in data:
                    data["version"] = DEFAULT_LAUNCH_VERSION
                return data
        except Exception:
            return OrderedDict([("version", DEFAULT_LAUNCH_VERSION), ("configurations", [])])

    def main_loop(self):
        if not self.generated_launch_configs :
            self.scan_executables()
        self.generate_and_save_launch_file()

def main_interactive():
    project_dir_env = os.environ.get("PROJECT_DIR")
    project_dir = None
    if not project_dir_env:
        print_error("未设置 PROJECT_DIR 环境变量。将设置默认项目根目录。")
        current_script_path = pathlib.Path(__file__).resolve()
        path_iterator = current_script_path
        while path_iterator.parent != path_iterator:
            if (path_iterator / ".vscode").is_dir():
                project_dir = path_iterator
                break
            path_iterator = path_iterator.parent        
    else:
        project_dir = pathlib.Path(project_dir_env).resolve()
    if not project_dir.is_dir():
        print_error(f"PROJECT_DIR '{project_dir_env}' 不是一个有效的目录。")
        sys.exit(1)
    
    app = InteractiveLaunchConfigGenerator(project_dir)
    app.main_loop()

if __name__ == "__main__":
    try:
        main_interactive()
    except SystemExit: pass
    except Exception as e:
        print_error(f"脚本执行遇到顶层错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)