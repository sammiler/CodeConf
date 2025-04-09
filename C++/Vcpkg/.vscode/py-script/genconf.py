import json
import platform
import re
from pathlib import Path
import shutil

class BaseGenerator:
    def __init__(self):
        self.root_dir = Path(__file__).resolve().parents[2]
        self.template_dir = self.root_dir / ".vscode" / "template"
        self.output_dir = self.root_dir / ".vscode"
        self.system = platform.system()
        self.os_map = {"Windows": "Windows", "Linux": "Linux", "Darwin": "Mac"}
        self.current_os = self.os_map.get(self.system, "Windows")

    def load_json(self, filename):
        file_path = self.template_dir / filename
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def load_template(self, filename):
        file_path = self.template_dir / filename
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()

    def save_json(self, filename, data):
        output_path = self.output_dir / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"已生成: {output_path}")
class SettingsGenerator(BaseGenerator):
    def replace_placeholders(self, template, replacements):
        result = template
        for key, value in replacements.items():
            placeholder = f"${{{key}}}"
            safe_value = str(value).replace("\\", "\\\\")
            result = result.replace(placeholder, safe_value)
        return result

    def generate(self):
        config = self.load_json("template.json")["settings"]
        platform_data = self.load_json("template.json")["platform"]
        template = self.load_template("settings.json.in")
        
        # 从 template.json 中获取当前操作系统的配置
        os_config = config["os"].get(self.current_os, {})
        dynamic = config.get("dynamic", [])

        # 准备替换字典
        replacements = {
            "bash": os_config.get("bash", "bash"),  # 默认值
            "os" : platform_data["os"],
            "qt_exe": os_config.get("qt_exe", ""),
            "toolchain": platform_data["toolchain"],
            "triplet": platform_data["triplet"],
            "MSVC_PATH": platform_data["compiler"]["MSVC_PATH"],
            "WINDOWS_SDK_PATH": platform_data["compiler"]["WINDOWS_SDK_PATH"],
            "WINDOWS_SDK_VERSION": platform_data["compiler"]["WINDOWS_SDK_VERSION"],
            # envPath 需要拼接为分号分隔的字符串
            "envPath": ";".join(platform_data["envPath"])
        }

        # 替换占位符
        template = self.replace_placeholders(template, replacements)
        try:
            self.save_json("settings.json", json.loads(template))
        except json.JSONDecodeError as e:
            print(f"JSON 解析错误: {e}")
            print(f"替换后的字符串: {template}")
            raise

class TasksGenerator(BaseGenerator):
    def replace_placeholders(self, template, replacements):
        result = template
        for key, value in replacements.items():
            placeholder = f"${{{key}}}"
            safe_value = json.dumps(value)[1:-1]
            result = result.replace(placeholder, safe_value)
        return result

    def generate(self):
        config = self.load_json("template.json")["tasks"]
        template = self.load_template("tasks.json.in")
        replacements = config.get(self.current_os, {})
        
        if not replacements:
            print(f"警告: 未在 template.json 的 tasks 中找到 {self.current_os} 的配置")
            return

        template = self.replace_placeholders(template, replacements)
        try:
            self.save_json("tasks.json", json.loads(template))
        except json.JSONDecodeError as e:
            print(f"JSON 解析错误: {e}")
            print(f"替换后的字符串: {template}")
            raise

class CCppPropertiesGenerator(BaseGenerator):
    def generate(self):
        config = self.load_json("template.json")["c_cpp_properties"]
        template = self.load_template("c_cpp_properties.json.in")
        replacements = config.get(self.current_os, {})
        
        for key, value in replacements.items():
            template = template.replace(f"${{{key}}}", str(value))
        
        self.save_json("c_cpp_properties.json", json.loads(template))

class LaunchGenerator(BaseGenerator):
    def find_executables(self):
        bin_dir = self.root_dir / "build" / "bin"
        exes = []
        ext = ".exe" if self.system == "Windows" else ""
        for file in bin_dir.rglob(f"*{ext}"):
            if file.is_file() and (self.system != "Windows" or file.suffix == ".exe"):
                exes.append({"name": file.name, "path": str(file).replace("\\", "/")})
        return exes

    def generate(self):
        config = self.load_json("template.json")["launch"]
        template = self.load_json("launch.json.in")
        replacements = config.get(self.current_os, {})
        exes = self.find_executables()
        configurations = []
        for exe in exes:
            config_str = self.load_template("launch.json.in").replace("[]", "[{}]")
            exe_replacements = replacements.copy()
            exe_replacements["exe_name"] = exe["name"]
            exe_replacements["exe_path"] = exe["path"]
            for key, value in exe_replacements.items():
                config_str = config_str.replace(f"${{{key}}}", str(value))
            config_data = json.loads(config_str)
            configurations.extend(config_data["configurations"])

        template["configurations"] = configurations
        self.save_json("launch.json", template)

class CopyTemplate(BaseGenerator):
    def normalize_path(self, path_str):
        return path_str.replace("\\", "/")

    def generate(self):
        config = self.load_json("template.json")
        files = config.get("files", [])
        
        if not files:
            print("未在 template.json 中找到 'files' 配置，跳过复制")
            return

        for file_entry in files:
            src_name = file_entry.get("name")
            dst_rel_path = file_entry.get("dst")
            
            if not src_name or not dst_rel_path:
                print(f"警告: 'files' 配置项缺少 'name' 或 'dst'，跳过: {file_entry}")
                continue
            
            src_name_normalized = self.normalize_path(src_name)
            dst_rel_path_normalized = self.normalize_path(dst_rel_path)
            
            src_path = self.template_dir / src_name_normalized
            dst_path = self.root_dir / dst_rel_path_normalized / src_name_normalized
            
            if not src_path.exists():
                print(f"错误: 源文件 {src_path} 不存在，跳过")
                continue
            
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_path, dst_path)
            print(f"已复制: {src_path} -> {dst_path}")


class CMakePresetsGenerator(BaseGenerator):
    def __init__(self):
        super().__init__()
        # 覆盖 output_dir 为根目录
        self.output_dir = self.root_dir
    def replace_placeholders(self, template, replacements):
        result = template
        for key, value in replacements.items():
            placeholder = f"${{{key}}}"
            safe_value = str(value).replace("\\", "\\\\")
            result = result.replace(placeholder, safe_value)
        return result

    def extract_flags(self, flag_str, flag_type):
        # 提取指定类型的标志，例如 CMAKE_CXX_FLAGS 或 CMAKE_C_FLAGS
        prefix = f"-D{flag_type}=\""
        start = flag_str.find(prefix) + len(prefix)
        end = flag_str.find("\"", start)
        return flag_str[start:end]

    def generate(self):
        template_json = self.load_json("template.json")
        platform_data = template_json["platform"]
        tasks_data = template_json["tasks"]
        c_cpp_data = template_json["c_cpp_properties"]
        template = self.load_template("CMakePresets.json.in")

        # 准备替换字典
        replacements = {
            "generator": platform_data["generator"],
            "CMAKE_CXX_STANDARD": platform_data["compiler"]["CMAKE_CXX_STANDARD"],
            "toolchain": platform_data["toolchain"],
            "triplet": platform_data["triplet"],
            # Windows
            "CMAKE_CXX_COMPILER_WINDOWS": platform_data["compiler"]["CMAKE_CXX_COMPILER"],
            "CMAKE_C_COMPILER_WINDOWS": platform_data["compiler"]["CMAKE_C_COMPILER"],
            "LINK_PATH_WINDOWS": platform_data["compiler"]["LINK_PATH"],
            "RC_COMPILER_WINDOWS": platform_data["compiler"]["RC_COMPILER"],
            "MT_WINDOWS": platform_data["compiler"]["MT"],
            "debug_cxx_flags_windows": self.extract_flags(tasks_data["Windows"]["debug_flag"], "CMAKE_CXX_FLAGS"),
            "debug_c_flags_windows": self.extract_flags(tasks_data["Windows"]["debug_flag"], "CMAKE_C_FLAGS"),
            "rel_cxx_flags_windows": self.extract_flags(tasks_data["Windows"]["rel_flag"], "CMAKE_CXX_FLAGS"),
            "rel_c_flags_windows": self.extract_flags(tasks_data["Windows"]["rel_flag"], "CMAKE_C_FLAGS"),
            # Linux
            "CMAKE_CXX_COMPILER_LINUX": c_cpp_data["Linux"]["compiler_path"].replace("gcc", "g++"),
            "CMAKE_C_COMPILER_LINUX": c_cpp_data["Linux"]["compiler_path"],
            "debug_cxx_flags_linux": self.extract_flags(tasks_data["Linux"]["debug_flag"], "CMAKE_CXX_FLAGS"),
            "debug_c_flags_linux": self.extract_flags(tasks_data["Linux"]["debug_flag"], "CMAKE_C_FLAGS"),
            "rel_cxx_flags_linux": self.extract_flags(tasks_data["Linux"]["rel_flag"], "CMAKE_CXX_FLAGS"),
            "rel_c_flags_linux": self.extract_flags(tasks_data["Linux"]["rel_flag"], "CMAKE_C_FLAGS"),
            # Mac
            "CMAKE_CXX_COMPILER_MAC": c_cpp_data["Mac"]["compiler_path"].replace("clang", "clang++"),
            "CMAKE_C_COMPILER_MAC": c_cpp_data["Mac"]["compiler_path"],
            "debug_cxx_flags_mac": self.extract_flags(tasks_data["Mac"]["debug_flag"], "CMAKE_CXX_FLAGS"),
            "debug_c_flags_mac": self.extract_flags(tasks_data["Mac"]["debug_flag"], "CMAKE_C_FLAGS"),
            "rel_cxx_flags_mac": self.extract_flags(tasks_data["Mac"]["rel_flag"], "CMAKE_CXX_FLAGS"),
            "rel_c_flags_mac": self.extract_flags(tasks_data["Mac"]["rel_flag"], "CMAKE_C_FLAGS"),
        }

        # 替换占位符
        template = self.replace_placeholders(template, replacements)
        try:
            self.save_json("CMakePresets.json", json.loads(template))
        except json.JSONDecodeError as e:
            print(f"JSON 解析错误: {e}")
            print(f"替换后的字符串: {template}")
            raise

def main():
    generators = [
        SettingsGenerator(),
        TasksGenerator(),
        CCppPropertiesGenerator(),
        LaunchGenerator(),
        CopyTemplate(),
        CMakePresetsGenerator()
    ]
    for generator in generators:
        generator.generate()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"脚本执行失败: {e}")
        exit(1)