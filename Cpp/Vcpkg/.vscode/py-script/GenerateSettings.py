import json
import os
import pathlib
import platform
import sys
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

# --- 内置的完整默认 settings.json 结构 ---
DEFAULT_SETTINGS_JSON = OrderedDict([
    ("files.associations", OrderedDict([
        ("*.qrc", "xml"),
        ("*.ui", "xml"), # 保持 xml，除非您想改为 xaml
        ("**/APP/ts/**/*.ts", "xml"), # 原始是 xml, 通常 ts 是 typescript
        ("*.clang-tidy", "yaml"),
        ("*.clang-uml", "yaml"),
        ("*.in", "plaintext") # txt 可能比 plaintext 更常见
    ])),
    ("C_Cpp.intelliSenseEngine", "disabled"),
    # clangd.fallbackFlags - 允许用户动态添加
    ("clangd.fallbackFlags", [
        "-I${workspaceFolder}/ext/core/include",
        # "-IC:/vcpkg/installed/x64-win-llvm/include" # 示例，让用户添加
    ]),
    ("editor.snippetSuggestions", "inline"),
    ("editor.tabCompletion", "on"),
    # clangd.arguments - 允许用户动态添加
    ("clangd.arguments", [
        "--compile-commands-dir=${workspaceFolder}/build",
        "--clang-tidy",
        "--all-scopes-completion",
        "--completion-style=detailed",
        "--header-insertion=never"
    ]),
    # openInExternalApp.openMapper - 允许用户动态添加/修改
    ("openInExternalApp.openMapper", [
        OrderedDict([
            ("extensionName", "ui"),
            ("apps", [
                OrderedDict([
                    ("title", "QtDesigner"), # 之前是 QtUI
                    ("openCommand", "C:/Qt/Qt5.9.5/5.9.5/msvc2017_64/bin/designer.exe") # 示例路径
                ])
            ])
        ])
    ]),
    ("syncfiles.view.scriptClickAction", "executeDefault"),
    ("terminal.integrated.defaultProfile.windows", "Git Bash"), #特定于Windows
    ("C_Cpp.default.compileCommands", "${workspaceFolder}/build/compile_commands.json")
])

# 定义哪些顶级键是用户可以直接编辑其值的 (非复杂结构)
SIMPLE_EDITABLE_TOP_LEVEL_KEYS = OrderedDict([
    ("C_Cpp.intelliSenseEngine", "C/C++ IntelliSense 引擎"),
    ("editor.snippetSuggestions", "编辑器代码片段建议方式"),
    ("editor.tabCompletion", "编辑器Tab自动完成"),
    ("syncfiles.view.scriptClickAction", "Sync VSIX 脚本点击行为"),
    ("terminal.integrated.defaultProfile.windows", "Windows 默认终端配置文件"),
    ("C_Cpp.default.compileCommands", "C/C++ 默认编译命令文件路径")
])


class InteractiveVSCodeSettingsEditor:
    def __init__(self, project_dir_path: pathlib.Path):
        self.project_dir = project_dir_path
        self.vscode_dir = self.project_dir / ".vscode"
        self.settings_file_path = self.vscode_dir / "settings.json"
        
        self.settings_data: OrderedDict = self._load_or_initialize_settings()
        
        self.is_running = True
        self.current_os_platform = platform.system() # "Windows", "Linux", "Darwin"

    def _load_or_initialize_settings(self) -> OrderedDict:
        if not self.settings_file_path.exists():
            print_info(f"文件 '{self.settings_file_path}' 不存在，将使用内置的默认配置。")
            return copy.deepcopy(DEFAULT_SETTINGS_JSON)
        try:
            with open(self.settings_file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    print_warning(f"文件 '{self.settings_file_path}' 为空，将使用内置的默认配置。")
                    return copy.deepcopy(DEFAULT_SETTINGS_JSON)
                
                # 加载时保留顺序
                loaded_data = json.loads(content, object_pairs_hook=OrderedDict)
                
                # 合并：以加载的数据为基础，用默认值补充缺失的顶级键
                # 这确保了即使 settings.json 中缺少一些默认键，它们也会被添加回来
                # 但如果用户文件中已有某个键，则保留用户的值。
                # 对于嵌套结构如 files.associations，如果用户文件中有此键，我们会保留用户的整个对象
                # 如果用户文件中没有，则从默认添加。
                
                # 创建一个结果字典，先用加载的，再用默认的补充
                # 确保 DEFAULT_SETTINGS_JSON 中的所有顶级键都存在于最终的 settings_data 中
                # 但如果 loaded_data 中有某个键，则优先使用 loaded_data 的值
                
                # 为了更好的合并，我们以默认结构为蓝本，用加载的数据去覆盖
                merged_data = copy.deepcopy(DEFAULT_SETTINGS_JSON)
                for key, value in loaded_data.items():
                    if key in merged_data and isinstance(merged_data[key], OrderedDict) and isinstance(value, OrderedDict):
                        # 对于字典类型，进行浅层合并（可以用更深的合并逻辑如果需要）
                        # 这里简单地用加载的值覆盖默认值中的同名键
                        merged_data[key].update(value)
                    elif key in merged_data and isinstance(merged_data[key], list) and isinstance(value, list):
                        # 对于列表，如果用户文件有，我们倾向于使用用户的列表，而不是合并
                        merged_data[key] = value
                    else:
                        # 其他类型或顶级键在默认中不存在，直接使用加载的值
                        merged_data[key] = value
                
                # 确保默认中存在但加载中不存在的顶级键被添加
                for key, default_value in DEFAULT_SETTINGS_JSON.items():
                    if key not in merged_data:
                        merged_data[key] = copy.deepcopy(default_value)


                print_success(f"已从 '{self.settings_file_path}' 加载并合并配置。")
                return merged_data

        except json.JSONDecodeError:
            print_error(f"文件 '{self.settings_file_path}' 包含无效JSON。将使用内置的默认配置。")
            return copy.deepcopy(DEFAULT_SETTINGS_JSON)
        except Exception as e:
            print_error(f"加载 '{self.settings_file_path}' 失败: {e}。将使用内置的默认配置。")
            return copy.deepcopy(DEFAULT_SETTINGS_JSON)

    def _save_settings_to_file(self):
        print_action("正在保存配置到 settings.json")
        try:
            self.vscode_dir.mkdir(parents=True, exist_ok=True)
            with open(self.settings_file_path, 'w', encoding='utf-8') as f:
                json.dump(self.settings_data, f, indent=4, ensure_ascii=False)
            print_success(f"配置已成功保存到: {self.settings_file_path}")
        except Exception as e:
            print_error(f"保存文件 '{self.settings_file_path}' 失败: {e}")
        input(f"\n{BLUE}按回车键返回主菜单...{RESET}")

    def _edit_simple_value(self, key_to_edit: str, description: str):
        current_value = self.settings_data.get(key_to_edit, "未设置")
        if self.current_os_platform != "Windows" and key_to_edit == "terminal.integrated.defaultProfile.windows":
            print_info(f"'{description}' 通常只在 Windows 上配置。当前系统为 {self.current_os_platform}。")
        
        new_value = input(f"{BLUE}编辑 '{description}' (当前: '{current_value}') [回车保留]: {RESET}").strip()
        if new_value or (new_value == "" and current_value != "未设置"): # 允许设置为空字符串
            if new_value != str(current_value):
                self.settings_data[key_to_edit] = new_value
                print_success("已更新。")
        input(f"\n{BLUE}按回车键继续...{RESET}")

    def _edit_string_list(self, key_to_edit: str, description: str, add_prefix: str = ""):
        """编辑字符串列表，如 clangd.fallbackFlags 或 clangd.arguments"""
        if key_to_edit not in self.settings_data or not isinstance(self.settings_data[key_to_edit], list):
            self.settings_data[key_to_edit] = [] # 如果不存在或类型不对，则初始化为空列表
        
        string_list_ref = self.settings_data[key_to_edit]
        
        while True:
            print_menu_header(f"编辑 '{description}'")
            if not string_list_ref: print_info("列表为空。")
            else:
                for i, item in enumerate(string_list_ref): print(f"  {i + 1}: {item}")
            
            print_option("a", "添加新项")
            if string_list_ref: print_option("r", "移除项")
            print_option("b", f"完成编辑 '{description}'")
            
            choice = input(f"{BLUE}选择操作 > {RESET}").strip().lower()
            if choice == 'a':
                new_val_base = input(f"{BLUE}输入要添加的值 (例如路径或参数): {RESET}").strip()
                if new_val_base:
                    final_val = f"{add_prefix}{new_val_base}" if add_prefix and not new_val_base.startswith(add_prefix.split('${')[0]) else new_val_base
                    string_list_ref.append(final_val)
                    print_success(f"已添加: '{final_val}'")
                else: print_warning("值不能为空。")
            elif choice == 'r' and string_list_ref:
                try:
                    idx = int(input(f"{BLUE}输入要移除项的编号: {RESET}").strip()) - 1
                    if 0 <= idx < len(string_list_ref): removed = string_list_ref.pop(idx); print_success(f"已移除: '{removed}'")
                    else: print_error("无效编号。")
                except ValueError: print_error("请输入数字。")
            elif choice == 'b': break
            else: print_error("无效选择。")

    def _edit_files_associations(self):
        if "files.associations" not in self.settings_data or not isinstance(self.settings_data["files.associations"], OrderedDict):
            self.settings_data["files.associations"] = OrderedDict()
        
        associations_ref = self.settings_data["files.associations"]
        
        while True:
            print_menu_header("编辑 'files.associations'")
            if not associations_ref: print_info("当前没有文件关联。")
            else:
                idx = 1
                # 将字典项转换为列表以便编号
                assoc_items = list(associations_ref.items())
                for pattern, lang_id in assoc_items:
                    print(f"  {idx}: '{pattern}' -> '{lang_id}'")
                    idx +=1
            
            print_option("a", "添加新关联")
            if associations_ref:
                print_option("m", "修改现有关联的语言ID")
                print_option("r", "移除关联")
            print_option("b", "完成编辑 'files.associations'")

            choice = input(f"{BLUE}选择操作 > {RESET}").strip().lower()
            if choice == 'a':
                pattern = input(f"{BLUE}输入文件模式 (e.g., *.myext): {RESET}").strip()
                lang_id = input(f"{BLUE}输入语言标识符 (e.g., python): {RESET}").strip()
                if pattern and lang_id:
                    associations_ref[pattern] = lang_id
                    print_success("已添加关联。")
                else: print_warning("模式和语言标识符均不能为空。")
            elif choice == 'm' and associations_ref:
                try:
                    num = int(input(f"{BLUE}输入要修改关联的编号: {RESET}").strip())
                    if 1 <= num <= len(assoc_items):
                        pattern_to_edit, old_lang_id = assoc_items[num-1]
                        new_lang_id = input(f"{BLUE}为模式 '{pattern_to_edit}' 输入新的语言标识符 (当前: '{old_lang_id}', 回车保留): {RESET}").strip()
                        if new_lang_id : associations_ref[pattern_to_edit] = new_lang_id; print_success("已更新。")
                    else: print_error("无效编号。")
                except ValueError: print_error("请输入数字。")
            elif choice == 'r' and associations_ref:
                try:
                    num = int(input(f"{BLUE}输入要移除关联的编号: {RESET}").strip())
                    if 1 <= num <= len(assoc_items):
                        pattern_to_remove, _ = assoc_items[num-1]
                        del associations_ref[pattern_to_remove]
                        print_success(f"已移除关联: '{pattern_to_remove}'")
                    else: print_error("无效编号。")
                except ValueError: print_error("请输入数字。")
            elif choice == 'b': break
            else: print_error("无效选择。")
            
    def _edit_open_in_external_app_mapper(self):
        if "openInExternalApp.openMapper" not in self.settings_data or not isinstance(self.settings_data["openInExternalApp.openMapper"], list):
            self.settings_data["openInExternalApp.openMapper"] = []
            
        mapper_list_ref = self.settings_data["openInExternalApp.openMapper"]

        while True:
            print_menu_header("编辑 'openInExternalApp.openMapper'")
            if not mapper_list_ref: print_info("当前没有外部应用映射。")
            else:
                for i, mapper_entry in enumerate(mapper_list_ref):
                    ext = mapper_entry.get("extensionName", "N/A")
                    app_title = "N/A"
                    app_cmd = "N/A"
                    if isinstance(mapper_entry.get("apps"), list) and len(mapper_entry["apps"]) > 0:
                        app_info = mapper_entry["apps"][0] # 取第一个app
                        app_title = app_info.get("title", "N/A")
                        app_cmd = app_info.get("openCommand", "N/A")
                    print(f"  {i + 1}: 扩展名='{ext}', 应用='{app_title}', 命令='{app_cmd}'")
            
            print_option("a", "添加新映射")
            if mapper_list_ref:
                print_option("m", "修改现有映射")
                print_option("r", "移除映射")
            print_option("b", "完成编辑 'openInExternalApp.openMapper'")

            choice = input(f"{BLUE}选择操作 > {RESET}").strip().lower()
            if choice == 'a':
                ext_name = input(f"{BLUE}输入扩展名 (e.g., 'ui'): {RESET}").strip()
                app_title = input(f"{BLUE}输入应用标题 (e.g., 'QtDesigner'): {RESET}").strip()
                app_cmd = input(f"{BLUE}输入应用打开命令/路径: {RESET}").strip()
                if ext_name and app_title and app_cmd:
                    new_mapper = OrderedDict([
                        ("extensionName", ext_name),
                        ("apps", [OrderedDict([("title", app_title), ("openCommand", app_cmd)])])
                    ])
                    mapper_list_ref.append(new_mapper)
                    print_success("已添加映射。")
                else: print_warning("所有字段均不能为空。")
            elif choice == 'm' and mapper_list_ref:
                try:
                    idx = int(input(f"{BLUE}输入要修改映射的编号: {RESET}").strip()) - 1
                    if 0 <= idx < len(mapper_list_ref):
                        entry_to_edit = mapper_list_ref[idx]
                        # 简单起见，只修改第一个app的信息
                        current_title = entry_to_edit.get("apps", [{}])[0].get("title", "")
                        current_cmd = entry_to_edit.get("apps", [{}])[0].get("openCommand", "")
                        
                        new_title = input(f"{BLUE}新应用标题 (当前: '{current_title}', 回车保留): {RESET}").strip()
                        new_cmd = input(f"{BLUE}新打开命令 (当前: '{current_cmd}', 回车保留): {RESET}").strip()
                        
                        if not isinstance(entry_to_edit.get("apps"), list) or len(entry_to_edit["apps"]) == 0:
                            entry_to_edit["apps"] = [OrderedDict()] #确保apps[0]存在
                        
                        if new_title: entry_to_edit["apps"][0]["title"] = new_title
                        if new_cmd: entry_to_edit["apps"][0]["openCommand"] = new_cmd
                        print_success("映射已更新。")
                    else: print_error("无效编号。")
                except (ValueError, IndexError): print_error("无效编号或映射结构错误。")
            elif choice == 'r' and mapper_list_ref:
                try:
                    idx = int(input(f"{BLUE}输入要移除映射的编号: {RESET}").strip()) - 1
                    if 0 <= idx < len(mapper_list_ref):
                        removed = mapper_list_ref.pop(idx)
                        print_success(f"已移除映射 (扩展名: {removed.get('extensionName')})。")
                    else: print_error("无效编号。")
                except ValueError: print_error("请输入数字。")
            elif choice == 'b': break
            else: print_error("无效选择。")

    def manage_settings_interactive(self):
        while True:
            print_menu_header("编辑 settings.json 内容")
            # 列出可编辑的类别/顶级键
            menu_options = OrderedDict()
            idx = 1
            
            # 简单值编辑
            for key, desc in SIMPLE_EDITABLE_TOP_LEVEL_KEYS.items():
                current_val = self.settings_data.get(key, "未设置")
                menu_options[str(idx)] = {"key": key, "desc": desc, "action": "_edit_simple_value", "is_simple": True, "current_val": current_val}
                print_option(str(idx), f"{desc} (当前: {current_val})")
                idx +=1
            
            # files.associations
            assoc_count = len(self.settings_data.get("files.associations", {}))
            menu_options[str(idx)] = {"key": "files.associations", "desc": "文件关联", "action": "_edit_files_associations"}
            print_option(str(idx), f"文件关联 (files.associations) ({assoc_count} 项)")
            idx +=1

            # clangd.fallbackFlags
            fallback_count = len(self.settings_data.get("clangd.fallbackFlags", []))
            menu_options[str(idx)] = {"key": "clangd.fallbackFlags", "desc": "Clangd Fallback Flags", "action": "_edit_string_list", "add_prefix": "-I"}
            print_option(str(idx), f"Clangd Fallback Flags ({fallback_count} 项)")
            idx +=1
            
            # clangd.arguments
            args_count = len(self.settings_data.get("clangd.arguments", []))
            menu_options[str(idx)] = {"key": "clangd.arguments", "desc": "Clangd Arguments", "action": "_edit_string_list"}
            print_option(str(idx), f"Clangd Arguments ({args_count} 项)")
            idx +=1

            # openInExternalApp.openMapper
            mapper_count = len(self.settings_data.get("openInExternalApp.openMapper", []))
            menu_options[str(idx)] = {"key": "openInExternalApp.openMapper", "desc": "外部应用映射", "action": "_edit_open_in_external_app_mapper"}
            print_option(str(idx), f"外部应用映射 (openInExternalApp.openMapper) ({mapper_count} 项)")
            idx +=1

            print_option("0", "完成编辑并返回主菜单")
            
            choice = input(f"{BLUE}请选择要编辑的配置项编号 > {RESET}").strip()
            if choice == '0': break

            selected_option = menu_options.get(choice)
            if selected_option:
                action_method_name = selected_option["action"]
                method_to_call = getattr(self, action_method_name)
                
                if selected_option.get("is_simple", False):
                    method_to_call(selected_option["key"], selected_option["desc"])
                elif "add_prefix" in selected_option: # clangd.fallbackFlags
                     method_to_call(selected_option["key"], selected_option["desc"], selected_option["add_prefix"])
                else: # files.associations, clangd.arguments, openInExternalApp.openMapper
                    method_to_call() if action_method_name not in ["_edit_string_list"] else method_to_call(selected_option["key"], selected_option["desc"])
            else:
                print_error("无效选项。")
        
    def main_loop(self):
        while self.is_running:
            print_menu_header("VSCode settings.json 编辑器")
            print_config_item("项目目录", str(self.project_dir))
            print_config_item("配置文件路径", str(self.settings_file_path))
            print("------------------------------------")
            print_option("1", "查看/编辑 settings.json 配置")
            print_option("2", "保存配置到文件")
            print_option("0", "退出 (未保存的更改将丢失)")
            print("------------------------------------")

            choice = input(f"{BLUE}请输入您的选择 > {RESET}").strip()

            try:
                if choice == '1':
                    self.manage_settings_interactive()
                elif choice == '2':
                    self._save_settings_to_file()
                elif choice == '0':
                    print_info("感谢使用，程序已退出。")
                    self.is_running = False
                else:
                    print_error("无效的选择，请重新输入。")
            except KeyboardInterrupt:
                print_warning("\n操作被用户中断。返回主菜单。")
            except Exception as e:
                print_error(f"发生意外错误: {e}")
                # import traceback
                # print_error(f"详细信息: {traceback.format_exc()}")
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
    
    app = InteractiveVSCodeSettingsEditor(project_dir)
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