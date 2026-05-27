"""Unit tests for kw_tiaojiechi (矿井水调节池)."""
import pytest
import numpy as np


class TestKwTiaojiechi:
    @pytest.fixture
    def node(self):
        from mods.mod_manager import get_mod_manager
        mgr = get_mod_manager()
        mgr.load_all()
        cls = mgr.load_mod("kw_tiaojiechi")
        if cls is None:
            pytest.skip("kw_tiaojiechi mod not loaded")
        return cls()

    def test_node_creation(self, node):
        assert node.NODE_TYPE == "kw_tiaojiechi"
        assert "调节" in node.NODE_NAME

    def test_calculate_success(self, node, sample_flow, sample_quality):
        result, _, _ = node.execute(sample_flow, sample_quality)
        assert result.success, f"Failed: {result.error_msg}"

    def test_calculate_produces_dimensions(self, node, sample_flow, sample_quality):
        result, _, _ = node.execute(sample_flow, sample_quality)
        assert len(result.dimensions) > 0

    def test_param_defaults(self, node):
        assert node.get_param("n") >= 2
