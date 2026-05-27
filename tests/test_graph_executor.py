"""test_graph_executor.py - DAG execution engine integration tests"""

from __future__ import annotations
import pytest
from models.base import WaterFlow, WaterQuality, NodeResult, NodeState
from controller.graph_executor import GraphExecutor


class TestGraphExecutor:

    @pytest.fixture
    def executor(self):
        return GraphExecutor()

    def test_empty_graph(self, executor):
        results = executor.execute()
        assert isinstance(results, dict)

    def test_single_node(self, test_node_class, executor):
        node = test_node_class()
        executor.add_node(node)
        results = executor.execute()
        assert node.node_id in results
        assert results[node.node_id].success is True

    def test_remove_node(self, executor, test_node_class):
        node = test_node_class(node_id="to_remove")
        executor.add_node(node)
        assert executor.get_node("to_remove") is not None
        executor.remove_node("to_remove")
        assert executor.get_node("to_remove") is None

    def test_two_node_chain(self, test_node_class, executor):
        up = test_node_class(node_id="up")
        down = test_node_class(node_id="down")
        executor.add_node(up)
        executor.add_node(down)
        executor.connect(up.output_ports[0], down.input_ports[0])
        results = executor.execute()
        assert "up" in results and "down" in results
        assert results["up"].success and results["down"].success

    def test_state_transitions(self, test_node_class, executor):
        node = test_node_class()
        assert node.state == NodeState.DIRTY
        executor.add_node(node)
        executor.execute()
        assert node.state == NodeState.CLEAN

    def test_dirty_mark(self, test_node_class, executor):
        node = test_node_class()
        executor.add_node(node)
        executor.execute()
        assert node.state == NodeState.CLEAN
        node.set_param("param_a", 5.0)
        assert node.state == NodeState.DIRTY

    def test_multiple_disconnected(self, test_node_class, executor):
        for i in range(3):
            executor.add_node(test_node_class(node_id=f"n{i}"))
        results = executor.execute()
        assert len(results) == 3

    def test_to_dict_empty(self, executor):
        d = executor.to_dict()
        assert "nodes" in d and "connections" in d
        assert len(d["nodes"]) == 0

    def test_to_dict_with_nodes(self, executor, test_node_class):
        up = test_node_class(node_id="up")
        down = test_node_class(node_id="down")
        executor.add_node(up); executor.add_node(down)
        executor.connect(up.output_ports[0], down.input_ports[0])
        d = executor.to_dict()
        assert len(d["nodes"]) == 2
        assert len(d["connections"]) == 1

    def test_default_factory_combiner(self):
        from controller.graph_executor import default_node_factory
        node = default_node_factory("combiner", {
            "id": "test-c", "type": "combiner",
            "position": {"x": 0, "y": 0},
        })
        assert node is not None
        assert node.NODE_TYPE == "combiner"

    def test_elevation_pass_handles_errors_gracefully(self, executor, test_node_class):
        """Ensure _execute_elevation_pass does not crash on missing module or exceptions."""
        node = test_node_class()
        node._result = NodeResult(success=True)
        node._result.add_dimension("长度", 10.0, "m")
        executor.add_node(node)
        # Execute: elevation pass runs internally, should not raise
        results = executor.execute(force_all=True)
        assert node.node_id in results
        # The key test: execute() returned without raising
        assert results[node.node_id].success is True

    def test_sludge_pass_handles_no_sludge_nodes(self, executor, test_node_class):
        """Ensure _execute_sludge_pass works when no sludge nodes exist."""
        node = test_node_class()
        executor.add_node(node)
        results = executor.execute(force_all=True)
        assert node.node_id in results
        assert results[node.node_id].success is True
