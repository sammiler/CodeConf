import os
import sys
import shutil
# import copy # 不再需要深拷贝静态列表
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

class InteractiveFileCopier:
    def __init__(self):
        self.script_dir = Path(__file__).resolve().parent
        self.template_dir = self.script_dir.parent / "template"
        self.project_root_dir: Path | None = self._get_project_root_from_env()

        # files_to_copy_config 结构:
        # [{"src_rel_in_template": Path("file.txt"), "dst_subdir_in_project": "."},
        #  {"src_rel_in_template": Path("subdir/icon.png"), "dst_subdir_in_project": "."}]
        self.files_to_copy_config: list[dict] = []
        self.is_running = True

        print_info(f"模板目录 (Template Directory): {self.template_dir}")
        if not self.template_dir.is_dir():
            print_warning(f"模板目录 '{self.template_dir}' 不存在或不是一个目录。功能可能无法正常工作。")

        self._scan_template_and_initialize_config() # 启动时扫描并初始化配置

    def _get_project_root_from_env(self) -> Path | None:
        project_dir_env = os.environ.get("PROJECT_DIR")
        if not project_dir_env:
            print_warning("环境变量 PROJECT_DIR 未设置。")
            return None
        try:
            root_path = Path(project_dir_env).resolve()
            if not root_path.exists():
                print_error(f"PROJECT_DIR 指定的路径 '{root_path}' 不存在。")
                return None
            if not root_path.is_dir():
                print_error(f"PROJECT_DIR 指定的路径 '{root_path}' 不是一个目录。")
                return None
            print_info(f"项目根目录 (Project Root): {root_path}")
            return root_path
        except Exception as e:
            print_error(f"解析 PROJECT_DIR 时出错: {e}")
            return None

    def _scan_template_and_initialize_config(self):
        """扫描模板目录并为每个文件创建默认配置条目。"""
        self.files_to_copy_config = [] # 清空旧配置
        if not self.template_dir.is_dir():
            print_warning(f"模板目录 '{self.template_dir}' 不存在，无法扫描。")
            return

        print_info(f"正在扫描模板目录: {self.template_dir} ...")
        scanned_count = 0
        for item_path in self.template_dir.rglob("*"):
            if item_path.is_file():
                src_rel = item_path.relative_to(self.template_dir)
                self.files_to_copy_config.append({
                    "src_rel_in_template": src_rel, # Path 对象
                    "dst_subdir_in_project": "."    # 默认为根目录
                })
                scanned_count +=1

        if scanned_count > 0:
            print_success(f"扫描完成，找到 {scanned_count} 个文件。默认目标均为项目根目录。")
        else:
            print_info("模板目录中未找到任何文件。")

    def _display_current_config(self):
        print_menu_header("当前待复制文件及其目标配置")
        if not self.files_to_copy_config:
            print_info("列表为空 (可能模板目录为空或未扫描成功)。")
            return

        for i, entry in enumerate(self.files_to_copy_config):
            src_rel_path = entry['src_rel_in_template'] # Path 对象
            dst_subdir = entry['dst_subdir_in_project']

            full_src_path = self.template_dir / src_rel_path
            status = f"{GREEN}源存在{RESET}" if full_src_path.exists() else f"{RED}源不存在!{RESET}"

            # 构建最终目标路径的预览
            if self.project_root_dir:
                if dst_subdir == ".":
                    final_dst_preview = self.project_root_dir / src_rel_path
                else:
                    final_dst_preview = self.project_root_dir / dst_subdir / src_rel_path
                final_dst_str = final_dst_preview.as_posix()
            else:
                final_dst_str = f"PROJECT_DIR(未设置)/{dst_subdir}/{src_rel_path.as_posix()}"


            print(f"  {GREEN}{i + 1}{RESET}: 源文件 (Template内): {YELLOW}{src_rel_path.as_posix()}{RESET} ({status})")
            print(f"     当前目标子目录 (PROJECT_DIR内): {YELLOW}{dst_subdir}{RESET}")
            print(f"     最终复制到: {YELLOW}{final_dst_str}{RESET}")

    def _edit_entry_destination(self):
        if not self.files_to_copy_config:
            print_info("文件列表为空，无法修改。")
            return

        print_menu_header("修改文件条目的目标子目录")
        self._display_current_config() # 显示当前列表以便用户选择
        try:
            idx_str = input(f"{BLUE}请输入要修改条目的编号: {RESET}").strip()
            idx_to_edit = int(idx_str) - 1

            if 0 <= idx_to_edit < len(self.files_to_copy_config):
                entry_to_edit = self.files_to_copy_config[idx_to_edit]
                current_dst = entry_to_edit['dst_subdir_in_project']
                src_file_display = entry_to_edit['src_rel_in_template'].as_posix()

                print_info(f"\n正在修改文件: '{src_file_display}'")
                print_info(f"当前目标子目录: '{current_dst}'")

                new_dst_subdir_input = input(f"{BLUE}请输入新的目标子目录 (相对于项目根目录, 输入 '.' 表示根目录, 按回车保留当前值): {RESET}").strip()

                if new_dst_subdir_input: # 如果用户输入了新值
                    # 规范化输入：去除首尾斜杠，如果是空字符串或仅含斜杠，则视为 "."
                    normalized_dst = new_dst_subdir_input.strip('/\\')
                    if not normalized_dst : normalized_dst = "."

                    entry_to_edit['dst_subdir_in_project'] = normalized_dst
                    print_success(f"文件 '{src_file_display}' 的目标子目录已更新为: '{normalized_dst}'")
                else:
                    print_info("目标子目录未更改。")
            else:
                print_error("无效的编号。")
        except ValueError:
            print_error("请输入一个有效的数字编号。")
        input(f"\n{BLUE}按回车键继续...{RESET}")

    def manage_file_targets(self):
        """管理扫描到的文件的目标子目录"""
        while True:
            self._display_current_config()
            print_menu_header("管理文件目标选项")
            if self.files_to_copy_config:
                print_option("e", "修改文件条目的目标子目录")
            print_option("r", "刷新模板文件列表 (重置目标为根目录)")
            print_option("b", "返回主菜单")

            choice = input(f"{BLUE}请选择操作 > {RESET}").strip().lower()

            if choice == 'e' and self.files_to_copy_config:
                self._edit_entry_destination()
            elif choice == 'r':
                print_info("正在刷新模板文件列表并重置所有目标为根目录...")
                self._scan_template_and_initialize_config()
                print_success("列表已刷新。")
            elif choice == 'b':
                break
            else:
                print_error("无效选项。")

    def execute_copy_operation(self):
        print_action("开始执行文件复制操作")

        if self.project_root_dir is None:
            print_error("无法执行复制：PROJECT_DIR 未设置或无效。请先设置环境变量。")
            return

        if not self.template_dir.is_dir():
            print_error(f"无法执行复制：模板目录 '{self.template_dir}' 不存在。")
            return

        if not self.files_to_copy_config:
            print_info("没有从模板目录扫描到任何文件进行复制。")
            return

        confirm = input(f"{YELLOW}您确定要将配置的 {len(self.files_to_copy_config)} 个文件从 '{self.template_dir}' 复制到 '{self.project_root_dir}' (根据指定的目标子目录) 吗? (y/N): {RESET}").strip().lower()
        if confirm != 'y':
            print_info("复制操作已取消。")
            return

        files_copied_count = 0
        files_failed_count = 0

        for entry in self.files_to_copy_config:
            src_relative_path = entry["src_rel_in_template"] # Path 对象
            dst_target_subdir = entry["dst_subdir_in_project"] # 字符串, e.g., "." or "config"

            full_src_file_path = self.template_dir / src_relative_path

            if not full_src_file_path.exists():
                print_warning(f"跳过：源文件 '{full_src_file_path}' 不存在 (可能在扫描后被删除)。")
                files_failed_count +=1
                continue
            if not full_src_file_path.is_file(): # 再次确认是文件
                print_warning(f"跳过：源路径 '{full_src_file_path}' 不是一个文件。")
                files_failed_count += 1
                continue

            # 构建最终的目标文件路径
            if dst_target_subdir == ".":
                # 目标是根目录，保持源文件的相对路径结构
                full_dst_file_path = self.project_root_dir / src_relative_path
            else:
                # 目标是指定子目录，将源文件的相对路径附加到该子目录下
                full_dst_file_path = self.project_root_dir / dst_target_subdir / src_relative_path

            try:
                full_dst_file_path.parent.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                print_error(f"创建目标目录 '{full_dst_file_path.parent}' 失败: {e}")
                files_failed_count += 1
                continue

            try:
                shutil.copy2(full_src_file_path, full_dst_file_path)
                print_success(f"已复制: '{src_relative_path.as_posix()}' (从模板) -> '{full_dst_file_path.relative_to(self.project_root_dir).as_posix()}' (到项目)")
                files_copied_count += 1
            except Exception as e:
                print_error(f"复制文件 '{full_src_file_path}' 到 '{full_dst_file_path}' 失败: {e}")
                files_failed_count += 1

        print_info(f"\n复制操作完成。成功复制 {files_copied_count} 个文件，失败 {files_failed_count} 个。")

    def main_loop(self):
        while self.is_running:
            print_menu_header("文件复制工具 主菜单")
            if self.project_root_dir:
                print_config_item("项目根目录 (PROJECT_DIR)", str(self.project_root_dir))
            else:
                print_warning("PROJECT_DIR 未设置或无效。复制功能将无法执行。")
            print_config_item("模板目录 (Template Dir)", str(self.template_dir))
            print_config_item("已扫描/配置的文件数", f"{len(self.files_to_copy_config)} 个")
            print("------------------------------------")
            print_option("1", "查看/管理文件目标")
            print_option("2", "执行复制操作")
            print_option("0", "退出")
            print("------------------------------------")

            choice = input(f"{BLUE}请输入您的选择 > {RESET}").strip()

            try:
                if choice == '1':
                    self.manage_file_targets()
                elif choice == '2':
                    if not self.project_root_dir:
                        print_error("无法执行复制：PROJECT_DIR 未设置或无效。")
                    elif not self.template_dir.is_dir():
                        print_error(f"无法执行复制：模板目录 '{self.template_dir}' 不存在。")
                    else:
                        self.execute_copy_operation()
                elif choice == '0':
                    self.is_running = False
                    print_info("感谢使用，程序已退出。")
                else:
                    print_error("无效的选择，请重新输入。")
            except KeyboardInterrupt:
                print_warning("\n操作被用户中断。返回主菜单。")
            except Exception as e:
                print_error(f"发生意外错误: {e}")
                # import traceback # 用于调试
                # print_error(f"详细信息: {traceback.format_exc()}")
                print_info("已返回主菜单。")

def main():
    if "PROJECT_DIR" not in os.environ:
        print_warning("警告: 环境变量 PROJECT_DIR 未设置。")
        print_info("请设置 PROJECT_DIR 指向您的项目根目录以便脚本正常复制文件。")

    app = InteractiveFileCopier()
    app.main_loop()

if __name__ == "__main__":
    main()