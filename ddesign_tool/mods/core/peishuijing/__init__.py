"""peishuijing.py — 配水井 (Distribution Well)

规范: 与集水井相同 (4-170)~(4-173), HRT 1~10min, h_eff 1.5~4.0m
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
    GRAVITY,
    PI,
)


class PeishuijingNode(NodeBase):
    """配水井 — HRT法确定井体尺寸 + 薄壁堰均匀配水"""

    NODE_TYPE = "peishuijing"
    NODE_NAME = "配水井"
    NODE_CATEGORY = "集配水模组"

    @classmethod
    def _default_params(cls) -> Dict[str, float]:
        return {"n_out": 2, "h_weir": 0.3, "HRT": 3.0, "h_eff": 2.5, "h_super": 0.5}

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
                "水力停留时间",
                "HRT",
                value=3.0,
                default=3.0,
                min_val=1.0,
                max_val=10.0,
                step=1.0,
                unit="min",
                description="GB50014: 配水井 1~10min",
            ),
            ParamDef(
                "有效水深",
                "h_eff",
                value=2.5,
                default=2.5,
                min_val=1.5,
                max_val=4.0,
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
        return {"SS": 0.0, "BOD5": 0.0, "COD": 0.0, "NH3N": 0.0, "TN": 0.0, "TP": 0.0}

    def calculate(self, flow: WaterFlow, quality: WaterQuality) -> NodeResult:
        n_out = int(self.get_param("n_out"))
        h_weir = self.get_param("h_weir")
        HRT = self.get_param("HRT")
        h_eff = self.get_param("h_eff")
        h_super = self.get_param("h_super")
        Q_max = flow.Q_design_as("m3/h")

        # ── (A) 有效容积 HRT法 (4-170) ──
        V = Q_max * HRT / 60.0  # m³
        # ── (B) 池体面积 (4-171) ──
        A = V / h_eff if h_eff > 0 else 0
        # ── (C) 井径 (圆形井, 4-172圆形版) ──
        D_HRT = math.sqrt(4 * A / PI) if A > 0 else 2.0

        # ── (D) 薄壁堰配水: b = Q / (n × m × √(2g) × H^(3/2)) ──
        m = 0.42
        b_weir = (
            Q_max / 3600.0 / (n_out * m * math.sqrt(2 * GRAVITY) * h_weir**1.5)
            if h_weir > 0
            else 0
        )  # m
        D_weir = b_weir * 1.5  # 井径取堰长的1.5倍

        # 井径取 HRT法和堰长法的较大值
        D = math.ceil(max(D_HRT, D_weir, 2.0) / 0.5) * 0.5
        # ── (E) 总高度 (4-173) ──
        H_total = h_eff + h_super

        result = NodeResult(success=True)
        result.params = {
            "n_out": n_out,
            "h_weir": h_weir,
            "HRT": HRT,
            "h_eff": h_eff,
            "h_super": h_super,
        }
        result.add_dimension("出水方向数", n_out, "个")
        result.add_dimension(
            "有效容积 V", round(V, 2), "m3", formula="V = Q_max × HRT / 60"
        )
        result.add_dimension("堰上水头", h_weir, "m")
        result.add_dimension(
            "井径 D", D, "m", formula="D = max(D_HRT, D_weir, 2.0), ceil 0.5m"
        )
        result.add_dimension(
            "总高度 H", round(H_total, 2), "m", formula="H = h_eff + h_super"
        )
        result.add_dimension("有效水深", h_eff, "m")
        result.add_check(
            "水力停留时间 1~10 min", 1.0 <= HRT <= 10.0, round(HRT, 1), "1~10", "min"
        )
        result.add_check(
            "有效水深 1.5~4.0 m", 1.5 <= h_eff <= 4.0, round(h_eff, 1), "1.5~4.0", "m"
        )
        result.add_check("井径 D >= 2.0 m", D >= 2.0, round(D, 1), ">= 2.0", "m")
        return result

    @classmethod
    def _vectorized_compute(
        cls, grid: dict, flow: WaterFlow, quality: WaterQuality, fixed: dict
    ) -> np.ndarray:
        n_out = grid["n_out"].astype(np.int32)
        h_weir = grid["h_weir"]
        HRT = grid.get("HRT", np.full(len(n_out), fixed.get("HRT", 3.0)))
        h_eff = grid.get("h_eff", np.full(len(n_out), fixed.get("h_eff", 2.5)))
        h_super = fixed.get("h_super", 0.5)
        N = len(n_out)
        PI_V = np.pi
        Q_max = flow.Q_design_as("m3/h")
        m = 0.42

        # HRT法
        V = Q_max * HRT / 60.0
        A_area = np.where(h_eff > 0, V / h_eff, 0.0)
        D_HRT = np.where(A_area > 0, np.sqrt(4 * A_area / PI_V), 2.0)
        # 堰长法
        b_weir = np.where(
            h_weir > 0,
            Q_max / 3600.0 / (n_out * m * np.sqrt(2 * GRAVITY) * h_weir**1.5),
            0.0,
        )
        D_weir = b_weir * 1.5
        D = np.ceil(np.maximum(np.maximum(D_HRT, D_weir), 2.0) / 0.5) * 0.5
        H_total = h_eff + h_super
        ok_HRT = (1.0 <= HRT) & (HRT <= 10.0)
        ok_h_eff = (1.5 <= h_eff) & (h_eff <= 4.0)
        ok_D = D >= 2.0
        concrete_m3 = PI_V * (D / 2) ** 2 * H_total * 0.4

        dtype = np.dtype(
            [
                ("V", np.float64),
                ("D", np.float64),
                ("H_total", np.float64),
                ("H", np.float64),
                ("concrete_m3", np.float64),
                ("ok_HRT", np.bool_),
                ("ok_h_eff", np.bool_),
                ("ok_D", np.bool_),
                ("val_HRT", np.float64),
                ("val_h_eff", np.float64),
                ("val_D", np.float64),
            ]
        )
        arr = np.empty(N, dtype=dtype)
        arr["V"] = V
        arr["D"] = D
        arr["H_total"] = H_total
        arr["H"] = H_total
        arr["concrete_m3"] = concrete_m3
        arr["ok_HRT"] = ok_HRT
        arr["ok_h_eff"] = ok_h_eff
        arr["ok_D"] = ok_D
        arr["val_HRT"] = HRT
        arr["val_h_eff"] = h_eff
        arr["val_D"] = D
        return arr
