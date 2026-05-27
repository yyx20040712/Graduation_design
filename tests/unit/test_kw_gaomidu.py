"""Unit tests for kw_gaomidu (矿井水高密度沉淀池)."""
import pytest
import numpy as np


class TestKwGaomidu:
    @pytest.fixture
    def node(self):
        from mods.mod_manager import get_mod_manager
        mgr = get_mod_manager(); mgr.load_all()
        cls = mgr.load_mod("kw_gaomidu")
        if cls is None: pytest.skip("mod not loaded")
        return cls()

    def test_node_creation(self, node):
        assert node.NODE_TYPE == "kw_gaomidu"
        assert "高密" in node.NODE_NAME or "沉淀" in node.NODE_NAME

    def test_calculate_success(self, node, sample_flow, sample_quality):
        result, _, _ = node.execute(sample_flow, sample_quality)
        assert result.success, f"Failed: {result.error_msg}"

    def test_calculate_produces_dimensions(self, node, sample_flow, sample_quality):
        result, _, _ = node.execute(sample_flow, sample_quality)
        dim_keys = " ".join(result.dimensions.keys())
        assert "长度" in dim_keys or "池径" in dim_keys or "L" in dim_keys or "D" in dim_keys
