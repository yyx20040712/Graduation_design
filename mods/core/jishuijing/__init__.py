"""jishuijing.py — 集水井 (Collection Well)"""

from __future__ import annotations
import math
from typing import Dict, List, Tuple
import numpy as np
from models.base import (
    NodeBase,
    NodeResult,
    WaterFlow,
    WaterQuality,
    ParamDef,
    Port,
    PortType,
)


class JishuijingNode(NodeBase):
    """集水井 — 收集各来水管道污水,兼具水量调节和初步沉砂功能"""

    NODE_TYPE = "jishuijing"
    NODE_NAME = "集水井"
    NODE_CATEGORY = "集配水模组"

    @classmethod
    def _default_params(cls) -> Dict[str, float]:
        return {"HRT": 5.0, "h_eff": 3.0, "h_super": 0.5}

    def _build_param_defs(self) -> List[ParamDef]:
        return [
            ParamDef(
                "水力停留时间",
                "HRT",
                value=5.0,
                default=5.0,
                min_val=3.0,
                max_val=15.0,
                step=1.0,
                unit="min",
                description="GB50014: 宜3~5min",
            ),
            ParamDef(
                "有效水深",
                "h_eff",
                value=3.0,
                default=3.0,
                min_val=2.0,
                max_val=5.0,
                step=0.5,
                unit="m",
            ),
            ParamDef(
                "超高",
                "h_super",
                value=0.5,
                default=0.5,
                min_val=0.3,
                max_val=1.0,
                step=0.1,
                unit="m",
            ),
        ]

    def _init_ports(self) -> None:
        self.input_ports = [
            Port(
                port_id=f"{self.node_id}-in",
                name="进水",
                port_type=PortType.MIXED,
                direction="input",
                node_id=self.node_id,
            ),
        ]
        self.output_ports = [
            Port(
                port_id=f"{self.node_id}-out",
                name="出水",
                port_type=PortType.MIXED,
                direction="output",
                node_id=self.node_id,
            ),
        ]

    @classmethod
    def _default_removal_rates(cls) -> Dict[str, float]:
        return {"SS": 0.05, "BOD5": 0.0, "COD": 0.0, "NH3N": 0.0, "TN": 0.0, "TP": 0.0}

    def calculate(self, flow: WaterFlow, quality: WaterQuality) -> NodeResult:
        HRT = self.get_param("HRT")
        h_eff = self.get_param("h_eff")

        grid = {
            "HRT": np.array([HRT]),
            "h_eff": np.array([h_eff]),
        }

        fixed = {
            "h_super": self.get_param("h_super"),
        }

        r = type(self)._vectorized_compute(grid, flow, quality, fixed)
        d = r[0]

        result = NodeResult(success=True)
        result.params = {"HRT": HRT, "h_eff": h_eff, "h_super": self.get_param("h_super")}
        result.add_dimension("有效容积 V", round(float(d["V"]), 2), "m3")
        result.add_dimension("池长 L", round(float(d["L"]), 2), "m")
        result.add_dimension("池宽 B", d["B"], "m")
        result.add_dimension("总高度 H", round(float(d["H_total"]), 2), "m")
        result.add_dimension("有效水深", h_eff, "m")
        result.add_check(
            "水力停留时间 3~15 min", bool(d["ok_HRT"]), round(float(d["val_HRT"]), 1), "3~15", "min"
        )
        result.add_check(
            "有效水深 2.0~5.0 m", bool(d["ok_h_eff"]), round(float(d["val_h_eff"]), 1), "2.0~5.0", "m"
        )
        return result

    @classmethod
    def _vectorized_compute(
        cls, grid: dict, flow: WaterFlow, quality: WaterQuality, fixed: dict
    ) -> np.ndarray:
        HRT = grid["HRT"]
        h_eff = grid.get("h_eff", np.full(len(HRT), fixed.get("h_eff", 3.0)))
        h_super = fixed.get("h_super", 0.5)
        N = len(HRT)
        Q_max = flow.Q_design_as("m3/h")
        V = Q_max * HRT / 60.0
        A = np.where(h_eff > 0, V / h_eff, 0.0)
        L = np.sqrt(A)
        B = L
        H_total = h_eff + h_super
        concrete_m3 = 2 * (L + B) * 0.3 * H_total + L * B * 0.3
        ok_HRT = (3.0 <= HRT) & (HRT <= 15.0)
        ok_h_eff = (2.0 <= h_eff) & (h_eff <= 5.0)
        dtype = np.dtype(
            [
                ("V", np.float64),
                ("L", np.float64),
                ("B", np.float64),
                ("H_total", np.float64),
                ("H", np.float64),
                ("concrete_m3", np.float64),
                ("ok_HRT", np.bool_),
                ("ok_h_eff", np.bool_),
                ("val_HRT", np.float64),
                ("val_h_eff", np.float64),
            ]
        )
        result = np.empty(N, dtype=dtype)
        result["V"] = V
        result["L"] = L
        result["B"] = B
        result["H_total"] = H_total
        result["H"] = H_total
        result["concrete_m3"] = concrete_m3
        result["ok_HRT"] = ok_HRT
        result["ok_h_eff"] = ok_h_eff
        result["val_HRT"] = HRT
        result["val_h_eff"] = h_eff
        return result
