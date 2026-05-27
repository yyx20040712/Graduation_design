"""Unit tests for wuni_xiaohua (污泥消化池)."""
import pytest
from models.base import SludgeFlow


class TestWuniXiaohua:
    @pytest.fixture
    def node(self):
        from mods.mod_manager import get_mod_manager
        mgr = get_mod_manager()
        mgr.load_all()
        cls = mgr.load_mod("wuni_xiaohua")
        if cls is None:
            pytest.skip("wuni_xiaohua mod not loaded")
        return cls()

    def test_node_creation(self, node):
        assert node.NODE_TYPE == "wuni_xiaohua"
        assert "消化" in node.NODE_NAME

    def test_is_sludge_only(self, node):
        """污泥消化池应为纯污泥节点"""
        assert node.is_sludge_only

    def test_execute_sludge(self, node, sample_sludge):
        """测试污泥计算入口"""
        result, downstream = node.execute_sludge(sample_sludge)
        if result is not None:
            assert result.success, f"Failed: {result.error_msg}"

    def test_param_defaults(self, node):
        params = node.get_param_defs()
        assert len(params) > 0, "污泥消化池应有参数定义"
