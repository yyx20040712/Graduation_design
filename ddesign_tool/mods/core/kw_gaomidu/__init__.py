"""矿井水高密度沉淀池 — 混凝絮凝沉淀一体化高效工艺"""

import math
from typing import Dict, List
import numpy as np
from models.base import (
    NodeBase,
    NodeResult,
    WaterFlow,
    WaterQuality,
    ParamDef,
    Port,
    PortType,
    PI,
)


class KwGaomiduNode(NodeBase):
    """矿井水高密度沉淀池

    计算方式与市政污水高密度沉淀池一致,但不含污泥排泥接口.
    公式来源: 中期报告 §3.6 (3-77)~(3-94)
    """

    NODE_TYPE = "kw_gaomidu"
    NODE_NAME = "矿井水高密度沉淀池"
    NODE_CATEGORY = "矿井水处理"

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
    def _default_params(cls) -> Dict[str, float]:
        return {
            "n": 4,
            "t_mix": 1.0,
            "t_floc": 10.0,
            "q_surf": 8.0,
            "L_tube": 1.0,
            "alpha_tube": 60.0,
            "h_clear": 1.0,
            "h_dist": 1.5,
            "h_super": 0.5,
        }

    def _build_param_defs(self) -> List[ParamDef]:
        return [
            ParamDef(
                "池数", "n", value=4, default=4, min_val=2, max_val=6, step=1, unit="座"
            ),
            ParamDef(
                "混合时间",
                "t_mix",
                value=1.0,
                default=1.0,
                min_val=0.5,
                max_val=2.0,
                step=0.1,
                unit="min",
            ),
            ParamDef(
                "絮凝时间",
                "t_floc",
                value=10.0,
                default=10.0,
                min_val=8.0,
                max_val=15.0,
                step=0.5,
                unit="min",
            ),
            ParamDef(
                "斜管区表面负荷",
                "q_surf",
                value=8.0,
                default=8.0,
                min_val=6.0,
                max_val=12.0,
                step=0.5,
                unit="m³/(m²·h)",
            ),
            ParamDef(
                "斜管长度",
                "L_tube",
                value=1.0,
                default=1.0,
                min_val=0.8,
                max_val=1.5,
                step=0.1,
                unit="m",
            ),
            ParamDef(
                "斜管倾角",
                "alpha_tube",
                value=60,
                default=60,
                min_val=55,
                max_val=65,
                step=1,
                unit="°",
            ),
        ]

    @classmethod
    def _default_removal_rates(cls) -> Dict[str, float]:
        return {
            "SS": 0.90,
            "COD": 0.60,
            "BOD5": 0.20,
            "NH3N": 0.0,
            "TN": 0.0,
            "TP": 0.85,
        }

    def calculate(self, flow: WaterFlow, quality: WaterQuality) -> NodeResult:
        n = int(self.get_param("n"))
        t_mix = self.get_param("t_mix")
        t_floc = self.get_param("t_floc")
        q_surf = self.get_param("q_surf")
        L_tube = self.get_param("L_tube")
        alpha_tube = self.get_param("alpha_tube")
        h_clear = self.get_param("h_clear")
        h_dist = self.get_param("h_dist")
        h_super = self.get_param("h_super")
        h_thicken = 0.5

        result = NodeResult(success=True)
        result.params = {
            "n": n,
            "t_mix": t_mix,
            "t_floc": t_floc,
            "q_surf": q_surf,
            "L_tube": L_tube,
            "alpha_tube": alpha_tube,
            "h_clear": h_clear,
            "h_dist": h_dist,
            "h_super": h_super,
        }

        Q_single = flow.Q_design / n
        Q_single_m3h = Q_single * 3600
        V_mix = Q_single * t_mix * 60.0
        V_floc = Q_single * t_floc * 60.0
        A_settle = Q_single_m3h / q_surf
        sin_alpha = math.sin(math.radians(alpha_tube))
        v_axial = q_surf / (3600.0 * sin_alpha)
        result.add_check(
            "斜管轴向流速 < 5mm/s", v_axial < 0.005, round(v_axial, 4), "< 0.005", "m/s"
        )
        LB_ratio = 1.5
        B_pool = math.ceil(math.sqrt(A_settle / LB_ratio) / 0.5) * 0.5
        L_pool = math.ceil(A_settle / B_pool / 0.5) * 0.5
        h_tube_vert = L_tube * sin_alpha
        H_total = h_super + h_clear + h_dist + h_thicken + h_tube_vert
        H_rounded = math.ceil(H_total / 0.1) * 0.1
        result.add_dimension("池数", n, "座")
        result.add_dimension("混合区容积", round(V_mix, 1), "m³")
        result.add_dimension("絮凝区容积", round(V_floc, 1), "m³")
        result.add_dimension("沉淀区面积", round(A_settle, 1), "m²")
        result.add_dimension("池长 L", L_pool, "m")
        result.add_dimension("池宽 B", B_pool, "m")
        result.add_dimension("斜管轴向流速", round(v_axial, 4), "m/s")
        result.add_dimension("总高度", H_rounded, "m")
        return result

    @classmethod
    def _vectorized_compute(
        cls, grid: dict, flow: "WaterFlow", quality: "WaterQuality", fixed: dict
    ) -> "np.ndarray":
        n = grid["n"].astype(np.int32)
        t_mix = grid["t_mix"]
        t_floc = grid["t_floc"]
        q_surf = grid["q_surf"]
        alpha_tube = fixed["alpha_tube"]
        h_clear = fixed["h_clear"]
        h_dist = fixed["h_dist"]
        h_super = fixed["h_super"]
        L_tube = fixed["L_tube"]
        N = len(n)
        h_thicken = 0.5

        if flow.Q_design <= 0:
            dtype = np.dtype(
                [
                    ("V_mix", np.float64),
                    ("V_floc", np.float64),
                    ("A_settle", np.float64),
                    ("L_pool", np.float64),
                    ("B_pool", np.float64),
                    ("v_axial", np.float64),
                    ("H_total", np.float64),
                    ("L", np.float64),
                    ("B", np.float64),
                    ("H", np.float64),
                    ("concrete_m3", np.float64),
                    ("ok_axial_v", np.bool_),
                    ("val_axial_v", np.float64),
                ]
            )
            return np.zeros(N, dtype=dtype)

        Q_single = flow.Q_design / n
        Q_single_m3h = Q_single * 3600
        V_mix = Q_single * t_mix * 60.0
        V_floc = Q_single * t_floc * 60.0
        A_settle = Q_single_m3h / q_surf
        sin_alpha = np.sin(np.radians(alpha_tube))
        v_axial = q_surf / (3600.0 * sin_alpha)
        ok_axial = v_axial < 0.005
        LB_ratio = 1.5
        B_pool = np.ceil(np.sqrt(A_settle / LB_ratio) / 0.5) * 0.5
        L_pool = np.ceil(A_settle / B_pool / 0.5) * 0.5
        h_tube_vert = L_tube * sin_alpha
        H_total = h_super + h_clear + h_dist + h_thicken + h_tube_vert
        concrete_m3 = L_pool * B_pool * H_total * n * 0.4

        dtype = np.dtype(
            [
                ("V_mix", np.float64),
                ("V_floc", np.float64),
                ("A_settle", np.float64),
                ("L_pool", np.float64),
                ("B_pool", np.float64),
                ("v_axial", np.float64),
                ("H_total", np.float64),
                ("L", np.float64),
                ("H", np.float64),
                ("B", np.float64),
                ("concrete_m3", np.float64),
                ("ok_axial_v", np.bool_),
                ("val_axial_v", np.float64),
            ]
        )
        result = np.empty(N, dtype=dtype)
        result["V_mix"] = V_mix
        result["V_floc"] = V_floc
        result["A_settle"] = A_settle
        result["L_pool"] = L_pool
        result["B_pool"] = B_pool
        result["v_axial"] = v_axial
        result["H_total"] = H_total
        result["concrete_m3"] = concrete_m3
        result["L"] = result["L_pool"]  # standard field
        result["B"] = result["B_pool"]  # standard field
        result["H"] = result["H_total"]  # standard field
        result["ok_axial_v"] = ok_axial
        result["val_axial_v"] = v_axial
        return result


__all__ = ["KwGaomiduNode"]
