"""
test_ui_import.py — UI 模块导入烟雾测试

确保所有 UI 层模块可正常导入,防止 SyntaxError 和
缺失方法导致的导入失败.
"""

import sys
import os
from pathlib import Path

SRC_DIR = Path(__file__).parent.parent / "ddesign_tool" / "src"
sys.path.insert(0, str(SRC_DIR))


def test_import_ui_logger():
    """ui.logger 可导入"""
    from ui.logger import log
    assert log is not None


def test_import_canvas_view():
    """ui.canvas_view 可导入"""
    from ui.canvas_view import NodeCanvas
    assert NodeCanvas is not None


def test_import_dimension_labels():
    """ui.dimension_labels 可导入"""
    from ui.dimension_labels import format_dimension_row
    assert format_dimension_row is not None


def test_import_file_manager():
    """ui.file_manager 可导入"""
    from ui.file_manager import FileManager
    assert FileManager is not None


def test_import_solution_browser():
    """ui.solution_browser 可导入 (曾因 SyntaxError 失败)"""
    from ui.solution_browser import SolutionBrowser
    assert SolutionBrowser is not None


def test_import_main_window():
    """ui.main_window 可导入 (依赖 solution_browser)"""
    from ui.main_window import MainWindow
    assert MainWindow is not None
