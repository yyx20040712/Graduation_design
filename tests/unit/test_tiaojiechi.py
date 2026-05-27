"""Unit tests for tiaojiechi (调节池)."""
import pytest
import numpy as np


class TestTiaojiechi:
    @pytest.fixture
    def node(self):
        from mods.mod_manager import get_mod_manager
        mgr = get_mod_manager(); mgr.load_all()
        cls = mgr.load_mod("tiaojiechi")
        if cls is None: pytest.skip("mod not loaded")
        return cls()

    def test_node_creation(self, node):
        assert node.NODE_TYPE == "tiaojiechi"
        assert "调节池" in node.NODE_NAME

    def test_calculate_success(self, node, sample_flow, sample_quality):
        result, _, _ = node.execute(sample_flow, sample_quality)
        assert result.success, f"Failed: {result.error_msg}"

    def test_param_n_range(self, node):
        n_defs = node.get_param_defs()
        n_param = next((d for d in n_defs if d.key == "n"), None)
        if n_param:
            assert 2 <= n_param.min_val <= n_param.max_val <= 8

    def test_no_removal(self, node):
        """调节池不改变水质"""
        rates = node.get_removal_rates()
        for pollutant, rate in rates.items():
            assert rate == 0.0, f"{pollutant} 不应被调节池去除"
