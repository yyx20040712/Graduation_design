"""Unit tests for aao (AAO生物反应池)."""
import pytest
import numpy as np


class TestAAO:
    @pytest.fixture
    def node(self):
        from mods.mod_manager import get_mod_manager
        mgr = get_mod_manager()
        mgr.load_all()
        cls = mgr.load_mod("aao")
        if cls is None:
            pytest.skip("aao mod not loaded")
        return cls()

    def test_node_creation(self, node):
        assert node.NODE_TYPE == "aao"
        assert "AAO" in node.NODE_NAME.upper() or "A2O" in node.NODE_NAME.upper()

    def test_calculate_success(self, node, sample_flow, sample_quality):
        result, _, _ = node.execute(sample_flow, sample_quality)
        assert result.success, f"Failed: {result.error_msg}"

    def test_removal_rates_high(self, node):
        rates = node.get_removal_rates()
        assert rates.get("BOD5", 0) >= 0.85
        assert rates.get("COD", 0) >= 0.80

    def test_vectorized_compute(self, node, sample_flow, sample_quality):
        try:
            import json, numpy as np
            with open("ddesign_tool/mods/core/aao/discretization.json", encoding="utf-8") as f:
                cfg = json.load(f)
            grid = {k: np.array([v[0]]) for k, v in cfg["free"].items()}
            fixed = dict(cfg["fixed"])
            result = type(node)._vectorized_compute(grid, sample_flow, sample_quality, fixed)
            assert len(result) == 1
        except NotImplementedError:
            pytest.skip("_vectorized_compute not implemented")
