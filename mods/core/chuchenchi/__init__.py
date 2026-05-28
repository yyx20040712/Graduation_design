"""chuchenchi.py — 辐流式初沉池 (Radial Primary Settling Tank)"""

import math
from typing import Dict, List

import numpy as np

from models.base import (
    NodeBase,
    NodeResult,
    WaterFlow,
    WaterQuality,
    SludgeFlow,
    ParamDef,
    PI,
)


class ChuchenchiNode(NodeBase):
    """辐流式初沉池

    公式来源: 中期报告 §3.4 (3-27)~(3-52)
    """

    NODE_TYPE = "chuchenchi"
    NODE_NAME = "辐流式初沉池"
    NODE_CATEGORY = "一级处理"

    def _init_ports(self) -> None:
        """初沉池: MIXED进水 → MIXED出水 + SLUDGE排泥"""
        from models.base import Port, PortType

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
            Port(
                port_id=f"{self.node_id}-sludge",
                name="排泥",
                port_type=PortType.SLUDGE,
                direction="output",
                node_id=self.node_id,
            ),
        ]

    @classmethod
    def _default_params(cls) -> Dict[str, float]:
        return {
            "n": 2,
            "q_prime": 2.0,
            "T_settle": 1.5,
            "h1": 0.3,
            "h3": 0.3,
            "i_slope": 0.05,
            "R1": 1.8,
            "R2": 0.8,
            "h5": 1.5,
            "P_sludge": 0.96,
            "T_sludge": 2,
            "v_center": 0.3,
        }

    def _build_param_defs(self) -> List[ParamDef]:
        return [
            ParamDef(
                "池数", "n", value=2, default=2, min_val=2, max_val=4, step=1, unit="座"
            ),
            ParamDef(
                "表面负荷 q'",
                "q_prime",
                value=2.0,
                default=2.0,
                min_val=1.5,
                max_val=3.0,
                step=0.1,
                unit="m³/(m²·h)",
            ),
            ParamDef(
                "沉淀时间 T",
                "T_settle",
                value=1.5,
                default=1.5,
                min_val=1.0,
                max_val=2.0,
                step=0.1,
                unit="h",
            ),
            ParamDef(
                "超高 h1",
                "h1",
                value=0.3,
                default=0.3,
                min_val=0.3,
                max_val=0.5,
                step=0.1,
                unit="m",
            ),
            ParamDef(
                "缓冲层 h3",
                "h3",
                value=0.3,
                default=0.3,
                min_val=0.3,
                max_val=0.5,
                step=0.1,
                unit="m",
            ),
            ParamDef(
                "池底坡度 i",
                "i_slope",
                value=0.05,
                default=0.05,
                min_val=0.03,
                max_val=0.08,
                step=0.01,
                unit="-",
            ),
            ParamDef(
                "泥斗上口半径 R1",
                "R1",
                value=1.8,
                default=1.8,
                min_val=1.5,
                max_val=2.0,
                step=0.1,
                unit="m",
            ),
            ParamDef(
                "泥斗下口半径 R2",
                "R2",
                value=0.8,
                default=0.8,
                min_val=0.6,
                max_val=1.0,
                step=0.1,
                unit="m",
            ),
            ParamDef(
                "泥斗高度 h5",
                "h5",
                value=1.5,
                default=1.5,
                min_val=1.2,
                max_val=2.0,
                step=0.1,
                unit="m",
            ),
            ParamDef(
                "污泥含水率",
                "P_sludge",
                value=0.96,
                default=0.96,
                min_val=0.95,
                max_val=0.97,
                step=0.01,
                unit="-",
            ),
            ParamDef(
                "排泥周期",
                "T_sludge",
                value=2,
                default=2,
                min_val=1,
                max_val=4,
                step=1,
                unit="d",
                description="贮泥时间",
            ),
            ParamDef(
                "中心管流速",
                "v_center",
                value=0.3,
                default=0.3,
                min_val=0.2,
                max_val=0.5,
                step=0.05,
                unit="m/s",
            ),
        ]

    @classmethod
    def _default_removal_rates(cls) -> Dict[str, float]:
        return {
            "SS": 0.50,
            "BOD5": 0.30,
            "COD": 0.30,
            "NH3N": 0.05,
            "TN": 0.05,
            "TP": 0.05,
        }

    def calculate(self, flow: WaterFlow, quality: WaterQuality) -> NodeResult:
        n = int(self.get_param("n"))
        q_prime = self.get_param("q_prime")
        T_settle = self.get_param("T_settle")
        h1 = self.get_param("h1")
        h3 = self.get_param("h3")
        i_slope = self.get_param("i_slope")
        R1 = self.get_param("R1")
        R2 = self.get_param("R2")
        h5 = self.get_param("h5")
        P_sludge = self.get_param("P_sludge")
        T_sludge = self.get_param("T_sludge")
        v_center = self.get_param("v_center")

        result = NodeResult(success=True)
        result.params = {
            "n": n,
            "q_prime": q_prime,
            "T_settle": T_settle,
            "h1": h1,
            "h3": h3,
            "i_slope": i_slope,
            "R1": R1,
            "R2": R2,
            "h5": h5,
            "P_sludge": P_sludge,
            "T_sludge": T_sludge,
            "v_center": v_center,
        }

        # ── 调用向量化计算 (N=1) ──
        grid = {
            "n": np.array([n]),
            "q_prime": np.array([q_prime]),
            "T_settle": np.array([T_settle]),
        }
        fixed = {
            "h1": h1,
            "h3": h3,
            "i_slope": i_slope,
            "R1": R1,
            "R2": R2,
            "h5": h5,
            "P_sludge": P_sludge,
            "T_sludge": T_sludge,
            "v_center": v_center,
        }
        r = self._vectorized_compute(grid, flow, quality, fixed)[0]

        D = float(r["D"])
        F_actual = float(r["F_actual"])
        q_prime_actual = float(r["q_prime_actual"])
        h2 = float(r["h2"])
        ratio_Dh2 = float(r["ratio_Dh2"])
        H = float(r["H_total"])
        h4_rounded = float(r["h4"])
        d_center = float(r["d_center"])
        q_weir = float(r["q_weir"])
        S_dry = float(r["S_dry"])
        S_wet = float(r["S_wet"])
        V_total_storage = float(r["V_total_storage"])
        v_peripheral = float(r["v_peripheral"])

        H_rounded = math.ceil(H / 0.1) * 0.1
        V_sludge = S_wet * T_sludge
        weir_len = 2.0 * PI * (D - 1.0)

        # ── 校核 ──
        result.add_check("池径 D>=16", D >= 16, round(D, 1), ">= 16", "m")
        result.add_check(
            "实际表面负荷 q'",
            1.5 <= q_prime_actual <= 3.0,
            round(q_prime_actual, 2),
            "1.5~3.0",
            "m³/(m²·h)",
        )
        result.add_check("有效水深 h2", 2.0 <= h2 <= 4.0, round(h2, 2), "2.0~4.0", "m")
        result.add_check(
            "径深比 D/h2", 6 <= ratio_Dh2 <= 12, round(ratio_Dh2, 2), "6~12", ""
        )
        result.add_check(
            "污泥区容积足够",
            V_total_storage >= V_sludge,
            round(V_total_storage - V_sludge, 2),
            ">= 0",
            "m³",
        )
        if V_total_storage < V_sludge:
            result.add_warning(
                f"污泥区容积不足: {V_total_storage:.1f} < {V_sludge:.1f} m³"
            )
        result.add_check("堰负荷", q_weir <= 2.9, round(q_weir, 2), "<= 2.9", "L/(s·m)")
        result.add_check("排泥周期 T_sludge", 1 <= T_sludge <= 2, T_sludge, "1~2", "d")
        result.add_check(
            "刮泥机线速", v_peripheral <= 3.0, round(v_peripheral, 2), "<= 3.0", "m/min"
        )

        # ── 尺寸 ──
        result.add_dimension("池数", n, "座")
        result.add_dimension("池径 D", D, "m")
        result.add_dimension("沉淀面积 F", round(F_actual, 1), "m²")
        result.add_dimension("有效水深 h2", round(h2, 2), "m")
        result.add_dimension("径深比", round(ratio_Dh2, 2), "")
        result.add_dimension("总高度 H", H_rounded, "m")
        result.add_dimension("池底坡降 h4", h4_rounded, "m")
        result.add_dimension("泥斗高度 h5", h5, "m")
        result.add_dimension("中心管径", d_center, "m")
        result.add_dimension(
            "出水堰长",
            round(weir_len, 1),
            "m",
            formula="L = 2π(D-1), 双侧堰",
            category="physical",
        )
        result.add_dimension("堰负荷", round(q_weir, 2), "L/(s·m)")
        result.add_dimension("每日干污泥", round(S_dry, 1), "kg/d")
        result.add_dimension("每日湿污泥", round(S_wet, 2), "m³/d")
        result.add_dimension("单池需贮泥容积", round(V_sludge, 2), "m³")
        result.add_dimension("污泥区总容积", round(V_total_storage, 2), "m³")
        result.add_dimension("刮泥机线速", round(v_peripheral, 2), "m/min")
        result.add_dimension("实际表面负荷", round(q_prime_actual, 2), "m³/(m²·h)")

        # ── 污泥输出 (SLUDGE 端口) — 汇总 n 池总量 ──
        self._sludge_output = SludgeFlow(
            Q_wet=S_wet * n,
            DS=S_dry * n,
            P_moisture=P_sludge,
            VS_ratio=0.60,
        )

        return result

    @classmethod
    def _vectorized_compute(
        cls, grid: dict, flow: "WaterFlow", quality: "WaterQuality", fixed: dict
    ) -> "np.ndarray":
        """向量化辐流式初沉池

        grid: n, q_prime, T_settle
        fixed: h1, h3, i_slope, R1, R2, h5, P_sludge, T_sludge, v_center
        """
        n = grid["n"].astype(np.int32)
        q_prime = grid["q_prime"]
        T_settle = grid["T_settle"]
        h1 = fixed["h1"]
        h3 = fixed["h3"]
        i_slope = fixed["i_slope"]
        R1 = fixed["R1"]
        R2 = fixed["R2"]
        h5 = fixed["h5"]
        P_sludge = fixed["P_sludge"]
        T_sludge = fixed["T_sludge"]
        v_center = fixed["v_center"]
        N = len(n)
        PI_V = np.pi

        Q_single = flow.Q_design / n
        Q_single_m3h = Q_single * 3600

        # 沉淀面积
        F = Q_single_m3h / q_prime

        # 直径
        D_theory = np.sqrt(4 * F / PI_V)
        D = np.ceil(D_theory / 0.5) * 0.5
        ok_D = D >= 16

        F_actual = PI_V * D**2 / 4
        q_prime_actual = np.divide(Q_single_m3h, F_actual,
                                   where=F_actual > 0,
                                   out=np.full_like(Q_single_m3h, 0.0, dtype=np.float64))
        ok_q = (1.5 <= q_prime_actual) & (q_prime_actual <= 3.0)

        # 有效水深
        h2 = q_prime_actual * T_settle
        ratio_Dh2 = np.divide(D, h2,
                              where=h2 > 0,
                              out=np.full_like(D, 0.0, dtype=np.float64))
        ok_h2 = (2.0 <= h2) & (h2 <= 4.0)
        ok_Dh2 = (6 <= ratio_Dh2) & (ratio_Dh2 <= 12)

        # 污泥计算 — 全按单池
        SS_in = quality.SS
        removal_ss = 0.50
        SS_out = SS_in * (1 - removal_ss)
        S_dry = flow.Q_avg_daily * (SS_in - SS_out) / 1000.0 / n  # kg/d 单池
        S_wet = np.where(P_sludge < 1, S_dry / ((1 - P_sludge) * 1000.0), 0.0)
        V_sludge = S_wet * T_sludge  # T_sludge 单位: d

        # 泥斗
        R = D / 2.0
        V1 = PI_V * h5 / 3 * (R1**2 + R1 * R2 + R2**2)
        h4 = i_slope * (R - R1)
        h4_rounded = np.ceil(h4 / 0.1) * 0.1
        V2 = PI_V * h4_rounded / 3 * (R**2 + R * R1 + R1**2)
        V_total_storage = V1 + V2
        ok_sludge = V_total_storage >= V_sludge

        # 出水堰
        weir_len = 2.0 * PI_V * (D - 1.0)
        q_weir = np.where(weir_len > 0, Q_single * 1000.0 / weir_len, 0.0)
        ok_weir = q_weir <= 2.9

        # 中心管
        d_center_theory = np.sqrt(4 * Q_single / (PI_V * v_center))
        d_center = np.ceil(d_center_theory / 0.1) * 0.1

        # 总高度
        H = h1 + h2 + h3 + h4_rounded + h5

        # 排泥周期约束 (1~2d, GB50014 §6.5.7)
        ok_T_sludge = (1 <= T_sludge) & (T_sludge <= 2)

        # 刮泥机线速
        v_peripheral = PI_V * D * 1.0 / 60.0
        ok_scraper = v_peripheral <= 3.0

        # 成本
        concrete_m3 = PI_V * R**2 * H * n * 0.4

        dtype = np.dtype(
            [
                ("D", np.float64),
                ("F_actual", np.float64),
                ("q_prime_actual", np.float64),
                ("h2", np.float64),
                ("ratio_Dh2", np.float64),
                ("H_total", np.float64),
                ("h4", np.float64),
                ("d_center", np.float64),
                ("q_weir", np.float64),
                ("S_dry", np.float64),
                ("S_wet", np.float64),
                ("V_total_storage", np.float64),
                ("v_peripheral", np.float64),
                ("H", np.float64),
                ("concrete_m3", np.float64),
                ("ok_D_min", np.bool_),
                ("ok_q_prime", np.bool_),
                ("ok_h2", np.bool_),
                ("ok_Dh2", np.bool_),
                ("ok_sludge", np.bool_),
                ("ok_weir", np.bool_),
                ("ok_scraper", np.bool_),
                ("ok_T_sludge", np.bool_),
                ("val_D_min", np.float64),
                ("val_q_prime", np.float64),
                ("val_h2", np.float64),
                ("val_Dh2", np.float64),
                ("val_sludge", np.float64),
                ("val_weir", np.float64),
                ("val_scraper", np.float64),
                ("val_T_sludge", np.float64),
            ]
        )
        result = np.empty(N, dtype=dtype)
        result["D"] = D
        result["F_actual"] = F_actual
        result["q_prime_actual"] = q_prime_actual
        result["h2"] = h2
        result["ratio_Dh2"] = ratio_Dh2
        result["H_total"] = H
        result["h4"] = h4_rounded
        result["d_center"] = d_center
        result["q_weir"] = q_weir
        result["S_dry"] = S_dry
        result["S_wet"] = S_wet
        result["V_total_storage"] = V_total_storage
        result["v_peripheral"] = v_peripheral
        result["concrete_m3"] = concrete_m3
        result["H"] = result["H_total"]  # standard field
        result["D"] = D  # standard field
        result["ok_D_min"] = ok_D
        result["ok_q_prime"] = ok_q
        result["ok_h2"] = ok_h2
        result["ok_Dh2"] = ok_Dh2
        result["ok_sludge"] = ok_sludge
        result["ok_weir"] = ok_weir
        result["ok_scraper"] = ok_scraper
        result["ok_T_sludge"] = ok_T_sludge
        result["val_D_min"] = D
        result["val_q_prime"] = q_prime_actual
        result["val_h2"] = h2
        result["val_Dh2"] = ratio_Dh2
        result["val_sludge"] = V_total_storage - V_sludge
        result["val_weir"] = q_weir
        result["val_scraper"] = v_peripheral
        result["val_T_sludge"] = np.full(N, T_sludge, dtype=np.float64)
        return result
