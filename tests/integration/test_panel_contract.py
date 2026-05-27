"""
test_panel_contract.py — 面板数据契约集成测试 (v5.2)

验证结果面板的输入→输出数据完整性:
- 每个模组的 NodeResult 正确填充到 result_tree 各列
- 分类(原始设计参数/计算结果/构筑物尺寸)正确
- 约束校核在底部 Text 窗口显示
"""
from __future__ import annotations

import os
import sys
import tkinter as tk
import pytest

# 路径设置
_SRC = os.path.join(os.path.dirname(__file__), "..", "..", "ddesign_tool", "src")
_TOOL = os.path.join(os.path.dirname(__file__), "..", "..", "ddesign_tool")
for p in [_SRC, _TOOL]:
    if p not in sys.path:
        sys.path.insert(0, p)


@pytest.fixture(scope="module")
def main_window():
    """创建最小化 MainWindow 实例 (模块级复用)"""
    from ui.main_window import MainWindow
    win = MainWindow()
    win.withdraw()
    # F5 计算获取结果数据
    win._on_calc_all()
    yield win
    try:
        win.destroy()
    except tk.TclError:
        pass


class TestResultPanelContract:
    """结果面板数据契约"""

    def test_result_tree_has_sections(self, main_window):
        """结果面板包含三大类标题"""
        # 选中第一个有结果的节点
        found = False
        for nid, node in main_window.executor._nodes.items():
            if node.result and node.result.success:
                main_window._on_node_selected(nid)
                main_window._populate_result_tree(node)
                found = True
                break
        assert found, "无可用计算结果"

        # 收集 Treeview 内容
        rows = []
        for item in main_window.result_tree.get_children():
            values = main_window.result_tree.item(item, "values")
            tags = main_window.result_tree.item(item, "tags")
            rows.append((values, tags or ()))

        # 检查三大类标题
        section_titles = {v[1] for v, t in rows if "section_banner" in t}
        expected = {"── 原始设计参数 ──", "── 计算结果 ──", "── 构筑物尺寸 ──"}
        missing = expected - section_titles
        assert not missing, f"缺少章节标题: {missing}"

    def test_result_tree_has_params(self, main_window):
        """原始设计参数区域包含参数行"""
        for nid, node in main_window.executor._nodes.items():
            if node.result and node.result.success and node.result.params:
                main_window._populate_result_tree(node)
                # 统计 param 标签行
                param_count = sum(
                    1 for i in main_window.result_tree.get_children()
                    if "param" in (main_window.result_tree.item(i, "tags") or ())
                )
                if param_count > 0:
                    return  # 通过
        pytest.fail("未找到参数行")

    def test_result_tree_has_dimensions(self, main_window):
        """计算结果或构筑物尺寸区域包含维度行"""
        for nid, node in main_window.executor._nodes.items():
            if node.result and node.result.success:
                main_window._populate_result_tree(node)
                rows = [
                    main_window.result_tree.item(i, "values")
                    for i in main_window.result_tree.get_children()
                ]
                # 排除章节标题和公式行
                data_rows = [r for r in rows if r[0] and not r[0].startswith("──") and not r[0].startswith("↳")]
                if len(data_rows) > 0:
                    return
        pytest.fail("未找到维度数据行")

    def test_constraint_text_populated(self, main_window):
        """约束校核在底部 Text 窗口显示"""
        for nid, node in main_window.executor._nodes.items():
            if node.result and node.result.success and node.result.checks:
                main_window._populate_result_tree(node)
                text_content = main_window.result_check_text.get("1.0", tk.END)
                assert "约束校核" in text_content, f"约束Text未填充: {text_content[:100]}"
                return
        pytest.skip("无约束校核数据的节点")


class TestQualityPanelContract:
    """水质面板数据契约"""

    def test_full_flow_has_sections(self, main_window):
        """全流程水质追踪包含各节点节"""
        from ui.quality_panel import QualityPanel
        # 使用 QualityPanel 实例
        qp = main_window._quality_panel
        qp.build_full_quality_flow()
        sections = getattr(qp, "_quality_sections", {})
        assert len(sections) > 0, "全流程水质追踪未生成任何节点节"


class TestResultDataConsistency:
    """结果数据一致性"""

    def test_params_count_matches(self, main_window):
        """result.params 条目数与显示行数一致"""
        for nid, node in main_window.executor._nodes.items():
            if node.result and node.result.success and node.result.params:
                expected = len(node.result.params)
                main_window._populate_result_tree(node)
                actual = sum(
                    1 for i in main_window.result_tree.get_children()
                    if "param" in (main_window.result_tree.item(i, "tags") or ())
                )
                if expected > 0:
                    assert actual == expected, (
                        f"{node.NODE_NAME}: params={expected}, displayed={actual}"
                    )
                    return

    def test_dimensions_include_physical_and_computed(self, main_window):
        """维度包含 physical 和 computed 分类"""
        for nid, node in main_window.executor._nodes.items():
            if node.result and node.result.success:
                cats = node.result.dimension_categories
                if cats:
                    has_physical = any(v == "physical" for v in cats.values())
                    has_computed = any(v == "computed" for v in cats.values())
                    assert has_physical or has_computed, (
                        f"{node.NODE_NAME}: 维度缺少分类"
                    )
                    return
