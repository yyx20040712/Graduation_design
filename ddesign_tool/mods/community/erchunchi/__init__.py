"""
erchunchi — 辐流式二沉池 (Secondary Clarifier) 社区模组

公式来源: GB50014-2021 §6.5, CJJ 131-2009
适用条件: 活性污泥法生物处理后泥水分离
表面负荷: 0.6~1.5 m³/(m²·h), 固体负荷 ≤150 kgMLSS/(m²·d)
"""

import math
from typing import Dict, List

import numpy as np

from models.base import (
    NodeBase, NodeResult, WaterFlow, WaterQuality, SludgeFlow,
    ParamDef, Port, PortType, PI,
)


class ErchunchiNode(NodeBase):
    """辐流式二沉池 — 中心进水周边出水,刮泥机排泥

    与初沉池的区别:
    - 表面负荷更低 (活性污泥沉降性差)
    - 增加固体负荷校核 (MLSS)
    - 沉淀时间更长
    - D/h2 比例要求更严
    - 出水堰负荷更严格 (≤1.7 L/(s·m))
    """

    NODE_TYPE = "erchunchi"
    NODE_NAME = "辐流式二沉池"
    NODE_CATEGORY = "市政污水处理"

    # ── PORTS: MIXED进水 → MIXED出水 + SLUDGE排泥 ──
    def _init_ports(self) -> None:
        self.input_ports = [
            Port(port_id=f"{self.node_id}-in", name="进水",
                 port_type=PortType.MIXED, direction="input", node_id=self.node_id),
        ]
        self.output_ports = [
            Port(port_id=f"{self.node_id}-out", name="出水",
                 port_type=PortType.MIXED, direction="output", node_id=self.node_id),
            Port(port_id=f"{self.node_id}-sludge", name="排泥",
                 port_type=PortType.SLUDGE, direction="output", node_id=self.node_id),
        ]

    # ── DEFAULT PARAMETERS ──
    @classmethod
    def _default_params(cls) -> Dict[str, float]:
        return {
            "n": 2, "q_prime": 1.0, "solid_load": 120.0,
            "T_settle": 2.5,
            "h3": 0.3, "i_slope": 0.05, "R1": 1.8, "R2": 0.8, "h5": 1.5,
            "P_sludge": 0.992, "X_MLSS": 3.5, "RAS_ratio": 0.5,
        }

    # ── UI PARAMETER DEFINITIONS ──
    def _build_param_defs(self) -> List[ParamDef]:
        return [
            ParamDef("池数量", "n", value=self.get_param("n"),
                     default=2, min_val=2, max_val=6, step=1, unit="座",
                     description="并联二沉池数量"),
            ParamDef("表面负荷 q'", "q_prime", value=self.get_param("q_prime"),
                     default=1.0, min_val=0.6, max_val=1.5, step=0.1,
                     unit="m³/(m²·h)",
                     description="GB50014 §6.5: 活性污泥法后 0.6~1.5"),
            ParamDef("固体负荷", "solid_load", value=self.get_param("solid_load"),
                     default=120.0, min_val=80, max_val=150, step=5,
                     unit="kgMLSS/(m²·d)",
                     description="GB50014: ≤150 kg/(m²·d)"),
            ParamDef("沉淀时间 T", "T_settle", value=self.get_param("T_settle"),
                     default=2.5, min_val=1.5, max_val=4.0, step=0.5, unit="h",
                     description="GB50014: 1.5~4.0h"),
        ]

    # ── DEFAULT REMOVAL RATES ──
    @classmethod
    def _default_removal_rates(cls) -> Dict[str, float]:
        return {
            "BOD5": 0.25, "COD": 0.20, "SS": 0.70,
            "NH3N": 0.05, "TN": 0.08, "TP": 0.10,
        }

    # ── CORE CALCULATION ──
    def calculate(self, flow: WaterFlow,
                  quality: WaterQuality) -> NodeResult:
        """执行标量计算 — 纯函数,不修改self状态"""
        n = int(self.get_param("n"))
        q_prime = self.get_param("q_prime")
        solid_load = self.get_param("solid_load")
        T_settle = self.get_param("T_settle")
        h3 = self.get_param("h3")
        i_slope = self.get_param("i_slope")
        R1 = self.get_param("R1")
        R2 = self.get_param("R2")
        h5 = self.get_param("h5")
        P_sludge = self.get_param("P_sludge")
        X_MLSS = self.get_param("X_MLSS")
        RAS_ratio = self.get_param("RAS_ratio")

        if n <= 0:
            return NodeResult.failed("池数 n 必须 >= 1")

        result = NodeResult(success=True)
        result.params = {
            "n": n, "q_prime": q_prime, "solid_load": solid_load,
            "T_settle": T_settle, "h3": h3, "i_slope": i_slope,
            "R1": R1, "R2": R2, "h5": h5,
            "P_sludge": P_sludge, "X_MLSS": X_MLSS, "RAS_ratio": RAS_ratio,
        }

        # ── 进水量 ──
        Q_single = flow.Q_design / n  # m³/s
        Q_single_m3h = Q_single * 3600  # m³/h

        # ── (A) 沉淀面积 (按表面负荷) ──
        F_surface = Q_single_m3h / q_prime  # m²

        # ── (B) 沉淀面积 (按固体负荷校核) ──
        Q_RAS = Q_single * RAS_ratio  # 回流污泥量 m³/s
        Q_total = Q_single + Q_RAS  # 进入二沉池总流量 m³/s
        Q_total_m3d = Q_total * 86400  # m³/d
        solid_mass = Q_total_m3d * X_MLSS / 1000.0  # kgMLSS/d
        F_solid = solid_mass / solid_load if solid_load > 0 else float('inf')  # m²

        # 取大值
        F = max(F_surface, F_solid)

        # ── (C) 池径 ──
        D_theory = math.sqrt(4 * F / PI)
        D = math.ceil(max(D_theory, 16.0) / 0.5) * 0.5  # 最小16m
        result.add_check("池径 D >= 16",
                         D >= 16, round(D, 1), ">= 16", "m")

        F_actual = PI * D ** 2 / 4
        q_prime_actual = Q_single_m3h / F_actual if F_actual > 0 else 0

        # ── 校核表面负荷 ──
        result.add_check("实际表面负荷 q'",
                         0.6 <= q_prime_actual <= 1.5,
                         round(q_prime_actual, 2), "0.6~1.5", "m³/(m²·h)")

        # ── 校核固体负荷 ──
        solid_load_actual = solid_mass / (F_actual * n) if F_actual > 0 else 0
        result.add_check("固体负荷 ≤ 150",
                         solid_load_actual <= 150,
                         round(solid_load_actual, 1),
                         "≤ 150 (GB50014)", "kgMLSS/(m²·d)")

        # ── (D) 有效水深 ──
        h2 = q_prime_actual * T_settle
        ratio_Dh2 = D / h2 if h2 > 0 else 0
        result.add_check("有效水深 h2 >= 2.5",
                         h2 >= 2.5, round(h2, 2), ">= 2.5", "m")
        result.add_check("径深比 D/h2",
                         6 <= ratio_Dh2 <= 12,
                         round(ratio_Dh2, 2), "6~12", "")

        # ── (E) 超高 ──
        h1 = 0.5  # 二沉池超高 ≥0.5m

        # ── (F) 泥斗 ──
        R = D / 2.0
        V1 = PI * h5 / 3 * (R1 ** 2 + R1 * R2 + R2 ** 2)
        h4 = i_slope * (R - R1)
        h4_rounded = math.ceil(h4 / 0.1) * 0.1
        V2 = PI * h4_rounded / 3 * (R ** 2 + R * R1 + R1 ** 2)
        V_total_storage = V1 + V2

        # ── (G) 污泥产量计算 ──
        SS_in = quality.SS
        removal_ss = self._removal_rates.get("SS", 0.70)
        SS_removed = SS_in * removal_ss  # mg/L
        S_dry = flow.Q_avg_daily * SS_removed / 1000.0  # kg/d (settled solids)
        # 包含回流污泥中的生物固体
        S_bio = flow.Q_avg_daily * X_MLSS * 0.3 / 1000.0  # kg/d (excess biomass, ~30% of MLSS)
        S_total_dry = S_dry + S_bio

        S_wet = S_total_dry / ((1 - P_sludge) * 1000.0) if P_sludge < 1 else float('inf')
        V_sludge_storage = S_wet * 2.0 / 24.0  # 2h贮泥时间

        result.add_check("污泥区容积足够",
                         V_total_storage >= V_sludge_storage,
                         round(V_total_storage - V_sludge_storage, 2),
                         ">= 0", "m³")

        # ── (H) 出水堰 ──
        weir_len = 2.0 * PI * (D - 1.0)  # 双侧堰
        q_weir = Q_single * 1000.0 / weir_len if weir_len > 0 else 0  # L/(s·m)
        result.add_check("堰负荷 ≤ 1.7",
                         q_weir <= 1.7,
                         round(q_weir, 3), "≤ 1.7", "L/(s·m)")

        # ── (I) 总高度 ──
        H = h1 + h2 + h3 + h4_rounded + h5
        H_rounded = math.ceil(H / 0.1) * 0.1

        # ── (J) 刮泥机线速 ──
        v_peripheral = PI * D * 1.0 / 60.0  # m/min
        result.add_check("刮泥机线速 ≤ 2.0",
                         v_peripheral <= 2.0,
                         round(v_peripheral, 2),
                         "≤ 2.0 (CJJ 131)", "m/min")

        # ── 组装尺寸 ──
        result.add_dimension("池数", n, "座")
        result.add_dimension("池径 D", D, "m")
        result.add_dimension("沉淀面积(单池)", round(F_actual, 1), "m²")
        result.add_dimension("有效水深 h2", round(h2, 2), "m")
        result.add_dimension("径深比 D/h2", round(ratio_Dh2, 2), "")
        result.add_dimension("超高 h1", h1, "m")
        result.add_dimension("缓冲层 h3", h3, "m")
        result.add_dimension("池底坡降 h4", h4_rounded, "m")
        result.add_dimension("泥斗高度 h5", h5, "m")
        result.add_dimension("总高度 H", H_rounded, "m")
        result.add_dimension("出水堰长", round(weir_len, 1), "m",
                             formula="L = 2π(D-1), 双侧堰",
                             category="physical")
        result.add_dimension("堰负荷", round(q_weir, 3), "L/(s·m)")
        result.add_dimension("实际表面负荷", round(q_prime_actual, 2), "m³/(m²·h)")
        result.add_dimension("实际固体负荷", round(solid_load_actual, 1), "kgMLSS/(m²·d)")
        result.add_dimension("每日干污泥", round(S_total_dry, 1), "kg/d")
        result.add_dimension("每日湿污泥", round(S_wet, 2), "m³/d")
        result.add_dimension("刮泥机线速", round(v_peripheral, 2), "m/min")
        result.add_dimension("MLSS浓度", X_MLSS, "g/L")
        result.add_dimension("回流比", RAS_ratio * 100, "%")

        # ── 污泥输出 (SLUDGE 端口) ──
        self._sludge_output = SludgeFlow(
            Q_wet=S_wet, DS=S_total_dry,
            P_moisture=P_sludge, VS_ratio=0.70,
        )

        return result

    # ── VECTORIZED COMPUTE (for Solution Browser) ──
    @classmethod
    def _vectorized_compute(cls, grid: dict, flow: WaterFlow,
                            quality: WaterQuality, fixed: dict) -> "np.ndarray":
        """向量化二沉池批量计算

        grid: n, q_prime, solid_load, T_settle
        fixed: h3, i_slope, R1, R2, h5, P_sludge, X_MLSS, RAS_ratio
        """
        import numpy as np
        N = len(next(iter(grid.values())))

        n = grid["n"].astype(np.int32)
        q_prime = grid["q_prime"]
        solid_load_grid = grid["solid_load"]
        T_settle = grid.get("T_settle",
                            np.full(N, fixed.get("T_settle", 2.5)))
        h3 = fixed.get("h3", 0.3)
        i_slope = fixed.get("i_slope", 0.05)
        R1 = fixed.get("R1", 1.8)
        R2 = fixed.get("R2", 0.8)
        h5 = fixed.get("h5", 1.5)
        P_sludge = fixed.get("P_sludge", 0.992)
        X_MLSS = fixed.get("X_MLSS", 3.5)
        RAS_ratio = fixed.get("RAS_ratio", 0.5)
        PI_V = np.pi

        Q_single = flow.Q_design / n
        Q_single_m3h = Q_single * 3600

        # 沉淀面积 (表面负荷)
        F_surface = Q_single_m3h / q_prime

        # 固体负荷校核
        Q_RAS = Q_single * RAS_ratio
        Q_total_m3d = (Q_single + Q_RAS) * 86400
        solid_mass = Q_total_m3d * X_MLSS / 1000.0
        F_solid = np.where(solid_load_grid > 0,
                           solid_mass / solid_load_grid, 1e9)
        F = np.maximum(F_surface, F_solid)

        # 池径
        D_theory = np.sqrt(4 * F / PI_V)
        D = np.ceil(np.maximum(D_theory, 16.0) / 0.5) * 0.5
        ok_D = D >= 16

        F_actual = PI_V * D ** 2 / 4
        q_prime_actual = np.where(F_actual > 0, Q_single_m3h / F_actual, 0.0)
        ok_q = (0.6 <= q_prime_actual) & (q_prime_actual <= 1.5)

        solid_load_actual = np.where(F_actual > 0,
                                     solid_mass / (F_actual * n), 0.0)
        ok_solid = solid_load_actual <= 150

        # 有效水深
        h2 = q_prime_actual * T_settle
        ratio_Dh2 = np.where(h2 > 0, D / h2, 0.0)
        ok_h2 = h2 >= 2.5
        ok_Dh2 = (6 <= ratio_Dh2) & (ratio_Dh2 <= 12)

        # 出水堰
        weir_len = 2.0 * PI_V * (D - 1.0)
        q_weir = np.where(weir_len > 0,
                          Q_single * 1000.0 / weir_len, 0.0)
        ok_weir = q_weir <= 1.7

        # 总高度
        h1_val = 0.5
        R = D / 2.0
        h4 = i_slope * (R - R1)
        h4_rounded = np.ceil(h4 / 0.1) * 0.1
        H_total = h1_val + h2 + h3 + h4_rounded + h5

        # 刮泥机线速
        v_peripheral = PI_V * D * 1.0 / 60.0
        ok_scraper = v_peripheral <= 2.0

        # 混凝土量估算
        concrete_m3 = (PI_V * (D/2)**2 * 0.3 +
                       PI_V * D * H_total * 0.3) * n

        # 定义输出 dtype — ok_* + val_* + concrete_m3 ALL required
        dt = np.dtype([
            ("D", np.float64), ("h2", np.float64), ("H_total", np.float64),
            ("F_actual", np.float64), ("q_prime_actual", np.float64),
            ("solid_load_actual", np.float64), ("ratio_Dh2", np.float64),
            ("H", np.float64),
            ("concrete_m3", np.float64),
            ("ok_D_min", np.bool_), ("val_D_min", np.float64),
            ("ok_q_prime", np.bool_), ("val_q_prime", np.float64),
            ("ok_solid", np.bool_), ("val_solid", np.float64),
            ("ok_h2", np.bool_), ("val_h2", np.float64),
            ("ok_Dh2", np.bool_), ("val_Dh2", np.float64),
            ("ok_weir", np.bool_), ("val_weir", np.float64),
            ("ok_scraper", np.bool_), ("val_scraper", np.float64),
        ])

        arr = np.zeros(N, dtype=dt)
        arr["D"] = D
        arr["h2"] = h2
        arr["H_total"] = H_total
        arr["F_actual"] = F_actual
        arr["q_prime_actual"] = q_prime_actual
        arr["solid_load_actual"] = solid_load_actual
        arr["ratio_Dh2"] = ratio_Dh2
        arr["concrete_m3"] = concrete_m3

        arr["ok_D_min"] = ok_D
        arr["val_D_min"] = D
        arr["ok_q_prime"] = ok_q
        arr["val_q_prime"] = q_prime_actual
        arr["ok_solid"] = ok_solid
        arr["val_solid"] = solid_load_actual
        arr["ok_h2"] = ok_h2
        arr["val_h2"] = h2
        arr["ok_Dh2"] = ok_Dh2
        arr["val_Dh2"] = ratio_Dh2
        arr["ok_weir"] = ok_weir
        arr["val_weir"] = q_weir
        arr["ok_scraper"] = ok_scraper
        arr["val_scraper"] = v_peripheral

        return arr
