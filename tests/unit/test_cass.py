"""Unit tests for cass (CASS反应器)."""
import pytest
import numpy as np


class TestCASS:
    @pytest.fixture
    def node(self):
        from mods.mod_manager import get_mod_manager
        mgr = get_mod_manager(); mgr.load_all()
        cls = mgr.load_mod("cass")
        if cls is None: pytest.skip("mod not loaded")
        return cls()

    def test_node_creation(self, node):
        assert node.NODE_TYPE == "cass"
        assert "CASS" in node.NODE_NAME.upper()

    def test_calculate_success(self, node, sample_flow, sample_quality):
        result, _, _ = node.execute(sample_flow, sample_quality)
        assert result.success, f"Failed: {result.error_msg}"

    def test_removal_rates_high(self, node):
        rates = node.get_removal_rates()
        assert rates.get("BOD5", 0) >= 0.85
        assert rates.get("COD", 0) >= 0.80, "CASS应为高效生物处理"

    def test_produces_sludge(self, node, sample_flow, sample_quality):
        result, _, _ = node.execute(sample_flow, sample_quality)
        if result.success and node.sludge_output:
            assert node.sludge_output.DS > 0, "CASS应产生活性污泥"
