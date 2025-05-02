import subprocess
import os
import sys
from pathlib import Path
import shutil # 用于清理目录

# --- 配置 ---

# 1. 从环境变量获取项目根目录
project_dir_env = os.environ.get('PROJECT_DIR')
if not project_dir_env:
    print("错误：未设置 PROJECT_DIR 环境变量。请设置该变量指向你的项目根目录。")
    sys.exit(1)

# 将环境变量转换为 Path 对象，并确保路径是绝对和规范化的
PROJECT_ROOT = Path(project_dir_env).resolve()
if not PROJECT_ROOT.is_dir():
    print(f"错误：PROJECT_DIR 指向的路径 '{PROJECT_ROOT}' 不是一个有效的目录。")
    sys.exit(1)

# 2. 定义要使用的 CMake Presets 名称 (根据你的 CMakePresets.json 文件)
#    这里我们硬编码使用 Linux Debug 配置，你可以根据需要修改
CONFIGURE_PRESET_NAME = "linux-release"  # 用于配置步骤的 Preset
BUILD_PRESET_NAME = "linux-release-build"      # 用于构建步骤的 Preset

# 3. 定义构建和安装目录 (相对于项目根目录)
#    你的 Preset "linux-debug" 定义了 binaryDir 为 "${sourceDir}/build"
BUILD_DIR_NAME = "build"
INSTALL_DIR_NAME = "installed_dir/release" # 你期望的安装目录名称

BUILD_DIR = PROJECT_ROOT / BUILD_DIR_NAME
INSTALL_DIR = PROJECT_ROOT / INSTALL_DIR_NAME

# 4. 构建选项
CLEAN_BEFORE_BUILD = True # 设置为 True 以在开始前删除旧的 build 和 installed_dir 目录
RUN_CONFIGURE = True      # 是否执行 CMake 配置步骤
RUN_BUILD = True          # 是否执行 CMake 构建步骤
RUN_INSTALL = True        # 是否执行 CMake 安装步骤
# 注意：并行任务数 'jobs' 由你的 Build Preset ("linux-debug-build" 中已定义为 8) 控制，无需在此处单独设置

# --- 辅助函数：运行外部命令 ---

def run_command(cmd_list, working_dir=None, error_msg="命令执行失败"):
    """运行一个命令并检查错误，打印输出。"""
    # 将列表中的所有元素（包括 Path 对象）转换为字符串
    cmd_str_list = [str(item) for item in cmd_list]
    cmd_display_str = ' '.join(cmd_str_list)
    print(f"\n--- 正在执行 (工作目录: {working_dir or '.'}): {cmd_display_str}", flush=True)
    try:
        # 使用 text=True 进行自动编码/解码, capture_output 获取输出
        result = subprocess.run(cmd_str_list, cwd=working_dir, check=True, text=True, capture_output=True, encoding='utf-8') # 指定utf-8编码
        if result.stdout:
            print("--- STDOUT ---")
            print(result.stdout.strip())
        if result.stderr:
            # CMake 配置/构建时常在 stderr 输出非错误信息
            print("--- STDERR ---")
            print(result.stderr.strip())
        print(f"--- 命令成功: {cmd_display_str}", flush=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n!!! {error_msg} !!!")
        print(f"命令: {cmd_display_str}")
        print(f"返回码: {e.returncode}")
        if e.stdout:
            print("--- 失败 STDOUT ---")
            print(e.stdout.strip())
        if e.stderr:
            print("--- 失败 STDERR ---")
            print(e.stderr.strip())
        return False
    except FileNotFoundError:
        print(f"\n!!! 错误: 命令 '{cmd_str_list[0]}' 未找到 (是否已安装并在 PATH 中?) !!!")
        print(f"命令: {cmd_display_str}")
        return False
    except Exception as e:
        print(f"\n!!! 执行命令时发生意外错误 !!!")
        print(f"命令: {cmd_display_str}")
        print(f"错误: {e}")
        return False

# --- 主执行逻辑 ---

def main():
    print("="*30)
    print(" CMake 构建与安装脚本")
    print("="*30)
    print(f"项目根目录 (来自 PROJECT_DIR): {PROJECT_ROOT}")
    print(f"使用的配置 Preset: {CONFIGURE_PRESET_NAME}")
    print(f"使用的构建 Preset: {BUILD_PRESET_NAME}")
    print(f"构建目录 (由 Preset 定义): {BUILD_DIR}")
    print(f"目标安装目录: {INSTALL_DIR}")
    print("-"*30)

    # 1. 可选：清理旧目录
    if CLEAN_BEFORE_BUILD:
        print("正在清理旧的构建和安装目录...")
        if BUILD_DIR.exists():
            try:
                shutil.rmtree(BUILD_DIR)
                print(f"已删除: {BUILD_DIR}")
            except OSError as e:
                print(f"错误：删除构建目录 {BUILD_DIR} 时出错: {e}")
                sys.exit(1)
        if INSTALL_DIR.exists():
            try:
                shutil.rmtree(INSTALL_DIR)
                print(f"已删除: {INSTALL_DIR}")
            except OSError as e:
                print(f"错误：删除安装目录 {INSTALL_DIR} 时出错: {e}")
                sys.exit(1)

    # 2. 配置步骤 (cmake --preset <name> -DCMAKE_INSTALL_PREFIX=...)
    #    使用 --preset 时，CMake 会自动处理源目录和构建目录（根据 preset 定义）
    #    我们需要在这里覆盖或添加 CMAKE_INSTALL_PREFIX
    if RUN_CONFIGURE:
        configure_cmd = [
            "cmake",
            "--preset", CONFIGURE_PRESET_NAME,
            # 关键：设置安装路径，会覆盖 preset 中可能存在的同名变量
            f"-DCMAKE_INSTALL_PREFIX={INSTALL_DIR}",
        ]
        # CMake preset 命令通常需要在项目根目录执行
        if not run_command(configure_cmd, working_dir=PROJECT_ROOT, error_msg="CMake 配置失败"):
            sys.exit(1)

    # 3. 构建步骤 (cmake --build --preset <name>)
    #    使用 --build --preset 时，CMake 会使用 preset 中定义的构建目录和 jobs 数量
    if RUN_BUILD:
        build_cmd = [
            "cmake",
            "--build",
            "--preset", BUILD_PRESET_NAME,
        ]
        # CMake preset 命令通常需要在项目根目录执行
        if not run_command(build_cmd, working_dir=PROJECT_ROOT, error_msg="CMake 构建失败"):
            sys.exit(1)

    # 4. 安装步骤 (cmake --install <build-dir>)
    #    这个命令会使用在配置步骤中通过 CMAKE_INSTALL_PREFIX 设置的安装路径
    if RUN_INSTALL:
        # 确保构建目录存在才能执行安装
        if not BUILD_DIR.is_dir():
            print(f"错误：构建目录 {BUILD_DIR} 不存在，无法执行安装。请先运行配置和构建步骤。")
            sys.exit(1)

        install_cmd = [
            "cmake",
            "--install", str(BUILD_DIR), # 需要显式指定构建目录
            # '--config' 通常不是必须的，因为安装通常依赖于配置时设置的类型，
            # 但如果 install() 命令中有特定于配置的逻辑，可以加上：
            # '--config', 'Debug' # 或者从 preset 中获取 CMAKE_BUILD_TYPE
        ]
        # 安装命令也建议在项目根目录执行，尽管它主要操作构建目录
        if not run_command(install_cmd, working_dir=PROJECT_ROOT, error_msg="CMake 安装失败"):
            sys.exit(1)

    print("\n" + "="*30)
    print(" 脚本执行成功！")
    print(f" 构建产物位于: {BUILD_DIR}")
    print(f" 安装的文件位于: {INSTALL_DIR}")
    print("="*30)

if __name__ == "__main__":
    main()