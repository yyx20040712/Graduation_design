"""wuni_ganhua.py — 污泥干化 (Sludge Drying)"""

from typing import Dict, List, Tuple, Optional

import numpy as np

from models.base import (
    NodeBase,
    NodeResult,
    SludgeFlow,
    ParamDef,
    Port,
    PortType,
)

# 水的汽化潜热 kJ/kg at ~100°C
LATENT_HEAT_WATER = 2260.0  # kJ/kg


class WuniGanhuaNode(NodeBase):
    """污泥干化 — 热干化/太阳能干化

    公式来源: GB50014-2021 §7.5, CJJ 131-2009
    """

    NODE_TYPE = "wuni_ganhua"
    NODE_NAME = "污泥干化"
    NODE_CATEGORY = "污泥处理"

    @classmethod
    def _default_params(cls) -> Dict[str, float]:
        return {
            "method": 0,  # 0=thermal, 1=solar
            "P_out": 0.25,
            "T_air": 180.0,
            "eta_thermal": 0.70,
            "q_evap": 8.0,
        }

    def _build_param_defs(self) -> List[ParamDef]:
        return [
            ParamDef(
                "干化方式(0=热干化,1=太阳能)",
                "method",
                value=0,
                default=0,
                min_val=0,
                max_val=1,
                step=1,
                unit="-",
            ),
            ParamDef(
                "出泥含水率",
                "P_out",
                value=0.25,
                default=0.25,
                min_val=0.10,
                max_val=0.40,
                step=0.05,
                unit="-",
            ),
            ParamDef(
                "热风温度",
                "T_air",
                value=180.0,
                default=180.0,
                min_val=120,
                max_val=250,
                step=10,
                unit="°C",
            ),
            ParamDef(
                "热效率",
                "eta_thermal",
                value=0.70,
                default=0.70,
                min_val=0.55,
                max_val=0.85,
                step=0.05,
                unit="-",
            ),
            ParamDef(
                "蒸发速率",
                "q_evap",
                value=8.0,
                default=8.0,
                min_val=4,
                max_val=15,
                step=1,
                unit="kgH2O/(m²·h)",
            ),
        ]

    @classmethod
    def _default_removal_rates(cls) -> Dict[str, float]:
        return {}

    def _init_ports(self) -> None:
        self.input_ports = [
            Port(
                port_id=f"{self.node_id}-s_in",
                name="污泥进",
                port_type=PortType.SLUDGE,
                direction="input",
                node_id=self.node_id,
            ),
        ]
        self.output_ports = [
            Port(
                port_id=f"{self.node_id}-s_out",
                name="干化污泥",
                port_type=PortType.SLUDGE,
                direction="output",
                node_id=self.node_id,
            ),
        ]

    def calculate(self, flow, quality) -> NodeResult:
        method = int(self.get_param("method"))
        P_out = self.get_param("P_out")
        T_air = self.get_param("T_air")
        eta_thermal = self.get_param("eta_thermal")
        q_evap = self.get_param("q_evap")
        method_name = "热干化" if method == 0 else "太阳能干化"

        grid, fixed = self._make_scalar_grid(
            {"method": method, "P_out": P_out, "q_evap": q_evap, "eta_thermal": eta_thermal},
            {"T_air": T_air, "_sludge_DS": 4000.0, "_sludge_Q_wet": 100.0, "_sludge_P": 0.80},
        )
        res = self._vectorized_compute(grid, flow, quality, fixed)
        r = res[0]

        DS = 4000.0
        Q_wet_in = 100.0
        P_in = 0.80
        water_evap = float(r["water_evap"])
        Q_wet_out_val = float(r["Q_wet_out"])

        result = NodeResult(success=True)
        result.params = {
            "method": method, "P_out": P_out, "T_air": T_air,
            "eta_thermal": eta_thermal, "q_evap": q_evap,
        }
        result.add_dimension("干化方式", method_name, "")
        result.add_dimension("进泥湿泥量", round(Q_wet_in, 2), "m³/d")
        result.add_dimension("进泥含水率", round(P_in, 3), "")
        result.add_dimension("出泥湿泥量", round(Q_wet_out_val, 2), "m³/d")
        result.add_dimension("出泥含水率", P_out, "")
        result.add_dimension("蒸发水量", round(water_evap, 1), "kg/d")
        result.add_dimension("干固体量", round(DS, 1), "kg/d")
        result.add_dimension(
            "减量率",
            round((Q_wet_in - Q_wet_out_val) / max(Q_wet_in, 0.01) * 100, 1), "%",
        )
        if method == 0:
            result.add_dimension("热风温度", T_air, "°C")
            result.add_dimension("热效率", eta_thermal * 100, "%")
            result.add_dimension("总热耗", round(float(r["heat_total"]), 1), "MJ/d")
            coal_equiv = float(r["heat_total"]) / 29307.0
            result.add_dimension("折合标煤", round(coal_equiv, 3), "tce/d")
        result.add_dimension("干化面积", round(float(r["A_dry"]), 1), "m²")
        if method == 0:
            result.add_check(
                "蒸发速率合理", bool(r["ok_evap_rate"]), q_evap, "4~15", "kgH2O/(m²·h)",
            )
        else:
            result.add_check(
                "蒸发速率合理", bool(r["ok_evap_rate"]), q_evap, "5~15", "kgH2O/(m²·d)",
            )
        return result

    def execute_sludge(
        self, sludge: SludgeFlow
    ) -> Tuple[Optional[NodeResult], SludgeFlow]:
        method = int(self.get_param("method"))
        P_out = self.get_param("P_out")
        T_air = self.get_param("T_air")
        eta_thermal = self.get_param("eta_thermal")
        q_evap = self.get_param("q_evap")

        method_name = "热干化" if method == 0 else "太阳能干化"

        result = NodeResult(success=True)
        result.params = {
            "method": method,
            "P_out": P_out,
            "T_air": T_air,
            "eta_thermal": eta_thermal,
            "q_evap": q_evap,
        }

        DS = sludge.DS
        Q_wet_in = sludge.Q_wet
        P_in = sludge.P_moisture

        # ── (A) 蒸发水量 ──
        # 湿泥中干固量: DS = Q_wet_in * ρ * (1 - P_in)
        # ρ ≈ 1000 kg/m³ for wet sludge
        m_wet_in = Q_wet_in * 1000.0  # kg/d (近似)
        m_water_in = m_wet_in * P_in
        m_dry = m_wet_in * (1 - P_in)  # kg/d

        # 目标含水率 P_out:
        # P_out = m_water_out / (m_water_out + m_dry)
        # → m_water_out = P_out * m_dry / (1 - P_out)
        m_water_out = P_out * m_dry / (1 - P_out) if P_out < 1 else m_water_in
        m_water_evap = max(0, m_water_in - m_water_out)  # kg/d

        # ── (B) 出泥量 ──
        Q_wet_out = (m_dry + m_water_out) / 1000.0  # m³/d
        DS_out = m_dry  # 干固量不变

        # ── (C) 热耗 (热干化) ──
        if method == 0:
            # 蒸发 + 升温
            heat_sensible = m_wet_in * 4.2 * (100 - 20) / 1000.0  # MJ/d (20→100°C)
            heat_latent = m_water_evap * LATENT_HEAT_WATER / 1000.0  # MJ/d
            heat_total = (heat_sensible + heat_latent) / eta_thermal  # MJ/d
            # 折合标准煤 (1 tce = 29307 MJ)
            coal_equiv = heat_total / 29307.0  # tce/d
        else:
            heat_total = 0
            coal_equiv = 0

        # ── (D) 干化面积 ──
        if method == 0:  # 热干化: q_evap in kgH2O/(m²·h)
            A_dry = m_water_evap / (q_evap * 24.0) if q_evap > 0 else 0
        else:  # 太阳能干化: q_evap in kgH2O/(m²·d)
            A_dry = m_water_evap / q_evap if q_evap > 0 else 0

        # ── 组装结果 ──
        result.add_dimension("干化方式", method_name, "")
        result.add_dimension("进泥湿泥量", round(Q_wet_in, 2), "m³/d")
        result.add_dimension("进泥含水率", round(P_in, 3), "")
        result.add_dimension("出泥湿泥量", round(Q_wet_out, 2), "m³/d")
        result.add_dimension("出泥含水率", P_out, "")
        result.add_dimension("蒸发水量", round(m_water_evap, 1), "kg/d")
        result.add_dimension("干固体量", round(DS, 1), "kg/d")
        result.add_dimension(
            "减量率", round((Q_wet_in - Q_wet_out) / max(Q_wet_in, 0.01) * 100, 1), "%"
        )

        if method == 0:
            result.add_dimension("热风温度", T_air, "°C")
            result.add_dimension("热效率", eta_thermal * 100, "%")
            result.add_dimension("总热耗", round(heat_total, 1), "MJ/d")
            result.add_dimension("折合标煤", round(coal_equiv, 3), "tce/d")

        result.add_dimension("干化面积", round(A_dry, 1), "m²")
        if method == 0:
            result.add_check(
                "蒸发速率合理", 4 <= q_evap <= 15, q_evap, "4~15", "kgH2O/(m²·h)"
            )
        else:
            result.add_check(
                "蒸发速率合理", 5 <= q_evap <= 15, q_evap, "5~15", "kgH2O/(m²·d)"
            )

        sludge_out = SludgeFlow(
            Q_wet=Q_wet_out,
            DS=DS_out,
            P_moisture=P_out,
            VS_ratio=sludge.VS_ratio,
        )
        self._sludge_output = sludge_out
        return result, sludge_out

    @classmethod
    def _vectorized_compute(cls, grid, flow, quality, fixed):
        """向量化干化 — 热干化/太阳能批量计算"""
        P_out = grid["P_out"]
        q_evap = grid["q_evap"]
        method = grid["method"].astype(np.int32)
        eta_thermal = grid.get(
            "eta_thermal", np.full(len(P_out), fixed.get("eta_thermal", 0.70))
        )
        DS = fixed.get("_sludge_DS", 4000.0)
        Q_wet_in = fixed.get("_sludge_Q_wet", 100.0)
        P_in = fixed.get("_sludge_P", 0.80)
        N = len(P_out)

        m_wet_in = Q_wet_in * 1000.0
        m_water_in = m_wet_in * P_in
        m_dry = m_wet_in * (1 - P_in)
        m_water_out = np.where(P_out < 1, P_out * m_dry / (1 - P_out), m_water_in)
        water_evap = np.maximum(0, m_water_in - m_water_out)
        Q_wet_out = (m_dry + m_water_out) / 1000.0

        heat_latent = water_evap * LATENT_HEAT_WATER / 1000.0
        heat_sensible = m_wet_in * 4.2 * 80 / 1000.0
        heat_total = np.where(
            eta_thermal > 0, (heat_sensible + heat_latent) / eta_thermal, 1e9
        )

        # 干化面积: 热干化用 kg/(m²·h), 太阳能用 kg/(m²·d)
        is_thermal = method == 0
        A_thermal = np.where(q_evap > 0, water_evap / (q_evap * 24.0), 0)
        A_solar = np.where(q_evap > 0, water_evap / q_evap, 0)
        A_dry = np.where(is_thermal, A_thermal, A_solar)

        ok_evap_th = (q_evap >= 4) & (q_evap <= 15)
        ok_evap_sol = (q_evap >= 5) & (q_evap <= 15)
        ok_evap = np.where(is_thermal, ok_evap_th, ok_evap_sol)

        dt = np.dtype(
            [
                ("water_evap", np.float64),
                ("Q_wet_out", np.float64),
                ("heat_total", np.float64),
                ("A_dry", np.float64),
                ("concrete_m3", np.float64),
                ("ok_evap_rate", np.bool_),
                ("val_evap_rate", np.float64),
            ]
        )
        arr = np.zeros(N, dtype=dt)
        arr["water_evap"] = water_evap
        arr["Q_wet_out"] = Q_wet_out
        arr["heat_total"] = heat_total
        arr["A_dry"] = A_dry
        arr["concrete_m3"] = A_dry * 0.3  # 干化间混凝土量 ≈ 面积×0.3m厚
        arr["ok_evap_rate"] = ok_evap
        arr["val_evap_rate"] = q_evap
        return arr
