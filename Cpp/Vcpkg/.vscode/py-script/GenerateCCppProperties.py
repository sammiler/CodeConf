import json
import os
import pathlib
import platform # 用于检测当前操作系统
import sys
import copy # 用于深拷贝配置
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

# --- 内置的完整三平台默认 C/C++ 属性配置 ---
DEFAULT_FULL_C_CPP_PROPERTIES = OrderedDict([
    ("configurations", [
        OrderedDict([
            ("name", "Win32"),
            ("includePath", ["${workspaceFolder}/**", "${vcpkgRoot}/include"]),
            ("defines", ["_DEBUG", "UNICODE", "_UNICODE"]),
            ("intelliSenseMode", "windows-msvc-x64"),
            ("compilerPath", "C:/Program Files/Microsoft Visual Studio/2022/Enterprise/VC/Tools/MSVC/14.43.34808/bin/Hostx64/x64/cl.exe"),
            ("cStandard", "c17"),
            ("cppStandard", "c++17"),
            ("configurationProvider", "ms-vscode.cmake-tools"),
            ("mergeConfigurations", True)
        ]),
        OrderedDict([
            ("name", "Linux"),
            ("includePath", ["${workspaceFolder}/**", "${vcpkgRoot}/include"]),
            ("defines", ["_DEBUG", "UNICODE", "_UNICODE"]),
            ("intelliSenseMode", "linux-gcc-x64"),
            ("compilerPath", "/usr/bin/gcc"),
            ("cStandard", "c17"),
            ("cppStandard", "c++17"),
            ("configurationProvider", "ms-vscode.cmake-tools"),
            ("mergeConfigurations", True)
        ]),
        OrderedDict([
            ("name", "macOS"),
            ("includePath", ["${workspaceFolder}/**", "${vcpkgRoot}/include"]),
            ("defines", ["_DEBUG", "UNICODE", "_UNICODE"]),
            ("intelliSenseMode", "macos-clang-x64"),
            ("compilerPath", "/usr/bin/clang"),
            ("cStandard", "c17"),
            ("cppStandard", "c++17"),
            ("configurationProvider", "ms-vscode.cmake-tools"),
            ("mergeConfigurations", True)
        ])
    ]),
    ("version", 4)
])

# 用户可以编辑的键 (除了name，因为name用于匹配)
# 我们会基于这个列表来生成可编辑属性的菜单
USER_EDITABLE_KEYS_IN_BLOCK = OrderedDict([
    ("includePath", "Include 路径列表"),
    ("defines", "预定义宏列表"),
    ("intelliSenseMode", "IntelliSense 模式"),
    ("compilerPath", "编译器路径"),
    ("cStandard", "C 标准"),
    ("cppStandard", "C++ 标准"),
    ("mergeConfigurations", "合并配置 (true/false)")
    # 更多键可以在这里添加描述
])

class InteractiveVSCodeCppPropertiesManager:
    def __init__(self, project_dir_path: pathlib.Path):
        self.project_dir = project_dir_path
        self.vscode_dir = self.project_dir / ".vscode"
        self.c_cpp_properties_file_path = self.vscode_dir / "c_cpp_properties.json"
        
        self.in_memory_configs: OrderedDict = copy.deepcopy(DEFAULT_FULL_C_CPP_PROPERTIES)
        
        self.is_running = True
        self.current_os_platform_name = self._get_current_os_platform_name()
        print_info(f"当前检测到的操作系统平台对应的配置名称: {self.current_os_platform_name}")

    def _get_current_os_platform_name(self) -> str:
        system = platform.system()
        if system == "Windows": return "Win32"
        if system == "Linux": return "Linux"
        if system == "Darwin": return "macOS"
        print_warning(f"未知的操作系统: {system}。将无法自动确定当前平台配置。")
        return "Unknown"

    def _load_existing_file_or_default(self) -> OrderedDict:
        if not self.c_cpp_properties_file_path.exists():
            print_info(f"文件 '{self.c_cpp_properties_file_path}' 不存在。将从空配置开始追加。")
            return OrderedDict([("configurations", []), ("version", 4)])
        try:
            with open(self.c_cpp_properties_file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    print_warning(f"文件 '{self.c_cpp_properties_file_path}' 为空。将从空配置开始追加。")
                    return OrderedDict([("configurations", []), ("version", 4)])
                
                data = json.loads(content, object_pairs_hook=OrderedDict)
                if "configurations" not in data or not isinstance(data["configurations"], list):
                    print_warning(f"文件 '{self.c_cpp_properties_file_path}' 结构无效。将尝试保留但可能出错。")
                    data["configurations"] = []
                if "version" not in data : data["version"] = 4
                return data
        except json.JSONDecodeError:
            print_error(f"文件 '{self.c_cpp_properties_file_path}' 包含无效JSON。将从空配置开始追加。")
            return OrderedDict([("configurations", []), ("version", 4)])
        except Exception as e:
            print_error(f"加载 '{self.c_cpp_properties_file_path}' 失败: {e}。将从空配置开始追加。")
            return OrderedDict([("configurations", []), ("version", 4)])

    def _save_to_file(self, data_to_save: OrderedDict):
        print_action("正在保存配置到 c_cpp_properties.json")
        try:
            self.vscode_dir.mkdir(parents=True, exist_ok=True)
            with open(self.c_cpp_properties_file_path, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, indent=4, ensure_ascii=False)
            print_success(f"配置已成功保存到: {self.c_cpp_properties_file_path}")
        except Exception as e:
            print_error(f"保存文件 '{self.c_cpp_properties_file_path}' 失败: {e}")

    def _find_config_block_in_memory(self, platform_name_to_find: str) -> OrderedDict | None:
        for config_block in self.in_memory_configs.get("configurations", []):
            if config_block.get("name") == platform_name_to_find:
                return config_block
        return None

    def _edit_list_property(self, current_list: list, prop_name: str):
        temp_list = copy.deepcopy(current_list)
        while True:
            print_menu_header(f"编辑 '{prop_name}' 列表") # 更改了菜单头
            print_info(f"(当前 {len(temp_list)} 项)")
            if not temp_list: print_info("列表为空。")
            else:
                for i, item in enumerate(temp_list): print(f"  {i + 1}: {item}")
            
            print_option("a", "添加新项")
            if temp_list: print_option("r", "移除项")
            print_option("c", f"确认对 '{prop_name}' 的更改")
            print_option("d", f"放弃对 '{prop_name}' 的更改并返回")
            
            choice = input(f"{BLUE}选择操作 > {RESET}").strip().lower()
            if choice == 'a':
                new_val = input(f"{BLUE}输入要添加的值: {RESET}").strip()
                if new_val: temp_list.append(new_val); print_success("已临时添加。")
                else: print_warning("值不能为空。")
            elif choice == 'r' and temp_list:
                try:
                    idx = int(input(f"{BLUE}输入要移除项的编号: {RESET}").strip()) - 1
                    if 0 <= idx < len(temp_list): removed = temp_list.pop(idx); print_success(f"已临时移除: '{removed}'")
                    else: print_error("无效编号。")
                except ValueError: print_error("请输入数字。")
            elif choice == 'c':
                current_list[:] = temp_list
                print_success(f"'{prop_name}' 已更新。")
                break 
            elif choice == 'd':
                print_info(f"对 '{prop_name}' 的更改已放弃。")
                break
            else: print_error("无效选择。")

    def edit_platform_config_in_memory(self):
        print_menu_header("编辑内存中的平台配置")
        
        platform_names_in_memory = [block.get("name") for block in self.in_memory_configs.get("configurations", [])]
        if not platform_names_in_memory:
            print_error("内存中没有可编辑的配置。")
            input(f"\n{BLUE}按回车键继续...{RESET}")
            return

        print_info("请选择要编辑配置的平台 (基于内存中的默认设置):")
        for i, name in enumerate(platform_names_in_memory):
            marker = f"{GREEN}(当前系统平台){RESET}" if name == self.current_os_platform_name else ""
            print_option(str(i + 1), f"{name} {marker}")
        print_option("0", "返回主菜单")

        platform_choice = input(f"{BLUE}请输入平台编号 > {RESET}").strip()
        if platform_choice == '0': return
            
        try:
            selected_platform_idx = int(platform_choice) - 1
            if not (0 <= selected_platform_idx < len(platform_names_in_memory)):
                print_error("无效的平台编号。")
                input(f"\n{BLUE}按回车键继续...{RESET}")
                return
            
            target_platform_name = platform_names_in_memory[selected_platform_idx]
            block_to_edit_in_memory = self._find_config_block_in_memory(target_platform_name)
            if not block_to_edit_in_memory:
                print_error(f"内部错误：无法在内存中找到配置块 '{target_platform_name}'。")
                input(f"\n{BLUE}按回车键继续...{RESET}")
                return

            # --- 子菜单：编辑特定平台的属性 ---
            while True:
                print_menu_header(f"编辑 '{target_platform_name}' 的属性")
                
                # 将 USER_EDITABLE_KEYS_IN_BLOCK 中的键转换为列表，以便使用索引
                editable_keys_list = list(USER_EDITABLE_KEYS_IN_BLOCK.keys())
                
                for i, key_name in enumerate(editable_keys_list):
                    description = USER_EDITABLE_KEYS_IN_BLOCK[key_name]
                    current_val_preview = block_to_edit_in_memory.get(key_name)
                    if isinstance(current_val_preview, list):
                        preview_str = f"列表 (共 {len(current_val_preview)} 项)"
                    elif current_val_preview is None:
                        preview_str = "未设置"
                    else:
                        preview_str = str(current_val_preview)
                    print_option(str(i + 1), f"{description} (当前: {preview_str})")
                
                print_option("0", f"完成编辑 '{target_platform_name}' 并返回")
                
                attr_choice_str = input(f"{BLUE}请选择要编辑的属性编号 > {RESET}").strip()
                if attr_choice_str == '0':
                    break # 完成对此平台配置的编辑

                try:
                    selected_attr_idx = int(attr_choice_str) - 1
                    if not (0 <= selected_attr_idx < len(editable_keys_list)):
                        print_error("无效的属性编号。")
                        continue

                    key_to_edit = editable_keys_list[selected_attr_idx]
                    current_value = block_to_edit_in_memory.get(key_to_edit)

                    print_info(f"\n--- 正在编辑 '{target_platform_name}' 的 '{USER_EDITABLE_KEYS_IN_BLOCK[key_to_edit]}' ---")

                    if key_to_edit in ["includePath", "defines"]:
                        if current_value is None: current_value = [] # 初始化为空列表以防万一
                        self._edit_list_property(current_value, USER_EDITABLE_KEYS_IN_BLOCK[key_to_edit])
                        block_to_edit_in_memory[key_to_edit] = current_value 
                    elif key_to_edit == "mergeConfigurations":
                        current_bool_val_str = str(current_value).lower() if isinstance(current_value, bool) else "未设置"
                        new_val_str = input(f"{BLUE}输入新值 ('true'/'false') [当前: {current_bool_val_str}, 回车保留]: {RESET}").strip().lower()
                        if new_val_str == "true": block_to_edit_in_memory[key_to_edit] = True; print_success("已更新。")
                        elif new_val_str == "false": block_to_edit_in_memory[key_to_edit] = False; print_success("已更新。")
                        elif new_val_str == "" and current_value is not None: pass
                        else: print_warning("无效输入或未更改。")
                    else: # 字符串类型
                        current_str_val = str(current_value) if current_value is not None else "未设置"
                        new_val = input(f"{BLUE}输入新值 [当前: '{current_str_val}', 回车保留]: {RESET}").strip()
                        if new_val or (new_val == "" and current_value is not None):
                            if new_val != current_str_val:
                                block_to_edit_in_memory[key_to_edit] = new_val
                                print_success("已更新。")
                    input(f"{BLUE}按回车键继续...{RESET}")


                except ValueError:
                    print_error("请输入有效的数字编号。")
            
            print_success(f"内存中 '{target_platform_name}' 的配置已更新。")

        except ValueError:
            print_error("请输入有效的平台编号。")
        input(f"\n{BLUE}按回车键返回主菜单...{RESET}") # 确保在最外层 try-except 后也有返回提示

    def view_platform_config_in_memory(self):
        print_menu_header("查看内存中的平台配置")
        platform_names_in_memory = [block.get("name") for block in self.in_memory_configs.get("configurations", [])]
        if not platform_names_in_memory:
            print_error("内存中没有可查看的配置。")
            input(f"\n{BLUE}按回车键继续...{RESET}")
            return

        print_info("请选择要查看配置的平台:")
        for i, name in enumerate(platform_names_in_memory):
            marker = f"{GREEN}(当前系统平台){RESET}" if name == self.current_os_platform_name else ""
            print_option(str(i + 1), f"{name} {marker}")
        print_option("0", "返回主菜单")

        choice = input(f"{BLUE}请输入平台编号 > {RESET}").strip()
        if choice == '0': return
            
        try:
            selected_idx = int(choice) - 1
            if not (0 <= selected_idx < len(platform_names_in_memory)):
                print_error("无效的平台编号。")
                input(f"\n{BLUE}按回车键继续...{RESET}")
                return
            
            target_platform_name = platform_names_in_memory[selected_idx]
            config_block = self._find_config_block_in_memory(target_platform_name)
            
            if config_block:
                print_info(f"\n--- 内存中 '{target_platform_name}' 的配置详情 ---")
                for key, value in config_block.items():
                    if isinstance(value, list):
                        print_config_item(f"  {key}", "")
                        for item in value: print(f"    - {YELLOW}{item}{RESET}")
                    else:
                        print_config_item(f"  {key}", str(value))
            else:
                print_error(f"内部错误：无法找到 '{target_platform_name}' 的配置。")

        except ValueError:
            print_error("请输入有效的数字编号。")
        input(f"\n{BLUE}按回车键继续...{RESET}")


    def generate_and_update_current_platform_config_file(self):
        print_action(f"准备为当前平台 '{self.current_os_platform_name}' 生成/更新 c_cpp_properties.json")

        if self.current_os_platform_name == "Unknown":
            print_error("无法确定当前操作系统平台。请先在编辑菜单中确保至少有一个配置块的 'name' 与您的系统匹配 (Win32, Linux, macOS)。")
            input(f"\n{BLUE}按回车键返回主菜单...{RESET}")
            return

        current_platform_config_from_memory = self._find_config_block_in_memory(self.current_os_platform_name)
        if not current_platform_config_from_memory:
            print_error(f"错误：在内存的默认配置中未找到 '{self.current_os_platform_name}' 的配置。无法生成。")
            input(f"\n{BLUE}按回车键返回主菜单...{RESET}")
            return

        file_data = self._load_existing_file_or_default()
        file_configurations = file_data.get("configurations", [])

        found_block_in_file_idx = -1
        for i, block_in_file in enumerate(file_configurations):
            if isinstance(block_in_file, dict) and block_in_file.get("name") == self.current_os_platform_name:
                found_block_in_file_idx = i
                break
        
        if found_block_in_file_idx != -1:
            print_info(f"在文件中找到现有的 '{self.current_os_platform_name}' 配置块，将进行更新...")
            existing_block_ref = file_configurations[found_block_in_file_idx]
            # 核心更新逻辑：用内存中的当前平台配置覆盖文件中的对应块
            # 确保所有内存中的键都更新到文件中，如果文件中有内存中没有的键，则保留
            for key_from_mem, value_from_mem in current_platform_config_from_memory.items():
                existing_block_ref[key_from_mem] = copy.deepcopy(value_from_mem) 
            print_success("配置块已更新。")
        else:
            print_info(f"在文件中未找到 '{self.current_os_platform_name}' 配置块，将追加新的配置块...")
            file_configurations.append(copy.deepcopy(current_platform_config_from_memory))
            print_success("新配置块已追加。")
            
        file_data["configurations"] = file_configurations
        file_data["version"] = self.in_memory_configs.get("version", 4) # 使用内存中 version或默认4

        self._save_to_file(file_data)
        input(f"\n{BLUE}按回车键返回主菜单...{RESET}")


    def main_loop(self):
        while self.is_running:
            print_menu_header("VSCode C/C++ 配置管理器")
            print_config_item("项目目录", str(self.project_dir))
            print_config_item("目标文件", str(self.c_cpp_properties_file_path))
            print_info(f"当前平台配置名 (用于生成): {GREEN}{self.current_os_platform_name}{RESET}")
            print("------------------------------------")
            print_option("1", "查看内存中的平台配置")
            print_option("2", "编辑内存中的平台配置")
            print_option("3", f"生成/更新 '{self.current_os_platform_name}' 配置到文件")
            print_option("0", "退出")
            print("------------------------------------")

            choice = input(f"{BLUE}请输入您的选择 > {RESET}").strip()

            try:
                if choice == '1':
                    self.view_platform_config_in_memory()
                elif choice == '2':
                    self.edit_platform_config_in_memory()
                elif choice == '3':
                    self.generate_and_update_current_platform_config_file()
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
    
    app = InteractiveVSCodeCppPropertiesManager(project_dir)
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