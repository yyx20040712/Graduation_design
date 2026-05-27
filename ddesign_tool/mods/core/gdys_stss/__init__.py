"""gdys_stss.py — 管道运输水头损失 (Pipe Head Loss)"""
from __future__ import annotations
import math
from typing import Dict, List, Tuple
import numpy as np
from models.base import (
    NodeBase, NodeResult, WaterFlow, WaterQuality,
    ParamDef, Port, PortType, GRAVITY,
)
from design_engine import DrainagePipeDesigner

_LOCAL_XI = 1.5  # 局部水头损失系数


class GdysStssNode(NodeBase):
    """管道运输水头损失 — 计算两构筑物间连接管渠的沿程+局部水头损失"""
    NODE_TYPE = "gdys_stss"
    NODE_NAME = "管道运输水头损失"
    NODE_CATEGORY = "高程模组"

    @classmethod
    def _default_params(cls) -> Dict[str, float]:
        return {"Q_manual": 0.57, "L_pipe": 50.0}

    def _build_param_defs(self) -> List[ParamDef]:
        return [
            ParamDef("设计流量", "Q_manual", value=0.57, default=0.57,
                     min_val=0.01, max_val=10.0, step=0.01, unit="m3/s"),
            ParamDef("管段长度", "L_pipe", value=50.0, default=50.0,
                     min_val=5.0, max_val=500.0, step=5.0, unit="m"),
        ]

    def _init_ports(self) -> None:
        self.input_ports = [
            Port(port_id=f"{self.node_id}-in", name="进水",
                 port_type=PortType.MIXED, direction="input", node_id=self.node_id),
        ]
        self.output_ports = [
            Port(port_id=f"{self.node_id}-out", name="出水",
                 port_type=PortType.MIXED, direction="output", node_id=self.node_id),
        ]

    @classmethod
    def _default_removal_rates(cls) -> Dict[str, float]:
        return {"SS": 0.0, "BOD5": 0.0, "COD": 0.0, "NH3N": 0.0, "TN": 0.0, "TP": 0.0}

    def calculate(self, flow: WaterFlow, quality: WaterQuality) -> NodeResult:
        Q_m3s = self.get_param("Q_manual")
        L = self.get_param("L_pipe")

        # DrainagePipeDesigner: Q in L/s, D in mm
        Q_Ls = Q_m3s * 1000.0
        designer = DrainagePipeDesigner(n=0.014, pipe_type="污水")
        rd = designer.design(Q_Ls, D_min=300, D_max=1000, D_step=100)

        if rd is None:
            return NodeResult.failed("无法设计满足要求的管道")

        DN_mm = rd["D"]          # mm
        DN = DN_mm / 1000.0      # m
        hD_ratio = rd["h_D"]     # 充满度
        i_slope = rd["slope"]    # 坡度
        v = rd["velocity"]       # m/s

        # 沿程水头损失: h_f = i × L
        h_f = i_slope * L
        # 局部水头损失: h_m = ξ × v²/(2g)
        h_m = _LOCAL_XI * v ** 2 / (2 * GRAVITY)
        h_total = h_f + h_m

        result = NodeResult(success=True)
        result.params = {"Q_manual": Q_m3s, "L_pipe": L}
        result.add_dimension("设计流量 Q", Q_m3s, "m3/s")
        result.add_dimension("管段长度 L", L, "m")
        result.add_dimension("管径 DN", DN_mm, "mm")
        result.add_dimension("设计流速 v", round(v, 2), "m/s")
        result.add_dimension("设计坡度 i", round(i_slope, 4), "")
        result.add_dimension("充满度 h/D", round(hD_ratio, 3), "")
        result.add_dimension("沿程水头损失 h_f", round(h_f, 3), "m")
        result.add_dimension("局部水头损失 h_m", round(h_m, 3), "m")
        result.add_dimension("总水头损失 h_total", round(h_total, 3), "m")
        result.add_check("总水头损失 ≤ 2.0m", h_total <= 2.0,
                         round(h_total, 3), "<= 2.0", "m")
        result.add_check("流速 0.6~1.5m/s", 0.6 <= v <= 1.5,
                         round(v, 2), "0.6~1.5", "m/s")
        result.add_check("充满度 ≤ GB50014限值",
                         hD_ratio <= 0.75, round(hD_ratio, 3), "<= 0.75", "")
        return result

    @classmethod
    def _vectorized_compute(cls, grid: dict, flow: WaterFlow,
                            quality: WaterQuality, fixed: dict) -> np.ndarray:
        Q_m3s = fixed.get("Q_manual", 0.57)
        L = grid["L_pipe"]
        N = len(L)
        Q_arr = np.full(N, Q_m3s, dtype=np.float64)

        DN_arr = np.zeros(N)
        v_arr = np.zeros(N)
        i_arr = np.zeros(N)
        hD_arr = np.zeros(N)
        h_f_arr = np.zeros(N)
        h_m_arr = np.zeros(N)
        h_total_arr = np.zeros(N)
        ok_total = np.zeros(N, dtype=bool)
        ok_v = np.zeros(N, dtype=bool)
        ok_fill = np.zeros(N, dtype=bool)

        designer = DrainagePipeDesigner(n=0.014, pipe_type="污水")
        for idx in range(N):
            Q_Ls = float(Q_arr[idx]) * 1000.0
            rd = designer.design(Q_Ls, D_min=300, D_max=1000, D_step=100)
            if rd is None:
                DN_arr[idx] = 0.3
                v_arr[idx] = 0.0
                i_arr[idx] = 0.0
                hD_arr[idx] = 0.0
                continue
            DN_arr[idx] = rd["D"] / 1000.0
            v_arr[idx] = rd["velocity"]
            i_arr[idx] = rd["slope"]
            hD_arr[idx] = rd["h_D"]
            h_f_arr[idx] = i_arr[idx] * float(L[idx])
            h_m_arr[idx] = _LOCAL_XI * v_arr[idx] ** 2 / (2 * GRAVITY)
            h_total_arr[idx] = h_f_arr[idx] + h_m_arr[idx]
            ok_total[idx] = h_total_arr[idx] <= 2.0
            ok_v[idx] = 0.6 <= v_arr[idx] <= 1.5
            ok_fill[idx] = hD_arr[idx] <= 0.75

        dtype = np.dtype([("DN", np.float64), ("v", np.float64), ("i", np.float64),
                          ("hD", np.float64), ("h_f", np.float64), ("h_m", np.float64),
                          ("h_total", np.float64),
                          ("H", np.float64), ("concrete_m3", np.float64),
                          ("ok_total", np.bool_), ("ok_v", np.bool_), ("ok_fill", np.bool_),
                          ("val_total", np.float64), ("val_v", np.float64), ("val_fill", np.float64)])
        result = np.empty(N, dtype=dtype)
        result["DN"] = DN_arr; result["v"] = v_arr; result["i"] = i_arr
        result["hD"] = hD_arr; result["h_f"] = h_f_arr; result["h_m"] = h_m_arr
        result["h_total"] = h_total_arr
        result["H"] = h_total_arr; result["concrete_m3"] = 0.0
        result["ok_total"] = ok_total; result["ok_v"] = ok_v; result["ok_fill"] = ok_fill
        result["val_total"] = h_total_arr; result["val_v"] = v_arr; result["val_fill"] = hD_arr
        return result
