"""
kw_cifenli.py — 磁盘分离机计算模块

磁盘分离机(Magnetic Disk Separator)利用稀土永磁磁盘组的高梯度磁场
捕获经磁种混凝后的磁性絮团,实现快速泥水分离.

核心设计参数:
  - 磁盘直径 D: 0.6~1.5m(典型1.0m)
  - 磁盘间距 δ: 20~30mm
  - 磁盘数量 n_disks: 9~48 盘(随流量增加)
  - 浸没率 η_immerse: 0.35~0.45
  - 转速 ω: 1~5 r/min(通常2~3)
  - 表面负荷 q: 20~40 m³/(m²·h)
  - 流道流速 v_disk ≤ 0.1 m/s
  - 流道停留时间 t_disk: 30~60s

计算公式来源: dlc.docx §4.5 磁分离磁盘设计计算
  (4-44): Q₁ = Q_max / N
  (4-45): A_total = 2 × n_disks × πD²/4 × η_immerse
  (4-46)(4-47): A_channel = (n_disks-1) × πDδ
  (4-48): L_channel = η_immerse × πD
  (4-49): t_disk = A_channel × L_channel / (Q₁/3600)
  (4-50): v_disk = Q₁/3600 / A_channel
  (4-51): q = Q₁ / A_total
  (4-52): v_line = πD × ω / 60
  (4-53): W_SS = Q_total × C₀ × η_SS × 10⁻⁶
  (4-54): V_sludge = W_SS / ((1-P_sludge) × ρ_sludge)
  (4-55)~(4-58): 设备外形尺寸
  (4-59): 装机功率
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

PI = math.pi


class KwCifenliNode(NodeBase):
    """磁盘分离机 — 高梯度磁分离"""

    NODE_TYPE = "kw_cifenli"
    NODE_NAME = "磁分离"
    NODE_CATEGORY = "矿井水处理"

    @classmethod
    def _default_params(cls) -> Dict[str, float]:
        return {
            "N_units": 2,  # 设备台数
            "D_disk": 1.0,  # 磁盘直径 m (0.6~1.5)
            "delta": 0.025,  # 磁盘间距 m (0.02~0.03)
            "eta_immerse": 0.40,  # 浸没率 (0.35~0.45)
            "omega": 3,  # 转速 r/min (1~5)
            "B0": 0.6,  # 磁场强度 T (0.5~0.7)
            "q_design": 30,  # 设计表面负荷 m³/(m²·h) (20~40)
            "eta_SS": 0.95,  # SS去除率 (≥0.90)
            "P_sludge": 0.92,  # 污泥含水率 (0.90~0.93)
            "rho_sludge": 1.1,  # 湿污泥密度 t/m³ (1.0~1.2)
            # 设备外形间隙
            "delta_end": 0.6,  # 轴向端部尺寸 m
            "delta_side": 0.3,  # 侧面间隙 m
            "delta_bottom": 0.4,  # 底部间隙 m
            "delta_top": 0.6,  # 顶部(刮渣机构) m
        }

    def _build_param_defs(self) -> List[ParamDef]:
        return [
            ParamDef(
                "设备台数 N",
                "N_units",
                value=2,
                default=2,
                min_val=1,
                max_val=6,
                step=1,
                unit="台",
                description="单台 50~700 m³/h",
            ),
            ParamDef(
                "磁盘直径 D",
                "D_disk",
                value=1.0,
                default=1.0,
                min_val=0.6,
                max_val=1.5,
                step=0.1,
                unit="m",
                description="0.6~1.5m,典型1.0m",
            ),
            ParamDef(
                "磁盘间距 δ",
                "delta",
                value=0.025,
                default=0.025,
                min_val=0.020,
                max_val=0.030,
                step=0.005,
                unit="m",
                description="20~30mm",
            ),
            ParamDef(
                "浸没率 η",
                "eta_immerse",
                value=0.40,
                default=0.40,
                min_val=0.35,
                max_val=0.45,
                step=0.05,
                unit="",
                description="0.35~0.45",
            ),
            ParamDef(
                "转速 ω",
                "omega",
                value=3,
                default=3,
                min_val=1,
                max_val=5,
                step=1,
                unit="r/min",
                description="通常2~3 r/min",
            ),
            ParamDef(
                "设计表面负荷",
                "q_design",
                value=30,
                default=30,
                min_val=20,
                max_val=40,
                step=5,
                unit="m³/(m²·h)",
                description="20~40 m³/(m²·h)",
            ),
            ParamDef(
                "SS去除率 η_SS",
                "eta_SS",
                value=0.95,
                default=0.95,
                min_val=0.90,
                max_val=0.98,
                step=0.01,
                unit="",
                description="≥90%,实际可达95~97.5%",
            ),
        ]

    @classmethod
    def _default_removal_rates(cls) -> Dict[str, float]:
        return {
            "BOD5": 0.10,
            "COD": 0.20,
            "SS": 0.85,
            "NH3N": 0.05,
            "TN": 0.05,
            "TP": 0.70,
        }

    def calculate(self, flow: WaterFlow, quality: WaterQuality) -> NodeResult:
        # ── 读取参数 ──
        N_units = int(self.get_param("N_units"))
        D_disk = self.get_param("D_disk")
        delta = self.get_param("delta")
        eta_immerse = self.get_param("eta_immerse")
        omega = self.get_param("omega")
        B0 = self.get_param("B0")
        q_design = self.get_param("q_design")
        eta_SS_user = self.get_param("eta_SS")
        P_sludge = self.get_param("P_sludge")
        rho_sludge = self.get_param("rho_sludge")
        delta_end = self.get_param("delta_end")
        delta_side = self.get_param("delta_side")
        delta_bottom = self.get_param("delta_bottom")
        delta_top = self.get_param("delta_top")

        result = NodeResult(success=True)
        result.params = {
            "N_units": N_units,
            "D_disk": D_disk,
            "delta": delta,
            "eta_immerse": eta_immerse,
            "omega": omega,
            "B0": B0,
            "q_design": q_design,
            "eta_SS": eta_SS_user,
            "P_sludge": P_sludge,
            "rho_sludge": rho_sludge,
            "delta_end": delta_end,
            "delta_side": delta_side,
            "delta_bottom": delta_bottom,
            "delta_top": delta_top,
        }

        # ── (4-44) 单台设计流量 ──
        Q_total_m3h = flow.Q_design * 3600  # m³/h (总)
        Q_1_m3h = Q_total_m3h / N_units  # m³/h (单台)
        Q_1_m3s = Q_1_m3h / 3600  # m³/s (单台)

        # ── (4-45) 所需总吸附面积 → 反推盘数 ──
        # q_design = Q₁ / A_total → A_total = Q₁ / q_design
        A_total_needed = Q_1_m3h / q_design if q_design > 0 else 0  # m²
        # 单片有效面积: A_per_disk = 2 × πD²/4 × η_immerse (双面)
        A_per_disk = 2 * PI * D_disk**2 / 4 * eta_immerse
        n_disks_calc = A_total_needed / A_per_disk if A_per_disk > 0 else 0
        # 按停留时间 30s 所需最小盘数: t_disk = (n-1)×π²D²δη / Q₁ ≥ 30
        n_disks_stay = (
            30 * Q_1_m3s / (PI**2 * D_disk**2 * delta * eta_immerse) + 1
            if (D_disk > 0 and delta > 0 and eta_immerse > 0)
            else 0
        )
        n_disks = max(
            9, math.ceil(n_disks_calc), math.ceil(n_disks_stay)
        )  # 同时满足表面负荷和停留时间

        A_total = n_disks * A_per_disk  # 实际总吸附面积

        # ── (4-46)(4-47) 流道过流断面面积 ──
        # A_channel_single ≈ π × D × δ (单片流道)
        A_channel = (n_disks - 1) * PI * D_disk * delta  # m²

        # ── (4-48) 流道有效长度 ──
        L_channel = eta_immerse * PI * D_disk  # m (浸没弧长)

        # ── (4-49) 流道停留时间 ──
        t_disk = A_channel * L_channel / Q_1_m3s if Q_1_m3s > 0 else 0  # s
        result.add_check(
            "流道停留时间 30~60s", 30 <= t_disk <= 60, round(t_disk, 1), "30~60", "s"
        )
        if t_disk < 30:
            result.add_warning(f"停留时间 {t_disk:.0f}s < 30s,建议增加盘数或减小间隙")
        elif t_disk > 60:
            result.add_warning(f"停留时间 {t_disk:.0f}s > 60s,设备利用率偏低")

        # ── (4-50) 流道流速校核 ──
        v_disk = Q_1_m3s / A_channel if A_channel > 0 else 0  # m/s
        result.add_check(
            "流道流速 ≤ 0.10 m/s", v_disk <= 0.10, round(v_disk, 3), "≤ 0.10", "m/s"
        )
        if v_disk > 0.10:
            result.add_warning(f"流道流速 {v_disk:.3f}m/s > 0.10,建议增加盘数")

        # ── (4-51) 表面水力负荷校核 ──
        q_actual = Q_1_m3h / A_total if A_total > 0 else 0
        result.add_check(
            "表面负荷 20~40 m³/(m²·h)",
            20 <= q_actual <= 40,
            round(q_actual, 1),
            "20~40",
            "m³/(m²·h)",
        )
        if q_actual > 40:
            result.add_warning(f"表面负荷 {q_actual:.0f} > 40,建议增加盘数或盘径")

        # ── (4-52) 磁盘外缘线速度 ──
        v_line = PI * D_disk * omega / 60  # m/s
        result.add_check(
            "外缘线速度 ≤ 0.30 m/s", v_line <= 0.30, round(v_line, 3), "≤ 0.30", "m/s"
        )

        # ── (4-53) 干固体去除量 ──
        C0 = quality.SS  # mg/L (进水SS)
        W_SS = flow.Q_avg_daily * C0 * eta_SS_user / 1e6  # t/d

        # ── (4-54) 湿污泥体积 ──
        V_sludge = W_SS / ((1 - P_sludge) * rho_sludge) if P_sludge < 1 else 0  # m³/d

        # ── (4-55)~(4-58) 设备外形尺寸 ──
        L_machine = n_disks * delta + 2 * delta_end  # m (轴向)
        B_machine = D_disk + 2 * delta_side  # m (宽度)
        H_machine = D_disk + delta_bottom + delta_top  # m (高度)
        S_machine = L_machine * B_machine  # m² (占地面积)

        # ── (4-59) 装机功率估算 ──
        # 主传动: 流体阻力+轴承摩擦+盘面夹带提升
        P_main = 0.5 + 0.02 * n_disks  # kW (经验估算)
        P_scraper = 0.9  # kW (刮渣机构)
        P_total = P_main + P_scraper

        # ── 组装结果 ──
        result.add_dimension(
            "设备台数", N_units, "台", formula="N = 根据总流量确定", category="physical"
        )
        result.add_dimension(
            "单台流量 Q₁",
            round(Q_1_m3h, 1),
            "m³/h",
            formula="Q₁ = Q_max / N",
            category="computed",
        )
        result.add_dimension("磁盘直径 D", D_disk, "m", category="physical")
        result.add_dimension("磁盘间距 δ", delta * 1000, "mm", category="physical")
        result.add_dimension(
            "磁盘数量 n_disks",
            n_disks,
            "盘",
            formula="n = A_total / A_per_disk, ≥9",
            category="physical",
        )
        result.add_dimension(
            "总吸附面积 A_total",
            round(A_total, 1),
            "m²",
            formula="A = 2×n×πD²/4×η",
            category="physical",
        )
        result.add_dimension(
            "流道断面面积 A_ch",
            round(A_channel, 3),
            "m²",
            formula="A_ch = (n-1)×πDδ",
            category="physical",
        )
        result.add_dimension(
            "流道有效长度 L_ch",
            round(L_channel, 2),
            "m",
            formula="L_ch = η×πD",
            category="physical",
        )
        result.add_dimension(
            "流道停留时间 t_disk",
            round(t_disk, 1),
            "s",
            formula="t = A_ch×L_ch/Q₁",
            category="computed",
        )
        result.add_dimension(
            "流道流速 v_disk",
            round(v_disk, 3),
            "m/s",
            formula="v = Q₁/A_ch",
            category="computed",
        )
        result.add_dimension(
            "实际表面负荷 q",
            round(q_actual, 1),
            "m³/(m²·h)",
            formula="q = Q₁/A_total",
            category="computed",
        )
        result.add_dimension(
            "外缘线速度 v_line",
            round(v_line, 3),
            "m/s",
            formula="v_line = πD×ω/60",
            category="computed",
        )
        result.add_dimension("磁场强度 B₀", B0, "T", category="physical")
        result.add_dimension(
            "SS去除率",
            eta_SS_user * 100,
            "%",
            formula="η_SS ≥ 90%",
            category="computed",
        )
        result.add_dimension(
            "日去除干固体 W_SS",
            round(W_SS, 2),
            "t/d",
            formula="W_SS = Q_total×C₀×η_SS×10⁻⁶",
            category="computed",
        )
        result.add_dimension(
            "日湿污泥量 V_sludge",
            round(V_sludge, 1),
            "m³/d",
            formula="V = W_SS/((1-P)×ρ)",
            category="computed",
        )
        result.add_dimension(
            "设备长度 L_machine",
            round(L_machine, 1),
            "m",
            formula="L = n×δ + 2Δ_end",
            category="physical",
        )
        result.add_dimension(
            "设备宽度 B_machine",
            round(B_machine, 1),
            "m",
            formula="B = D + 2Δ_side",
            category="physical",
        )
        result.add_dimension(
            "设备高度 H_machine",
            round(H_machine, 1),
            "m",
            formula="H = D + Δ_bottom + Δ_top",
            category="physical",
        )
        result.add_dimension(
            "单台占地面积",
            round(S_machine, 1),
            "m²",
            formula="S = L × B",
            category="physical",
        )
        result.add_dimension(
            "总装机功率",
            round(P_total, 1),
            "kW",
            formula="P = P_main + P_scraper",
            category="computed",
        )

        # 概算用 (设备为主,土建少量)
        result.add_dimension(
            "总占地面积", round(S_machine * N_units, 1), "m²", category="physical"
        )
        result.add_dimension(
            "混凝土量估算",
            round(S_machine * 0.5 * N_units, 1),
            "m³",
            category="physical",
        )

        return result

    @classmethod
    def _vectorized_compute(
        cls, grid: dict, flow: "WaterFlow", quality: "WaterQuality", fixed: dict
    ) -> "np.ndarray":
        N_units = grid["N_units"].astype(np.int32)
        D_disk = grid["D_disk"]
        delta = grid["delta"]
        eta_immerse = grid["eta_immerse"]
        omega = fixed.get("omega", 3.0)
        q_design = grid["q_design"]
        eta_SS_user = fixed.get("eta_SS", 0.95)
        P_sludge = fixed.get("P_sludge", 0.92)
        rho_sludge = fixed.get("rho_sludge", 1.1)
        delta_end = fixed.get("delta_end", 0.6)
        delta_side = fixed.get("delta_side", 0.3)
        delta_bottom = fixed.get("delta_bottom", 0.4)
        delta_top = fixed.get("delta_top", 0.6)
        N = len(N_units)

        if flow.Q_design <= 0:
            dtype = np.dtype(
                [
                    ("n_disks", np.int32),
                    ("A_total", np.float64),
                    ("A_channel", np.float64),
                    ("L_channel", np.float64),
                    ("t_disk", np.float64),
                    ("v_disk", np.float64),
                    ("q_actual", np.float64),
                    ("v_line", np.float64),
                    ("L_machine", np.float64),
                    ("B_machine", np.float64),
                    ("H_machine", np.float64),
                    ("S_machine", np.float64),
                    ("P_total", np.float64),
                    ("W_SS", np.float64),
                    ("V_sludge", np.float64),
                    ("H", np.float64),
                    ("area_total", np.float64),
                    ("concrete_m3", np.float64),
                    ("ok_tdisk", np.bool_),
                    ("ok_vdisk", np.bool_),
                    ("ok_q", np.bool_),
                    ("ok_vline", np.bool_),
                    ("val_tdisk", np.float64),
                    ("val_vdisk", np.float64),
                    ("val_q", np.float64),
                    ("val_vline", np.float64),
                ]
            )
            return np.zeros(N, dtype=dtype)

        Q_total_m3h = flow.Q_design * 3600
        Q_1_m3h = Q_total_m3h / N_units
        Q_1_m3s = Q_1_m3h / 3600

        A_per_disk = 2 * PI * D_disk**2 / 4 * eta_immerse
        A_total_needed = np.where(q_design > 0, Q_1_m3h / q_design, 0.0)
        n_disks_calc = np.where(A_per_disk > 0, A_total_needed / A_per_disk, 0.0)
        # 按停留时间 30s 所需最小盘数
        denom = PI**2 * D_disk**2 * delta * eta_immerse
        n_disks_stay = np.where(denom > 0, 30 * Q_1_m3s / denom + 1, 0.0)
        n_disks = np.maximum(
            9, np.maximum(np.ceil(n_disks_calc), np.ceil(n_disks_stay))
        ).astype(np.int32)
        A_total = n_disks * A_per_disk

        A_channel = (n_disks - 1) * PI * D_disk * delta
        L_channel = eta_immerse * PI * D_disk

        t_disk = np.where(Q_1_m3s > 0, A_channel * L_channel / Q_1_m3s, 0.0)
        ok_tdisk = (30 <= t_disk) & (t_disk <= 60)

        v_disk = np.where(A_channel > 0, Q_1_m3s / A_channel, 0.0)
        ok_vdisk = v_disk <= 0.10

        q_actual = np.where(A_total > 0, Q_1_m3h / A_total, 0.0)
        ok_q = (20 <= q_actual) & (q_actual <= 40)

        v_line = PI * D_disk * omega / 60
        ok_vline = v_line <= 0.30

        L_machine = n_disks * delta + 2 * delta_end
        B_machine = D_disk + 2 * delta_side
        S_machine = L_machine * B_machine
        P_total = 0.5 + 0.02 * n_disks + 0.9

        area_total = S_machine * N_units
        concrete_m3 = S_machine * 0.5 * N_units
        H_machine = D_disk + delta_bottom + delta_top
        C0 = quality.SS
        W_SS = flow.Q_avg_daily * C0 * eta_SS_user / 1e6
        V_sludge = np.where(P_sludge < 1, W_SS / ((1 - P_sludge) * rho_sludge), 0.0)

        dtype = np.dtype(
            [
                ("n_disks", np.int32),
                ("A_total", np.float64),
                ("A_channel", np.float64),
                ("L_channel", np.float64),
                ("t_disk", np.float64),
                ("v_disk", np.float64),
                ("q_actual", np.float64),
                ("v_line", np.float64),
                ("L_machine", np.float64),
                ("B_machine", np.float64),
                ("H_machine", np.float64),
                ("S_machine", np.float64),
                ("P_total", np.float64),
                ("W_SS", np.float64),
                ("V_sludge", np.float64),
                ("H", np.float64),
                ("area_total", np.float64),
                ("concrete_m3", np.float64),
                ("ok_tdisk", np.bool_),
                ("ok_vdisk", np.bool_),
                ("ok_q", np.bool_),
                ("ok_vline", np.bool_),
                ("val_tdisk", np.float64),
                ("val_vdisk", np.float64),
                ("val_q", np.float64),
                ("val_vline", np.float64),
            ]
        )
        result = np.empty(N, dtype=dtype)
        result["n_disks"] = n_disks
        result["A_total"] = A_total
        result["A_channel"] = A_channel
        result["L_channel"] = L_channel
        result["t_disk"] = t_disk
        result["v_disk"] = v_disk
        result["q_actual"] = q_actual
        result["v_line"] = v_line
        result["L_machine"] = L_machine
        result["B_machine"] = B_machine
        result["H_machine"] = H_machine
        result["S_machine"] = S_machine
        result["P_total"] = P_total
        result["W_SS"] = W_SS
        result["V_sludge"] = V_sludge
        result["H"] = H_machine
        result["area_total"] = area_total
        result["concrete_m3"] = concrete_m3
        result["ok_tdisk"] = ok_tdisk
        result["ok_vdisk"] = ok_vdisk
        result["ok_q"] = ok_q
        result["ok_vline"] = ok_vline
        result["val_tdisk"] = t_disk
        result["val_vdisk"] = v_disk
        result["val_q"] = q_actual
        result["val_vline"] = v_line
        return result
