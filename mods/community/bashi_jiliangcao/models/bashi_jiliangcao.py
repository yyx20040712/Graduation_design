"""bashi_jiliangcao.py — 巴氏计量槽 (Parshall Flume)

设计依据: CJ/T3008.5-93《巴歇尔量水槽》、GB50014-2021
核心公式: Q = C × h_a^n  (自由出流, 淹没度 ≤ 0.6)
"""

import numpy as np
import math
from typing import Dict, List

from models.base import (
    NodeBase, NodeResult, WaterFlow, WaterQuality,
    ParamDef, Port, PortType, GRAVITY,
)


# ═══════════════════════════════════════════════════════
# 巴歇尔量水槽标准系数表 (Q = C × h_a^n, Q:m³/s, h_a:m)
# 数据来源: CJ/T3008.5-93 附录
# ═══════════════════════════════════════════════════════
_PARSHALL_TABLE: Dict[float, tuple] = {
    0.152: (0.381, 1.58),
    0.228: (0.535, 1.53),
    0.30:  (0.679, 1.521),
    0.45:  (1.038, 1.537),
    0.60:  (1.403, 1.548),
}
_STANDARD_B_VALUES = list(_PARSHALL_TABLE.keys())


class BashiJiliangcaoNode(NodeBase):
    """巴氏计量槽 — 明渠流量测量装置

    用于污水处理厂进出水流量计量.喉道收缩段使水流加速→临界流,
    通过上游水位 h_a 反算流量.自由出流条件: 淹没度 S = h_b/h_a ≤ 0.6.
    """

    NODE_TYPE = "bashi_jiliangcao"
    NODE_NAME = "巴氏计量槽"
    NODE_CATEGORY = "社区模组"

    # ── 默认参数 ──
    @classmethod
    def _default_params(cls) -> Dict[str, float]:
        return {"b": 0.30}

    # ── 参数定义 ──
    def _build_param_defs(self) -> List[ParamDef]:
        return [
            ParamDef("喉道宽度", "b", value=self.get_param("b"),
                     default=0.30, min_val=0.152, max_val=0.60, step=0.001,
                     unit="m",
                     description="标准喉宽: 0.152,0.228,0.30,0.45,0.60m.喉宽≈渠道宽1/3~1/2"),
        ]

    # ── 去除率 (仅计量,无处理) ──
    @classmethod
    def _default_removal_rates(cls) -> Dict[str, float]:
        return {"BOD5": 0.0, "COD": 0.0, "SS": 0.0,
                "NH3N": 0.0, "TN": 0.0, "TP": 0.0}

    # ── 端口 ──
    def _init_ports(self) -> None:
        self.input_ports = [
            Port(port_id=f"{self.node_id}-in", name="进水",
                 port_type=PortType.MIXED, direction="input", node_id=self.node_id),
        ]
        self.output_ports = [
            Port(port_id=f"{self.node_id}-out", name="出水",
                 port_type=PortType.MIXED, direction="output", node_id=self.node_id),
        ]

    # ═══════════════════════════════════════════════
    # 核心计算
    # ═══════════════════════════════════════════════

    def calculate(self, flow: WaterFlow, quality: WaterQuality) -> NodeResult:
        b = self.get_param("b")

        # ── 防护 ──
        if flow.Q_design <= 0:
            return NodeResult.failed("设计流量 Q_design 必须 > 0")
        if b not in _PARSHALL_TABLE:
            valid = ", ".join(str(v) for v in _STANDARD_B_VALUES)
            return NodeResult.failed(
                f"喉宽 b={b} 不是标准值.标准喉宽: {valid} m")

        Q = flow.Q_design  # m³/s

        # ── (A) 查表获取 C, n ──
        C, n_exp = _PARSHALL_TABLE[b]

        # ── (B) 上游水深: Q = C × h_a^n → h_a = (Q/C)^(1/n) ──
        h_a = (Q / C) ** (1.0 / n_exp)

        # ── (C) 渠道宽度 (喉宽 ≈ 渠道宽 × 1/3 ~ 1/2) ──
        B_channel = math.ceil(b * 3.0 / 0.1) * 0.1

        # ── (D) 下游水深 (自由出流极限: 淹没度 ≤ 0.6) ──
        h_b = h_a * 0.6
        S = h_b / h_a  # = 0.6 (自由出流极限)

        # ── (E) 行进流速 ──
        v_approach = Q / (B_channel * h_a)

        # ── (F) 弗劳德数 ──
        Fr = v_approach / (GRAVITY * h_a) ** 0.5

        # ── (G) 上下游直段长度 ──
        L_upstream = 10.0 * B_channel    # ≥10×B (淹没自由流, CJ/T3008.5)
        L_downstream = math.ceil(5.0 * B_channel / 0.5) * 0.5  # ≥5×B
        L_total = L_upstream + L_downstream

        # ── 组装结果 ──
        result = NodeResult(success=True, params=dict(self._params))

        result.add_dimension("喉道宽度 b", b, "m")
        result.add_dimension("流量系数 C", round(C, 4), "")
        result.add_dimension("指数 n", n_exp, "")
        result.add_dimension("上游水深 h_a", round(h_a, 3), "m")
        result.add_dimension("下游水深 h_b", round(h_b, 3), "m")
        result.add_dimension("淹没度 S", round(S, 3), "")
        result.add_dimension("渠道宽度", round(B_channel, 2), "m")
        result.add_dimension("行进流速", round(v_approach, 3), "m/s")
        result.add_dimension("弗劳德数 Fr", round(Fr, 3), "")
        result.add_dimension("上游直段长度", round(L_upstream, 1), "m")
        result.add_dimension("下游直段长度", round(L_downstream, 1), "m")
        result.add_dimension("渠道总长", round(L_total, 1), "m")
        result.add_dimension("设计流量", round(Q, 4), "m³/s")
        result.add_dimension("设计流量(L/s)", round(Q * 1000, 1), "L/s")

        # ── 约束校核 ──
        result.add_check("标准喉宽 b",
                         b in _PARSHALL_TABLE,
                         round(b, 3),
                         "∈{0.152,0.228,0.30,0.45,0.60} (CJ/T3008.5-93)", "m")
        result.add_check("弗劳德数 Fr",
                         Fr < 1.0,
                         round(Fr, 3),
                         "< 1.0 (亚临界流)", "")
        result.add_check("行进流速 v_approach",
                         0.3 <= v_approach <= 2.0,
                         round(v_approach, 3),
                         "0.3~2.0 m/s", "m/s")

        return result

    # ═══════════════════════════════════════════════
    # 向量化计算 (方案空间枚举)
    # ═══════════════════════════════════════════════

    @classmethod
    def _vectorized_compute(cls, grid: dict, flow: WaterFlow,
                            quality: WaterQuality, fixed: dict) -> "np.ndarray":
        N = len(next(iter(grid.values())))
        b_vals = grid["b"].astype(np.float64)

        Q = flow.Q_design

        # ── 预计算每个标准喉宽对应的 C, n (查表) ──
        # 5 个标准值: 0.152, 0.228, 0.30, 0.45, 0.60
        C_lookup = np.array([0.381, 0.535, 0.679, 1.038, 1.403], dtype=np.float64)
        n_lookup = np.array([1.58, 1.53, 1.521, 1.537, 1.548], dtype=np.float64)
        b_standard = np.array([0.152, 0.228, 0.30, 0.45, 0.60], dtype=np.float64)

        # 通过最近邻匹配每个方案对应的系数
        idx = np.abs(b_vals[:, None] - b_standard[None, :]).argmin(axis=1)
        C_arr = C_lookup[idx]
        n_arr = n_lookup[idx]
        b_matched = b_standard[idx]

        # ── 上游水深 ──
        h_a = (Q / C_arr) ** (1.0 / n_arr)

        # ── 渠道宽度 ──
        B_channel = np.ceil(b_matched * 3.0 / 0.1) * 0.1

        # ── 行进流速 ──
        v_approach = Q / (B_channel * h_a)

        # ── 弗劳德数 ──
        Fr = v_approach / np.sqrt(GRAVITY * h_a)

        # ── 上下游直段长度 ──
        L_upstream = 10.0 * B_channel
        L_total = L_upstream + np.ceil(B_channel * 5.0 / 0.5) * 0.5

        # ── 约束 (含容差) ──
        ok_b = np.abs(b_vals - b_matched) < 0.005  # 喉宽必须在标准值 ±5mm
        ok_Fr = Fr < 1.0
        ok_v = (v_approach >= 0.3) & (v_approach <= 2.0)

        # ── 组装向量化输出 ──
        dt = np.dtype([
            ("b", np.float64), ("C_coeff", np.float64), ("n_exp", np.float64),
            ("h_a", np.float64), ("B_channel", np.float64),
            ("v_approach", np.float64), ("L_upstream", np.float64),
            ("L_total", np.float64), ("Fr", np.float64),
            ("concrete_m3", np.float64),
            ("ok_b_standard", np.bool_), ("val_b_standard", np.float64),
            ("ok_Fr", np.bool_), ("val_Fr", np.float64),
            ("ok_v_approach", np.bool_), ("val_v_approach", np.float64),
        ])
        arr = np.zeros(N, dtype=dt)
        arr["b"] = b_vals
        arr["C_coeff"] = C_arr
        arr["n_exp"] = n_arr
        arr["h_a"] = h_a
        arr["B_channel"] = B_channel
        arr["v_approach"] = v_approach
        arr["L_upstream"] = L_upstream
        arr["L_total"] = L_total
        arr["Fr"] = Fr
        arr["concrete_m3"] = 0.0  # 明渠无混凝土结构
        arr["ok_b_standard"] = ok_b
        arr["val_b_standard"] = b_vals
        arr["ok_Fr"] = ok_Fr
        arr["val_Fr"] = Fr
        arr["ok_v_approach"] = ok_v
        arr["val_v_approach"] = v_approach
        return arr
