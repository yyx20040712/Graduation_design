"""test_wuni_tisheng.py — 污水提升泵房 测试 (v5.3)"""

import sys
from pathlib import Path

SRC_DIR = Path(__file__).parent.parent / "ddesign_tool" / "src"
APP_DIR = Path(__file__).parent.parent / "ddesign_tool"
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(APP_DIR))

import pytest
import numpy as np
from models.base import WaterFlow, WaterQuality
from mods.mod_manager import get_mod_manager


def _get_node():
    mgr = get_mod_manager()
    mgr.load_all()
    cls = mgr.get_node_class("wuni_tisheng")
    assert cls is not None, "wuni_tisheng not registered"
    return cls()


class TestWuniTisheng:
    """污水提升泵房 smoke tests"""

    def test_node_identity(self):
        node = _get_node()
        assert node.NODE_TYPE == "wuni_tisheng"
        assert node.NODE_NAME == "污水提升泵房"

    def test_calculate_success(self):
        node = _get_node()
        flow = WaterFlow()
        quality = WaterQuality()
        result, _, _ = node.execute(flow, quality)
        assert result.success, f"Failed: {result.error_msg}"

    def test_dimensions_positive(self):
        node = _get_node()
        flow = WaterFlow()
        quality = WaterQuality()
        result, _, _ = node.execute(flow, quality)
        for name, (val, unit) in result.dimensions.items():
            if isinstance(val, (int, float)):
                assert val >= 0, f"{name} = {val} < 0"

    def test_vectorized_consistency(self):
        node = _get_node()
        flow, quality = WaterFlow(), WaterQuality()
        scalar, _, _ = node.execute(flow, quality)
        from models.discretization import get_config

        cfg = get_config("wuni_tisheng")
        grid = {k: np.array([cfg["free"][k][0]]) for k in cfg["free"]}
        fixed = {}
        vec = type(node)._vectorized_compute(grid, flow, quality, fixed)
        assert len(vec) == 1
        assert abs(vec["H_total"][0] - scalar.dimensions["总扬程 H"][0]) < 3.0

    def test_solution_space_has_feasible(self):
        """方案空间枚举产生可行方案"""
        node = _get_node()
        from models.solution_space import get_engine

        flow, quality = WaterFlow(), WaterQuality()
        engine = get_engine()
        sols = engine.enumerate("wuni_tisheng", flow, quality)
        assert len(sols) > 0, "无可行方案"
        assert sols[0].robustness > 0, "robustness 应为正数"
        assert sols[0].cost_wan_yuan > 0, "cost 应为正数"

    def test_serialization_roundtrip(self):
        """序列化往返保持参数一致"""
        node = _get_node()
        node.execute(WaterFlow(), WaterQuality())
        d = node.to_dict()
        restored = type(node).from_dict(d)
        assert restored.node_id == node.node_id
        for key, val in node._params.items():
            assert abs(restored._params.get(key, 0) - val) < 1e-9

    def test_constraint_keys_all_present(self):
        """离散化约束字段齐全"""
        node = _get_node()
        from models.discretization import get_config

        cfg = get_config("wuni_tisheng")
        flow, quality = WaterFlow(), WaterQuality()
        grid = {k: np.array([cfg["free"][k][0]]) for k in cfg["free"]}
        fixed = cfg.get("fixed", {})
        vec = type(node)._vectorized_compute(grid, flow, quality, fixed)
        for ck in cfg.get("constraint_keys", []):
            assert f"ok_{ck}" in vec.dtype.names, f"missing ok_{ck}"
