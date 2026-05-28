"""
kw_ningjiao.py — 磁种混凝反应池计算模块

磁种混凝反应池(Magnetic Seed Coagulation Reactor)是磁混凝工艺的核心单元,
通过投加磁种(Fe₃O₄磁铁矿粉)+PAC+PAM,大幅提高絮体密度和磁分离效率.

包含4个功能区:
  1. 混合区 — 投加PAC,快速搅拌 G=600~1000 s⁻¹
  2. 磁种混合区 — 加入磁种+回流磁种,适度搅拌 G=200~500 s⁻¹
  3. 絮凝区 — 投加PAM,慢速搅拌 G=50~100 s⁻¹
  4. 熟化区 — 增强絮体接触,微搅拌 G=30~60 s⁻¹

计算公式来源: dlc.docx §4.4 磁种混凝反应池设计计算
  (4-23)~(4-28): 分区容积
  (4-30)~(4-32): 分区尺寸
  (4-33)~(4-35): 搅拌功率 (含磁种密度修正)
  (4-36)(4-37): 药剂投加量
  (4-38)~(4-40): 磁种投加与补充
  (4-39): γ_mag ≥ 0.5 质量比校核
  (4-41): 出水管径
  (4-42): 总高度
  (4-43): GT值分项校核
"""

from typing import Dict, List

import numpy as np

from models.base import (
    NodeBase,
    NodeResult,
    WaterFlow,
    WaterQuality,
    ParamDef,
)

# ── 物理常数 ──
RHO_W = 1000.0  # 水的密度 kg/m³


class KwNingjiaoNode(NodeBase):
    """磁种混凝反应池 — 4区 + 磁种 + PAC/PAM"""

    NODE_TYPE = "kw_ningjiao"
    NODE_NAME = "混凝反应池"
    NODE_CATEGORY = "矿井水处理"

    @classmethod
    def _default_params(cls) -> Dict[str, float]:
        return {
            "n": 3,  # 系列数
            # 分区停留时间
            "t1": 60,  # 混合区 s (30~60)
            "t2": 1.5,  # 磁种混合区 min (1~2)
            "t3": 4.0,  # 絮凝区 min (3~6)
            "t4": 1.5,  # 熟化区 min (1~2)
            # 分区速度梯度
            "G1": 900,  # 混合区 s⁻¹ (600~1000)
            "G2": 350,  # 磁种混合区 s⁻¹ (200~500)
            "G3": 75,  # 絮凝区 s⁻¹ (50~100)
            "G4": 45,  # 熟化区 s⁻¹ (30~60)
            # 池体几何
            "h_eff": 3.5,  # 有效水深 m (2.5~4.0)
            "h_super": 0.4,  # 超高 m (0.3~0.5)
            # 磁种参数
            "D_mag": 1000,  # 磁种保有浓度 mg/L (500~2000)
            "rho_mag": 5000,  # 磁种密度 kg/m³ (4500~5200)
            "r_loss": 0.04,  # 磁种日损失率 (0.03~0.05)
            # 药剂
            "D_PAC": 80,  # PAC投加量 mg/L (50~100)
            "D_PAM": 2.0,  # PAM投加量 mg/L (0.1~5.0)
            "kappa_PAC": 0.4,  # PAC产泥系数 kgDS/kgPAC (0.3~0.5)
            # 出水
            "v_out": 0.8,  # 出水流速 m/s (0.6~1.0)
            # 水温
            "T_water": 15,  # 设计水温 ℃
        }

    def _build_param_defs(self) -> List[ParamDef]:
        return [
            ParamDef(
                "系列数 n",
                "n",
                value=3,
                default=3,
                min_val=2,
                max_val=4,
                step=1,
                unit="系列",
            ),
            ParamDef(
                "混合区 t₁",
                "t1",
                value=60,
                default=60,
                min_val=30,
                max_val=60,
                step=5,
                unit="s",
            ),
            ParamDef(
                "磁种混合区 t₂",
                "t2",
                value=1.5,
                default=1.5,
                min_val=1.0,
                max_val=2.0,
                step=0.5,
                unit="min",
            ),
            ParamDef(
                "絮凝区 t₃",
                "t3",
                value=4.0,
                default=4.0,
                min_val=3.0,
                max_val=6.0,
                step=1.0,
                unit="min",
            ),
            ParamDef(
                "熟化区 t₄",
                "t4",
                value=1.5,
                default=1.5,
                min_val=1.0,
                max_val=2.0,
                step=0.5,
                unit="min",
            ),
            ParamDef(
                "混合区 G₁",
                "G1",
                value=900,
                default=900,
                min_val=600,
                max_val=1000,
                step=50,
                unit="s⁻¹",
            ),
            ParamDef(
                "磁种混合区 G₂",
                "G2",
                value=350,
                default=350,
                min_val=200,
                max_val=500,
                step=50,
                unit="s⁻¹",
            ),
            ParamDef(
                "絮凝区 G₃",
                "G3",
                value=75,
                default=75,
                min_val=50,
                max_val=100,
                step=25,
                unit="s⁻¹",
            ),
            ParamDef(
                "有效水深 H",
                "h_eff",
                value=3.5,
                default=3.5,
                min_val=2.5,
                max_val=4.0,
                step=0.5,
                unit="m",
            ),
            ParamDef(
                "磁种保有浓度",
                "D_mag",
                value=1000,
                default=1000,
                min_val=500,
                max_val=2000,
                step=100,
                unit="mg/L",
                description="0.5~2.0 g/L",
            ),
            ParamDef(
                "PAC投加量",
                "D_PAC",
                value=80,
                default=80,
                min_val=50,
                max_val=100,
                step=10,
                unit="mg/L",
            ),
            ParamDef(
                "PAM投加量",
                "D_PAM",
                value=2.0,
                default=2.0,
                min_val=0.1,
                max_val=5.0,
                step=0.5,
                unit="mg/L",
            ),
            ParamDef(
                "设计水温",
                "T_water",
                value=15,
                default=15,
                min_val=5,
                max_val=30,
                step=5,
                unit="°C",
            ),
        ]

    @classmethod
    def _default_removal_rates(cls) -> Dict[str, float]:
        return {
            "BOD5": 0.15,
            "COD": 0.40,
            "SS": 0.70,
            "NH3N": 0.05,
            "TN": 0.05,
            "TP": 0.60,
        }

    @staticmethod
    def _water_viscosity(T: float) -> float:
        """水的动力粘度 Pa·s (按水温插值)"""
        # 表格: 5°C=1.519, 10°C=1.307, 15°C=1.139, 20°C=1.002, 25°C=0.890, 30°C=0.797 (×10⁻³)
        pts = [
            (5, 1.519),
            (10, 1.307),
            (15, 1.139),
            (20, 1.002),
            (25, 0.890),
            (30, 0.797),
        ]
        if T <= pts[0][0]:
            return pts[0][1] * 1e-3
        if T >= pts[-1][0]:
            return pts[-1][1] * 1e-3
        for i in range(len(pts) - 1):
            t0, m0 = pts[i]
            t1, m1 = pts[i + 1]
            if t0 <= T <= t1:
                frac = (T - t0) / (t1 - t0)
                return (m0 + frac * (m1 - m0)) * 1e-3
        return 1.0e-3

    def calculate(self, flow: WaterFlow, quality: WaterQuality) -> NodeResult:
        n = int(self.get_param("n"))
        t1_s = self.get_param("t1")
        t2_min = self.get_param("t2")
        t3_min = self.get_param("t3")
        t4_min = self.get_param("t4")
        G1 = self.get_param("G1")
        G2 = self.get_param("G2")
        G3 = self.get_param("G3")
        G4 = self.get_param("G4")
        h_eff = self.get_param("h_eff")
        h_super = self.get_param("h_super")
        D_mag = self.get_param("D_mag")
        rho_mag = self.get_param("rho_mag")
        r_loss = self.get_param("r_loss")
        D_PAC = self.get_param("D_PAC")
        D_PAM = self.get_param("D_PAM")
        kappa_PAC = self.get_param("kappa_PAC")
        v_out = self.get_param("v_out")
        T_water = self.get_param("T_water")

        result = NodeResult(success=True)
        result.params = {
            "n": n,
            "t1": t1_s,
            "t2": t2_min,
            "t3": t3_min,
            "t4": t4_min,
            "G1": G1,
            "G2": G2,
            "G3": G3,
            "G4": G4,
            "h_eff": h_eff,
            "h_super": h_super,
            "D_mag": D_mag,
            "rho_mag": rho_mag,
            "r_loss": r_loss,
            "D_PAC": D_PAC,
            "D_PAM": D_PAM,
            "kappa_PAC": kappa_PAC,
            "v_out": v_out,
            "T_water": T_water,
        }

        grid = {
            "n": np.array([n]),
            "t1": np.array([t1_s]),
            "t2": np.array([t2_min]),
            "t3": np.array([t3_min]),
            "h_eff": np.array([h_eff]),
            "G1": np.array([G1]),
            "G2": np.array([G2]),
            "G3": np.array([G3]),
        }
        fixed = {
            "t4": t4_min,
            "G4": G4,
            "h_super": h_super,
            "D_mag": D_mag,
            "rho_mag": rho_mag,
            "r_loss": r_loss,
            "D_PAC": D_PAC,
            "D_PAM": D_PAM,
            "kappa_PAC": kappa_PAC,
            "v_out": v_out,
            "T_water": T_water,
        }

        r = self._vectorized_compute(grid, flow, quality, fixed)
        row = r[0]

        # ── 检查与警告 ──
        if not bool(row["ok_ttotal"]):
            result.add_warning(
                f"总停留时间 {float(row['val_ttotal']):.1f}min > 12min,建议减小各分区停留时间"
            )
        result.add_check(
            "总停留时间 ≤ 12min",
            bool(row["ok_ttotal"]),
            round(float(row["val_ttotal"]), 1),
            "≤ 12",
            "min",
        )

        C0 = quality.SS
        sludge_prod = C0 + D_PAC * kappa_PAC
        if not bool(row["ok_gamma"]):
            result.add_warning(
                f"磁种质量比 γ_mag={float(row['val_gamma']):.2f} < 0.5,建议增大 D_mag 至 ≥{0.5*sludge_prod:.0f} mg/L"
            )
        result.add_check(
            "磁种质量比 γ_mag ≥ 0.5",
            bool(row["ok_gamma"]),
            round(float(row["val_gamma"]), 3),
            "≥ 0.5",
            "",
        )

        # ── L/B / L_i ≥ 0.3 形状校核 ──
        B_val = float(row["B"])
        L1_val = float(row["L1"])
        L2_val = float(row["L2"])
        L3_val = float(row["L3"])
        L4_val = float(row["L4"])
        areas = [L1_val * B_val, L2_val * B_val, L3_val * B_val, L4_val * B_val]
        i_max = areas.index(max(areas)) + 1  # 1-based
        zone_names = ["混合区", "磁种混合区", "絮凝区", "熟化区"]
        for i, name in enumerate(zone_names, 1):
            Li = [L1_val, L2_val, L3_val, L4_val][i - 1]
            if B_val > 0 and Li > 0:
                ok_field = f"ok_LB{i}"
                val_field = f"val_LB{i}"
                if i == i_max:
                    result.add_check(
                        f"分区{i} {name} L/B 0.8~1.5",
                        bool(row[ok_field]),
                        round(float(row[val_field]), 2),
                        "0.8~1.5",
                        "",
                    )
                else:
                    result.add_check(
                        f"分区{i} {name} L_i ≥ 0.3m",
                        bool(row[ok_field]),
                        round(Li, 2),
                        "≥ 0.3",
                        "m",
                    )

        result.add_check(
            "混合区 GT₁ 5e4~1e5",
            bool(row["ok_GT1"]),
            round(float(row["val_GT1"]), 0),
            "5e4~1e5",
            "",
        )
        result.add_check(
            "磁种混合区 GT₂ 3e4~5e4",
            bool(row["ok_GT2"]),
            round(float(row["val_GT2"]), 0),
            "3e4~5e4",
            "",
        )
        result.add_check(
            "絮凝区 GT₃ 1e4~3e4",
            bool(row["ok_GT3"]),
            round(float(row["val_GT3"]), 0),
            "1e4~3e4",
            "",
        )
        result.add_check(
            "熟化区 GT₄ 3e3~1e4",
            bool(row["ok_GT4"]),
            round(float(row["val_GT4"]), 0),
            "3e3~1e4",
            "",
        )

        # ── PAC/PAM 小时耗量 (不在向量化输出中, 单独计算) ──
        Q_1_m3h = flow.Q_design * 3600 / n
        PAC_kg_h = Q_1_m3h * D_PAC / 1000
        PAM_kg_h = Q_1_m3h * D_PAM / 1000

        # ── 维度标签 (与原有 labels.json 完全一致) ──
        result.add_dimension("系列数", n, "系列", category="physical")
        result.add_dimension("有效水深 H", h_eff, "m", category="physical")
        result.add_dimension(
            "总高度 H_t",
            round(float(row["H_total"]), 2),
            "m",
            formula="H_t = H + h_free",
            category="physical",
        )
        result.add_dimension("池宽 B", round(float(row["B"]), 1), "m", category="physical")
        result.add_dimension(
            "单格总长 L_cell",
            round(float(row["L_cell"]), 1),
            "m",
            formula="L_cell = L1+L2+L3+L4",
            category="physical",
        )
        result.add_dimension("混合区长度 L1", round(float(row["L1"]), 1), "m", category="physical")
        result.add_dimension("磁种混合区长度 L2", round(float(row["L2"]), 1), "m", category="physical")
        result.add_dimension("絮凝区长度 L3", round(float(row["L3"]), 1), "m", category="physical")
        result.add_dimension("熟化区长度 L4", round(float(row["L4"]), 1), "m", category="physical")
        result.add_dimension(
            "单格总容积 V_cell", round(float(row["V_cell"]), 1), "m³", category="physical"
        )
        result.add_dimension(
            "总有效容积 V_total", round(float(row["V_total"]), 1), "m³", category="physical"
        )
        result.add_dimension(
            "总停留时间 t_total",
            round(float(row["t_total"]), 1),
            "min",
            formula="t_total = 60×V_cell/Q_1",
            category="computed",
        )
        result.add_dimension(
            "搅拌总功率",
            round(float(row["P_kW"]), 1),
            "kW",
            formula="P = Σ(G_i²×μ×V_i)×k_ρ×n/1000",
            category="computed",
        )
        result.add_dimension(
            "PAC小时耗量(单系列)",
            round(PAC_kg_h, 2),
            "kg/h",
            formula="W_PAC = Q₁×D_PAC×10⁻³",
            category="computed",
        )
        result.add_dimension(
            "PAM小时耗量(单系列)",
            round(PAM_kg_h, 3),
            "kg/h",
            formula="W_PAM = Q₁×D_PAM×10⁻³",
            category="computed",
        )
        result.add_dimension(
            "PAC日耗量", round(float(row["PAC_kg_d"]), 1), "kg/d", category="computed"
        )
        result.add_dimension(
            "PAM日耗量", round(float(row["PAM_kg_d"]), 2), "kg/d", category="computed"
        )
        result.add_dimension(
            "磁种保有量(单格)",
            round(float(row["M_mag"]), 1),
            "kg",
            formula="M_mag = V_cell×D_mag×10⁻³",
            category="computed",
        )
        result.add_dimension(
            "磁种日补充量",
            round(float(row["M_supply_daily"]), 1),
            "kg/d",
            formula="M_supply = n×M_mag×r_loss",
            category="computed",
        )
        result.add_dimension(
            "磁种质量比 γ_mag",
            round(float(row["gamma_mag"]), 3),
            "",
            formula="γ_mag = D_mag/(C0+D_PAC×κ_PAC)",
            category="computed",
        )
        result.add_dimension(
            "出水管径 D_out",
            int(row["D_out_mm"]),
            "mm",
            formula="D_out = √(4Q/(π·v_out))",
            category="physical",
        )
        result.add_dimension(
            "密度修正系数 k_ρ",
            round(float(row["k_rho"]), 3),
            "",
            formula="k_ρ = ρ_mix/ρ_w",
            category="computed",
        )

        result.add_dimension(
            "总面积", round(float(row["area_total"]), 1), "m²", category="physical"
        )
        result.add_dimension(
            "混凝土量估算", round(float(row["concrete_m3"]), 1), "m³", category="physical"
        )

        return result

    @classmethod
    def _vectorized_compute(
        cls, grid: dict, flow: "WaterFlow", quality: "WaterQuality", fixed: dict
    ) -> "np.ndarray":
        n = grid["n"].astype(np.int32)
        t1_s = grid["t1"]
        t2_min = grid["t2"]
        t3_min = grid["t3"]
        t4_min = fixed.get("t4", 1.5)
        h_eff = grid["h_eff"]
        G1 = grid["G1"]
        G2 = grid["G2"]
        G3 = grid["G3"]
        G4 = fixed.get("G4", 45.0)
        h_super = fixed["h_super"]
        D_mag = fixed.get("D_mag", 1000.0)
        rho_mag = fixed.get("rho_mag", 5000.0)
        r_loss = fixed.get("r_loss", 0.04)
        D_PAC = fixed.get("D_PAC", 80.0)
        D_PAM = fixed.get("D_PAM", 2.0)
        kappa_PAC = fixed.get("kappa_PAC", 0.4)
        v_out = fixed.get("v_out", 0.8)
        T_water = fixed.get("T_water", 15.0)
        N = len(n)

        # 粘度
        mu_arr = np.full(N, cls._water_viscosity(float(T_water)))

        if flow.Q_design <= 0:
            dtype = np.dtype(
                [
                    ("L_cell", np.float64),
                    ("B", np.float64),
                    ("H_total", np.float64),
                    ("L1", np.float64),
                    ("L2", np.float64),
                    ("L3", np.float64),
                    ("L4", np.float64),
                    ("V_cell", np.float64),
                    ("V_total", np.float64),
                    ("t_total", np.float64),
                    ("P_kW", np.float64),
                    ("M_mag", np.float64),
                    ("M_supply_daily", np.float64),
                    ("gamma_mag", np.float64),
                    ("k_rho", np.float64),
                    ("D_out_mm", np.float64),
                    ("PAC_kg_d", np.float64),
                    ("PAM_kg_d", np.float64),
                    ("H", np.float64),
                    ("area_total", np.float64),
                    ("concrete_m3", np.float64),
                    ("ok_ttotal", np.bool_),
                    ("ok_gamma", np.bool_),
                    ("ok_GT1", np.bool_),
                    ("ok_GT2", np.bool_),
                    ("ok_GT3", np.bool_),
                    ("ok_GT4", np.bool_),
                    ("ok_LB1", np.bool_),
                    ("ok_LB2", np.bool_),
                    ("ok_LB3", np.bool_),
                    ("ok_LB4", np.bool_),
                    ("val_ttotal", np.float64),
                    ("val_gamma", np.float64),
                    ("val_GT1", np.float64),
                    ("val_GT2", np.float64),
                    ("val_GT3", np.float64),
                    ("val_GT4", np.float64),
                    ("val_LB1", np.float64),
                    ("val_LB2", np.float64),
                    ("val_LB3", np.float64),
                    ("val_LB4", np.float64),
                ]
            )
            return np.zeros(N, dtype=dtype)

        Q_max = flow.Q_design
        Q_1 = Q_max / n

        t2_s = t2_min * 60
        t3_s = t3_min * 60
        t4_s = t4_min * 60

        V1 = Q_1 * t1_s
        V2 = Q_1 * t2_s
        V3 = Q_1 * t3_s
        V4 = Q_1 * t4_s
        V_cell = V1 + V2 + V3 + V4

        t_total = V_cell / Q_1 / 60.0
        ok_ttotal = t_total <= 12

        A1 = V1 / h_eff
        A2 = V2 / h_eff
        A3 = V3 / h_eff
        A4 = V4 / h_eff
        A_max = np.maximum(np.maximum(A1, A2), np.maximum(A3, A4))
        B_calc = np.sqrt(A_max / 1.2)
        B = np.ceil(np.maximum(B_calc, 1.0) / 0.5) * 0.5

        L1 = np.where(B > 0, A1 / B, 0)
        L2 = np.where(B > 0, A2 / B, 0)
        L3 = np.where(B > 0, A3 / B, 0)
        L4 = np.where(B > 0, A4 / B, 0)
        ratio1 = np.where(B > 0, L1 / B, 0)
        ratio2 = np.where(B > 0, L2 / B, 0)
        ratio3 = np.where(B > 0, L3 / B, 0)
        ratio4 = np.where(B > 0, L4 / B, 0)

        # L/B 校核: 仅对面积最大分区校验
        areas = np.stack([A1, A2, A3, A4], axis=-1)  # (N, 4)
        i_max = np.argmax(areas, axis=-1)  # (N,) 0-based index of max area
        ok_LB1 = np.where(i_max == 0, (0.8 <= ratio1) & (ratio1 <= 1.5), L1 >= 0.3)
        ok_LB2 = np.where(i_max == 1, (0.8 <= ratio2) & (ratio2 <= 1.5), L2 >= 0.3)
        ok_LB3 = np.where(i_max == 2, (0.8 <= ratio3) & (ratio3 <= 1.5), L3 >= 0.3)
        ok_LB4 = np.where(i_max == 3, (0.8 <= ratio4) & (ratio4 <= 1.5), L4 >= 0.3)

        L_cell = L1 + L2 + L3 + L4

        P1 = G1**2 * mu_arr * V1
        P2_raw = G2**2 * mu_arr * V2
        P3_raw = G3**2 * mu_arr * V3
        P4 = G4**2 * mu_arr * V4
        rho_mix = RHO_W + D_mag * (rho_mag - RHO_W) / 1e6
        k_rho = rho_mix / RHO_W
        P2 = k_rho * P2_raw
        P3 = P3_raw * 1.2
        P_kW = (P1 + P2 + P3 + P4) * n / 1000

        C0 = quality.SS
        sludge_prod = C0 + D_PAC * kappa_PAC
        gamma_mag = np.where(sludge_prod > 0, D_mag / sludge_prod, np.inf)
        ok_gamma = gamma_mag >= 0.5

        M_mag = V_cell * D_mag / 1000

        D_out_theory = np.where(v_out > 0, np.sqrt(4 * Q_1 / (np.pi * v_out)), 0.0)
        D_out_mm = np.round(
            np.ceil(np.maximum(D_out_theory, 0.05) / 0.01) * 0.01 * 1000
        )

        H_total = h_eff + h_super

        GT1 = G1 * t1_s
        GT2 = G2 * t2_s
        GT3 = G3 * t3_s
        GT4 = G4 * t4_s
        ok_GT1 = (5e4 <= GT1) & (GT1 <= 1e5)
        ok_GT2 = (3e4 <= GT2) & (GT2 <= 5e4)
        ok_GT3 = (1e4 <= GT3) & (GT3 <= 3e4)
        ok_GT4 = (3e3 <= GT4) & (GT4 <= 1e4)

        area_total = L_cell * B * n
        concrete_m3 = V_cell * n * 1.25
        V_total = V_cell * n
        Q_daily = flow.Q_avg_daily
        PAC_kg_d = D_PAC * Q_daily / 1000
        PAM_kg_d = D_PAM * Q_daily / 1000
        M_supply_daily = n * M_mag * r_loss

        dtype = np.dtype(
            [
                ("L_cell", np.float64),
                ("B", np.float64),
                ("H_total", np.float64),
                ("L1", np.float64),
                ("L2", np.float64),
                ("L3", np.float64),
                ("L4", np.float64),
                ("V_cell", np.float64),
                ("V_total", np.float64),
                ("t_total", np.float64),
                ("P_kW", np.float64),
                ("M_mag", np.float64),
                ("M_supply_daily", np.float64),
                ("gamma_mag", np.float64),
                ("k_rho", np.float64),
                ("D_out_mm", np.float64),
                ("PAC_kg_d", np.float64),
                ("PAM_kg_d", np.float64),
                ("H", np.float64),
                ("area_total", np.float64),
                ("concrete_m3", np.float64),
                ("ok_ttotal", np.bool_),
                ("ok_gamma", np.bool_),
                ("ok_GT1", np.bool_),
                ("ok_GT2", np.bool_),
                ("ok_GT3", np.bool_),
                ("ok_GT4", np.bool_),
                ("ok_LB1", np.bool_),
                ("ok_LB2", np.bool_),
                ("ok_LB3", np.bool_),
                ("ok_LB4", np.bool_),
                ("val_ttotal", np.float64),
                ("val_gamma", np.float64),
                ("val_GT1", np.float64),
                ("val_GT2", np.float64),
                ("val_GT3", np.float64),
                ("val_GT4", np.float64),
                ("val_LB1", np.float64),
                ("val_LB2", np.float64),
                ("val_LB3", np.float64),
                ("val_LB4", np.float64),
            ]
        )
        result = np.empty(N, dtype=dtype)
        result["L_cell"] = L_cell
        result["B"] = B
        result["H_total"] = H_total
        result["L1"] = L1
        result["L2"] = L2
        result["L3"] = L3
        result["L4"] = L4
        result["V_cell"] = V_cell
        result["V_total"] = V_total
        result["t_total"] = t_total
        result["P_kW"] = P_kW
        result["M_mag"] = M_mag
        result["M_supply_daily"] = M_supply_daily
        result["gamma_mag"] = gamma_mag
        result["k_rho"] = k_rho
        result["D_out_mm"] = D_out_mm
        result["PAC_kg_d"] = PAC_kg_d
        result["PAM_kg_d"] = PAM_kg_d
        result["H"] = result["H_total"]
        result["area_total"] = area_total
        result["concrete_m3"] = concrete_m3
        result["ok_ttotal"] = ok_ttotal
        result["ok_gamma"] = ok_gamma
        result["ok_GT1"] = ok_GT1
        result["ok_GT2"] = ok_GT2
        result["ok_GT3"] = ok_GT3
        result["ok_GT4"] = ok_GT4
        result["ok_LB1"] = ok_LB1
        result["ok_LB2"] = ok_LB2
        result["ok_LB3"] = ok_LB3
        result["ok_LB4"] = ok_LB4
        result["val_ttotal"] = t_total
        result["val_gamma"] = gamma_mag
        result["val_GT1"] = GT1
        result["val_GT2"] = GT2
        result["val_GT3"] = GT3
        result["val_GT4"] = GT4
        result["val_LB1"] = ratio1
        result["val_LB2"] = ratio2
        result["val_LB3"] = ratio3
        result["val_LB4"] = ratio4
        return result
