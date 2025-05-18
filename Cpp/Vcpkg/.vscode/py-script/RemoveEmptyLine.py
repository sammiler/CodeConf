import os
import re
import sys

def process_file_content(content, new_header_comment_raw):
    """
    处理文件内容：删除前导空行并替换头部注释。
    """
    # 1. 删除前导空行
    #    模式解释:
    #    \A       - 匹配字符串的绝对开头
    #    (?: ... )+ - 非捕获组，匹配一次或多次
    #    ^\s* - 匹配一行的开始，后跟零个或多个空白字符
    #    \n       - 匹配一个换行符
    content_no_leading_blanks = re.sub(r'\A(?:^\s*\n)+', '', content, flags=re.MULTILINE)

    # 2. 替换头部注释
    #    模式解释 (具体模式需要根据您的注释块格式和替换内容来调整):
    #    \A       - 再次确保从（可能已修改的）内容的开头开始匹配
    #    \s* - 匹配任何可能的前导空白（如果第一步后仍有，或者注释前有少量空格）
    #    \/\*+\s*Olive - Non-Linear Video Editor - 匹配注释开始和特定文本
    #    [\s\S]*? - 匹配包括换行符在内的任何字符，零次或多次，非贪婪
    #    \*+\/    - 匹配注释的结束
    #    \s* - 匹配注释块后的任何换行符或空白，以便完全替换掉
    header_pattern = re.compile(r'\A\s*\/\*+[\s\S]*?This file is part of KDDockWidgets.[\s\S]*?\*+\/\s*', flags=re.MULTILINE)

    # 准备替换内容
    # 如果 new_header_comment_raw 为空字符串，则表示删除
    # 否则，确保末尾有一个换行符（如果它本身不以换行符结尾且非空）
    replacement_text = new_header_comment_raw
    if replacement_text and not replacement_text.endswith('\n'):
        replacement_text += '\n'
    if not replacement_text and content_no_leading_blanks: # 如果删除且后面有内容，确保后续内容不意外紧贴
        pass # 通常 re.sub 替换为空字符串即可

    final_content = header_pattern.sub(replacement_text, content_no_leading_blanks, count=1) # count=1确保只替换第一个匹配项（文件头）

    return final_content

def process_project_files(project_dir, new_header_comment_raw, dry_run=True):
    """
    遍历项目目录中的 .h 和 .cpp 文件，并处理它们。
    """
    if not project_dir:
        print("错误: PROJECT_DIR 环境变量未设置或为空。")
        return

    if not os.path.isdir(project_dir):
        print(f"错误: 项目目录 '{project_dir}' 不存在或不是一个目录。")
        return

    print(f"正在处理项目目录: {project_dir}")
    if dry_run:
        print("--- 试运行模式 --- (文件不会被修改)")

    file_extensions = ('.h', '.cpp')
    processed_files_count = 0
    modified_files_count = 0

    for root, _, files in os.walk(project_dir):
        for filename in files:
            if filename.lower().endswith(file_extensions):
                file_path = os.path.join(root, filename)
                print(f"  检查文件: {file_path}")
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        original_content = f.read()

                    modified_content = process_file_content(original_content, new_header_comment_raw)

                    if modified_content != original_content:
                        modified_files_count += 1
                        print(f"    文件 '{file_path}' 将被修改。")
                        if not dry_run:
                            with open(file_path, 'w', encoding='utf-8') as f:
                                f.write(modified_content)
                            print(f"    文件 '{file_path}' 已更新。")
                    else:
                        print(f"    文件 '{file_path}' 无需修改。")
                    processed_files_count += 1
                except Exception as e:
                    print(f"    处理文件 '{file_path}' 时发生错误: {e}")

    print(f"\n处理完成。共检查 {processed_files_count} 个文件，其中 {modified_files_count} 个文件被修改（或将在非试运行模式下被修改）。")

if __name__ == "__main__":
    project_directory = os.environ.get('PROJECT_DIR')

    # ----- 请在这里配置您的替换内容 -----
    # 示例1: 删除注释块
    new_comment_text = ""

    # 示例2: 替换为新的单行注释
    # new_comment_text = "/* My Awesome Project - Copyright 2025 */"


    # ------------------------------------

    if not project_directory:
        print("错误：PROJECT_DIR 环境变量未设置。请在运行脚本前设置它。")
        print("例如： export PROJECT_DIR=/path/to/your/project (Linux/macOS)")
        print("       set PROJECT_DIR=C:\\path\\to\\your\\project (Windows CMD)")
        print("       $env:PROJECT_DIR = 'C:\\path\\to\\your\\project' (Windows PowerShell)")
        sys.exit(1)

    # 设置 dry_run=False 以实际修改文件
    # 设置 dry_run=True (默认) 以查看哪些文件会被修改而不实际写入
    perform_dry_run = False # 改为 False 以实际写入文件

    process_project_files(project_directory, new_comment_text, dry_run=perform_dry_run)