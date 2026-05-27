"""Unit tests for wuni_nongsuo (污泥浓缩池)."""
import pytest
from models.base import SludgeFlow


class TestWuniNongsuo:
    @pytest.fixture
    def node(self):
        from mods.mod_manager import get_mod_manager
        mgr = get_mod_manager(); mgr.load_all()
        cls = mgr.load_mod("wuni_nongsuo")
        if cls is None: pytest.skip("mod not loaded")
        return cls()

    def test_node_creation(self, node):
        assert node.NODE_TYPE == "wuni_nongsuo"
        assert "浓缩" in node.NODE_NAME

    def test_is_sludge_only(self, node):
        assert node.is_sludge_only, "浓缩池应为纯污泥节点"

    def test_execute_sludge(self, node, sample_sludge):
        result, downstream = node.execute_sludge(sample_sludge)
        if result is not None:
            assert result.success, f"Failed: {result.error_msg}"
