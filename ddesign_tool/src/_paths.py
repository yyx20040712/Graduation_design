"""
_paths.py — 应用路径解析 (兼容 PyInstaller 打包 + 源码运行)

PyInstaller 环境中:
  - sys.frozen = True
  - sys._MEIPASS = 临时解压目录 (包含 --add-data 添加的所有文件)
  - 当前工作目录 = exe 所在目录 (用于输出文件)

源码环境中:
  - __file__ = 源文件路径
  - 据此推导项目根目录
"""

import os
import sys

from _logging import get_logger

_log = get_logger(__name__)


def is_frozen() -> bool:
    """是否为 PyInstaller 打包环境"""
    return getattr(sys, "frozen", False)


def get_app_root() -> str:
    """获取应用根目录

    源码: ddesign_tool/ (main.py 所在目录)
    打包: sys._MEIPASS (PyInstaller 临时解压目录)
    """
    if is_frozen():
        return sys._MEIPASS
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _get_user_dir() -> str:
    """获取用户数据根目录 (v5.4-s7)

    打包: EXE 所在目录 (data/output/logs 放这里)
    源码: 项目根目录
    """
    if is_frozen():
        return os.path.dirname(sys.executable)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def get_src_dir() -> str:
    """获取源码目录"""
    return os.path.join(get_app_root(), "src")


def get_data_dir() -> str:
    """获取数据目录 (data/)

    打包: EXE_dir/data (bootstrap 拷贝目标)
         回退 MEIPASS/data (原始文件)
    源码: 项目根目录 data/
    """
    if is_frozen():
        user_data = os.path.join(_get_user_dir(), "data")
        if os.path.isdir(user_data) and os.listdir(user_data):
            return user_data
        meipass_data = os.path.join(sys._MEIPASS, "data")
        if os.path.isdir(meipass_data):
            return meipass_data
        return user_data
    return os.path.join(get_app_root(), "data")


def get_mods_dir() -> str:
    """获取模组目录 (mods/)

    优先级:
      1. DDESIGN_MODS_PATH 环境变量 (自定义路径)
      2. 项目根目录 mods/ (开发模式, 与测试共享同一目录)
      3. ddesign_tool/mods/ (回退, 兼容旧布局)
      4. PyInstaller: os.getcwd()/mods
    """
    env_path = os.environ.get("DDESIGN_MODS_PATH", "")
    if env_path and os.path.isdir(env_path):
        return env_path

    if is_frozen():
        user_mods = os.path.join(_get_user_dir(), "mods")
        if os.path.isdir(user_mods) and os.listdir(user_mods):
            return user_mods
        # 回退: MEIPASS 原始文件 (只读)
        meipass_mods = os.path.join(sys._MEIPASS, "mods")
        if os.path.isdir(meipass_mods):
            return meipass_mods
        return user_mods

    # 开发模式: 优先使用项目根目录的 mods/
    project_root = os.path.abspath(os.path.join(get_app_root(), ".."))
    root_mods = os.path.join(project_root, "mods")
    if os.path.isdir(root_mods):
        return root_mods

    return os.path.join(get_app_root(), "mods")


def get_mods_search_paths() -> list:
    """返回所有可能的模组搜索路径 (用于多目录扫描)

    按优先级排序: 首个路径为主目录, 后续为回退路径.
    """
    primary = get_mods_dir()
    paths = [primary]

    # 如果主路径不是 ddesign_tool/mods/, 将其加入回退
    app_mods = os.path.join(get_app_root(), "mods")
    if os.path.isdir(app_mods) and os.path.abspath(app_mods) != os.path.abspath(primary):
        paths.append(app_mods)

    # 如果主路径不是项目根目录 mods/, 将其加入回退
    project_root = os.path.abspath(os.path.join(get_app_root(), ".."))
    root_mods = os.path.join(project_root, "mods")
    if os.path.isdir(root_mods) and os.path.abspath(root_mods) != os.path.abspath(primary):
        if os.path.abspath(root_mods) != os.path.abspath(app_mods):
            paths.append(root_mods)

    return paths


def get_config_path() -> str:
    """获取配置文件路径 (EXE_dir/config.ini)"""
    if is_frozen():
        return os.path.join(_get_user_dir(), "config.ini")
    return os.path.join(get_app_root(), "config.ini")


def get_knowledge_dir() -> str:
    """获取知识库目录 (EXE_dir/knowledge/)"""
    if is_frozen():
        return os.path.join(_get_user_dir(), "knowledge")
    return os.path.join(get_app_root(), "knowledge")


def get_template_dir() -> str:
    """获取模板文件目录"""
    return _get_user_dir() if is_frozen() else get_app_root()


def get_output_dir() -> str:
    """获取输出目录 (EXE_dir/output/)"""
    d = os.path.join(_get_user_dir(), "output")
    os.makedirs(d, exist_ok=True)
    return d


def get_logs_dir() -> str:
    """获取日志目录 (EXE_dir/logs/)"""
    d = os.path.join(_get_user_dir(), "logs")
    os.makedirs(d, exist_ok=True)
    return d


def get_cache_dir() -> str:
    """获取缓存目录 (EXE_dir/cache/)"""
    d = os.path.join(_get_user_dir(), "cache")
    os.makedirs(d, exist_ok=True)
    return d


def get_projects_dir() -> str:
    """获取项目目录 (EXE_dir/projects/)"""
    d = os.path.join(_get_user_dir(), "projects")
    os.makedirs(d, exist_ok=True)
    return d


def setup_import_paths() -> None:
    """将 src/ 和项目根目录添加到 sys.path, 确保所有模块可导入"""
    src = get_src_dir()
    if src not in sys.path:
        sys.path.insert(0, src)
    app = get_app_root()
    if app not in sys.path:
        sys.path.insert(0, app)
    # 项目根目录: 使 mods/ 模块可被 from mods.xxx import 找到
    project_root = os.path.abspath(os.path.join(app, ".."))
    if os.path.isdir(os.path.join(project_root, "mods")):
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
