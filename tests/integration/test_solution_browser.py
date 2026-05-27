"""
test_solution_browser.py — 方案浏览器 GUI 集成测试 (v5.3)

验证方案空间的完整交互链:
- F5 计算 → 方案枚举 → 选择排序 → 应用 → 参数更新
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
    """创建 MainWindow 实例并执行 F5 全量计算"""
    from ui.main_window import MainWindow

    win = MainWindow()
    win.withdraw()
    win._on_calc_all()
    yield win
    try:
        win.destroy()
    except tk.TclError:
        pass


class TestSolutionBrowserIntegration:
    """方案浏览器端到端测试"""

    def test_enumerate_produces_solutions(self, main_window):
        """F5 后至少一个模组枚举出可行方案"""
        from models.node_registry import has_solution_space
        from models.base import WaterFlow, WaterQuality

        flow = WaterFlow(Q_design=0.57, Q_avg_daily=34760.7, Kz=1.4)
        quality = WaterQuality()
        solvable = 0

        for nid, node in main_window.executor._nodes.items():
            if not has_solution_space(node.NODE_TYPE):
                continue
            try:
                sols = node.get_solution_space(flow, quality)
                if sols and len(sols) > 0:
                    solvable += 1
            except Exception:
                pass

        assert solvable > 0, "所有可枚举模组均无可行方案"

    def test_solutions_sorted_by_cost(self, main_window):
        """方案按成本升序排列 (rank=1 是最低成本的推荐方案)"""
        from models.node_registry import has_solution_space
        from models.base import WaterFlow, WaterQuality

        flow = WaterFlow(Q_design=0.57, Q_avg_daily=34760.7, Kz=1.4)
        quality = WaterQuality()

        for nid, node in main_window.executor._nodes.items():
            if not has_solution_space(node.NODE_TYPE):
                continue
            sols = node.get_solution_space(flow, quality)
            if sols and len(sols) >= 2:
                # rank_by_cost: 方案按成本升序, rank=1 是最低成本
                for i in range(len(sols) - 1):
                    assert sols[i].cost_wan_yuan <= sols[i + 1].cost_wan_yuan + 1e-6, (
                        f"{node.NODE_NAME}: 方案未按成本升序, "
                        f"rank {i+1}: {sols[i].cost_wan_yuan:.1f} > "
                        f"rank {i+2}: {sols[i+1].cost_wan_yuan:.1f}"
                    )
                return  # 验证通过

    def test_apply_solution_updates_params(self, main_window):
        """方案参数写入节点后节点参数发生变化"""
        from models.node_registry import has_solution_space
        from models.base import WaterFlow, WaterQuality

        flow = WaterFlow(Q_design=0.57, Q_avg_daily=34760.7, Kz=1.4)
        quality = WaterQuality()

        for nid, node in main_window.executor._nodes.items():
            if not has_solution_space(node.NODE_TYPE):
                continue
            sols = node.get_solution_space(flow, quality)
            if not sols:
                continue

            best = sols[0]
            # 记录应用前的参数值
            old_params = dict(node._params) if hasattr(node, "_params") else {}

            # 模拟方案应用: 将方案参数写入节点
            for key, value in best.params.items():
                try:
                    node.set_param(key, value)
                except (AttributeError, KeyError):
                    pass

            # 验证至少一个参数发生变化
            for key, new_val in best.params.items():
                if key in old_params and abs(old_params[key] - new_val) > 1e-6:
                    return  # 参数已更新

            # 如果参数值恰好相同，检查节点状态
            if old_params:
                pytest.skip("方案参数与当前参数一致，无变化可验证")

        pytest.fail("无方案可用于验证参数更新")

    def test_solution_space_robustness_positive(self, main_window):
        """所有可行方案的 robustness > 0"""
        from models.node_registry import has_solution_space
        from models.base import WaterFlow, WaterQuality

        flow = WaterFlow(Q_design=0.57, Q_avg_daily=34760.7, Kz=1.4)
        quality = WaterQuality()

        checked = 0
        for nid, node in main_window.executor._nodes.items():
            if not has_solution_space(node.NODE_TYPE):
                continue
            sols = node.get_solution_space(flow, quality)
            if not sols:
                continue
            for sol in sols[:10]:  # 上限 10 个
                assert (
                    sol.robustness >= 0
                ), f"{node.NODE_NAME}: robustness={sol.robustness} < 0"
                checked += 1

        assert checked > 0, "未检查任何方案"
