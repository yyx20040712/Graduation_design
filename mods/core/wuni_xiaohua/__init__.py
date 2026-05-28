"""wuni_xiaohua.py — 污泥消化池 (Anaerobic Sludge Digester)"""

import math
from typing import Dict, List, Tuple, Optional

import numpy as np

from models.base import (
    NodeBase,
    NodeResult,
    SludgeFlow,
    ParamDef,
    Port,
    PortType,
    PI,
)


class WuniXiaohuaNode(NodeBase):
    """污泥消化池 — 厌氧消化 + 沼气产量

    公式来源: GB50014-2021 §7.3, CJJ 131-2009
    """

    NODE_TYPE = "wuni_xiaohua"
    NODE_NAME = "污泥消化池"
    NODE_CATEGORY = "污泥处理"

    @classmethod
    def _default_params(cls) -> Dict[str, float]:
        return {
            "n": 2,
            "T_digest": 35.0,
            "theta_digest": 20.0,
            "eta_VS": 0.45,
            "biogas_rate": 0.9,
        }

    def _build_param_defs(self) -> List[ParamDef]:
        return [
            ParamDef(
                "池数量",
                "n",
                value=2,
                default=2,
                min_val=1,
                max_val=4,
                step=1,
                unit="座",
            ),
            ParamDef(
                "消化温度",
                "T_digest",
                value=35.0,
                default=35.0,
                min_val=30,
                max_val=55,
                step=1,
                unit="°C",
            ),
            ParamDef(
                "消化时间",
                "theta_digest",
                value=20.0,
                default=20.0,
                min_val=15,
                max_val=30,
                step=1,
                unit="d",
            ),
            ParamDef(
                "VS降解率",
                "eta_VS",
                value=0.45,
                default=0.45,
                min_val=0.30,
                max_val=0.60,
                step=0.05,
                unit="",
            ),
            ParamDef(
                "产气率",
                "biogas_rate",
                value=0.9,
                default=0.9,
                min_val=0.7,
                max_val=1.0,
                step=0.05,
                unit="m³/kgVS",
                description="单位VS降解产沼气量 (0.8~1.0)",
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
                name="消化污泥",
                port_type=PortType.SLUDGE,
                direction="output",
                node_id=self.node_id,
            ),
        ]

    def calculate(self, flow, quality) -> NodeResult:
        n = int(self.get_param("n"))
        T_digest = self.get_param("T_digest")
        theta_digest = self.get_param("theta_digest")
        eta_VS = self.get_param("eta_VS")
        biogas_rate = self.get_param("biogas_rate")

        grid, fixed = self._make_scalar_grid(
            {"n": n, "theta_digest": theta_digest,
             "eta_VS": eta_VS, "biogas_rate": biogas_rate},
            {"T_digest": T_digest, "_sludge_DS": 4000.0,
             "_sludge_Q_wet": 100.0, "_sludge_VS": 0.60},
        )
        res = self._vectorized_compute(grid, flow, quality, fixed)
        r = res[0]

        DS_in = 4000.0
        Q_wet_in = 100.0
        VS_in = DS_in * 0.60
        FS_in = DS_in - VS_in

        result = NodeResult(success=True)
        result.params = {
            "n": n, "T_digest": T_digest, "theta_digest": theta_digest,
            "eta_VS": eta_VS, "biogas_rate": biogas_rate,
        }
        result.add_dimension("池数", n, "座")
        result.add_dimension("池径 D", float(r["D"]), "m")
        result.add_dimension("总高度 H", float(r["H"]), "m")
        result.add_dimension("单池容积", round(float(r["V_single"]), 1), "m³")
        result.add_dimension("总容积", round(float(r["D"]) ** 2 * np.pi / 4 * float(r["H"]) * n, 1), "m³")
        result.add_dimension("消化温度", T_digest, "°C")
        result.add_dimension("消化时间", theta_digest, "d")
        result.add_dimension("进泥湿泥量", round(Q_wet_in, 2), "m³/d")
        result.add_dimension("进泥干固量", round(DS_in, 1), "kg/d")
        result.add_dimension("VS降解量", round(float(r["VS_degraded"]), 1), "kgVS/d")
        result.add_dimension("VS降解率", eta_VS * 100, "%")
        result.add_dimension("出泥干固量", round(VS_in - float(r["VS_degraded"]) + FS_in, 1), "kg/d")
        result.add_dimension("出泥湿泥量", round(float(r["Q_wet_out"]), 2), "m³/d")
        result.add_dimension("出泥含水率", 0.92, "")
        result.add_dimension("沼气产量", round(float(r["biogas"]), 1), "m³/d")
        result.add_dimension("甲烷产量", round(float(r["biogas"]) * 0.65, 1), "m³/d")
        result.add_dimension(
            "容积负荷",
            round(VS_in / (float(r["D"]) ** 2 * np.pi / 4 * float(r["H"]) * n) if float(r["D"]) > 0 else 0, 2),
            "kgVS/(m³·d)",
        )
        result.add_check(
            "池径 D >= 8", bool(r["ok_D_min"]),
            round(float(r["val_D_min"]), 1), ">= 8", "m",
        )
        result.add_check(
            "容积负荷", bool(r["ok_vol_load"]),
            round(float(r["val_vol_load"]), 2), "1.0~4.0", "kgVS/(m³·d)",
        )
        return result

    def execute_sludge(
        self, sludge: SludgeFlow
    ) -> Tuple[Optional[NodeResult], SludgeFlow]:
        n = int(self.get_param("n"))
        T_digest = self.get_param("T_digest")
        theta_digest = self.get_param("theta_digest")
        eta_VS = self.get_param("eta_VS")
        biogas_rate = self.get_param("biogas_rate")

        result = NodeResult(success=True)
        result.params = {
            "n": n,
            "T_digest": T_digest,
            "theta_digest": theta_digest,
            "eta_VS": eta_VS,
            "biogas_rate": biogas_rate,
        }

        DS_in = sludge.DS
        Q_wet_in = sludge.Q_wet
        VS_in = DS_in * sludge.VS_ratio  # kgVS/d
        FS_in = DS_in - VS_in  # kg/d 固定固体

        # ── (A) 消化池容积 (GB50014 §7.3.4) ──
        V_total = Q_wet_in * theta_digest
        V_single = V_total / n

        # ── (B) 池体尺寸 (圆柱形) ──
        # H/D ≈ 0.8~1.2 (卵形或圆柱形)
        ratio_HD = 0.9
        D_theory = (4 * V_single / (PI * ratio_HD)) ** (1 / 3)
        D = math.ceil(max(D_theory, 8.0) / 0.5) * 0.5  # 最小 8m
        H_theory = V_single / (PI * (D / 2) ** 2)
        H = math.ceil(max(H_theory, 8.0) / 0.5) * 0.5

        result.add_check("池径 D >= 8", D >= 8, round(D, 1), ">= 8", "m")

        # ── (C) 容积负荷校核 ──
        V_actual = PI * (D / 2) ** 2 * H * n
        vol_load = VS_in / V_actual if V_actual > 0 else 0  # kgVS/(m³·d)
        result.add_check(
            "容积负荷",
            1.0 <= vol_load <= 4.0,
            round(vol_load, 2),
            "1.0~4.0",
            "kgVS/(m³·d)",
        )

        # ── (D) VS 降解 ──
        VS_degraded = VS_in * eta_VS  # kgVS/d
        VS_out = VS_in - VS_degraded
        DS_out = VS_out + FS_in
        VS_ratio_out = VS_out / DS_out if DS_out > 0 else 0

        # ── (E) 沼气产量 ──
        biogas_daily = VS_degraded * biogas_rate  # m³/d
        # 甲烷含量 ~65%
        methane_daily = biogas_daily * 0.65

        # ── (F) 出泥含水率 (消化后 ~92%) ──
        P_out = 0.92
        Q_wet_out = DS_out / ((1 - P_out) * 1000.0) if P_out < 1 else float("inf")

        result.add_dimension("池数", n, "座")
        result.add_dimension("池径 D", D, "m")
        result.add_dimension("总高度 H", H, "m")
        result.add_dimension("单池容积", round(V_single, 1), "m³")
        result.add_dimension("总容积", round(V_actual, 1), "m³")
        result.add_dimension("消化温度", T_digest, "°C")
        result.add_dimension("消化时间", theta_digest, "d")
        result.add_dimension("进泥湿泥量", round(Q_wet_in, 2), "m³/d")
        result.add_dimension("进泥干固量", round(DS_in, 1), "kg/d")
        result.add_dimension("VS降解量", round(VS_degraded, 1), "kgVS/d")
        result.add_dimension("VS降解率", eta_VS * 100, "%")
        result.add_dimension("出泥干固量", round(DS_out, 1), "kg/d")
        result.add_dimension("出泥湿泥量", round(Q_wet_out, 2), "m³/d")
        result.add_dimension("出泥含水率", P_out, "")
        result.add_dimension("沼气产量", round(biogas_daily, 1), "m³/d")
        result.add_dimension("甲烷产量", round(methane_daily, 1), "m³/d")
        result.add_dimension("容积负荷", round(vol_load, 2), "kgVS/(m³·d)")

        sludge_out = SludgeFlow(
            Q_wet=Q_wet_out,
            DS=DS_out,
            P_moisture=P_out,
            VS_ratio=VS_ratio_out,
        )
        self._sludge_output = sludge_out
        return result, sludge_out

    @classmethod
    def _vectorized_compute(cls, grid, flow, quality, fixed):
        """向量化消化池 — 厌氧消化批量计算"""
        n = grid["n"].astype(np.int32)
        theta_digest = grid["theta_digest"]
        eta_VS = grid["eta_VS"]
        biogas_rate = grid.get(
            "biogas_rate", np.full(len(n), fixed.get("biogas_rate", 0.9))
        )
        T_digest = fixed.get("T_digest", 35.0)
        DS = fixed.get("_sludge_DS", 4000.0)
        Q_wet_in = fixed.get("_sludge_Q_wet", 100.0)
        VS_ratio = fixed.get("_sludge_VS", 0.60)
        N = len(n)
        PI_V = np.pi

        VS_in = DS * VS_ratio
        FS_in = DS - VS_in
        V_total = Q_wet_in * theta_digest
        V_single = V_total / n
        ratio_HD = 0.9
        D_theory = (4 * V_single / (PI_V * ratio_HD)) ** (1 / 3)
        D = np.ceil(np.maximum(D_theory, 8.0) / 0.5) * 0.5
        ok_D = D >= 8

        H_theory = np.where(D > 0, V_single / (PI_V * (D / 2) ** 2), 8.0)
        H = np.ceil(np.maximum(H_theory, 8.0) / 0.5) * 0.5
        V_actual = PI_V * (D / 2) ** 2 * H * n
        vol_load = np.where(V_actual > 0, VS_in / V_actual, 0)
        ok_vol = (1.0 <= vol_load) & (vol_load <= 4.0)

        VS_degraded = VS_in * eta_VS
        DS_out = VS_in - VS_degraded + FS_in
        biogas = VS_degraded * biogas_rate
        Q_wet_out = DS_out / ((1 - 0.92) * 1000.0)
        concrete_m3 = PI_V * (D / 2) ** 2 * H * n * 0.4

        dt = np.dtype(
            [
                ("D", np.float64),
                ("H", np.float64),
                ("V_single", np.float64),
                ("VS_degraded", np.float64),
                ("biogas", np.float64),
                ("Q_wet_out", np.float64),
                ("concrete_m3", np.float64),
                ("ok_D_min", np.bool_),
                ("ok_vol_load", np.bool_),
                ("val_D_min", np.float64),
                ("val_vol_load", np.float64),
            ]
        )
        arr = np.zeros(N, dtype=dt)
        arr["D"] = D
        arr["H"] = H
        arr["V_single"] = V_single
        arr["VS_degraded"] = VS_degraded
        arr["biogas"] = biogas
        arr["Q_wet_out"] = Q_wet_out
        arr["concrete_m3"] = concrete_m3
        arr["ok_D_min"] = ok_D
        arr["ok_vol_load"] = ok_vol
        arr["val_D_min"] = D
        arr["val_vol_load"] = vol_load
        return arr
