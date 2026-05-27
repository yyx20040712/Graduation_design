"""wuni_tisheng.py — 污水提升泵房 (Sewage Lift Pump Station)

设计依据: GB50014-2021 §6.2-§6.4
核心计算: 水泵选型、集水池容积、进出水管径、扬程计算 (曼宁公式水头损失)
"""

import math
import numpy as np
from typing import Dict, List

from models.base import (
    NodeBase, NodeResult, WaterFlow, WaterQuality,
    ParamDef, Port, PortType, PI, GRAVITY,
)


class WuniTishengNode(NodeBase):
    """污水提升泵房 — 污水提升 + 集水池 + 泵站设计

    将上游来水提升至设计高程,以满足后续重力流处理单元的水头需求.
    设计内容包括: 工作泵/备用泵台数、集水池容积、吸水管/出水管径、
    沿程+局部水头损失、总扬程、轴功率.
    """

    NODE_TYPE = "wuni_tisheng"
    NODE_NAME = "污水提升泵房"
    NODE_CATEGORY = "社区模组"

    # ── 默认参数 ──
    @classmethod
    def _default_params(cls) -> Dict[str, float]:
        return {
            "n_work": 3,
            "H_st": 5.0,
            "v_suction": 1.0,
            "v_discharge": 1.5,
            "L_suction": 10.0,
            "L_discharge": 50.0,
        }

    # ── 参数定义 ──
    def _build_param_defs(self) -> List[ParamDef]:
        return [
            ParamDef("工作泵台数", "n_work", value=self.get_param("n_work"),
                     default=3, min_val=2, max_val=8, step=1, unit="台",
                     description="GB50014 §6.4.1: 工作泵≥2台, ≤8台"),
            ParamDef("静扬程", "H_st", value=self.get_param("H_st"),
                     default=5.0, min_val=3.0, max_val=12.0, step=0.5, unit="m",
                     description="提升高度(静扬程)"),
            ParamDef("吸水管流速", "v_suction", value=self.get_param("v_suction"),
                     default=1.0, min_val=0.7, max_val=1.5, step=0.1, unit="m/s",
                     description="GB50014 §6.4.4: 吸水管 0.7~1.5 m/s"),
            ParamDef("出水管流速", "v_discharge", value=self.get_param("v_discharge"),
                     default=1.5, min_val=0.8, max_val=2.5, step=0.1, unit="m/s",
                     description="GB50014 §6.4.4: 出水管 0.8~2.5 m/s"),
            ParamDef("吸水管长度", "L_suction", value=self.get_param("L_suction"),
                     default=10.0, min_val=5.0, max_val=30.0, step=1.0, unit="m"),
            ParamDef("出水管长度", "L_discharge", value=self.get_param("L_discharge"),
                     default=50.0, min_val=10.0, max_val=200.0, step=5.0, unit="m"),
        ]

    # ── 去除率 (仅提升,无处理) ──
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
        n_work = int(self.get_param("n_work"))
        H_st = self.get_param("H_st")
        v_suction = self.get_param("v_suction")
        v_discharge = self.get_param("v_discharge")
        L_suction = self.get_param("L_suction")
        L_discharge = self.get_param("L_discharge")

        # ── 防护 ──
        if n_work <= 0:
            return NodeResult.failed("工作泵台数 n_work 必须 ≥ 1")
        if flow.Q_design <= 0:
            return NodeResult.failed("设计流量 Q_design 必须 > 0")

        # ── 固定设计常数 ──
        eta_pump = 0.75         # 水泵效率
        t_sump_min = 5.0        # 最小停留时间 min (§6.3.1)
        h_outlet = 1.5          # 出水自由水头 m
        h_super = 0.5           # 超高 m
        h_sump_eff = 2.5        # 集水池有效水深 m
        k_local = 1.2           # 局部水头损失放大系数
        n_rough = 0.014         # 混凝土管 Manning 粗糙系数 (GB50014)

        Q = flow.Q_design                     # m³/s
        Q_single = Q / n_work                 # 单泵设计流量 m³/s

        # ── (A) 管径计算 ──
        D_suction = math.sqrt(4 * Q_single / (PI * v_suction))
        D_discharge = math.sqrt(4 * Q_single / (PI * v_discharge))

        # ── (B) 曼宁公式水头损失 ──
        # v = (1/n) * R^(2/3) * i^(1/2) → i = (n*v / R^(2/3))^2
        # 满管流: R = D/4
        R_suction = D_suction / 4
        R_discharge = D_discharge / 4

        i_suction = (n_rough * v_suction / (R_suction ** (2.0 / 3.0))) ** 2
        i_discharge = (n_rough * v_discharge / (R_discharge ** (2.0 / 3.0))) ** 2

        h_f_suction = i_suction * L_suction
        h_f_discharge = i_discharge * L_discharge

        h_loss_suction = h_f_suction * k_local
        h_loss_discharge = h_f_discharge * k_local

        # ── (C) 总扬程 ──
        H_total = H_st + h_loss_suction + h_loss_discharge + h_outlet

        # ── (D) 水泵功率 (kW) ──
        P_shaft = 1000 * GRAVITY * Q_single * H_total / eta_pump / 1000

        # ── (E) 集水池容积 ──
        V_sump_min = Q_single * t_sump_min * 60    # m³
        A_sump = V_sump_min / h_sump_eff
        # 近似 2:1 长宽比 (4-142)(4-143)
        L_sump = math.ceil(max(math.sqrt(A_sump / 2.0), 2.0) / 0.5) * 0.5
        B_sump = math.ceil(A_sump / L_sump / 0.5) * 0.5
        V_sump_actual = L_sump * B_sump * h_sump_eff
        H_sump_total = h_sump_eff + h_super

        # ── (F) 备用泵 (§6.4.1) ──
        n_standby = 1 if n_work <= 4 else 2
        n_total = n_work + n_standby

        # ── 组装结果 ──
        result = NodeResult(success=True, params=dict(self._params))

        result.add_dimension("工作泵台数", n_work, "台")
        result.add_dimension("备用泵台数", n_standby, "台")
        result.add_dimension("水泵总台数", n_total, "台")
        result.add_dimension("单泵流量", round(Q_single, 4), "m³/s")
        result.add_dimension("吸水管径 D_suction", round(D_suction, 3), "m")
        result.add_dimension("出水管径 D_discharge", round(D_discharge, 3), "m")
        result.add_dimension("静扬程", H_st, "m")
        result.add_dimension("吸水管水力坡度 i_s", round(i_suction, 6), "",
                             formula="i = (n·v/R^(2/3))²",
                             category="computed")
        result.add_dimension("出水管水力坡度 i_d", round(i_discharge, 6), "",
                             formula="i = (n·v/R^(2/3))²",
                             category="computed")
        result.add_dimension("吸水管沿程水损 h_f,s", round(h_f_suction, 3), "m",
                             formula="h_f = i × L",
                             category="computed")
        result.add_dimension("出水管沿程水损 h_f,d", round(h_f_discharge, 3), "m",
                             formula="h_f = i × L",
                             category="computed")
        result.add_dimension("吸水管总水损(含局部)", round(h_loss_suction, 3), "m",
                             formula="h_loss = k_local × h_f, k=1.2",
                             category="computed")
        result.add_dimension("出水管总水损(含局部)", round(h_loss_discharge, 3), "m",
                             formula="h_loss = k_local × h_f, k=1.2",
                             category="computed")
        result.add_dimension("总扬程 H", round(H_total, 2), "m")
        result.add_dimension("轴功率", round(P_shaft, 1), "kW")
        result.add_dimension("池长 L", L_sump, "m")
        result.add_dimension("池宽 B", B_sump, "m")
        result.add_dimension("有效水深", h_sump_eff, "m")
        result.add_dimension("总高度 H", round(H_sump_total, 2), "m")
        result.add_dimension("集水池容积", round(V_sump_actual, 1), "m³")
        result.add_dimension("最小集水池容积", round(V_sump_min, 1), "m³")

        # ── 约束校核 ──
        result.add_check("吸水管流速 v_suction",
                         0.7 <= v_suction <= 1.5,
                         round(v_suction, 2),
                         "0.7~1.5 (GB50014 §6.4.4)", "m/s")
        result.add_check("出水管流速 v_discharge",
                         0.8 <= v_discharge <= 2.5,
                         round(v_discharge, 2),
                         "0.8~2.5 (GB50014 §6.4.4)", "m/s")
        result.add_check("总扬程 H_total",
                         5.0 <= H_total <= 30.0,
                         round(H_total, 1),
                         "5~30 m", "m")
        result.add_check("集水池容积 V_sump",
                         V_sump_actual >= V_sump_min,
                         round(V_sump_actual, 1),
                         f">= {round(V_sump_min, 1)} m³ (GB50014 §6.3.1)", "m³")

        return result

    # ═══════════════════════════════════════════════
    # 向量化计算 (方案空间枚举)
    # ═══════════════════════════════════════════════

    @classmethod
    def _vectorized_compute(cls, grid: dict, flow: WaterFlow,
                            quality: WaterQuality, fixed: dict) -> "np.ndarray":
        N = len(next(iter(grid.values())))

        n_work = grid["n_work"].astype(np.int32)
        H_st = grid["H_st"].astype(np.float64)
        v_suction = grid["v_suction"].astype(np.float64)
        v_discharge = grid["v_discharge"].astype(np.float64)

        Q = flow.Q_design
        Q_single = Q / n_work

        # 固定常数
        eta_pump = 0.75; t_sump_min = 5.0; h_outlet = 1.5
        h_super = 0.5; h_sump_eff = 2.5; k_local = 1.2
        n_rough = 0.014; L_suction = fixed.get("L_suction", 10.0); L_discharge = fixed.get("L_discharge", 50.0)

        # 管径
        D_suction = np.sqrt(4.0 * Q_single / (PI * v_suction))
        D_discharge = np.sqrt(4.0 * Q_single / (PI * v_discharge))

        # Manning 水头损失
        R_suction = D_suction / 4.0
        R_discharge = D_discharge / 4.0
        i_suction = (n_rough * v_suction / (R_suction ** (2.0 / 3.0))) ** 2
        i_discharge = (n_rough * v_discharge / (R_discharge ** (2.0 / 3.0))) ** 2
        h_f_suction = i_suction * L_suction
        h_f_discharge = i_discharge * L_discharge
        h_loss_suction = h_f_suction * k_local
        h_loss_discharge = h_f_discharge * k_local

        H_total = H_st + h_loss_suction + h_loss_discharge + h_outlet
        P_shaft = 1000.0 * GRAVITY * Q_single * H_total / eta_pump / 1000.0

        # 集水池
        V_sump_min = Q_single * t_sump_min * 60.0
        A_sump = V_sump_min / h_sump_eff
        L_sump = np.ceil(np.maximum(np.sqrt(A_sump / 2.0), 2.0) * 2) / 2  # ceil to 0.5
        B_sump = np.ceil(A_sump / L_sump * 2) / 2
        V_sump_actual = L_sump * B_sump * h_sump_eff
        H_sump_total = h_sump_eff + h_super

        n_standby = np.where(n_work <= 4, 1, 2)

        # 混凝土量 (泵房土建)
        concrete = (L_sump * B_sump * H_sump_total * 0.25) * n_work

        # 约束
        ok_v_suction = (v_suction >= 0.7) & (v_suction <= 1.5)
        ok_v_discharge = (v_discharge >= 0.8) & (v_discharge <= 2.5)
        ok_H_total = (H_total >= 5.0) & (H_total <= 30.0)
        ok_V_sump = V_sump_actual >= V_sump_min

        dt = np.dtype([
            ("D_suction", np.float64), ("D_discharge", np.float64),
            ("i_suction", np.float64), ("i_discharge", np.float64),
            ("h_f_suction", np.float64), ("h_f_discharge", np.float64),
            ("h_loss_suction", np.float64), ("h_loss_discharge", np.float64),
            ("H_total", np.float64), ("P_shaft", np.float64),
            ("L_sump", np.float64), ("B_sump", np.float64),
            ("H_sump_total", np.float64), ("V_sump_actual", np.float64),
            ("n_standby", np.int32), ("concrete_m3", np.float64),
            ("L", np.float64), ("B", np.float64), ("H", np.float64),
            ("ok_v_suction", np.bool_), ("val_v_suction", np.float64),
            ("ok_v_discharge", np.bool_), ("val_v_discharge", np.float64),
            ("ok_H_total_range", np.bool_), ("val_H_total_range", np.float64),
            ("ok_V_sump", np.bool_), ("val_V_sump", np.float64),
        ])
        arr = np.zeros(N, dtype=dt)
        arr["D_suction"] = D_suction
        arr["D_discharge"] = D_discharge
        arr["i_suction"] = i_suction; arr["i_discharge"] = i_discharge
        arr["h_f_suction"] = h_f_suction; arr["h_f_discharge"] = h_f_discharge
        arr["h_loss_suction"] = h_loss_suction
        arr["h_loss_discharge"] = h_loss_discharge
        arr["H_total"] = H_total
        arr["P_shaft"] = P_shaft
        arr["L_sump"] = L_sump
        arr["B_sump"] = B_sump
        arr["H_sump_total"] = H_sump_total
        arr["V_sump_actual"] = V_sump_actual
        arr["n_standby"] = n_standby
        arr["concrete_m3"] = concrete
        arr["L"] = arr["L_sump"]; arr["B"] = arr["B_sump"]; arr["H"] = arr["H_sump_total"]
        arr["ok_v_suction"] = ok_v_suction
        arr["val_v_suction"] = v_suction
        arr["ok_v_discharge"] = ok_v_discharge
        arr["val_v_discharge"] = v_discharge
        arr["ok_H_total_range"] = ok_H_total
        arr["val_H_total_range"] = H_total
        arr["ok_V_sump"] = ok_V_sump
        arr["val_V_sump"] = V_sump_actual
        return arr
