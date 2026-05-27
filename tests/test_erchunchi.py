"""test_erchunchi.py — 二沉池社区模组测试 (v5.3)"""

import sys
from pathlib import Path

SRC_DIR = Path(__file__).parent.parent / "ddesign_tool" / "src"
APP_DIR = Path(__file__).parent.parent / "ddesign_tool"
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(APP_DIR))

import numpy as np
import pytest
from models.base import WaterFlow, WaterQuality
from mods.mod_manager import get_mod_manager


def _get_node():
    mgr = get_mod_manager()
    mgr.load_all()
    cls = mgr.get_node_class("erchunchi")
    assert cls is not None, "erchunchi not registered"
    return cls()


def test_erchunchi_loaded():
    """二沉池模组已加载并注册"""
    from mods.mod_manager import get_mod_manager

    mgr = get_mod_manager()
    mgr.load_all()
    cls = mgr.get_node_class("erchunchi")
    assert cls is not None, "erchunchi not registered"
    assert cls.__name__ == "ErchunchiNode"


def test_erchunchi_calculate():
    """标量计算不报错"""
    node = _get_node()
    flow = WaterFlow()
    quality = WaterQuality()
    result, d_flow, d_qual = node.execute(flow, quality)
    assert result.success, f"Failed: {result.error_msg}"


def test_erchunchi_solution_space():
    """方案空间枚举产生可行方案"""
    from models.solution_space import get_engine

    flow = WaterFlow()
    quality = WaterQuality()
    engine = get_engine()
    sols = engine.enumerate("erchunchi", flow, quality)
    assert len(sols) > 0, "No feasible solutions"
    best = max(sols, key=lambda s: s.robustness)
    assert best.robustness > 0, "Robustness should be > 0"
    assert best.cost_wan_yuan > 0, "Cost should be > 0"
    assert len(best.checks) >= 5, f"Expected >=5 checks, got {len(best.checks)}"


def test_erchunchi_serialization_roundtrip():
    """序列化往返: to_dict → from_dict 保持数据一致"""
    node = _get_node()
    flow = WaterFlow()
    quality = WaterQuality()
    node.execute(flow, quality)

    d = node.to_dict()
    restored = type(node).from_dict(d)

    assert restored.node_id == node.node_id
    assert restored.NODE_TYPE == node.NODE_TYPE
    for key, val in node._params.items():
        assert (
            abs(restored._params.get(key, 0) - val) < 1e-9
        ), f"param {key} mismatch: {restored._params.get(key)} vs {val}"


def test_erchunchi_vectorized_shape():
    """向量化输出 dtype 包含约束和尺寸字段"""
    node = _get_node()
    from models.discretization import get_config

    cfg = get_config("erchunchi")
    flow, quality = WaterFlow(), WaterQuality()
    grid = {k: np.array([cfg["free"][k][0]]) for k in cfg["free"]}
    fixed = cfg.get("fixed", {})
    vec = type(node)._vectorized_compute(grid, flow, quality, fixed)
    assert len(vec) == 1
    assert "concrete_m3" in vec.dtype.names
    for ck in cfg.get("constraint_keys", []):
        assert f"ok_{ck}" in vec.dtype.names, f"missing ok_{ck}"
        assert f"val_{ck}" in vec.dtype.names, f"missing val_{ck}"


def test_erchunchi_all_constraints_present():
    """所有约束的 ok_*/val_* 字段存在（不强制通过，因默认值组合可能不满足）"""
    import numpy as np

    node = _get_node()
    from models.discretization import get_config

    cfg = get_config("erchunchi")
    flow, quality = WaterFlow(), WaterQuality()
    free_keys = list(cfg.get("free", {}).keys())
    grid = {}
    for k in free_keys:
        vals = cfg["free"][k]
        grid[k] = np.array([vals[0]], dtype=float)
    fixed = cfg.get("fixed", {})
    vec = type(node)._vectorized_compute(grid, flow, quality, fixed)
    assert len(vec) == 1, f"expected 1 result, got {len(vec)}"
    missing = []
    for ck in cfg.get("constraint_keys", []):
        for prefix in ("ok_", "val_"):
            field = f"{prefix}{ck}"
            if field not in vec.dtype.names:
                missing.append(field)
    assert not missing, f"缺少约束字段: {missing}"
