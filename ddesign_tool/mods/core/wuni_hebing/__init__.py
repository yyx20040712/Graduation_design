"""污泥合并 — 多股污泥流汇集 (SLUDGE Combiner)"""
from typing import Dict, List, Tuple, Optional
from models.base import (
    NodeBase, NodeResult, SludgeFlow,
    Port, PortType,
)


class WuniHebingNode(NodeBase):
    """污泥合并节点 — 多股SLUDGE合并为一股

    类似水处理线的 Combiner,但专门用于 SLUDGE 端口.
    采用干固量加权平均合并各上游污泥参数.
    无计算参数,纯数据透传+合并.
    """
    NODE_TYPE = "wuni_hebing"
    NODE_NAME = "污泥合并"
    NODE_CATEGORY = "污泥处理"

    @classmethod
    def _default_params(cls) -> Dict[str, float]:
        return {}

    def _build_param_defs(self) -> List:
        return []

    def _init_ports(self) -> None:
        self.input_ports = [
            Port(port_id=f"{self.node_id}-s_in", name="污泥进(可多连)",
                 port_type=PortType.SLUDGE, direction="input",
                 node_id=self.node_id),
        ]
        self.output_ports = [
            Port(port_id=f"{self.node_id}-s_out", name="合并污泥",
                 port_type=PortType.SLUDGE, direction="output",
                 node_id=self.node_id),
        ]

    @classmethod
    def _default_removal_rates(cls) -> Dict[str, float]:
        return {}

    def calculate(self, flow, quality) -> NodeResult:
        return NodeResult(success=True)

    def execute_sludge(self, sludge: SludgeFlow) -> Tuple[Optional[NodeResult], SludgeFlow]:
        result = NodeResult(success=True)
        result.add_dimension("合并湿泥量", round(sludge.Q_wet, 2), "m3/d")
        result.add_dimension("合并干固量", round(sludge.DS, 1), "kg/d")
        result.add_dimension("合并含水率", round(sludge.P_moisture, 3), "")
        result.add_dimension("合并VS比", round(sludge.VS_ratio, 3), "")
        self._sludge_output = sludge
        return result, sludge

    @classmethod
    def _vectorized_compute(cls, grid, flow, quality, fixed):
        import numpy as np
        N = len(next(iter(grid.values())))
        return np.zeros(N, dtype=np.dtype([("dummy", np.float64)]))


__all__ = ["WuniHebingNode"]
