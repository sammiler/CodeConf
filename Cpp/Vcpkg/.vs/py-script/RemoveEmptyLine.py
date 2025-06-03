import os
import re
import sys

# ANSI Color Codes
BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"
BOLD = "\033[1m"

# Helper print functions for better readability
def print_info(message):
    print(f"{BLUE}ℹ️  {message}{RESET}")

def print_success(message):
    print(f"{GREEN}✅ {message}{RESET}")

def print_warning(message):
    print(f"{YELLOW}⚠️  {message}{RESET}")

def print_error(message):
    print(f"{RED}❌ {message}{RESET}")

def print_action(command_to_display):
    print(f"\n{BLUE}▶️  执行操作:{RESET} {command_to_display}")

def process_file_content(content, target_string_in_comment):
    """
    处理文件内容：删除前导空行并删除包含特定字符串的头部注释块。
    """
    content_no_leading_blanks = re.sub(r'\A(?:^\s*\n)+', '', content, flags=re.MULTILINE)
    escaped_target_string = re.escape(target_string_in_comment)
    header_pattern_str = rf'\A\s*\/\*+[\s\S]*?{escaped_target_string}[\s\S]*?\*+\/\s*'
    header_pattern = re.compile(header_pattern_str, flags=re.MULTILINE)
    replacement_text = ""
    final_content = header_pattern.sub(replacement_text, content_no_leading_blanks, count=1)
    return final_content

def process_project_files(project_dir, target_string_in_comment, dry_run=True):
    """
    遍历项目目录中的 .h 和 .cpp 文件，并处理它们。
    """
    if not project_dir:
        print_error("错误: 项目目录未设置或为空。")
        return

    if not os.path.isdir(project_dir):
        print_error(f"错误: 项目目录 '{project_dir}' 不存在或不是一个目录。")
        return

    if not target_string_in_comment:
        print_error("错误: 未指定要删除注释中包含的字符串。")
        return

    print_action(f"开始处理项目目录: {project_dir}")
    if dry_run:
        print_warning("--- 试运行模式 --- (文件不会被修改)")
    else:
        print_warning(f"--- {BOLD}{RED}⭐⭐⭐ 实际修改模式 ⭐⭐⭐{RESET} --- (文件将被修改)")

    file_extensions = ('.h', '.cpp')
    processed_files_count = 0
    modified_files_count = 0

    for root, _, files in os.walk(project_dir):
        for filename in files:
            if filename.lower().endswith(file_extensions):
                file_path = os.path.join(root, filename)
                # Individual file processing errors are already caught and reported here
                try:
                    print_info(f"  检查文件: {file_path}")
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        original_content = f.read()

                    modified_content = process_file_content(original_content, target_string_in_comment)

                    if modified_content != original_content:
                        modified_files_count += 1
                        if dry_run:
                            print_success(f"    文件 '{file_path}' {YELLOW}将被修改{RESET}。")
                        else:
                            print_success(f"    文件 '{file_path}' {GREEN}将被修改{RESET}。")

                        if not dry_run:
                            with open(file_path, 'w', encoding='utf-8') as f:
                                f.write(modified_content)
                            print_success(f"    文件 '{file_path}' 已更新。")
                    else:
                        print_info(f"    文件 '{file_path}' 无需修改。")
                    processed_files_count += 1
                except Exception as e: # Catch errors for a single file
                    print_error(f"    处理文件 '{file_path}' 时发生错误: {e}")
                    print_warning(f"    跳过文件 '{file_path}' 并继续处理其他文件。")


    print_success(f"\n处理完成。共检查 {processed_files_count} 个文件，其中 {modified_files_count} 个文件被修改（或将在非试运行模式下被修改）。")

def main_menu():
    """
    显示主菜单并处理用户输入。
    """
    project_directory = os.environ.get('PROJECT_DIR')
    target_comment_substring = "This file is part of KDDockWidgets."
    perform_dry_run = True

    while True:
        print(f"\n{BOLD}--- C++/头文件注释批量删除工具 ---{RESET}")
        print("------------------------------------")
        print(f"当前设置:")
        print(f"  1. 项目目录: {YELLOW}{project_directory or '未设置'}{RESET}")
        print(f"  2. 删除注释包含的字符串: {YELLOW}'{target_comment_substring}'{RESET}")
        print(f"  3. 模式: {YELLOW}{'试运行 (Dry Run)' if perform_dry_run else f'{RED}{BOLD}实际修改 (Live Run){RESET}'}{RESET}")
        print("------------------------------------")
        print(f"{GREEN}操作选项:{RESET}")
        print(f"  {GREEN}1{RESET} - 设置/确认目标字符串并开始处理") # Clarified option 1
        print(f"  {GREEN}2{RESET} - 设置项目目录")
        print(f"  {GREEN}3{RESET} - 切换 试运行 / 实际修改 模式")
        print(f"  {GREEN}0{RESET} - 退出程序")
        print("------------------------------------")

        choice = input(f"{BLUE}请输入您的选择 > {RESET}").strip()

        if choice == '1':
            try: # Add try-except block for the main processing action
                new_target_substring_input = input(f"{BLUE}请输入要删除注释中包含的字符串 (当前: '{target_comment_substring}', 直接回车确认): {RESET}").strip()
                if new_target_substring_input:
                    target_comment_substring = new_target_substring_input

                if not target_comment_substring:
                    print_error("目标字符串不能为空！请重新设置或确认。")
                    continue # Go back to menu
                if not project_directory:
                    print_error("项目目录未设置！请先通过选项 '2' 设置。")
                    continue # Go back to menu

                print_action(f"准备删除包含 \"{target_comment_substring}\" 的注释块")
                process_project_files(project_directory, target_comment_substring, perform_dry_run)

            except KeyboardInterrupt: # Handle Ctrl+C gracefully
                print_warning("\n操作被用户中断。返回主菜单。")
                continue # Go back to menu
            except Exception as e: # Catch any other unexpected errors during this action
                print_error(f"执行操作时发生意外错误: {e}")
                print_info("已返回主菜单。请检查设置或错误信息后重试。")
                # Optionally, log the full traceback for debugging
                # import traceback
                # print_error(f"详细错误信息:\n{traceback.format_exc()}")
                continue # Go back to menu

        elif choice == '2':
            try: # Add try-except for robustness, though less likely to fail here
                new_project_dir_input = input(f"{BLUE}请输入项目目录的绝对或相对路径 (当前: {project_directory or '未设置'}): {RESET}").strip()
                if new_project_dir_input:
                    expanded_dir = os.path.abspath(os.path.expanduser(new_project_dir_input))
                    if os.path.isdir(expanded_dir):
                        project_directory = expanded_dir
                        print_success(f"项目目录已更新为: {project_directory}")
                    else:
                        print_error(f"路径 '{expanded_dir}' 不是一个有效的目录。项目目录未更改。")
                else:
                    print_warning("输入为空，项目目录未更改。")
            except Exception as e:
                print_error(f"设置项目目录时发生错误: {e}")
                continue # Go back to menu

        elif choice == '3':
            perform_dry_run = not perform_dry_run
            if perform_dry_run:
                print_success("模式已切换为: 试运行 (Dry Run)")
            else:
                print_warning(f"模式已切换为: {RED}{BOLD}实际修改 (Live Run){RESET} - 请谨慎操作！")

        elif choice == '0':
            print_info("感谢使用，程序已退出。")
            sys.exit(0)
        else:
            print_error("无效的选择，请重新输入。")

if __name__ == "__main__":
    initial_project_dir = os.environ.get('PROJECT_DIR')
    if initial_project_dir:
        if os.path.isdir(initial_project_dir):
            print_info(f"检测到 PROJECT_DIR 环境变量，初始项目目录设置为: {initial_project_dir}")
        else:
            print_warning(f"PROJECT_DIR 环境变量 ('{initial_project_dir}') 不是有效目录，请在菜单中设置。")
            # No need to pop, main_menu will use None if it's invalid and prompt user
            os.environ.pop('PROJECT_DIR', None)


    try: # Overall try-except for the main_menu itself, e.g., for unexpected exit or setup issues
        main_menu()
    except KeyboardInterrupt:
        print_info("\n程序被用户中断退出。")
        sys.exit(0)
    except Exception as e:
        print_error(f"程序遇到严重错误并即将退出: {e}")
        # For debugging, you might want to see the full traceback
        import traceback
        print_error(f"详细错误信息:\n{traceback.format_exc()}")
        sys.exit(1)