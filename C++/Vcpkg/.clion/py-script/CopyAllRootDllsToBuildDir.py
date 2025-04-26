import os
from pathlib import Path
import shutil
import platform


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
class CopyDllTask:
    """负责复制动态链接库文件的任务类"""
    def __init__(self):
        super().__init__()
        self.system = platform.system()
        # 定义源目录和目标目录
        self.source_dir = ProjectRootFinder().find_root() # 回到根目录
        print(self.source_dir)
        self.target_dir = self.source_dir / "build" / "bin"

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
            if directory == self.target_dir:
                return lib_files
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



def main():

        copy_task = CopyDllTask()
        copy_task.execute()

if __name__ == "__main__":
    main()