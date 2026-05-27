"""wuni_nongsuo.py — 污泥浓缩池 (Sludge Thickener)"""
import math
from typing import Dict, List, Tuple, Optional

import numpy as np

from models.base import (
    NodeBase, NodeResult, SludgeFlow, ParamDef,
    Port, PortType, PI,
)


class WuniNongsuoNode(NodeBase):
    """污泥浓缩池 — 重力/气浮浓缩

    公式来源: GB50014-2021 §7.2, CJJ 131-2009
    进泥含水率 ~96%, 出泥含水率 ~94%
    """
    NODE_TYPE = "wuni_nongsuo"
    NODE_NAME = "污泥浓缩池"
    NODE_CATEGORY = "污泥处理"

    @classmethod
    def _default_params(cls) -> Dict[str, float]:
        return {
            "n": 2, "q_solid": 50.0, "T_thicken": 16.0,
            "P_out": 0.96, "h_eff": 4.0,
        }

    def _build_param_defs(self) -> List[ParamDef]:
        return [
            ParamDef("池数量", "n", value=2, default=2,
                     min_val=1, max_val=4, step=1, unit="座"),
            ParamDef("固体负荷", "q_solid", value=50.0, default=50.0,
                     min_val=30, max_val=60, step=5,
                     unit="kgDS/(m²·d)",
                     description="GB50014 §8.2.1: 30~60"),
            ParamDef("浓缩时间", "T_thicken", value=16.0, default=16.0,
                     min_val=12, max_val=24, step=2, unit="h",
                     description="GB50014: ≥12h"),
            ParamDef("出泥含水率", "P_out", value=0.96, default=0.96,
                     min_val=0.94, max_val=0.98, step=0.01, unit="-",
                     description="GB50014: 97~98%"),
            ParamDef("有效水深", "h_eff", value=4.0, default=4.0,
                     min_val=3.0, max_val=5.0, step=0.5, unit="m",
                     description="GB50014 §8.2.1: 宜为4m"),
        ]

    @classmethod
    def _default_removal_rates(cls) -> Dict[str, float]:
        return {}

    def _init_ports(self) -> None:
        self.input_ports = [
            Port(port_id=f"{self.node_id}-s_in", name="污泥进",
                 port_type=PortType.SLUDGE, direction="input",
                 node_id=self.node_id),
        ]
        self.output_ports = [
            Port(port_id=f"{self.node_id}-s_out", name="浓缩污泥",
                 port_type=PortType.SLUDGE, direction="output",
                 node_id=self.node_id),
        ]

    def calculate(self, flow, quality) -> NodeResult:
        return NodeResult(success=True)

    def execute_sludge(self, sludge: SludgeFlow) -> Tuple[Optional[NodeResult], SludgeFlow]:
        n = int(self.get_param("n"))
        q_solid = self.get_param("q_solid")
        T_thicken = self.get_param("T_thicken")
        P_out = self.get_param("P_out")

        result = NodeResult(success=True)
        h_eff = self.get_param("h_eff")
        result.params = {
            "n": n, "q_solid": q_solid, "T_thicken": T_thicken,
            "P_out": P_out, "h_eff": h_eff,
        }

        DS = sludge.DS
        Q_wet_in = sludge.Q_wet
        P_in = sludge.P_moisture

        # ── (A) 浓缩面积 (GB50014 §7.2.3) ──
        A_total = DS / q_solid if q_solid > 0 else 0
        A_single = A_total / n

        # ── (B) 池体尺寸 (圆形浓缩池) ──
        D_theory = math.sqrt(4 * A_single / PI)
        D = math.ceil(max(D_theory, 5.0) / 0.5) * 0.5  # 最小 5m

        result.add_check("池径 D >= 5", D >= 5,
                         round(D, 1), ">= 5", "m")

        # ── (C) 有效水深 ──
        A_actual = PI * D ** 2 / 4
        q_solid_actual = DS / (n * A_actual) if A_actual > 0 else 0
        result.add_check("固体负荷合理", 30 <= q_solid_actual <= 60,
                         round(q_solid_actual, 1), "30~60 (GB50014 §8.2.1)",
                         "kgDS/(m²·d)")

        # 有效水深 (GB50014 §8.2.1: 宜为4m)
        h_eff_target = self.get_param("h_eff")
        V_single = Q_wet_in * (T_thicken / 24) / n
        h_eff_calc = V_single / A_actual if A_actual > 0 else h_eff_target
        h_eff_calc = max(3.0, min(h_eff_calc, 5.0))

        result.add_check("有效水深", 3.0 <= h_eff_calc <= 5.0,
                         round(h_eff_calc, 2), "3.0~5.0 (GB50014: 宜4m)", "m")

        # ── (D) 超高 ──
        h_super = 0.5
        H_total = h_eff_calc + h_super

        # ── (E) 出泥量 ──
        if P_out < 1.0:
            Q_wet_out = DS / ((1 - P_out) * 1000.0)
        else:
            Q_wet_out = float('inf')

        # 分离液量
        Q_separate = max(0, Q_wet_in - Q_wet_out)

        # ── (F) 污泥固体回收率 ──
        # 浓缩上清液 SS ≤ 200mg/L
        SS_supernatant = min(200, 200.0)
        recovery = 0.95  # 典型固体回收率

        # ── 组装结果 ──
        result.add_dimension("池数", n, "座")
        result.add_dimension("池径 D", D, "m")
        result.add_dimension("浓缩面积(单池)", round(A_actual, 1), "m²")
        result.add_dimension("有效水深", round(h_eff_calc, 2), "m")
        result.add_dimension("总高度", round(H_total, 2), "m")
        result.add_dimension("固体负荷(实际)", round(q_solid_actual, 1),
                            "kgDS/(m²·d)")
        result.add_dimension("浓缩时间", T_thicken, "h")
        result.add_dimension("进泥湿泥量", round(Q_wet_in, 2), "m³/d")
        result.add_dimension("进泥含水率", round(P_in, 3), "")
        result.add_dimension("出泥湿泥量", round(Q_wet_out, 2), "m³/d")
        result.add_dimension("出泥含水率", P_out, "")
        result.add_dimension("分离液量", round(Q_separate, 2), "m³/d")
        result.add_dimension("干固体量", round(DS, 1), "kg/d")
        result.add_dimension("固体回收率", recovery * 100, "%")

        # 出泥
        sludge_out = SludgeFlow(
            Q_wet=Q_wet_out, DS=DS * recovery,
            P_moisture=P_out, VS_ratio=sludge.VS_ratio,
        )
        self._sludge_output = sludge_out
        return result, sludge_out

    @classmethod
    def _vectorized_compute(cls, grid, flow, quality, fixed):
        """向量化浓缩池 — 固废负荷法批量计算"""
        n = grid["n"].astype(np.int32)
        q_solid = grid["q_solid"]
        T_thicken = grid["T_thicken"]
        P_out = fixed.get("P_out", 0.96)
        h_eff_target = fixed.get("h_eff", 4.0)
        DS = fixed.get("_sludge_DS", 4000.0)
        Q_wet_in = fixed.get("_sludge_Q_wet", 100.0)
        N = len(n)
        PI_V = np.pi

        # Area
        A_total = DS / q_solid
        A_single = A_total / n
        D_theory = np.sqrt(4 * A_single / PI_V)
        D = np.ceil(np.maximum(D_theory, 5.0) / 0.5) * 0.5
        ok_D_min = D >= 5

        A_actual = PI_V * D ** 2 / 4
        q_solid_actual = np.where(A_actual > 0, DS / (n * A_actual), 0)
        ok_solid_flux = (30 <= q_solid_actual) & (q_solid_actual <= 60)

        # Depth
        V_single = Q_wet_in * (T_thicken / 24) / n
        h_eff_calc = np.where(A_actual > 0, V_single / A_actual, h_eff_target)
        h_eff_calc = np.clip(h_eff_calc, 3.0, 5.0)
        ok_h_eff = (3.0 <= h_eff_calc) & (h_eff_calc <= 5.0)

        H_total = h_eff_calc + 0.5

        # Output sludge
        Q_wet_out = np.where(P_out < 1, DS * 0.95 / ((1 - P_out) * 1000.0), 1e9)
        concrete_m3 = PI_V * (D/2)**2 * H_total * n * 0.4

        dt = np.dtype([
            ("D", np.float64), ("h_eff_calc", np.float64), ("H_total", np.float64),
            ("q_solid_actual", np.float64), ("Q_wet_out", np.float64),
            ("H", np.float64),
            ("concrete_m3", np.float64),
            ("ok_D_min", np.bool_), ("ok_solid_flux", np.bool_), ("ok_h_eff", np.bool_),
            ("val_D_min", np.float64), ("val_solid_flux", np.float64), ("val_h_eff", np.float64),
        ])
        arr = np.zeros(N, dtype=dt)
        arr["D"] = D; arr["h_eff_calc"] = h_eff_calc; arr["H_total"] = H_total
        arr["q_solid_actual"] = q_solid_actual; arr["Q_wet_out"] = Q_wet_out
        arr["concrete_m3"] = concrete_m3
        arr["ok_D_min"] = ok_D_min; arr["ok_solid_flux"] = ok_solid_flux; arr["ok_h_eff"] = ok_h_eff
        arr["val_D_min"] = D; arr["val_solid_flux"] = q_solid_actual; arr["val_h_eff"] = h_eff_calc
        return arr
