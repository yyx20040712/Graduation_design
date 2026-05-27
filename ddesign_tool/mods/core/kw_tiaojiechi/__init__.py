"""
kw_tiaojiechi.py — 矿井水调节池计算模块

矿井水调节池(Mine Water Equalization Tank)用于均衡矿井涌水量波动、
初步沉淀煤粉颗粒.与市政调节池的主要区别:
  - HRT ≥ 6h(取 8h,比市政 4-6h 更长)
  - SS 去除率 ~30%(含煤颗粒沉降)
  - 搅拌功率 ≥ 5 W/m³(低于市政 12 W/m³,避免打碎煤颗粒)
  - 池底坡度 ≥ 1%,便于煤泥收集
  - 煤颗粒密度低(1.3~1.5 t/m³),沉降速度慢,需校核积泥坑容积

计算公式来源:dlc.docx §4.2 调节池设计计算
  (4-2):  V = Q_avg · t_HRT · k
  (4-3):  A₁ = V₁ / H
  (4-4):  L = A₁ / B
  (4-5):  H_t = H + h_free + h_pit
  (4-6):  W_d = Q_d · C₀ · η_reg × 10⁻⁶
  (4-7):  V_sludge = W_d / ((1-P_sludge) · ρ_sludge)
  (4-8):  V_pit ≥ V_sludge · T_sludge
  (4-9):  Q_out = Q_avg
  (4-10): D_out = √(4·Q_out/3600 / (π·v_out))
  (4-1):  u_s = g(ρ_s-ρ)d² / (18μ)    (Stokes)
"""

import math
from typing import Dict, List

import numpy as np

from models.base import (
    NodeBase, NodeResult,
    WaterFlow, WaterQuality,
    ParamDef, GRAVITY,
)


# ── 物理常数 ──
MU_WATER = 1.005e-3   # 水的动力粘度 Pa·s (20°C)
RHO_WATER = 1000.0    # 水的密度 kg/m³


class KwTiaojiechiNode(NodeBase):
    """矿井水调节池 — 水量调节 + 煤粉预沉淀"""

    NODE_TYPE = "kw_tiaojiechi"
    NODE_NAME = "矿井水调节池"
    NODE_CATEGORY = "矿井水处理"

    @classmethod
    def _default_params(cls) -> Dict[str, float]:
        return {
            "n": 4,             # 池数(4~8,步长2)
            "HRT": 8,           # 水力停留时间 h(6~12h)
            "k": 1.0,           # 综合变化系数
            "h_eff": 4.0,       # 有效水深 m(3.0~5.0m)
            "h_super": 0.5,     # 超高 m(0.3~0.5m)
            "h_pit": 1.0,       # 积泥坑深度 m(0.5~1.5m)
            "ratio_LB": 2.5,    # 长宽比 L/B(2:1~4:1)
            "P_density": 8,     # 搅拌功率密度 W/m³(5~10)
            "slope": 0.02,      # 池底坡度(≥0.01~0.02)
            "P_sludge": 0.92,   # 沉泥含水率(0.90~0.95)
            "T_sludge": 2,      # 排泥周期 d(1~2d)
            "rho_sludge": 1.1,  # 湿泥密度 t/m³(1.0~1.2)
            "v_out": 1.5,       # 出水管流速 m/s(1.0~2.0)
            "rho_coal": 1400,   # 煤颗粒密度 kg/m³(1300~1500)
            "d_coal": 0.1,      # 煤颗粒粒径 mm(0.01~0.5)
        }

    def _build_param_defs(self) -> List[ParamDef]:
        return [
            ParamDef("池数 n", "n", value=4, default=4,
                     min_val=4, max_val=16, step=2, unit="座",
                     description="调节池格数,≥2 保证检修备用"),
            ParamDef("水力停留时间 HRT", "HRT", value=8, default=8,
                     min_val=6, max_val=12, step=1, unit="h",
                     description="≥6h,涌水量波动大时取高值"),
            ParamDef("综合变化系数 k", "k", value=1.0, default=1.0,
                     min_val=0.8, max_val=1.5, step=0.05, unit="-",
                     description="按日处理能力查表确定"),
            ParamDef("有效水深", "h_eff", value=4.0, default=4.0,
                     min_val=3.0, max_val=5.0, step=0.5, unit="m",
                     description="有效水深 3.0~5.0m"),
            ParamDef("超高", "h_super", value=0.5, default=0.5,
                     min_val=0.3, max_val=0.5, step=0.1, unit="m"),
            ParamDef("积泥坑深度", "h_pit", value=1.0, default=1.0,
                     min_val=0.5, max_val=1.5, step=0.1, unit="m",
                     description="池底集泥区加深,0.5~1.5m"),
            ParamDef("长宽比 L/B", "ratio_LB", value=2.5, default=2.5,
                     min_val=2.0, max_val=4.0, step=0.25, unit="-",
                     description="2:1~4:1,保证推流状态"),
            ParamDef("搅拌功率密度", "P_density", value=8, default=8,
                     min_val=5, max_val=10, step=1, unit="W/m³",
                     description="5~10 W/m³,防煤粉沉积"),
            ParamDef("池底坡度", "slope", value=0.02, default=0.02,
                     min_val=0.01, max_val=0.03, step=0.005, unit="-",
                     description="≥1%,向积泥坑倾斜,取0.02"),
            ParamDef("沉泥含水率", "P_sludge", value=0.92, default=0.92,
                     min_val=0.90, max_val=0.95, step=0.01, unit="-",
                     description="煤泥含水率 90%~95%"),
            ParamDef("排泥周期", "T_sludge", value=2, default=2,
                     min_val=1, max_val=2, step=1, unit="d",
                     description="一般 1~2d 排泥一次"),
            ParamDef("湿泥密度", "rho_sludge", value=1.1, default=1.1,
                     min_val=1.0, max_val=1.2, step=0.05, unit="t/m³"),
            ParamDef("出水管流速", "v_out", value=1.5, default=1.5,
                     min_val=1.0, max_val=2.0, step=0.1, unit="m/s",
                     description="满管流设计流速"),
            ParamDef("煤颗粒密度", "rho_coal", value=1400, default=1400,
                     min_val=1300, max_val=1500, step=50, unit="kg/m³",
                     description="1.3~1.5 t/m³,低于砂粒"),
            ParamDef("煤颗粒粒径", "d_coal", value=0.1, default=0.1,
                     min_val=0.01, max_val=0.5, step=0.01, unit="mm",
                     description="以细粉为主 0.01~0.5mm"),
        ]

    @classmethod
    def _default_removal_rates(cls) -> Dict[str, float]:
        # 矿井水调节池可去除部分悬浮煤粉
        return {
            "BOD5": 0.05, "COD": 0.10, "SS": 0.30,
            "NH3N": 0.0, "TN": 0.0, "TP": 0.05,
        }

    def calculate(self, flow: WaterFlow,
                  quality: WaterQuality) -> NodeResult:
        # ── 读取参数 ──
        n = int(self.get_param("n"))
        HRT = self.get_param("HRT")
        k = self.get_param("k")
        h_eff = self.get_param("h_eff")
        h_super = self.get_param("h_super")
        h_pit = self.get_param("h_pit")
        ratio_LB = self.get_param("ratio_LB")
        P_density = self.get_param("P_density")
        slope = self.get_param("slope")
        P_sludge = self.get_param("P_sludge")
        T_sludge = self.get_param("T_sludge")
        rho_sludge = self.get_param("rho_sludge")
        v_out = self.get_param("v_out")
        rho_coal = self.get_param("rho_coal")
        d_coal = self.get_param("d_coal")

        result = NodeResult(success=True)
        result.params = {
            "n": n, "HRT": HRT, "k": k, "h_eff": h_eff,
            "h_super": h_super, "h_pit": h_pit, "ratio_LB": ratio_LB,
            "P_density": P_density, "slope": slope,
            "P_sludge": P_sludge, "T_sludge": T_sludge,
            "rho_sludge": rho_sludge, "v_out": v_out,
            "rho_coal": rho_coal, "d_coal": d_coal,
        }

        # ── (4-2) 单池设计流量与有效容积 ──
        Q_avg_h = flow.Q_avg_hourly       # m³/h
        Q_per_pool = Q_avg_h / n           # m³/h (单池)
        V_eff = Q_per_pool * HRT * k       # m³ (单池有效容积)

        # ── (4-3) 有效面积 ──
        A_eff = V_eff / h_eff if h_eff > 0 else 0  # m²

        # ── (4-4) 平面尺寸 ──
        B_theory = math.sqrt(A_eff / ratio_LB)
        L_theory = ratio_LB * B_theory
        B = math.ceil(max(B_theory, 1.0) / 0.5) * 0.5
        L = math.ceil(max(L_theory, B) / 0.5) * 0.5

        # ── 取整后校核 ──
        V_actual = L * B * h_eff           # m³ (单池实际)
        HRT_actual = V_actual / (Q_per_pool * k) if Q_per_pool > 0 else 0  # h
        ratio_actual = L / B

        result.add_check("长宽比 L/B",
                         2.0 <= ratio_actual <= 4.0,
                         round(ratio_actual, 2), "2~4", "")
        result.add_check("实际 HRT",
                         6.0 <= HRT_actual <= 12.0,
                         round(HRT_actual, 2), "6~12", "h")
        if not (6.0 <= HRT_actual <= 12.0):
            result.add_warning(
                f"实际 HRT={HRT_actual:.1f}h 超出 6~12h 范围,建议调整池体尺寸")

        # ── (4-5) 总高度 ──
        H_total = h_eff + h_super + h_pit
        H_rounded = math.ceil(H_total / 0.1) * 0.1

        # ── (4-6) 煤泥产量 ──
        SS_in = quality.SS                          # mg/L
        eta_SS = self._removal_rates.get("SS", 0.30)
        dry_sludge_t_d = flow.Q_avg_daily * SS_in * eta_SS / 1e6  # t/d (4-6)
        # ── (4-7) 湿泥体积 ──
        wet_sludge_m3_d = dry_sludge_t_d / ((1 - P_sludge) * rho_sludge) if P_sludge < 1 else 0
        # ── (4-8) 贮泥容积需求 ──
        V_sludge_needed = wet_sludge_m3_d * T_sludge  # m³

        # ── 积泥坑容积估算 (三角形断面近似) ──
        # 积泥坑位于池底深端,由池底坡度形成
        # V_pit ≈ B × h_pit² / (2 × slope)
        V_pit_available = B * h_pit ** 2 / (2 * slope) if slope > 0 else 0
        pit_ok = V_pit_available >= V_sludge_needed
        result.add_check("积泥坑容积足够",
                         pit_ok,
                         round(V_pit_available, 2),
                         f">= {round(V_sludge_needed, 2)}", "m³")
        if not pit_ok:
            result.add_warning(
                f"积泥坑容积不足: {V_pit_available:.1f}m³ < {V_sludge_needed:.1f}m³,"
                f"建议增大 h_pit 或缩短排泥周期")

        # ── 搅拌总功率 ──
        V_total = V_actual * n
        P_total = P_density * V_total  # W
        P_total_kW = math.ceil(P_total / 100) / 10  # 向上取整 0.1kW

        # ── (4-1) Stokes 沉降速度 ──
        d_m = d_coal / 1000.0  # mm → m
        u_s = GRAVITY * (rho_coal - RHO_WATER) * d_m ** 2 / (18 * MU_WATER)  # m/s
        u_s_mm_s = u_s * 1000  # mm/s

        # ── (4-9)(4-10) 出水系统 ──
        Q_out_m3s = Q_avg_h / 3600.0
        if v_out > 0:
            D_out_theory = math.sqrt(4 * Q_out_m3s / (math.pi * v_out))
        else:
            D_out_theory = 0
        D_out_mm = round(math.ceil(max(D_out_theory, 0.1) / 0.05) * 0.05 * 1000)  # m → mm
        D_out_m = D_out_mm / 1000.0
        v_out_actual = Q_out_m3s / (math.pi * D_out_m ** 2 / 4) if D_out_m > 0 else 0

        # ── 堰口负荷校核 ──
        # 双侧出水堰: 堰长 = 2 × B (两端出水)
        Q_per_pool_Ls = Q_per_pool * 1000 / 3600  # L/s
        q_weir = Q_per_pool_Ls / (2 * B) if B > 0 else 0
        weir_ok = q_weir <= 2.9
        result.add_check("堰口负荷 ≤ 2.9 L/(s·m)",
                         weir_ok,
                         round(q_weir, 2), "≤ 2.9", "L/(s·m)")
        if not weir_ok:
            result.add_warning(
                f"堰口负荷 {q_weir:.1f} L/(s·m) > 2.9,建议增加池数或增设出水堰")

        # ── 组装结果 ──
        result.add_dimension("池数", n, "座",
                             formula="n = 4~8 (步长2)",
                             category="physical")
        result.add_dimension("单池长度 L", L, "m",
                             formula="L = ceil(A₁/B, 0.5m)",
                             category="physical")
        result.add_dimension("单池宽度 B", B, "m",
                             formula="B = ceil(√(A₁/ratio_LB), 0.5m)",
                             category="physical")
        result.add_dimension("有效水深 h_eff", h_eff, "m",
                             formula="h_eff = 设计取值 (3.0~5.0m)",
                             category="physical")
        result.add_dimension("积泥坑深度 h_pit", h_pit, "m",
                             formula="h_pit = 设计取值 (0.5~1.5m)",
                             category="physical")
        result.add_dimension("总高度 H_t", H_rounded, "m",
                             formula="H_t = h_eff + h_super + h_pit",
                             category="physical")
        result.add_dimension("池底坡度 i", slope, "",
                             formula="i = 设计取值 (≥0.01)",
                             category="physical")
        result.add_dimension("单池有效容积", round(V_actual, 1), "m³",
                             formula="V = L × B × h_eff",
                             category="physical")
        result.add_dimension("总有效容积", round(V_total, 1), "m³",
                             formula="V_total = V × n",
                             category="physical")
        result.add_dimension("实际 HRT", round(HRT_actual, 2), "h",
                             formula="HRT_actual = V / (Q_single × k)",
                             category="computed")
        result.add_dimension("长宽比 L/B", round(ratio_actual, 2), "",
                             formula="L/B = 取整后校核",
                             category="computed")
        result.add_dimension("搅拌总功率", P_total_kW, "kW",
                             formula="P = P_density × V_total / 1000",
                             category="computed")
        result.add_dimension("单池设计流量", round(Q_per_pool, 2), "m³/h",
                             formula="Q_single = Q_avg_h / n",
                             category="computed")
        result.add_dimension("日产干泥量", round(dry_sludge_t_d, 2), "t/d",
                             formula="W_d = Q_d × C₀ × η_SS × 10⁻⁶",
                             category="computed")
        result.add_dimension("日产湿泥体积", round(wet_sludge_m3_d, 1), "m³/d",
                             formula="V_sludge = W_d / ((1-P) × ρ)",
                             category="computed")
        result.add_dimension("贮泥容积需求", round(V_sludge_needed, 1), "m³",
                             formula="V_needed = V_sludge × T_sludge",
                             category="computed")
        result.add_dimension("积泥坑有效容积", round(V_pit_available, 1), "m³",
                             formula="V_pit ≈ B × h_pit² / (2 × i)",
                             category="physical")
        result.add_dimension("Stokes沉降速度 u_s", round(u_s_mm_s, 3), "mm/s",
                             formula="u_s = g(ρ_s-ρ)d² / (18μ)",
                             category="computed")
        result.add_dimension("出水管径 D_out", D_out_mm, "mm",
                             formula="D_out = √(4Q/(π·v_out))",
                             category="physical")
        result.add_dimension("实际出水流速", round(v_out_actual, 2), "m/s",
                             formula="v_actual = Q / A_out",
                             category="computed")
        result.add_dimension("堰口负荷", round(q_weir, 2), "L/(s·m)",
                             formula="q_weir = Q_single(L/s) / B(m)",
                             category="computed")

        # 概算用
        result.add_dimension("调节池总面积", round(L * B * n, 1), "m²",
                             category="physical")
        result.add_dimension("混凝土量估算", round(V_total * 1.2, 1), "m³",
                             category="physical")

        return result

    @classmethod
    def _vectorized_compute(cls, grid: dict, flow: "WaterFlow",
                            quality: "WaterQuality", fixed: dict) -> "np.ndarray":
        """向量化批量计算矿井水调节池"""
        n = grid["n"].astype(np.int32)
        HRT = grid["HRT"]
        h_eff = grid["h_eff"]
        ratio_LB = grid["ratio_LB"]
        k = fixed.get("k", 1.0)
        h_super = fixed["h_super"]
        h_pit = fixed["h_pit"]
        P_density = fixed["P_density"]
        slope = fixed["slope"]
        P_sludge = fixed["P_sludge"]
        T_sludge = fixed["T_sludge"]
        rho_sludge = fixed["rho_sludge"]
        v_out = fixed["v_out"]
        rho_coal = fixed.get("rho_coal", 1400.0)
        d_coal = fixed.get("d_coal", 0.1)
        N = len(n)

        # 零流量守卫
        if flow.Q_design <= 0:
            dtype = np.dtype([
                ("L", np.float64), ("B", np.float64), ("h_eff_out", np.float64),
                ("V_actual", np.float64), ("V_total", np.float64),
                ("H_total", np.float64), ("HRT_actual", np.float64),
                ("ratio_actual", np.float64), ("P_kW", np.float64),
                ("Q_per_pool", np.float64), ("dry_sludge", np.float64),
                ("wet_sludge", np.float64), ("V_sludge_needed", np.float64),
                ("V_pit_available", np.float64), ("u_s_mm_s", np.float64),
                ("D_out_mm", np.float64), ("q_weir", np.float64),
                ("H", np.float64), ("area_total", np.float64), ("concrete_m3", np.float64),
                ("ok_LB_ratio", np.bool_), ("ok_HRT_actual", np.bool_),
                ("ok_pit_vol", np.bool_), ("ok_weir_load", np.bool_),
                ("val_LB_ratio", np.float64), ("val_HRT_actual", np.float64),
                ("val_pit_vol", np.float64), ("val_weir_load", np.float64),
            ])
            return np.zeros(N, dtype=dtype)

        Q_avg_h = flow.Q_avg_hourly
        Q_per_pool = Q_avg_h / n
        V_eff = Q_per_pool * HRT * k
        A_eff = np.where(h_eff > 0, V_eff / h_eff, 0.0)

        B_theory = np.sqrt(A_eff / ratio_LB)
        L_theory = ratio_LB * B_theory
        B = np.ceil(np.maximum(B_theory, 1.0) / 0.5) * 0.5
        L = np.ceil(np.maximum(L_theory, B) / 0.5) * 0.5

        V_actual = L * B * h_eff
        HRT_actual = np.where(Q_per_pool > 0, V_actual / (Q_per_pool * k), 0.0)
        ratio_actual = L / B

        ok_LB = (2.0 <= ratio_actual) & (ratio_actual <= 4.0)
        ok_HRT = (6.0 <= HRT_actual) & (HRT_actual <= 12.0)

        H_total = h_eff + h_super + h_pit
        V_total = V_actual * n
        P_total = P_density * V_total
        P_kW = np.ceil(P_total / 100) * 0.1

        # 煤泥产量 (4-6)(4-7)
        SS_in = quality.SS
        eta_SS = 0.30
        dry_sludge = flow.Q_avg_daily * SS_in * eta_SS / 1e6
        wet_sludge = np.where(P_sludge < 1, dry_sludge / ((1 - P_sludge) * rho_sludge), 0.0)
        V_sludge_needed = wet_sludge * T_sludge

        # 积泥坑容积 (4-8)
        V_pit_available = np.where(slope > 0, B * h_pit ** 2 / (2 * slope), 0.0)
        ok_pit = V_pit_available >= V_sludge_needed

        # Stokes 沉降速度 (4-1)
        d_m = d_coal / 1000.0
        u_s = GRAVITY * (rho_coal - RHO_WATER) * d_m ** 2 / (18 * MU_WATER)
        u_s_mm_s = u_s * 1000

        # 出水系统 (4-9)(4-10)
        Q_out_m3s = Q_avg_h / 3600.0
        D_out_theory = np.where(v_out > 0, np.sqrt(4 * Q_out_m3s / (np.pi * v_out)), 0.0)
        D_out_m = np.ceil(np.maximum(D_out_theory, 0.1) / 0.05) * 0.05
        D_out_mm = np.round(D_out_m * 1000)

        # 堰口负荷
        Q_per_pool_Ls = Q_per_pool * 1000 / 3600
        q_weir = np.where(B > 0, Q_per_pool_Ls / (2 * B), 0.0)
        ok_weir = q_weir <= 2.9

        area_total = L * B * n
        concrete_m3 = V_total * 1.2

        dtype = np.dtype([
            ("L", np.float64), ("B", np.float64), ("h_eff_out", np.float64),
            ("V_actual", np.float64), ("V_total", np.float64),
            ("H_total", np.float64), ("HRT_actual", np.float64),
            ("ratio_actual", np.float64), ("P_kW", np.float64),
            ("Q_per_pool", np.float64), ("dry_sludge", np.float64),
            ("wet_sludge", np.float64), ("V_sludge_needed", np.float64),
            ("V_pit_available", np.float64), ("u_s_mm_s", np.float64),
            ("D_out_mm", np.float64), ("q_weir", np.float64),
            ("H", np.float64), ("area_total", np.float64), ("concrete_m3", np.float64),
            ("ok_LB_ratio", np.bool_), ("ok_HRT_actual", np.bool_),
            ("ok_pit_vol", np.bool_), ("ok_weir_load", np.bool_),
            ("val_LB_ratio", np.float64), ("val_HRT_actual", np.float64),
            ("val_pit_vol", np.float64), ("val_weir_load", np.float64),
        ])
        result = np.empty(N, dtype=dtype)
        result["L"] = L; result["B"] = B; result["h_eff_out"] = h_eff
        result["V_actual"] = V_actual; result["V_total"] = V_total
        result["H_total"] = H_total; result["HRT_actual"] = HRT_actual
        result["ratio_actual"] = ratio_actual; result["P_kW"] = P_kW
        result["Q_per_pool"] = Q_per_pool
        result["dry_sludge"] = dry_sludge; result["wet_sludge"] = wet_sludge
        result["V_sludge_needed"] = V_sludge_needed; result["V_pit_available"] = V_pit_available
        result["u_s_mm_s"] = u_s_mm_s; result["D_out_mm"] = D_out_mm
        result["q_weir"] = q_weir
        result["H"] = result["H_total"]  # standard field
        result["area_total"] = area_total; result["concrete_m3"] = concrete_m3
        result["ok_LB_ratio"] = ok_LB; result["ok_HRT_actual"] = ok_HRT
        result["ok_pit_vol"] = ok_pit; result["ok_weir_load"] = ok_weir
        result["val_LB_ratio"] = ratio_actual; result["val_HRT_actual"] = HRT_actual
        result["val_pit_vol"] = V_pit_available; result["val_weir_load"] = q_weir
        return result
