import json
import os
import pathlib
import platform
import sys
from collections import OrderedDict # 确保导入

class BaseGenerator:
    def __init__(self, dir_path): # dir_path 应该是 pathlib.Path 对象
        self.root_dir = pathlib.Path(dir_path) 
        self.template_dir = self.root_dir / ".vscode" / "template"
        self.output_dir = self.root_dir / ".vscode"
        self.system = platform.system()
        self.os_map = {"Windows": "Windows", "Linux": "Linux", "Darwin": "Mac"}
        self.current_os_key = self.os_map.get(self.system, "Windows")

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

    def load_output_json_safe(self, filename, default_structure_factory=OrderedDict):
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
            print(f"警告: 文件 {output_path} '{filename}' 包含无效的JSON。将使用空的默认结构。")
            return default_structure_factory()
        except Exception as e:
            print(f"警告: 无法读取文件 '{filename}' ({e})。将使用空的默认结构。")
            return default_structure_factory()

    def save_json(self, filename, data):
        output_path = self.output_dir / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"已生成/更新: {output_path}")

class LaunchGenerator(BaseGenerator):
    def find_executables(self):
        # 确保 build 和 build/bin 目录存在，如果不存在则返回空列表，避免后续错误
        build_dir = self.root_dir / "build"
        bin_dir = build_dir / "bin"
        if not bin_dir.is_dir():
            print(f"警告: 目录 {bin_dir} 不存在。无法查找可执行文件。")
            return []
        
        exes = []
        # 根据操作系统确定可执行文件扩展名
        # 对于Linux/Mac，我们通常查找没有特定扩展名但具有执行权限的文件
        # 但 glob 模式对于权限不敏感，所以我们先按有无扩展名来粗略查找
        
        # 首先尝试查找没有扩展名的文件 (主要针对 Linux/Mac)
        if self.system != "Windows":
            for file in bin_dir.rglob("*"): # 查找所有文件
                # 排除目录，并且确保是可执行的 (os.access 更可靠，但需要 import os)
                # pathlib 的 is_file() 检查是否是文件
                # 对于是否可执行，一个简单的代理是确保它没有常见的非可执行扩展名
                # 或者，如果知道编译器的输出，可以更精确。
                # 这里简化：假设没有扩展名的文件是目标，或者需要更复杂的检查
                if file.is_file() and not file.suffix: # 无后缀且是文件
                     # 进一步检查是否可执行 (可选，但推荐)
                    if os.access(str(file), os.X_OK):
                        exes.append({"name": file.name, "path": str(file).replace("\\", "/")})

        # 然后查找带 .exe 后缀的文件 (主要针对 Windows，但也可能在交叉编译的Linux/Mac上出现)
        for file in bin_dir.rglob("*.exe"):
            if file.is_file():
                # 避免重复添加（如果无后缀版本已被添加）
                path_str = str(file).replace("\\", "/")
                if not any(e["path"] == path_str for e in exes):
                    exes.append({"name": file.stem, "path": path_str}) # 使用 file.stem 获取不带后缀的文件名
        
        # 如果在Windows上，只保留 .exe 文件
        if self.system == "Windows":
            exes = [e for e in exes if e["path"].endswith(".exe")]

        # 去重，以防万一（基于路径）
        unique_exes = []
        seen_paths = set()
        for exe in exes:
            if exe["path"] not in seen_paths:
                unique_exes.append(exe)
                seen_paths.add(exe["path"])
        
        if not unique_exes:
            print(f"提示: 在 {bin_dir} 未找到可识别的可执行文件。")
        return unique_exes

    def _get_base_launch_config_template(self, os_specific_conf_from_vscode):
        """
        构建一个基础的启动配置模板，其中动态部分会从 os_specific_conf_from_vscode 获取。
        这个模板定义了脚本希望确保存在的标准键。
        """
        # vscodeConf.json 中的 "launch"."<OS>" 部分
        # 例如: os_specific_conf_from_vscode = {"debug_type": "cppvsdbg", "qt5_natvis": "path/to/qt5.natvis"}
        
        template = OrderedDict([
            ("name", ""), # 将由 "Debug " + exe_name 填充
            ("program", ""), # 将由 exe_path 填充
            ("type", os_specific_conf_from_vscode.get("debug_type", "cppvsdbg" if self.system == "Windows" else "cppdbg")),
            ("request", "launch"),
            ("stopAtEntry", True),
            ("cwd", "${workspaceFolder}/build/bin"), # 或者 ${fileDirname} 如果程序期望从其自身目录运行
            ("environment", [
                # OrderedDict([("name", "PATH"), ("value", "${env:PATH}")]) # 简化，VS Code通常会自动处理PATH
            ]), # 通常为空或根据需要添加
            ("console", "internalConsole"), # "internalConsole", "integratedTerminal", "externalTerminal"
            # ("MIMode", "gdb" if self.system != "Windows" else None), # 示例: Linux/Mac 可能需要MIMode
            # ("miDebuggerPath", "/usr/bin/gdb" if self.system != "Windows" else None), # 示例
            ("logging", OrderedDict([
                ("moduleLoad", True), # VSCode C++ 扩展可能不再直接使用这个，但保留无妨
                ("exceptions", True)  # 同上
            ])),
            ("visualizerFile", os_specific_conf_from_vscode.get("qt5_natvis", "")),
            ("sourceFileMap", OrderedDict()) # 通常为空，除非有特定映射需求
        ])

        # 移除值为 None 的键 (例如 MIMode 在 Windows 上)
        # return OrderedDict((k, v) for k, v in template.items() if v is not None)
        # 或者，让它们保留，VSCode调试器会忽略不适用的键
        return template

    def generate(self):
        # 1. 从 vscodeConf.json 加载 launch 部分的配置
        vscode_conf_launch_part = self.load_json_template("vscodeConf.json").get("launch", OrderedDict())
        # 获取当前操作系统的特定配置，例如 {"debug_type": "cppvsdbg", "qt_plugins": "...", ...}
        os_specific_conf_from_vscode = vscode_conf_launch_part.get(self.current_os_key, OrderedDict())

        # 2. 查找项目中的可执行文件
        discovered_executables = self.find_executables()
        # 创建一个集合，方便快速查找本次发现的可执行文件路径
        current_script_exe_paths = {exe_info["path"] for exe_info in discovered_executables}

        # 3. 加载现有的 launch.json 文件
        #    默认结构包含 version 和一个空的 configurations 列表
        default_launch_json_structure = OrderedDict([("version", "0.2.0"), ("configurations", [])])
        existing_launch_data = self.load_output_json_safe("launch.json", lambda: OrderedDict(default_launch_json_structure.items())) # 使用 lambda 创建副本

        # 确保基本结构有效
        if not isinstance(existing_launch_data.get("configurations"), list):
            print(f"警告: launch.json 中的 'configurations' 不是列表或丢失。将重置。")
            existing_launch_data["configurations"] = []
        existing_launch_data.setdefault("version", "0.2.0")

        # 4. 构建新的 configurations 列表
        final_configurations_list = []
        # 用于跟踪已处理的现有配置块的索引，避免重复添加或错误删除
        processed_existing_indices = set()

        # --- 阶段 A: 处理/更新与当前发现的 executables 匹配的现有配置 ---
        for exe_info in discovered_executables:
            exe_path = exe_info["path"]
            exe_name = exe_info["name"]
            
            # 构建此可执行文件的“理想”脚本模板（已填充动态值）
            base_template_for_this_exe = self._get_base_launch_config_template(os_specific_conf_from_vscode)
            base_template_for_this_exe["name"] = f"Debug {exe_name}" # 使用exe_info["name"]，它可能不含.exe
            base_template_for_this_exe["program"] = exe_path

            found_matching_existing_block = None
            matching_existing_block_index = -1

            for i, existing_block in enumerate(existing_launch_data["configurations"]):
                if i in processed_existing_indices:
                    continue # 这个块已被处理（例如，它可能匹配了另一个exe，虽然不太可能基于program路径）
                if isinstance(existing_block, dict) and existing_block.get("program") == exe_path:
                    found_matching_existing_block = existing_block
                    matching_existing_block_index = i
                    break
            
            if found_matching_existing_block:
                print(f"找到与 '{exe_path}' 匹配的现有启动配置。将进行更新/补充。")
                # 用户文件中的块优先，脚本只补充缺失的标准键
                updated_block = OrderedDict(found_matching_existing_block.items()) # 从现有块开始
                
                # 确保 'name' 和 'program' 是最新的（如果它们可以改变）
                # 通常 'program' 是匹配键，不应改变。'name' 可以基于 program 的文件名更新。
                updated_block["name"] = base_template_for_this_exe["name"] # 确保名称与当前文件名一致
                updated_block["program"] = exe_path # 确保路径正确（通常不变，因为是匹配键）

                # 遍历脚本基础模板中的所有键
                for template_key, template_default_value in base_template_for_this_exe.items():
                    if template_key not in updated_block: # 如果用户块中完全没有这个键
                        updated_block[template_key] = template_default_value # 则从脚本模板添加
                        print(f"    为 '{updated_block['name']}' 添加了缺失的键 '{template_key}'")
                
                final_configurations_list.append(updated_block)
                processed_existing_indices.add(matching_existing_block_index)
            else:
                print(f"未找到与 '{exe_path}' 匹配的现有启动配置。将创建新的。")
                # 直接使用已填充的脚本模板作为新块
                final_configurations_list.append(base_template_for_this_exe)

        # --- 阶段 B: 处理现有 launch.json 中不匹配当前发现的 executables 的配置 ---
        for i, existing_block in enumerate(existing_launch_data["configurations"]):
            if i in processed_existing_indices:
                continue # 这个块已经匹配了当前的一个exe并被处理了

            if isinstance(existing_block, dict):
                program_path_in_existing_block = existing_block.get("program")
                # 如果这个现有块看起来是脚本之前生成的（有 program 路径），但现在这个程序找不到了
                if program_path_in_existing_block and program_path_in_existing_block not in current_script_exe_paths:
                    # 为了更安全，我们可以检查 name 是否也符合脚本生成模式
                    block_name = existing_block.get("name", "")
                    if block_name.startswith("Debug ") or block_name.startswith("(gdb) Launch") or block_name.startswith("(Windows) Launch"): # 假设这些是脚本可能生成的前缀
                        print(f"删除过时的启动配置: '{existing_block.get('name', 'Unnamed')}' (程序: {program_path_in_existing_block})")
                        continue # 跳过，不加入到 final_configurations_list
                
                # 如果执行到这里，意味着这个块：
                # 1. 没有 program 路径 (可能是附加进程等用户自定义类型)
                # 2. 或其 program 路径不在当前发现的exe中，但其名称不像脚本生成的（用户自定义的）
                # 这种情况下，我们保留它
                print(f"保留用户自定义或未匹配的现有启动配置: '{existing_block.get('name', 'Unnamed')}'")
                final_configurations_list.append(existing_block)
            else: # 非字典类型的条目，也保留
                final_configurations_list.append(existing_block)


        # 5. 构建最终的 launch.json 数据
        final_launch_data = OrderedDict([
            ("version", existing_launch_data["version"]), # 保留现有版本号或默认
            ("configurations", final_configurations_list)
        ])

        # 6. 保存
        self.save_json("launch.json", final_launch_data)


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
        LaunchGenerator(project_dir)
        # 如果还有 SettingsGenerator, CCppPropertiesGenerator 等，也在这里实例化
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