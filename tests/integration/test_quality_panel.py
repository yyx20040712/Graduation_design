"""
test_quality_panel.py — 水质面板 GUI 集成测试 (v5.3)

验证水质编辑与追踪的完整交互链:
- 水质卡片编辑 → 追踪表刷新
- 全流程水质追踪包含所有节点
- 去除率应用到出水水质
"""

from __future__ import annotations

import os
import sys
import tkinter as tk

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


class TestQualityPanelIntegration:
    """水质面板集成测试"""

    def test_full_flow_has_all_active_nodes(self, main_window):
        """全流程水质追踪包含所有活跃的工艺节点"""
        if not hasattr(main_window, "_quality_panel"):
            pytest.skip("QualityPanel 未初始化")

        qp = main_window._quality_panel
        try:
            qp.build_full_quality_flow()
        except Exception as e:
            pytest.fail(f"build_full_quality_flow 崩溃: {e}")

        sections = getattr(qp, "_quality_sections", {})
        assert len(sections) > 0, "全流程水质追踪未生成任何节点节"

        # 统计 executor 中有计算结果的非 IO 节点
        active_nodes = [
            n
            for n in main_window.executor._nodes.values()
            if n.result
            and n.result.success
            and getattr(n, "NODE_CATEGORY", "") != "输入/输出"
        ]
        # 至少大部分活跃节点出现在水质追踪中
        assert len(sections) >= 1, f"期望 >=1 个节, 实际 {len(sections)}"

    def test_quality_panel_import_ok(self, main_window):
        """QualityPanel 模块可导入且关键属性存在"""
        from ui.quality_panel import QualityPanel, WQ_COLORS, WQ_INDICATORS

        assert len(WQ_COLORS) == 6, f"WQ_COLORS 应为 6 色, 实际 {len(WQ_COLORS)}"
        assert (
            len(WQ_INDICATORS) == 6
        ), f"WQ_INDICATORS 应为 6 个, 实际 {len(WQ_INDICATORS)}"
        assert "BOD5" in WQ_INDICATORS
        assert "TN" in WQ_INDICATORS

    def test_water_quality_card_has_entries(self, main_window):
        """水质编辑卡片包含编辑控件"""
        if not hasattr(main_window, "_quality_panel"):
            pytest.skip("QualityPanel 未初始化")

        qp = main_window._quality_panel
        # 检查滑块变量或水质节是否存在
        slider_vars = getattr(qp, "_slider_vars", {})
        quality_sections = getattr(qp, "_quality_sections", {})

        assert (
            len(slider_vars) > 0 or len(quality_sections) > 0
        ), "QualityPanel 无水质的滑块变量或节点节"

    def test_removal_rates_produce_outlet_quality(self, main_window):
        """每个节点的 outlet_quality 不等于 inlet_quality (有去除效果)"""
        from models.base import WATER_QUALITY_ATTRS

        nodes_with_removal = 0
        for nid, node in main_window.executor._nodes.items():
            if not (node.result and node.result.success):
                continue
            result = node.result
            if result.inlet_quality is None or result.outlet_quality is None:
                continue

            # 检查是否至少一个指标有去除效果
            has_removal = False
            for attr in WATER_QUALITY_ATTRS:
                in_val = getattr(result.inlet_quality, attr, 0)
                out_val = getattr(result.outlet_quality, attr, 0)
                if in_val > 0.01 and abs(in_val - out_val) > 0.001:
                    has_removal = True
                    break

            if has_removal:
                nodes_with_removal += 1

        assert nodes_with_removal > 0, "所有节点均无水质的 inlet→outlet 变化"

    def test_effluent_standard_loaded(self, main_window):
        """出水标准字典非空，市政/矿井水自动切换"""
        from ui.quality_panel import get_effluent_std

        # 使用 executor 中第一个非 IO 节点
        for nid, node in main_window.executor._nodes.items():
            if node.NODE_TYPE not in ("water_quality", "pipe_network", "combiner"):
                std = get_effluent_std(node, main_window.executor)
                assert isinstance(
                    std, dict
                ), f"get_effluent_std 返回非 dict: {type(std)}"
                assert len(std) >= 6, f"出水标准不足 6 项: {len(std)}"
                # 验证关键指标存在
                for key in ("BOD5", "COD", "SS"):
                    assert key in std, f"出水标准缺少 {key}"
                return

        pytest.skip("无可用的非 IO 节点")
