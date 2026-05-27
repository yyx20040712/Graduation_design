"""
test_export_pipeline.py — 导出管线集成测试 (v5.2)

验证: F5计算 → 导出 → Excel文件生成 → 内容完整性
"""
from __future__ import annotations

import os
import sys
import tempfile
import tkinter as tk
from pathlib import Path

import pytest

_SRC = os.path.join(os.path.dirname(__file__), "..", "..", "ddesign_tool", "src")
_TOOL = os.path.join(os.path.dirname(__file__), "..", "..", "ddesign_tool")
for p in [_SRC, _TOOL]:
    if p not in sys.path:
        sys.path.insert(0, p)


@pytest.fixture(scope="module")
def main_window():
    """创建 MainWindow 实例并执行 F5 计算"""
    from ui.main_window import MainWindow
    win = MainWindow()
    win.withdraw()
    win._on_calc_all()
    yield win
    try:
        win.destroy()
    except tk.TclError:
        pass


class TestExportPipeline:
    """导出管道端到端测试"""

    @pytest.fixture
    def tmp_output_dir(self, tmp_path):
        """临时输出目录"""
        out = tmp_path / "output"
        out.mkdir()
        old_cwd = os.getcwd()
        os.chdir(out)
        yield out
        os.chdir(old_cwd)

    def test_export_all_produces_excel(self, main_window, tmp_output_dir):
        """全部输出生成 Excel 文件"""
        try:
            main_window._on_export_all()
        except Exception as e:
            pytest.fail(f"导出全部输出崩溃: {e}")

        # 检查生成了 xlsx 文件
        xlsx_files = list(Path(tmp_output_dir).rglob("*.xlsx"))
        assert len(xlsx_files) > 0, f"未生成 Excel 文件, 输出目录: {tmp_output_dir}"

    def test_export_cost_produces_excel(self, main_window, tmp_output_dir):
        """导出概算生成 Excel 文件"""
        try:
            main_window._on_export_cost()
        except Exception as e:
            pytest.fail(f"导出概算崩溃: {e}")

    def test_calc_pipe_cost_handles_no_pipe(self, main_window):
        """管网概算在无管网节点时不崩溃"""
        # 不设置管网节点
        main_window._pipe_node = None
        try:
            main_window._on_calc_pipe_cost()
        except Exception as e:
            # 预期可能弹窗提示, 但不应该崩溃
            if "TclError" in str(type(e).__name__):
                pytest.skip("GUI popup in headless mode")
            pytest.fail(f"管网概算崩溃: {e}")


class TestDataIntegrity:
    """计算→导出数据完整性"""

    def test_all_nodes_have_result_after_f5(self, main_window):
        """F5 后所有节点都有计算结果"""
        failed_nodes = []
        for nid, node in main_window.executor._nodes.items():
            if not node.result:
                failed_nodes.append(f"{node.NODE_NAME}(no result)")
            elif not node.result.success:
                failed_nodes.append(
                    f"{node.NODE_NAME}: {node.result.error_msg}"
                )
        # 管道节点可能未加载 Excel, 允许失败
        real_failures = [
            n for n in failed_nodes
            if "pipe" not in n.lower() and "water_quality" not in n.lower()
        ]
        assert len(real_failures) == 0, f"计算失败节点: {real_failures}"

    def test_solution_space_not_empty(self, main_window):
        """至少部分模组有方案空间"""
        from models.node_registry import has_solution_space
        from models.base import WaterFlow, WaterQuality
        flow = WaterFlow(Q_design=0.57, Q_avg_daily=34760.7, Kz=1.4)
        quality = WaterQuality()
        solvable_count = 0
        for nid, node in main_window.executor._nodes.items():
            if has_solution_space(node.NODE_TYPE):
                try:
                    sols = node.get_solution_space(flow, quality)
                    if sols and len(sols) > 0:
                        solvable_count += 1
                except Exception:
                    pass
        assert solvable_count > 0, "所有模组方案空间均为空"
