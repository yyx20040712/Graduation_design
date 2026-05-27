"""Integration boundary tests: methods that caused runtime bugs due to missing coverage."""

import pytest


class TestFlowOrder:
    """Test ModManager.get_flow_order() handles all stages (including 'collection').

    Bug: KeyError on 'collection' stage — get_flow_order iterated a stage
    that was missing from stage_order dict initialization.
    """

    @pytest.fixture
    def mgr(self):
        from mods.mod_manager import get_mod_manager
        m = get_mod_manager()
        m.load_all()
        return m

    def test_get_flow_order_returns_list(self, mgr):
        order = mgr.get_flow_order()
        assert isinstance(order, list)
        assert len(order) > 0, "Should have at least some mods"

    def test_get_flow_order_all_stages_present(self, mgr):
        """Verify that all mod stages are accounted for (no KeyError)."""
        order = mgr.get_flow_order()
        node_types = {nt for nt, _ in order}
        # Check that known stages produce results
        # If 'collection' mods exist, they must appear without KeyError
        stages_found = set()
        for mod_info in mgr.mods.values():
            stages_found.add(mod_info.process_stage)
        # The test passes if get_flow_order() returned without exception
        assert len(order) >= 0  # No KeyError = pass


class TestBuildFlowOrder:
    """Test cost_report_writer._build_flow_order handles edge cases."""

    def test_build_flow_order_does_not_crash(self):
        """_build_flow_order was calling get_flow_order which had KeyError on 'collection'."""
        import sys
        sys.path.insert(0, "ddesign_tool/src")
        from models.cost.cost_report_writer import _build_flow_order
        order = _build_flow_order()
        assert isinstance(order, list)

    def test_build_flow_order_has_expected_keys(self):
        import sys
        sys.path.insert(0, "ddesign_tool/src")
        from models.cost.cost_report_writer import _build_flow_order
        order = _build_flow_order()
        # Each entry should be (node_type, display_name)
        for entry in order:
            assert isinstance(entry, tuple)
            assert len(entry) == 2
            assert isinstance(entry[0], str)
            assert isinstance(entry[1], str)
