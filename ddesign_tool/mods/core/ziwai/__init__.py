"""ziwai.py — 紫外消毒池 (UV Disinfection Channel)"""

from typing import Dict, List

import numpy as np

from models.base import (
    NodeBase,
    NodeResult,
    WaterFlow,
    WaterQuality,
    ParamDef,
    GRAVITY,
)


class ZiwaiNode(NodeBase):
    """紫外消毒池

    公式来源: 中期报告 §3.8 (3-124)~(3-130)
    """

    NODE_TYPE = "ziwai"
    NODE_NAME = "紫外消毒池"
    NODE_CATEGORY = "深度处理"

    @classmethod
    def _default_params(cls) -> Dict[str, float]:
        return {
            "n": 2,
            "D_UV": 20.0,
            "k_aging": 0.7,
            "k_foul": 0.8,
            "T254": 65.0,
            "n_T": 1.5,
            "eta_geo": 0.7,
            "v_channel": 0.4,
            "h_channel": 1.0,
            "h_super": 0.3,
            "L_lamp": 1.5,
            "gap": 0.1,
            "N_layer": 6,
            "d_vert": 0.08,
            "d_long": 0.12,
            "P_lamp": 250.0,
            "L_in": 1.0,
            "L_out": 1.0,
            "xi_total": 3.0,
        }

    def _build_param_defs(self) -> List[ParamDef]:
        return [
            ParamDef(
                "渠道数",
                "n",
                value=2,
                default=2,
                min_val=1,
                max_val=3,
                step=1,
                unit="条",
            ),
            ParamDef(
                "紫外剂量",
                "D_UV",
                value=40,
                default=40,
                min_val=20,
                max_val=50,
                step=5,
                unit="mJ/cm²",
            ),
            ParamDef(
                "老化系数",
                "k_aging",
                value=0.7,
                default=0.7,
                min_val=0.6,
                max_val=0.8,
                step=0.05,
                unit="",
            ),
            ParamDef(
                "结垢系数",
                "k_foul",
                value=0.8,
                default=0.8,
                min_val=0.7,
                max_val=0.9,
                step=0.05,
                unit="",
            ),
            ParamDef(
                "紫外透光率",
                "T254",
                value=65,
                default=65,
                min_val=55,
                max_val=75,
                step=5,
                unit="%",
            ),
            ParamDef(
                "渠道流速",
                "v_channel",
                value=0.4,
                default=0.4,
                min_val=0.3,
                max_val=1.8,
                step=0.05,
                unit="m/s",
            ),
            ParamDef(
                "有效水深",
                "h_channel",
                value=1.0,
                default=1.0,
                min_val=0.8,
                max_val=1.8,
                step=0.1,
                unit="m",
            ),
        ]

    @classmethod
    def _default_removal_rates(cls) -> Dict[str, float]:
        # 紫外消毒只灭菌,不改变水质指标
        return {"BOD5": 0.0, "COD": 0.0, "SS": 0.0, "NH3N": 0.0, "TN": 0.0, "TP": 0.0}

    def calculate(self, flow: WaterFlow, quality: WaterQuality) -> NodeResult:
        n = int(self.get_param("n"))
        D_UV = self.get_param("D_UV")
        k_aging = self.get_param("k_aging")
        k_foul = self.get_param("k_foul")
        T254 = self.get_param("T254")
        n_T = self.get_param("n_T")
        eta_geo = self.get_param("eta_geo")
        v_channel = self.get_param("v_channel")
        h_channel = self.get_param("h_channel")
        h_super = self.get_param("h_super")
        L_lamp = self.get_param("L_lamp")
        gap = self.get_param("gap")
        N_layer = int(self.get_param("N_layer"))
        d_vert = self.get_param("d_vert")
        d_long = self.get_param("d_long")
        P_lamp = self.get_param("P_lamp")
        L_in = self.get_param("L_in")
        L_out = self.get_param("L_out")
        xi_total = self.get_param("xi_total")

        result = NodeResult(success=True)
        result.params = {
            "n": n,
            "D_UV": D_UV,
            "k_aging": k_aging,
            "k_foul": k_foul,
            "T254": T254,
            "n_T": n_T,
            "eta_geo": eta_geo,
            "v_channel": v_channel,
            "h_channel": h_channel,
            "h_super": h_super,
            "L_lamp": L_lamp,
            "gap": gap,
            "N_layer": N_layer,
            "d_vert": d_vert,
            "d_long": d_long,
            "P_lamp": P_lamp,
            "L_in": L_in,
            "L_out": L_out,
            "xi_total": xi_total,
        }

        if n <= 0:
            return NodeResult.failed("渠道数 n 必须 >= 1")

        grid = {
            "n": np.array([n], dtype=np.int32),
            "D_UV": np.array([D_UV]),
            "v_channel": np.array([v_channel]),
            "h_channel": np.array([h_channel]),
        }
        fixed = {
            "k_aging": k_aging,
            "k_foul": k_foul,
            "T254": T254,
            "n_T": n_T,
            "eta_geo": eta_geo,
            "h_super": h_super,
            "L_lamp": L_lamp,
            "gap": gap,
            "N_layer": N_layer,
            "d_vert": d_vert,
            "d_long": d_long,
            "P_lamp": P_lamp,
            "L_in": L_in,
            "L_out": L_out,
            "xi_total": xi_total,
        }

        r = self._vectorized_compute(grid, flow, quality, fixed)

        Q_single = flow.Q_design / n
        B_channel = r["B_channel"][0]
        h_ch_eff = r["h_channel_eff"][0]
        A_channel = B_channel * h_ch_eff
        if A_channel <= 0:
            return NodeResult.failed("过流断面面积为 0,请检查渠宽和有效水深")
        v_actual = r["v_actual"][0]
        I_avg = r["I_avg"][0]
        if I_avg <= 0 or v_actual <= 0:
            return NodeResult.failed("光强或流速为 0,无法计算紫外剂量")

        D_actual = r["D_actual"][0]
        N_rows = int(r["N_rows"][0])
        t_actual = r["t_actual"][0]
        N_lamps = int(r["N_lamps"][0])
        L_total = r["L_total"][0]
        h_loss = r["h_loss"][0]
        H_total = r["H_total"][0]
        k_total = r["k_total"][0]
        T_eff = r["T_eff"][0]

        result.add_check(
            "渠内流速",
            bool(r["ok_v_channel"][0]),
            round(v_actual, 3),
            "0.15~0.7",
            "m/s",
        )

        if v_actual < 0.15 and n >= 2:
            v_if_single = flow.Q_design / A_channel
            result.add_warning(
                f"渠内流速 {v_actual:.2f} m/s 低于 0.15 m/s 下限."
                f"当前渠道数 n={n},单渠流量仅 {Q_single:.3f} m³/s."
                f"若改为 n=1(单渠道),流速可达 {v_if_single:.2f} m/s,"
                f"但将失去备用检修能力."
                f"建议: 在低流量工况下,可接受略低于下限的流速,"
                f"确保紫外剂量达标即可."
            )

        result.add_check(
            "紫外剂量",
            bool(r["ok_UV_dose"][0]),
            round(D_actual, 1),
            f">= {D_UV}",
            "mJ/cm²",
        )

        if t_actual < 6:
            if D_actual >= D_UV:
                result.add_warning(
                    f"接触时间 {t_actual:.1f}s < 6s, 但紫外剂量已达标"
                    f"({D_actual:.0f} ≥ {D_UV:.0f} mJ/cm²), 可接受"
                )
            else:
                result.add_warning(
                    f"接触时间 {t_actual:.1f}s < 6s 且剂量未达标, "
                    f"建议降低流速或增加灯管排数"
                )

        result.add_dimension("渠道数", n, "条")
        result.add_dimension("渠宽", round(B_channel, 2), "m")
        result.add_dimension("有效水深", round(h_ch_eff, 2), "m")
        result.add_dimension("实际流速", round(v_actual, 3), "m/s")
        result.add_dimension("综合衰减系数", round(k_total, 2), "")
        result.add_dimension("有效透光率", round(T_eff, 3), "")
        result.add_dimension("平均光强", round(I_avg, 1), "W/m²")
        result.add_dimension("灯管排数", N_rows, "排")
        result.add_dimension("灯管总数", N_lamps, "支")
        result.add_dimension("接触时间", round(t_actual, 2), "s")
        result.add_dimension("设计剂量", round(D_UV, 0), "mJ/cm²")
        result.add_dimension("实际剂量", round(D_actual, 1), "mJ/cm²")
        result.add_dimension("渠道总长", round(L_total, 2), "m")
        result.add_dimension("水头损失", round(h_loss, 3), "m")
        result.add_dimension("总高度", H_total, "m")

        return result

    @classmethod
    def _vectorized_compute(
        cls, grid: dict, flow: "WaterFlow", quality: "WaterQuality", fixed: dict
    ) -> "np.ndarray":
        """向量化紫外消毒池

        grid: n, D_UV, v_channel, h_channel
        fixed: k_aging, k_foul, T254, n_T, eta_geo, h_super, L_lamp, gap, N_layer, d_vert, d_long, P_lamp, L_in, L_out, xi_total
        """
        n = grid["n"].astype(np.int32)
        D_UV = grid["D_UV"]
        v_channel = grid["v_channel"]
        h_channel = grid["h_channel"]
        k_aging = fixed["k_aging"]
        k_foul = fixed["k_foul"]
        T254 = fixed["T254"]
        n_T = fixed["n_T"]
        eta_geo = fixed["eta_geo"]
        h_super = fixed["h_super"]
        L_lamp = fixed["L_lamp"]
        gap = fixed["gap"]
        N_layer = int(fixed["N_layer"])
        d_vert = fixed["d_vert"]
        d_long = fixed["d_long"]
        P_lamp = fixed["P_lamp"]
        L_in = fixed["L_in"]
        L_out = fixed["L_out"]
        xi_total = fixed["xi_total"]
        N = len(n)
        G = 9.81

        # 零流量守卫: 无上游流量时全部方案标记为不可行
        if flow.Q_design <= 0:
            dtype = np.dtype(
                [
                    ("B_channel", np.float64),
                    ("h_channel_eff", np.float64),
                    ("v_actual", np.float64),
                    ("k_total", np.float64),
                    ("T_eff", np.float64),
                    ("I_avg", np.float64),
                    ("N_rows", np.int32),
                    ("N_lamps", np.int32),
                    ("t_actual", np.float64),
                    ("D_UV_design", np.float64),
                    ("D_actual", np.float64),
                    ("L_total", np.float64),
                    ("h_loss", np.float64),
                    ("H_total", np.float64),
                    ("L", np.float64),
                    ("B", np.float64),
                    ("H", np.float64),
                    ("concrete_m3", np.float64),
                    ("ok_v_channel", np.bool_),
                    ("ok_UV_dose", np.bool_),
                    ("val_v_channel", np.float64),
                    ("val_UV_dose", np.float64),
                ]
            )
            result = np.zeros(N, dtype=dtype)
            return result

        Q_single = flow.Q_design / n
        k_total = k_aging * k_foul
        T_eff = (T254 / 100.0) ** n_T
        B_channel = L_lamp + 2 * gap
        h_min = N_layer * d_vert + 0.3 + 0.2  # h_upper + h_lower
        h_ch_eff = np.maximum(h_channel, h_min)
        A_channel = B_channel * h_ch_eff
        v_actual = Q_single / A_channel
        ok_v = (0.15 <= v_actual) & (v_actual <= 0.7)

        # (4-140) I_avg = N_layer·P_lamp·η·f(τ)·C / (10·A), mW/cm²
        I_avg = P_lamp * N_layer * eta_geo * T_eff * k_total / (10.0 * A_channel)
        dose_per_row = I_avg * d_long / v_actual  # mJ/cm² per row
        N_rows = np.maximum(np.ceil(D_UV / dose_per_row), 1).astype(np.int32)
        t_actual = N_rows * d_long / v_actual
        D_actual = I_avg * t_actual
        ok_dose = D_actual >= D_UV
        N_lamps = N_rows * N_layer
        L_uv = N_rows * d_long
        L_total = L_in + L_uv + L_out
        h_loss = np.maximum(xi_total * v_actual**2 / (2 * G), 0.10)
        H_total = np.ceil((h_ch_eff + h_super) / 0.1) * 0.1

        concrete_m3 = B_channel * L_total * H_total * n * 0.3

        dtype = np.dtype(
            [
                ("B_channel", np.float64),
                ("h_channel_eff", np.float64),
                ("v_actual", np.float64),
                ("k_total", np.float64),
                ("T_eff", np.float64),
                ("I_avg", np.float64),
                ("N_rows", np.int32),
                ("N_lamps", np.int32),
                ("t_actual", np.float64),
                ("D_UV_design", np.float64),
                ("D_actual", np.float64),
                ("L_total", np.float64),
                ("h_loss", np.float64),
                ("H_total", np.float64),
                ("L", np.float64),
                ("H", np.float64),
                ("B", np.float64),
                ("concrete_m3", np.float64),
                ("ok_v_channel", np.bool_),
                ("ok_UV_dose", np.bool_),
                ("val_v_channel", np.float64),
                ("val_UV_dose", np.float64),
            ]
        )
        result = np.empty(N, dtype=dtype)
        result["B_channel"] = B_channel
        result["h_channel_eff"] = h_ch_eff
        result["v_actual"] = v_actual
        result["k_total"] = k_total
        result["T_eff"] = T_eff
        result["I_avg"] = I_avg
        result["N_rows"] = N_rows
        result["N_lamps"] = N_lamps
        result["t_actual"] = t_actual
        result["D_UV_design"] = D_UV
        result["D_actual"] = D_actual
        result["L_total"] = L_total
        result["h_loss"] = h_loss
        result["H_total"] = H_total
        result["concrete_m3"] = concrete_m3
        result["L"] = result["L_total"]  # standard field
        result["B"] = result["B_channel"]  # standard field
        result["H"] = result["H_total"]  # standard field
        result["ok_v_channel"] = ok_v
        result["ok_UV_dose"] = ok_dose
        result["val_v_channel"] = v_actual
        result["val_UV_dose"] = D_actual
        return result
