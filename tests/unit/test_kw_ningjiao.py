"""Unit tests for kw_ningjiao (矿井水混凝反应器)."""
import pytest


class TestKwNingjiao:
    @pytest.fixture
    def node(self):
        from mods.mod_manager import get_mod_manager
        mgr = get_mod_manager(); mgr.load_all()
        cls = mgr.load_mod("kw_ningjiao")
        if cls is None: pytest.skip("mod not loaded")
        return cls()

    def test_node_creation(self, node):
        assert node.NODE_TYPE == "kw_ningjiao"
        assert "混凝" in node.NODE_NAME or "反应" in node.NODE_NAME

    def test_calculate_success(self, node, sample_flow, sample_quality):
        result, _, _ = node.execute(sample_flow, sample_quality)
        assert result.success, f"Failed: {result.error_msg}"

    def test_calculate_produces_dimensions(self, node, sample_flow, sample_quality):
        result, _, _ = node.execute(sample_flow, sample_quality)
        assert len(result.dimensions) > 0, "应产生构筑物尺寸"
