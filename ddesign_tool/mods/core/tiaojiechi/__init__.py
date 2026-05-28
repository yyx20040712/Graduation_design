"""
tiaojiechi.py — 调节池计算模块

调节池(Equalization Tank)是污水处理厂的预处理构筑物,
核心功能是对来水进行水量调节和水质均化.

计算公式来源:中期报告 §3.1 调节池设计计算
  (3-1): Q_single = Q_avg / n
  (3-2): V_eff = Q_single * HRT
  (3-9): A_eff = V_eff / h_eff
  (3-10): H_total = h_eff + h_super
  (3-11): P_total = P_density * V_total
"""

from typing import Dict, List, Tuple

import numpy as np

from models.base import (
    NodeBase,
    NodeResult,
    NodeState,
    WaterFlow,
    WaterQuality,
    ParamDef,
)


class TiaojiechiNode(NodeBase):
    """调节池节点 — 水量调节 + 水质均化

    设计参数:
      - n: 调节池个数 (2-8)
      - HRT: 水力停留时间 (2-12 h)
      - h_eff: 有效水深 (3-5 m)
      - h_super: 超高 (0.3-0.5 m)
      - ratio_LB: 长宽比 (1.5-3.0)
      - P_density: 搅拌功率密度 (10-15 W/m³)

    约束:
      - 长宽比 L/B ∈ [1.5, 3.0]
      - 实际 HRT >= 设计 HRT - 0.5h
    """

    NODE_TYPE = "tiaojiechi"
    NODE_NAME = "调节池"
    NODE_CATEGORY = "一级处理"

    @classmethod
    def _default_params(cls) -> Dict[str, float]:
        return {
            "n": 4,  # 池数,座
            "HRT": 6,  # 水力停留时间,h
            "h_eff": 4.0,  # 有效水深,m
            "h_super": 0.5,  # 超高,m
            "ratio_LB": 2.0,  # 长宽比 L/B
            "P_density": 12,  # 搅拌功率密度,W/m³
        }

    def _build_param_defs(self) -> List[ParamDef]:
        return [
            ParamDef(
                "池数 n",
                "n",
                value=4,
                default=4,
                min_val=2,
                max_val=8,
                step=1,
                unit="座",
                description="调节池个数",
            ),
            ParamDef(
                "水力停留时间 HRT",
                "HRT",
                value=6,
                default=6,
                min_val=2,
                max_val=12,
                step=0.5,
                unit="h",
                description="水力停留时间",
            ),
            ParamDef(
                "有效水深",
                "h_eff",
                value=4.0,
                default=4.0,
                min_val=3.0,
                max_val=5.0,
                step=0.1,
                unit="m",
                description="调节池有效水深",
            ),
            ParamDef(
                "超高",
                "h_super",
                value=0.5,
                default=0.5,
                min_val=0.3,
                max_val=0.5,
                step=0.1,
                unit="m",
                description="池体超高",
            ),
            ParamDef(
                "长宽比 L/B",
                "ratio_LB",
                value=2.0,
                default=2.0,
                min_val=1.5,
                max_val=3.0,
                step=0.1,
                unit="",
                description="池长与池宽之比",
            ),
            ParamDef(
                "搅拌功率密度",
                "P_density",
                value=12,
                default=12,
                min_val=10,
                max_val=15,
                step=1,
                unit="W/m³",
                description="单位容积搅拌功率,≥12 W/m³",
            ),
        ]

    @classmethod
    def _default_removal_rates(cls) -> Dict[str, float]:
        # 调节池不改变水质
        return {
            "BOD5": 0.0,
            "COD": 0.0,
            "SS": 0.0,
            "NH3N": 0.0,
            "TN": 0.0,
            "TP": 0.0,
        }

    def calculate(self, flow: WaterFlow, quality: WaterQuality) -> NodeResult:
        """执行调节池设计计算 (v5.4: 通过 _vectorized_compute(N=1) 消除双路径)

        计算流程:
          1. 单池设计流量 Q_per_pool = Q_avg_hourly / n
          2. 有效容积 V_eff = Q_per_pool * HRT
          3. 有效面积 A_eff = V_eff / h_eff
          4. 按长宽比计算 L, B → 取整到 0.5m
          5. 校核长宽比和实际 HRT
          6. 计算总高度、搅拌功率
        """
        # ── 读取参数 ──
        n = int(self.get_param("n"))
        HRT = self.get_param("HRT")
        h_eff = self.get_param("h_eff")
        h_super = self.get_param("h_super")
        ratio_LB = self.get_param("ratio_LB")
        P_density = self.get_param("P_density")

        # ── 通过向量化路径计算 (N=1) ──
        grid, fixed = self._make_scalar_grid(
            {"n": n, "HRT": HRT, "h_eff": h_eff, "ratio_LB": ratio_LB},
            {"h_super": h_super, "P_density": P_density},
        )
        res = self._vectorized_compute(grid, flow, quality, fixed)
        r = res[0]  # 单行结果

        # ── 组装 NodeResult ──
        result = NodeResult(success=True)
        result.params = {
            "n": n, "HRT": HRT, "h_eff": h_eff,
            "h_super": h_super, "ratio_LB": ratio_LB, "P_density": P_density,
        }

        # 校核
        result.add_check(
            "长宽比 L/B", bool(r["ok_LB_ratio"]),
            round(float(r["val_LB_ratio"]), 2), "1.0~2.0", "",
        )
        hrt_ok = bool(r["ok_HRT_actual"])
        result.add_check(
            "实际 HRT", hrt_ok,
            round(float(r["val_HRT_actual"]), 2), "2~12", "h",
        )
        if not hrt_ok:
            result.add_warning(
                f"实际 HRT={r['val_HRT_actual']:.1f}h 低于设计值 {HRT}h-0.5h,"
                f"建议增大池体尺寸或减少池数"
            )

        # 尺寸
        result.add_dimension("池数", n, "座")
        result.add_dimension("单池长度 L", float(r["L"]), "m")
        result.add_dimension("单池宽度 B", float(r["B"]), "m")
        result.add_dimension("有效水深 h_eff", h_eff, "m")
        result.add_dimension("总高度 H", float(r["H"]), "m")
        result.add_dimension("单池有效容积", round(float(r["V_actual"]), 1), "m³")
        result.add_dimension("总有效容积", round(float(r["V_total"]), 1), "m³")
        result.add_dimension("设计 HRT", round(float(r["HRT_actual"]), 2), "h")
        result.add_dimension("长宽比 L/B", round(float(r["ratio_actual"]), 2), "")
        result.add_dimension("搅拌总功率", float(r["P_kW"]), "kW")
        result.add_dimension("单池设计流量", round(float(r["Q_per_pool"]), 2), "m³/h")

        # 概算字段
        result.add_dimension("调节池总面积", round(float(r["area_total"]), 1), "m²")
        result.add_dimension("混凝土量估算", round(float(r["concrete_m3"]), 1), "m³")

        return result

    @classmethod
    def _vectorized_compute(
        cls, grid: dict, flow: "WaterFlow", quality: "WaterQuality", fixed: dict
    ) -> "np.ndarray":
        """向量化批量计算调节池 (N 个参数组合一次计算)

        grid 键: n, HRT, h_eff, ratio_LB  (均为 shape (N,) 的 float 数组)
        fixed 键: h_super, P_density

        Returns:
            numpy 结构化数组,dtype 包含:
              - L, B, V_actual, V_total, H_total, HRT_actual, ratio_actual, P_kW (float)
              - area_total, concrete_m3 (float) — 成本估算用
              - ok_LB_ratio, ok_HRT_actual (bool)
        """
        n = grid["n"].astype(np.int32)
        HRT = grid["HRT"]
        h_eff = grid["h_eff"]
        ratio_LB = grid["ratio_LB"]
        h_super = fixed["h_super"]
        P_density = fixed["P_density"]
        N = len(n)

        # (1) 单池设计流量
        Q_avg_h = flow.Q_avg_hourly
        Q_per_pool = Q_avg_h / n  # m³/h

        # (2) 单池有效容积
        V_eff = Q_per_pool * HRT  # m³

        # (3) 有效面积
        A_eff = V_eff / h_eff  # m²

        # (4) 平面尺寸
        B_theory = np.sqrt(A_eff / ratio_LB)
        L_theory = ratio_LB * B_theory
        B = np.ceil(B_theory / 0.5) * 0.5
        L = np.ceil(L_theory / 0.5) * 0.5

        # (5) 取整后校核 (safe division)
        V_actual = L * B * h_eff  # 单池实际容积
        HRT_actual = np.divide(V_actual, Q_per_pool, where=Q_per_pool > 0,
                               out=np.full_like(V_actual, np.nan, dtype=np.float64))  # h
        ratio_actual = np.divide(L, B, where=B > 0,
                                 out=np.full_like(L, np.nan, dtype=np.float64))

        # 约束
        ok_ratio = (1.0 <= ratio_actual) & (ratio_actual <= 2.0)
        ok_hrt = (2.0 <= HRT_actual) & (HRT_actual <= 12.0)

        # (6) 总高度
        H_total = h_eff + h_super

        # (7) 搅拌功率
        V_total = V_actual * n  # 总有效容积
        P_total = P_density * V_total
        P_kW = np.ceil(P_total / 100) * 0.1  # 取整到 0.1kW

        # 成本估算字段
        area_total = L * B * n
        concrete_m3 = V_total * 1.2

        # 构建结构化数组
        dtype = np.dtype(
            [
                ("L", np.float64),
                ("B", np.float64),
                ("h_eff_out", np.float64),
                ("V_actual", np.float64),
                ("V_total", np.float64),
                ("H_total", np.float64),
                ("HRT_actual", np.float64),
                ("ratio_actual", np.float64),
                ("P_kW", np.float64),
                ("Q_per_pool", np.float64),
                ("area_total", np.float64),
                ("H", np.float64),
                ("concrete_m3", np.float64),
                ("ok_LB_ratio", np.bool_),
                ("ok_HRT_actual", np.bool_),
                ("val_LB_ratio", np.float64),
                ("val_HRT_actual", np.float64),
            ]
        )
        result = np.empty(N, dtype=dtype)
        result["L"] = L
        result["B"] = B
        result["h_eff_out"] = h_eff
        result["V_actual"] = V_actual
        result["V_total"] = V_total
        result["H_total"] = H_total
        result["HRT_actual"] = HRT_actual
        result["ratio_actual"] = ratio_actual
        result["P_kW"] = P_kW
        result["Q_per_pool"] = Q_per_pool
        result["area_total"] = area_total
        result["concrete_m3"] = concrete_m3
        result["L"] = L  # standard field
        result["B"] = B  # standard field
        result["H"] = result["H_total"]  # standard field
        result["ok_LB_ratio"] = ok_ratio
        result["ok_HRT_actual"] = ok_hrt
        result["val_LB_ratio"] = ratio_actual
        result["val_HRT_actual"] = HRT_actual
        return result
