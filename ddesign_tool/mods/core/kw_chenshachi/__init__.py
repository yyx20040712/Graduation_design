"""
kw_chenshachi.py — 平流沉砂池计算模块

平流式沉砂池(Horizontal Flow Grit Chamber)用于去除矿井水中
高浓度的煤灰粉、砂粒等无机颗粒.矩形平流式,多斗式棱台砂斗收集.

与市政旋流沉砂池的主要区别:
  - 矩形平流式,非圆形旋流式
  - 有效水深 ≤ 1.2m(远浅于市政沉砂池)
  - 水平流速 0.20~0.25 m/s
  - 停留时间 30~60s
  - 砂斗倾角 ≥ 55°
  - 矿井水沉砂量 κ = 0.03~0.05 L/m³(高于市政)

计算公式来源:dlc.docx §4.3 平流沉砂池设计计算
  (4-11): L = v · t
  (4-12): A₁ = Q_max / (n · v)
  (4-13): v_actual = Q_max / (n · B · H), 0.15 ≤ v ≤ 0.30
  (4-14): B = A₁ / H
  (4-15): V_sand,daily = Q_d × 86400 × κ
  (4-16): V_hopper,total = V_sand,daily × T_sand
  (4-17): V_hopper,single = V_hopper,total / n
  (4-18): h_hopper = (b₁-b₂)/2 × tan(α)
  (4-19): V_hopper = h/3 × (b₁² + b₂² + b₁·b₂)   (棱台)
  (4-20): V_hopper ≥ V_hopper,single
  (4-21): H_t = H + h_hopper + h_free
  (4-22): L_weir = Q_max × 1000 / q_weir
"""

import math
from typing import Dict, List

import numpy as np

from models.base import (
    NodeBase,
    NodeResult,
    WaterFlow,
    WaterQuality,
    ParamDef,
)


class KwChenshachiNode(NodeBase):
    """平流沉砂池 — 去除煤灰粉和砂粒"""

    NODE_TYPE = "kw_chenshachi"
    NODE_NAME = "平流沉砂池"
    NODE_CATEGORY = "矿井水处理"

    @classmethod
    def _default_params(cls) -> Dict[str, float]:
        return {
            "n": 2,  # 格数(≥2)
            "v_h": 0.22,  # 水平流速 m/s(0.20~0.25)
            "t_stay": 50,  # 停留时间 s(30~60)
            "h_eff": 0.8,  # 有效水深 m(≤1.2,一般0.25~1.0)
            "h_super": 0.3,  # 超高 m(≥0.3)
            "slope": 0.02,  # 池底坡度(0.01~0.02)
            "hopper_angle": 55,  # 砂斗倾角 °(≥55°)
            "hopper_bottom": 0.4,  # 砂斗下口宽 m(0.4~0.6,须小于单格宽度B)
            "kappa": 0.03,  # 沉砂量系数 L/m³(0.03~0.05)
            "T_sand": 2,  # 贮砂时间 d(一般2d)
            "P_sand": 0.60,  # 沉砂含水率
            "rho_sand": 1500,  # 沉砂密度 kg/m³
            "q_weir_design": 2.5,  # 设计堰负荷 L/(s·m)(1.5~2.9)
        }

    def _build_param_defs(self) -> List[ParamDef]:
        return [
            ParamDef(
                "格数 n",
                "n",
                value=2,
                default=2,
                min_val=2,
                max_val=8,
                step=1,
                unit="格",
                description="沉砂池格数,≥2",
            ),
            ParamDef(
                "水平流速 v",
                "v_h",
                value=0.22,
                default=0.22,
                min_val=0.20,
                max_val=0.25,
                step=0.01,
                unit="m/s",
                description="最大流量时水平流速 0.20~0.25m/s",
            ),
            ParamDef(
                "停留时间 t",
                "t_stay",
                value=50,
                default=50,
                min_val=30,
                max_val=60,
                step=5,
                unit="s",
                description="≥30s,一般30~60s",
            ),
            ParamDef(
                "有效水深 H",
                "h_eff",
                value=0.8,
                default=0.8,
                min_val=0.25,
                max_val=1.0,
                step=0.05,
                unit="m",
                description="≤1.2m,一般0.25~1.0m",
            ),
            ParamDef(
                "超高",
                "h_super",
                value=0.3,
                default=0.3,
                min_val=0.3,
                max_val=0.5,
                step=0.1,
                unit="m",
                description="≥0.3m",
            ),
            ParamDef(
                "池底坡度 i",
                "slope",
                value=0.02,
                default=0.02,
                min_val=0.01,
                max_val=0.02,
                step=0.005,
                unit="-",
                description="0.01~0.02",
            ),
            ParamDef(
                "砂斗倾角 α",
                "hopper_angle",
                value=55,
                default=55,
                min_val=55,
                max_val=60,
                step=1,
                unit="°",
                description="≥55°,一般55°~60°",
            ),
            ParamDef(
                "砂斗下口宽 b₂",
                "hopper_bottom",
                value=0.4,
                default=0.4,
                min_val=0.3,
                max_val=0.6,
                step=0.1,
                unit="m",
            ),
            ParamDef(
                "沉砂量系数 κ",
                "kappa",
                value=0.03,
                default=0.03,
                min_val=0.03,
                max_val=0.05,
                step=0.01,
                unit="L/m³",
                description="矿井水 0.03~0.05 L/m³",
            ),
            ParamDef(
                "贮砂时间 T",
                "T_sand",
                value=2,
                default=2,
                min_val=1,
                max_val=3,
                step=1,
                unit="d",
                description="一般按2d计",
            ),
            ParamDef(
                "沉砂含水率",
                "P_sand",
                value=0.60,
                default=0.60,
                min_val=0.55,
                max_val=0.65,
                step=0.05,
                unit="-",
            ),
            ParamDef(
                "沉砂密度",
                "rho_sand",
                value=1500,
                default=1500,
                min_val=1400,
                max_val=1600,
                step=50,
                unit="kg/m³",
            ),
            ParamDef(
                "设计堰负荷",
                "q_weir_design",
                value=2.5,
                default=2.5,
                min_val=1.5,
                max_val=2.9,
                step=0.1,
                unit="L/(s·m)",
                description="1.5~2.9 L/(s·m)",
            ),
        ]

    @classmethod
    def _default_removal_rates(cls) -> Dict[str, float]:
        return {
            "BOD5": 0.05,
            "COD": 0.10,
            "SS": 0.25,
            "NH3N": 0.0,
            "TN": 0.0,
            "TP": 0.05,
        }

    def calculate(self, flow: WaterFlow, quality: WaterQuality) -> NodeResult:
        # ── 读取参数 ──
        n = int(self.get_param("n"))
        v_h = self.get_param("v_h")
        t_stay = self.get_param("t_stay")
        h_eff = self.get_param("h_eff")
        h_super = self.get_param("h_super")
        slope = self.get_param("slope")
        hopper_angle = self.get_param("hopper_angle")
        hopper_bottom = self.get_param("hopper_bottom")
        kappa = self.get_param("kappa")  # L/m³
        T_sand = self.get_param("T_sand")  # d
        P_sand = self.get_param("P_sand")
        rho_sand = self.get_param("rho_sand")  # kg/m³
        q_weir_design = self.get_param("q_weir_design")  # L/(s·m)

        result = NodeResult(success=True)
        result.params = {
            "n": n,
            "v_h": v_h,
            "t_stay": t_stay,
            "h_eff": h_eff,
            "h_super": h_super,
            "slope": slope,
            "hopper_angle": hopper_angle,
            "hopper_bottom": hopper_bottom,
            "kappa": kappa,
            "T_sand": T_sand,
            "P_sand": P_sand,
            "rho_sand": rho_sand,
            "q_weir_design": q_weir_design,
        }

        Q_max = flow.Q_design  # m³/s
        Q_single = Q_max / n  # m³/s (单格)
        Q_avg_daily = flow.Q_avg_daily  # m³/d

        # ── (4-11) 沉砂池长度 L = v × t ──
        L_calc = v_h * t_stay
        L = math.ceil(L_calc / 0.5) * 0.5

        # ── (4-12) 单格水流断面面积 A₁ = Q_max / (n × v) ──
        A_cross = Q_max / (n * v_h) if v_h > 0 else 0  # m²

        # ── (4-14) 单格池宽 B = A₁ / H ──
        B_calc = A_cross / h_eff if h_eff > 0 else 0
        B = round(math.ceil(max(B_calc, 0.6) / 0.1) * 0.1, 2)  # B ≥ 0.6m

        # ── (4-13) 实际流速校核 v_actual = Q_max / (n × B × H) ──
        A_actual = B * h_eff
        v_actual = Q_max / (n * A_actual) if A_actual > 0 else 0
        result.add_check(
            "水平流速 0.15~0.30 m/s",
            0.15 <= v_actual <= 0.30,
            round(v_actual, 3),
            "0.15~0.30",
            "m/s",
        )
        if v_actual < 0.15:
            result.add_warning(f"实际流速 v={v_actual:.3f}m/s < 0.15,建议减小B或增大n")
        elif v_actual > 0.30:
            result.add_warning(f"实际流速 v={v_actual:.3f}m/s > 0.30,建议增大B或减小n")

        # ── 有效水深校核 H ≤ 1.2m ──
        result.add_check(
            "有效水深 H ≤ 1.2m", h_eff <= 1.2, round(h_eff, 2), "≤ 1.2", "m"
        )

        # ── 单格宽度校核 B ≥ 0.6m ──
        result.add_check("单格宽度 B ≥ 0.6m", B >= 0.6, round(B, 2), "≥ 0.6", "m")

        # ── 宽深比 B/H 1.0~2.0 ──
        if h_eff > 0:
            ratio_BH = B / h_eff
            result.add_check(
                "宽深比 B/H 1.0~2.0",
                1.0 <= ratio_BH <= 2.0,
                round(ratio_BH, 2),
                "1.0~2.0",
                "",
            )
            if ratio_BH < 1.0 or ratio_BH > 2.0:
                result.add_warning(f"宽深比 B/H={ratio_BH:.1f},建议调整 H 或 n")

        # ── (4-15) 每日沉砂体积 ──
        # κ: L/m³ → m³/m³: κ_m3 = κ / 1000
        kappa_m3_per_m3 = kappa / 1000.0  # m³砂 / m³水
        V_sand_daily = Q_avg_daily * kappa_m3_per_m3  # m³/d

        # ── (4-16) 所需砂斗总容积 ──
        V_hopper_needed_total = V_sand_daily * T_sand  # m³

        # ── (4-17) 单格所需砂斗容积 ──
        V_hopper_needed_per = V_hopper_needed_total / n  # m³

        # ── (4-18) 砂斗深度 h_hopper = (b₁ - b₂)/2 × tan(α) ──
        b1 = B  # 砂斗上口宽 = 池宽
        b2 = hopper_bottom
        alpha_rad = math.radians(hopper_angle)
        h_hopper = (b1 - b2) / 2.0 * math.tan(alpha_rad)

        # ── (4-19) 单斗容积(棱台)V = h/3 × (b₁² + b₂² + b₁·b₂) ──
        V_hopper_single = h_hopper / 3.0 * (b1**2 + b2**2 + b1 * b2)

        # ── 沿池长方向砂斗个数 ──
        n_hoppers_per_cell = max(1, int(L / max(b1, 0.1)))
        V_hopper_total = V_hopper_single * n_hoppers_per_cell * n

        # ── (4-20) 砂斗容积校核 ──
        hopper_ok = V_hopper_total >= V_hopper_needed_total
        result.add_check(
            "砂斗容积足够",
            hopper_ok,
            round(V_hopper_total, 2),
            f">= {round(V_hopper_needed_total, 2)}",
            "m³",
        )
        if not hopper_ok:
            result.add_warning(
                f"砂斗总容积不足: {V_hopper_total:.1f}m³ < {V_hopper_needed_total:.1f}m³,"
                f"建议增大砂斗深度或增加砂斗个数"
            )

        # ── (4-21) 池体总高度 H_t = H + h_hopper + h_free ──
        H_total = h_eff + h_hopper + h_super
        H_rounded = math.ceil(H_total / 0.1) * 0.1

        # ── (4-22) 出水堰设计 ──
        # 需堰长: L_weir_req = Q_max × 1000 / q_weir_design
        Q_max_Ls = Q_max * 1000  # L/s
        L_weir_required = Q_max_Ls / q_weir_design if q_weir_design > 0 else 0

        # 可用堰长: 每格三面出水堰 (两侧+末端), 总长 = n × (L + 2×B)
        L_weir_available = n * (L_calc + 2 * B)

        # 实际堰负荷
        q_weir_actual = Q_max_Ls / L_weir_available if L_weir_available > 0 else 0

        result.add_check(
            "堰口负荷 ≤ 10 L/(s·m)",
            q_weir_actual <= 10,
            round(q_weir_actual, 2),
            "≤ 10",
            "L/(s·m)",
        )
        if q_weir_actual > 10:
            result.add_warning(
                f"堰负荷 q={q_weir_actual:.1f} > 2.9 L/(s·m),"
                f"需堰长 {L_weir_required:.1f}m > 可用 {L_weir_available:.1f}m,建议增设堰长"
            )

        # ── 排砂管径校核 D ≥ 200mm ──
        # 最小排砂管径
        D_discharge = 200  # mm (最小要求)
        result.add_dimension(
            "排砂管最小管径",
            D_discharge,
            "mm",
            formula="D_pipe ≥ 200mm (重力排砂)",
            category="physical",
        )

        # ── 组装结果 ──
        result.add_dimension("格数", n, "格", formula="n ≥ 2", category="physical")
        result.add_dimension(
            "池长 L", L, "m", formula="L = v × t, ceil 0.5m", category="physical"
        )
        result.add_dimension(
            "单格宽度 B",
            B,
            "m",
            formula="B = A₁ / H, ceil 0.1m, ≥0.6m",
            category="physical",
        )
        result.add_dimension(
            "有效水深 H", h_eff, "m", formula="H ≤ 1.2m (规范强制)", category="physical"
        )
        result.add_dimension(
            "砂斗深度 h_斗",
            round(h_hopper, 2),
            "m",
            formula="h_斗 = (B-b₂)/2 × tan(α)",
            category="physical",
        )
        result.add_dimension(
            "总高度 H_t",
            H_rounded,
            "m",
            formula="H_t = H + h_斗 + h_free",
            category="physical",
        )
        result.add_dimension(
            "砂斗个数/格",
            n_hoppers_per_cell,
            "个",
            formula="n_hoppers = L / B",
            category="physical",
        )
        result.add_dimension(
            "砂斗总数", n_hoppers_per_cell * n, "个", category="physical"
        )
        result.add_dimension(
            "单斗容积",
            round(V_hopper_single, 2),
            "m³",
            formula="V_斗 = h/3×(b₁²+b₂²+b₁·b₂)",
            category="physical",
        )
        result.add_dimension(
            "砂斗总容积",
            round(V_hopper_total, 2),
            "m³",
            formula="V_total = V_斗 × n_hoppers × n",
            category="physical",
        )
        result.add_dimension(
            "需砂斗容积",
            round(V_hopper_needed_total, 2),
            "m³",
            formula="V_needed = V_sand,daily × T_sand",
            category="computed",
        )
        result.add_dimension(
            "设计水平流速",
            v_h,
            "m/s",
            formula="v = 设计取值 0.20~0.25",
            category="computed",
        )
        result.add_dimension(
            "实际水平流速",
            round(v_actual, 3),
            "m/s",
            formula="v_actual = Q_max/(n×B×H)",
            category="computed",
        )
        result.add_dimension(
            "停留时间", t_stay, "s", formula="t = 设计取值 30~60s", category="computed"
        )
        result.add_dimension("池底坡度", slope, "", category="physical")
        result.add_dimension(
            "日产砂体积",
            round(V_sand_daily, 3),
            "m³/d",
            formula="V_sand = Q_d × κ/1000",
            category="computed",
        )
        result.add_dimension(
            "需堰长 L_weir",
            round(L_weir_required, 1),
            "m",
            formula="L_weir = Q_max×1000/q_weir",
            category="computed",
        )
        result.add_dimension(
            "可用堰长",
            round(L_weir_available, 1),
            "m",
            formula="L_avail = n × B",
            category="physical",
        )
        result.add_dimension(
            "实际堰负荷",
            round(q_weir_actual, 2),
            "L/(s·m)",
            formula="q_actual = Q_max×1000/L_avail",
            category="computed",
        )

        # 概算用
        result.add_dimension(
            "沉砂池总面积", round(L * B * n, 1), "m²", category="physical"
        )
        result.add_dimension(
            "混凝土量估算",
            round(L * B * H_rounded * n * 1.3, 1),
            "m³",
            category="physical",
        )

        return result

    @classmethod
    def _vectorized_compute(
        cls, grid: dict, flow: "WaterFlow", quality: "WaterQuality", fixed: dict
    ) -> "np.ndarray":
        """向量化批量计算平流沉砂池"""
        n = grid["n"].astype(np.int32)
        v_h = grid["v_h"]
        t_stay = grid["t_stay"]
        h_eff = grid["h_eff"]
        h_super = fixed["h_super"]
        slope = fixed["slope"]
        hopper_angle = fixed["hopper_angle"]
        hopper_bottom = fixed["hopper_bottom"]
        kappa = fixed.get("kappa", 0.03)
        T_sand = fixed.get("T_sand", 2.0)
        q_weir_design = fixed.get("q_weir_design", 2.5)
        N = len(n)

        # 零流量守卫
        if flow.Q_design <= 0:
            dtype = np.dtype(
                [
                    ("L", np.float64),
                    ("B", np.float64),
                    ("h_eff_out", np.float64),
                    ("H_total", np.float64),
                    ("h_hopper", np.float64),
                    ("V_hopper_single", np.float64),
                    ("V_hopper_total", np.float64),
                    ("V_hopper_needed", np.float64),
                    ("V_sand_daily", np.float64),
                    ("n_hoppers_per_cell", np.int32),
                    ("v_actual", np.float64),
                    ("ratio_BH", np.float64),
                    ("L_weir_req", np.float64),
                    ("L_weir_avail", np.float64),
                    ("q_weir_actual", np.float64),
                    ("H", np.float64),
                    ("area_total", np.float64),
                    ("concrete_m3", np.float64),
                    ("ok_v", np.bool_),
                    ("ok_H", np.bool_),
                    ("ok_B", np.bool_),
                    ("ok_BH", np.bool_),
                    ("ok_hopper", np.bool_),
                    ("ok_weir", np.bool_),
                    ("val_v", np.float64),
                    ("val_H", np.float64),
                    ("val_B", np.float64),
                    ("val_BH", np.float64),
                    ("val_hopper", np.float64),
                    ("val_weir", np.float64),
                ]
            )
            return np.zeros(N, dtype=dtype)

        Q_max = flow.Q_design
        Q_avg_daily = flow.Q_avg_daily

        L_calc = v_h * t_stay
        L = np.ceil(L_calc / 0.5) * 0.5

        A_cross = np.where(v_h > 0, Q_max / (n * v_h), 0.0)
        B_calc = np.where(h_eff > 0, A_cross / h_eff, 0.0)
        B = np.round(np.ceil(np.maximum(B_calc, 0.6) / 0.1) * 0.1, 2)

        A_actual = B * h_eff
        v_actual = np.where(A_actual > 0, Q_max / (n * A_actual), 0.0)

        ok_v = (0.15 <= v_actual) & (v_actual <= 0.30)
        ok_H = h_eff <= 1.2
        ok_B = B >= 0.6
        ratio_BH = np.where(h_eff > 0, B / h_eff, 0.0)
        ok_BH = (1.0 <= ratio_BH) & (ratio_BH <= 2.0)

        # 砂斗
        b1 = B
        b2 = hopper_bottom
        alpha_rad = np.radians(hopper_angle)
        h_hopper = (b1 - b2) / 2.0 * np.tan(alpha_rad)

        V_hopper_single = h_hopper / 3.0 * (b1**2 + b2**2 + b1 * b2)
        n_hoppers_per_cell = np.maximum(1, (L / np.maximum(b1, 0.1)).astype(np.int32))
        V_hopper_total = V_hopper_single * n_hoppers_per_cell * n

        kappa_m3 = kappa / 1000.0
        V_sand_daily = Q_avg_daily * kappa_m3
        V_hopper_needed = V_sand_daily * T_sand
        ok_hopper = V_hopper_total >= V_hopper_needed

        H_total = h_eff + h_hopper + h_super

        # 堰
        Q_max_Ls = Q_max * 1000
        L_weir_avail = n * (L_calc + 2 * B)
        q_weir_actual = np.where(L_weir_avail > 0, Q_max_Ls / L_weir_avail, 0.0)
        ok_weir = q_weir_actual <= 10
        L_weir_req = np.where(q_weir_design > 0, Q_max_Ls / q_weir_design, 0.0)

        area_total = L * B * n
        concrete_m3 = L * B * H_total * n * 1.3

        dtype = np.dtype(
            [
                ("L", np.float64),
                ("B", np.float64),
                ("h_eff_out", np.float64),
                ("H_total", np.float64),
                ("h_hopper", np.float64),
                ("V_hopper_single", np.float64),
                ("V_hopper_total", np.float64),
                ("V_hopper_needed", np.float64),
                ("V_sand_daily", np.float64),
                ("n_hoppers_per_cell", np.int32),
                ("v_actual", np.float64),
                ("ratio_BH", np.float64),
                ("L_weir_req", np.float64),
                ("L_weir_avail", np.float64),
                ("q_weir_actual", np.float64),
                ("H", np.float64),
                ("area_total", np.float64),
                ("concrete_m3", np.float64),
                ("ok_v", np.bool_),
                ("ok_H", np.bool_),
                ("ok_B", np.bool_),
                ("ok_BH", np.bool_),
                ("ok_hopper", np.bool_),
                ("ok_weir", np.bool_),
                ("val_v", np.float64),
                ("val_H", np.float64),
                ("val_B", np.float64),
                ("val_BH", np.float64),
                ("val_hopper", np.float64),
                ("val_weir", np.float64),
            ]
        )
        result = np.empty(N, dtype=dtype)
        result["L"] = L
        result["B"] = B
        result["h_eff_out"] = h_eff
        result["H_total"] = H_total
        result["h_hopper"] = h_hopper
        result["V_hopper_single"] = V_hopper_single
        result["V_hopper_total"] = V_hopper_total
        result["V_hopper_needed"] = V_hopper_needed
        result["V_sand_daily"] = V_sand_daily
        result["n_hoppers_per_cell"] = n_hoppers_per_cell
        result["v_actual"] = v_actual
        result["ratio_BH"] = ratio_BH
        result["L_weir_req"] = L_weir_req
        result["L_weir_avail"] = L_weir_avail
        result["q_weir_actual"] = q_weir_actual
        result["H"] = result["H_total"]
        result["area_total"] = area_total
        result["concrete_m3"] = concrete_m3
        result["ok_v"] = ok_v
        result["ok_H"] = ok_H
        result["ok_B"] = ok_B
        result["ok_BH"] = ok_BH
        result["ok_hopper"] = ok_hopper
        result["ok_weir"] = ok_weir
        result["val_v"] = v_actual
        result["val_H"] = h_eff
        result["val_B"] = B
        result["val_BH"] = ratio_BH
        result["val_hopper"] = V_hopper_total
        result["val_weir"] = q_weir_actual
        return result
