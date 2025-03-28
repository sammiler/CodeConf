from conan import ConanFile
from conan.tools.files import copy
import os
class PortAudioConan(ConanFile):
    name = "portaudio"
    version = "19.8.0"
    settings = "os", "compiler", "build_type", "arch"
    exports_sources = "install_dir/*"
    package_type = "library"
    options = {"shared": [True, False]}  # 添加 shared 选项
    default_options = {"shared": True}   # 默认动态库

    def package(self):
        copy(self, "*.h", src=os.path.join(self.source_folder, "install_dir/include"), dst=os.path.join(self.package_folder, "include"))
        if self.options.shared:  # 根据 shared 选项选择动态库
            if self.settings.build_type == "Debug":
                copy(self, "portaudio.lib", src=os.path.join(self.source_folder, "install_dir/debug/lib"), dst=os.path.join(self.package_folder, "lib"))
                copy(self, "portaudio.dll", src=os.path.join(self.source_folder, "install_dir/debug/bin"), dst=os.path.join(self.package_folder, "bin"))
            elif self.settings.build_type == "Release":
                copy(self, "portaudio.lib", src=os.path.join(self.source_folder, "install_dir/release/lib"), dst=os.path.join(self.package_folder, "lib"))
                copy(self, "portaudio.dll", src=os.path.join(self.source_folder, "install_dir/release/bin"), dst=os.path.join(self.package_folder, "bin"))
        else:  # 静态库
            if self.settings.build_type == "Debug":
                copy(self, "portaudio.lib", src=os.path.join(self.source_folder, "install_dir/debug/lib"), dst=os.path.join(self.package_folder, "lib"))
            elif self.settings.build_type == "Release":
                copy(self, "portaudio.lib", src=os.path.join(self.source_folder, "install_dir/release/lib"), dst=os.path.join(self.package_folder, "lib"))

    def package_info(self):
        self.cpp_info.libs = ["portaudio"]
        if self.options.shared:
            self.cpp_info.bindirs = ["bin"]  # 动态库路径
        self.cpp_info.libdirs = ["lib"]