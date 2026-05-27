"""gaomidu.py — 高密度沉淀池 (High-Density Sedimentation Tank)"""

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


class GaomiduNode(NodeBase):
    """高密度沉淀池

    公式来源: 中期报告 §3.6 (3-77)~(3-94)
    """

    NODE_TYPE = "gaomidu"
    NODE_NAME = "高密度沉淀池"
    NODE_CATEGORY = "深度处理"

    def _init_ports(self) -> None:
        """高密度沉淀池: MIXED进水 → MIXED出水 + SLUDGE排泥(化学污泥)"""
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
            "n": 4,
            "t_mix": 1.0,
            "t_floc": 10.0,
            "R_sludge": 0.03,
            "q_surf": 8.0,
            "L_tube": 1.0,
            "alpha_tube": 60.0,
            "h_clear": 1.0,
            "h_dist": 1.5,
            "h_super": 0.5,
            "t_thicken": 1.5,
            "P_out": 0.96,
            "D_PAC": 40.0,
            "k_PAC": 0.5,
            "G_mix": 750.0,
            "G_floc": 75.0,
            "X_r_assumed": 15.0,
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
                "污泥回流比",
                "R_sludge",
                value=0.03,
                default=0.03,
                min_val=0.01,
                max_val=1.80,
                step=0.01,
                unit="",
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
            ParamDef(
                "PAC投加量",
                "D_PAC",
                value=40,
                default=40,
                min_val=15,
                max_val=80,
                step=5,
                unit="mg/L",
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
        # ── 读取参数 ──
        n = int(self.get_param("n"))
        t_mix = self.get_param("t_mix")  # min
        t_floc = self.get_param("t_floc")  # min
        R_sludge = self.get_param("R_sludge")
        q_surf = self.get_param("q_surf")  # m³/(m²·h)
        L_tube = self.get_param("L_tube")  # m
        alpha_tube = self.get_param("alpha_tube")  # °
        h_clear = self.get_param("h_clear")  # m
        h_dist = self.get_param("h_dist")  # m
        h_super = self.get_param("h_super")  # m
        t_thicken = self.get_param("t_thicken")  # h
        D_PAC = self.get_param("D_PAC")  # mg/L
        k_PAC = self.get_param("k_PAC")  # kgDS/kgPAC
        G_mix = self.get_param("G_mix")  # s⁻¹
        G_floc = self.get_param("G_floc")  # s⁻¹
        X_r_assumed = self.get_param("X_r_assumed")  # g/L

        result = NodeResult(success=True)
        P_out = self.get_param("P_out")
        result.params = {
            "n": n,
            "t_mix": t_mix,
            "t_floc": t_floc,
            "R_sludge": R_sludge,
            "q_surf": q_surf,
            "L_tube": L_tube,
            "alpha_tube": alpha_tube,
            "h_clear": h_clear,
            "h_dist": h_dist,
            "h_super": h_super,
            "t_thicken": t_thicken,
            "D_PAC": D_PAC,
            "k_PAC": k_PAC,
            "G_mix": G_mix,
            "G_floc": G_floc,
            "X_r_assumed": X_r_assumed,
            "P_out": P_out,
        }

        # 水的动力粘度 (20°C)
        mu = 1.005e-3  # Pa·s

        # ── 单池流量 ──
        Q_single = flow.Q_design / n  # m³/s
        Q_single_m3h = Q_single * 3600  # m³/h

        # ═══════════════════════════════════════════════
        # (A) 快速混合区 — 公式(4-77)(4-78)
        # ═══════════════════════════════════════════════
        V_mix = Q_single * t_mix * 60.0  # m³
        P_mix = (G_mix**2) * mu * V_mix  # W
        result.add_dimension(
            "混合区容积",
            round(V_mix, 2),
            "m³",
            formula="V_mix = Q_max × t_mix",
            category="physical",
        )
        result.add_dimension(
            "混合区功率 P_mix",
            round(P_mix, 1),
            "W",
            formula="P_mix = G_mix² × μ × V_mix",
            category="computed",
        )
        result.add_check(
            "混合区 G_mix 500~1000 s⁻¹",
            500 <= G_mix <= 1000,
            round(G_mix, 0),
            "500~1000",
            "s⁻¹",
        )

        # ═══════════════════════════════════════════════
        # (B) 絮凝区(带污泥循环)— 公式(4-79)~(4-82)
        # ═══════════════════════════════════════════════
        Q_r = Q_single * R_sludge  # m³/s 回流污泥量
        Q_floc_total = Q_single + Q_r  # m³/s 进入絮凝区总流量
        V_floc = Q_floc_total * t_floc * 60.0  # m³
        P_floc = (G_floc**2) * mu * V_floc  # W
        result.add_dimension(
            "絮凝区容积",
            round(V_floc, 2),
            "m³",
            formula="V_floc = (1+R)×Q_max × t_floc",
            category="physical",
        )
        result.add_dimension(
            "絮凝区功率 P_floc",
            round(P_floc, 1),
            "W",
            formula="P_floc = G_floc² × μ × V_floc",
            category="computed",
        )
        result.add_check(
            "絮凝区 G_floc 50~100 s⁻¹",
            50 <= G_floc <= 100,
            round(G_floc, 0),
            "50~100",
            "s⁻¹",
        )

        # ═══════════════════════════════════════════════
        # (C) 斜管沉淀区 — 公式(4-83)(4-84)
        # ═══════════════════════════════════════════════
        A_settle = Q_single_m3h / q_surf  # m²
        sin_alpha = math.sin(math.radians(alpha_tube))
        # 斜管轴向流速 v₀ = Q_max / (A × sinθ) = q_surf / (3600 × sinθ)
        v_axial_m_s = q_surf / (3600.0 * sin_alpha)  # m/s
        v_axial = v_axial_m_s * 1000.0  # mm/s (便于显示)
        result.add_dimension(
            "沉淀区面积",
            round(A_settle, 1),
            "m²",
            formula="A = Q_max(m³/h) / q_surf",
            category="physical",
        )
        result.add_dimension(
            "斜管轴向流速 v₀",
            round(v_axial, 2),
            "mm/s",
            formula="v₀ = q_surf / (3600 × sinθ)",
            category="computed",
        )
        result.add_check(
            "斜管轴向流速 ≤ 5 mm/s", v_axial <= 5.0, round(v_axial, 2), "≤ 5", "mm/s"
        )

        # ── 池体尺寸 ──
        LB_ratio = 1.5
        B_pool = math.ceil(math.sqrt(A_settle / LB_ratio) / 0.5) * 0.5
        L_pool = math.ceil(A_settle / B_pool / 0.5) * 0.5
        A_actual = L_pool * B_pool
        ratio_LB = L_pool / B_pool
        result.add_dimension(
            "池长 L", L_pool, "m", formula="L = ceil(A / B, 0.5m)", category="physical"
        )
        result.add_dimension(
            "池宽 B",
            B_pool,
            "m",
            formula="B = ceil(√(A / 1.5), 0.5m)",
            category="physical",
        )
        result.add_check(
            "长宽比 L/B 1~2", 1.0 <= ratio_LB <= 2.0, round(ratio_LB, 2), "1~2", ""
        )

        # ═══════════════════════════════════════════════
        # (D) 污泥产量 — 公式(4-85)~(4-88)
        # ═══════════════════════════════════════════════
        SS_removal = self._removal_rates.get("SS", 0.90)
        SS_removed = quality.SS * SS_removal  # mg/L
        # W_SS = Q_d × (C₀ - Cₑ) × 10⁻⁶  (t/d → ×1000 = kg/d),全厂总量
        S_dry_SS_total = flow.Q_avg_daily * SS_removed / 1000.0  # kg/d (总)
        S_dry_chem_total = flow.Q_avg_daily * (D_PAC / 1000.0) * k_PAC  # kg/d (总)
        S_dry_total = S_dry_SS_total + S_dry_chem_total  # kg/d (总)

        # 进入浓缩区污泥含水率 P_w,in = 99% (spec: 99~99.5%)
        P_in = 0.99
        V_sludge_wet_total = S_dry_total / ((1 - P_in) * 1000.0)  # m³/d (总)

        # 单池污泥量 (每池下方独立浓缩区)
        S_dry_per = S_dry_total / n
        V_sludge_wet_per = V_sludge_wet_total / n

        result.add_dimension(
            "SS去除干污泥 W_SS(总)",
            round(S_dry_SS_total, 1),
            "kg/d",
            formula="W_SS = Q_d × (C₀-Cₑ) × 10⁻³",
            category="computed",
        )
        result.add_dimension(
            "化学干污泥 W_chem(总)",
            round(S_dry_chem_total, 1),
            "kg/d",
            formula="W_chem = Q_d × D_PAC × κ_PAC × 10⁻³",
            category="computed",
        )
        result.add_dimension(
            "总干污泥 W_s(总)",
            round(S_dry_total, 1),
            "kg/d",
            formula="W_s = W_SS + W_chem",
            category="computed",
        )
        result.add_dimension(
            "单池干污泥 W_s(单池)",
            round(S_dry_per, 1),
            "kg/d",
            formula="W_s(单池) = W_s(总) / n",
            category="computed",
        )
        result.add_dimension(
            "日湿污泥量 V_s,in(总)",
            round(V_sludge_wet_total, 1),
            "m³/d",
            formula="V_s,in = W_s / ((1-P_in)×1000), P_in=0.99",
            category="computed",
        )

        # ═══════════════════════════════════════════════
        # (E) 污泥浓缩区(单池)— 公式(4-89)~(4-92)
        # ═══════════════════════════════════════════════
        # 每池下方独立浓缩区,使用单池污泥量和单池面积
        V_thicken_per = V_sludge_wet_per * t_thicken / 24.0  # m³ (单池)
        h_thicken = max(V_thicken_per / A_actual, 0.5) if A_actual > 0 else 0.5

        # 固体通量 G = W_s(单池) / A(单池) ≤ G_lim (4-91)
        solid_flux = S_dry_per / A_actual if A_actual > 0 else 0  # kgDS/(m²·d)
        result.add_dimension(
            "浓缩区高度 h_thick(单池)",
            round(h_thicken, 2),
            "m",
            formula="h_thick = V_thicken(单池) / A(单池)",
            category="physical",
        )
        result.add_dimension(
            "固体通量 G(单池)",
            round(solid_flux, 1),
            "kgDS/(m²·d)",
            formula="G = W_s(单池) / A(单池)",
            category="computed",
        )
        result.add_check(
            "固体通量 G ≤ 150 kgDS/(m²·d)",
            solid_flux <= 150,
            round(solid_flux, 1),
            "≤ 150",
            "kgDS/(m²·d)",
        )

        # 回流污泥浓度校核 X_r = W_s(单池) / Q_r  (4-92)
        Q_r_daily = Q_r * 86400.0  # m³/d (单池回流量)
        X_r_calc = S_dry_per / Q_r_daily if Q_r_daily > 0 else 0  # kg/m³ = g/L
        result.add_dimension(
            "回流污泥浓度 X_r(单池)",
            round(X_r_calc, 1),
            "g/L",
            formula="X_r = W_s(单池) / Q_r",
            category="computed",
        )
        result.add_check(
            "回流污泥浓度 X_r ≥ 0 g/L", X_r_calc >= 0, round(X_r_calc, 1), "≥ 0", "g/L"
        )
        if X_r_calc < 1.0:
            result.add_warning(
                f"回流污泥浓度极低 X_r={X_r_calc:.1f} g/L (< 1.0),"
                f"进水SS={quality.SS:.0f} mg/L偏低,深度处理段属正常现象"
            )

        # ═══════════════════════════════════════════════
        # (F) 池体总高度 — 公式(4-93)
        # ═══════════════════════════════════════════════
        h_tube_vert = L_tube * sin_alpha
        H_total = h_super + h_clear + h_dist + h_thicken + h_tube_vert
        H_rounded = math.ceil(H_total / 0.1) * 0.1
        result.add_dimension(
            "总高度 H_t",
            H_rounded,
            "m",
            formula="H_t = h_free+h_clear+h_tube+h_dist+h_thick",
            category="physical",
        )

        # ═══════════════════════════════════════════════
        # (G) 出水堰负荷 — 公式(4-94)
        # ═══════════════════════════════════════════════
        # 设双侧集水堰,堰长 ≈ 2 × (L+B) × 2 (双侧×2边)
        weir_len = 2.0 * (L_pool + B_pool) * 2.0  # m (双侧堰, 每侧沿池周)
        q_weir = Q_single * 1000.0 / weir_len if weir_len > 0 else 0  # L/(s·m)
        result.add_dimension(
            "出水堰总长 L_w",
            round(weir_len, 1),
            "m",
            formula="L_w = 2×(L+B)×2 (双侧堰)",
            category="physical",
        )
        result.add_dimension(
            "堰负荷 q_堰",
            round(q_weir, 2),
            "L/(s·m)",
            formula="q_堰 = Q_max(L/s) / L_w(m)",
            category="computed",
        )
        result.add_check(
            "堰负荷 1.5~2.9 L/(s·m)",
            1.5 <= q_weir <= 2.9,
            round(q_weir, 2),
            "1.5~2.9",
            "L/(s·m)",
        )

        # ── 汇总 ──
        result.add_dimension("池数", n, "座")
        result.add_dimension(
            "PAC日耗量", round(D_PAC * flow.Q_avg_daily / 1000, 1), "kg/d"
        )

        # ── 污泥输出 (SLUDGE 端口, 化学污泥, 全厂总量) ──
        self._sludge_output = SludgeFlow(
            Q_wet=V_sludge_wet_total,
            DS=S_dry_total,
            P_moisture=P_in,
            VS_ratio=0.40,
        )

        return result

    @classmethod
    def _vectorized_compute(
        cls, grid: dict, flow: "WaterFlow", quality: "WaterQuality", fixed: dict
    ) -> "np.ndarray":
        """向量化高密度沉淀池

        grid: n, t_mix, t_floc, q_surf
        fixed: R_sludge, L_tube, alpha_tube, h_clear, h_dist, h_super,
               t_thicken, D_PAC, k_PAC, G_mix, G_floc, X_r_assumed
        """
        n = grid["n"].astype(np.int32)
        t_mix = grid["t_mix"]
        t_floc = grid["t_floc"]
        q_surf = grid["q_surf"]
        R_sludge = fixed["R_sludge"]
        alpha_tube = fixed["alpha_tube"]
        h_clear = fixed["h_clear"]
        h_dist = fixed["h_dist"]
        h_super = fixed["h_super"]
        t_thicken = fixed["t_thicken"]
        D_PAC = fixed["D_PAC"]
        k_PAC = fixed["k_PAC"]
        L_tube = fixed["L_tube"]
        G_mix = fixed.get("G_mix", 750.0)
        G_floc = fixed.get("G_floc", 75.0)
        N = len(n)

        # 零流量守卫
        if flow.Q_design <= 0:
            dtype = np.dtype(
                [
                    ("V_mix", np.float64),
                    ("V_floc", np.float64),
                    ("A_settle", np.float64),
                    ("L_pool", np.float64),
                    ("B_pool", np.float64),
                    ("P_mix", np.float64),
                    ("P_floc", np.float64),
                    ("v_axial", np.float64),
                    ("H_total", np.float64),
                    ("S_dry_SS_total", np.float64),
                    ("S_dry_chem_total", np.float64),
                    ("S_dry_total", np.float64),
                    ("h_thicken", np.float64),
                    ("solid_flux", np.float64),
                    ("X_r_calc", np.float64),
                    ("weir_len", np.float64),
                    ("q_weir", np.float64),
                    ("L", np.float64),
                    ("B", np.float64),
                    ("H", np.float64),
                    ("concrete_m3", np.float64),
                    ("ok_axial_v", np.bool_),
                    ("ok_solid_flux", np.bool_),
                    ("ok_G_mix", np.bool_),
                    ("ok_G_floc", np.bool_),
                    ("ok_LB", np.bool_),
                    ("ok_X_r", np.bool_),
                    ("ok_weir", np.bool_),
                    ("val_axial_v", np.float64),
                    ("val_solid_flux", np.float64),
                    ("val_G_mix", np.float64),
                    ("val_G_floc", np.float64),
                    ("val_LB", np.float64),
                    ("val_X_r", np.float64),
                    ("val_weir", np.float64),
                ]
            )
            return np.zeros(N, dtype=dtype)

        mu = 1.005e-3
        Q_single = flow.Q_design / n
        Q_single_m3h = Q_single * 3600

        # (A) 快速混合区
        V_mix = Q_single * t_mix * 60.0
        P_mix = (G_mix**2) * mu * V_mix
        ok_G_mix = np.full(N, 500 <= G_mix <= 1000)

        # (B) 絮凝区
        Q_r = Q_single * R_sludge
        Q_floc_total = Q_single + Q_r
        V_floc = Q_floc_total * t_floc * 60.0
        P_floc = (G_floc**2) * mu * V_floc
        ok_G_floc = np.full(N, 50 <= G_floc <= 100)

        # (C) 斜管沉淀区
        A_settle = Q_single_m3h / q_surf
        sin_alpha = np.sin(np.radians(alpha_tube))
        v_axial = q_surf / (3600.0 * sin_alpha) * 1000.0  # mm/s
        ok_axial = v_axial <= 5.0

        # 池体尺寸
        LB_ratio = 1.5
        B_pool = np.ceil(np.sqrt(A_settle / LB_ratio) / 0.5) * 0.5
        L_pool = np.ceil(A_settle / B_pool / 0.5) * 0.5
        A_actual = L_pool * B_pool
        ratio_LB = L_pool / B_pool
        ok_LB = (1.0 <= ratio_LB) & (ratio_LB <= 2.0)

        # (D) 污泥产量
        SS_removal = 0.90
        SS_removed = quality.SS * SS_removal
        S_dry_SS_total = flow.Q_avg_daily * SS_removed / 1000.0
        S_dry_chem_total = flow.Q_avg_daily * (D_PAC / 1000.0) * k_PAC
        S_dry_total = S_dry_SS_total + S_dry_chem_total
        P_in = 0.99
        V_sludge_wet_total = np.where(
            P_in < 1, S_dry_total / ((1 - P_in) * 1000.0), 0.0
        )
        # 单池量
        S_dry_per = S_dry_total / n
        V_sludge_wet_per = V_sludge_wet_total / n

        # (E) 浓缩区(单池)
        V_thicken_per = V_sludge_wet_per * t_thicken / 24.0
        h_thicken = np.maximum(V_thicken_per / A_actual, 0.5)
        solid_flux = np.where(A_actual > 0, S_dry_per / A_actual, 0.0)
        ok_flux = solid_flux <= 150

        # 回流污泥浓度 X_r = W_s(单池) / Q_r  (单池)
        Q_r_daily = Q_r * 86400.0
        X_r_calc = np.where(Q_r_daily > 0, S_dry_per / Q_r_daily, 0.0)
        ok_X_r = X_r_calc >= 0

        # (F) 总高度
        h_tube_vert = L_tube * sin_alpha
        H_total = h_super + h_clear + h_dist + h_thicken + h_tube_vert

        # (G) 出水堰
        weir_len = 2.0 * (L_pool + B_pool) * 2.0
        q_weir = np.where(weir_len > 0, Q_single * 1000.0 / weir_len, 0.0)
        ok_weir = (1.5 <= q_weir) & (q_weir <= 2.9)

        concrete_m3 = L_pool * B_pool * H_total * n * 0.4

        dtype = np.dtype(
            [
                ("V_mix", np.float64),
                ("V_floc", np.float64),
                ("A_settle", np.float64),
                ("L_pool", np.float64),
                ("B_pool", np.float64),
                ("P_mix", np.float64),
                ("P_floc", np.float64),
                ("v_axial", np.float64),
                ("H_total", np.float64),
                ("S_dry_SS_total", np.float64),
                ("S_dry_chem_total", np.float64),
                ("S_dry_total", np.float64),
                ("h_thicken", np.float64),
                ("solid_flux", np.float64),
                ("X_r_calc", np.float64),
                ("weir_len", np.float64),
                ("q_weir", np.float64),
                ("L", np.float64),
                ("B", np.float64),
                ("H", np.float64),
                ("concrete_m3", np.float64),
                ("ok_axial_v", np.bool_),
                ("ok_solid_flux", np.bool_),
                ("ok_G_mix", np.bool_),
                ("ok_G_floc", np.bool_),
                ("ok_LB", np.bool_),
                ("ok_X_r", np.bool_),
                ("ok_weir", np.bool_),
                ("val_axial_v", np.float64),
                ("val_solid_flux", np.float64),
                ("val_G_mix", np.float64),
                ("val_G_floc", np.float64),
                ("val_LB", np.float64),
                ("val_X_r", np.float64),
                ("val_weir", np.float64),
            ]
        )
        result = np.empty(N, dtype=dtype)
        result["V_mix"] = V_mix
        result["V_floc"] = V_floc
        result["A_settle"] = A_settle
        result["L_pool"] = L_pool
        result["B_pool"] = B_pool
        result["P_mix"] = P_mix
        result["P_floc"] = P_floc
        result["v_axial"] = v_axial
        result["H_total"] = H_total
        result["S_dry_SS_total"] = S_dry_SS_total
        result["S_dry_chem_total"] = S_dry_chem_total
        result["S_dry_total"] = S_dry_total
        result["h_thicken"] = h_thicken
        result["solid_flux"] = solid_flux
        result["X_r_calc"] = X_r_calc
        result["weir_len"] = weir_len
        result["q_weir"] = q_weir
        result["concrete_m3"] = concrete_m3
        result["L"] = result["L_pool"]
        result["B"] = result["B_pool"]
        result["H"] = result["H_total"]
        result["ok_axial_v"] = ok_axial
        result["ok_solid_flux"] = ok_flux
        result["ok_G_mix"] = ok_G_mix
        result["ok_G_floc"] = ok_G_floc
        result["ok_LB"] = ok_LB
        result["ok_X_r"] = ok_X_r
        result["ok_weir"] = ok_weir
        result["val_axial_v"] = v_axial
        result["val_solid_flux"] = solid_flux
        result["val_G_mix"] = np.full(N, G_mix)
        result["val_G_floc"] = np.full(N, G_floc)
        result["val_LB"] = ratio_LB
        result["val_X_r"] = X_r_calc
        result["val_weir"] = q_weir
        return result
