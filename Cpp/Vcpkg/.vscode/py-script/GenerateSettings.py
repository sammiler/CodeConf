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
        # "-IC:/vcpkg/installed/x64-win-llvm/include" # 示例，让用户添加
    ]),
    ("editor.snippetSuggestions", "inline"),
    ("editor.tabCompletion", "on"),
    ("editor.formatOnSave", True),
    # clangd.arguments - 允许用户动态添加
    ("clangd.arguments", [
        "--compile-commands-dir=${workspaceFolder}/build",
        "--clang-tidy",
        "--all-scopes-completion",
        "--completion-style=detailed",
        "--header-insertion=never"
    ]),
    ("qt-qml.qmlls.additionalImportPaths", ["C:/Qt/6.10.0/msvc2022_64/qml"]), 
    ("editor.fontFamily", "Maple Mono NF, Jetbrains Mono, Menlo, Consolas, monospace"),
    ("editor.fontLigatures", "'calt', 'cv01', 'ss01', 'zero'"),
    ("editor.fontSize", 13),
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


        
    def main_loop(self):
        self._save_settings_to_file()

def main_interactive():
    project_dir_env = os.environ.get("PROJECT_DIR")
    project_dir = None
    if not project_dir_env:
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