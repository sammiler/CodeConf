import json
import os
from pathlib import Path

class ProjectRootFinder:
    def find_root(self) -> Path:
        # 从环境变量 PROJECT_DIR 获取项目根路径
        project_dir = os.environ.get("PROJECT_DIR")

        # 检查环境变量是否存在
        if not project_dir:
            raise FileNotFoundError("环境变量 PROJECT_DIR 未设置")

        # 将字符串路径转换为 Path 对象并解析
        root_path = Path(project_dir).resolve()

        # 验证路径是否存在
        if not root_path.exists():
            raise FileNotFoundError(f"PROJECT_DIR 指定的路径 {root_path} 不存在")

        # 验证路径是否为目录
        if not root_path.is_dir():
            raise FileNotFoundError(f"PROJECT_DIR 指定的路径 {root_path} 不是一个目录")

        return root_path
class GenerateQrcTask:
    """生成 Qt 资源文件 (.qrc) 和代码片段的任务类"""
    def __init__(self):
        super().__init__()
        self.root_dir = ProjectRootFinder().find_root()  # 从 .vscode/py-script 回到根目录

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
        upper_path = Path(__file__).parent
        util_dir = upper_path.parent / "util"
        qrc_json_path = util_dir / "qrc-snippets.json"

        default_qrc = {
            "run": True,
            "ignore": ["h", "cpp", "c", "hpp", "mm", "qml", "js", "ui", "json", "sh", "webp", "txt", "qrc"],
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

    def execute(self):
        """执行任务的主方法"""
        if not self.is_qt_project():
            return
        self.generate_qrc_and_snippets()

def main():

    generate_arc = GenerateQrcTask()
    generate_arc.execute()

if __name__ == "__main__":
    main()