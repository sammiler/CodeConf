import sys
import datetime
import os
import time # 导入 time 模块
import json
import re

# --- 配置 ---
LOG_FILE_NAME = "event.log" # 主日志文件
# DEBUG_LOG_FILE_NAME = "debug_script_trace.log" # 可选的更详细的调试日志
TARGET_FILE_BASENAME = "compile_commands.json"
SLEEP_DURATION_SECONDS = 1 # 为文件稳定操作设置的延时

# --- 日志记录函数 ---
def log_message_to_file(log_file, message_prefix, event_type, file_path_affected, additional_info=""):
    return
    # timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # log_entry = f"[{timestamp}] {message_prefix}: Event='{event_type}', Path='{file_path_affected}'"
    # if additional_info:
    #     log_entry += f", Info='{additional_info}'"
    # log_entry += "\n"
    
    # print(log_entry.strip()) # 总是打印到 stdout/stderr，方便直接查看

    # try:
    #     with open(log_file, "a", encoding="utf-8") as f:
    #         f.write(log_entry)
    # except Exception as e_log:
    #     # 如果写入主日志失败，尝试打印一个更紧急的错误
    #     print(f"[{timestamp}] VERY CRITICAL: Logging to {log_file} FAILED: {e_log}. Original message: {log_entry.strip()}")

def log_event(event_type, file_path_affected, additional_info=""):
    log_message_to_file(LOG_FILE_NAME, "EVENT", event_type, file_path_affected, additional_info)

# def log_debug(message): # 可选的调试日志函数
#     timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#     log_entry = f"[{timestamp}] DEBUG: {message}\n"
#     print(log_entry.strip())
#     try:
#         with open(DEBUG_LOG_FILE_NAME, "a", encoding="utf-8") as f:
#             f.write(log_entry)
#     except Exception:
#         pass # 调试日志失败就算了

def process_compile_commands_content(content_string):
    log_event("DEBUG", "process_function", f"Entering process_compile_commands_content. Input length: {len(content_string if isinstance(content_string, str) else [])}. Type: {type(content_string)}")
    
    if not isinstance(content_string, str):
        log_event("ERROR", "process_function", f"content_string is not a string, it's {type(content_string)}. Returning as is.")
        return content_string, False

    # 初始化，假设最初内容为输入内容
    current_processing_content = content_string 
    overall_changes_made = False

    # --- 规则 1: -imsvc 处理 ---
    changes_made_rule1 = False
    try:
        # (使用您最终解决空格问题的规则1代码)
        # 例如，我们假设这是之前能正确工作的版本：
        path_pattern_for_rule1 = r'([A-Za-z]:[\\/][^<>:"/\\|?*\s]*|[^<>:"/\\|?*\s]+)'
        regex_imsvc_combined = rf'-imsvc\s*({path_pattern_for_rule1})'
        
        processed_content_rule1, num_replacements1 = re.subn(regex_imsvc_combined, r'-I\1', current_processing_content)
        log_event("DEBUG", "process_function_rule1", f"re.subn (Rule 1) result: num_replacements={num_replacements1}")

        if num_replacements1 > 0:
            current_processing_content = processed_content_rule1 # 更新内容
            changes_made_rule1 = True
            overall_changes_made = True # 标记总的更改状态
            log_event("INFO", "process_function_rule1", f"Rule 1 (-imsvc) applied. Replacements: {num_replacements1}.")
            
    except Exception as e_r1:
        log_event("ERROR", "process_function_rule1", f"Exception during Rule 1 (-imsvc): {type(e_r1).__name__} - {e_r1}")
        # 根据策略，如果一个规则失败，可以选择是否中止或继续。这里我们选择继续，但标记 overall_changes_made 可能不准确。
        # 或者直接 return content_string, False

    # --- 规则 2: /MP 处理 ---
    changes_made_rule2 = False
    try:
        # 规则2 在 规则1 处理后的 current_processing_content 上操作
        log_event("DEBUG", "process_function_rule2", f"Before Rule 2 (/MP). Input length: {len(current_processing_content)}")
        processed_content_rule2, num_replacements2 = re.subn(r'\s*/MP\b', '', current_processing_content)
        log_event("DEBUG", "process_function_rule2", f"re.subn (Rule 2) result: num_replacements={num_replacements2}")
        if num_replacements2 > 0:
            current_processing_content = processed_content_rule2 # 更新内容
            changes_made_rule2 = True
            overall_changes_made = True # 标记总的更改状态
            log_event("INFO", "process_function_rule2", f"Rule 2 (/MP) applied. Replacements: {num_replacements2}.")
    except Exception as e_r2:
        log_event("ERROR", "process_function_rule2", f"Exception during Rule 2 (/MP): {type(e_r2).__name__} - {e_r2}")
        # return content_string, False # 或者之前的 current_processing_content (如果规则1有修改)

    # --- 规则 3: -std:c++XX 替换为 /std:c++XX ---
    changes_made_rule3 = False
    try:
        # 规则3 在 规则2 处理后的 current_processing_content 上操作
        log_event("DEBUG", "process_function_rule3", f"Before Rule 3 (-std:c++). Input length: {len(current_processing_content)}")
        
        # 正则表达式：匹配 "-std:c++" 后面跟着数字 (例如 17, 20, 23 等)
        # 捕获组 \1: c++
        # 捕获组 \2: XX (版本号)
        # 我们也可以直接匹配整个 -std:c++XX
        # regex_std_cpp = r'-std:(c\+\+\d+)' # 捕获 "c++XX"
        # 替换为 r'/std:\1'

        # 或者更简单，直接替换 "-std:" 为 "/std:" 如果后面是 "c++"
        # 为了精确匹配 -std:c++20 或 -std:c++17 等
        # (\d{2}) 捕获两位数字作为版本号
        # 使用 (c\+\+) 是为了让 '+' 被正确处理，而不是作为正则表达式的量词
        # `\b` 词边界，确保我们替换的是独立的标志
        regex_std_cpp_version = r'(?<!\w)-std:(c\+\+\d{2})(?!\w)'
        
        processed_content_rule3, num_replacements3 = re.subn(regex_std_cpp_version, r'/std:\1', current_processing_content)
        log_event("DEBUG", "process_function_rule3", f"re.subn (Rule 3 with regex '{regex_std_cpp_version}') result: num_replacements={num_replacements3}")

        if num_replacements3 > 0:
            current_processing_content = processed_content_rule3 # 更新内容
            changes_made_rule3 = True
            overall_changes_made = True # 标记总的更改状态
            log_event("INFO", "process_function_rule3", f"Rule 3 (-std:c++XX to /std:c++XX) applied. Replacements: {num_replacements3}.")
    except Exception as e_r3:
        log_event("ERROR", "process_function_rule3", f"Exception during Rule 3 (-std:c++XX): {type(e_r3).__name__} - {e_r3}")
        # return content_string, False

    log_event("DEBUG", "process_function", f"Exiting process_compile_commands_content. Overall changes made: {overall_changes_made}. Final length: {len(current_processing_content)}")
    return current_processing_content, overall_changes_made

# --- 主逻辑 ---
if __name__ == "__main__":
    # log_debug(f"Script execution started. Raw arguments: {sys.argv}")

    if len(sys.argv) < 3:
        log_event("Script Error", "N/A", f"Insufficient arguments. Received: {sys.argv}")
        sys.exit(1)

    script_path = sys.argv[0]
    event_type = sys.argv[1]
    file_path = sys.argv[2]

    log_event(event_type, file_path, f"Script invoked. Script path: {script_path}")

    # 对特定事件类型引入延时
    if event_type == "Change New" or event_type == "Change Mod":
        log_event(event_type, file_path, f"Event requires delay. Sleeping for {SLEEP_DURATION_SECONDS} second(s).")
        # time.sleep(SLEEP_DURATION_SECONDS)
        log_event(event_type, file_path, "Resumed after sleep.")

    # 检查是否是目标文件，并且事件类型适合内容处理
    # log_debug(f"Checking if '{file_path}' (basename: {os.path.basename(file_path).lower()}) is target '{TARGET_FILE_BASENAME.lower()}'")
    if os.path.basename(file_path).lower() == TARGET_FILE_BASENAME.lower() and \
       (event_type == "Change Mod" or event_type == "Change New"):
        
        log_event(event_type, file_path, "Target file and event type match. Proceeding with processing.")
        
        original_content_str = None
        try:
            # --- 阶段 1: 检查和读取文件 ---
            # log_debug(f"Checking existence of '{file_path}'")
            if not os.path.exists(file_path):
                log_event(event_type, file_path, "File not found (after potential sleep). Skipping content modification.")
                sys.exit(0) # 文件可能在延时期间被删除了
            
            # log_debug(f"File '{file_path}' exists. Is it a file? {os.path.isfile(file_path)}")
            if not os.path.isfile(file_path):
                log_event(event_type, file_path, "Path is not a regular file. Skipping content modification.")
                sys.exit(0)

            # log_debug(f"Attempting to open and read '{file_path}'")
            with open(file_path, 'r', encoding='utf-8') as f_read:
                original_content_str = f_read.read()
            # log_debug(f"Successfully read content from '{file_path}'. Length: {len(original_content_str)}")

            if not original_content_str.strip(): # 如果文件是空的或只包含空白
                 log_event(event_type, file_path, "File is empty or contains only whitespace. Skipping processing.")
                 sys.exit(0)

            # --- 阶段 2: 处理内容 ---
            processed_content_str, changes_were_made = process_compile_commands_content(original_content_str)
            
            # --- 阶段 3: 写回文件 (如果需要) ---
            if changes_were_made:
                # log_debug(f"Content was modified by script. Attempting to write back to '{file_path}'")
                with open(file_path, 'w', encoding='utf-8') as f_write:
                    f_write.write(processed_content_str)
                # log_debug(f"Successfully wrote back to '{file_path}'")
                log_event(event_type, file_path, "Content modified and written back by script.")
                
                # JSON 验证
                try:
                    json.loads(processed_content_str)
                    # log_debug("Modified content is valid JSON.")
                except json.JSONDecodeError as je:
                    log_event("JSON Error", file_path, f"CRITICAL: Script modification resulted in invalid JSON: {je}")
            else:
                log_event(event_type, file_path, "No content modification needed by script (rules applied but content was already compliant or no rules matched).")

        except IOError as ioe:
            log_event("IOError", file_path, f"IOError during file processing: {ioe}. Errno: {ioe.errno if hasattr(ioe, 'errno') else 'N/A'}")
            sys.exit(1)
        except Exception as e:
            log_event("Processing Error", file_path, f"Generic error during file processing: {type(e).__name__} - {e}. Original content was read: {original_content_str is not None}")
            sys.exit(1)
    else:
        log_event(event_type, file_path, "File or event type not targeted for content processing.")

    # log_debug("Script execution finished.")
    sys.exit(0) # 确保脚本正常结束时返回0