"""wuni_shusong.py — 污泥输送泵站 (Sludge Collection & Pumping)"""

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


class WuniShusongNode(NodeBase):
    """污泥输送泵站 — 多股污泥汇集 + 泵送设计

    公式来源: GB50014-2021 §7.1, CJJ 131-2009
    """

    NODE_TYPE = "wuni_shusong"
    NODE_NAME = "污泥输送泵站"
    NODE_CATEGORY = "污泥处理"

    @classmethod
    def _default_params(cls) -> Dict[str, float]:
        return {
            "n_pumps": 2,
            "Q_pump": 20.0,
            "H_pump": 15.0,
            "v_pipe": 1.5,
            "L_pipe": 80.0,
        }

    def _build_param_defs(self) -> List[ParamDef]:
        return [
            ParamDef(
                "泵数量",
                "n_pumps",
                value=2,
                default=2,
                min_val=1,
                max_val=4,
                step=1,
                unit="台",
            ),
            ParamDef(
                "单泵流量",
                "Q_pump",
                value=20.0,
                default=20.0,
                min_val=5,
                max_val=100,
                step=5,
                unit="m³/h",
            ),
            ParamDef(
                "扬程",
                "H_pump",
                value=15.0,
                default=15.0,
                min_val=5,
                max_val=50,
                step=1,
                unit="m",
            ),
            ParamDef(
                "管道流速",
                "v_pipe",
                value=1.5,
                default=1.5,
                min_val=1.0,
                max_val=2.5,
                step=0.1,
                unit="m/s",
                description="污泥管道设计流速 (≥1.0m/s)",
            ),
            ParamDef(
                "出水管长度",
                "L_pipe",
                value=80.0,
                default=80.0,
                min_val=10.0,
                max_val=500.0,
                step=10.0,
                unit="m",
            ),
        ]

    @classmethod
    def _default_removal_rates(cls) -> Dict[str, float]:
        return {}

    def _init_ports(self) -> None:
        """单端口节点: 1×SLUDGE输入 → 1×SLUDGE输出"""
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
                name="污泥出",
                port_type=PortType.SLUDGE,
                direction="output",
                node_id=self.node_id,
            ),
        ]

    def calculate(self, flow, quality) -> NodeResult:
        """污泥节点不参与水处理线,由 execute_sludge() 处理"""
        return NodeResult(success=True)

    def execute_sludge(
        self, sludge: SludgeFlow
    ) -> Tuple[Optional[NodeResult], SludgeFlow]:
        """执行污泥汇集 + 泵站计算"""
        n_pumps = int(self.get_param("n_pumps"))
        Q_pump = self.get_param("Q_pump")
        H_pump = self.get_param("H_pump")
        v_pipe = self.get_param("v_pipe")
        L_pipe = self.get_param("L_pipe")

        result = NodeResult(success=True)
        result.params = {
            "n_pumps": n_pumps,
            "Q_pump": Q_pump,
            "H_pump": H_pump,
            "v_pipe": v_pipe,
            "L_pipe": L_pipe,
        }

        # ── 泵送能力校核 ──
        Q_total_pump = n_pumps * Q_pump  # m³/h
        Q_sludge_h = sludge.Q_wet_m3h  # m³/h
        capacity_ok = Q_total_pump >= Q_sludge_h * 0.9

        result.add_check(
            "泵送能力充足",
            capacity_ok,
            round(Q_total_pump - Q_sludge_h, 1),
            ">= 0",
            "m³/h",
        )

        # ── 管道直径 ──
        Q_pump_m3s = Q_pump / 3600.0
        D_theory = math.sqrt(4 * Q_pump_m3s / (PI * v_pipe))
        D_pipe = math.ceil(max(D_theory, 0.1) / 0.05) * 0.05
        D_actual = max(D_pipe, 0.1)

        result.add_check("管道流速合理", 1.0 <= v_pipe <= 2.5, v_pipe, "1.0~2.5", "m/s")

        # ── 出水管水头损失 (Manning公式) ──
        n_rough = 0.013
        R_hyd = D_actual / 4.0
        v_actual = Q_pump_m3s / (PI * D_actual**2 / 4.0) if D_actual > 0 else 0
        i_fric = (n_rough * v_actual / (R_hyd ** (2.0 / 3.0))) ** 2 if R_hyd > 0 else 0
        h_f = i_fric * L_pipe
        h_m = 1.5 * v_actual**2 / (2 * 9.81)
        h_loss_pipe = h_f + h_m
        result.add_dimension(
            "出水管沿程水损 h_f",
            round(h_f, 3),
            "m",
            formula="h_f = (n·v/R^(2/3))² × L",
            category="computed",
        )
        result.add_dimension(
            "出水管局部水损 h_m",
            round(h_m, 3),
            "m",
            formula="h_m = ξ·v²/(2g), ξ=1.5",
            category="computed",
        )
        result.add_dimension(
            "出水管总水损 h_loss",
            round(h_loss_pipe, 3),
            "m",
            formula="h_loss = h_f + h_m",
            category="computed",
        )
        result.add_check(
            "出水管水损 ≤ 扬程",
            h_loss_pipe <= H_pump,
            round(h_loss_pipe, 2),
            f"≤ {H_pump}",
            "m",
        )

        # ── 电机功率估算 ──
        eta_pump = 0.65  # 污泥泵效率
        P_motor = Q_pump_m3s * H_pump * 10.0 / eta_pump  # kW (近似)

        # ── 组装结果 ──
        result.add_dimension("泵台数", n_pumps, "台")
        result.add_dimension("单泵流量", Q_pump, "m³/h")
        result.add_dimension("总泵送能力", round(Q_total_pump, 1), "m³/h")
        result.add_dimension("扬程", H_pump, "m")
        result.add_dimension("管径", D_pipe, "m")
        result.add_dimension("管道流速", v_pipe, "m/s")
        result.add_dimension("电机功率", round(P_motor, 1), "kW")
        result.add_dimension("进泥湿泥量", round(sludge.Q_wet, 2), "m³/d")
        result.add_dimension("进泥干固量", round(sludge.DS, 1), "kg/d")
        result.add_dimension("进泥含水率", round(sludge.P_moisture, 3), "")

        # 透传 (汇集节点不改变污泥性质)
        self._sludge_output = sludge
        return result, sludge

    @classmethod
    def _vectorized_compute(cls, grid, flow, quality, fixed):
        """向量化输送泵站 — 批量校核泵送能力"""
        n_pumps = grid["n_pumps"].astype(np.int32)
        Q_pump = grid["Q_pump"]
        v_pipe = grid["v_pipe"]
        H_pump = fixed.get("H_pump", 15.0)
        Q_wet_in = fixed.get("_sludge_Q_wet", 100.0)
        N = len(n_pumps)
        PI_V = np.pi

        Q_total = n_pumps * Q_pump  # m³/h total capacity
        Q_sludge_h = Q_wet_in / 24.0  # m³/h incoming
        ok_capacity = Q_total >= Q_sludge_h * 0.9
        ok_v_pipe = (1.0 <= v_pipe) & (v_pipe <= 2.5)

        Q_pump_m3s = Q_pump / 3600.0
        D_theory = np.sqrt(4 * Q_pump_m3s / (PI_V * np.maximum(v_pipe, 0.1)))
        D_pipe = np.ceil(np.maximum(D_theory, 0.1) / 0.05) * 0.05
        D_actual = np.maximum(D_pipe, 0.1)

        # 出水管水头损失 (Manning)
        n_rough = 0.013
        L_pipe = fixed.get("L_pipe", 80.0)
        R_hyd = D_actual / 4.0
        v_actual = Q_pump_m3s / (PI_V * D_actual**2 / 4.0)
        i_fric = np.where(
            R_hyd > 0, (n_rough * v_actual / (R_hyd ** (2.0 / 3.0))) ** 2, 0.0
        )
        h_f = i_fric * L_pipe
        h_m = 1.5 * v_actual**2 / (2 * 9.81)
        h_loss_pipe = h_f + h_m
        ok_h_loss = h_loss_pipe <= H_pump

        P_motor = Q_pump_m3s * H_pump * 10.0 / 0.65

        dt = np.dtype(
            [
                ("n_pumps", np.float64),
                ("Q_pump", np.float64),
                ("Q_total", np.float64),
                ("D_pipe", np.float64),
                ("h_f", np.float64),
                ("h_m", np.float64),
                ("h_loss", np.float64),
                ("P_motor", np.float64),
                ("concrete_m3", np.float64),
                ("ok_capacity", np.bool_),
                ("ok_v_pipe", np.bool_),
                ("ok_h_loss", np.bool_),
                ("val_capacity", np.float64),
                ("val_v_pipe", np.float64),
                ("val_h_loss", np.float64),
            ]
        )
        arr = np.zeros(N, dtype=dt)
        arr["n_pumps"] = n_pumps
        arr["Q_pump"] = Q_pump
        arr["Q_total"] = Q_total
        arr["D_pipe"] = D_pipe
        arr["h_f"] = h_f
        arr["h_m"] = h_m
        arr["h_loss"] = h_loss_pipe
        arr["P_motor"] = P_motor
        arr["concrete_m3"] = n_pumps * 15.0
        arr["ok_capacity"] = ok_capacity
        arr["ok_v_pipe"] = ok_v_pipe
        arr["ok_h_loss"] = ok_h_loss
        arr["val_capacity"] = Q_total - Q_sludge_h
        arr["val_v_pipe"] = v_pipe
        arr["val_h_loss"] = h_loss_pipe
        return arr
