import json
import os
import shutil
import platform
import re
from pathlib import Path

class ProjectRootFinder:
    def find_root(self, start_path: Path) -> Path:
        current = start_path.resolve()
        cmake_lists = ["CMakeLists.txt", "cmakelists.txt"]
        while current != current.parent:
            for name in cmake_lists:
                if (current / name).exists():
                    return current
            current = current.parent
        raise FileNotFoundError("未找到CMakeLists.txt，确认是否在CMake项目中")

class CMakePresetsGenerator:
    def __init__(self, template_dir: Path):
        self.template_dir = template_dir
        self.root_finder = ProjectRootFinder()

    def _get_path_separator(self, os_name: str) -> str:
        return ";" if os_name == "Windows" else ":"

    def _normalize_path(self, path: str, os_name: str) -> str:
        path = path.replace("/", "\\") if os_name == "Windows" else path.replace("\\", "/")
        return path.replace("\\", "\\\\")

    def generate(self):
        root_dir = self.root_finder.find_root(self.template_dir)

        template_json_path = self.template_dir / "template.json"
        if not template_json_path.exists():
            raise FileNotFoundError(f"未找到{template_json_path}")

        with open(template_json_path, 'r', encoding='utf-8') as f:
            template_data = json.load(f)

        template_file_path = self.template_dir / "CMakePresets.json.in"
        if not template_file_path.exists():
            raise FileNotFoundError(f"未找到{template_file_path}")

        with open(template_file_path, 'r', encoding='utf-8') as f:
            template_content = f.read()

        replacements = {}
        for platform_config in template_data.get("platform", []):
            os_name = platform_config.get("os")
            if os_name not in ["Windows", "Linux", "Darwin"]:
                print(f"跳过未知平台: {os_name}")
                continue

            prefix = {"Windows": "WIN_", "Linux": "LINUX_", "Darwin": "MAC_"}[os_name]
            env_path_field = (
                "envPath" if os_name == "Windows" else
                "linuxEnvPath" if os_name == "Linux" else
                "macEnvPath"
            )
            env_paths = platform_config.get(env_path_field, [])
            if not env_paths:
                print(f"警告: {os_name} 的 {env_path_field} 为空")

            debug_flag = platform_config.get("debug_flag", {})
            rel_flag = platform_config.get("rel_flag", {})
            replacements.update({
                f"${{{prefix}GENERATOR}}": platform_config.get("generator", "Ninja"),
                f"${{{prefix}CMAKE_CXX_STANDARD}}": platform_config.get("CMAKE_CXX_STANDARD", "17"),
                f"${{{prefix}COMPILER}}": platform_config.get("COMPILER", ""),
                f"${{{prefix}LINK}}": platform_config.get("LINK", ""),
                f"${{{prefix}RC}}": platform_config.get("RC", ""),
                f"${{{prefix}MT}}": platform_config.get("MT", ""),
                f"${{{prefix}MC}}": platform_config.get("MC", ""),
                f"${{{prefix}DEBUG_CXX_FLAGS}}": debug_flag.get("CMAKE_CXX_FLAGS", ""),
                f"${{{prefix}DEBUG_C_FLAGS}}": debug_flag.get("CMAKE_C_FLAGS", ""),
                f"${{{prefix}REL_CXX_FLAGS}}": rel_flag.get("CMAKE_CXX_FLAGS", ""),
                f"${{{prefix}REL_C_FLAGS}}": rel_flag.get("CMAKE_C_FLAGS", ""),
                f"${{{prefix}TOOLCHAIN}}": self._normalize_path(platform_config.get("toolchain", ""), os_name),
                f"${{{prefix}TRIPLET}}": platform_config.get("triplet", ""),
                f"${{{prefix}ENV_PATH}}": self._get_path_separator(os_name).join(
                    self._normalize_path(p, os_name) for p in env_paths
                )
            })

        print("替换变量:")
        for key, value in replacements.items():
            print(f"  {key} -> {value}")

        preset_content = template_content
        for key, value in replacements.items():
            preset_content = preset_content.replace(key, value)

        preset_content = re.sub(r',\s*"[^"]*":\s*""', '', preset_content)
        preset_content = re.sub(
            r'"\${(WIN_|LINUX_|MAC_)[^{}]*}"', '""', preset_content, flags=re.IGNORECASE
        )

        try:
            json.loads(preset_content)
        except json.JSONDecodeError as e:
            raise ValueError(f"生成的CMakePresets.json格式无效: {e}")

        output_path = root_dir / "CMakePresets.json"
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(preset_content)
            print(f"已生成 {output_path} for all platforms")
        except OSError as e:
            raise OSError(f"写入{output_path}失败: {e}")

class FileCopier:
    def __init__(self, template_dir: Path):
        self.template_dir = template_dir
        self.root_finder = ProjectRootFinder()

    def copy_files(self):
        root_dir = self.root_finder.find_root(self.template_dir)

        template_json_path = self.template_dir / "template.json"
        if not template_json_path.exists():
            raise FileNotFoundError(f"未找到{template_json_path}")

        with open(template_json_path, 'r', encoding='utf-8') as f:
            template_data = json.load(f)

        for file_entry in template_data.get("files", []):
            src_name = file_entry.get("name")
            dst_rel_path = file_entry.get("dst")

            if not src_name or not dst_rel_path:
                print(f"跳过无效的文件条目: {file_entry}")
                continue

            src_path = self.template_dir / src_name
            dst_path = root_dir / dst_rel_path / src_name

            if not src_path.exists():
                print(f"源文件不存在: {src_path}")
                continue

            try:
                dst_path.parent.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                print(f"创建目标目录{dst_path.parent}失败: {e}")
                continue

            try:
                shutil.copy2(src_path, dst_path)
                print(f"已复制 {src_path} 到 {dst_path}")
            except OSError as e:
                print(f"复制{src_path}到{dst_path}失败: {e}")

def main():
    script_path = Path(__file__).parent
    template_dir = script_path.parent / "template"

    try:
        generator = CMakePresetsGenerator(template_dir)
        generator.generate()
    except Exception as e:
        print(f"生成CMakePresets.json失败: {e}")

    try:
        copier = FileCopier(template_dir)
        copier.copy_files()
    except Exception as e:
        print(f"复制文件失败: {e}")

if __name__ == "__main__":
    main()