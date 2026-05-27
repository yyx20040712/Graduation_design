"""Unit tests for sludge mods (污泥处理线: 泵站/干化/合并/输送/脱水)."""
import pytest
from models.base import SludgeFlow


class TestWuniBengzhan:
    @pytest.fixture
    def node(self):
        from mods.mod_manager import get_mod_manager
        mgr = get_mod_manager(); mgr.load_all()
        cls = mgr.load_mod("wuni_bengzhan")
        if cls is None: pytest.skip("mod not loaded")
        return cls()

    def test_node_creation(self, node):
        assert node.NODE_TYPE == "wuni_bengzhan"

    def test_is_sludge_node(self, node):
        assert node.is_sludge_only, "污泥泵站应为纯污泥节点"

    def test_execute_sludge(self, node, sample_sludge):
        result, downstream = node.execute_sludge(sample_sludge)
        if result is not None:
            assert result.success, f"Failed: {result.error_msg}"


class TestWuniGanhua:
    @pytest.fixture
    def node(self):
        from mods.mod_manager import get_mod_manager
        mgr = get_mod_manager(); mgr.load_all()
        cls = mgr.load_mod("wuni_ganhua")
        if cls is None: pytest.skip("mod not loaded")
        return cls()

    def test_node_creation(self, node):
        assert node.NODE_TYPE == "wuni_ganhua"

    def test_is_sludge_node(self, node):
        assert node.is_sludge_only, "干化应为纯污泥节点"

    def test_execute_sludge(self, node, sample_sludge):
        result, downstream = node.execute_sludge(sample_sludge)
        if result is not None:
            assert result.success, f"Failed: {result.error_msg}"


class TestWuniHebing:
    @pytest.fixture
    def node(self):
        from mods.mod_manager import get_mod_manager
        mgr = get_mod_manager(); mgr.load_all()
        cls = mgr.load_mod("wuni_hebing")
        if cls is None: pytest.skip("mod not loaded")
        return cls()

    def test_node_creation(self, node):
        assert node.NODE_TYPE == "wuni_hebing"

    def test_is_sludge_node(self, node):
        assert node.is_sludge_only, "合并应为纯污泥节点"

    def test_execute_sludge(self, node, sample_sludge):
        result, downstream = node.execute_sludge(sample_sludge)
        if result is not None:
            assert result.success, f"Failed: {result.error_msg}"


class TestWuniShusong:
    @pytest.fixture
    def node(self):
        from mods.mod_manager import get_mod_manager
        mgr = get_mod_manager(); mgr.load_all()
        cls = mgr.load_mod("wuni_shusong")
        if cls is None: pytest.skip("mod not loaded")
        return cls()

    def test_node_creation(self, node):
        assert node.NODE_TYPE == "wuni_shusong"

    def test_is_sludge_node(self, node):
        assert node.is_sludge_only, "输送应为纯污泥节点"

    def test_execute_sludge(self, node, sample_sludge):
        result, downstream = node.execute_sludge(sample_sludge)
        if result is not None:
            assert result.success, f"Failed: {result.error_msg}"


class TestWuniTuoshui:
    @pytest.fixture
    def node(self):
        from mods.mod_manager import get_mod_manager
        mgr = get_mod_manager(); mgr.load_all()
        cls = mgr.load_mod("wuni_tuoshui")
        if cls is None: pytest.skip("mod not loaded")
        return cls()

    def test_node_creation(self, node):
        assert node.NODE_TYPE == "wuni_tuoshui"

    def test_is_sludge_node(self, node):
        assert node.is_sludge_only, "脱水应为纯污泥节点"

    def test_execute_sludge(self, node, sample_sludge):
        result, downstream = node.execute_sludge(sample_sludge)
        if result is not None:
            assert result.success, f"Failed: {result.error_msg}"
