"""Unit tests for ziwai (紫外消毒池)."""
import pytest
import numpy as np


class TestZiwai:
    @pytest.fixture
    def node(self):
        from mods.mod_manager import get_mod_manager
        mgr = get_mod_manager(); mgr.load_all()
        cls = mgr.load_mod("ziwai")
        if cls is None: pytest.skip("mod not loaded")
        return cls()

    def test_node_creation(self, node):
        assert node.NODE_TYPE == "ziwai"
        assert "紫外" in node.NODE_NAME or "UV" in node.NODE_NAME.upper()

    def test_calculate_success(self, node, sample_flow, sample_quality):
        result, _, _ = node.execute(sample_flow, sample_quality)
        assert result.success, f"Failed: {result.error_msg}"

    def test_no_removal(self, node):
        """紫外消毒不应有污染物去除率"""
        rates = node.get_removal_rates()
        for pollutant, rate in rates.items():
            assert rate == 0.0, f"{pollutant} 不应被紫外去除"

    def test_produces_uv_checks(self, node, sample_flow, sample_quality):
        result, _, _ = node.execute(sample_flow, sample_quality)
        checks_text = " ".join(result.checks.keys())
        assert "剂量" in checks_text or "流速" in checks_text or "dose" in checks_text.lower()
