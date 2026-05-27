"""test_bashi_jiliangcao.py — 巴氏计量槽 测试 (v5.3)"""

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
    cls = mgr.get_node_class("bashi_jiliangcao")
    assert cls is not None, "bashi_jiliangcao not registered"
    node = cls()
    node.set_param("b", 0.30)
    return node


class TestBashiJiliangcao:
    """巴氏计量槽 tests"""

    def test_node_identity(self):
        node = _get_node()
        assert node.NODE_TYPE == "bashi_jiliangcao"
        assert node.NODE_NAME == "巴氏计量槽"

    def test_calculate_success(self):
        node = _get_node()
        flow = WaterFlow()
        quality = WaterQuality()
        result, _, _ = node.execute(flow, quality)
        assert result.success, f"Failed: {result.error_msg}"

    def test_all_standard_throat_widths(self):
        """全部5种标准喉宽都能成功计算"""
        _STANDARD_B_VALUES = [0.152, 0.228, 0.30, 0.45, 0.60]
        flow = WaterFlow()
        quality = WaterQuality()
        node = _get_node()
        for b in _STANDARD_B_VALUES:
            node.set_param("b", b)
            result, _, _ = node.execute(flow, quality)
            assert result.success, f"b={b} failed: {result.error_msg}"
            assert result.dimensions["上游水深 h_a"][0] > 0
            fr_check = result.checks.get("弗劳德数 Fr")
            if fr_check:
                assert fr_check[0], f"b={b}: Fr check failed (Fr={fr_check[1]})"

    def test_invalid_throat_width(self):
        """非法喉宽应返回失败"""
        node = _get_node()
        node.set_param("b", 0.999)
        flow = WaterFlow()
        result = node.calculate(flow, WaterQuality())
        assert not result.success

    def test_vectorized_produces_correct_shape(self):
        node = _get_node()
        from models.discretization import get_config

        cfg = get_config("bashi_jiliangcao")
        flow, quality = WaterFlow(), WaterQuality()
        grid = {k: np.array(cfg["free"][k]) for k in cfg["free"]}
        fixed = {}
        vec = type(node)._vectorized_compute(grid, flow, quality, fixed)
        assert len(vec) == len(grid["b"])
        assert "concrete_m3" in vec.dtype.names
        assert "ok_Fr" in vec.dtype.names
        assert "val_Fr" in vec.dtype.names

    def test_serialization_roundtrip(self):
        """序列化往返保持参数一致"""
        node = _get_node()
        node.execute(WaterFlow(), WaterQuality())
        d = node.to_dict()
        restored = type(node).from_dict(d)
        assert restored.node_id == node.node_id
        assert abs(restored._params.get("b", 0) - node._params["b"]) < 1e-9

    def test_constraint_limits_coverage(self):
        """所有约束的 ok_*/val_* 字段存在且默认通过"""
        node = _get_node()
        from models.discretization import get_config

        cfg = get_config("bashi_jiliangcao")
        flow, quality = WaterFlow(), WaterQuality()
        grid = {k: np.array([cfg["free"][k][0]]) for k in cfg["free"]}
        fixed = cfg.get("fixed", {})
        vec = type(node)._vectorized_compute(grid, flow, quality, fixed)
        for ck in cfg.get("constraint_keys", []):
            ok_field = f"ok_{ck}"
            val_field = f"val_{ck}"
            assert ok_field in vec.dtype.names, f"missing {ok_field}"
            assert val_field in vec.dtype.names, f"missing {val_field}"
            assert vec[ok_field][0], f"默认参数下约束 {ck} 失败"
