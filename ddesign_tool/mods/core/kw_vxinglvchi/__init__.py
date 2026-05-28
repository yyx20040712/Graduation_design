"""kw_vxinglvchi.py — 矿井水V型滤池 (Mine Water V-type Filter)

与市政污水V型滤池计算方式一致,公式(4-95)~(4-123).
"""

import math
from typing import Dict, List
import numpy as np
from models.base import NodeBase, NodeResult, WaterFlow, WaterQuality, ParamDef, PI


class KwVxinglvchiNode(NodeBase):
    NODE_TYPE = "kw_vxinglvchi"
    NODE_NAME = "矿井水V型滤池"
    NODE_CATEGORY = "矿井水处理"

    @classmethod
    def _default_params(cls) -> Dict[str, float]:
        return {
            "n": 4,
            "v_filter": 6.0,
            "v_force": 10.0,
            "T_filter": 24.0,
            "k_self": 1.05,
            "h_media": 1.2,
            "h_water": 1.2,
            "h_super": 0.5,
            "h_plate": 0.1,
            "h_under": 0.9,
            "rho_head": 55.0,
            "q_g1": 15.0,
            "q_w2": 3.0,
            "q_w3": 5.0,
            "q_s": 2.0,
            "t_g1": 3.0,
            "t_gw": 4.0,
            "t_w3": 5.0,
        }

    def _build_param_defs(self) -> List[ParamDef]:
        return [
            ParamDef(
                "滤池格数",
                "n",
                value=4,
                default=4,
                min_val=2,
                max_val=16,
                step=1,
                unit="格",
            ),
            ParamDef(
                "设计滤速",
                "v_filter",
                value=6.0,
                default=6.0,
                min_val=5.0,
                max_val=8.0,
                step=0.5,
                unit="m/h",
            ),
            ParamDef(
                "强制滤速限值",
                "v_force",
                value=10.0,
                default=10.0,
                min_val=7.0,
                max_val=12.0,
                step=0.5,
                unit="m/h",
            ),
            ParamDef(
                "过滤周期",
                "T_filter",
                value=24,
                default=24,
                min_val=12,
                max_val=36,
                step=4,
                unit="h",
            ),
            ParamDef(
                "滤层厚度",
                "h_media",
                value=1.2,
                default=1.2,
                min_val=1.0,
                max_val=1.5,
                step=0.1,
                unit="m",
            ),
            ParamDef(
                "滤层上水深",
                "h_water",
                value=1.2,
                default=1.2,
                min_val=1.2,
                max_val=1.5,
                step=0.1,
                unit="m",
            ),
        ]

    @classmethod
    def _default_removal_rates(cls) -> Dict[str, float]:
        return {
            "SS": 0.65,
            "BOD5": 0.15,
            "COD": 0.25,
            "NH3N": 0.0,
            "TN": 0.0,
            "TP": 0.80,
        }

    def calculate(self, flow: WaterFlow, quality: WaterQuality) -> NodeResult:
        n = int(self.get_param("n"))
        v_filter_val = self.get_param("v_filter")
        h_media_val = self.get_param("h_media")
        h_water_val = self.get_param("h_water")

        grid = {
            "n": np.array([n], dtype=np.float64),
            "v_filter": np.array([v_filter_val]),
            "h_media": np.array([h_media_val]),
            "h_water": np.array([h_water_val]),
        }

        fixed = {
            "v_force": self.get_param("v_force"),
            "T_filter": self.get_param("T_filter"),
            "k_self": self.get_param("k_self"),
            "h_super": self.get_param("h_super"),
            "h_plate": self.get_param("h_plate"),
            "h_under": self.get_param("h_under"),
            "rho_head": self.get_param("rho_head"),
            "q_g1": self.get_param("q_g1"),
            "q_w2": self.get_param("q_w2"),
            "q_w3": self.get_param("q_w3"),
            "q_s": self.get_param("q_s"),
            "t_g1": self.get_param("t_g1"),
            "t_gw": self.get_param("t_gw"),
            "t_w3": self.get_param("t_w3"),
        }

        r = type(self)._vectorized_compute(grid, flow, quality, fixed)
        d = r[0]

        result = NodeResult(success=True)
        result.params = {k: self.get_param(k) for k in self._default_params()}

        result.add_dimension("设计总流量 Q_d(总)", round(float(d["Q_d"]), 0), "m³/d")
        result.add_dimension("日有效工作时间 T_w", round(float(d["T_w"]), 1), "h/d")
        result.add_dimension("总过滤面积 F(总)", round(float(d["F_total"]), 1), "m²")
        result.add_dimension("单格过滤面积 f(单格)", round(float(d["f_single"]), 1), "m²")
        result.add_dimension("滤池格数", n, "格")
        result.add_dimension("单格长度 L(单格)", d["L"], "m")
        result.add_dimension("单格宽度 B(单格)", d["B"], "m")
        result.add_dimension("滤池总高度 H_t", math.ceil(float(d["H_total"]) / 0.1) * 0.1, "m")
        result.add_dimension("设计滤速 v", d["v_filter"], "m/h")
        result.add_dimension("实际强制滤速 v_q", round(float(d["v_force_actual"]), 2), "m/h")
        result.add_dimension("单次冲洗水量 W_w(单格)", round(float(d["W_w"]), 1), "m³")
        result.add_dimension("冲洗水占比 η_w", round(float(d["eta_w"]) * 100, 2), "%")
        result.add_dimension("滤头数量 N_nozzle(单格)", int(d["N_head"]), "个")
        result.add_check(
            "强制滤速 v_q <= 限值",
            bool(d["ok_force"]),
            round(float(d["val_force"]), 2),
            f"<= {fixed['v_force']}",
            "m/h",
        )
        result.add_check(
            "冲洗水占比 < 5%",
            bool(d["ok_bw"]),
            round(float(d["val_bw"]) * 100, 1),
            "< 5",
            "%",
        )
        return result

    @classmethod
    def _vectorized_compute(cls, grid, flow, quality, fixed):
        n = grid["n"].astype(np.int32)
        v_filter = grid["v_filter"]
        h_media = grid["h_media"]
        h_water = grid["h_water"]
        v_force = fixed["v_force"]
        T_filter = fixed["T_filter"]
        k_self = fixed["k_self"]
        h_super = fixed["h_super"]
        h_plate = fixed["h_plate"]
        h_under = fixed["h_under"]
        rho_head = fixed["rho_head"]
        q_g1 = fixed.get("q_g1", 15.0)
        q_w2 = fixed.get("q_w2", 3.0)
        q_w3 = fixed.get("q_w3", 5.0)
        q_s = fixed.get("q_s", 2.0)
        t_g1 = fixed.get("t_g1", 3.0)
        t_gw = fixed.get("t_gw", 4.0)
        t_w3 = fixed.get("t_w3", 5.0)
        N = len(n)
        PI_V = np.pi

        if flow.Q_avg_daily <= 0:
            dt = np.dtype(
                [
                    ("F_total", np.float64),
                    ("f_single", np.float64),
                    ("L", np.float64),
                    ("B", np.float64),
                    ("H_total", np.float64),
                    ("W_w", np.float64),
                    ("eta_w", np.float64),
                    ("N_head", np.int32),
                    ("H", np.float64),
                    ("concrete_m3", np.float64),
                    ("ok_force", np.bool_),
                    ("ok_bw", np.bool_),
                    ("val_force", np.float64),
                    ("val_bw", np.float64),
                ]
            )
            return np.zeros(N, dtype=dt)

        Q_d = flow.Q_avg_daily * k_self
        t_bw = t_g1 + t_gw + t_w3
        t_bw_h = t_bw / 60.0
        T_w = 24.0 - 24.0 * t_bw_h / T_filter
        F_total = Q_d / (v_filter * T_w)
        f_single = F_total / n
        v_force_actual = np.where(n > 1, n / (n - 1) * v_filter, np.inf)
        ok_force = v_force_actual <= v_force
        B = np.minimum(np.ceil(np.sqrt(f_single / 2.0) / 0.1) * 0.1, 4.5)
        L = np.ceil(f_single / B / 0.1) * 0.1
        A_actual = L * B
        H_total = h_super + h_water + h_media + h_plate + h_under
        Q_w2_v = q_w2 * A_actual
        Q_w3_v = q_w3 * A_actual
        Q_s_v = q_s * A_actual
        W_w = (Q_w2_v * t_gw * 60 + Q_w3_v * t_w3 * 60 + Q_s_v * t_bw * 60) / 1000.0
        V_daily = Q_d / n
        eta_w = np.where(V_daily > 0, W_w * (24.0 / T_filter) / V_daily, 0.0)
        ok_bw = eta_w < 0.05
        N_head = np.ceil(rho_head * A_actual).astype(np.int32)
        concrete_m3 = L * B * H_total * n * 0.4

        dt = np.dtype(
            [
                ("F_total", np.float64),
                ("f_single", np.float64),
                ("L", np.float64),
                ("B", np.float64),
                ("A_actual", np.float64),
                ("H_total", np.float64),
                ("v_filter", np.float64),
                ("v_force_actual", np.float64),
                ("W_w", np.float64),
                ("eta_w", np.float64),
                ("N_head", np.int32),
                ("T_w", np.float64),
                ("Q_d", np.float64),
                ("H", np.float64),
                ("concrete_m3", np.float64),
                ("ok_force", np.bool_),
                ("ok_bw", np.bool_),
                ("val_force", np.float64),
                ("val_bw", np.float64),
            ]
        )
        arr = np.empty(N, dtype=dt)
        arr["F_total"] = F_total
        arr["f_single"] = f_single
        arr["L"] = L
        arr["B"] = B
        arr["A_actual"] = A_actual
        arr["H_total"] = H_total
        arr["v_filter"] = v_filter
        arr["v_force_actual"] = v_force_actual
        arr["W_w"] = W_w
        arr["eta_w"] = eta_w
        arr["N_head"] = N_head
        arr["T_w"] = T_w
        arr["Q_d"] = Q_d
        arr["concrete_m3"] = concrete_m3
        arr["H"] = arr["H_total"]
        arr["ok_force"] = ok_force
        arr["ok_bw"] = ok_bw
        arr["val_force"] = v_force_actual
        arr["val_bw"] = eta_w
        return arr
