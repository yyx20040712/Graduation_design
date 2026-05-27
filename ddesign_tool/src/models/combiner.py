"""
combiner.py — 流量水质合并节点

将独立的 WATER 端口(来自管网输入)和 QUALITY 端口(来自水质节点)
合并为 MIXED 端口,送入处理单元.
"""

from typing import Dict, List

from .base import (
    NodeBase,
    NodeResult,
    ParamDef,
    Port,
    PortType,
    WaterFlow,
    WaterQuality,
)


class CombinerNode(NodeBase):
    """合并节点 — WATER + QUALITY → MIXED

    输入端口:
      - water_in (WATER): 来自管网输入的水量
      - quality_in (QUALITY): 来自水质节点的水质

    输出端口:
      - mixed_out (MIXED): 合并后的水量+水质
    """

    NODE_TYPE = "combiner"
    NODE_NAME = "水量水质合并"
    NODE_CATEGORY = "输入/输出"

    @classmethod
    def _default_params(cls) -> Dict[str, float]:
        return {}

    def _build_param_defs(self) -> List[ParamDef]:
        return []

    def _init_ports(self) -> None:
        self.input_ports = [
            Port(
                port_id=f"{self.node_id}-win",
                name="水量",
                port_type=PortType.WATER,
                direction="input",
                node_id=self.node_id,
            ),
            Port(
                port_id=f"{self.node_id}-qin",
                name="水质",
                port_type=PortType.QUALITY,
                direction="input",
                node_id=self.node_id,
            ),
        ]
        self.output_ports = [
            Port(
                port_id=f"{self.node_id}-mout",
                name="出水(水量+水质)",
                port_type=PortType.MIXED,
                direction="output",
                node_id=self.node_id,
            ),
        ]

    @classmethod
    def _default_removal_rates(cls) -> Dict[str, float]:
        return {}

    def calculate(self, flow: WaterFlow, quality: WaterQuality) -> NodeResult:
        """合并节点:直接透传上游数据"""
        result = NodeResult(success=True)
        result.params = {
            "Q_design": flow.Q_design,
            "Q_avg_daily": flow.Q_avg_daily,
            "Kz": flow.Kz,
        }

        result.add_dimension("设计流量", flow.Q_design, "m³/s")
        result.add_dimension("设计流量", flow.Q_design * 1000, "L/s")
        result.add_dimension("平均日流量", flow.Q_avg_daily, "m³/d")
        result.add_dimension("变化系数", flow.Kz, "")

        for attr in ["BOD5", "COD", "SS", "NH3N", "TN", "TP"]:
            val = getattr(quality, attr)
            result.add_dimension(f"进水{attr}", val, "mg/L")

        return result
