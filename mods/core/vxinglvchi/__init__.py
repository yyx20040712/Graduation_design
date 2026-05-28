"""vxinglvchi.py — V型滤池 (V-type Filter)

公式来源: 中期报告 §3.7 (4-95)~(4-123)
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
    PI,
)


class VxinglvchiNode(NodeBase):
    """V型滤池 — 均质滤料气水反冲洗

    公式来源: 中期报告 §3.7 (4-95)~(4-123)
    """

    NODE_TYPE = "vxinglvchi"
    NODE_NAME = "V型滤池"
    NODE_CATEGORY = "深度处理"

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
            # 反冲洗参数
            "q_g1": 15.0,
            "q_g2": 15.0,
            "q_w2": 3.0,
            "q_w3": 5.0,
            "q_s": 2.0,
            "t_g1": 3.0,
            "t_gw": 4.0,
            "t_w3": 5.0,
            # 管路流速
            "v_g_pipe": 12.0,
            "v_w_pipe": 2.0,
            "v_out_pipe": 1.0,
            # V型槽扫洗孔
            "d_hole": 0.025,
            "v_hole": 2.0,
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
                value=24.0,
                default=24.0,
                min_val=12.0,
                max_val=36.0,
                step=4.0,
                unit="h",
            ),
            ParamDef(
                "自用水系数",
                "k_self",
                value=1.05,
                default=1.05,
                min_val=1.02,
                max_val=1.10,
                step=0.01,
                unit="",
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
            ParamDef(
                "超高",
                "h_super",
                value=0.5,
                default=0.5,
                min_val=0.3,
                max_val=0.8,
                step=0.1,
                unit="m",
            ),
            ParamDef(
                "承托层厚度",
                "h_plate",
                value=0.1,
                default=0.1,
                min_val=0.05,
                max_val=0.2,
                step=0.05,
                unit="m",
            ),
            ParamDef(
                "配水区高度",
                "h_under",
                value=0.9,
                default=0.9,
                min_val=0.6,
                max_val=1.2,
                step=0.1,
                unit="m",
            ),
            ParamDef(
                "滤头密度",
                "rho_head",
                value=55.0,
                default=55.0,
                min_val=48.0,
                max_val=56.0,
                step=1.0,
                unit="个/m²",
            ),
            ParamDef(
                "气冲强度 q_g1",
                "q_g1",
                value=15.0,
                default=15.0,
                min_val=12.0,
                max_val=18.0,
                step=0.5,
                unit="L/(m²·s)",
            ),
            ParamDef(
                "气冲强度 q_g2",
                "q_g2",
                value=15.0,
                default=15.0,
                min_val=12.0,
                max_val=18.0,
                step=0.5,
                unit="L/(m²·s)",
            ),
            ParamDef(
                "水冲强度 q_w3",
                "q_w3",
                value=5.0,
                default=5.0,
                min_val=3.0,
                max_val=8.0,
                step=0.5,
                unit="L/(m²·s)",
            ),
            ParamDef(
                "扫洗孔径 d_hole",
                "d_hole",
                value=0.025,
                default=0.025,
                min_val=0.020,
                max_val=0.030,
                step=0.001,
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
        # ── 基本参数 ──
        n = int(self.get_param("n"))
        v_filter = self.get_param("v_filter")  # m/h
        v_force = self.get_param("v_force")  # m/h
        T_filter = self.get_param("T_filter")  # h
        k_self = self.get_param("k_self")
        h_media = self.get_param("h_media")  # m
        h_water = self.get_param("h_water")  # m
        h_super = self.get_param("h_super")  # m
        h_plate = self.get_param("h_plate")  # m
        h_under = self.get_param("h_under")  # m
        rho_head = self.get_param("rho_head")  # 个/m²
        # 反冲洗参数
        q_g1 = self.get_param("q_g1")  # L/(m²·s)
        q_g2 = self.get_param("q_g2")  # L/(m²·s)
        q_w2 = self.get_param("q_w2")  # L/(m²·s)
        q_w3 = self.get_param("q_w3")  # L/(m²·s)
        q_s = self.get_param("q_s")  # L/(m²·s)
        t_g1 = self.get_param("t_g1")  # min
        t_gw = self.get_param("t_gw")  # min
        t_w3 = self.get_param("t_w3")  # min
        # 管路流速
        v_g_pipe = self.get_param("v_g_pipe")  # m/s
        v_w_pipe = self.get_param("v_w_pipe")  # m/s
        v_out_pipe = self.get_param("v_out_pipe")  # m/s
        # V型槽扫洗孔
        d_hole = self.get_param("d_hole")  # m
        v_hole = self.get_param("v_hole")  # m/s

        result = NodeResult(success=True)
        result.params = {
            "n": n,
            "v_filter": v_filter,
            "v_force": v_force,
            "T_filter": T_filter,
            "k_self": k_self,
            "h_media": h_media,
            "h_water": h_water,
            "h_super": h_super,
            "h_plate": h_plate,
            "h_under": h_under,
            "rho_head": rho_head,
            "q_g1": q_g1,
            "q_g2": q_g2,
            "q_w2": q_w2,
            "q_w3": q_w3,
            "q_s": q_s,
            "t_g1": t_g1,
            "t_gw": t_gw,
            "t_w3": t_w3,
            "v_g_pipe": v_g_pipe,
            "v_w_pipe": v_w_pipe,
            "v_out_pipe": v_out_pipe,
            "d_hole": d_hole,
            "v_hole": v_hole,
        }

        # ── trivial scalars ──
        Q_d = flow.Q_avg_daily * k_self
        t_bw = t_g1 + t_gw + t_w3
        T_w = 24.0 - 24.0 * (t_bw / 60.0) / T_filter

        # ── delegate to vectorized engine ──
        grid = {
            "n": np.array([n]),
            "v_filter": np.array([v_filter]),
            "h_media": np.array([h_media]),
            "h_water": np.array([h_water]),
        }
        fixed = {
            "v_force": v_force, "k_self": k_self,
            "h_super": h_super, "h_plate": h_plate, "h_under": h_under,
            "rho_head": rho_head, "T_filter": T_filter,
            "q_g1": q_g1, "q_g2": q_g2,
            "q_w2": q_w2, "q_w3": q_w3, "q_s": q_s,
            "t_g1": t_g1, "t_gw": t_gw, "t_w3": t_w3,
            "v_g_pipe": v_g_pipe, "v_w_pipe": v_w_pipe, "v_out_pipe": v_out_pipe,
            "d_hole": d_hole, "v_hole": v_hole,
        }
        arr = self.__class__._vectorized_compute(grid, flow, quality, fixed)
        r = arr[0]

        # ═══════════════════════════════════════════════
        # (1) 设计总流量 — 公式(4-95)
        # ═══════════════════════════════════════════════
        result.add_dimension(
            "设计总流量 Q_d",
            round(Q_d, 0),
            "m³/d",
            formula="Q_d = α × Q, α=1.05",
            category="computed",
        )

        # ═══════════════════════════════════════════════
        # (2) 反冲洗历时 + 有效工作时间 — 公式(4-96)(4-97)
        # ═══════════════════════════════════════════════
        result.add_dimension(
            "反冲洗总历时 t",
            round(t_bw, 1),
            "min",
            formula="t = t_g1 + t_gw + t_w3",
            category="computed",
        )
        result.add_dimension(
            "日有效工作时间 T_w",
            round(T_w, 1),
            "h/d",
            formula="T_w = 24 - 24×t/T_f",
            category="computed",
        )

        # ═══════════════════════════════════════════════
        # (3) 滤池总过滤面积 — 公式(4-98)
        # ═══════════════════════════════════════════════
        result.add_dimension(
            "总过滤面积 F",
            round(r["F_total"], 1),
            "m²",
            formula="F = Q_d / (v × T_w)",
            category="physical",
        )

        # ═══════════════════════════════════════════════
        # (4) 单格面积 + 强制滤速 — 公式(4-99)(4-100)
        # ═══════════════════════════════════════════════
        result.add_dimension(
            "单格过滤面积 f",
            round(r["f_single"], 1),
            "m²",
            formula="f = F / N",
            category="physical",
        )
        result.add_dimension(
            "设计滤速 v",
            v_filter,
            "m/h",
            formula="v = 设计取值 (5~8 m/h)",
            category="computed",
        )
        v_force_val = r["v_force_actual"]
        result.add_dimension(
            "实际强制滤速 v_q",
            round(v_force_val, 2),
            "m/h",
            formula="v_q = N/(N-1) × v",
            category="computed",
        )
        result.add_check(
            "强制滤速 v_q ≤ 限值",
            bool(r["ok_force"]),
            round(v_force_val, 2),
            f"≤ {v_force}",
            "m/h",
        )

        # ═══════════════════════════════════════════════
        # (5) 单格尺寸 — B ≤ 5m
        # ═══════════════════════════════════════════════
        result.add_dimension(
            "单格长度 L", r["L"], "m", formula="L = ceil(f / B, 0.1m)", category="physical"
        )
        result.add_dimension(
            "单格宽度 B",
            r["B"],
            "m",
            formula="B = min(ceil(√(f/2), 0.1m), 4.5m)",
            category="physical",
        )
        result.add_check("单格宽度 B ≤ 5m", bool(r["ok_B"]), round(r["B"], 2), "≤ 5.0", "m")
        LB_ratio_val = r["L"] / r["B"] if r["B"] > 0 else 0
        result.add_check(
            "长宽比 L/B 1~3", bool(r["ok_LB"]), round(LB_ratio_val, 2), "1~3", ""
        )

        # ═══════════════════════════════════════════════
        # (6) 总高度 — 公式(4-101)
        # ═══════════════════════════════════════════════
        H_rounded = math.ceil(r["H_total"] / 0.1) * 0.1
        result.add_dimension(
            "滤池总高度 H_t",
            H_rounded,
            "m",
            formula="H_t = h_free+h_water+h_filter+h_plate+h_under",
            category="physical",
        )

        # ═══════════════════════════════════════════════
        # (7) 反冲洗系统 — 公式(4-102)~(4-112)
        # ═══════════════════════════════════════════════
        result.add_dimension(
            "气冲流量 Q_g1",
            round(r["Q_g1"], 1),
            "L/s",
            formula="Q_g1 = q_g1 × f",
            category="computed",
        )
        result.add_dimension(
            "气冲流量 Q_g2",
            round(r["Q_g2"], 1),
            "L/s",
            formula="Q_g2 = q_g2 × f",
            category="computed",
        )
        result.add_dimension(
            "水冲流量 Q_w2",
            round(r["Q_w2"], 1),
            "L/s",
            formula="Q_w2 = q_w2 × f",
            category="computed",
        )
        result.add_dimension(
            "水冲流量 Q_w3",
            round(r["Q_w3"], 1),
            "L/s",
            formula="Q_w3 = q_w3 × f",
            category="computed",
        )
        result.add_dimension(
            "表扫流量 Q_s",
            round(r["Q_s"], 1),
            "L/s",
            formula="Q_s = q_s × f",
            category="computed",
        )

        result.add_dimension(
            "单次冲洗水量 W_w",
            round(r["W_w"], 1),
            "m³",
            formula="W_w = (Q_w2·t_gw+Q_w3·t_w3+Q_s·t)×60×10⁻³",
            category="computed",
        )

        eta_w_val = r["eta_w"]
        result.add_dimension(
            "冲洗水占比 η_w",
            round(eta_w_val * 100, 2),
            "%",
            formula="η_w = W_w×(24/T_f) / (Q_d/N)",
            category="computed",
        )
        result.add_check(
            "冲洗水占比 η_w < 5%", bool(r["ok_bw"]), round(eta_w_val * 100, 2), "< 5", "%"
        )

        result.add_dimension(
            "空气干管管径 D_g",
            round(r["D_g"] * 1000, 0),
            "mm",
            formula="D_g = √(4×Q_g1/1000/(π×v_g))",
            category="physical",
        )

        result.add_dimension(
            "水冲干管管径 D_w",
            round(r["D_w"] * 1000, 0),
            "mm",
            formula="D_w = √(4×max(Q_w2,Q_w3)/1000/(π×v_w))",
            category="physical",
        )

        result.add_dimension(
            "鼓风机风量 Q_blower",
            round(r["Q_blower"], 0),
            "m³/h",
            formula="Q_blower = Q_g1 × 3.6",
            category="computed",
        )

        result.add_dimension(
            "冲洗水泵流量 Q_pump",
            round(r["Q_pump"], 0),
            "m³/h",
            formula="Q_pump = max(Q_w3, Q_w2+Q_s) × 3.6",
            category="computed",
        )

        # ═══════════════════════════════════════════════
        # (8) 滤头布置 — 公式(4-113)
        # ═══════════════════════════════════════════════
        result.add_dimension(
            "滤头数量 N_nozzle",
            int(r["N_head"]),
            "个",
            formula="N_nozzle = n_nozzle × f",
            category="computed",
        )
        rho_val = r["val_rho"]
        result.add_check(
            "滤头密度 48~56 个/m²",
            bool(r["ok_rho"]),
            round(rho_val, 1),
            "48~56",
            "个/m²",
        )

        # ═══════════════════════════════════════════════
        # (9) V型槽始端流速校核 — 公式(4-115)
        # ═══════════════════════════════════════════════
        result.add_dimension(
            "V型槽断面积",
            round(r["A_v_slot"], 3),
            "m²",
            formula="A_V = (h_water-0.5) × 0.6",
            category="physical",
        )
        v_slot_val = r["v_v_slot"]
        result.add_dimension(
            "V型槽始端流速 v_V",
            round(v_slot_val, 2),
            "m/s",
            formula="v_V = Q_cell / (2×A_V槽)",
            category="computed",
        )
        result.add_check(
            "V型槽流速 ≤ 0.6 m/s", bool(r["ok_v_slot"]), round(v_slot_val, 2), "≤ 0.6", "m/s"
        )

        # ═══════════════════════════════════════════════
        # (9b) V型槽扫洗孔 — 公式(4-116)~(4-118)
        # ═══════════════════════════════════════════════
        result.add_dimension(
            "扫洗孔总面积 A_孔(单侧)",
            round(r["A_hole"], 4),
            "m²",
            formula="A_孔 = Q_s×10⁻³ / v_孔",
            category="physical",
        )
        result.add_dimension(
            "单孔面积 a_孔",
            round(r["a_hole"] * 1e6, 1),
            "mm²",
            formula="a_孔 = πd_孔²/4",
            category="computed",
        )
        n_hole_val = int(r["n_hole"])
        result.add_dimension(
            "每侧孔数 n_孔",
            n_hole_val,
            "个",
            formula="n_孔 = ceil(A_孔 / a_孔)",
            category="computed",
        )
        result.add_check("扫洗孔数 ≥ 20 个/侧", bool(r["ok_n_hole"]), n_hole_val, "≥ 20", "个/侧")

        # ═══════════════════════════════════════════════
        # (10) 滤后水出水管 — 公式(4-121)(4-122)
        # ═══════════════════════════════════════════════
        result.add_dimension(
            "出水管径 D_out",
            round(r["D_out"] * 1000, 0),
            "mm",
            formula="D_out = √(4×Q_filtered/(π×v_out))",
            category="physical",
        )

        # ═══════════════════════════════════════════════
        # (11) 过滤总水头损失 H_loss — 公式(4-123)
        # ═══════════════════════════════════════════════
        h_loss_val = r["H_loss"]
        result.add_dimension(
            "过滤总水头损失 H_loss",
            round(h_loss_val, 2),
            "m",
            formula="H_loss = h_filter(1.8m) + h_head(0.22m)",
            category="computed",
        )
        result.add_check(
            "过滤水头损失 2~3 m", bool(r["ok_H_loss"]), round(h_loss_val, 2), "2~3", "m"
        )

        # ── 汇总 ──
        result.add_dimension("滤池格数", n, "格")

        return result

    @classmethod
    def _vectorized_compute(
        cls, grid: dict, flow: "WaterFlow", quality: "WaterQuality", fixed: dict
    ) -> "np.ndarray":
        """向量化 V型滤池

        grid: n, v_filter, h_media, h_water
        fixed: v_force, T_filter, k_self, h_super, h_plate, h_under, rho_head,
               q_g1, q_g2, q_w2, q_w3, q_s, t_g1, t_gw, t_w3,
               v_g_pipe, v_w_pipe, v_out_pipe
        """
        n = grid["n"].astype(np.int32)
        v_filter = grid["v_filter"]
        h_media = grid["h_media"]
        h_water = grid["h_water"]
        v_force = fixed["v_force"]
        k_self = fixed["k_self"]
        h_super = fixed["h_super"]
        h_plate = fixed["h_plate"]
        h_under = fixed["h_under"]
        rho_head = fixed["rho_head"]
        T_filter = fixed["T_filter"]
        q_g1 = fixed.get("q_g1", 15.0)
        q_g2 = fixed.get("q_g2", 15.0)
        q_w2 = fixed.get("q_w2", 3.0)
        q_w3 = fixed.get("q_w3", 5.0)
        q_s = fixed.get("q_s", 2.0)
        t_g1 = fixed.get("t_g1", 3.0)
        t_gw = fixed.get("t_gw", 4.0)
        t_w3 = fixed.get("t_w3", 5.0)
        v_g_pipe = fixed.get("v_g_pipe", 12.0)
        v_w_pipe = fixed.get("v_w_pipe", 2.0)
        v_out_pipe = fixed.get("v_out_pipe", 1.0)
        d_hole = fixed.get("d_hole", 0.025)
        v_hole = fixed.get("v_hole", 2.0)
        N = len(n)
        PI_V = np.pi

        if flow.Q_avg_daily <= 0:
            dtype = np.dtype(
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
                    ("D_g", np.float64),
                    ("D_w", np.float64),
                    ("D_out", np.float64),
                    ("Q_blower", np.float64),
                    ("Q_pump", np.float64),
                    ("N_head", np.int32),
                    ("v_v_slot", np.float64),
                    ("H_loss", np.float64),
                    ("Q_g1", np.float64),
                    ("Q_g2", np.float64),
                    ("Q_w2", np.float64),
                    ("Q_w3", np.float64),
                    ("Q_s", np.float64),
                    ("A_v_slot", np.float64),
                    ("A_hole", np.float64),
                    ("a_hole", np.float64),
                    ("n_hole", np.int32),
                    ("H", np.float64),
                    ("concrete_m3", np.float64),
                    ("ok_force", np.bool_),
                    ("ok_bw", np.bool_),
                    ("ok_B", np.bool_),
                    ("ok_LB", np.bool_),
                    ("ok_rho", np.bool_),
                    ("ok_v_slot", np.bool_),
                    ("ok_H_loss", np.bool_),
                    ("ok_n_hole", np.bool_),
                    ("val_force", np.float64),
                    ("val_bw", np.float64),
                    ("val_B", np.float64),
                    ("val_LB", np.float64),
                    ("val_rho", np.float64),
                    ("val_v_slot", np.float64),
                    ("val_H_loss", np.float64),
                    ("val_n_hole", np.float64),
                ]
            )
            return np.zeros(N, dtype=dtype)

        Q_d = flow.Q_avg_daily * k_self  # m³/d

        # 反冲洗时间
        t_bw = t_g1 + t_gw + t_w3  # min
        t_bw_h = t_bw / 60.0
        T_w = 24.0 - 24.0 * t_bw_h / T_filter

        # 总过滤面积
        F_total = Q_d / (v_filter * T_w)
        f_single = F_total / n

        # 强制滤速
        v_force_actual = np.where(n > 1, n / (n - 1) * v_filter, np.inf)
        ok_force = v_force_actual <= v_force

        # 单格尺寸
        LB_ratio = 2.0
        B = np.minimum(np.ceil(np.sqrt(f_single / LB_ratio) / 0.1) * 0.1, 4.5)
        L = np.ceil(f_single / B / 0.1) * 0.1
        A_actual = L * B
        ok_B = B <= 5.0
        ok_LB = (1.0 <= L / B) & (L / B <= 3.0)

        # 总高度
        H_total = h_super + h_water + h_media + h_plate + h_under

        # 反冲洗
        Q_w2_val = q_w2 * A_actual
        Q_w3_val = q_w3 * A_actual
        Q_s_val = q_s * A_actual
        Q_g1_val = q_g1 * A_actual
        Q_g2_val = q_g2 * A_actual
        W_w = (
            Q_w2_val * t_gw * 60.0 + Q_w3_val * t_w3 * 60.0 + Q_s_val * t_bw * 60.0
        ) / 1000.0
        V_daily = Q_d / n
        eta_w = np.where(V_daily > 0, W_w * (24.0 / T_filter) / V_daily, 0.0)
        ok_bw = eta_w < 0.05

        # 管径
        D_g = np.sqrt(4.0 * Q_g1_val / 1000.0 / (PI_V * v_g_pipe))
        Q_w_max = np.maximum(Q_w2_val, Q_w3_val)
        D_w = np.sqrt(4.0 * Q_w_max / 1000.0 / (PI_V * v_w_pipe))

        # 设备
        Q_blower = Q_g1_val * 3.6
        Q_pump = np.maximum(Q_w3_val, Q_w2_val + Q_s_val) * 3.6

        # 滤头
        N_head = np.ceil(rho_head * A_actual).astype(np.int32)
        rho_actual = np.where(A_actual > 0, N_head / A_actual, 0.0)
        ok_rho = (48.0 <= rho_actual) & (rho_actual <= 56.0)

        # V型槽
        A_v_slot = (h_water - 0.5) * 0.6
        Q_cell = Q_d / n / 3600.0 / 24.0
        v_v_slot = np.where(A_v_slot > 0, Q_cell / (2.0 * A_v_slot), 0.0)
        ok_v_slot = v_v_slot <= 0.6

        # 扫洗孔 (4-116)~(4-118)
        Q_s_val = q_s * A_actual
        A_hole = np.where(v_hole > 0, Q_s_val * 1e-3 / v_hole, 0.0)
        a_hole = PI_V * d_hole**2 / 4.0
        n_hole = np.where(a_hole > 0, np.ceil(A_hole / a_hole), 0).astype(np.int32)
        ok_n_hole = n_hole >= 20

        # 出水管
        Q_filtered_m3s = Q_d / n / 24.0 / 3600.0
        D_out = np.sqrt(4.0 * Q_filtered_m3s / (PI_V * v_out_pipe))

        # 水头损失
        H_loss = np.full(N, 1.8 + 0.22)
        ok_H_loss = (2.0 <= H_loss) & (H_loss <= 3.0)

        concrete_m3 = L * B * H_total * n * 0.4

        dtype = np.dtype(
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
                ("D_g", np.float64),
                ("D_w", np.float64),
                ("D_out", np.float64),
                ("Q_blower", np.float64),
                ("Q_pump", np.float64),
                ("N_head", np.int32),
                ("v_v_slot", np.float64),
                ("H_loss", np.float64),
                ("Q_g1", np.float64),
                ("Q_g2", np.float64),
                ("Q_w2", np.float64),
                ("Q_w3", np.float64),
                ("Q_s", np.float64),
                ("A_v_slot", np.float64),
                ("A_hole", np.float64),
                ("a_hole", np.float64),
                ("n_hole", np.int32),
                ("H", np.float64),
                ("concrete_m3", np.float64),
                ("ok_force", np.bool_),
                ("ok_bw", np.bool_),
                ("ok_B", np.bool_),
                ("ok_LB", np.bool_),
                ("ok_rho", np.bool_),
                ("ok_v_slot", np.bool_),
                ("ok_H_loss", np.bool_),
                ("ok_n_hole", np.bool_),
                ("val_force", np.float64),
                ("val_bw", np.float64),
                ("val_B", np.float64),
                ("val_LB", np.float64),
                ("val_rho", np.float64),
                ("val_v_slot", np.float64),
                ("val_H_loss", np.float64),
                ("val_n_hole", np.float64),
            ]
        )
        arr = np.empty(N, dtype=dtype)
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
        arr["D_g"] = D_g
        arr["D_w"] = D_w
        arr["D_out"] = D_out
        arr["Q_blower"] = Q_blower
        arr["Q_pump"] = Q_pump
        arr["N_head"] = N_head
        arr["v_v_slot"] = v_v_slot
        arr["H_loss"] = H_loss
        arr["Q_g1"] = Q_g1_val
        arr["Q_g2"] = Q_g2_val
        arr["Q_w2"] = Q_w2_val
        arr["Q_w3"] = Q_w3_val
        arr["Q_s"] = Q_s_val
        arr["A_v_slot"] = A_v_slot
        arr["A_hole"] = A_hole
        arr["a_hole"] = a_hole
        arr["n_hole"] = n_hole
        arr["Q_blower"] = Q_blower
        arr["Q_pump"] = Q_pump
        arr["N_head"] = N_head
        arr["v_v_slot"] = v_v_slot
        arr["H_loss"] = H_loss
        arr["n_hole"] = n_hole
        arr["concrete_m3"] = concrete_m3
        arr["H"] = arr["H_total"]
        arr["ok_force"] = ok_force
        arr["ok_bw"] = ok_bw
        arr["ok_B"] = ok_B
        arr["ok_LB"] = ok_LB
        arr["ok_rho"] = ok_rho
        arr["ok_v_slot"] = ok_v_slot
        arr["ok_H_loss"] = ok_H_loss
        arr["ok_n_hole"] = ok_n_hole
        arr["val_force"] = v_force_actual
        arr["val_bw"] = eta_w
        arr["val_B"] = B
        arr["val_LB"] = L / B
        arr["val_rho"] = rho_actual
        arr["val_v_slot"] = v_v_slot
        arr["val_H_loss"] = H_loss
        arr["val_n_hole"] = n_hole.astype(np.float64)
        arr["val_LB"] = L / B
        arr["val_rho"] = rho_actual
        arr["val_v_slot"] = v_v_slot
        arr["val_H_loss"] = H_loss
        return arr
