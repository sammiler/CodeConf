import json
import os
from pathlib import Path
import re
import shutil
import sys
import subprocess
import platform
import argparse
import threading

class BaseTask:
    """基类，包含公共方法和属性"""
    def __init__(self):
        self.system = platform.system()
        root_dir = Path(__file__).resolve().parents[2]
        # 构建 template.json 的路径（从根目录到 .vscode/template/template.json）
        template_path = root_dir / '.vscode' / 'template' / 'template.json'
        # 检查文件是否存在
        if not template_path.exists():
            raise FileNotFoundError(f"无法找到文件: {template_path}")
                
                # 读取和解析 JSON 文件
        with open(template_path, 'r', encoding='utf-8') as file:
            self.data = json.load(file)
        # 获取 "platform" 部分
        self.platformdata = self.data['platform']
        self.compiler = self.platformdata['compiler']
        if self.system == "Windows":
            self.shell_path = self.platformdata['shell_path']
        elif self.platformdata['shell_path'] == "":
            self.shell_path = "/bin/bash"
        else:
            self.shell_path = self.platformdata['shell_path']
        #不需要的可以为空
        self.compiler_path = self.compiler['COMPILER_PATH']
        self.linker_path = self.compiler['LINK_PATH']
        self.rc_compiler = self.compiler['RC_COMPILER']
        self.mt = self.compiler['MT']
        self.toolChain = self.platformdata['toolchain'] + "/scripts/buildsystems/vcpkg.cmake"
        self.mc_compiler = self.compiler['MC_COMPILER']
        self.triplet = self.platformdata['triplet']
        if self.system == "Windows" and not os.path.exists(self.shell_path):
            raise FileNotFoundError("Unix Like Bash not found. Please adjust shell_path.")
        elif self.system in ("Linux", "Darwin") and not os.path.exists(self.shell_path):
            raise FileNotFoundError("Bash not found. Please fill the right path in template.json.")

# ANSI 转义码着色函数
    def color_line(self,line):
        RED = "\033[91m"
        YELLOW = "\033[93m"
        RESET = "\033[0m"
        # 根据 MSVC 输出格式，可根据需要调整正则匹配
        if re.search(r'\berror\b', line, re.IGNORECASE):
            return RED + line + RESET
        elif re.search(r'\bwarning\b', line, re.IGNORECASE):
            return YELLOW + line + RESET
        return line
    

    def stream_output(self,stream, color_func):
        for line in iter(stream.readline, ""):
            sys.stdout.write(color_func(line))
        stream.close()
    def run_command_with_color(self,cmd, env, cwd):
        """执行命令，实时着色输出"""
        process = subprocess.Popen(
            cmd,
            env=env,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            encoding='utf-8',    # 强制使用 UTF-8 编码
            errors='replace',  
            bufsize=1,
            shell=True
        )
        t1 = threading.Thread(target=self.stream_output, args=(process.stdout, self.color_line))
        t2 = threading.Thread(target=self.stream_output, args=(process.stderr, self.color_line))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        return process.wait()
        

    def setup_windows_env(self, env):
        """设置 Windows 特定的环境变量"""
        env["MSYS_NO_PATHCONV"] = "1"
        additional_path = self.platformdata['envPath']
        combined_path = ';'.join(additional_path)
        if self.compiler['NAME'] == "gcc" or self.compiler['NAME'] == "g++" or self.system != "Windows":
            env["PATH"] = f"{combined_path};{env['PATH']}"
            return
        msvc_path = self.compiler['MSVC_PATH']
        windows_sdk_path = self.compiler['WINDOWS_SDK_PATH']
        windows_sdk_version = self.compiler['WINDOWS_SDK_VERSION']

        if not os.path.exists(msvc_path):
            raise FileNotFoundError(f"MSVC path not found: {msvc_path}")
        if not os.path.exists(windows_sdk_path):
            raise FileNotFoundError(f"Windows SDK path not found: {windows_sdk_path}")
        env["PATH"] = f"{combined_path};{msvc_path}/bin/Hostx64/x64;{env['PATH']}"
        env["INCLUDE"] = f"{msvc_path}/include;{windows_sdk_path}/Include/{windows_sdk_version}/ucrt;{windows_sdk_path}/Include/{windows_sdk_version}/um;{windows_sdk_path}/Include/{windows_sdk_version}/shared;"
        env["LIB"] = f"{msvc_path}/lib/x64;{windows_sdk_path}/Lib/{windows_sdk_version}/ucrt/x64;{windows_sdk_path}/Lib/{windows_sdk_version}/um/x64;"
        


class TerminalLauncher(BaseTask):
    """打开终端并设置环境变量"""
    def launch(self, profile):
        """根据参数打开终端并设置环境"""
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
        os.environ['PYTHONIOENCODING'] = 'utf-8'

        env = self.get_conanrun_env() if profile == "full" else os.environ.copy()
        env["LC_ALL"] = "en_US.UTF-8"
        env["LANG"] = "en_US.UTF-8"
        if self.system == "Windows":
            self.setup_windows_env(env)


        cmd = [self.shell_path, "-i"]
        process = subprocess.Popen(cmd, env=env, shell=True)
        process.wait()

class CMakeConfigurer(BaseTask):
    """配置 CMake 环境并运行 cmake 命令"""
    def configure(self, build_type, cmake_flags):
        """设置环境变量并运行 cmake"""
        env = os.environ.copy()
        if self.system == "Windows":
            print("Windows")
            self.setup_windows_env(env)
        elif self.system in ("Linux", "Darwin"):
            env["PATH"] = f"/usr/local/bin:/opt/cmake/bin:{env['PATH']}"

        env["LC_ALL"] = "en_US.UTF-8"
        env["LANG"] = "en_US.UTF-8"
        root_dir = os.getcwd()
        runtime_output_dir = os.path.join(root_dir, "build", "bin").replace("\\", "/")
        library_output_dir = os.path.join(root_dir, "build", "lib").replace("\\", "/")
        archive_output_dir = os.path.join(root_dir, "build", "lib").replace("\\", "/")
        install_prefix = os.path.join(root_dir, "install_dir").replace("\\", "/")
        toolchain_file = self.toolChain
        cmake_cmd = []
        if  os.path.exists(toolchain_file):
            toolchain_file = toolchain_file.replace("\\", "/")
            cmake_cmd = [
            "cmake",
            "-S", ".",
            "-B", "build",
            "-G", "Ninja",
            "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
            "-DCMAKE_POLICY_DEFAULT_CMP0091=NEW",
            f"-DCMAKE_CXX_COMPILER={self.compiler_path}",
            f"-DCMAKE_C_COMPILER={self.compiler_path}",
            f"-DCMAKE_LINKER={self.linker_path}",
            f"-DCMAKE_RC_COMPILER={self.rc_compiler}",
            f"-DCMAKE_MT={self.mt}",
            f"-DCMAKE_MC_COMPILER={self.mc_compiler}",
            f"-DCMAKE_BUILD_TYPE={build_type}",
            f"-DCMAKE_TOOLCHAIN_FILE={toolchain_file}",
            f"-DVCPKG_TARGET_TRIPLET={self.triplet}",
            cmake_flags,
            f"-DCMAKE_RUNTIME_OUTPUT_DIRECTORY={runtime_output_dir}",
            f"-DCMAKE_LIBRARY_OUTPUT_DIRECTORY={library_output_dir}",
            f"-DCMAKE_ARCHIVE_OUTPUT_DIRECTORY={archive_output_dir}",
            f"-DCMAKE_INSTALL_PREFIX={install_prefix}"
            ]
        else:
            cmake_cmd = [
            "cmake",
            "-S", ".",
            "-B", "build",
            "-G", "Ninja",
            "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
            "-DCMAKE_POLICY_DEFAULT_CMP0091=NEW",
            f"-DCMAKE_BUILD_TYPE={build_type}",
            f"-DCMAKE_CXX_COMPILER={self.compiler_path}",
            f"-DCMAKE_C_COMPILER={self.compiler_path}",
            f"-DCMAKE_LINKER={self.linker_path}",
            f"-DCMAKE_RC_COMPILER={self.rc_compiler}",
            f"-DCMAKE_MT={self.mt}",
            f"-DCMAKE_MC_COMPILER={self.mc_compiler}",
            cmake_flags,
            f"-DCMAKE_RUNTIME_OUTPUT_DIRECTORY={runtime_output_dir}",
            f"-DCMAKE_LIBRARY_OUTPUT_DIRECTORY={library_output_dir}",
            f"-DCMAKE_ARCHIVE_OUTPUT_DIRECTORY={archive_output_dir}",
            f"-DCMAKE_INSTALL_PREFIX={install_prefix}"
            ]
        cmake_cmd_str = " ".join(f'"{arg}"' if " " in arg or "=" in arg else arg for arg in cmake_cmd)
        print(f"CMake command: {cmake_cmd_str}")

        cmd = [self.shell_path, "-c", cmake_cmd_str]
        retcode =  self.run_command_with_color(cmd,env,root_dir)
        if retcode != 0:
            print(f"Configured failed with exit code: {retcode}")
        else:
            print("Configure finished successfully.")

class CMakeBuilder(BaseTask):
    """执行 CMake 构建（ninja）"""
    def build(self):
        """设置环境变量并运行 ninja 构建"""
        env = os.environ.copy()
        if self.system == "Windows":
            self.setup_windows_env(env)
        elif self.system in ("Linux", "Darwin"):
            env["PATH"] = f"/usr/local/bin:/opt/cmake/bin:{env['PATH']}"

        env["LC_ALL"] = "en_US.UTF-8"
        env["LANG"] = "en_US.UTF-8"

        root_dir = os.getcwd()
        build_dir = os.path.join(root_dir, "build").replace("\\", "/")

        ninja_cmd = "ninja -C " + build_dir
        print(f"Ninja command: {ninja_cmd}")

        cmd = [self.shell_path, "-c", ninja_cmd]
        retcode = self.run_command_with_color(cmd, env, root_dir)
        if retcode != 0:
            print(f"Build failed with exit code: {retcode}")
        else:
            print("Build finished successfully.")


    
class CMakeInstaller(BaseTask):
    """执行 CMake 安装（ninja install）"""
    def install(self):
        """设置环境变量并运行 ninja install"""
        env = os.environ.copy()

        if self.system == "Windows":
            self.setup_windows_env(env)
        env["LC_ALL"] = "en_US.UTF-8"
        env["LANG"] = "en_US.UTF-8"

        root_dir = os.getcwd()
        build_dir = os.path.join(root_dir, "build").replace("\\", "/")

        ninja_cmd = "ninja -C " + build_dir + " install"
        print(f"Ninja install command: {ninja_cmd}")

        cmd = [self.shell_path, "-c", ninja_cmd]
        process = subprocess.Popen(cmd, env=env, cwd=root_dir, shell=True)
        process.wait()

class CMakeCleaner(BaseTask):
    """执行 CMake 清理（ninja clean）"""
    def clean(self):
        """设置环境变量并运行 ninja clean"""
        env = os.environ.copy()

        if self.system == "Windows":
            self.setup_windows_env(env)
        env["LC_ALL"] = "en_US.UTF-8"
        env["LANG"] = "en_US.UTF-8"

        root_dir = os.getcwd()
        build_dir = os.path.join(root_dir, "build").replace("\\", "/")

        ninja_cmd = "ninja -C " + build_dir + " -t clean"
        print(f"Ninja clean command: {ninja_cmd}")

        cmd = [self.shell_path, "-c", ninja_cmd]
        process = subprocess.Popen(cmd, env=env, cwd=root_dir, shell=True)
        process.wait()


class CopyDllTask(BaseTask):
    """负责复制动态链接库文件的任务类"""
    def __init__(self):
        super().__init__()
        # 定义源目录和目标目录
        self.source_dir = Path(__file__).resolve().parents[2]  # 回到根目录
        print(self.source_dir)
        self.target_dir = self.source_dir / "build" / "bin" / "Debug"
        
        # 根据操作系统设置文件扩展名
        self.lib_extension = {
            "Windows": ".dll",
            "Linux": ".so",
            "Darwin": ".dylib"
        }.get(self.system, ".dll")  # 默认使用 .dll 如果系统未识别
        
    def ensure_target_dir(self):
        """确保目标目录存在"""
        try:
            self.target_dir.mkdir(parents=True, exist_ok=True)
            print(f"目标目录已准备: {self.target_dir}")
        except Exception as e:
            print(f"创建目标目录失败: {e}")
            raise

    def find_lib_files(self, directory):
        """递归查找指定类型的动态链接库文件"""
        lib_files = []
        try:
            for entry in directory.iterdir():
                if entry.is_dir():
                    # 递归处理子目录
                    lib_files.extend(self.find_lib_files(entry))
                elif (entry.is_file() and 
                      entry.suffix.lower() == self.lib_extension):
                    # 添加匹配的动态链接库文件
                    lib_files.append(entry)
            return lib_files
        except Exception as e:
            print(f"读取目录 {directory} 时出错: {e}")
            return lib_files

    def copy_lib_files(self):
        """复制动态链接库文件到目标目录"""
        try:
            # 获取所有匹配的动态链接库文件
            lib_files = self.find_lib_files(self.source_dir)

            if not lib_files:
                print(f"未找到任何 {self.lib_extension} 文件")
                return

            # 复制每个文件
            for source_path in lib_files:
                target_path = self.target_dir / source_path.name
                shutil.copy2(source_path, target_path)
                print(f"已复制: {source_path} -> {target_path}")

            print(f"完成！共复制 {len(lib_files)} 个 {self.lib_extension} 文件")
        except Exception as e:
            print(f"复制 {self.lib_extension} 文件时出错: {e}")
            raise

    def execute(self):
        """执行任务的主方法"""
        print(f"开始复制 {self.lib_extension} 文件...")
        print(f"源目录: {self.source_dir}")
        print(f"目标目录: {self.target_dir}")
        
        self.ensure_target_dir()
        self.copy_lib_files()


class GenerateQrcTask(BaseTask):
    """生成 Qt 资源文件 (.qrc) 和代码片段的任务类"""
    def __init__(self):
        super().__init__()
        self.root_dir = Path(__file__).resolve().parents[2]  # 从 .vscode/py-script 回到根目录
        
    def is_qt_project(self):
        """检查是否为 Qt 项目"""
        cmake_path = self.root_dir / "CMakeLists.txt"
        try:
            with open(cmake_path, 'r', encoding='utf-8') as f:
                content = f.read()
                if "find_package(Qt" not in content:
                    print("不是Qt项目，未找到find_package(Qt)")
                    return False
            return True
        except (FileNotFoundError, IOError):
            print("未找到CMakeLists.txt或读取失败")
            return False

    def load_qrc_config(self):
        """加载或创建 qrc-snippets.json 配置文件"""
        util_dir = self.root_dir / ".vscode" / "util"
        qrc_json_path = util_dir / "qrc-snippets.json"
        
        default_qrc = {
            "run": True,
            "ignore": ["h", "cpp", "c", "hpp", "mm", "qml", "js", "ui", "json", "sh", "webp", "txt", ".qrc"],
            "ignoreName": ["忽略的文件名1", "忽略的文件名2"],
            "resources": [
                {"path": "是相对于根目录的路径1", "prefix": "/"},
                {"path": "是相对于根目录的路径2", "prefix": "/"}
            ]
        }
        if os.path.exists(qrc_json_path):
            with open(qrc_json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            print("即将创建默认配置文件")
            util_dir.mkdir(parents=True, exist_ok=True)
            with open(qrc_json_path, 'w', encoding='utf-8') as f:
                json.dump(default_qrc, f, indent=2, ensure_ascii=False)
            exit(0)

    def get_files_recursively(self, directory, ignore_exts, ignore_names):
        """递归获取目录中的文件，排除忽略的扩展名和文件名"""
        results = []
        try:
            for entry in directory.iterdir():
                if entry.is_dir():
                    results.extend(self.get_files_recursively(entry, ignore_exts, ignore_names))
                else:
                    relative_path = entry.relative_to(self.root_dir).as_posix()  # 跨平台路径，使用 /
                    ext = entry.suffix[1:] if entry.suffix else ""
                    if ext not in ignore_exts and entry.name not in ignore_names:
                        results.append(relative_path)
        except Exception as e:
            print(f"读取目录 {directory} 时出错: {e}")
        return results

    def generate_qrc_and_snippets(self):
        """生成 .qrc 文件和代码片段"""
        qrc_config = self.load_qrc_config()
        
        if not qrc_config.get("run", False):
            print("run属性为false，脚本退出")
            return

        new_snippets = {}
        for resource in qrc_config["resources"]:
            source_dir = self.root_dir / resource["path"]
            files = self.get_files_recursively(source_dir, qrc_config["ignore"], qrc_config["ignoreName"])
            
            xml_content = "<RCC>\n"
            xml_content += f'    <qresource prefix="{resource["prefix"]}">\n'
            
            for file in files:
                relative_path = Path(file).relative_to(resource["path"]).as_posix()
                xml_content += f"        <file>{relative_path}</file>\n"

                # 生成资源路径
                resource_path = f'":/{relative_path}"' if resource["prefix"] == "/" else f'":{resource["prefix"]}/{relative_path}"'
                file_name = Path(relative_path).name
                snippet_name = f"qrc_{relative_path.replace('/', '_')}"
                new_snippets[snippet_name] = {
                    "prefix": file_name,
                    "body": [resource_path],
                    "description": f"Qt resource path for {relative_path}",
                    "scope": "cpp,qml"
                }
            
            xml_content += "    </qresource>\n"
            xml_content += "</RCC>\n"

            output_path = source_dir / "resources.qrc"
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(xml_content)
            print(f"已生成: {output_path}")

        # 更新代码片段文件
        snippets_dir = self.root_dir / ".vscode"
        snippets_path = snippets_dir / "qrc.code-snippets"
        existing_snippets = {}
        
        try:
            with open(snippets_path, 'r', encoding='utf-8') as f:
                existing_snippets = json.load(f)
        except FileNotFoundError:
            print("未找到现有snippets文件，将创建新的")

        updated_snippets = {**existing_snippets, **new_snippets}
        snippets_dir.mkdir(parents=True, exist_ok=True)
        with open(snippets_path, 'w', encoding='utf-8') as f:
            json.dump(updated_snippets, f, indent=2, ensure_ascii=False)
        print(f"已更新代码片段: {snippets_path}")

    def execute(self):
        """执行任务的主方法"""
        if not self.is_qt_project():
            return
        self.generate_qrc_and_snippets()

def main():
    parser = argparse.ArgumentParser(description="Terminal Manager for Multiple Platforms")
    parser.add_argument("--task", choices=["launch-terminal", "cmake-configure", "cmake-build", "cmake-install", "cmake-clean","copy-dll","generate-qrc"], required=True, help="Task to execute")
    parser.add_argument("--param", help="Parameter for launch-terminal")
    parser.add_argument("--build-type", default="Debug", help="Build type for cmake-configure")
    parser.add_argument(
        "--cmake-flags",
        default='-DCMAKE_CXX_FLAGS="/EHsc /W3 /MP6 /Zi /FS /MDd /D_ITERATOR_DEBUG_LEVEL=2" -DCMAKE_C_FLAGS="/EHsc /W3 /MP6 /Zi /FS /MDd /D_ITERATOR_DEBUG_LEVEL=2"',
        help="CMake flags"
    )

    args = parser.parse_args()

    if args.task == "launch-terminal":
        if not args.param:
            raise ValueError("launch-terminal requires --param")
        launcher = TerminalLauncher()
        launcher.launch(args.param)
    elif args.task == "cmake-configure":
        configurer = CMakeConfigurer()
        configurer.configure(args.build_type, args.cmake_flags)
    elif args.task == "cmake-build":
        builder = CMakeBuilder()
        builder.build()
    elif args.task == "cmake-install":
        installer = CMakeInstaller()
        installer.install()
    elif args.task == "cmake-clean":
        cleaner = CMakeCleaner()
        cleaner.clean()
    elif args.task == "copy-dll":
        copy_task = CopyDllTask()
        copy_task.execute()
    elif args.task == "generate-qrc":
        generate_arc = GenerateQrcTask()
        generate_arc.execute()

if __name__ == "__main__":
    main()