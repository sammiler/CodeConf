# VSCode 项目配置辅助工具

这是一个通过 Python 脚本自动生成 VSCode 配置文件的工具，旨在为 **Windows**、**Linux** 和 **macOS** 提供跨平台的 C++ 开发支持。工具使用模板和 template.json 文件生成 .vscode 配置文件，集成 Conan 依赖管理，支持 CMake、Ninja 和 Qt 开发。



## 功能简介

- **自动配置**：基于 template.json 和模板文件生成 VSCode 配置文件。
- **跨平台支持**：适配 Windows（MSVC）、Linux（GCC）和 macOS（Clang）。
- **动态字段**：支持 conan_path、exe_name 等自定义路径。
- **构建与调试**：预设调试和发布模式的 CMake 标志。
- **Qt 集成**：支持 Qt Designer 和插件路径配置。

核心配置文件 template.json 定义了操作系统特定的设置（如 cmake_lib、qt_exe）、任务标志（如 debug_flag）、调试配置（如 qt_plugins）和平台细节（如 Ninja 生成器和 MSVC 编译器路径）。

## 使用方法

1. **准备环境**：
   
   - 安装 Python 3.x 和 Conan（可选）。
   - 确保 .vscode/template 中有模板文件，.vscode/py-script 中有脚本。

2. **初始化配置**：
   
   - 运行以下命令生成初始配置文件：
     
     bash
     
     python .vscode/py-script/genconf.py`
     
     该脚本根据 template.json 和模板生成 .vscode 下的 settings.json、tasks.json 等文件。

3. **执行任务**：
   
   - 使用 main.py 控制所有任务（如构建、调试）自动调用：

4. **Conan 集成**（可选）：
   
   - 编辑 conanfile.py 配置依赖，运行：
     
     bash
     
     `python .vscode/py-script/conanfile.py`

5. **打开 VSCode**：
   
   - 在 VSCode 中加载项目，享受自动配置的开发环境。

## Windows 特性

Windows 支持特有的可选字段，留空不会影响运行，例如：

- qt5_natvis：可为空，默认不启用 Natvis 文件。
- qml_path：若未指定 Qt QML 路径，保持默认或为空。
