"""Unit tests for gaomidu (高密度沉淀池)."""
import pytest
import numpy as np
from models.base import WaterFlow, WaterQuality


class TestGaomidu:
    @pytest.fixture
    def node(self):
        from mods.mod_manager import get_mod_manager
        mgr = get_mod_manager()
        mgr.load_all()
        cls = mgr.load_mod("gaomidu")
        if cls is None:
            pytest.skip("gaomidu mod not loaded")
        return cls()

    def test_node_creation(self, node):
        assert node.NODE_TYPE == "gaomidu"
        assert "高密度" in node.NODE_NAME or "高密" in node.NODE_NAME

    def test_calculate_success(self, node, sample_flow, sample_quality):
        result, _, _ = node.execute(sample_flow, sample_quality)
        assert result.success, f"Failed: {result.error_msg}"

    def test_calculate_produces_dimensions(self, node, sample_flow, sample_quality):
        result, _, _ = node.execute(sample_flow, sample_quality)
        dim_keys = " ".join(result.dimensions.keys())
        assert "长度" in dim_keys or "池径" in dim_keys or "L" in dim_keys or "D" in dim_keys

    def test_vectorized_compute(self, node, sample_flow, sample_quality):
        try:
            import json, numpy as np
            with open("ddesign_tool/mods/core/gaomidu/discretization.json", encoding="utf-8") as f:
                cfg = json.load(f)
            grid = {k: np.array([v[0]]) for k, v in cfg["free"].items()}
            fixed = dict(cfg["fixed"])
            result = type(node)._vectorized_compute(grid, sample_flow, sample_quality, fixed)
            assert len(result) == 1
        except NotImplementedError:
            pytest.skip("_vectorized_compute not implemented")
