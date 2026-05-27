"""
test_cost_estimator.py — TDD tests for cost estimator data source fix

Verifies that CostEstimator correctly uses the results dict from
executor.execute() when available, falling back to node.result otherwise.
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ddesign_tool", "src"))

from models.base import NodeBase, NodeResult, NodeState, WaterFlow, WaterQuality
from models.cost.cost_estimator import CostEstimator, EstimateResult, BOQItem


# ── Mock node with controllable result ──

class _MockNode(NodeBase):
    """Minimal node subclass for testing cost estimation."""
    NODE_TYPE = "tiaojiechi"
    NODE_NAME = "调节池"
    NODE_CATEGORY = "预处理"

    def __init__(self, node_id="mock-001"):
        super().__init__(node_id=node_id)
        # 构造标准尺寸维度 (调节池矩形的 L/B/H/n)
        self._result = NodeResult(success=True, params={"n": 2, "HRT": 4.0})
        self._result.add_dimension("池数", 2, "座")
        self._result.add_dimension("池长 L", 12.0, "m")
        self._result.add_dimension("池宽 B", 6.0, "m")
        self._result.add_dimension("总高度 H", 5.0, "m")
        self._result.add_dimension("有效水深 h2", 3.5, "m")
        self._state = NodeState.CLEAN

    def calculate(self, flow, quality):
        return self._result


class _MockExecutor:
    """Minimal executor for testing."""
    def __init__(self):
        self._nodes = {}

    def add_node(self, node):
        self._nodes[node.node_id] = node


# ── Fixtures ──

@pytest.fixture
def mock_node():
    return _MockNode()


@pytest.fixture
def mock_executor(mock_node):
    ex = _MockExecutor()
    ex.add_node(mock_node)
    return ex


@pytest.fixture
def estimator():
    return CostEstimator()


# ═══════════════════════════════════════════════
# Tests: estimate() with and without results dict
# ═══════════════════════════════════════════════

class TestEstimateWithResults:
    """estimate() receives an optional results dict."""

    def test_with_results_dict_uses_results_data(self, mock_executor, mock_node, estimator):
        """When results dict is provided, it should be used as data source."""
        result_from_execute = NodeResult(success=True, params={"n": 3})
        result_from_execute.add_dimension("池数", 3, "座")
        result_from_execute.add_dimension("池长 L", 15.0, "m")
        result_from_execute.add_dimension("池宽 B", 8.0, "m")
        result_from_execute.add_dimension("总高度 H", 5.5, "m")

        results = {mock_node.node_id: result_from_execute}

        est = estimator.estimate(mock_executor, results=results)

        # Should have generated cost items
        civil_items = [i for i in est.items if i.category == "建筑工程"
                       and i.node_type == "tiaojiechi"]
        assert len(civil_items) > 0, "Should generate civil cost items from results dict"

    def test_without_results_dict_falls_back_to_node(self, mock_executor, mock_node, estimator):
        """Without results dict, falls back to node.result."""
        est = estimator.estimate(mock_executor)

        civil_items = [i for i in est.items if i.category == "建筑工程"
                       and i.node_type == "tiaojiechi"]
        assert len(civil_items) > 0, "Should fall back to node.result"

    def test_results_dict_overrides_none_node_result(self, mock_executor, mock_node, estimator):
        """When node._result is None but results dict has data, should succeed."""
        mock_node._result = None  # Simulate missing cache

        result_from_execute = NodeResult(success=True, params={"n": 2})
        result_from_execute.add_dimension("池数", 2, "座")
        result_from_execute.add_dimension("池长 L", 12.0, "m")
        result_from_execute.add_dimension("池宽 B", 6.0, "m")
        result_from_execute.add_dimension("总高度 H", 5.0, "m")

        results = {mock_node.node_id: result_from_execute}

        est = estimator.estimate(mock_executor, results=results)

        civil_items = [i for i in est.items if i.category == "建筑工程"
                       and i.node_type == "tiaojiechi"]
        assert len(civil_items) > 0, (
            "Should use results dict when node._result is None"
        )

    def test_failed_result_in_results_dict_is_skipped(self, mock_executor, mock_node, estimator):
        """Results dict with success=False should be skipped."""
        result_from_execute = NodeResult(success=False, error_msg="Mock failure")
        results = {mock_node.node_id: result_from_execute}

        est = estimator.estimate(mock_executor, results=results)

        civil_items = [i for i in est.items if i.category == "建筑工程"
                       and i.node_type == "tiaojiechi"]
        assert len(civil_items) == 0, "Failed results should be skipped"


# ═══════════════════════════════════════════════
# Tests: _structure_civil() with explicit result
# ═══════════════════════════════════════════════

class TestStructureCivilWithResult:
    """_structure_civil() accepts optional result parameter."""

    def test_with_explicit_result_uses_it(self, mock_node, estimator):
        """When result is provided, use its dimensions."""
        explicit_result = NodeResult(success=True, params={})
        explicit_result.add_dimension("池径 D", 20.0, "m")  # 圆形池 → _circular_tank
        explicit_result.add_dimension("总高度 H", 5.0, "m")
        explicit_result.add_dimension("池数", 1, "座")

        items = estimator._structure_civil(mock_node, result=explicit_result)

        civil_items = [i for i in items if i.category == "建筑工程"]
        assert len(civil_items) > 0, "Should use explicit result dimensions"

    def test_without_result_falls_back_to_node(self, mock_node, estimator):
        """Without result parameter, falls back to node.result."""
        items = estimator._structure_civil(mock_node)
        civil_items = [i for i in items if i.category == "建筑工程"]
        assert len(civil_items) > 0, "Should fall back to node.result"

    def test_explicit_result_none_falls_back(self, mock_node, estimator):
        """Explicit result=None plus valid node.result should still work."""
        items = estimator._structure_civil(mock_node, result=None)
        civil_items = [i for i in items if i.category == "建筑工程"]
        assert len(civil_items) > 0, "None result should fall back to node.result"

    def test_failed_explicit_result_returns_empty(self, mock_node, estimator):
        """Failed explicit result returns empty items."""
        failed_result = NodeResult(success=False)
        items = estimator._structure_civil(mock_node, result=failed_result)
        assert len(items) == 0, "Failed result should produce no items"


# ═══════════════════════════════════════════════
# Tests: _val() dimension extraction robustness
# ═══════════════════════════════════════════════

class TestValDimensionExtraction:
    """_val() extracts dimensions from various key formats."""

    def test_exact_chinese_key_match(self, estimator):
        dims = {"池长 L": (12.0, "m"), "池宽 B": (6.0, "m")}
        assert estimator._val(dims, "池长 L") == 12.0
        assert estimator._val(dims, "池宽 B") == 6.0

    def test_substring_match(self, estimator):
        """'池径 D' should be found via substring '池径' in key."""
        dims = {"池径 D": (20.0, "m")}
        assert estimator._val(dims, "池径 D") == 20.0

    def test_alias_fallback(self, estimator):
        """'池长' should match '单池长度 L' or '单格长度 L' via alias."""
        dims = {"单池长度 L": (10.0, "m")}
        assert estimator._val(dims, "池长 L") == 10.0

    def test_english_key_fallback(self, estimator):
        """Fall back to English keys for vectorized results."""
        dims = {"L": (15.0, "m"), "B": (8.0, "m"), "H_total": (5.0, "m")}
        assert estimator._val(dims, "池长 L") == 15.0
        assert estimator._val(dims, "池宽 B") == 8.0
        assert estimator._val(dims, "总高度 H") == 5.0

    def test_missing_key_returns_none(self, estimator):
        dims = {}
        assert estimator._val(dims, "池长 L") is None

    def test_geshan_special_keys(self, estimator):
        """格栅 uses 栅槽总长/栅槽宽度/栅后总高."""
        dims = {"栅槽总长 L": (8.0, "m"), "栅槽宽度 B": (2.0, "m"), "栅后总高 H": (3.0, "m")}
        # 需要构造 cugeshan 节点, 此处仅测试 _val 可用性
        assert estimator._val(dims, "栅槽总长 L") == 8.0
        assert estimator._val(dims, "栅槽宽度 B") == 2.0
        assert estimator._val(dims, "栅后总高 H") == 3.0


# ═══════════════════════════════════════════════
# Integration: full estimate() pipeline
# ═══════════════════════════════════════════════

class TestEstimateIntegration:
    """End-to-end test of the estimate pipeline."""

    def test_multiple_nodes_with_results_dict(self, estimator):
        """Multiple nodes in executor, each with result in results dict."""
        from models.base import NodeBase, NodeResult, NodeState

        class MultiMockNode(NodeBase):
            def __init__(self, node_id, ntype, name):
                super().__init__(node_id=node_id)
                self.NODE_TYPE = ntype
                self.NODE_NAME = name
                self._state = NodeState.CLEAN

            def calculate(self, flow, quality):
                return NodeResult(success=True)

        ex = _MockExecutor()
        n1 = MultiMockNode("n1", "tiaojiechi", "调节池")
        n2 = MultiMockNode("n2", "cugeshan", "粗格栅")
        n3 = MultiMockNode("n3", "cass", "CASS反应器")
        ex.add_node(n1); ex.add_node(n2); ex.add_node(n3)

        # results dict has data for n1 and n3 but NOT n2
        r1 = NodeResult(success=True, params={"n": 2})
        r1.add_dimension("池长 L", 12.0, "m")
        r1.add_dimension("池宽 B", 6.0, "m")
        r1.add_dimension("总高度 H", 5.0, "m")
        r1.add_dimension("池数", 2, "座")

        r3 = NodeResult(success=True, params={"n": 4})
        r3.add_dimension("池长 L", 20.0, "m")
        r3.add_dimension("池宽 B", 10.0, "m")
        r3.add_dimension("总高度 H", 5.5, "m")
        r3.add_dimension("池数", 4, "座")

        results = {"n1": r1, "n3": r3}

        est = estimator.estimate(ex, results=results)

        # n1 should have cost items (from results dict)
        n1_items = [i for i in est.items if i.node_type == "tiaojiechi"]
        assert len(n1_items) > 0, "n1 should have cost items from results dict"

        # n2 has no result → civil items skipped, but equipment items
        # may still appear (from EQUIPMENT dict in unit_prices.py)
        n2_civil = [i for i in est.items if i.node_type == "cugeshan"
                     and i.category == "建筑工程"]
        assert len(n2_civil) == 0, "n2 should have no civil items (no result)"

        # n3 should have cost items (from results dict)
        n3_items = [i for i in est.items if i.node_type == "cass"]
        assert len(n3_items) > 0, "n3 should have cost items from results dict"

    def test_cost_summary_values_are_reasonable(self, mock_executor, mock_node, estimator):
        """EstimateResult should have reasonable totals."""
        est = estimator.estimate(mock_executor, project_name="Test")
        assert est.project_name == "Test"
        assert est.civil_cost >= 0
        assert est.equip_cost >= 0
        assert est.total_cost > 0, "Total cost should be positive for a valid node"
