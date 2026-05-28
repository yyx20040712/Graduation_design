"""peishuiqu.py — 配水渠 (Distribution Channel)

规范: (4-174) A=B×h_eff, (4-175) v_actual=Q/A, (4-176) L=v_actual×60
"""

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


class PeishuiquNode(NodeBase):
    """配水渠 — 沿程配水明渠"""

    NODE_TYPE = "peishuiqu"
    NODE_NAME = "配水渠"
    NODE_CATEGORY = "集配水模组"

    @classmethod
    def _default_params(cls) -> Dict[str, float]:
        return {"B_channel": 0.8, "h_eff": 1.5, "h_super": 0.4, "n_out": 4}

    def _build_param_defs(self) -> List[ParamDef]:
        return [
            ParamDef(
                "渠宽 B",
                "B_channel",
                value=0.8,
                default=0.8,
                min_val=0.5,
                max_val=3.0,
                step=0.1,
                unit="m",
            ),
            ParamDef(
                "有效水深 h_eff",
                "h_eff",
                value=1.5,
                default=1.5,
                min_val=0.5,
                max_val=3.0,
                step=0.1,
                unit="m",
            ),
            ParamDef(
                "超高 h_super",
                "h_super",
                value=0.4,
                default=0.4,
                min_val=0.3,
                max_val=0.8,
                step=0.1,
                unit="m",
            ),
            ParamDef(
                "出水口数",
                "n_out",
                value=4,
                default=4,
                min_val=2,
                max_val=10,
                step=1,
                unit="个",
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
        return {"SS": 0.0, "BOD5": 0.0, "COD": 0.0, "NH3N": 0.0, "TN": 0.0, "TP": 0.0}

    def calculate(self, flow: WaterFlow, quality: WaterQuality) -> NodeResult:
        B_val = self.get_param("B_channel")
        h_eff = self.get_param("h_eff")
        n_out = int(self.get_param("n_out"))

        grid = {
            "B_channel": np.array([B_val]),
            "h_eff": np.array([h_eff]),
        }

        fixed = {
            "h_super": self.get_param("h_super"),
            "n_out": float(n_out),
        }

        r = type(self)._vectorized_compute(grid, flow, quality, fixed)
        d = r[0]

        result = NodeResult(success=True)
        result.params = {
            "B_channel": B_val,
            "h_eff": h_eff,
            "h_super": self.get_param("h_super"),
            "n_out": n_out,
        }
        result.add_dimension("渠宽 B", d["B"], "m", formula="B = 设计取值 (0.5~3.0m)")
        result.add_dimension(
            "有效水深 h_eff", d["h_eff"], "m", formula="h_eff = 设计取值 (0.5~3.0m)"
        )
        result.add_dimension("过水面积 A", round(float(d["A"]), 2), "m²", formula="A = B × h_eff")
        result.add_dimension(
            "实际流速 v_actual", round(float(d["v_actual"]), 3), "m/s", formula="v_actual = Q / A"
        )
        result.add_dimension("渠长 L", d["L"], "m", formula="L = v_actual × 60 (停留1min)")
        result.add_dimension(
            "总高度 H", round(float(d["H_total"]), 2), "m", formula="H = h_eff + h_super"
        )
        result.add_dimension("出水口数", n_out, "个")
        result.add_check(
            "渠内流速 0.3~1.2 m/s",
            bool(d["ok_v"]),
            round(float(d["val_v"]), 3),
            "0.3~1.2",
            "m/s",
        )
        result.add_check(
            "有效水深 0.5~3.0 m", bool(d["ok_h"]), round(float(d["val_h"]), 1), "0.5~3.0", "m"
        )
        result.add_check("渠宽 0.5~3.0 m", bool(d["ok_B"]), round(float(d["val_B"]), 1), "0.5~3.0", "m")
        return result

    @classmethod
    def _vectorized_compute(
        cls, grid: dict, flow: WaterFlow, quality: WaterQuality, fixed: dict
    ) -> np.ndarray:
        B = grid["B_channel"]
        h_eff = grid["h_eff"]
        h_super = fixed.get("h_super", 0.4)
        n_out = grid.get("n_out", np.full(len(B), fixed.get("n_out", 4)))
        N = len(B)
        Q = flow.Q_design

        A = B * h_eff
        v_actual = np.where(A > 0, Q / A, 0.0)
        L = np.ceil(v_actual * 60.0 / 0.5) * 0.5
        H_total = h_eff + h_super
        ok_v = (0.3 <= v_actual) & (v_actual <= 1.2)
        ok_h = (0.5 <= h_eff) & (h_eff <= 3.0)
        ok_B = (0.5 <= B) & (B <= 3.0)
        concrete_m3 = B * H_total * L * 0.3

        dtype = np.dtype(
            [
                ("B", np.float64),
                ("h_eff", np.float64),
                ("A", np.float64),
                ("v_actual", np.float64),
                ("L", np.float64),
                ("H_total", np.float64),
                ("H", np.float64),
                ("concrete_m3", np.float64),
                ("ok_v", np.bool_),
                ("ok_h", np.bool_),
                ("ok_B", np.bool_),
                ("val_v", np.float64),
                ("val_h", np.float64),
                ("val_B", np.float64),
            ]
        )
        arr = np.empty(N, dtype=dtype)
        arr["B"] = B
        arr["h_eff"] = h_eff
        arr["A"] = A
        arr["v_actual"] = v_actual
        arr["L"] = L
        arr["H_total"] = H_total
        arr["H"] = H_total
        arr["concrete_m3"] = concrete_m3
        arr["ok_v"] = ok_v
        arr["ok_h"] = ok_h
        arr["ok_B"] = ok_B
        arr["val_v"] = v_actual
        arr["val_h"] = h_eff
        arr["val_B"] = B
        return arr
