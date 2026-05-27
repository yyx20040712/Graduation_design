"""cass.py — CASS 反应器 (Cyclic Activated Sludge System)"""

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
)


class CASSNode(NodeBase):
    """CASS 循环式活性污泥反应器

    公式来源: 中期报告 §3.5 (3-53)~(3-76)
    """

    NODE_TYPE = "cass"
    NODE_NAME = "CASS反应器"
    NODE_CATEGORY = "二级处理"

    def _init_ports(self) -> None:
        """CASS: MIXED进水 → MIXED出水 + SLUDGE排泥(剩余污泥)"""
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
                name="剩余污泥",
                port_type=PortType.SLUDGE,
                direction="output",
                node_id=self.node_id,
            ),
        ]

    @classmethod
    def _default_params(cls) -> Dict[str, float]:
        return {
            "n": 4,
            "Ns": 0.08,
            "X_MLSS": 3500,
            "f": 0.75,
            "theta_c": 20,
            "Y": 0.6,
            "Kd20": 0.05,
            "theta_t": 1.04,
            "T_design": 12,
            "Tc": 6,
            "lam": 0.3,
            "H_max": 6.0,
            "h_super": 0.5,
            "r_selector": 0.15,
            "SVI": 120,
            "delta_H_safe": 0.5,
            "a_prime": 0.5,
            "b_prime": 0.12,
            "t_d": 1,
        }

    def _build_param_defs(self) -> List[ParamDef]:
        return [
            ParamDef(
                "池数", "n", value=4, default=4, min_val=2, max_val=8, step=1, unit="座"
            ),
            ParamDef(
                "BOD负荷 Ns",
                "Ns",
                value=0.08,
                default=0.08,
                min_val=0.05,
                max_val=0.15,
                step=0.01,
                unit="kgBOD5/(kgMLSS·d)",
            ),
            ParamDef(
                "MLSS浓度 X",
                "X_MLSS",
                value=3500,
                default=3500,
                min_val=2500,
                max_val=4500,
                step=100,
                unit="mg/L",
            ),
            ParamDef(
                "MLVSS/MLSS f",
                "f",
                value=0.75,
                default=0.75,
                min_val=0.7,
                max_val=0.8,
                step=0.01,
                unit="",
            ),
            ParamDef(
                "设计污泥龄 θc",
                "theta_c",
                value=20,
                default=20,
                min_val=10,
                max_val=30,
                step=1,
                unit="d",
            ),
            ParamDef(
                "产率系数 Y",
                "Y",
                value=0.6,
                default=0.6,
                min_val=0.4,
                max_val=0.8,
                step=0.05,
                unit="kgVSS/kgBOD5",
            ),
            ParamDef(
                "设计水温 T",
                "T_design",
                value=12,
                default=12,
                min_val=8,
                max_val=25,
                step=1,
                unit="°C",
            ),
            ParamDef(
                "工作周期 Tc",
                "Tc",
                value=6,
                default=6,
                min_val=4,
                max_val=8,
                step=1,
                unit="h",
            ),
            ParamDef(
                "充水比 λ",
                "lam",
                value=0.3,
                default=0.3,
                min_val=0.2,
                max_val=0.4,
                step=0.05,
                unit="",
            ),
            ParamDef(
                "最大有效水深",
                "H_max",
                value=6.0,
                default=6.0,
                min_val=4.0,
                max_val=6.0,
                step=0.1,
                unit="m",
            ),
            ParamDef(
                "超高",
                "h_super",
                value=0.5,
                default=0.5,
                min_val=0.5,
                max_val=0.5,
                step=0.1,
                unit="m",
            ),
            ParamDef(
                "选择区比例",
                "r_selector",
                value=0.15,
                default=0.15,
                min_val=0.10,
                max_val=0.20,
                step=0.01,
                unit="",
            ),
            ParamDef(
                "SVI",
                "SVI",
                value=120,
                default=120,
                min_val=80,
                max_val=150,
                step=5,
                unit="mL/g",
            ),
            ParamDef(
                "安全距离 ΔH",
                "delta_H_safe",
                value=0.5,
                default=0.5,
                min_val=0.3,
                max_val=0.8,
                step=0.1,
                unit="m",
            ),
        ]

    @classmethod
    def _default_removal_rates(cls) -> Dict[str, float]:
        return {
            "BOD5": 0.92,
            "COD": 0.88,
            "SS": 0.70,
            "NH3N": 0.90,
            "TN": 0.75,
            "TP": 0.65,
        }

    def calculate(self, flow: WaterFlow, quality: WaterQuality) -> NodeResult:
        # ── 读取参数 ──
        n = int(self.get_param("n"))
        Ns = self.get_param("Ns")
        X_MLSS = self.get_param("X_MLSS")
        f = self.get_param("f")
        theta_c_design = self.get_param("theta_c")
        Y = self.get_param("Y")
        Kd20 = self.get_param("Kd20")
        theta_t = self.get_param("theta_t")
        T_design = self.get_param("T_design")
        Tc = self.get_param("Tc")
        lam = self.get_param("lam")
        H_max = self.get_param("H_max")
        h_super = self.get_param("h_super")
        r_selector = self.get_param("r_selector")
        SVI = self.get_param("SVI")
        delta_H_safe = self.get_param("delta_H_safe")
        a_prime = self.get_param("a_prime")
        b_prime = self.get_param("b_prime")
        t_d = self.get_param("t_d")

        result = NodeResult(success=True)
        result.params = {
            "n": n,
            "Ns": Ns,
            "X_MLSS": X_MLSS,
            "f": f,
            "theta_c": theta_c_design,
            "Y": Y,
            "Kd20": Kd20,
            "theta_t": theta_t,
            "T_design": T_design,
            "Tc": Tc,
            "lam": lam,
            "H_max": H_max,
            "h_super": h_super,
            "r_selector": r_selector,
            "SVI": SVI,
            "delta_H_safe": delta_H_safe,
            "a_prime": a_prime,
            "b_prime": b_prime,
            "t_d": t_d,
        }

        Q_avg = flow.Q_avg_daily  # m³/d
        X_kg = X_MLSS / 1000.0  # mg/L → kg/m³

        # ── (1) 温度修正衰减系数 (3-53) ──
        KdT = Kd20 * (theta_t ** (T_design - 20))  # d⁻¹

        # ── (2) 主反应区总有效容积 (3-54) ──
        S0_kg = quality.BOD5 / 1000.0  # mg/L → kg/m³
        Se_kg = 10.0 / 1000.0  # 出水 BOD5=10 mg/L (一级A)
        V_main = Q_avg * (S0_kg - Se_kg) / (Ns * X_kg * f)  # m³ (所有池总容积)

        # ── (3) 单池容积 (3-55)(3-56)(3-57) ──
        V_main_single = V_main / n
        V_selector = V_main_single * r_selector
        V_eff_single = V_main_single + V_selector

        # ── (4) 平面尺寸 (3-58)~(3-60) ──
        A_single = V_eff_single / H_max
        # L/B target = 2.0, B 受 H_max 约束: B/H_max ∈ [1, 2]
        B_candidate = math.sqrt(A_single / 2.0)
        B = max(H_max, min(B_candidate, 2.0 * H_max))
        B = max(math.ceil(B / 1.0) * 1.0, 1.0)
        L = max(math.ceil(A_single / B / 1.0) * 1.0, B)
        ratio_LB = L / B
        ratio_BH = B / H_max

        result.add_check(
            "长宽比 L/B", 4 <= ratio_LB <= 6, round(ratio_LB, 2), "4~6", ""
        )
        result.add_check(
            "宽高比 B/H", 1 <= ratio_BH <= 2, round(ratio_BH, 2), "1~2", ""
        )

        # ── (5) 实际有效容积 ──
        A_actual = L * B
        V_eff_actual = A_actual * H_max

        # ── (6) 滗水高度 ──
        H_decant = H_max * lam

        # ── (7) 泥面高度 (3-63) ──
        H_sludge = H_max * X_MLSS * SVI / 1e6

        # ── (8) 安全距离 (3-64)(3-65) — 约束 1.5~2.0m,不满足则调整 λ ──
        H_safe = H_max - H_decant - H_sludge
        safe_ok = 1.5 <= H_safe <= 2.0
        lam_original = lam
        if not safe_ok:
            # λ 调整: H_safe = H_max × (1 - λ - H_sludge/H_max)
            # 目标 H_safe = 1.75m (中点),钳制到 [0.2, 0.4]
            lam = max(0.2, min(0.4, 1.0 - H_sludge / H_max - 1.75 / H_max))
            H_decant = H_max * lam
            H_safe = H_max - H_decant - H_sludge
            safe_ok = 1.5 <= H_safe <= 2.0
            if lam != lam_original:
                result.params["lam"] = lam  # 同步更新参数记录
                result.add_warning(
                    f"安全距离 {H_safe:.2f}m 不满足 1.5~2.0m,"
                    f"充水比 λ 已自动从 {lam_original:.3f} 调整为 {lam:.3f}"
                )
        result.add_check("安全距离 1.5~2.0m", safe_ok, round(H_safe, 2), "1.5~2.0", "m")

        # ── (6b) 充水比一致性校核 (3-61)(3-62) — 放在 λ 调整之后 ──
        lam_check = Q_avg * Tc / (24 * n * V_eff_actual)
        lam_deviation = abs(lam_check - lam) / lam if lam > 0 else 0
        result.add_dimension(
            "设计充水比 λ_design",
            round(lam, 3),
            "",
            formula="λ_design = 用户设定值 (0.2~0.4)",
            category="computed",
        )
        result.add_dimension(
            "实际充水比 λ_actual",
            round(lam_check, 3),
            "",
            formula="λ_actual = Q_avg × Tc / (24 × n × V_eff)",
            category="computed",
        )
        result.add_check(
            "充水比一致性 |λ_actual-λ_design|/λ_design < 15%",
            lam_deviation < 0.15,
            round(lam_deviation * 100, 1),
            "< 15%",
            "%偏差",
        )

        # ── (9) 总高度 (3-66) ──
        H_total = H_max + h_super

        # ── (10) 剩余污泥 (4-76)(4-77)(4-78) ──
        # ① 剩余生物污泥量 (4-76): ΔXv = Y·Qd·(S0-Se)/1000 - Kd(T)·V·X·f/θc
        Px_bio = (
            Y * Q_avg * (S0_kg - Se_kg) - KdT * V_main * X_kg * f / theta_c_design
        )  # kgVSS/d

        # ② 剩余非生物污泥量 (4-77): ΔXs = Qd·(1-f·f_b)·(C0-Ce)/1000
        f_b = 0.7  # 进水VSS中可生化系数
        C0 = quality.SS  # 进水SS, mg/L
        Ce = C0 * (1.0 - self._removal_rates.get("SS", 0.70))  # 出水SS, mg/L
        Px_nbio = Q_avg * (1.0 - f * f_b) * (C0 - Ce) / 1000.0  # kg/d

        # ③ 剩余污泥总量 (4-78)
        Px_total = Px_bio + Px_nbio  # kg/d

        # ── (11) 污泥龄校核 (4-79) ──
        # θc' = V·X·f / ΔXv
        #   V = 主反应区总容积 (V_main), m³
        #   X = MLSS浓度 (X_kg), kg/m³
        #   f = MLVSS/MLSS 比值
        #   ΔXv = 每日挥发性污泥产量 (Px_bio), kgVSS/d
        # 校核: θc_design ≤ θc' ≤ 30 d
        if Px_bio > 0:
            theta_c_prime = V_main * X_kg * f / Px_bio  # d
        else:
            theta_c_prime = float("inf")
        theta_c_ok = theta_c_design <= theta_c_prime <= 30
        result.add_check(
            "污泥龄校核 θc'",
            theta_c_ok,
            round(theta_c_prime, 1),
            f"{theta_c_design}~30",
            "d",
        )

        # ── (11b) 硝化污泥龄校核 (4-79 注) ──
        # 当需要满足氨氮完全硝化要求时,θc'一般不应小于15~30 d
        result.add_check(
            "硝化污泥龄校核 θc'≥15d",
            15 <= theta_c_prime <= 30,
            round(theta_c_prime, 1),
            "15~30",
            "d",
        )

        # ── (12) 需氧量 (3-71)~(3-74) ──
        # 碳化需氧量
        O2_carbon = (
            a_prime * Q_avg * (S0_kg - Se_kg) + b_prime * V_main * X_kg * f
        )  # kgO2/d

        # 硝化需氧量
        N_synth = 0.124 * Px_bio  # 细胞合成用氮 kgN/d
        NH3_load = Q_avg * (quality.NH3N - 5.0) / 1000.0  # kgN/d
        O2_nitrification = 4.57 * max(0.0, NH3_load - N_synth)  # kgO2/d

        # 反硝化产氧
        TN_load = Q_avg * (quality.TN - 15.0) / 1000.0  # kgN/d
        O2_denitrification = 2.86 * max(0.0, TN_load - N_synth)  # kgO2/d

        # 总需氧量
        O2_total = O2_carbon + O2_nitrification - O2_denitrification
        result.add_check(
            "总需氧量 > 0", O2_total > 0, round(O2_total, 1), "> 0", "kgO2/d"
        )

        # ── (13) 滗水器 (3-75)(3-76) ──
        Q_decant = V_eff_actual * lam / t_d  # m³/h

        # ── (14) 滗水器堰口长度 (4-76) ──
        # L_w = Q_h / q_L, 式中:
        #   Q_h = 滗水流量 (m³/h)
        #   q_L = 堰口负荷, 限值 20~30 L/(s·m) = 72~108 m³/(m·h)
        #   单位换算: 1 L/(s·m) = 3.6 m³/(m·h)
        q_L = 25.0  # 设计堰口负荷 L/(s·m)
        q_L_m3h = q_L * 3.6  # 转换为 m³/(m·h)
        L_w = Q_decant / q_L_m3h if q_L_m3h > 0 else 0  # m
        q_L_actual = Q_decant / max(L_w, 0.01) / 3.6  # 反算实际堰口负荷 L/(s·m)
        result.add_dimension(
            "滗水器堰口长度 L_w",
            round(L_w, 2),
            "m",
            formula="L_w = Q_h / (q_L × 3.6), q_L=25 L/(s·m)",
            category="physical",
        )
        result.add_check(
            "堰口负荷 q_L 20~30 L/(s·m)",
            20 <= q_L_actual <= 30,
            round(q_L_actual, 1),
            "20~30",
            "L/(s·m)",
        )

        # ── 组装结果 ──
        result.add_dimension("池数", n, "座")
        result.add_dimension("主反应区总容积", round(V_main, 1), "m³")
        result.add_dimension("单池主反应区容积", round(V_main_single, 1), "m³")
        result.add_dimension("选择区容积", round(V_selector, 1), "m³")
        result.add_dimension("单池总有效容积", round(V_eff_actual, 1), "m³")
        result.add_dimension("池长 L", L, "m")
        result.add_dimension("池宽 B", B, "m")
        result.add_dimension("长宽比 L/B", round(ratio_LB, 2), "")
        result.add_dimension("宽高比 B/H", round(ratio_BH, 2), "")
        result.add_dimension("有效水深 H_max", H_max, "m")
        result.add_dimension("总高度", H_total, "m")
        result.add_dimension("滗水高度", round(H_decant, 2), "m")
        result.add_dimension("污泥层高度", round(H_sludge, 2), "m")
        result.add_dimension("安全距离", round(H_safe, 2), "m")
        result.add_dimension("进水BOD5", quality.BOD5, "mg/L")
        result.add_dimension("出水BOD5", 10.0, "mg/L")
        result.add_dimension("BOD负荷 Ns", Ns, "kgBOD5/(kgMLSS·d)")
        result.add_dimension(
            "实际污泥龄 θc'",
            round(theta_c_prime, 1),
            "d",
            formula="θc' = V·X·f / ΔXv, (4-79)",
            category="computed",
        )
        result.add_dimension("剩余生物污泥", round(Px_bio, 1), "kgVSS/d")
        result.add_dimension("剩余非生物污泥", round(Px_nbio, 1), "kg/d")
        result.add_dimension("剩余污泥总量", round(Px_total, 1), "kg/d")
        result.add_dimension("碳化需氧量", round(O2_carbon, 1), "kgO2/d")
        result.add_dimension("硝化需氧量", round(O2_nitrification, 1), "kgO2/d")
        result.add_dimension("反硝化产氧", round(O2_denitrification, 1), "kgO2/d")
        result.add_dimension("总需氧量", round(O2_total, 1), "kgO2/d")
        result.add_dimension("单池滗水流量", round(Q_decant, 1), "m³/h")
        result.add_dimension("设计水温衰减系数 KdT", round(KdT, 4), "d⁻¹")

        # ── 污泥输出 (SLUDGE 端口, 剩余活性污泥) ──
        P_moisture_was = 0.992  # 剩余活性污泥含水率 99.2%
        Q_wet_was = Px_total / ((1 - P_moisture_was) * 1000.0) if Px_total > 0 else 0.0
        vs_ratio_was = Px_bio / max(Px_total, 0.01) if Px_total > 0 else 0.70
        self._sludge_output = SludgeFlow(
            Q_wet=Q_wet_was,
            DS=Px_total,
            P_moisture=P_moisture_was,
            VS_ratio=min(max(vs_ratio_was, 0.0), 1.0),
        )

        return result

    @classmethod
    def _vectorized_compute(
        cls, grid: dict, flow: "WaterFlow", quality: "WaterQuality", fixed: dict
    ) -> "np.ndarray":
        """向量化 CASS 反应器 — 最复杂模块 (7 自由变量 × 4 取值 = 9216 组合)

        grid: n, Ns, X_MLSS, theta_c, Tc, lam, H_max
        fixed: f, Y, Kd20, theta_t, T_design, h_super, r_selector, SVI, delta_H_safe, a_prime, b_prime, t_d
        """
        n = grid["n"].astype(np.int32)
        Ns = grid["Ns"]
        X_MLSS = grid["X_MLSS"]
        theta_c_design = grid["theta_c"]
        Tc = grid["Tc"]
        lam = grid["lam"]
        H_max = grid["H_max"]
        f = fixed["f"]
        Y = fixed["Y"]
        Kd20 = fixed["Kd20"]
        theta_t = fixed["theta_t"]
        T_design = fixed["T_design"]
        h_super = fixed["h_super"]
        r_selector = fixed["r_selector"]
        SVI = fixed["SVI"]
        delta_H_safe = fixed["delta_H_safe"]
        a_prime = fixed["a_prime"]
        b_prime = fixed["b_prime"]
        t_d = fixed["t_d"]
        N = len(n)

        Q_avg = flow.Q_avg_daily
        X_kg = X_MLSS / 1000.0

        # (1) 温度修正衰减系数
        KdT = Kd20 * (theta_t ** (T_design - 20))

        # (2) 主反应区总有效容积
        S0_kg = quality.BOD5 / 1000.0
        Se_kg = 10.0 / 1000.0
        V_main = Q_avg * (S0_kg - Se_kg) / (Ns * X_kg * f)

        # (3) 单池容积
        V_main_single = V_main / n
        V_selector = V_main_single * r_selector
        V_eff_single = V_main_single + V_selector

        # (4) 平面尺寸 (L/B target = 2.0, 但 B 受 H_max 约束)
        A_single = V_eff_single / H_max
        # B 须满足 B/H_max ∈ [1, 2],即 B ∈ [H_max, 2*H_max]
        B_candidate = np.sqrt(A_single / 2.0)
        B = np.clip(B_candidate, H_max, 2 * H_max)
        B = np.maximum(np.ceil(B / 1.0) * 1.0, 1.0)
        # L 由面积除以 B 得到
        L = np.ceil(A_single / B / 1.0) * 1.0
        L = np.maximum(L, B)  # L ≥ B
        ratio_LB = L / B
        ratio_BH = B / H_max

        ok_LB = (4 <= ratio_LB) & (ratio_LB <= 6)
        ok_BH = (1 <= ratio_BH) & (ratio_BH <= 2)

        # (5) 实际有效容积
        A_actual = L * B
        V_eff_actual = A_actual * H_max

        # (6) 滗水高度 + 充水比一致性
        H_decant = H_max * lam
        lam_check = Q_avg * Tc / (24 * n * V_eff_actual)
        lam_deviation = np.where(lam > 0, np.abs(lam_check - lam) / lam, 0.0)
        ok_lam = lam_deviation < 0.15

        # (7) 泥面高度
        H_sludge = H_max * X_MLSS * SVI / 1e6

        # (8) 安全距离 1.5~2.0m
        H_safe = H_max - H_decant - H_sludge
        ok_safe = (1.5 <= H_safe) & (H_safe <= 2.0)

        # (9) 总高度
        H_total = H_max + h_super

        # (10) 剩余污泥 (4-76)(4-77)(4-78)
        # ① ΔXv = Y·Qd·(S0-Se)/1000 - Kd(T)·V·X·f/θc
        Px_bio = Y * Q_avg * (S0_kg - Se_kg) - KdT * V_main * X_kg * f / theta_c_design
        # ② ΔXs = Qd·(1-f·f_b)·(C0-Ce)/1000
        f_b = 0.7
        C0 = quality.SS
        Ce = C0 * 0.30  # (1-0.70)
        Px_nbio = Q_avg * (1.0 - f * f_b) * (C0 - Ce) / 1000.0
        # ③ ΔX = ΔXv + ΔXs
        Px_total = Px_bio + Px_nbio

        # (11) 污泥龄校核 (4-79)
        # θc' = V·X·f / ΔXv, 校核: θc_design ≤ θc' ≤ 30
        theta_c_prime = np.where(Px_bio > 0, V_main * X_kg * f / Px_bio, np.inf)
        ok_theta_c = (theta_c_prime >= theta_c_design) & (theta_c_prime <= 30)
        ok_nitrification = (15 <= theta_c_prime) & (theta_c_prime <= 30)

        # (12) 需氧量
        O2_carbon = a_prime * Q_avg * (S0_kg - Se_kg) + b_prime * V_main * X_kg * f
        N_synth = 0.124 * Px_bio
        NH3_load = Q_avg * (quality.NH3N - 5.0) / 1000.0
        O2_nitrification = 4.57 * np.maximum(0.0, NH3_load - N_synth)
        TN_load = Q_avg * (quality.TN - 15.0) / 1000.0
        O2_denitrification = 2.86 * np.maximum(0.0, TN_load - N_synth)
        O2_total = O2_carbon + O2_nitrification - O2_denitrification
        ok_O2 = O2_total > 0

        # 滗水器
        Q_decant = V_eff_actual * lam / t_d

        # 滗水器堰口长度 (4-76)
        q_L = 25.0  # L/(s·m)
        q_L_m3h = q_L * 3.6
        L_w = np.where(q_L_m3h > 0, Q_decant / q_L_m3h, 0.0)
        q_L_actual = np.where(L_w > 0, Q_decant / L_w / 3.6, 0.0)
        ok_weir = (20 <= q_L_actual) & (q_L_actual <= 30)

        # 成本估算
        concrete_m3 = L * B * H_total * n * 0.4

        dtype = np.dtype(
            [
                ("V_main", np.float64),
                ("V_main_single", np.float64),
                ("V_selector", np.float64),
                ("V_eff_actual", np.float64),
                ("L", np.float64),
                ("B", np.float64),
                ("H_max_out", np.float64),
                ("H_total", np.float64),
                ("H_decant", np.float64),
                ("H_sludge", np.float64),
                ("H_safe", np.float64),
                ("lam_out", np.float64),
                ("ratio_LB", np.float64),
                ("ratio_BH", np.float64),
                ("Ns_out", np.float64),
                ("theta_c_actual", np.float64),
                ("Px_bio", np.float64),
                ("Px_nbio", np.float64),
                ("Px_total", np.float64),
                ("O2_carbon", np.float64),
                ("O2_nitrification", np.float64),
                ("O2_denitrification", np.float64),
                ("O2_total", np.float64),
                ("Q_decant", np.float64),
                ("KdT", np.float64),
                ("L_w", np.float64),
                ("q_L_actual", np.float64),
                ("H", np.float64),
                ("concrete_m3", np.float64),
                ("ok_LB", np.bool_),
                ("ok_BH", np.bool_),
                ("ok_lam", np.bool_),
                ("ok_safe", np.bool_),
                ("ok_theta_c", np.bool_),
                ("ok_O2", np.bool_),
                ("ok_weir", np.bool_),
                ("ok_nitrification", np.bool_),
                ("val_LB", np.float64),
                ("val_BH", np.float64),
                ("val_lam", np.float64),
                ("val_safe", np.float64),
                ("val_theta_c", np.float64),
                ("val_O2", np.float64),
                ("val_weir", np.float64),
                ("val_nitrification", np.float64),
            ]
        )
        result = np.empty(N, dtype=dtype)
        result["V_main"] = V_main
        result["V_main_single"] = V_main_single
        result["V_selector"] = V_selector
        result["V_eff_actual"] = V_eff_actual
        result["L"] = L
        result["B"] = B
        result["H_max_out"] = H_max
        result["H_total"] = H_total
        result["H_decant"] = H_decant
        result["H_sludge"] = H_sludge
        result["H_safe"] = H_safe
        result["lam_out"] = lam
        result["ratio_LB"] = ratio_LB
        result["ratio_BH"] = ratio_BH
        result["Ns_out"] = Ns
        result["theta_c_actual"] = theta_c_prime
        result["Px_bio"] = Px_bio
        result["Px_nbio"] = Px_nbio
        result["Px_total"] = Px_total
        result["O2_carbon"] = O2_carbon
        result["O2_nitrification"] = O2_nitrification
        result["O2_denitrification"] = O2_denitrification
        result["O2_total"] = O2_total
        result["Q_decant"] = Q_decant
        result["KdT"] = KdT
        result["L_w"] = L_w
        result["q_L_actual"] = q_L_actual
        result["concrete_m3"] = concrete_m3
        result["L"] = L  # standard field
        result["B"] = B  # standard field
        result["H"] = result["H_total"]  # standard field
        result["ok_LB"] = ok_LB
        result["ok_BH"] = ok_BH
        result["ok_lam"] = ok_lam
        result["ok_safe"] = ok_safe
        result["ok_theta_c"] = ok_theta_c
        result["ok_O2"] = ok_O2
        result["ok_weir"] = ok_weir
        result["ok_nitrification"] = ok_nitrification
        result["val_LB"] = ratio_LB
        result["val_BH"] = ratio_BH
        result["val_lam"] = lam_deviation
        result["val_safe"] = H_safe
        result["val_theta_c"] = theta_c_prime
        result["val_O2"] = O2_total
        result["val_weir"] = q_L_actual
        result["val_nitrification"] = theta_c_prime
        return result
