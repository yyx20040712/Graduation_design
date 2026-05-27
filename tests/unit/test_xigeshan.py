"""Unit tests for xigeshan (细格栅)."""
import pytest


class TestXigeshan:
    @pytest.fixture
    def node(self):
        from mods.mod_manager import get_mod_manager
        mgr = get_mod_manager(); mgr.load_all()
        cls = mgr.load_mod("xigeshan")
        if cls is None: pytest.skip("mod not loaded")
        return cls()

    def test_node_creation(self, node):
        assert node.NODE_TYPE == "xigeshan"
        assert "细格栅" in node.NODE_NAME or "格栅" in node.NODE_NAME

    def test_calculate_success(self, node, sample_flow, sample_quality):
        result, _, _ = node.execute(sample_flow, sample_quality)
        assert result.success, f"Failed: {result.error_msg}"

    def test_smaller_gap_than_coarse(self, node):
        """细格栅栅条间隙应小于粗格栅"""
        params = node.get_param_defs()
        b_param = next((d for d in params if d.key == "b"), None)
        if b_param:
            assert b_param.max_val <= 10, "细格栅间隙应≤10mm"
