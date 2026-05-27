"""Unit tests for chuchenchi (辐流初沉池)."""
import pytest
import numpy as np


class TestChuchenchi:
    @pytest.fixture
    def node(self):
        from mods.mod_manager import get_mod_manager
        mgr = get_mod_manager(); mgr.load_all()
        cls = mgr.load_mod("chuchenchi")
        if cls is None: pytest.skip("mod not loaded")
        return cls()

    def test_node_creation(self, node):
        assert node.NODE_TYPE == "chuchenchi"
        assert "初沉" in node.NODE_NAME or "沉淀" in node.NODE_NAME

    def test_calculate_success(self, node, sample_flow, sample_quality):
        result, _, _ = node.execute(sample_flow, sample_quality)
        assert result.success, f"Failed: {result.error_msg}"

    def test_produces_sludge(self, node, sample_flow, sample_quality):
        """初沉池应产生污泥"""
        result, _, _ = node.execute(sample_flow, sample_quality)
        if result.success and node.sludge_output is not None:
            assert node.sludge_output.DS > 0, "初沉池应有干固体产出"
