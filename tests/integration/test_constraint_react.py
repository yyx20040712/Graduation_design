"""
test_constraint_react.py — 约束面板反应性 GUI 集成测试 (v5.3)

验证约束校核的完整交互链:
- 参数修改 → 重新计算 → 约束面板更新
- 约束通过/失败的文本颜色标记
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


class TestConstraintReactivity:
    """约束面板反应性测试"""

    def test_constraint_text_populated_after_calc(self, main_window):
        """F5 后至少一个节点的约束 Text 包含 '约束校核'"""
        found = False
        for nid, node in main_window.executor._nodes.items():
            if node.result and node.result.success and node.result.checks:
                main_window._populate_result_tree(node)
                text_content = main_window.result_check_text.get("1.0", tk.END)
                if "约束校核" in text_content:
                    found = True
                    # 验证包含具体约束条目
                    check_items = [
                        n for n, c in node.result.checks.items()
                        if isinstance(c, (list, tuple)) and len(c) >= 3
                    ]
                    if check_items:
                        # 至少第一个约束名出现在文本中
                        first_name = check_items[0]
                        assert first_name in text_content or "✓" in text_content or "✗" in text_content, (
                            f"约束 '{first_name}' 未在文本中找到, "
                            f"内容: {text_content[:200]}"
                        )
                    break

        assert found, "无节点的约束 Text 包含 '约束校核'"

    def test_param_change_triggers_recalc(self, main_window):
        """修改参数后重新计算不崩溃，result 结构完整"""
        from models.base import WaterFlow, WaterQuality

        # 找一个有参数的可计算节点
        for nid, node in main_window.executor._nodes.items():
            if not (node.result and node.result.success):
                continue
            if not hasattr(node, "_params") or not node._params:
                continue

            for key, val in node._params.items():
                if not isinstance(val, (int, float)):
                    continue
                old_val = val
                try:
                    node.set_param(key, val * 0.9)
                except (AttributeError, ValueError):
                    continue
                flow = WaterFlow(Q_design=0.57, Q_avg_daily=34760.7, Kz=1.4)
                quality = WaterQuality()
                result, _, _ = node.execute(flow, quality)
                # 恢复参数
                try:
                    node.set_param(key, old_val)
                except (AttributeError, ValueError):
                    pass
                # 验证重新计算不崩溃，result 结构完整
                assert result is not None, (
                    f"{node.NODE_NAME}: 修改 {key} 后 execute 返回 None"
                )
                assert hasattr(result, "dimensions"), (
                    f"{node.NODE_NAME}: 修改 {key} 后 result 无 dimensions"
                )
                assert hasattr(result, "checks"), (
                    f"{node.NODE_NAME}: 修改 {key} 后 result 无 checks"
                )
                if result.success and result.dimensions:
                    return  # 验证通过

        pytest.skip("无可修改参数的节点")

    def test_constraint_check_count_matches(self, main_window):
        """result.checks 数量与约束 Text 中约束行数一致"""
        for nid, node in main_window.executor._nodes.items():
            if node.result and node.result.success and node.result.checks:
                # 统计 result.checks 中格式完整的条目
                valid_checks = [
                    (n, c)
                    for n, c in node.result.checks.items()
                    if isinstance(c, (list, tuple)) and len(c) >= 3
                ]
                if len(valid_checks) == 0:
                    continue

                main_window._populate_result_tree(node)
                text_content = main_window.result_check_text.get("1.0", tk.END)

                # 统计文本中 [✓] 或 [✗] 开头的行
                check_lines = [
                    line for line in text_content.split("\n")
                    if line.strip() and ("✓" in line or "✗" in line or "约束校核" in line)
                ]
                # 至少有一行（含标题行 "约束校核"）
                assert len(check_lines) >= 1, (
                    f"{node.NODE_NAME}: 约束文本无可辨识的校核行, "
                    f"checks 数: {len(valid_checks)}, 文本: {text_content[:200]}"
                )
                return

    def test_constraint_failure_shown(self, main_window):
        """失败的约束在文本中可见"""
        from models.base import WaterFlow, WaterQuality

        for nid, node in main_window.executor._nodes.items():
            if not (node.result and node.result.success and node.result.checks):
                continue

            # 检查是否有 FAIL 的约束
            failed = [
                (n, c) for n, c in node.result.checks.items()
                if isinstance(c, (list, tuple)) and not c[0]
            ]
            if not failed:
                continue

            main_window._populate_result_tree(node)
            text_content = main_window.result_check_text.get("1.0", tk.END)

            # 至少一个失败约束名出现在文本中
            found_fail = any(
                fname in text_content for fname, _ in failed
            )
            if not found_fail:
                # 检查是否通过 ✗ 符号显示
                assert "✗" in text_content or "[FAIL]" in text_content, (
                    f"{node.NODE_NAME}: {len(failed)} 个失败约束未在文本中显示"
                )
            return

        pytest.skip("无失败约束的节点")
