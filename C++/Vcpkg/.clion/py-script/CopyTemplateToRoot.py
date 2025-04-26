import json
import os
import shutil
import platform
import re
from pathlib import Path

class ProjectRootFinder:
    def find_root(self, start_path: Path) -> Path:
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
        copier = FileCopier(template_dir)
        copier.copy_files()
    except Exception as e:
        print(f"复制文件失败: {e}")

if __name__ == "__main__":
    main()