"""
water_quality_node.py — 水质输入节点

独立设置进水水质,默认值为城市污水数据.
城市污水: BOD5=200, COD=400, SS=220, NH3N=35, TN=45, TP=5
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from models.base import (
    NodeBase,
    NodeResult,
    NodeState,
    ParamDef,
    Port,
    PortType,
    WaterFlow,
    WaterQuality,
)


class WaterQualityNode(NodeBase):
    """水质输入节点 — 用户设定进水水质参数

    提供 6 项水质指标的滑块调节: BOD5, COD, SS, NH3N, TN, TP
    """

    NODE_TYPE = "water_quality"
    NODE_NAME = "进水水质"
    NODE_CATEGORY = "输入/输出"

    def __init__(self, node_id: Optional[str] = None):
        super().__init__(node_id)
        self.water_quality = WaterQuality(
            BOD5=200.0,
            COD=400.0,
            SS=220.0,
            NH3N=35.0,
            TN=45.0,
            TP=5.0,
            pH=7.0,
        )
        self._sync_quality_to_params()

    def _sync_quality_to_params(self) -> None:
        """将 water_quality 的属性同步到 _params (使 set_param 生效)"""
        for attr in ["BOD5", "COD", "SS", "NH3N", "TN", "TP"]:
            self._params[attr] = getattr(self.water_quality, attr)

    @classmethod
    def _default_params(cls) -> Dict[str, float]:
        return {
            "BOD5": 200.0,
            "COD": 400.0,
            "SS": 220.0,
            "NH3N": 35.0,
            "TN": 45.0,
            "TP": 5.0,
        }

    def _build_param_defs(self) -> List[ParamDef]:
        return [
            ParamDef(
                "BOD5",
                "BOD5",
                value=200.0,
                default=200.0,
                min_val=50,
                max_val=500,
                step=1,
                unit="mg/L",
                description="五日生化需氧量",
            ),
            ParamDef(
                "COD",
                "COD",
                value=400.0,
                default=400.0,
                min_val=100,
                max_val=1000,
                step=1,
                unit="mg/L",
                description="化学需氧量",
            ),
            ParamDef(
                "SS",
                "SS",
                value=220.0,
                default=220.0,
                min_val=50,
                max_val=600,
                step=1,
                unit="mg/L",
                description="悬浮固体",
            ),
            ParamDef(
                "NH3N",
                "NH3N",
                value=35.0,
                default=35.0,
                min_val=5,
                max_val=80,
                step=0.5,
                unit="mg/L",
                description="氨氮",
            ),
            ParamDef(
                "TN",
                "TN",
                value=45.0,
                default=45.0,
                min_val=10,
                max_val=100,
                step=0.5,
                unit="mg/L",
                description="总氮",
            ),
            ParamDef(
                "TP",
                "TP",
                value=5.0,
                default=5.0,
                min_val=1,
                max_val=20,
                step=0.1,
                unit="mg/L",
                description="总磷",
            ),
        ]

    @classmethod
    def _default_removal_rates(cls) -> Dict[str, float]:
        return {}

    def _init_ports(self) -> None:
        self.output_ports.append(
            Port(
                port_id=f"{self.node_id}-out",
                name="水质输出",
                port_type=PortType.QUALITY,
                direction="output",
                node_id=self.node_id,
            )
        )

    def set_param(self, key: str, value: float) -> None:
        """重写 set_param, 同步更新 water_quality 对象"""
        super().set_param(key, value)
        if hasattr(self.water_quality, key):
            setattr(self.water_quality, key, value)

    def reset_params(self) -> None:
        """重写 reset_params, 同步重置 water_quality"""
        super().reset_params()
        for attr in ["BOD5", "COD", "SS", "NH3N", "TN", "TP"]:
            if attr in self._params:
                setattr(self.water_quality, attr, self._params[attr])

    def calculate(self, flow: WaterFlow, quality: WaterQuality) -> NodeResult:
        """返回当前水质设定"""
        result = NodeResult()
        wq = self.water_quality
        result.params = {
            attr: getattr(wq, attr)
            for attr in ["BOD5", "COD", "SS", "NH3N", "TN", "TP"]
        }
        for attr in ["BOD5", "COD", "SS", "NH3N", "TN", "TP"]:
            result.add_dimension(f"进水{attr}", round(getattr(wq, attr), 2), "mg/L")
        return result

    def execute(
        self, flow: WaterFlow, quality: WaterQuality
    ) -> Tuple[Optional[NodeResult], WaterFlow, WaterQuality]:
        """重写 execute: 使用自身水质而非上游合并结果"""
        self.state = NodeState.COMPUTING
        try:
            result = self.calculate(flow, quality)
            self._result = result
            if result.success:
                self.state = NodeState.CLEAN
                # 下游水质 = 用户设定的进水水质
                downstream_quality = WaterQuality(
                    BOD5=self.water_quality.BOD5,
                    COD=self.water_quality.COD,
                    SS=self.water_quality.SS,
                    NH3N=self.water_quality.NH3N,
                    TN=self.water_quality.TN,
                    TP=self.water_quality.TP,
                    pH=7.0,
                )
                result.inlet_quality = WaterQuality()  # 进水水质节点无上游
                result.outlet_quality = downstream_quality
                # 更新维度
                for attr in ["BOD5", "COD", "SS", "NH3N", "TN", "TP"]:
                    val = getattr(downstream_quality, attr)
                    result.add_dimension(f"进水{attr}", round(val, 2), "mg/L")
                return (
                    result,
                    WaterFlow(Q_design=0.0, Q_avg_daily=0.0, Kz=1.0),
                    downstream_quality,
                )
            else:
                self.state = NodeState.ERROR
                return result, flow, quality
        except Exception as e:
            self.state = NodeState.ERROR
            failed = NodeResult.failed(str(e))
            self._result = failed
            return failed, flow, quality

    def to_dict(self) -> Dict:
        d = super().to_dict()
        d["water_quality"] = self.water_quality.to_dict()
        return d

    @classmethod
    def from_dict(cls, d: Dict) -> "WaterQualityNode":
        node = cls(node_id=d["id"])
        node.x = d["position"]["x"]
        node.y = d["position"]["y"]
        for key, value in d.get("params", {}).items():
            node._params[key] = value
            if hasattr(node.water_quality, key):
                setattr(node.water_quality, key, value)
        for key, value in d.get("removal_rates", {}).items():
            node._removal_rates[key] = value
        cached = d.get("cached_result")
        if cached:
            inlet_q = cached.get("inlet_quality")
            outlet_q = cached.get("outlet_quality")
            node._result = NodeResult(
                success=cached.get("success", True),
                params=cached.get("params", {}),
                dimensions={
                    k: tuple(v) for k, v in cached.get("dimensions", {}).items()
                },
                checks={k: tuple(v) for k, v in cached.get("checks", {}).items()},
                warnings=cached.get("warnings", []),
                error_msg=cached.get("error_msg", ""),
                removal_rates=cached.get("removal_rates", {}),
                inlet_quality=WaterQuality.from_dict(inlet_q) if inlet_q else None,
                outlet_quality=WaterQuality.from_dict(outlet_q) if outlet_q else None,
            )
        state_name = d.get("state", "DIRTY")
        try:
            node._state = NodeState[state_name]
        except KeyError:
            node._state = NodeState.DIRTY
        return node
