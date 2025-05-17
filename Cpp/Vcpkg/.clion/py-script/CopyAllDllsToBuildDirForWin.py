#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import subprocess
import shutil
import re
import sys
import time
import stat # Needed for checking write permissions on target dir

# --- Configuration ---
ENV_DUMPBIN_PATH = "DUMPBIN_PATH"
ENV_EXECUTABLE_PATHS = "ANALYZE_EXECUTABLES" # Semicolon-separated list
ENV_TARGET_DIR = "TARGET_DLL_DIR"
ENV_SEARCH_PATHS = "DLL_SEARCH_PATHS"  # Semicolon-separated paths
ENV_INCLUDE_VCRUNTIME = "INCLUDE_VCRUNTIME_DLLS" # Set to 1, true, or yes
ENV_EXTRA_COPY_ITEMS = "EXTRA_COPY_ITEMS" # Semicolon-separated DIRS to copy entirely
ENV_EXTRA_COPY_ITEMS_BIN = "EXTRA_COPY_ITEMS_BIN" # Semicolon-separated DIRS to copy DLLs from

# Common system DLLs to exclude (lowercase)
SYSTEM_DLLS_LOWER = {
    "kernel32.dll", "user32.dll", "gdi32.dll", "advapi32.dll", "shell32.dll",
    "ole32.dll", "oleaut32.dll", "msvcrt.dll", "ws2_32.dll", "shlwapi.dll",
    "crypt32.dll", "winmm.dll", "version.dll", "setupapi.dll", "cfgmgr32.dll",
    "imm32.dll", "comctl32.dll", "comdlg32.dll", "rpcrt4.dll", "secur32.dll",
    "ntdll.dll", "bcrypt.dll", "powrprof.dll", "dwmapi.dll", "uxtheme.dll",
    "propsys.dll", "dbghelp.dll", "wininet.dll", "iphlpapi.dll", "kernelbase.dll",
    "msvcp_win.dll", "winhttp.dll", "dnsapi.dll", "userenv.dll", "netapi32.dll",
    "wtsapi32.dll", "psapi.dll", "profapi.dll", "nsi.dll", "winnsi.dll",
    "wevtapi.dll", "esent.dll", "clbcatq.dll", "cryptbase.dll", "sspicli.dll",
    "mswsock.dll", "wldp.dll", "amsi.dll",
    "ucrtbase.dll",
}

# VC++ Runtime DLLs (lowercase) - Excluded by default
VCRUNTIME_DLLS_LOWER = {
    "vcruntime140.dll", "vcruntime140_1.dll", "msvcp140.dll", "msvcp140_1.dll",
    "msvcp140_2.dll", "msvcp140_atomic_wait.dll", "msvcp140_codecvt_ids.dll",
    "vccorlib140.dll", "concrt140.dll",
}

# --- Functions ---

def get_dependencies(executable_path, dumpbin_exe):
    """Use dumpbin to get dependencies."""
    if not os.path.exists(executable_path):
        print(f"  错误: 文件不存在: {executable_path}", file=sys.stderr)
        return None
    if not dumpbin_exe or not os.path.exists(dumpbin_exe):
        print(f"  错误: dumpbin.exe 路径无效或不存在: {dumpbin_exe}", file=sys.stderr)
        return None
    try:
        abs_executable_path = os.path.abspath(executable_path)
        command = [dumpbin_exe, "/dependents", abs_executable_path]
        # print(f"  执行 dumpbin: {' '.join(command)}") # Verbose
        result = subprocess.run(command, capture_output=True, text=False, check=True, timeout=60)
        output_bytes = result.stdout
        output = ""
        # Decode robustly
        try:
            output = output_bytes.decode('utf-8')
        except UnicodeDecodeError:
            try:
                cp_encoding = f'cp{subprocess.check_output(["chcp"]).decode().split(":")[-1].strip()}'
                output = output_bytes.decode(cp_encoding, errors='replace')
                print(f"  警告: dumpbin 输出不是 UTF-8，尝试使用控制台代码页 '{cp_encoding}' 解码。", file=sys.stderr)
            except Exception:
                try:
                    output = output_bytes.decode(sys.getdefaultencoding(), errors='replace')
                    print(f"  警告: dumpbin 输出不是 UTF-8/控制台CP，使用系统默认编码 '{sys.getdefaultencoding()}' 解码。", file=sys.stderr)
                except Exception:
                    output = output_bytes.decode('latin-1', errors='replace')
                    print("  警告: dumpbin 输出解码完全失败，尝试使用 latin-1。", file=sys.stderr)
    except FileNotFoundError:
        print(f"  错误: 无法执行 dumpbin.exe (路径: {dumpbin_exe})。", file=sys.stderr)
        return None
    except subprocess.TimeoutExpired:
        print(f"  错误: dumpbin 执行超时。", file=sys.stderr)
        return None
    except subprocess.CalledProcessError as e:
        print(f"  错误: dumpbin 执行失败 (返回码 {e.returncode}):", file=sys.stderr)
        print(f"    命令: {' '.join(e.cmd)}")
        stderr_snippet = "[无法解码 stderr]"
        if e.stderr:
            try: stderr_snippet = e.stderr.decode('utf-8', errors='replace')[:500].strip()
            except Exception: stderr_snippet = e.stderr.decode('latin-1', errors='replace')[:500].strip()
        stdout_snippet = "[无法解码 stdout]"
        if e.stdout:
            try: stdout_snippet = e.stdout.decode('utf-8', errors='replace')[:500].strip()
            except Exception: stdout_snippet = e.stdout.decode('latin-1', errors='replace')[:500].strip()
        print(f"    stderr: {stderr_snippet}...", file=sys.stderr)
        print(f"    stdout: {stdout_snippet}...", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  执行 dumpbin 时发生未知错误: {e}", file=sys.stderr)
        return None

    dependencies = set()
    dll_pattern = re.compile(r"^\s+([a-zA-Z0-9_.-]+\.dll)\s*$", re.IGNORECASE | re.MULTILINE)
    lines = output.splitlines()
    found_matches = 0
    dependency_section_found = False
    dependency_marker = "image has the following dependencies:"
    for line in lines:
        line_lower = line.lower()
        if dependency_marker in line_lower:
            dependency_section_found = True
            continue
        if dependency_section_found:
            # Match indented lines ending in .dll
            if line.startswith((' ', '\t')) and line.strip().lower().endswith('.dll'):
                match = dll_pattern.match(line)
                if match:
                    dll_name = match.group(1)
                    dependencies.add(dll_name)
                    found_matches += 1
            # Stop searching after dependency section if an empty line is hit? (Optional optimization)
            # elif dependency_section_found and not line.strip():
            #     break # Assumes block structure
    if not dependency_section_found:
        print(f"    警告: 未在 '{os.path.basename(executable_path)}' 的 dumpbin 输出中找到 '{dependency_marker}' 标记。")
    if found_matches == 0 and dependency_section_found:
        print(f"    警告: 在 '{os.path.basename(executable_path)}' 的 dumpbin 输出中找到了依赖项标记，但未解析到任何 DLL。")
    return dependencies

def filter_dependencies(dependencies, include_vcruntime):
    """Filter out system DLLs and (optionally) VC++ Runtime DLLs."""
    if dependencies is None:
        return set()
    # print(f"  开始过滤 {len(dependencies)} 个依赖项...") # Less verbose
    filtered = set()
    skipped_system_count = 0
    skipped_apiset_count = 0
    skipped_vcruntime_count = 0
    for dep in dependencies:
        dep_lower = dep.lower()
        if dep_lower in SYSTEM_DLLS_LOWER:
            skipped_system_count += 1
            continue
        if dep_lower.startswith("api-ms-win-") or dep_lower.startswith("ext-ms-win-"):
            skipped_apiset_count += 1
            continue
        if not include_vcruntime and dep_lower in VCRUNTIME_DLLS_LOWER:
            skipped_vcruntime_count += 1
            continue
        filtered.add(dep)
    # Optional: Log counts if > 0
    # if skipped_system_count > 0: print(f"    过滤掉系统 DLL: {skipped_system_count}")
    # if skipped_apiset_count > 0: print(f"    过滤掉 API Set: {skipped_apiset_count}")
    # if not include_vcruntime and skipped_vcruntime_count > 0: print(f"    过滤掉 VC Runtime: {skipped_vcruntime_count}")
    if filtered: print(f"  过滤后需要查找 {len(filtered)} 个依赖项: {filtered}")
    return filtered

def find_dll_recursively_in_search_paths(dll_name, search_root_dirs):
    """Search recursively within the specified root directories for the DLL."""
    dll_name_lower = dll_name.lower()
    for root_dir in search_root_dirs:
        abs_root_dir = os.path.abspath(root_dir)
        if not os.path.isdir(abs_root_dir):
            continue
        # print(f"    递归搜索 '{dll_name}' 于: {abs_root_dir}") # Verbose
        for dirpath, _, filenames in os.walk(abs_root_dir):
            for filename in filenames:
                if filename.lower() == dll_name_lower:
                    found_path = os.path.join(dirpath, filename)
                    # print(f"      找到: {found_path}") # Verbose
                    return found_path
    return None

def copy_dependencies_recursive(
        initial_target_abs,
        target_dir_abs,
        initial_exe_dir_abs, # Original exe dir for searching
        cmake_search_paths_abs,
        dumpbin_exe,
        include_vcruntime,
        # --- Shared state ---
        processed_files,
        copied_dll_basenames,
        files_to_process_queue, # Shared queue
        not_found_anywhere,
        failed_to_copy,
        processed_counter): # Shared mutable counter
    """
    Recursively find and copy dependencies for a single initial target,
    updating shared state. Operates on the shared queue.
    """
    initial_base = os.path.basename(initial_target_abs)
    target_exe_path_abs = os.path.abspath(os.path.join(target_dir_abs, initial_base))

    # --- Handle the initial target passed to this function ---
    try:
        norm_initial_target = os.path.normcase(initial_target_abs)
        norm_target_exe_path = os.path.normcase(target_exe_path_abs)
        copy_initial_needed = True

        if norm_initial_target == norm_target_exe_path:
            try:
                with open(initial_target_abs, 'rb'): pass # Check readability
                copy_initial_needed = False
                print(f"初始目标 '{initial_base}' 已在目标目录且可访问。")
                # Add to queue if not already processed/queued
                if initial_target_abs not in processed_files and initial_target_abs not in files_to_process_queue:
                    files_to_process_queue.add(initial_target_abs)
                    print(f"  添加现有目标 '{initial_base}' 到处理队列。")
            except Exception as e_access:
                print(f"警告: 初始目标 '{initial_base}' 在目标目录但访问出错: {e_access}", file=sys.stderr)
                # Proceed as if copy needed, might fix permissions or overwrite corrupt file
                copy_initial_needed = True

        elif os.path.exists(target_exe_path_abs):
            try:
                source_mtime = os.stat(initial_target_abs).st_mtime
                target_mtime = os.stat(target_exe_path_abs).st_mtime
                if source_mtime <= target_mtime:
                    copy_initial_needed = False
                    print(f"初始目标 '{initial_base}' 在目标目录已存在且不旧。")
                    # Add the *target* version to queue if needed
                    if target_exe_path_abs not in processed_files and target_exe_path_abs not in files_to_process_queue:
                        files_to_process_queue.add(target_exe_path_abs)
                        print(f"  添加现有目标 '{initial_base}' 到处理队列。")
                else:
                    print(f"初始目标 '{initial_base}' 在目标目录存在旧版本，将更新。")
                    copy_initial_needed = True
            except Exception as e_stat:
                print(f"警告: 比较初始目标 '{initial_base}' 时间戳时出错: {e_stat}", file=sys.stderr)
                copy_initial_needed = True # Attempt copy if unsure
        else:
            copy_initial_needed = True

        if copy_initial_needed:
            print(f"复制初始目标: {initial_base} -> {target_dir_abs}")
            # Optional delay: time.sleep(0.5)
            shutil.copy2(initial_target_abs, target_dir_abs)
            processed_counter[0] += 1
            # Add the *copied* target to the processing queue
            if target_exe_path_abs not in processed_files and target_exe_path_abs not in files_to_process_queue:
                files_to_process_queue.add(target_exe_path_abs)
                print(f"  添加复制后的目标 '{initial_base}' 到处理队列。")

        # Mark initial basename as handled (present or copied)
        copied_dll_basenames.add(initial_base.lower())

    except PermissionError as e_perm_copy:
        print(f"错误: 处理初始目标 {initial_base} 时发生权限错误: {e_perm_copy}", file=sys.stderr)
        failed_to_copy.add(f"{initial_base} (初始目标权限)")
        return # Stop processing this specific initial target
    except Exception as e_copy:
        print(f"错误: 处理初始目标 {initial_base} 时发生错误: {e_copy}", file=sys.stderr)
        failed_to_copy.add(f"{initial_base} (初始目标复制)")
        return # Stop processing this specific initial target

    # --- Process the shared queue ---
    # Note: This loop might run multiple times if called for multiple initial targets,
    # but `processed_files` prevents redundant work.
    processed_in_this_call = 0 # Track work done *during* this specific call
    while files_to_process_queue:
        # Check if queue has items added by *other* calls first
        if not any(item not in processed_files for item in files_to_process_queue):
            # Optimization: If everything currently in the queue has been processed, break early.
            # This prevents infinite loops if queue logic has issues.
            # However, normally this shouldn't be needed if the logic adding to queue is correct.
            # print("  队列中所有项目均已处理，提前退出循环。") # Debug
            break

        current_file_abs = files_to_process_queue.pop()
        current_file_base = os.path.basename(current_file_abs)
        current_file_dir_abs = os.path.dirname(current_file_abs) # Should be target_dir after first copy

        if current_file_abs in processed_files:
            continue # Already processed its dependencies

        processed_files.add(current_file_abs)
        processed_in_this_call += 1

        print(f"\n[{len(processed_files)}/?] 处理文件: {current_file_base} (位于: {current_file_dir_abs})")

        if not current_file_abs.lower().endswith((".exe", ".dll")):
            print(f"  跳过非 PE 文件: {current_file_base}")
            continue

        dependencies = get_dependencies(current_file_abs, dumpbin_exe)
        if dependencies is None:
            print(f"  无法获取 {current_file_base} 的依赖项，跳过此文件。")
            continue # Skip this file, but continue processing queue

        needed_dlls = filter_dependencies(dependencies, include_vcruntime)
        if not needed_dlls:
            # print(f"  过滤后 {current_file_base} 无需处理的依赖项。") # Less verbose
            continue # No dependencies to find for this file

        # --- Process each needed DLL for the current file ---
        for dll_name in sorted(list(needed_dlls)):
            dll_name_lower = dll_name.lower()
            # print(f"  检查依赖项: {dll_name}") # Less verbose

            target_dll_path_abs = os.path.abspath(os.path.join(target_dir_abs, dll_name))

            # Check if already copied/verified in target dir (by basename)
            if dll_name_lower in copied_dll_basenames:
                # print(f"    基名 '{dll_name_lower}' 已在目标目录中处理过。") # Less verbose
                # Ensure it's added for *its* dependency scanning if not already processed/queued
                if os.path.exists(target_dll_path_abs) and \
                        target_dll_path_abs not in processed_files and \
                        target_dll_path_abs not in files_to_process_queue:
                    # print(f"      -> (重新)添加 {dll_name} 到队列以检查其依赖。") # Less verbose
                    files_to_process_queue.add(target_dll_path_abs)
                continue # Move to the next needed DLL for the current file

            # --- If not already handled, find the source DLL ---
            print(f"    查找源文件: {dll_name}")
            dll_path = None

            # Search Order:
            # 1. Dir of current file (usually target_dir)
            potential_path = os.path.join(current_file_dir_abs, dll_name)
            if os.path.isfile(potential_path):
                dll_path = potential_path
                # print(f"      找到于当前文件目录: {dll_path}") # Less verbose

            # 2. Dir of the *initial* executable for this specific run
            if not dll_path and os.path.normcase(initial_exe_dir_abs) != os.path.normcase(current_file_dir_abs):
                potential_path = os.path.join(initial_exe_dir_abs, dll_name)
                if os.path.isfile(potential_path):
                    dll_path = potential_path
                    # print(f"      找到于初始目标目录: {dll_path}") # Less verbose

            # 3. Recursive search in specified CMake search paths
            if not dll_path and cmake_search_paths_abs:
                # print(f"      在指定搜索路径中递归查找 {dll_name}...") # Less verbose
                dll_path = find_dll_recursively_in_search_paths(dll_name, cmake_search_paths_abs)
                if dll_path:
                    print(f"      递归查找找到于: {os.path.dirname(dll_path)}") # Log dir found in

            # --- Copy the found DLL (if found) ---
            if dll_path:
                try:
                    norm_source_path = os.path.normcase(os.path.abspath(dll_path))
                    norm_target_path = os.path.normcase(target_dll_path_abs)
                    copy_needed = True

                    if norm_source_path == norm_target_path:
                        copy_needed = False
                    elif os.path.exists(target_dll_path_abs):
                        source_mtime = os.stat(dll_path).st_mtime
                        target_mtime = os.stat(target_dll_path_abs).st_mtime
                        if source_mtime <= target_mtime:
                            copy_needed = False
                        # else: Target exists but is older

                    if copy_needed:
                        print(f"    **复制: {dll_name} 从 {os.path.dirname(dll_path)} -> {target_dir_abs}**")
                        shutil.copy2(dll_path, target_dir_abs)
                        processed_counter[0] += 1
                    # else:
                    # print(f"    '{dll_name}' 已在目标目录且最新/相同，跳过复制。") # Less verbose

                    # Regardless of copy, mark basename as handled and add target path to queue
                    copied_dll_basenames.add(dll_name_lower)
                    if target_dll_path_abs not in processed_files and target_dll_path_abs not in files_to_process_queue:
                        # print(f"      -> 添加 {dll_name} 到队列以检查其依赖。") # Less verbose
                        files_to_process_queue.add(target_dll_path_abs)

                except PermissionError as e_perm_dep:
                    print(f"    错误: 复制 {dll_name} 从 {dll_path} 时发生权限错误: {e_perm_dep}", file=sys.stderr)
                    failed_to_copy.add(f"{dll_name} (依赖项权限)")
                except Exception as e_copy_dep:
                    print(f"    错误: 复制 {dll_name} 从 {dll_path} 时出错: {e_copy_dep}", file=sys.stderr)
                    failed_to_copy.add(f"{dll_name} (依赖项复制)")
            else:
                # DLL not found anywhere
                print(f"    **警告: 未在任何位置找到 {dll_name}**")
                not_found_anywhere.add(dll_name) # Add basename to not found list
        # --- End loop for needed_dlls ---
    # --- End while files_to_process_queue ---
    # print(f"  此调用处理了 {processed_in_this_call} 个文件。") # Debug


# --- REFINED Function: Copy Extra Items (Directories) ---
def copy_extra_items(extra_items_list, target_dir_abs, failed_items):
    """Copies entire directory trees specified in extra_items_list to the target directory."""
    if not extra_items_list:
        return

    print("\n--- 开始处理额外复制项 (整个目录) ---")
    # Check Python version for dirs_exist_ok support
    use_dirs_exist_ok = sys.version_info >= (3, 8)
    if not use_dirs_exist_ok:
        print("  注意: Python < 3.8，将使用 '先删除后复制' 的方式处理现有目标目录。")

    for item_path_str in extra_items_list:
        item_path_str = item_path_str.strip()
        if not item_path_str: continue

        abs_item_path = os.path.abspath(item_path_str)
        # Ensure we get the actual directory name, even if input has trailing slash
        item_basename = os.path.basename(os.path.normpath(abs_item_path))

        if not item_basename: # Handles cases like "C:\" or "/" if passed directly
            print(f"  错误: 无法从 '{item_path_str}' 提取有效的目录名，跳过。", file=sys.stderr)
            failed_items.add(f"{item_path_str} (无效源名称)")
            continue

        # The target path *is* the directory *inside* the main target directory
        target_path = os.path.join(target_dir_abs, item_basename)

        print(f"处理目录项: {item_path_str}")
        print(f"  源: {abs_item_path}")
        print(f"  目标: {target_path}")

        if not os.path.isdir(abs_item_path):
            print(f"  错误: 源路径不是一个有效目录，跳过。", file=sys.stderr)
            failed_items.add(f"{item_path_str} (不是目录)")
            continue

        try:
            if use_dirs_exist_ok:
                # Python 3.8+ : Overwrites existing directories/files within the target
                shutil.copytree(abs_item_path, target_path, dirs_exist_ok=True)
                print(f"    成功复制/更新目录树 '{item_basename}' (使用 dirs_exist_ok=True)")
            else:
                # Older Python: Remove target first if it exists
                if os.path.exists(target_path):
                    print(f"    目标 '{target_path}' 已存在，正在删除...")
                    try:
                        # Be careful with shutil.rmtree!
                        shutil.rmtree(target_path)
                        print(f"    旧目标 '{target_path}' 已删除。")
                    except Exception as e_rm:
                        print(f"  错误: 删除现有目标 '{target_path}' 失败: {e_rm}", file=sys.stderr)
                        failed_items.add(f"{item_path_str} (删除旧目标失败)")
                        continue # Skip copying if deletion failed

                # Now copy the tree
                shutil.copytree(abs_item_path, target_path)
                print(f"    成功复制目录树 '{item_basename}' (使用 rmtree/copytree)")

        except PermissionError as e_perm:
            print(f"  错误: 复制目录树 '{item_basename}' 时发生权限错误: {e_perm}", file=sys.stderr)
            failed_items.add(f"{item_path_str} (目录复制权限)")
        except Exception as e:
            print(f"  错误: 复制目录树 '{item_basename}' 时失败: {e}", file=sys.stderr)
            failed_items.add(f"{item_path_str} (目录复制失败)")


# --- Function: Copy Extra Binary Items (DLLs from Dirs) --- (Unchanged from previous correct version)
def copy_extra_bin_items(extra_bin_dirs_list, target_dir_abs, failed_items, copied_basenames):
    """Copies only .dll files from the top level of specified directories to the target directory."""
    if not extra_bin_dirs_list:
        return

    print("\n--- 开始处理额外复制项 (目录中的 DLL) ---")
    for dir_path_str in extra_bin_dirs_list:
        dir_path_str = dir_path_str.strip()
        if not dir_path_str: continue

        abs_dir_path = os.path.abspath(dir_path_str)
        print(f"处理 DLL 目录: {dir_path_str}")
        print(f"  源目录: {abs_dir_path}")

        if not os.path.isdir(abs_dir_path):
            print(f"  错误: 路径不是一个有效目录，跳过。", file=sys.stderr)
            failed_items.add(f"{dir_path_str} (不是目录)")
            continue

        dll_found_count = 0
        dll_copied_count = 0
        try:
            # print(f"  在 '{abs_dir_path}' 中查找 DLL...") # Less verbose
            for item_name in os.listdir(abs_dir_path):
                item_name_lower = item_name.lower()
                if item_name_lower.endswith(".dll"):
                    source_dll_path = os.path.join(abs_dir_path, item_name)
                    if os.path.isfile(source_dll_path): # Ensure it's a file
                        dll_found_count += 1
                        target_dll_path = os.path.join(target_dir_abs, item_name)
                        copy_needed = True
                        try:
                            if os.path.exists(target_dll_path):
                                source_mtime = os.stat(source_dll_path).st_mtime
                                target_mtime = os.stat(target_dll_path).st_mtime
                                if source_mtime <= target_mtime:
                                    copy_needed = False
                                # else: print(f"    '{item_name}' 已存在但较旧，将更新。")

                            if copy_needed:
                                print(f"    **复制 DLL: {item_name} 从 {abs_dir_path} -> {target_dir_abs}**")
                                shutil.copy2(source_dll_path, target_dir_abs)
                                copied_basenames.add(item_name_lower) # Track copied DLLs
                                dll_copied_count += 1

                        except PermissionError as e_perm_dll:
                            print(f"    错误: 复制 DLL '{item_name}' 时发生权限错误: {e_perm_dll}", file=sys.stderr)
                            failed_items.add(f"{item_name} (来自 {dir_path_str}, 权限)")
                        except Exception as e_copy_dll:
                            print(f"    错误: 复制 DLL '{item_name}' 时失败: {e_copy_dll}", file=sys.stderr)
                            failed_items.add(f"{item_name} (来自 {dir_path_str}, 复制)")

            if dll_found_count == 0:
                print(f"    未在 '{abs_dir_path}' 的顶层找到 DLL 文件。")
            else:
                print(f"    找到 {dll_found_count} 个 DLL 文件，复制/更新了 {dll_copied_count} 个。")

        except PermissionError as e_perm_list:
            print(f"  错误: 访问目录 '{abs_dir_path}' 时发生权限错误: {e_perm_list}", file=sys.stderr)
            failed_items.add(f"{dir_path_str} (访问目录权限)")
        except Exception as e_list:
            print(f"  错误: 访问或列出目录 '{abs_dir_path}' 时失败: {e_list}", file=sys.stderr)
            failed_items.add(f"{dir_path_str} (访问目录失败)")


# --- Main Execution Block ---
if __name__ == "__main__":
    print("--- 开始执行依赖项和额外项复制脚本 (读取环境变量) ---")
    start_time = time.time()

    if sys.platform != "win32":
        print("错误: 此脚本仅设计用于 Windows 平台。", file=sys.stderr)
        sys.exit(1)

    # --- Read Environment Variables ---
    dumpbin_path = os.environ.get(ENV_DUMPBIN_PATH)
    executable_paths_str = os.environ.get(ENV_EXECUTABLE_PATHS) # Read semicolon-separated list
    target_dir = os.environ.get(ENV_TARGET_DIR)
    search_paths_str = os.environ.get(ENV_SEARCH_PATHS, "")
    include_vcruntime_str = os.environ.get(ENV_INCLUDE_VCRUNTIME, "0")
    extra_items_str = os.environ.get(ENV_EXTRA_COPY_ITEMS, "") # Semicolon-separated list
    extra_bin_items_str = os.environ.get(ENV_EXTRA_COPY_ITEMS_BIN, "") # Semicolon-separated list

    # --- Validate Required Environment Variables ---
    config_errors = []
    if not dumpbin_path: config_errors.append(f"错误: 环境变量 '{ENV_DUMPBIN_PATH}' 未设置。")
    else:
        dumpbin_path = dumpbin_path.strip('"\' ')
        if not os.path.isfile(dumpbin_path): config_errors.append(f"错误: '{ENV_DUMPBIN_PATH}' ({dumpbin_path}) 不是有效文件。")
        elif not dumpbin_path.lower().endswith("dumpbin.exe"): print(f"警告: '{ENV_DUMPBIN_PATH}' 指向的文件名不是 'dumpbin.exe': {dumpbin_path}", file=sys.stderr)

    if not executable_paths_str: config_errors.append(f"错误: 环境变量 '{ENV_EXECUTABLE_PATHS}' 未设置或为空。")

    if not target_dir: config_errors.append(f"错误: 环境变量 '{ENV_TARGET_DIR}' 未设置。")
    else: target_dir = target_dir.strip('"\' ')

    if config_errors:
        print("-" * 20, file=sys.stderr); [print(e, file=sys.stderr) for e in config_errors]; print("-" * 20, file=sys.stderr)
        print("请确保构建脚本或 IDE 正确设置了所有必需的环境变量。", file=sys.stderr); sys.exit(1)

    # --- Process and Validate Executable Paths List ---
    executable_path_list_raw = [p.strip() for p in executable_paths_str.split(';') if p.strip()]
    executable_paths_valid = []
    if not executable_path_list_raw:
        config_errors.append(f"错误: 环境变量 '{ENV_EXECUTABLE_PATHS}' 解析后为空列表。")
    else:
        for p in executable_path_list_raw:
            p_clean = p.strip('"\' ')
            if not os.path.isfile(p_clean):
                config_errors.append(f"错误: '{ENV_EXECUTABLE_PATHS}' 中的路径不是有效文件: {p_clean}")
            else:
                executable_paths_valid.append(os.path.abspath(p_clean)) # Store absolute path

    if not executable_paths_valid and not config_errors: # If list had items but none were valid
        config_errors.append(f"错误: 环境变量 '{ENV_EXECUTABLE_PATHS}' 未包含任何有效的可执行文件/DLL 路径。")

    # --- Process Optional Environment Variables ---
    search_paths_list_raw = [p.strip() for p in search_paths_str.split(';') if p.strip()]
    search_paths_abs = []
    for p in search_paths_list_raw:
        p_clean = p.strip('"\' ')
        abs_p = os.path.abspath(p_clean)
        if not os.path.isdir(abs_p):
            print(f"警告: 搜索路径 '{p_clean}' ({abs_p}) 无效或不是目录，将忽略。", file=sys.stderr)
        else:
            search_paths_abs.append(abs_p)

    extra_items_list = [p.strip('"\' ') for p in extra_items_str.split(';') if p.strip()]
    extra_bin_items_list = [p.strip('"\' ') for p in extra_bin_items_str.split(';') if p.strip()]
    include_vcruntime_bool = include_vcruntime_str.lower() in ['1', 'true', 'yes']

    # --- Create Target Directory and Check Permissions ---
    target_dir_abs = os.path.abspath(target_dir)
    try:
        os.makedirs(target_dir_abs, exist_ok=True)
        # Basic write permission check
        test_file = os.path.join(target_dir_abs, f".write_test_{int(time.time())}")
        with open(test_file, "w") as f: f.write("test")
        os.remove(test_file)
    except PermissionError:
        config_errors.append(f"错误: 无法写入目标目录 '{target_dir_abs}'。检查权限。")
    except Exception as e_dir:
        config_errors.append(f"错误: 创建或访问目标目录 '{target_dir_abs}' 时出错: {e_dir}")

    # --- Final Configuration Validation ---
    if config_errors:
        print("-" * 20, file=sys.stderr); [print(e, file=sys.stderr) for e in config_errors]; print("-" * 20, file=sys.stderr)
        sys.exit(1)

    # --- Print Configuration ---
    print(f"使用配置:")
    print(f"  Dumpbin: {dumpbin_path}")
    print(f"  分析目标:")
    for exe_path in executable_paths_valid: print(f"    - {exe_path}")
    print(f"  目标目录: {target_dir_abs}")
    print(f"  DLL 搜索路径 (递归): {search_paths_abs if search_paths_abs else '无'}")
    print(f"  包含 VC Runtime DLLs: {include_vcruntime_bool}")
    print(f"  额外复制项 (目录): {extra_items_list if extra_items_list else '无'}")
    print(f"  额外复制项 (目录内 DLL): {extra_bin_items_list if extra_bin_items_list else '无'}")
    print("-" * 20)

    # --- Initialize Shared State ---
    master_processed_files = set() # Files whose dependencies have been checked (abs path)
    master_copied_dll_basenames = set() # Basenames of DLLs/EXEs copied or verified in target
    master_files_to_process_queue = set() # Files waiting to be processed (abs path in target)
    master_not_found_anywhere = set() # Basenames of DLLs that couldn't be found
    master_failed_to_copy = set() # Basenames/Paths of items that failed copy/processing
    master_processed_counter = [0] # Mutable counter for DLLs/EXEs copied/verified

    # --- Execute Core Logic: Dependency Copying ---
    print("\n--- 开始处理依赖项复制 ---")
    initial_targets_processed = 0
    for exe_path_abs in executable_paths_valid:
        initial_targets_processed += 1
        print(f"\n=== 处理初始目标 {initial_targets_processed}/{len(executable_paths_valid)}: {os.path.basename(exe_path_abs)} ===")
        initial_exe_dir_abs = os.path.dirname(exe_path_abs)
        copy_dependencies_recursive(
            exe_path_abs,
            target_dir_abs,
            initial_exe_dir_abs,
            search_paths_abs,
            dumpbin_path,
            include_vcruntime_bool,
            # --- Pass shared state ---
            master_processed_files,
            master_copied_dll_basenames,
            master_files_to_process_queue,
            master_not_found_anywhere,
            master_failed_to_copy,
            master_processed_counter
        )
        # The shared queue is processed within the function call

    # --- Execute Core Logic: Extra Item Copying ---
    # These are processed after all dependency analysis is queued/done
    copy_extra_items(extra_items_list, target_dir_abs, master_failed_to_copy)
    copy_extra_bin_items(extra_bin_items_list, target_dir_abs, master_failed_to_copy, master_copied_dll_basenames)

    # --- Final Summary ---
    print("\n--- 依赖项和额外项复制完成 ---")
    print(f"分析了 {len(executable_paths_valid)} 个初始目标。")
    print(f"处理了 {len(master_processed_files)} 个 PE 文件以查找依赖项。")
    print(f"已复制或验证目标目录中存在 {master_processed_counter[0]} 个依赖项文件 (EXE/DLL)。")
    # Counts for extra items are logged during their respective functions.

    if master_not_found_anywhere:
        print("\n警告: 以下依赖项 DLL 在所有搜索位置均未找到 (程序可能无法运行):", file=sys.stderr)
        for missing in sorted(list(master_not_found_anywhere)): print(f"  - {missing}", file=sys.stderr)

    if master_failed_to_copy:
        print("\n错误: 以下文件或目录在复制/处理过程中失败:", file=sys.stderr)
        for failed in sorted(list(master_failed_to_copy)): print(f"  - {failed}", file=sys.stderr)

    print("\n重要提示:")
    print("- 此脚本查找编译时链接的 DLL。动态加载 (LoadLibrary) 的 DLL 需要手动处理。")
    print("- VC++ Runtime DLLs 默认不复制。建议最终用户安装官方的 Visual C++ Redistributable 包。")
    print(f"- 请确保环境变量 '{ENV_SEARCH_PATHS}' 提供了所有相关的 CMake 构建输出目录和第三方库目录 (用分号分隔)。脚本会递归搜索这些目录。")
    print(f"- '{ENV_EXTRA_COPY_ITEMS}' 用于复制整个目录 (如资源、插件) 到目标目录。")
    print(f"- '{ENV_EXTRA_COPY_ITEMS_BIN}' 用于从指定目录的顶层复制 DLL 文件到目标目录。")

    # --- Final Message ---
    end_time = time.time()
    print(f"\n--- 脚本执行完毕 (耗时: {end_time - start_time:.2f} 秒) ---")

    # Optional: Exit with error code if failures occurred
    if master_failed_to_copy or master_not_found_anywhere:
        # sys.exit(1) # Uncomment to signal failure to build systems
        pass