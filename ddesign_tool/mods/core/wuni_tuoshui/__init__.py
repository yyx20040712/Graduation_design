"""wuni_tuoshui.py — 污泥脱水间 (Sludge Dewatering)"""

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


class WuniTuoshuiNode(NodeBase):
    """污泥脱水间 — 带式压滤/离心脱水 + PAM投加

    公式来源: GB50014-2021 §7.4, CJJ 131-2009
    """

    NODE_TYPE = "wuni_tuoshui"
    NODE_NAME = "污泥脱水间"
    NODE_CATEGORY = "污泥处理"

    @classmethod
    def _default_params(cls) -> Dict[str, float]:
        return {
            "equip_type": 0,  # 0=belt, 1=centrifuge
            "q_capacity": 20.0,
            "n_machines": 2,
            "P_out": 0.78,
            "dosage_PAM": 4.0,
        }

    def _build_param_defs(self) -> List[ParamDef]:
        return [
            ParamDef(
                "设备类型(0=带式,1=离心)",
                "equip_type",
                value=0,
                default=0,
                min_val=0,
                max_val=1,
                step=1,
                unit="-",
            ),
            ParamDef(
                "单机处理量",
                "q_capacity",
                value=20.0,
                default=20.0,
                min_val=5,
                max_val=60,
                step=5,
                unit="m³/h",
            ),
            ParamDef(
                "脱水机台数",
                "n_machines",
                value=2,
                default=2,
                min_val=1,
                max_val=6,
                step=1,
                unit="台",
            ),
            ParamDef(
                "出泥含水率",
                "P_out",
                value=0.78,
                default=0.78,
                min_val=0.60,
                max_val=0.85,
                step=0.02,
                unit="-",
            ),
            ParamDef(
                "PAM投加量",
                "dosage_PAM",
                value=4.0,
                default=4.0,
                min_val=2,
                max_val=8,
                step=0.5,
                unit="g/kgDS",
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
                name="脱水污泥",
                port_type=PortType.SLUDGE,
                direction="output",
                node_id=self.node_id,
            ),
        ]

    def calculate(self, flow, quality) -> NodeResult:
        equip_type = int(self.get_param("equip_type"))
        q_capacity = self.get_param("q_capacity")
        n_machines = int(self.get_param("n_machines"))
        P_out = self.get_param("P_out")
        dosage_PAM = self.get_param("dosage_PAM")
        equip_name = "带式压滤机" if equip_type == 0 else "离心脱水机"

        grid, fixed = self._make_scalar_grid(
            {"equip_type": equip_type, "n_machines": n_machines,
             "q_capacity": q_capacity, "P_out": P_out},
            {"dosage_PAM": dosage_PAM, "_sludge_DS": 4000.0, "_sludge_Q_wet": 100.0},
        )
        res = self._vectorized_compute(grid, flow, quality, fixed)
        r = res[0]

        DS = 4000.0
        Q_wet_in = 100.0
        P_in = 0.96
        T_run_val = float(r["T_run"])
        Q_wet_out_val = float(r["Q_wet_out"])
        PAM_daily = float(r["PAM_daily"])
        PAM_solution = PAM_daily / 0.002 / 1000.0

        result = NodeResult(success=True)
        result.params = {
            "equip_type": equip_type, "q_capacity": q_capacity,
            "n_machines": n_machines, "P_out": P_out, "dosage_PAM": dosage_PAM,
        }
        result.add_dimension("设备类型", equip_name, "")
        result.add_dimension("脱水机台数", n_machines, "台")
        result.add_dimension("单机处理量", q_capacity, "m³/h")
        result.add_dimension("日运行时间", round(T_run_val, 1), "h/d")
        result.add_dimension("进泥湿泥量", round(Q_wet_in, 2), "m³/d")
        result.add_dimension("进泥含水率", round(P_in, 3), "")
        result.add_dimension("出泥湿泥量", round(Q_wet_out_val, 2), "m³/d")
        result.add_dimension("出泥含水率", P_out, "")
        result.add_dimension(
            "分离液量", round(max(0, Q_wet_in - Q_wet_out_val), 2), "m³/d",
        )
        result.add_dimension("干固体量", round(DS, 1), "kg/d")
        result.add_dimension("PAM日耗量", round(PAM_daily, 1), "kg/d")
        result.add_dimension("PAM溶液流量", round(PAM_solution, 2), "m³/d")
        result.add_dimension("固体回收率", 97.0, "%")
        result.add_check(
            "日运行时间 <= 20h", bool(r["ok_run_time"]),
            round(float(r["val_run_time"]), 1), "<= 20", "h/d",
        )
        return result

    def execute_sludge(
        self, sludge: SludgeFlow
    ) -> Tuple[Optional[NodeResult], SludgeFlow]:
        equip_type = int(self.get_param("equip_type"))
        q_capacity = self.get_param("q_capacity")
        n_machines = int(self.get_param("n_machines"))
        P_out = self.get_param("P_out")
        dosage_PAM = self.get_param("dosage_PAM")

        equip_name = "带式压滤机" if equip_type == 0 else "离心脱水机"

        result = NodeResult(success=True)
        result.params = {
            "equip_type": equip_type,
            "q_capacity": q_capacity,
            "n_machines": n_machines,
            "P_out": P_out,
            "dosage_PAM": dosage_PAM,
        }

        DS = sludge.DS
        Q_wet_in = sludge.Q_wet
        P_in = sludge.P_moisture

        # ── (A) 运行时间校核 ──
        Q_total_capacity = n_machines * q_capacity  # m³/h
        T_run = Q_wet_in / Q_total_capacity if Q_total_capacity > 0 else 24  # h/d
        result.add_check(
            "日运行时间 <= 20h", T_run <= 20, round(T_run, 1), "<= 20", "h/d"
        )

        # ── (B) 出泥量 ──
        if P_out < 1.0:
            Q_wet_out = DS / ((1 - P_out) * 1000.0)
        else:
            Q_wet_out = float("inf")

        # ── (C) 分离液量 ──
        Q_filtrate = max(0, Q_wet_in - Q_wet_out)

        # ── (D) PAM 投加量 ──
        PAM_daily = DS * dosage_PAM / 1000.0  # kg/d
        # PAM 溶液浓度 0.1%~0.3%
        PAM_conc = 0.002
        PAM_solution_flow = PAM_daily / PAM_conc / 1000.0  # m³/d

        # ── (E) 固体回收率 ──
        recovery = 0.97  # 脱水后固体回收率 ≥95%

        # ── 组装结果 ──
        result.add_dimension("设备类型", equip_name, "")
        result.add_dimension("脱水机台数", n_machines, "台")
        result.add_dimension("单机处理量", q_capacity, "m³/h")
        result.add_dimension("日运行时间", round(T_run, 1), "h/d")
        result.add_dimension("进泥湿泥量", round(Q_wet_in, 2), "m³/d")
        result.add_dimension("进泥含水率", round(P_in, 3), "")
        result.add_dimension("出泥湿泥量", round(Q_wet_out, 2), "m³/d")
        result.add_dimension("出泥含水率", P_out, "")
        result.add_dimension("分离液量", round(Q_filtrate, 2), "m³/d")
        result.add_dimension("干固体量", round(DS, 1), "kg/d")
        result.add_dimension("PAM日耗量", round(PAM_daily, 1), "kg/d")
        result.add_dimension("PAM溶液流量", round(PAM_solution_flow, 2), "m³/d")
        result.add_dimension("固体回收率", recovery * 100, "%")

        sludge_out = SludgeFlow(
            Q_wet=Q_wet_out,
            DS=DS * recovery,
            P_moisture=P_out,
            VS_ratio=sludge.VS_ratio,
        )
        self._sludge_output = sludge_out
        return result, sludge_out

    @classmethod
    def _vectorized_compute(cls, grid, flow, quality, fixed):
        """向量化脱水间 — 机械脱水批量计算"""
        n_machines = grid["n_machines"].astype(np.int32)
        q_capacity = grid["q_capacity"]
        P_out = grid["P_out"]
        DS = fixed.get("_sludge_DS", 4000.0)
        Q_wet_in = fixed.get("_sludge_Q_wet", 100.0)
        dosage_PAM = fixed.get("dosage_PAM", 4.0)
        N = len(n_machines)

        Q_total = n_machines * q_capacity
        T_run = np.where(Q_total > 0, Q_wet_in / Q_total, 24)
        ok_run = T_run <= 20

        Q_wet_out = np.where(P_out < 1, DS * 0.97 / ((1 - P_out) * 1000.0), 1e9)
        PAM_daily = DS * dosage_PAM / 1000.0

        dt = np.dtype(
            [
                ("T_run", np.float64),
                ("Q_wet_out", np.float64),
                ("PAM_daily", np.float64),
                ("concrete_m3", np.float64),
                ("ok_run_time", np.bool_),
                ("val_run_time", np.float64),
            ]
        )
        arr = np.zeros(N, dtype=dt)
        arr["T_run"] = T_run
        arr["Q_wet_out"] = Q_wet_out
        arr["PAM_daily"] = PAM_daily
        arr["concrete_m3"] = n_machines * 50.0  # 脱水间建筑面积估算
        arr["ok_run_time"] = ok_run
        arr["val_run_time"] = T_run
        return arr
