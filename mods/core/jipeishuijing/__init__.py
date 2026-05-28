"""jipeishuijing.py — 集配水井 (Collection & Distribution Well)"""

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
    GRAVITY,
)


class JipeishuijingNode(NodeBase):
    """集配水井 — 集水+配水组合构筑物"""

    NODE_TYPE = "jipeishuijing"
    NODE_NAME = "集配水井"
    NODE_CATEGORY = "集配水模组"

    @classmethod
    def _default_params(cls) -> Dict[str, float]:
        return {"n_out": 2, "h_weir": 0.3, "h_eff": 3.0, "h_super": 0.5, "HRT": 5.0}

    def _build_param_defs(self) -> List[ParamDef]:
        return [
            ParamDef(
                "出水方向数",
                "n_out",
                value=2,
                default=2,
                min_val=1,
                max_val=6,
                step=1,
                unit="个",
            ),
            ParamDef(
                "堰上水头",
                "h_weir",
                value=0.3,
                default=0.3,
                min_val=0.1,
                max_val=0.5,
                step=0.05,
                unit="m",
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
            ParamDef(
                "水力停留时间",
                "HRT",
                value=5.0,
                default=5.0,
                min_val=3.0,
                max_val=15.0,
                step=1.0,
                unit="min",
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
        n_out = int(self.get_param("n_out"))
        h_eff = self.get_param("h_eff")
        HRT = self.get_param("HRT")

        grid = {
            "n_out": np.array([n_out], dtype=np.float64),
            "HRT": np.array([HRT]),
            "h_eff": np.array([h_eff]),
        }

        fixed = {
            "h_super": self.get_param("h_super"),
        }

        r = type(self)._vectorized_compute(grid, flow, quality, fixed)
        d = r[0]

        result = NodeResult(success=True)
        result.params = {
            "n_out": n_out,
            "h_weir": self.get_param("h_weir"),
            "h_eff": h_eff,
            "h_super": self.get_param("h_super"),
            "HRT": HRT,
        }
        result.add_dimension("出水方向数", n_out, "个")
        result.add_dimension("堰上水头", self.get_param("h_weir"), "m")
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
        n_out = grid["n_out"].astype(np.int32)
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
