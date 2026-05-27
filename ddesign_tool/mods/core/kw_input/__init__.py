"""
kw_input.py — 矿井水水源输入节点

煤炭矿井水处理的工艺起点.定义矿井涌水量和进水水质.
设计参数来源于 dlc.docx §4.1.2 原始数据.

输入端口: 无
输出端口: 1个 MIXED 端口(水量+水质)
"""

from typing import Dict, List, Optional

from models.base import (
    NodeBase,
    NodeResult,
    NodeState,
    WaterFlow,
    WaterQuality,
    ParamDef,
    Port,
    PortType,
)


class KwInputNode(NodeBase):
    """矿井水进水输入节点 — 定义矿井涌水量及进水水质"""

    NODE_TYPE = "kw_input"
    NODE_NAME = "矿井水输入"
    NODE_CATEGORY = "矿井水处理"

    @classmethod
    def _default_params(cls) -> Dict[str, float]:
        # 源自 dlc.docx §4.1.2
        # Q_design 由 Q_avg_daily / 86400 * Kz 自动计算,不再作为可调参数
        return {
            "Q_avg_daily": 43835.6,  # m³/d
            "Kz": 1.5,  # 总变化系数 (2739.8/1826.5)
            "SS_in": 800,
            "TDS": 1500,
            "pH": 7.5,
            "COD": 200,
            "BOD5": 30.0,
            "NH3N": 8.0,
            "TN": 12.0,
            "TP": 2.0,
        }

    def _build_param_defs(self) -> List[ParamDef]:
        return [
            ParamDef(
                "平均日涌水量",
                "Q_avg_daily",
                value=43835.6,
                default=43835.6,
                min_val=1000,
                max_val=500000,
                step=1,
                unit="m³/d",
                description="矿井平均日涌水量",
            ),
            ParamDef(
                "总变化系数 Kz",
                "Kz",
                value=1.5,
                default=1.5,
                min_val=1.0,
                max_val=3.0,
                step=0.1,
                unit="-",
                description="涌水量变化系数",
            ),
            ParamDef(
                "进水SS",
                "SS_in",
                value=800,
                default=800,
                min_val=100,
                max_val=3000,
                step=10,
                unit="mg/L",
                description="进水悬浮固体浓度",
            ),
            ParamDef(
                "进水COD",
                "COD",
                value=200,
                default=200,
                min_val=50,
                max_val=500,
                step=10,
                unit="mg/L",
                description="进水化学需氧量",
            ),
            ParamDef(
                "进水BOD5",
                "BOD5",
                value=30.0,
                default=30.0,
                min_val=5,
                max_val=200,
                step=5,
                unit="mg/L",
                description="进水五日生化需氧量",
            ),
            ParamDef(
                "进水NH3N",
                "NH3N",
                value=8.0,
                default=8.0,
                min_val=1.0,
                max_val=50.0,
                step=0.5,
                unit="mg/L",
                description="进水氨氮",
            ),
            ParamDef(
                "进水TN",
                "TN",
                value=12.0,
                default=12.0,
                min_val=2.0,
                max_val=60.0,
                step=1.0,
                unit="mg/L",
                description="进水总氮",
            ),
            ParamDef(
                "进水TP",
                "TP",
                value=2.0,
                default=2.0,
                min_val=0.5,
                max_val=10.0,
                step=0.1,
                unit="mg/L",
                description="进水总磷",
            ),
            ParamDef(
                "TDS",
                "TDS",
                value=1500,
                default=1500,
                min_val=500,
                max_val=5000,
                step=50,
                unit="mg/L",
                description="总溶解固体(不作去除率传递)",
            ),
            ParamDef(
                "pH",
                "pH",
                value=7.5,
                default=7.5,
                min_val=5.0,
                max_val=9.0,
                step=0.1,
                unit="-",
                description="进水酸碱度",
            ),
        ]

    def _init_ports(self) -> None:
        self.input_ports = []
        self.output_ports = [
            Port(
                port_id=f"{self.node_id}-out",
                name="出水(水量+水质)",
                port_type=PortType.MIXED,
                direction="output",
                node_id=self.node_id,
            )
        ]

    def __init__(self, node_id: Optional[str] = None):
        super().__init__(node_id)
        # 默认矿井水水质(高SS、含煤粉,源自 dlc.docx 表4-2)
        self.water_quality = WaterQuality(
            BOD5=self.get_param("BOD5"),
            COD=self.get_param("COD"),
            SS=self.get_param("SS_in"),
            NH3N=self.get_param("NH3N"),
            TN=self.get_param("TN"),
            TP=self.get_param("TP"),
            pH=self.get_param("pH"),
        )

    def set_water_quality(self, **kwargs: float) -> None:
        param_map = {"SS": "SS_in"}
        for key, value in kwargs.items():
            if hasattr(self.water_quality, key):
                setattr(self.water_quality, key, value)
                param_key = param_map.get(key, key)
                if param_key in self._params:
                    self._params[param_key] = value
        self.state = NodeState.DIRTY

    def calculate(self, flow: WaterFlow, quality: WaterQuality) -> NodeResult:
        Qad = self.get_param("Q_avg_daily")
        Kz = self.get_param("Kz")
        # Q_design 由 Q_avg_daily / 86400 * Kz 自动计算
        Qd = Qad / 86400.0 * Kz

        # Sync water_quality from adjustable params
        self.water_quality.BOD5 = self.get_param("BOD5")
        self.water_quality.COD = self.get_param("COD")
        self.water_quality.SS = self.get_param("SS_in")
        self.water_quality.NH3N = self.get_param("NH3N")
        self.water_quality.TN = self.get_param("TN")
        self.water_quality.TP = self.get_param("TP")
        self.water_quality.pH = self.get_param("pH")

        flow_out = WaterFlow(Q_design=Qd, Q_avg_daily=Qad, Kz=Kz)

        result = NodeResult(success=True)
        result.params = {
            "Q_design": Qd,
            "Q_avg_daily": Qad,
            "Kz": Kz,
            "SS_in": self.get_param("SS_in"),
            "TDS": self.get_param("TDS"),
            "pH": self.get_param("pH"),
            "COD": self.get_param("COD"),
            "BOD5": self.get_param("BOD5"),
            "NH3N": self.get_param("NH3N"),
            "TN": self.get_param("TN"),
            "TP": self.get_param("TP"),
        }
        result.add_dimension("设计流量", round(Qd, 4), "m³/s")
        result.add_dimension("平均日涌水量", Qad, "m³/d")
        result.add_dimension("平均时涌水量", flow_out.Q_avg_hourly, "m³/h")
        result.add_dimension("变化系数", Kz, "")
        result.add_dimension("进水TDS", self.get_param("TDS"), "mg/L")

        wq = self.water_quality
        for attr in ["BOD5", "COD", "SS", "NH3N", "TN", "TP"]:
            val = getattr(wq, attr)
            result.add_dimension(f"进水{attr}", val, "mg/L")

        return result

    def execute(self, flow: WaterFlow, quality: WaterQuality):
        """重写 execute: 输出流量使用节点设定值而非上游输入"""
        from models.base import NodeState, WaterQuality as WQ

        self.state = NodeState.COMPUTING
        try:
            result = self.calculate(flow, quality)
            self._result = result
            if result.success:
                self.state = NodeState.CLEAN
                Qad = self.get_param("Q_avg_daily")
                Kz = self.get_param("Kz")
                # Q_design 由 Q_avg_daily / 86400 * Kz 自动计算
                Qd = Qad / 86400.0 * Kz
                out_flow = WaterFlow(Q_design=Qd, Q_avg_daily=Qad, Kz=Kz)
                downstream_quality = WQ(
                    BOD5=self.water_quality.BOD5,
                    COD=self.water_quality.COD,
                    SS=self.water_quality.SS,
                    NH3N=self.water_quality.NH3N,
                    TN=self.water_quality.TN,
                    TP=self.water_quality.TP,
                    pH=self.water_quality.pH,
                )
                result.inlet_quality = (
                    WQ(
                        BOD5=quality.BOD5,
                        COD=quality.COD,
                        SS=quality.SS,
                        NH3N=quality.NH3N,
                        TN=quality.TN,
                        TP=quality.TP,
                        pH=quality.pH,
                    )
                    if hasattr(quality, "BOD5")
                    else None
                )
                result.outlet_quality = downstream_quality
                return result, out_flow, downstream_quality
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
    def from_dict(cls, d: Dict) -> "KwInputNode":
        node = cls(node_id=d["id"])
        node.x = d["position"]["x"]
        node.y = d["position"]["y"]
        for key, value in d.get("params", {}).items():
            node._params[key] = value
        if "water_quality" in d:
            node.water_quality = WaterQuality.from_dict(d["water_quality"])
        return node
