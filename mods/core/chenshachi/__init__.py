"""chenshachi.py — 旋流沉砂池 (Vortex Grit Chamber)"""

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
    Port,
    PortType,
    PI,
)


class ChenshachiNode(NodeBase):
    """旋流沉砂池 (钟氏沉砂池)

    公式来源: 中期报告 §3.3 (3-21)~(3-29)
    """

    NODE_TYPE = "chenshachi"
    NODE_NAME = "旋流沉砂池"
    NODE_CATEGORY = "一级处理"

    def _init_ports(self) -> None:
        """沉砂池: MIXED进水 → MIXED出水 + SLUDGE沉砂"""
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
                port_id=f"{self.node_id}-grit",
                name="沉砂",
                port_type=PortType.SLUDGE,
                direction="output",
                node_id=self.node_id,
            ),
        ]

    @classmethod
    def _default_params(cls) -> Dict[str, float]:
        return {
            "n": 2,
            "q_surf": 180,
            "t": 45,
            "h1": 0.3,
            "X": 30,
            "T_clean": 2,
            "theta": 55,
            "dr": 0.5,
            "B_channel": 0.8,
            "v_channel": 1.0,
        }

    def _build_param_defs(self) -> List[ParamDef]:
        return [
            ParamDef(
                "池数", "n", value=2, default=2, min_val=2, max_val=4, step=1, unit="座"
            ),
            ParamDef(
                "表面负荷 q",
                "q_surf",
                value=180,
                default=180,
                min_val=150,
                max_val=200,
                step=10,
                unit="m³/(m²·h)",
            ),
            ParamDef(
                "停留时间 t",
                "t",
                value=45,
                default=45,
                min_val=25,
                max_val=60,
                step=5,
                unit="s",
            ),
            ParamDef(
                "超高 h1",
                "h1",
                value=0.3,
                default=0.3,
                min_val=0.3,
                max_val=0.5,
                step=0.1,
                unit="m",
            ),
            ParamDef(
                "砂斗倾角",
                "theta",
                value=55,
                default=55,
                min_val=55,
                max_val=60,
                step=1,
                unit="°",
            ),
            ParamDef(
                "排沙口直径 dr",
                "dr",
                value=0.5,
                default=0.5,
                min_val=0.4,
                max_val=0.6,
                step=0.05,
                unit="m",
            ),
            ParamDef(
                "清砂间隔 T",
                "T_clean",
                value=2,
                default=2,
                min_val=1,
                max_val=3,
                step=1,
                unit="d",
            ),
            ParamDef(
                "进水渠宽",
                "B_channel",
                value=0.8,
                default=0.8,
                min_val=0.5,
                max_val=2.0,
                step=0.1,
                unit="m",
                description="进水渠道宽度",
            ),
            ParamDef(
                "进水流速",
                "v_channel",
                value=1.0,
                default=1.0,
                min_val=0.6,
                max_val=1.2,
                step=0.1,
                unit="m/s",
                description="进水渠道设计流速",
            ),
        ]

    @classmethod
    def _default_removal_rates(cls) -> Dict[str, float]:
        return {
            "SS": 0.10,
            "BOD5": 0.05,
            "COD": 0.05,
            "NH3N": 0.0,
            "TN": 0.0,
            "TP": 0.0,
        }

    def calculate(self, flow: WaterFlow, quality: WaterQuality) -> NodeResult:
        n = int(self.get_param("n"))
        q_surf = self.get_param("q_surf")
        t = self.get_param("t")
        h1 = self.get_param("h1")
        X = self.get_param("X")
        T_clean = self.get_param("T_clean")
        theta = self.get_param("theta")
        dr = self.get_param("dr")
        B_channel = self.get_param("B_channel")
        v_channel = self.get_param("v_channel")

        result = NodeResult(success=True)
        result.params = {
            "n": n,
            "q_surf": q_surf,
            "t": t,
            "h1": h1,
            "X": X,
            "T_clean": T_clean,
            "theta": theta,
            "dr": dr,
            "B_channel": B_channel,
            "v_channel": v_channel,
        }

        # ── (1) 单池流量 ──
        Q_single = flow.Q_design / n
        Q_single_m3h = Q_single * 3600

        # ── (2) 直径 (3-21) ──
        D_theory = math.sqrt(4 * Q_single_m3h / (PI * q_surf))
        D = math.ceil(D_theory / 0.1) * 0.1

        # ── (3) 有效水深 (3-22) ──
        h2 = q_surf * t / 3600.0

        # ── 校核有效水深 h2 (旋流沉砂池: 1.0~2.0m) ──
        result.add_check("有效水深 h2", 1.0 <= h2 <= 2.0, round(h2, 2), "1.0~2.0", "m")

        # ── 校核 D/h2 (旋流沉砂池: 2.0~2.5) ──
        ratio_Dh2 = D / h2 if h2 > 0 else 0
        result.add_check(
            "径深比 D/h2", 2.0 <= ratio_Dh2 <= 2.5, round(ratio_Dh2, 2), "2.0~2.5", ""
        )

        # ── (4) 有效容积 (3-23) — 基于实际取整后尺寸 ──
        V_eff = PI * (D / 2) ** 2 * h2
        t_actual = V_eff / Q_single if Q_single > 0 else 0
        result.add_check(
            "停留时间 t", 25 <= t_actual <= 60, round(t_actual, 1), "25~60", "s"
        )

        # ── (5) 每日沉砂量 (3-24) — 单池 ──
        V_sand_daily = (flow.Q_avg_daily / n) * X / 1e6  # m³/d

        # ── (6) 砂斗所需容积 (3-25) — 单池 ──
        V_hopper = V_sand_daily * T_clean * 1.5

        # ── (7) 砂斗上口直径 (3-26) ──
        d_upper = 0.5 * D

        # ── (8) 锥体高度 (3-27) ──
        h4 = (d_upper - dr) / (2 * math.tan(math.radians(theta)))

        # ── (9) 锥体容积 ──
        V_cone = (
            PI
            * h4
            / 3
            * ((d_upper / 2) ** 2 + (d_upper / 2) * (dr / 2) + (dr / 2) ** 2)
        )

        # ── 圆柱段 (3-28)(3-29): 锥体不足时补圆柱,h_cyl 向上取整 ──
        V_cyl = 0.0
        if V_cone < V_hopper:
            h_cyl_exact = (V_hopper - V_cone) / (PI * (d_upper / 2) ** 2)
            h_cyl = math.ceil(h_cyl_exact / 0.1) * 0.1
            V_cyl = PI * (d_upper / 2) ** 2 * h_cyl
        else:
            h_cyl = 0.0
            V_cyl = 0.0

        # 总储砂容积 = 锥体 + 圆柱段(取整后 > V_hopper)
        V_storage = V_cone + V_cyl

        # ── 缓冲层 ──
        h3 = 0.5

        # ── 总高度 ──
        H_total = h1 + h2 + h3 + h4 + h_cyl
        H_rounded = math.ceil(H_total / 0.1) * 0.1

        # ── (10) 进水渠道设计 (4-26)(4-27)(4-28) ──
        A_channel = Q_single / v_channel if v_channel > 0 else 0
        h_channel = A_channel / B_channel if B_channel > 0 else 0
        L_straight = max(7 * B_channel, 4.5)

        result.add_check(
            "进水渠水深 h渠 ≥ 0.2", h_channel >= 0.2, round(h_channel, 3), "≥ 0.2", "m"
        )
        result.add_check(
            "进水渠宽深比 B/h",
            1.0 <= B_channel / h_channel <= 3.0 if h_channel > 0 else False,
            round(B_channel / h_channel, 2) if h_channel > 0 else float("inf"),
            "1.0~3.0",
            "",
        )

        # ── (11) 出水渠道 (4-29) ──
        B_out = 2 * B_channel

        # ── 组装结果 ──
        result.add_dimension("池数", n, "座", formula="n = 用户设定 (≥2)")
        result.add_dimension(
            "池径 D", D, "m", formula="D = √(4×Q₁/(π×q_surf)), 取整到0.1m (3-21)"
        )
        result.add_dimension(
            "有效水深 h2", round(h2, 2), "m", formula="h2 = q_surf × t / 3600 (3-22)"
        )
        result.add_dimension(
            "径深比", round(ratio_Dh2, 2), "", formula="D/h₂ = 池径 / 有效水深"
        )
        result.add_dimension(
            "有效容积",
            round(V_eff, 2),
            "m³",
            formula="V_eff = π×(D/2)²×h2 (基于取整尺寸)",
        )
        result.add_dimension(
            "实际停留时间", round(t_actual, 1), "s", formula="t_actual = V_eff / Q₁"
        )
        result.add_dimension(
            "每日沉砂量",
            round(V_sand_daily, 4),
            "m³/d",
            formula="V_sand = (Q_avg/n)×X/10⁶ (3-24)",
        )
        result.add_dimension(
            "砂斗上口直径", round(d_upper, 2), "m", formula="d_upper = 0.5×D"
        )
        result.add_dimension(
            "锥体高度 h4",
            round(h4, 2),
            "m",
            formula="h₄ = (d_upper−dr)/(2×tanθ) (3-27)",
        )
        result.add_dimension(
            "圆柱段高度",
            round(h_cyl, 2),
            "m",
            formula="h_cyl = ceil((V_hopper−V_cone)/A_upper, 0.1)",
        )
        result.add_dimension(
            "总高度 H", H_rounded, "m", formula="H = h1 + h2 + h3 + h4 + h_cyl"
        )
        result.add_dimension(
            "进水流速 v渠", v_channel, "m/s", formula="v渠 = 设计规范推荐 1.0 m/s"
        )
        result.add_dimension(
            "进水渠宽 B渠", B_channel, "m", formula="B渠 = 用户设定 (0.5~2.0m)"
        )
        result.add_dimension(
            "进水渠水深 h渠",
            round(h_channel, 3),
            "m",
            formula="h渠 = A渠/B渠 = Q₁/(v渠×B渠) (4-27)",
        )
        result.add_dimension(
            "进水渠断面 A渠", round(A_channel, 3), "m²", formula="A渠 = Q₁/v渠 (4-26)"
        )
        result.add_dimension(
            "进水直段长度 L直",
            round(L_straight, 2),
            "m",
            formula="L直 = max(7×B渠, 4.5) (4-28)",
        )
        result.add_dimension("出水渠宽 B出", B_out, "m", formula="B出 = 2×B渠 (4-29)")
        result.add_dimension(
            "砂斗所需容积",
            round(V_hopper, 3),
            "m³",
            formula="V_hopper = V_sand×T_clean×1.5 (3-25)",
        )
        result.add_dimension(
            "锥体实际容积",
            round(V_cone, 3),
            "m³",
            formula="V_cone = πh₄/3(R²+Rr+r²) (圆台)",
        )
        result.add_dimension(
            "圆柱储砂容积", round(V_cyl, 3), "m³", formula="V_cyl = π(d_upper/2)²×h_cyl"
        )
        result.add_dimension(
            "砂斗总容积",
            round(V_storage, 3),
            "m³",
            formula="V_storage = V_cone + V_cyl (取整后)",
        )

        # ── 沉砂输出 (SLUDGE 端口) — 汇总 n 池总量 ──
        # 沉砂含水率 ~60%, 无机质为主 (VS~5%), 湿密度~1600kg/m³
        P_grit = 0.60
        DS_grit = V_sand_daily * (1 - P_grit) * 1600.0  # kg/d (单池)
        self._sludge_output = SludgeFlow(
            Q_wet=V_sand_daily * n,
            DS=DS_grit * n,
            P_moisture=P_grit,
            VS_ratio=0.05,
        )

        return result

    @classmethod
    def _vectorized_compute(
        cls, grid: dict, flow: "WaterFlow", quality: "WaterQuality", fixed: dict
    ) -> "np.ndarray":
        """向量化旋流沉砂池计算

        grid: n, q_surf, t
        fixed: h1, X, T_clean, theta, dr
        """
        n = grid["n"].astype(np.int32)
        q_surf = grid["q_surf"]
        t = grid["t"]
        h1 = fixed["h1"]
        X = fixed["X"]
        T_clean = fixed["T_clean"]
        theta_deg = fixed["theta"]
        dr = fixed["dr"]
        N = len(n)
        PI_V = np.pi

        Q_single = flow.Q_design / n
        Q_single_m3h = Q_single * 3600

        # 直径
        D_theory = np.sqrt(4 * Q_single_m3h / (PI_V * q_surf))
        D = np.ceil(D_theory / 0.1) * 0.1

        # 有效水深
        h2 = q_surf * t / 3600.0

        # 有效水深 h2 校核 (1.0~2.0m)
        ok_h2 = (1.0 <= h2) & (h2 <= 2.0)

        # 径深比 (旋流沉砂池: 2.0~2.5)
        ratio_Dh2 = np.where(h2 > 0, D / h2, 0.0)
        ok_ratio = (2.0 <= ratio_Dh2) & (ratio_Dh2 <= 2.5)

        # 有效容积 — 基于实际取整后尺寸
        V_eff = PI_V * (D / 2) ** 2 * h2
        t_actual = np.where(Q_single > 0, V_eff / Q_single, 0.0)
        ok_t = (25 <= t_actual) & (t_actual <= 60)

        # 每日沉砂量 — 单池
        V_sand_daily = (flow.Q_avg_daily / n) * X / 1e6
        V_hopper = V_sand_daily * T_clean * 1.5
        d_upper = 0.5 * D
        h4 = (d_upper - dr) / (2 * np.tan(np.radians(theta_deg)))
        V_cone = (
            PI_V
            * h4
            / 3
            * ((d_upper / 2) ** 2 + (d_upper / 2) * (dr / 2) + (dr / 2) ** 2)
        )
        h_cyl_exact = np.where(
            V_cone < V_hopper, (V_hopper - V_cone) / (PI_V * (d_upper / 2) ** 2), 0.0
        )
        h_cyl = np.ceil(h_cyl_exact / 0.1) * 0.1  # 向上取整到0.1m
        V_cyl = PI_V * (d_upper / 2) ** 2 * h_cyl  # 圆柱段容积
        V_storage = V_cone + V_cyl  # 总储砂容积(取整后 > V_hopper)

        h3_buf = 0.5
        H_total = h1 + h2 + h3_buf + h4 + h_cyl

        # 进水渠道设计
        B_channel = fixed.get("B_channel", 0.8)
        v_channel = fixed.get("v_channel", 1.0)
        A_channel = np.where(v_channel > 0, Q_single / v_channel, 0.0)
        h_channel = np.where(B_channel > 0, A_channel / B_channel, 0.0)
        L_straight = np.maximum(7 * B_channel, 4.5)
        B_out = 2 * B_channel

        # 渠道约束校核
        ok_channel_depth = h_channel >= 0.2
        ok_channel_Bh = np.where(
            h_channel > 0,
            (1.0 <= B_channel / h_channel) & (B_channel / h_channel <= 3.0),
            False,
        )

        # 成本字段
        concrete_m3 = PI_V * (D / 2) ** 2 * H_total * n * 0.4

        dtype = np.dtype(
            [
                ("D", np.float64),
                ("h2", np.float64),
                ("ratio_Dh2", np.float64),
                ("V_eff", np.float64),
                ("t_actual", np.float64),
                ("V_sand_daily", np.float64),
                ("V_hopper", np.float64),
                ("d_upper", np.float64),
                ("h4", np.float64),
                ("h_cyl", np.float64),
                ("H_total", np.float64),
                ("V_cone", np.float64),
                ("V_storage", np.float64),
                ("A_channel", np.float64),
                ("h_channel", np.float64),
                ("L_straight", np.float64),
                ("B_out", np.float64),
                ("H", np.float64),
                ("concrete_m3", np.float64),
                ("ok_Dh2", np.bool_),
                ("ok_h2", np.bool_),
                ("ok_t", np.bool_),
                ("ok_channel_depth", np.bool_),
                ("ok_channel_Bh", np.bool_),
                ("val_Dh2", np.float64),
                ("val_h2", np.float64),
                ("val_t", np.float64),
                ("val_channel_depth", np.float64),
                ("val_channel_Bh", np.float64),
            ]
        )
        result = np.empty(N, dtype=dtype)
        result["D"] = D
        result["h2"] = h2
        result["ratio_Dh2"] = ratio_Dh2
        result["V_eff"] = V_eff
        result["t_actual"] = t_actual
        result["V_sand_daily"] = V_sand_daily
        result["V_hopper"] = V_hopper
        result["d_upper"] = d_upper
        result["h4"] = h4
        result["h_cyl"] = h_cyl
        result["H_total"] = H_total
        result["V_cone"] = V_cone
        result["V_storage"] = V_storage
        result["A_channel"] = A_channel
        result["h_channel"] = h_channel
        result["L_straight"] = L_straight
        result["B_out"] = B_out
        result["concrete_m3"] = concrete_m3
        result["H"] = result["H_total"]  # standard field
        result["D"] = D  # standard field
        result["ok_Dh2"] = ok_ratio
        result["ok_h2"] = ok_h2
        result["ok_t"] = ok_t
        result["ok_channel_depth"] = ok_channel_depth
        result["ok_channel_Bh"] = ok_channel_Bh
        result["val_Dh2"] = ratio_Dh2
        result["val_h2"] = h2
        result["val_t"] = t_actual
        result["val_channel_depth"] = h_channel
        result["val_channel_Bh"] = np.where(h_channel > 0, B_channel / h_channel, 0)
        return result
