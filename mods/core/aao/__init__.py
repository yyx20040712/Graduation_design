"""aao.py — AAO反应池 (A2O生物脱氮除磷)"""

import numpy as np
from typing import Dict, List
from models.base import (
    NodeBase,
    NodeResult,
    WaterFlow,
    WaterQuality,
    SludgeFlow,
    ParamDef,
)


class AAONode(NodeBase):
    NODE_TYPE = "aao"
    NODE_NAME = "AAO反应池"
    NODE_CATEGORY = "市政污水处理"

    def _init_ports(self) -> None:
        """AAO: MIXED进水 → MIXED出水 + SLUDGE排泥(剩余污泥)"""
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
            "n": 2,
            "Ls": 0.10,
            "X_MLSS": 3.5,
            "theta_c": 15,
            "tp": 1.5,
            "tn": 3.0,
            "to": 10.0,
            "h_eff": 5.0,
            "ratio_LB": 2.0,
            "h_super": 0.5,
            "R": 60,
            "Ri": 200,
            "y": 0.7,
            "Y_obs": 0.5,
        }

    def _build_param_defs(self) -> List[ParamDef]:
        return [
            ParamDef(
                "系列数",
                "n",
                value=2,
                default=2,
                min_val=1,
                max_val=4,
                step=1,
                unit="系列",
            ),
            ParamDef(
                "BOD负荷",
                "Ls",
                value=0.10,
                default=0.10,
                min_val=0.05,
                max_val=0.15,
                step=0.01,
                unit="kgBOD5/(kgMLSS·d)",
            ),
            ParamDef(
                "MLSS",
                "X_MLSS",
                value=3.5,
                default=3.5,
                min_val=2.0,
                max_val=4.5,
                step=0.5,
                unit="g/L",
            ),
            ParamDef(
                "厌氧HRT",
                "tp",
                value=1.5,
                default=1.5,
                min_val=1.0,
                max_val=2.0,
                step=0.5,
                unit="h",
            ),
            ParamDef(
                "缺氧HRT",
                "tn",
                value=3.0,
                default=3.0,
                min_val=2.0,
                max_val=4.0,
                step=0.5,
                unit="h",
            ),
            ParamDef(
                "好氧HRT",
                "to",
                value=10.0,
                default=10.0,
                min_val=8.0,
                max_val=12.0,
                step=1.0,
                unit="h",
            ),
            ParamDef(
                "有效水深",
                "h_eff",
                value=5.0,
                default=5.0,
                min_val=4.0,
                max_val=6.0,
                step=0.5,
                unit="m",
            ),
            ParamDef(
                "长宽比",
                "ratio_LB",
                value=2.0,
                default=2.0,
                min_val=1.5,
                max_val=3.0,
                step=0.5,
                unit="",
            ),
        ]

    @classmethod
    def _default_removal_rates(cls) -> Dict[str, float]:
        return {
            "BOD5": 0.92,
            "COD": 0.88,
            "SS": 0.80,
            "NH3N": 0.90,
            "TN": 0.70,
            "TP": 0.75,
        }

    def calculate(self, flow: WaterFlow, quality: WaterQuality) -> NodeResult:
        n = int(self.get_param("n"))
        Ls = self.get_param("Ls")
        X_MLSS = self.get_param("X_MLSS")
        tp = self.get_param("tp")
        tn = self.get_param("tn")
        to = self.get_param("to")
        h_eff = self.get_param("h_eff")
        ratio_LB = self.get_param("ratio_LB")
        h_super = self.get_param("h_super")
        R = self.get_param("R")
        Ri = self.get_param("Ri")
        y = self.get_param("y")
        Y_obs = self.get_param("Y_obs")
        theta_c = self.get_param("theta_c")
        O2_rate = 1.5

        result = NodeResult(success=True)
        result.params = {k: self.get_param(k) for k in self._default_params()}

        grid, fixed = self._make_scalar_grid(
            {"n": n, "tp": tp, "tn": tn, "to": to, "Ls": Ls, "X_MLSS": X_MLSS},
            {"h_eff": h_eff, "ratio_LB": ratio_LB, "y": y, "Y_obs": Y_obs,
             "h_super": h_super, "R": R, "Ri": Ri, "O2_rate": O2_rate},
        )
        res = self._vectorized_compute(grid, flow, quality, fixed)
        r = res[0]

        result.add_check(
            "总HRT", bool(r["ok_HRT_total"]),
            round(float(r["val_HRT_total"]), 1), f">= {tp+tn+to-1:.0f}", "h"
        )
        result.add_check(
            "好氧HRT", bool(r["ok_HRT_oxic"]),
            round(float(r["val_HRT_oxic"]), 1), f">= {to-1:.0f}", "h"
        )
        if float(r["val_BOD_load"]) > 0:
            result.add_check(
                "BOD负荷", bool(r["ok_BOD_load"]),
                round(float(r["val_BOD_load"]), 1), f"<= {float(r['Vo']):.0f}", "m3"
            )

        result.add_dimension("系列数", n, "系列")
        result.add_dimension("池长 L", float(r["L"]), "m")
        result.add_dimension("池宽 B", float(r["B"]), "m")
        result.add_dimension("有效水深", h_eff, "m")
        result.add_dimension("总高度", float(r["H_total"]), "m")
        result.add_dimension("厌氧区容积", round(float(r["Va"]), 1), "m3")
        result.add_dimension("缺氧区容积", round(float(r["Vn"]), 1), "m3")
        result.add_dimension("好氧区容积", round(float(r["Vo"]), 1), "m3")
        result.add_dimension("单系列总容积", round(float(r["V_total_series"]), 1), "m3")
        result.add_dimension("总有效容积", round(float(r["V_total"]), 1), "m3")
        result.add_dimension("总HRT", round(float(r["t_total"]), 1), "h")
        result.add_dimension("BOD污泥负荷", Ls, "kgBOD5/(kgMLSS·d)")
        result.add_dimension("污泥龄", theta_c, "d")
        result.add_dimension("日产泥量", round(float(r["Px"]), 1), "kg/d")
        result.add_dimension("日需氧量", round(float(r["O2_total"]), 1), "kgO2/d")
        result.add_dimension("污泥回流比", R, "%")
        result.add_dimension("内回流比", Ri, "%")
        result.add_dimension("回流污泥量", round(float(r["Q_r"]), 2), "m3/h")
        result.add_dimension("内回流量", round(float(r["Q_ri"]), 2), "m3/h")
        result.add_dimension("总面积", round(float(r["area_total"]), 1), "m2")
        result.add_dimension("混凝土量估算", round(float(r["concrete_m3"]), 1), "m3")

        # ── 污泥输出 (SLUDGE 端口, 剩余活性污泥) ──
        Px = float(r["Px"])
        P_moisture_was = 0.992
        Q_wet_was = Px / ((1 - P_moisture_was) * 1000.0) if Px > 0 else 0.0
        self._sludge_output = SludgeFlow(
            Q_wet=Q_wet_was,
            DS=Px,
            P_moisture=P_moisture_was,
            VS_ratio=0.50,
        )

        return result

    @classmethod
    def _vectorized_compute(cls, grid, flow, quality, fixed):
        n = grid["n"].astype(np.int32)
        tp = grid["tp"]
        tn = grid["tn"]
        to = grid["to"]
        Ls = grid.get("Ls", np.full(len(n), fixed.get("Ls", 0.10)))
        X_MLSS = grid.get("X_MLSS", np.full(len(n), fixed.get("X_MLSS", 3.5)))
        h_eff = fixed["h_eff"]
        ratio_LB = fixed["ratio_LB"]
        y = fixed["y"]
        Y_obs = fixed.get("Y_obs", 0.5)
        O2_rate = fixed.get("O2_rate", 1.5)
        h_super = fixed.get("h_super", 0.5)
        N = len(n)
        Q_avg_h = flow.Q_avg_hourly
        Q_per = Q_avg_h / n
        S0 = quality.BOD5
        Va = Q_per * tp
        Vn = Q_per * tn
        Vo = Q_per * to
        V_total_series = Va + Vn + Vo
        A_eff = V_total_series / h_eff
        B_theory = np.sqrt(A_eff / ratio_LB)
        L_theory = ratio_LB * B_theory
        B = np.ceil(B_theory / 0.5) * 0.5
        L = np.ceil(L_theory / 0.5) * 0.5
        V_actual = L * B * h_eff
        t_total = np.where(Q_per > 0, V_actual / Q_per, 0)
        t_oxic = np.where(V_actual > 0, Vo / V_actual * t_total, 0)
        Q_daily = Q_per * 24
        Xv = X_MLSS * y
        with np.errstate(divide="ignore", invalid="ignore"):
            Vo_req = np.where((Ls > 0) & (Xv > 0), Q_daily * S0 / (Ls * Xv * 1000), 0)
        ok_hrt_total = t_total >= (tp + tn + to - 1)
        ok_hrt_oxic = t_oxic >= (to - 1)
        ok_bod = Vo >= Vo_req * 0.6
        H_total = h_eff + h_super
        V_total = V_total_series * n
        area_total = L * B * n
        concrete_m3 = V_total * 1.2
        Q_total_daily = flow.Q_avg_daily
        Px = Y_obs * Q_total_daily * S0 / 1000
        O2_total = O2_rate * Q_total_daily * S0 / 1000 * 0.92
        Q_r = fixed.get("R", 60) / 100 * Q_per
        Q_ri = fixed.get("Ri", 200) / 100 * Q_per
        dtype = np.dtype(
            [
                ("L", np.float64),
                ("B", np.float64),
                ("h_eff_out", np.float64),
                ("Va", np.float64),
                ("Vn", np.float64),
                ("Vo", np.float64),
                ("V_total", np.float64),
                ("V_total_series", np.float64),
                ("H_total", np.float64),
                ("t_total", np.float64),
                ("t_oxic", np.float64),
                ("Px", np.float64),
                ("O2_total", np.float64),
                ("Q_r", np.float64),
                ("Q_ri", np.float64),
                ("H", np.float64),
                ("area_total", np.float64),
                ("concrete_m3", np.float64),
                ("ok_HRT_total", np.bool_),
                ("ok_HRT_oxic", np.bool_),
                ("ok_BOD_load", np.bool_),
                ("val_HRT_total", np.float64),
                ("val_HRT_oxic", np.float64),
                ("val_BOD_load", np.float64),
            ]
        )
        arr = np.zeros(N, dtype=dtype)
        arr["L"] = L
        arr["B"] = B
        arr["h_eff_out"] = h_eff
        arr["Va"] = Va
        arr["Vn"] = Vn
        arr["Vo"] = Vo
        arr["V_total"] = V_total
        arr["V_total_series"] = V_total_series
        arr["H_total"] = H_total
        arr["t_total"] = t_total
        arr["t_oxic"] = t_oxic
        arr["Px"] = Px
        arr["O2_total"] = O2_total
        arr["Q_r"] = Q_r
        arr["Q_ri"] = Q_ri
        arr["area_total"] = area_total
        arr["concrete_m3"] = concrete_m3
        arr["ok_HRT_total"] = ok_hrt_total
        arr["ok_HRT_oxic"] = ok_hrt_oxic
        arr["ok_BOD_load"] = ok_bod
        arr["val_HRT_total"] = t_total
        arr["val_HRT_oxic"] = t_oxic
        arr["val_BOD_load"] = Vo_req
        return arr
