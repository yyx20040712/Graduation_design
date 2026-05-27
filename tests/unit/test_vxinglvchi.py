"""Unit tests for vxinglvchi (V型滤池)."""
import pytest
import numpy as np


class TestVxinglvchi:
    @pytest.fixture
    def node(self):
        from mods.mod_manager import get_mod_manager
        mgr = get_mod_manager()
        mgr.load_all()
        cls = mgr.load_mod("vxinglvchi")
        if cls is None:
            pytest.skip("vxinglvchi mod not loaded")
        return cls()

    def test_node_creation(self, node):
        assert node.NODE_TYPE == "vxinglvchi"
        assert "V型" in node.NODE_NAME or "滤池" in node.NODE_NAME

    def test_calculate_success(self, node, sample_flow, sample_quality):
        result, _, _ = node.execute(sample_flow, sample_quality)
        assert result.success, f"Failed: {result.error_msg}"

    def test_param_n_range(self, node):
        n_defs = node.get_param_defs()
        n_param = next((d for d in n_defs if d.key == "n"), None)
        if n_param:
            assert n_param.min_val >= 2

    def test_vectorized_compute(self, node, sample_flow, sample_quality):
        try:
            import json, numpy as np
            with open("ddesign_tool/mods/core/vxinglvchi/discretization.json", encoding="utf-8") as f:
                cfg = json.load(f)
            grid = {k: np.array([v[0]]) for k, v in cfg["free"].items()}
            fixed = dict(cfg["fixed"])
            result = type(node)._vectorized_compute(grid, sample_flow, sample_quality, fixed)
            assert len(result) == 1
        except NotImplementedError:
            pytest.skip("_vectorized_compute not implemented")
