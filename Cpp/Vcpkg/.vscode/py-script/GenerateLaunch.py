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

    # +++ 添加 _save_to_file 方法 +++
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
    # ++++++++++++++++++++++++++++++++

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
                        OrderedDict([ # 使用 OrderedDict 保证内部顺序
                            ("description", "Enable pretty-printing for gdb"),
                            ("text", "-enable-pretty-printing"),
                            ("ignoreFailures", True)
                        ])
                    ]
                new_launch_configs.append(default_block)
        
        self.generated_launch_configs = new_launch_configs
        print_success(f"已为扫描到的文件生成/更新 {len(self.generated_launch_configs)} 条内存中的启动配置。")


    def _edit_list_or_obj_property(self, current_value_ref, prop_name: str, is_env_list: bool = False):
        # 直接修改传入的引用 current_value_ref (它应该是 block_to_edit[key_to_edit])
        temp_data = copy.deepcopy(current_value_ref) 
        
        print_menu_header(f"编辑 '{prop_name}' (复杂结构)")
        # ... (省略了这部分内部逻辑，与前一版本相同，确保它修改 temp_data)
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
                    # 应用更改到原始引用
                    if isinstance(current_value_ref, list):
                        current_value_ref[:] = temp_data 
                    elif isinstance(current_value_ref, dict):
                        current_value_ref.clear()
                        current_value_ref.update(temp_data)
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
                    line = sys.stdin.readline().rstrip('\n') # 使用 sys.stdin.readline
                    if line.strip().upper() == 'EOF': break
                    new_json_lines.append(line)
                new_json_str = "\n".join(new_json_lines)
                try:
                    new_data_from_json = json.loads(new_json_str, object_pairs_hook=OrderedDict)
                    # 应用更改到原始引用
                    if isinstance(current_value_ref, list): current_value_ref[:] = new_data_from_json
                    elif isinstance(current_value_ref, dict): current_value_ref.clear(); current_value_ref.update(new_data_from_json)
                    else: # Should not happen if current_value_ref was a list/dict
                          print_error("内部错误：尝试修改非容器类型的复杂属性。")
                    print_success(f"'{prop_name}' 已通过JSON更新。")
                except json.JSONDecodeError:
                    print_error("无效的JSON格式，未更新。")

    def manage_launch_configs_interactive(self):
        page_size = 10
        current_page = 0

        while True:
            print_menu_header("管理生成的启动配置")
            if not self.generated_launch_configs:
                print_info("没有扫描到或生成的启动配置。请先扫描可执行文件目录。")
                print_option("s", "设置可执行文件目录并扫描")
                print_option("b", "返回主菜单")
                choice = input(f"{BLUE}选择 > {RESET}").strip().lower()
                if choice == 's': self.set_executables_directory_and_scan()
                elif choice == 'b': return
                else: print_error("无效选项")
                continue

            start_index = current_page * page_size
            end_index = start_index + page_size
            page_items = self.generated_launch_configs[start_index:end_index]

            print_info(f"显示第 {current_page + 1} 页 (共 { (len(self.generated_launch_configs) - 1) // page_size + 1} 页)")
            for i, config_block in enumerate(page_items):
                actual_index = start_index + i
                program_path = config_block.get('program', 'N/A')
                program_display = f"...{program_path[-50:]}" if len(program_path) > 50 else program_path
                print_option(str(i + 1), f"{config_block.get('name', '未命名配置')} (程序: {program_display})")
            
            print("---")
            if current_page > 0: print_option("p", "上一页")
            if end_index < len(self.generated_launch_configs): print_option("n", "下一页")
            print_option("s", "重新扫描 (当前目录: '" + self.executables_dir_rel + "')")
            if page_items: # 只有当前页有项目时才显示删除和编辑
                print_option("d", "删除一个配置 (从当前页选择)")
                print_option("e", "编辑一个配置 (从当前页选择)")
            print_option("b", "完成管理并返回主菜单")

            choice = input(f"{BLUE}选择操作或配置编号 > {RESET}").strip().lower()

            if choice == 'b': break
            elif choice == 'p' and current_page > 0: current_page -= 1
            elif choice == 'n' and end_index < len(self.generated_launch_configs): current_page += 1
            elif choice == 's': self.set_executables_directory_and_scan(); current_page = 0 # 扫描后重置到第一页
            elif choice == 'd' and page_items:
                try:
                    num_on_page_str = input(f"{BLUE}输入当前页上要删除配置的编号: {RESET}").strip()
                    num_on_page = int(num_on_page_str) -1
                    if 0 <= num_on_page < len(page_items):
                        actual_idx_to_delete = start_index + num_on_page
                        deleted_name = self.generated_launch_configs[actual_idx_to_delete].get('name')
                        confirm = input(f"{YELLOW}确定删除 '{deleted_name}'? (y/N): {RESET}").strip().lower()
                        if confirm == 'y':
                            self.generated_launch_configs.pop(actual_idx_to_delete)
                            print_success(f"配置 '{deleted_name}' 已从内存中删除。")
                            if start_index >= len(self.generated_launch_configs) and current_page > 0: current_page -=1
                        else: print_info("删除已取消。")
                    else: print_error("页内编号无效。")
                except ValueError: print_error("请输入数字。")
            elif (choice == 'e' or choice.isdigit()) and page_items:
                idx_to_process_str = choice if choice.isdigit() else input(f"{BLUE}输入当前页上要编辑配置的编号: {RESET}").strip()
                try:
                    num_on_page = int(idx_to_process_str) - 1
                    if 0 <= num_on_page < len(page_items):
                        actual_idx_to_edit = start_index + num_on_page
                        self._edit_single_launch_config_block(actual_idx_to_edit)
                    else: print_error("页内编号无效。")
                except ValueError: print_error("请输入有效的数字编号。" if choice == 'e' else "无效输入。")
            else:
                print_error("无效输入。")
            # input(f"{BLUE}按回车键继续...{RESET}") # 放在循环末尾或特定操作后


    def _edit_single_launch_config_block(self, block_index_in_memory: int):
        if not (0 <= block_index_in_memory < len(self.generated_launch_configs)):
            print_error("无效的配置块索引。")
            return
        
        block_to_edit = self.generated_launch_configs[block_index_in_memory]
        block_name_display = block_to_edit.get("name", f"配置 {block_index_in_memory+1}")
        
        while True:
            print_menu_header(f"编辑启动配置: '{block_name_display}'")
            editable_fields_for_menu = list(EDITABLE_LAUNCH_KEYS.items())

            for i, (key, desc) in enumerate(editable_fields_for_menu):
                # 只显示块中实际存在的、且在EDITABLE_LAUNCH_KEYS中的键，或者所有EDITABLE_LAUNCH_KEYS中的键
                # 为了简单，我们显示所有EDITABLE_LAUNCH_KEYS，如果块中没有则显示"未设置"
                current_val = block_to_edit.get(key)
                preview_str = ""
                if isinstance(current_val, list): preview_str = f"列表 (共 {len(current_val)} 项)"
                elif isinstance(current_val, dict): preview_str = f"对象 (共 {len(current_val)} 键)"
                elif current_val is None: preview_str = f"{YELLOW}未设置{RESET}"
                else: preview_str = str(current_val)
                print_option(str(i + 1), f"{desc} (当前: {preview_str})")
            
            print_option("0", f"完成编辑 '{block_name_display}'")
            
            choice_str = input(f"{BLUE}请选择要编辑的属性编号 > {RESET}").strip()
            if choice_str == '0': break

            try:
                selected_attr_idx = int(choice_str) - 1
                if not (0 <= selected_attr_idx < len(editable_fields_for_menu)):
                    print_error("无效的属性编号。"); continue

                key_to_edit, desc_of_key = editable_fields_for_menu[selected_attr_idx]
                # 确保操作的是 block_to_edit[key_to_edit] 的引用 (对于列表/字典)
                # 或直接修改 block_to_edit[key_to_edit] (对于简单类型)
                
                print_info(f"\n--- 正在编辑 '{block_name_display}' 的 '{desc_of_key}' ---")

                if key_to_edit == "environment":
                    if key_to_edit not in block_to_edit or not isinstance(block_to_edit[key_to_edit], list):
                        block_to_edit[key_to_edit] = [] # 初始化
                    self._edit_list_or_obj_property(block_to_edit[key_to_edit], desc_of_key, is_env_list=True)
                elif key_to_edit in ["logging", "sourceFileMap", "setupCommands"]: 
                    if key_to_edit not in block_to_edit or not isinstance(block_to_edit[key_to_edit], (dict, list)):
                         block_to_edit[key_to_edit] = OrderedDict() if key_to_edit != "setupCommands" else []
                    self._edit_list_or_obj_property(block_to_edit[key_to_edit], desc_of_key)
                elif key_to_edit == "stopAtEntry":
                    current_value = block_to_edit.get(key_to_edit, True) # 默认为True如果不存在
                    current_bool_val_str = str(current_value).lower()
                    new_val_str = input(f"{BLUE}输入新值 ('true'/'false') [当前: {current_bool_val_str}, 回车保留]: {RESET}").strip().lower()
                    if new_val_str == "true": block_to_edit[key_to_edit] = True; print_success("已更新。")
                    elif new_val_str == "false": block_to_edit[key_to_edit] = False; print_success("已更新。")
                    elif new_val_str == "" : pass # 保留
                    else: print_warning("无效输入或未更改。")
                else: 
                    current_value = block_to_edit.get(key_to_edit, "") # 默认为空字符串如果不存在
                    current_str_val = str(current_value)
                    new_val = input(f"{BLUE}输入新值 [当前: '{current_str_val}', 回车保留]: {RESET}").strip()
                    if new_val or (new_val == "" and current_value is not None): 
                        if new_val != current_str_val:
                            block_to_edit[key_to_edit] = new_val
                            print_success("已更新。")
                input(f"{BLUE}按回车键继续...{RESET}")
            except ValueError: print_error("请输入有效的数字编号。")


    def set_executables_directory_and_scan(self):
        print_menu_header("设置可执行文件目录")
        current_dir = self.executables_dir_rel
        new_dir_rel = input(f"{BLUE}请输入可执行文件目录 (相对于项目根 '{self.project_dir}', 当前: '{current_dir}', 回车保留): {RESET}").strip()
        
        if new_dir_rel:
            self.executables_dir_rel = pathlib.Path(new_dir_rel.strip('/\\')).as_posix()
            print_success(f"可执行文件目录已更新为: '{self.executables_dir_rel}'")
        
        self.scan_executables()
        input(f"{BLUE}按回车键继续...{RESET}")


    def generate_and_save_launch_file(self):
        print_action("准备生成/更新 launch.json 文件")

        if not self.generated_launch_configs:
            print_warning("内存中没有已生成/编辑的启动配置。是否要先扫描可执行文件目录？")
            choice = input(f"{BLUE}扫描可执行文件目录 (当前: '{self.executables_dir_rel}')? (Y/n): {RESET}").strip().lower()
            if choice != 'n':
                self.scan_executables()
                if not self.generated_launch_configs:
                    print_info("扫描后仍无配置，取消生成。")
                    input(f"\n{BLUE}按回车键返回主菜单...{RESET}")
                    return
            else:
                print_info("已取消生成。")
                input(f"\n{BLUE}按回车键返回主菜单...{RESET}")
                return

        file_data = self._load_existing_file_or_default_for_launch()
        existing_configurations_in_file = file_data.get("configurations", [])
        
        final_configurations_for_file = []
        processed_program_paths_from_file = set()

        for mem_config in self.generated_launch_configs:
            mem_program_path = mem_config.get("program")
            if not mem_program_path: 
                print_warning(f"内存中发现一个没有 'program' 路径的配置: '{mem_config.get('name', '未命名')}'，已跳过。")
                continue

            match_found_in_file = False
            for i, file_config_block in enumerate(existing_configurations_in_file):
                if isinstance(file_config_block, dict) and file_config_block.get("program") == mem_program_path:
                    print_info(f"更新文件中已有的配置: '{mem_config.get('name')}' (基于 program path)")
                    updated_block = copy.deepcopy(file_config_block) 
                    for key, mem_value in mem_config.items():
                        updated_block[key] = copy.deepcopy(mem_value) 
                    final_configurations_for_file.append(updated_block)
                    processed_program_paths_from_file.add(mem_program_path)
                    match_found_in_file = True
                    # 将此块从 existing_configurations_in_file 中标记为已处理（或移除），以简化阶段B
                    # 为简单起见，我们使用 processed_program_paths_from_file 集合
                    break 
            
            if not match_found_in_file:
                print_info(f"追加新的启动配置到文件: '{mem_config.get('name')}'")
                final_configurations_for_file.append(copy.deepcopy(mem_config))

        for file_config_block in existing_configurations_in_file:
            if isinstance(file_config_block, dict):
                file_program_path = file_config_block.get("program")
                if file_program_path not in processed_program_paths_from_file:
                    print_info(f"保留文件中用户自定义的启动配置: '{file_config_block.get('name', '未命名')}'")
                    final_configurations_for_file.append(copy.deepcopy(file_config_block))
                elif not file_program_path:
                    is_already_added = any(fc == file_config_block for fc in final_configurations_for_file)
                    if not is_already_added:
                        print_info(f"保留文件中无program路径的用户自定义配置: '{file_config_block.get('name', '未命名')}'")
                        final_configurations_for_file.append(copy.deepcopy(file_config_block))
            else: 
                final_configurations_for_file.append(copy.deepcopy(file_config_block))

        file_data_to_save = OrderedDict([
            ("version", DEFAULT_LAUNCH_VERSION),
            ("configurations", final_configurations_for_file)
        ])

        self._save_to_file(file_data_to_save, "launch.json") # 明确指定文件名
        input(f"\n{BLUE}按回车键返回主菜单...{RESET}")

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

        while self.is_running:
            print_menu_header("VSCode launch.json 生成器")
            print_config_item("项目目录", str(self.project_dir))
            print_config_item("可执行文件扫描目录 (相对项目根)", self.executables_dir_rel)
            print_config_item("内存中已配置的启动项数", str(len(self.generated_launch_configs)))
            print("------------------------------------")
            print_option("1", "设置可执行文件目录并扫描")
            print_option("2", "查看/管理扫描到的启动配置 (分页)")
            print_option("3", "生成/更新 launch.json 文件")
            print_option("0", "退出")
            print("------------------------------------")

            choice = input(f"{BLUE}请输入您的选择 > {RESET}").strip()

            try:
                if choice == '1':
                    self.set_executables_directory_and_scan()
                elif choice == '2':
                    self.manage_launch_configs_interactive()
                elif choice == '3':
                    self.generate_and_save_launch_file()
                elif choice == '0':
                    print_info("感谢使用，程序已退出。")
                    self.is_running = False
                else:
                    print_error("无效的选择，请重新输入。")
            except KeyboardInterrupt:
                print_warning("\n操作被用户中断。返回主菜单。")
            except Exception as e:
                print_error(f"发生意外错误: {e}")
                print_info("已返回主菜单。")

def main_interactive():
    project_dir_env = os.environ.get("PROJECT_DIR")
    if not project_dir_env:
        print_error("未设置 PROJECT_DIR 环境变量。请设置该变量指向项目根目录。")
        sys.exit(1)
    
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