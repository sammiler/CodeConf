
---

# VS Code 工作区自动化脚本说明

本文件旨在说明 `.vscode/py-script/` 目录下的 Python 脚本的功能以及如何使用它们来自动化常见的项目任务。

## 核心目录结构

- **`.vscode/py-script/`**: 存放所有用于项目自动化的核心 Python 脚本。
- **`.vscode/template/`**: 存放项目的模板文件，例如  `.clang-format`。

---

## 脚本功能介绍

- **`CMakePresetsGenerator.py`**:
  - **功能**: 生成或更新 `CMakePresets.json` 文件。该文件预定义了多种开发环境（如 Windows, Linux, macOS）和构建类型（如 Debug, Release）的 CMake 配置。
  - **使用场景**: 在项目初始化或需要更新构建配置时运行，以确保跨平台和团队成员之间的一致性。

- **`CopyTemplateToRoot.py`**:
  - **功能**: 将 `.vscode/template/` 目录下的所有模板文件（例如 `.clang-format` 等）复制到项目的根目录。
  - **使用场景**: 在项目初始化时，用于快速应用团队统一的代码风格、Git 忽略规则等配置。

- **`GenerateSettings.py`**:
  - **功能**: 在 `.vscode/` 目录下创建或更新 `settings.json` 文件。此文件可以根据项目类型配置 VS Code 的特定行为，例如默认的 CMake 配置、IntelliSense 设置等。
  - **使用场景**: 项目初始化时，用于统一团队成员的 VS Code 开发体验。

- **`GenerateLaunch.py`**:
  - **功能**: 在 `.vscode/` 目录下创建或更新 `launch.json` 文件。此文件生成项目生成目录文件的调试相关配置。
  - **使用场景**: 项目初始化时，用于统一团队成员的 VS Code 开发体验。

---

## 自动化任务指令

这些任务旨在简化项目的生命周期管理。您可以指示 AI 助手順序执行这些任务中的步骤。

### 任务一：初始化新项目

**执行流程**:
1.  **检查 `CMakeLists.txt`**:
    - 如果项目根目录下**不存在** `CMakeLists.txt` 文件，则首先创建一个基础的 "Hello World" 项目结构。
    - 如果文件已存在，则跳过此步。

2.  **生成 CMake 预设**:
    - 执行 **`CMakePresetsGenerator.py`** 脚本，在项目根目录生成 `CMakePresets.json` 文件，用于配置构建环境。

3.  **复制项目模板**:
    - 执行 **`CopyTemplateToRoot.py`** 脚本，将所有必要的模板文件（`.clang-format`）复制到项目根目录。

4.  **生成 VS Code 设置**:
    - 执行 **`GenerateSettings.py`** 脚本，创建或更新 `.vscode/settings.json` 文件以优化当前项目的开发体验。

### 任务二：生成VSCode调试配置文件

**执行流程**:
1.  **生成Launch.json文件**:
    - 执行 **`GenerateLaunch.py`** 脚本，在 `.vscode/` 目录下生成或更新 `launch.json` 文件，用于配置VS Code的调试功能。
    
---
