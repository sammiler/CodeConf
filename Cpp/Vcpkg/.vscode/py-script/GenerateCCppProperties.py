import json
import os
import pathlib
import platform # 保留，但在这个生成器中不再直接决定当前OS的配置块
import sys
from collections import OrderedDict

class BaseGenerator:
    def __init__(self, dir_path):
        self.root_dir = pathlib.Path(dir_path)
        self.template_dir = self.root_dir / ".vscode" / "template"
        self.output_dir = self.root_dir / ".vscode"

    def load_json_template(self, filename):
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

    def load_output_json_safe(self, filename, default_structure=None):
        output_path = self.output_dir / filename
        
        final_default_structure = OrderedDict()
        if default_structure is None:
            default_structure = OrderedDict([("configurations", []), ("version", 4)])

        for k, v in default_structure.items():
            if isinstance(v, list):
                final_default_structure[k] = list(v) 
            elif isinstance(v, dict): 
                final_default_structure[k] = OrderedDict(v.items())
            else:
                final_default_structure[k] = v
        
        if not output_path.exists():
            return final_default_structure

        try:
            with open(output_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    return final_default_structure
                return json.loads(content, object_pairs_hook=OrderedDict)
        except json.JSONDecodeError:
            print(f"警告: 文件 {output_path} 包含无效的JSON。将使用默认结构。")
            return final_default_structure
        except Exception as e:
            print(f"警告: 无法读取 {output_path} ({e})。将使用默认结构。")
            return final_default_structure

    def save_json(self, filename, data):
        output_path = self.output_dir / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"已生成/更新: {output_path}")

class CCppPropertiesGenerator(BaseGenerator):
    def generate(self):
        vscode_conf_root = self.load_json_template("vscodeConf.json")
        all_template_os_configs = vscode_conf_root.get("c_cpp_properties", OrderedDict())

        default_c_cpp_props_structure = OrderedDict([("configurations", []), ("version", 4)])
        existing_c_cpp_data = self.load_output_json_safe("c_cpp_properties.json", default_c_cpp_props_structure)

        if not isinstance(existing_c_cpp_data.get("configurations"), list):
            print("警告: 'configurations' 在 c_cpp_properties.json 中不是列表或丢失。将重置。")
            existing_c_cpp_data["configurations"] = []
        existing_c_cpp_data.setdefault("version", 4)

        processed_template_config_names = set()

        preferred_keys_in_block_order = [
            "name", "includePath", "defines", "intelliSenseMode",
            "compilerPath", "cStandard", "cppStandard",
            "configurationProvider", "mergeConfigurations"
        ]
        
        script_defaults_for_entirely_missing_keys = {
            "includePath": [],
            "defines": ["_DEBUG"],
            "cStandard": "c11",
            "cppStandard": "c++17", 
            "configurationProvider": "ms-vscode.cmake-tools",
            "mergeConfigurations": False
            # 注意: "name", "intelliSenseMode", "compilerPath" 的默认值处理方式更复杂
        }
        
        # 为 intelliSenseMode 和 compilerPath 定义脚本级的固定回退值 (如果模板和用户文件都没有)
        script_fixed_defaults = {
            "intelliSenseMode": {
                "Windows": "windows-msvc-x64",
                "Linux": "linux-gcc-x64",
                "Mac": "macos-clang-x64",
                "Default": "Default" # 一个通用的回退值
            },
            "compilerPath": "" # 如果完全没有来源，则设为空字符串
        }


        new_configurations_list_for_output = [] 

        for existing_block_from_file in existing_c_cpp_data["configurations"]:
            if not isinstance(existing_block_from_file, dict):
                print(f"警告: 在 c_cpp_properties.json 的 configurations 中发现非字典条目，已跳过但将保留原样。")
                new_configurations_list_for_output.append(existing_block_from_file)
                continue

            current_block_being_processed = OrderedDict(existing_block_from_file.items())
            name_of_current_block_in_file = current_block_being_processed.get("name")

            matching_template_source_data = None
            template_os_key_if_match = None # 例如 "Windows", "Linux", "Mac" (vscodeConf.json中的顶层键)

            for t_os_key, t_os_data in all_template_os_configs.items():
                target_name_from_template = t_os_data.get("os", t_os_key)
                if target_name_from_template == name_of_current_block_in_file:
                    matching_template_source_data = t_os_data
                    template_os_key_if_match = t_os_key
                    processed_template_config_names.add(target_name_from_template)
                    break
            
            if matching_template_source_data:
                print(f"处理与模板匹配的现有配置: '{name_of_current_block_in_file}'")

                # 1. 标准化 'name' 字段
                current_block_being_processed["name"] = matching_template_source_data.get("os", template_os_key_if_match)
                
                # 2. 处理 'intelliSenseMode'
                if "mode" in matching_template_source_data:
                    current_block_being_processed["intelliSenseMode"] = matching_template_source_data["mode"]
                elif "intelliSenseMode" not in current_block_being_processed: # 用户文件没有，模板也没有
                    # 使用基于 template_os_key_if_match 的脚本固定默认值
                    current_block_being_processed["intelliSenseMode"] = script_fixed_defaults["intelliSenseMode"].get(
                        template_os_key_if_match, script_fixed_defaults["intelliSenseMode"]["Default"]
                    )
                    print(f"    为 '{name_of_current_block_in_file}' 添加了缺失的 'intelliSenseMode' 并设为脚本默认值: {current_block_being_processed['intelliSenseMode']}")
                # else: 用户文件中已有的 intelliSenseMode 被保留 (因为模板没有提供)

                # 3. 处理 'compilerPath' (用户优先)
                if "compilerPath" not in current_block_being_processed: # 只有当用户文件中完全没有此键时
                    if "compiler_path" in matching_template_source_data:
                        current_block_being_processed["compilerPath"] = matching_template_source_data["compiler_path"]
                    else: # 用户没有，模板也没有，则设为脚本默认（空字符串）
                        current_block_being_processed["compilerPath"] = script_fixed_defaults["compilerPath"]
                    print(f"    为 '{name_of_current_block_in_file}' 添加了缺失的 'compilerPath' 并设置为: {current_block_being_processed['compilerPath']}")
                # else: 用户文件中已有的 compilerPath 被完全保留

                # 4. 处理其他常用键 (如果用户文件中完全缺失，则补充脚本默认值)
                for key_to_check, default_val in script_defaults_for_entirely_missing_keys.items():
                    if key_to_check not in current_block_being_processed:
                        current_block_being_processed[key_to_check] = default_val
                        print(f"    为 '{name_of_current_block_in_file}' 添加了缺失的键 '{key_to_check}' 并设为默认值: {default_val}")
            else:
                print(f"保留用户自定义或模板中未定义的配置: '{name_of_current_block_in_file}'")
            
            # 整理键顺序
            final_ordered_block_for_output = OrderedDict()
            for p_key in preferred_keys_in_block_order:
                if p_key in current_block_being_processed:
                    final_ordered_block_for_output[p_key] = current_block_being_processed[p_key]
            for other_key, other_value in current_block_being_processed.items():
                if other_key not in final_ordered_block_for_output:
                    final_ordered_block_for_output[other_key] = other_value
            
            new_configurations_list_for_output.append(final_ordered_block_for_output)
        
        existing_c_cpp_data["configurations"] = new_configurations_list_for_output

        # --- 阶段 2: 添加 vscodeConf.json 中定义了但 c_cpp_properties.json 中不存在的配置块 ---
        for t_os_key, t_os_data in all_template_os_configs.items():
            target_name_from_template = t_os_data.get("os", t_os_key) 

            if target_name_from_template not in processed_template_config_names:
                print(f"从 vscodeConf.json 添加新配置: '{target_name_from_template}'")
                new_block_to_add = OrderedDict()
                new_block_to_add["name"] = target_name_from_template
                
                # intelliSenseMode: 从模板或脚本固定默认值
                if "mode" in t_os_data:
                    new_block_to_add["intelliSenseMode"] = t_os_data["mode"]
                else:
                    new_block_to_add["intelliSenseMode"] = script_fixed_defaults["intelliSenseMode"].get(
                        t_os_key, script_fixed_defaults["intelliSenseMode"]["Default"]
                    )
                
                # compilerPath: 从模板或脚本固定默认值 (空字符串)
                new_block_to_add["compilerPath"] = t_os_data.get("compiler_path", script_fixed_defaults["compilerPath"])
                
                # 其他键使用脚本定义的默认值
                for key_to_add, default_val in script_defaults_for_entirely_missing_keys.items():
                    new_block_to_add[key_to_add] = default_val
                
                # 整理键顺序
                final_ordered_new_block = OrderedDict()
                for p_key in preferred_keys_in_block_order:
                    if p_key in new_block_to_add: 
                        final_ordered_new_block[p_key] = new_block_to_add[p_key]
                for other_key, other_value in new_block_to_add.items():
                    if other_key not in final_ordered_new_block:
                        final_ordered_new_block[other_key] = other_value
                
                existing_c_cpp_data["configurations"].append(final_ordered_new_block)

        self.save_json("c_cpp_properties.json", existing_c_cpp_data)

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
        CCppPropertiesGenerator(project_dir)
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