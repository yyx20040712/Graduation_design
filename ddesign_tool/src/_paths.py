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
    打包: sys._MEIPASS (PyInstaller 临时解压目录, 包含 src/, mods/, data/, config.ini)
    """
    if is_frozen():
        return sys._MEIPASS
    # 源码: 此文件位于 src/_paths.py, 向上两级 = ddesign_tool/
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def get_src_dir() -> str:
    """获取源码目录"""
    return os.path.join(get_app_root(), "src")


def get_data_dir() -> str:
    """获取数据目录 (data/)"""
    if is_frozen():
        return os.path.join(os.getcwd(), "data")
    return os.path.join(get_app_root(), "data")


def get_mods_dir() -> str:
    """获取模组目录 (mods/)"""
    if is_frozen():
        return os.path.join(os.getcwd(), "mods")
    return os.path.join(get_app_root(), "mods")


def get_config_path() -> str:
    """获取配置文件路径 (config.ini)"""
    if is_frozen():
        return os.path.join(os.getcwd(), "config.ini")
    return os.path.join(get_app_root(), "config.ini")


def get_knowledge_dir() -> str:
    """获取知识库目录 (knowledge/)"""
    if is_frozen():
        return os.path.join(os.getcwd(), "knowledge")
    return os.path.join(get_app_root(), "knowledge")


def get_template_dir() -> str:
    """获取模板文件目录 (cwd 根目录)"""
    return os.getcwd() if is_frozen() else get_app_root()


def get_output_dir() -> str:
    """获取输出目录 (output/), 在工作目录下创建"""
    d = os.path.join(os.getcwd(), "output")
    os.makedirs(d, exist_ok=True)
    return d


def get_logs_dir() -> str:
    """获取日志目录 (logs/), 在工作目录下创建"""
    d = os.path.join(os.getcwd(), "logs")
    os.makedirs(d, exist_ok=True)
    return d


def get_cache_dir() -> str:
    """获取缓存目录 (cache/), 在工作目录下创建"""
    d = os.path.join(os.getcwd(), "cache")
    os.makedirs(d, exist_ok=True)
    return d


def get_projects_dir() -> str:
    """获取项目目录 (projects/), 在工作目录下创建"""
    d = os.path.join(os.getcwd(), "projects")
    os.makedirs(d, exist_ok=True)
    return d


def setup_import_paths() -> None:
    """将 src/ 添加到 sys.path, 确保所有模块可导入"""
    src = get_src_dir()
    if src not in sys.path:
        sys.path.insert(0, src)
    app = get_app_root()
    if app not in sys.path:
        sys.path.insert(0, app)
