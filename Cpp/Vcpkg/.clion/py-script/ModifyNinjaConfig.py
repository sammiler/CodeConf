import sys
import datetime
import os
import time # 导入 time 模块
import json
import re

# --- 配置 ---
LOG_FILE_NAME = "event.log" # 主日志文件
# DEBUG_LOG_FILE_NAME = "debug_script_trace.log" # 可选的更详细的调试日志
TARGET_FILE_BASENAME = "build.ninja"
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



def process_compile_commands_content(content_string):
    log_event("DEBUG", "process_function", f"Entering process_compile_commands_content. Input length: {len(content_string if isinstance(content_string, str) else [])}. Type: {type(content_string)}")
    
    if not isinstance(content_string, str):
        log_event("ERROR", "process_function", f"content_string is not a string, it's {type(content_string)}. Returning as is.")
        return content_string, False

    # 初始化，假设最初内容为输入内容
    current_processing_content = content_string 
    overall_changes_made = False
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

    return current_processing_content, overall_changes_made
        # return content_string, False # 或者之前的 current_processing_content (如果规则1有修改)


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