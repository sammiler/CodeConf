import os
import sys
import copy # 用于深拷贝排除列表
from pathlib import Path

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

# --- 初始配置 ---
INITIAL_EXCLUDED_DIRECTORIES = [
    "app/crashhandler",
    "ext",
    ".vscode", # 常见的排除目录
    "build",   # 常见的构建目录
    ".git",    # Git 目录
    # 如果需要，可以添加其他常见的默认排除项
]

# --- 原始核心逻辑 (根据用户要求保持不变，放在此处进行封装) ---
def find_qobject_headers(project_dir_str: str, excluded_dirs: list = None):
    """
    在项目目录中查找包含 Q_OBJECT 的头文件，
    排除指定的子目录，并生成 CMake 兼容的路径列表。
    (用户提供的原始函数)
    """
    project_path = Path(project_dir_str)
    if not project_path.is_dir():
        # 使用原始打印风格以保持函数一致性，但添加颜色
        print(f"{RED}错误：项目目录 '{project_dir_str}' 不存在或不是一个目录。{RESET}")
        return None

    if excluded_dirs is None:
        excluded_dirs = []

    # 这些路径是相对于 project_path 的
    normalized_excluded_paths = [project_path / Path(d).as_posix() for d in excluded_dirs]


    q_object_headers_relative_paths = []
    header_extensions = ("*.h", "*.hpp", "*.hxx")

    print(f"{BLUE}正在扫描头文件于: {project_path}{RESET}") # 为清晰起见添加了颜色
    if normalized_excluded_paths:
        print(f"{BLUE}正在排除的完整路径:{RESET}")
        for p in normalized_excluded_paths:
            print(f"{YELLOW}  - {str(p)}{RESET}")


    for ext in header_extensions:
        for header_file in project_path.rglob(ext):
            is_excluded = False
            for excluded_path_obj in normalized_excluded_paths:
                try:
                    # 检查 header_file 是否在任何 excluded_path_obj 目录内
                    if header_file.resolve().is_relative_to(excluded_path_obj.resolve()): # Python 3.9+
                        is_excluded = True
                        break
                except AttributeError: # 兼容 Python < 3.9
                    try:
                        header_file.resolve().relative_to(excluded_path_obj.resolve())
                        is_excluded = True
                        break
                    except ValueError:
                        pass # 不是相对于此 excluded_path
                except Exception as e_rel: # 捕获路径比较期间的其他潜在错误
                    print(f"{YELLOW}警告：比较路径 {header_file} 与 {excluded_path_obj} 时出错: {e_rel}{RESET}")


            if is_excluded:
                # print(f"跳过 (已排除): {header_file}") # 原始调试打印
                continue # 跳过此文件

            try:
                content = header_file.read_text(encoding='utf-8', errors='ignore')
                if "Q_OBJECT" in content:
                    relative_path = header_file.relative_to(project_path)
                    relative_path_str = str(relative_path).replace('\\', '/')
                    q_object_headers_relative_paths.append(relative_path_str)
                    # print(f"在以下文件中找到 Q_OBJECT: {header_file} (相对路径: {relative_path_str})") # 原始打印
            except Exception as e:
                print(f"{YELLOW}警告：无法读取或处理文件 {header_file}: {e}{RESET}")

    if q_object_headers_relative_paths:
        print_success(f"找到了 {len(q_object_headers_relative_paths)} 个包含 Q_OBJECT 的头文件。")
    else:
        print_info("未找到符合条件的包含 Q_OBJECT 的头文件。")
    return q_object_headers_relative_paths

def generate_cmake_file(project_dir_str: str, relative_header_paths: list):
    """
    生成列出 Q_OBJECT 头文件的 CMake 文件。
    (用户提供的原始函数)
    """
    project_path = Path(project_dir_str)
    cmake_subdir = project_path / "cmake"
    try:
        cmake_subdir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"{RED}错误：无法在 {cmake_subdir} 创建 'cmake' 子目录: {e}{RESET}")
        return

    output_file_path = cmake_subdir / "QHeaders.cmake"
    cmake_content = "# QHeaders.cmake (由 Python 脚本自动生成)\n"
    cmake_content += "# 包含带有 Q_OBJECT 宏的头文件，供 Qt MOC 使用。\n\n"

    if not relative_header_paths:
        cmake_content += "set(Q_HEADERS)\n"
        cmake_content += "# 未找到包含 Q_OBJECT 的头文件，或所有文件均被排除。\n"
    else:
        cmake_content += "set(Q_HEADERS\n"
        for rel_path in sorted(relative_header_paths):
            cmake_path_entry = f"${{CMAKE_SOURCE_DIR}}/{rel_path}"
            cmake_content += f"        {cmake_path_entry}\n" # 为 CMake 可读性缩进
        cmake_content += ")\n"

    try:
        output_file_path.write_text(cmake_content, encoding='utf-8')
        print_success(f"成功生成 CMake 文件: {output_file_path}")
        # print("内容:\n----------\n" + cmake_content.strip() + "\n----------") # 原始打印
    except Exception as e:
        print(f"{RED}错误：无法写入到 {output_file_path}: {e}{RESET}")

# --- 交互式应用程序类 ---
class QObjectCmakeGeneratorApp:
    def __init__(self):
        self.project_dir: str | None = os.environ.get("PROJECT_DIR")
        self.excluded_directories: list = copy.deepcopy(INITIAL_EXCLUDED_DIRECTORIES)
        self.is_running = True

        if self.project_dir:
            # 在开始时验证一次 project_dir
            project_path_obj = Path(self.project_dir)
            if not project_path_obj.exists():
                print_warning(f"PROJECT_DIR '{self.project_dir}' 不存在。")
                self.project_dir = None # 如果路径不存在则无效化
            elif not project_path_obj.is_dir():
                print_warning(f"PROJECT_DIR '{self.project_dir}' 不是一个目录。")
                self.project_dir = None # 如果不是目录则无效化
            else:
                self.project_dir = str(project_path_obj.resolve()) # 使用解析后的绝对路径
                print_info(f"使用项目目录: {self.project_dir}")
        else:
            print_warning("环境变量 PROJECT_DIR 未设置。")
            print_info("请设置 PROJECT_DIR 为您的项目根目录，以便脚本正常工作。")


    def _get_valid_project_dir(self) -> str | None:
        if not self.project_dir:
            print_error("PROJECT_DIR 未设置或无效。请设置后重启脚本，或确保其有效。")
            return None
        return self.project_dir

    def manage_excluded_directories(self):
        while True:
            print_menu_header("管理排除的目录")
            if not self.excluded_directories:
                print_info("当前没有排除任何目录。")
            else:
                print_info("当前排除的目录 (相对于项目根目录):")
                for i, dir_path in enumerate(self.excluded_directories):
                    print(f"  {GREEN}{i + 1}{RESET}: {YELLOW}{dir_path}{RESET}")

            print_option("a", "添加一个排除目录")
            if self.excluded_directories:
                print_option("r", "移除一个排除目录")
            print_option("b", "返回主菜单")

            choice = input(f"{BLUE}请选择一个选项 > {RESET}").strip().lower()

            if choice == 'a':
                new_dir = input(f"{BLUE}请输入要排除的目录路径 (例如 'build', 'src/tests'): {RESET}").strip()
                if new_dir:
                    # 为保持一致性，将路径分隔符规范化为正斜杠
                    normalized_new_dir = new_dir.replace('\\', '/')
                    if normalized_new_dir not in self.excluded_directories:
                        self.excluded_directories.append(normalized_new_dir)
                        print_success(f"已将 '{normalized_new_dir}' 添加到排除列表。")
                    else:
                        print_warning(f"'{normalized_new_dir}' 已存在于排除列表中。")
                else:
                    print_warning("目录路径不能为空。")
            elif choice == 'r' and self.excluded_directories:
                try:
                    idx_str = input(f"{BLUE}请输入要移除目录的编号: {RESET}").strip()
                    idx_to_remove = int(idx_str) - 1
                    if 0 <= idx_to_remove < len(self.excluded_directories):
                        removed_dir = self.excluded_directories.pop(idx_to_remove)
                        print_success(f"已从排除列表移除 '{removed_dir}'。")
                    else:
                        print_error("无效的编号。")
                except ValueError:
                    print_error("请输入一个有效的数字。")
            elif choice == 'b':
                break
            else:
                print_error("无效选项，请重试。")

    def execute_generation(self):
        print_action("执行 Q_OBJECT 头文件扫描及 CMake 文件生成")

        current_project_dir = self._get_valid_project_dir()
        if not current_project_dir:
            return # _get_valid_project_dir 已打印错误信息

        print_info(f"使用项目目录: {current_project_dir}")
        print_info(f"使用排除目录: {self.excluded_directories or '无'}")

        # 执行前确认 (可选，但对于破坏性或长时间操作是好的实践)
        confirm = input(f"{YELLOW}是否继续扫描并生成文件? (y/N): {RESET}").strip().lower()
        if confirm != 'y':
            print_info("用户取消了操作。")
            return

        try:
            relative_header_paths = find_qobject_headers(current_project_dir, self.excluded_directories)

            if relative_header_paths is not None: # find_qobject_headers 在初始目录错误时返回 None
                generate_cmake_file(current_project_dir, relative_header_paths)
            else:
                # 这种情况 (project_dir 本身无效) 理想情况下应由 _get_valid_project_dir 捕获
                # 但 find_qobject_headers 有其自身的检查。
                print_error("由于项目目录问题，无法找到 Q_OBJECT 头文件。")

        except Exception as e:
            print_error(f"生成过程中发生意外错误: {e}")
            # import traceback # 用于调试
            # print_error(f"详细回溯信息: {traceback.format_exc()}")

    def main_loop(self):
        while self.is_running:
            print_menu_header("Q_OBJECT CMake 生成器")
            if self.project_dir:
                print_config_item("项目目录 (PROJECT_DIR)", self.project_dir)
            else:
                print_warning("PROJECT_DIR 未设置或无效。执行将会失败。")

            print_config_item("已排除的目录", f"{len(self.excluded_directories)} 个已配置")
            print("------------------------------------")
            print_option("1", "管理排除的目录")
            print_option("2", "执行扫描和 CMake 生成")
            print_option("0", "退出")
            print("------------------------------------")

            choice = input(f"{BLUE}请输入您的选择 > {RESET}").strip()

            try:
                if choice == '1':
                    self.manage_excluded_directories()
                elif choice == '2':
                    if not self.project_dir:
                        print_error("无法执行：PROJECT_DIR 未设置或无效。")
                        print_info("请设置 PROJECT_DIR 环境变量并重启，或检查其有效性。")
                    else:
                        self.execute_generation()
                elif choice == '0':
                    self.is_running = False
                    print_info("正在退出应用程序。")
                else:
                    print_error("无效选择，请重试。")
            except KeyboardInterrupt:
                print_warning("\n操作被用户中断。返回主菜单。")
            except Exception as e:
                print_error(f"发生意外的应用程序错误: {e}")
                # import traceback # 用于调试
                # print_error(f"详细回溯信息: {traceback.format_exc()}")
                print_info("返回主菜单。")


def main_interactive():
    app = QObjectCmakeGeneratorApp()
    app.main_loop()

if __name__ == "__main__":
    main_interactive()