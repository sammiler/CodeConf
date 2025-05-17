import os
from conan import ConanFile
from conan.tools.cmake import CMake, cmake_layout
from conan.tools.files  import patch
from conan.tools.cmake import CMakeToolchain, CMakeDeps
from conan.tools.env import VirtualBuildEnv
from conan.tools.env import VirtualRunEnv
from pathlib import Path
import json
import os
import platform
class MyProjectConan(ConanFile):
    name = "myproject"
    version = "0.1"
    settings = "os", "compiler", "build_type", "arch"

    def layout(self):
        generators = "CMakeDeps", "CMakeToolchain"
        cmake_layout(self,generators,"../../","build")  # 使用标准的 cmake_layout 函数
    def requirements(self):
        self.requires("ffmpeg/6.1")
        self.requires("openimageio/2.5.18.0")
        self.requires("imath/3.1.9")
        self.requires("opencolorio/2.3.1")
        self.requires("portaudio/19.8.0")
        self.requires("openexr/3.2.3")
        self.requires("libdeflate/1.19")
        # self.requires("minizip-ng/4.0.3")  # 使用合适的版本 
        self.requires("qt/5.15.16")

    def configure(self):
        self.output.info(f"configure : {self.source_folder}")
        self.options["*"].shared = True
        self.options["qt"].gui = True
        self.options["qt"].openssl = True
        self.options["qt"].widgets = True
        self.options["qt"].with_pq = True
        self.options["qt"].with_md4c = True
        self.options["qt"].with_odbc = True
        self.options["qt"].with_zstd = True
        self.options["qt"].with_pcre2 = True
        self.options["qt"].with_libpng = True
        self.options["qt"].with_sqlite3 = True
        self.options["qt"].with_freetype = True
        self.options["qt"].with_doubleconversion = True
        self.options["qt"].qttools = True       # 启用 Qt Tools
        self.options["qt"].qtdeclarative = True # 启用 QML 支持
        self.options["qt"].qtmultimedia = True
        self.options["qt"].qtquickcontrols2 = True
        self.options["qt"].qtxmlpatterns = True
        self.options["qt"].qtnetwork = True
        self.options["minizip-ng"].shared = False  # 强制静态库


    def generate(self):
        
        tc = CMakeToolchain(self)
        root_dir = Path(__file__).resolve().parents[2]
        # 构建 template.json 的路径（从根目录到 .vscode/template/template.json）
        template_path = root_dir / '.vscode' / 'template' / 'template.json'
        # 检查文件是否存在
        if not template_path.exists():
            raise FileNotFoundError(f"无法找到文件: {template_path}")
                
                # 读取和解析 JSON 文件
        with open(template_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
        # 获取 "platform" 部分
        platform = data['platform']
        compiler = platform['compiler']
        tc.generator = platform['generator']
        tc.cache_variables["CMAKE_CXX_STANDARD"] = compiler['CMAKE_CXX_STANDARD']
        tc.cache_variables["CMAKE_C_COMPILER"] = compiler['CMAKE_C_COMPILER']
        tc.cache_variables["CMAKE_CXX_COMPILER"] = compiler['CMAKE_CXX_COMPILER']
        tc.generate()

        deps = CMakeDeps(self)

        deps.generate()

        # 使用 VirtualRunEnv 设置运行时环境
        env = VirtualRunEnv(self)
        env_vars = env.environment()

        # 你的所有路径
        custom_paths = platform['envPath']
        
        # 遍历并追加所有路径到 PATH
        for path in custom_paths:
            env_vars.prepend_path("PATH", path)  # 使用 append_path 追加到 PATH

        # 生成环境脚本
        env.generate()