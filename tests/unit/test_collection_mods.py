"""Unit tests for collection mods (集配水: 集水井/配水井/集配水井/配水渠)."""
import pytest


class TestJishuijing:
    @pytest.fixture
    def node(self):
        from mods.mod_manager import get_mod_manager
        mgr = get_mod_manager(); mgr.load_all()
        cls = mgr.load_mod("jishuijing")
        if cls is None: pytest.skip("mod not loaded")
        return cls()

    def test_node_creation(self, node):
        assert node.NODE_TYPE == "jishuijing"

    def test_calculate_success(self, node, sample_flow, sample_quality):
        result, _, _ = node.execute(sample_flow, sample_quality)
        assert result.success, f"Failed: {result.error_msg}"

    def test_calculate_produces_dimensions(self, node, sample_flow, sample_quality):
        result, _, _ = node.execute(sample_flow, sample_quality)
        assert len(result.dimensions) > 0


class TestPeishuijing:
    @pytest.fixture
    def node(self):
        from mods.mod_manager import get_mod_manager
        mgr = get_mod_manager(); mgr.load_all()
        cls = mgr.load_mod("peishuijing")
        if cls is None: pytest.skip("mod not loaded")
        return cls()

    def test_node_creation(self, node):
        assert node.NODE_TYPE == "peishuijing"

    def test_calculate_success(self, node, sample_flow, sample_quality):
        result, _, _ = node.execute(sample_flow, sample_quality)
        assert result.success, f"Failed: {result.error_msg}"


class TestJipeishuijing:
    @pytest.fixture
    def node(self):
        from mods.mod_manager import get_mod_manager
        mgr = get_mod_manager(); mgr.load_all()
        cls = mgr.load_mod("jipeishuijing")
        if cls is None: pytest.skip("mod not loaded")
        return cls()

    def test_node_creation(self, node):
        assert node.NODE_TYPE == "jipeishuijing"

    def test_calculate_success(self, node, sample_flow, sample_quality):
        result, _, _ = node.execute(sample_flow, sample_quality)
        assert result.success, f"Failed: {result.error_msg}"


class TestPeishuiqu:
    @pytest.fixture
    def node(self):
        from mods.mod_manager import get_mod_manager
        mgr = get_mod_manager(); mgr.load_all()
        cls = mgr.load_mod("peishuiqu")
        if cls is None: pytest.skip("mod not loaded")
        return cls()

    def test_node_creation(self, node):
        assert node.NODE_TYPE == "peishuiqu"

    def test_calculate_success(self, node, sample_flow, sample_quality):
        result, _, _ = node.execute(sample_flow, sample_quality)
        assert result.success, f"Failed: {result.error_msg}"
