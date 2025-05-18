import json
import os
import pathlib
import platform
import sys
from collections import OrderedDict # 确保导入

class BaseGenerator:
    def __init__(self, dir_path): # 确保 dir_path 是 Path 对象
        self.root_dir = pathlib.Path(dir_path)
        self.template_dir = self.root_dir / ".vscode" / "template"
        self.output_dir = self.root_dir / ".vscode"
        self.system = platform.system()
        self.os_map = {"Windows": "Windows", "Linux": "Linux", "Darwin": "Mac"}
        self.current_os_key = self.os_map.get(self.system, "Windows")

    def load_json_template(self, filename): # 从模板目录加载 vscodeConf.json
        file_path = self.template_dir / filename
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f, object_pairs_hook=OrderedDict)
        except FileNotFoundError:
            print(f"错误: 模板文件 {file_path} 未找到。")
            sys.exit(1)
        except json.JSONDecodeError:
            print(f"错误: 模板文件 {file_path} 包含无效的JSON。")
            sys.exit(1)

    def load_output_json_safe(self, filename, default_structure_factory=OrderedDict): # 从输出目录加载 settings.json
        output_path = self.output_dir / filename
        if not output_path.exists():
            return default_structure_factory()
        try:
            with open(output_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    return default_structure_factory()
                return json.loads(content, object_pairs_hook=OrderedDict)
        except json.JSONDecodeError:
            print(f"警告: 文件 {output_path} 包含无效的JSON。将使用空的默认结构。")
            return default_structure_factory()
        except Exception as e:
            print(f"警告: 无法读取 {output_path} ({e})。将使用空的默认结构。")
            return default_structure_factory()

    def save_json(self, filename, data):
        output_path = self.output_dir / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"已生成/更新: {output_path}")

class SettingsGenerator(BaseGenerator):

    def _recursive_merge_settings(self, existing_data, script_template_data):
        """
        递归地将 script_template_data 中的键值对补充到 existing_data 中。
        - 如果 script_template_data 中的键在 existing_data 中不存在，则添加。
        - 如果键已存在：
            - 若两者都是字典, 则递归合并。
            - 否则 (包括列表或简单类型), 保留 existing_data 中的值 (用户优先)。
        返回合并后的 existing_data (原地修改)。
        """
        if not isinstance(existing_data, dict) or not isinstance(script_template_data, dict):
            return existing_data

        for key, template_value in script_template_data.items():
            if key not in existing_data:
                # 键在用户文件中不存在，直接从脚本模板添加
                existing_data[key] = template_value
            else:
                # 键在用户文件中已存在
                existing_value = existing_data[key]
                if isinstance(existing_value, dict) and isinstance(template_value, dict):
                    # 如果两边都是字典，递归合并
                    self._recursive_merge_settings(existing_value, template_value)
                # else: 用户文件中已有的值 (列表、简单类型等) 被保留
        return existing_data

    def generate(self):
        # 1. 从 vscodeConf.json 加载配置源 (仅用于获取少数动态值)
        vscode_conf_source = self.load_json_template("vscodeConf.json")
        # settings_from_vscode_conf 指向 vscodeConf.json 中的 "settings" 部分
        settings_from_vscode_conf = vscode_conf_source.get("settings", OrderedDict())
        # os_specific_dynamic_values 指向 vscodeConf.json["settings"]["os"][self.current_os_key]
        os_specific_dynamic_values = settings_from_vscode_conf.get("os", OrderedDict()).get(self.current_os_key, OrderedDict())

        # 2. 构建“脚本模板”(script_template_for_settings)
        #    这就是您原始脚本中的 settings_json 结构，但动态部分已填充。
        #    使用 OrderedDict 来尽量保持定义的顺序。
        script_template_for_settings = OrderedDict([
            ("files.associations", OrderedDict([
                ("*.qrc", "xml"),
                ("**/APP/ts/**/*.ts", "xml"),
                ("*.ui", "xml"),
                ("*.clang-tidy","yaml")
            ])),
            # 只有 Windows 才需要这个特定的键，所以我们有条件地添加它
            # 或者，如果希望非Windows时该键不存在，则不在模板中定义它，
            # 或者vscodeConf.json的OS特定部分不包含它。
            # 为了与您原始脚本一致，这里仍然定义它，但值依赖于OS。
            ("terminal.integrated.defaultProfile.windows", os_specific_dynamic_values.get("bash", "Git Bash" if self.current_os_key == "Windows" else None)), # 只有Windows时才有意义设为Git Bash，其他OS可能设为None或不设
            ("C_Cpp.intelliSenseEngine", "disabled"),
            ("clangd.arguments", [
                "--compile-commands-dir=${workspaceFolder}/build",
                "--clang-tidy",
                "--all-scopes-completion",
                "--completion-style=detailed",
                "--header-insertion=never"
            ]),
            ("clangd.fallbackFlags", [
                "-I${workspaceFolder}/ext/core/include",
                # 如果 os_specific_dynamic_values 中没有 'clangdInclude'，则设为空字符串或一个明确的占位符
                f"-I{os_specific_dynamic_values.get('clangdInclude', '')}"
            ]),
            ("C_Cpp.default.compileCommands", "${workspaceFolder}/build/compile_commands.json"),
            ("editor.snippetSuggestions", "inline"),
            ("editor.tabCompletion", "on"),
            ("openInExternalApp.openMapper", [
                OrderedDict([ # 确保列表内的字典也是 OrderedDict
                    ("extensionName", "ui"),
                    ("apps", [
                        OrderedDict([ # 确保更深层嵌套的字典也是 OrderedDict
                            ("title", "QtUI"),
                            ("openCommand", os_specific_dynamic_values.get("qt_exe", "")) # 如果没有则为空字符串
                        ])
                    ])
                ])
            ])
        ])

        # 对于特定于OS的键，如 terminal.integrated.defaultProfile.windows，
        # 如果当前不是Windows，且其值为None，则从模板中移除，以避免写入不必要的键。
        if self.current_os_key != "Windows" and \
           script_template_for_settings.get("terminal.integrated.defaultProfile.windows") is None:
            if "terminal.integrated.defaultProfile.windows" in script_template_for_settings:
                del script_template_for_settings["terminal.integrated.defaultProfile.windows"]
        # 也可以对其他OS特定键做类似处理，或者更好地在vscodeConf.json中就不为不相关的OS定义这些键。

        # 3. 加载用户现有的 settings.json (如果存在)
        existing_settings_data = self.load_output_json_safe("settings.json", OrderedDict)

        # 4. 执行递归合并/补充
        #    将 script_template_for_settings (脚本希望确保存在的结构)
        #    补充到 existing_settings_data (用户现有的 settings.json 内容) 中。
        #    _recursive_merge_settings 会修改 existing_settings_data。
        final_settings = self._recursive_merge_settings(existing_settings_data, script_template_for_settings)
        
        # 5. 保存结果
        self.save_json("settings.json", final_settings)

def main():
    project_dir_env = os.environ.get("PROJECT_DIR")
    if not project_dir_env:
        print("错误：未设置 PROJECT_DIR 环境变量。请设置该变量指向项目根目录。")
        sys.exit(1)
    
    project_dir = pathlib.Path(project_dir_env)
    if not project_dir.is_dir():
        print(f"错误：PROJECT_DIR '{project_dir_env}' 不是一个有效的目录。")
        sys.exit(1)

    template_path_for_check = project_dir / ".vscode" / "template"
    if not template_path_for_check.exists():
        template_path_for_check.mkdir(parents=True, exist_ok=True)
        print(f"已创建模板目录: {template_path_for_check}")
        print(f"请确保 vscodeConf.json 文件存在于该目录中。")
    
    generators = [
        SettingsGenerator(project_dir)
    ]
    for generator in generators:
        generator.generate()

if __name__ == "__main__":
    try:
        main()
    except SystemExit: 
        raise
    except Exception as e:
        print(f"脚本执行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)