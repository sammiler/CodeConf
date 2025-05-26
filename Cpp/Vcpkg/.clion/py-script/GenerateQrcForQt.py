import json
import os
import sys
import copy # For deep copying the configuration template
from pathlib import Path

# ANSI Color Codes
BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"
BOLD = "\033[1m"

# Helper print functions
def print_info(message): print(f"{BLUE}ℹ️  {message}{RESET}")
def print_success(message): print(f"{GREEN}✅ {message}{RESET}")
def print_warning(message): print(f"{YELLOW}⚠️  {message}{RESET}")
def print_error(message): print(f"{RED}❌ {message}{RESET}")
def print_action(command_to_display): print(f"\n{BLUE}▶️  {command_to_display}{RESET}")
def print_option(key, text): print(f"  {GREEN}{key}{RESET} - {text}")
def print_menu_header(title): print(f"\n{BOLD}--- {title} ---{RESET}")
def print_config_item(key, value_str): print(f"  {key}: {YELLOW}{value_str}{RESET}")


# Initial configuration template (in-memory)
INITIAL_QRC_CONFIG_TEMPLATE = {
    "ignore": ["h", "cpp", "c", "hpp", "mm", "qml", "js", "ui", "json", "sh", "webp", "txt", "qrc", "DS_Store", "ini"],
    "ignoreName": [".DS_Store", "Thumbs.db", "desktop.ini"], # Common ignorable file names
    "resources": []  # User must define these
}

class ProjectRootFinder:
    def find_root(self) -> Path | None:
        project_dir_env = os.environ.get("PROJECT_DIR")
        if not project_dir_env:
            print_warning("环境变量 PROJECT_DIR 未设置。某些功能可能受限或需要手动设置。")
            return None

        try:
            root_path = Path(project_dir_env).resolve()
            if not root_path.exists():
                print_error(f"PROJECT_DIR 指定的路径 {root_path} 不存在。")
                return None
            if not root_path.is_dir():
                print_error(f"PROJECT_DIR 指定的路径 {root_path} 不是一个目录。")
                return None
            print_info(f"项目根目录已从 PROJECT_DIR 加载: {root_path}")
            return root_path
        except Exception as e:
            print_error(f"解析 PROJECT_DIR 时出错: {e}")
            return None

class QrcGeneratorApp:
    def __init__(self):
        self.project_root_dir: Path | None = ProjectRootFinder().find_root()
        self.current_config = copy.deepcopy(INITIAL_QRC_CONFIG_TEMPLATE)
        self.is_running = True

    def _get_valid_project_root(self) -> Path | None:
        if not self.project_root_dir:
            print_error("项目根目录未设置或无效。请确保 PROJECT_DIR 环境变量已正确设置。")
            # Future enhancement: Allow setting project_root_dir interactively
            return None
        if not self.project_root_dir.is_dir():
            print_error(f"配置的项目根目录 {self.project_root_dir} 不是有效目录。")
            return None
        return self.project_root_dir

    def is_qt_project(self) -> bool:
        root_dir = self._get_valid_project_root()
        if not root_dir:
            return False

        cmake_path = root_dir / "CMakeLists.txt"
        try:
            with open(cmake_path, 'r', encoding='utf-8') as f:
                content = f.read()
                if "find_package(Qt" not in content and "find_package(QT" not in content : # common variations
                    print_warning("当前项目可能不是Qt项目 (CMakeLists.txt 中未找到 'find_package(Qt...)')。")
                    return False # Or return True and let user decide if they want to proceed
            return True
        except FileNotFoundError:
            print_warning("未找到 CMakeLists.txt，无法确认是否为 Qt 项目。")
            return False # Or True, depending on desired strictness
        except IOError as e:
            print_error(f"读取 CMakeLists.txt 失败: {e}")
            return False

    def _manage_list_items(self, config_key: str, item_name_singular: str, item_name_plural: str):
        """Generic helper to manage lists like 'ignore' or 'ignoreName'."""
        while True:
            print_menu_header(f"管理忽略的{item_name_plural}")
            current_items = self.current_config[config_key]
            if not current_items:
                print_info(f"当前没有忽略的{item_name_plural}。")
            else:
                print_info(f"当前忽略的{item_name_plural}:")
                for i, item in enumerate(current_items):
                    print_config_item(f"  {i+1}", item)

            print_option("a", f"添加新的{item_name_singular}")
            if current_items:
                print_option("r", f"移除一个{item_name_singular}")
            print_option("b", "返回主菜单")

            choice = input(f"{BLUE}选择操作 > {RESET}").strip().lower()

            if choice == 'a':
                new_item = input(f"{BLUE}输入要添加的{item_name_singular}: {RESET}").strip()
                if new_item and new_item not in current_items:
                    current_items.append(new_item)
                    print_success(f"已添加 '{new_item}'。")
                elif not new_item:
                    print_warning("输入为空，未添加。")
                else:
                    print_warning(f"'{new_item}' 已经存在。")
            elif choice == 'r' and current_items:
                try:
                    idx_str = input(f"{BLUE}输入要移除的{item_name_singular}的编号: {RESET}").strip()
                    idx = int(idx_str) - 1
                    if 0 <= idx < len(current_items):
                        removed_item = current_items.pop(idx)
                        print_success(f"已移除 '{removed_item}'。")
                    else:
                        print_error("无效的编号。")
                except ValueError:
                    print_error("请输入有效的数字编号。")
            elif choice == 'b':
                break
            else:
                print_error("无效选择。")

    def manage_ignored_extensions(self):
        self._manage_list_items("ignore", "后缀名", "后缀名列表")

    def manage_ignored_names(self):
        self._manage_list_items("ignoreName", "文件名", "文件名列表")

    def manage_resource_directories(self):
        while True:
            print_menu_header("管理资源目录")
            resources = self.current_config["resources"]
            if not resources:
                print_info("当前没有配置资源目录。")
            else:
                print_info("当前配置的资源目录:")
                for i, res in enumerate(resources):
                    print(f"  {GREEN}{i+1}{RESET}: Path='{YELLOW}{res['path']}{RESET}', Prefix='{YELLOW}{res['prefix']}{RESET}'")

            print_option("a", "添加新的资源目录")
            if resources:
                print_option("r", "移除一个资源目录")
                print_option("m", "修改一个资源目录")
            print_option("b", "返回主菜单")

            choice = input(f"{BLUE}选择操作 > {RESET}").strip().lower()

            if choice == 'a':
                path = input(f"{BLUE}输入资源路径 (相对于项目根目录): {RESET}").strip()
                prefix = input(f"{BLUE}输入资源前缀 (例如 /icons, 默认为 /): {RESET}").strip()
                if not prefix: prefix = "/"
                if not prefix.startswith("/"): prefix = "/" + prefix

                if path:
                    resources.append({"path": path, "prefix": prefix})
                    print_success(f"已添加资源: Path='{path}', Prefix='{prefix}'")
                else:
                    print_warning("路径不能为空。")

            elif choice == 'r' and resources:
                try:
                    idx_str = input(f"{BLUE}输入要移除的资源目录的编号: {RESET}").strip()
                    idx = int(idx_str) - 1
                    if 0 <= idx < len(resources):
                        removed = resources.pop(idx)
                        print_success(f"已移除资源: Path='{removed['path']}', Prefix='{removed['prefix']}'")
                    else:
                        print_error("无效的编号。")
                except ValueError:
                    print_error("请输入有效的数字编号。")

            elif choice == 'm' and resources:
                try:
                    idx_str = input(f"{BLUE}输入要修改的资源目录的编号: {RESET}").strip()
                    idx = int(idx_str) - 1
                    if 0 <= idx < len(resources):
                        print_info(f"当前值: Path='{resources[idx]['path']}', Prefix='{resources[idx]['prefix']}'")
                        new_path = input(f"{BLUE}输入新路径 (回车保留 '{resources[idx]['path']}'): {RESET}").strip()
                        new_prefix = input(f"{BLUE}输入新前缀 (回车保留 '{resources[idx]['prefix']}'): {RESET}").strip()

                        if new_path: resources[idx]['path'] = new_path
                        if new_prefix:
                            if not new_prefix.startswith("/"): new_prefix = "/" + new_prefix
                            resources[idx]['prefix'] = new_prefix
                        print_success("资源已更新。")
                    else:
                        print_error("无效的编号。")
                except ValueError:
                    print_error("请输入有效的数字编号。")

            elif choice == 'b':
                break
            else:
                print_error("无效选择。")

    def show_current_configuration(self):
        print_menu_header("当前 QRC 生成配置")
        if self.project_root_dir:
            print_config_item("项目根目录 (PROJECT_DIR)", str(self.project_root_dir))
        else:
            print_config_item("项目根目录 (PROJECT_DIR)", "未设置或无效")

        print_config_item("忽略的后缀", ", ".join(self.current_config['ignore']) or "无")
        print_config_item("忽略的文件名", ", ".join(self.current_config['ignoreName']) or "无")
        print_info("资源目录:")
        if not self.current_config['resources']:
            print_info("  无")
        else:
            for i, res in enumerate(self.current_config['resources']):
                print(f"  {GREEN}{i+1}{RESET}: Path='{YELLOW}{res['path']}{RESET}', Prefix='{YELLOW}{res['prefix']}{RESET}'")
        input(f"\n{BLUE}按回车键返回主菜单...{RESET}")

    def _get_files_recursively(self, base_dir: Path, current_resource_path: Path, ignore_exts: list, ignore_names: list) -> list:
        """
        Recursively get files, paths relative to base_dir (project root).
        current_resource_path is the specific sub-directory for this resource element.
        """
        results = []
        try:
            # Ensure current_resource_path is absolute for iteration
            absolute_resource_dir = base_dir / current_resource_path
            if not absolute_resource_dir.is_dir():
                print_warning(f"资源路径 '{absolute_resource_dir}' 不是一个目录或不存在，跳过。")
                return []

            for entry in absolute_resource_dir.rglob("*"): # Use rglob for recursive search
                if entry.is_file():
                    # Path relative to project root for potential global ignores or other logic
                    relative_to_root = entry.relative_to(base_dir).as_posix()
                    ext = entry.suffix[1:].lower() if entry.suffix else ""

                    # Check against ignore lists
                    if ext not in ignore_exts and entry.name not in ignore_names:
                        results.append(relative_to_root) # Store path relative to project root
        except Exception as e:
            print_error(f"读取目录 {current_resource_path} (在 {base_dir} 内) 时出错: {e}")
        return results

    def trigger_qrc_generation(self):
        print_action("开始生成 QRC 文件")

        root_dir = self._get_valid_project_root()
        if not root_dir:
            print_error("无法生成 QRC：项目根目录无效。")
            return

        if not self.current_config["resources"]:
            print_error("无法生成 QRC：没有配置任何资源目录。请先通过菜单添加。")
            return

        if not self.is_qt_project():
            # is_qt_project already prints a warning if not a Qt project
            confirm = input(f"{YELLOW}当前项目可能不是标准的Qt项目，或者无法验证。是否仍要继续生成QRC文件? (y/N): {RESET}").strip().lower()
            if confirm != 'y':
                print_info("QRC 生成已取消。")
                return

        # Actual generation logic (adapted from GenerateQrcTask)
        qrc_config = self.current_config
        new_snippets = {} # For VS Code snippets, if still desired

        for resource_item in qrc_config["resources"]:
            resource_sub_path_str = resource_item["path"] # Path like "icons" or "assets/images"
            resource_prefix = resource_item["prefix"]

            # source_dir_for_files is the absolute path for scanning files
            source_dir_for_files = root_dir / resource_sub_path_str

            if not source_dir_for_files.is_dir():
                print_warning(f"资源路径 '{resource_sub_path_str}' (即 '{source_dir_for_files}') 不存在或不是目录，跳过此资源。")
                continue

            print_info(f"处理资源: Path='{resource_sub_path_str}', Prefix='{resource_prefix}'")

            # Files are returned as paths relative to root_dir
            files_in_resource_dir = self._get_files_recursively(
                root_dir,
                Path(resource_sub_path_str), # Pass the relative path for this resource
                qrc_config["ignore"],
                qrc_config["ignoreName"]
            )

            if not files_in_resource_dir:
                print_info(f"  在 '{resource_sub_path_str}' 中没有找到符合条件的文件。")
                continue

            xml_content = "<RCC>\n"
            xml_content += f'    <qresource prefix="{resource_prefix}">\n'

            for file_rel_to_root_str in files_in_resource_dir:
                file_path_obj = Path(file_rel_to_root_str) # e.g., "assets/images/icon.png"

                # Path for QRC <file> tag should be relative to the resource_sub_path_str
                # e.g., if resource_sub_path_str is "assets/images", and file is "assets/images/icon.png",
                # then qrc_file_path should be "icon.png"
                try:
                    qrc_file_path = file_path_obj.relative_to(Path(resource_sub_path_str)).as_posix()
                except ValueError:
                    print_warning(f"  文件 '{file_path_obj}' 不在预期的资源子目录 '{resource_sub_path_str}'下，跳过。")
                    continue

                xml_content += f"        <file>{qrc_file_path}</file>\n"

                # Snippet generation (optional, kept from original)
                snippet_resource_path = f'":{qrc_file_path}"' if resource_prefix == "/" else f'":{resource_prefix}/{qrc_file_path}"'
                # Ensure snippet prefix doesn't start with / if resource_prefix is not "/"
                if resource_prefix != "/" and snippet_resource_path.startswith(":/"):
                    snippet_resource_path = f'":{resource_prefix.lstrip("/")}/{qrc_file_path}"'


                file_name_for_snippet = Path(qrc_file_path).name
                snippet_key_name = f"qrc_{resource_sub_path_str.replace('/', '_')}_{qrc_file_path.replace('/', '_')}"
                new_snippets[snippet_key_name] = {
                    "prefix": file_name_for_snippet,
                    "body": [snippet_resource_path],
                    "description": f"Qt resource path for {qrc_file_path} in {resource_sub_path_str}",
                    "scope": "cpp,qml"
                }

            xml_content += "    </qresource>\n"
            xml_content += "</RCC>\n"

            # Output QRC file inside the resource specific directory
            output_qrc_path = source_dir_for_files / f"{Path(resource_sub_path_str).name}_resources.qrc" # e.g. icons_resources.qrc
            try:
                with open(output_qrc_path, 'w', encoding='utf-8') as f:
                    f.write(xml_content)
                print_success(f"  已生成 QRC 文件: {output_qrc_path.relative_to(root_dir)}")
            except IOError as e:
                print_error(f"  写入 QRC 文件 {output_qrc_path} 失败: {e}")

        if new_snippets:
            # Decide where/if to save snippets. Original saved to util/qrc-snippets.json
            # For now, just print a message or save to a predefined location.
            snippets_output_path = root_dir / ".vscode" / "qrc_generated.code-snippets"
            try:
                snippets_output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(snippets_output_path, 'w', encoding='utf-8') as f:
                    json.dump(new_snippets, f, indent=2, ensure_ascii=False)
                print_success(f"VS Code 代码片段已生成/更新: {snippets_output_path.relative_to(root_dir)}")
            except IOError as e:
                print_error(f"写入代码片段文件失败: {e}")

        print_success("QRC 文件生成过程完成。")


    def main_loop(self):
        while self.is_running:
            print_menu_header("QRC 生成器主菜单")
            if self.project_root_dir:
                print_info(f"当前项目根目录: {YELLOW}{self.project_root_dir}{RESET}")
            else:
                print_warning("项目根目录 (PROJECT_DIR) 未设置或无效。")

            print_option("1", "管理忽略的后缀名")
            print_option("2", "管理忽略的文件名")
            print_option("3", "管理资源目录 (路径和前缀)")
            print_option("4", "显示当前配置")
            print_option("5", "生成 .qrc 文件")
            print_option("0", "退出")
            print("------------------------------------")

            choice = input(f"{BLUE}请输入您的选择 > {RESET}").strip()

            try:
                if choice == '1':
                    self.manage_ignored_extensions()
                elif choice == '2':
                    self.manage_ignored_names()
                elif choice == '3':
                    self.manage_resource_directories()
                elif choice == '4':
                    self.show_current_configuration()
                elif choice == '5':
                    self.trigger_qrc_generation()
                elif choice == '0':
                    self.is_running = False
                    print_info("感谢使用，程序已退出。")
                else:
                    print_error("无效的选择，请重新输入。")
            except KeyboardInterrupt:
                print_warning("\n操作被用户中断。返回主菜单。")
            except Exception as e:
                print_error(f"发生意外错误: {e}")
                # import traceback
                # print_error(f"详细信息: {traceback.format_exc()}") # Uncomment for debugging
                print_info("已返回主菜单。")


def main():
    if "PROJECT_DIR" not in os.environ:
        print_warning("警告: 环境变量 PROJECT_DIR 未设置。")
        print_info("请设置 PROJECT_DIR 指向您的项目根目录以便脚本正常工作。")
        # Example: export PROJECT_DIR=/path/to/your/project
        # For testing, you can set it temporarily:
        # os.environ["PROJECT_DIR"] = "." # or a specific test project path
        # return # Or allow to continue and let user see warnings

    app = QrcGeneratorApp()
    app.main_loop()

if __name__ == "__main__":
    main()