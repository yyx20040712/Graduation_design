from typing import Dict, List
import numpy as np
from models.base import (
    NodeBase,
    NodeResult,
    NodeState,
    WaterFlow,
    WaterQuality,
    SludgeFlow,
    ParamDef,
    Port,
    PortType,
    GRAVITY,
)


class _BarScreenBase(NodeBase):
    """格栅基类 — 粗格栅和细格栅的共享计算逻辑"""

    def _init_ports(self) -> None:
        """格栅: MIXED进水 → MIXED出水 + SLUDGE栅渣"""
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
                port_id=f"{self.node_id}-slag",
                name="栅渣",
                port_type=PortType.SLUDGE,
                direction="output",
                node_id=self.node_id,
            ),
        ]

    @classmethod
    def _default_params(cls) -> Dict[str, float]:
        return {
            "n": 3,
            "b": cls._b_default,
            "alpha": cls._alpha_default,
            "h": cls._h_default,
            "v": 0.8,
            "v1": 0.7,
            "s": cls._s_default,
            "bar_shape": 0,
        }

    @classmethod
    def _default_removal_rates(cls) -> Dict[str, float]:
        return {"BOD5": 0.0, "COD": 0.0, "SS": 0.0, "NH3N": 0.0, "TN": 0.0, "TP": 0.0}

    # ── 栅条形状系数 β (GB50014-2021 §6.3) ──
    _BAR_SHAPE_BETA = {0: 2.42, 1: 1.97, 2: 1.83}
    _BAR_SHAPE_NAMES = {0: "矩形栅条", 1: "半圆形栅条", 2: "圆形栅条"}

    @classmethod
    def _get_beta(cls, bar_shape: int) -> float:
        return cls._BAR_SHAPE_BETA.get(bar_shape, 2.42)

    def _build_param_defs(self) -> List[ParamDef]:
        return [
            ParamDef(
                "格栅台数",
                "n",
                value=3,
                default=3,
                min_val=2,
                max_val=4,
                step=1,
                unit="台",
            ),
            ParamDef(
                "栅条间隙",
                "b",
                value=self._b_default,
                default=self._b_default,
                min_val=self._b_range[0],
                max_val=self._b_range[1],
                step=5,
                unit="mm",
                description="栅条间隙宽度",
            ),
            ParamDef(
                "格栅倾角",
                "alpha",
                value=self._alpha_default,
                default=self._alpha_default,
                min_val=60,
                max_val=90,
                step=5,
                unit="°",
            ),
            ParamDef(
                "栅前水深",
                "h",
                value=self._h_default,
                default=self._h_default,
                min_val=0.4,
                max_val=1.0,
                step=0.1,
                unit="m",
            ),
            ParamDef(
                "过栅流速",
                "v",
                value=0.8,
                default=0.8,
                min_val=0.6,
                max_val=1.0,
                step=0.05,
                unit="m/s",
            ),
            ParamDef(
                "栅前流速",
                "v1",
                value=0.7,
                default=0.7,
                min_val=0.4,
                max_val=0.9,
                step=0.05,
                unit="m/s",
            ),
            ParamDef(
                "栅条宽度",
                "s",
                value=self._s_default,
                default=self._s_default,
                min_val=1,
                max_val=20,
                step=1,
                unit="mm",
                description="栅条宽度(粗格栅10mm, 细格栅2~5mm)",
            ),
            ParamDef(
                "栅条形状",
                "bar_shape",
                value=0,
                default=0,
                min_val=0,
                max_val=2,
                step=1,
                unit="-",
                description="0=矩形(β=2.42) 1=半圆(β=1.97) 2=圆形(β=1.83)",
            ),
        ]

    def calculate(self, flow: WaterFlow, quality: WaterQuality) -> NodeResult:
        n = int(self.get_param("n"))
        b_mm = self.get_param("b")
        alpha_deg = self.get_param("alpha")
        h = self.get_param("h")
        v = self.get_param("v")
        v1 = self.get_param("v1")
        s_mm = self.get_param("s")
        bar_shape = int(self.get_param("bar_shape"))

        result = NodeResult(success=True)
        result.params = {
            "n": n,
            "b": b_mm,
            "alpha": alpha_deg,
            "h": h,
            "v": v,
            "v1": v1,
            "s": s_mm,
            "bar_shape": bar_shape,
        }

        grid = {
            "n": np.array([n], dtype=np.int32),
            "b": np.array([b_mm]),
            "alpha": np.array([alpha_deg]),
            "h": np.array([h]),
            "bar_shape": np.array([bar_shape], dtype=np.int32),
        }
        fixed = {"v": v, "v1": v1, "s": s_mm}

        r = self._vectorized_compute(grid, flow, quality, fixed)

        bar_name = self._BAR_SHAPE_NAMES.get(bar_shape, "未知")
        result.params["bar_shape_name"] = bar_name

        cleaning = "机械清渣" if r["W_slag"][0] > 0.2 else "人工清渣"

        result.add_dimension("格栅台数", n, "台")
        result.add_dimension("单台流量", round(r["q_single_Ls"][0], 2), "L/s")
        result.add_dimension("栅条间隙数", int(r["n_gap"][0]), "个")
        result.add_dimension("栅槽宽度 B", r["B"][0], "m")
        result.add_dimension("进水渠宽 B1", r["B1"][0], "m")
        result.add_dimension("校核过栅流速", round(r["v_checked"][0], 3), "m/s")
        result.add_dimension("校核渠内流速", round(r["v1_checked"][0], 3), "m/s")
        result.add_dimension("过栅水头损失 h1", round(r["h1_loss"][0], 3), "m")
        result.add_dimension("栅条形状系数 β", r["beta_val"][0], "")
        result.add_dimension("阻力系数 ξ", round(r["xi"][0], 4), "")
        result.add_dimension("(s/b)^(4/3)", round(r["sb_factor"][0], 4), "")
        result.add_dimension("栅后总高 H", r["H_total"][0], "m")
        result.add_dimension("栅槽总长 L", r["L_total"][0], "m")
        result.add_dimension("每日栅渣量", round(r["W_slag"][0], 4), "m³/d")
        result.add_dimension("清渣方式", cleaning, "")

        result.add_check(
            "B1 < B",
            bool(r["ok_B1_B"][0]),
            round(r["val_B1_B"][0], 2),
            "> 0",
            "m",
        )
        result.add_check(
            "过栅流速 v", bool(r["ok_v"][0]), round(r["val_v"][0], 3), "0.6~1.0", "m/s"
        )
        result.add_check(
            "渠内流速 v1",
            bool(r["ok_v1"][0]),
            round(r["val_v1"][0], 3),
            "0.4~0.9",
            "m/s",
        )
        result.add_check(
            "水头损失 h1", bool(r["ok_h1_loss"][0]), round(r["val_h1_loss"][0], 3), "<= 0.3", "m"
        )

        if not r["ok_B1_B"][0]:
            result.add_warning("进水渠宽 B1 不小于栅槽宽 B,需调整参数")

        W = r["W_slag"][0]
        P_slag = 0.80
        DS_slag = W * (1 - P_slag) * 1000.0
        self._sludge_output = SludgeFlow(
            Q_wet=W,
            DS=DS_slag,
            P_moisture=P_slag,
            VS_ratio=0.85,
        )

        return result

    @classmethod
    def _vectorized_compute(
        cls, grid: dict, flow: "WaterFlow", quality: "WaterQuality", fixed: dict
    ) -> "np.ndarray":
        """向量化批量格栅计算

        grid: n, b(mm), alpha(°), h(m)
        fixed: v, v1
        子类通过 cls._W1, GRAVITY 访问类型特定值
        """
        n = grid["n"].astype(np.int32)
        b_mm = grid["b"]
        alpha_deg = grid["alpha"]
        h = grid["h"]
        v_design = fixed["v"]
        v1_design = fixed["v1"]
        N = len(n)

        b_m = b_mm / 1000.0
        sin_alpha = np.sin(np.radians(alpha_deg))
        tan_alpha = np.tan(np.radians(alpha_deg))
        G = 9.81

        q = flow.Q_design / n  # 单台流量 m³/s

        # 栅条间隙数
        n_gap = np.ceil(q * np.sqrt(sin_alpha) / (b_m * h * v_design)).astype(np.int32)

        # 栅槽宽度
        s_mm = fixed["s"]  # 栅条宽度 mm
        s_m = s_mm / 1000.0  # mm → m
        B = s_m * (n_gap - 1) + b_m * n_gap + 0.2
        B_rounded = np.ceil(B / 0.1) * 0.1

        # 进水渠宽
        B1 = q / (h * v1_design)
        B1_rounded = np.ceil(B1 / 0.1) * 0.1

        # 校核流速 (safe division)
        denom_v = np.maximum(b_m * h * n_gap, 1e-10)
        v_checked = q * np.sqrt(sin_alpha) / denom_v
        denom_v1 = np.maximum(h * B1_rounded, 1e-10)
        v1_checked = q / denom_v1

        # 水头损失
        bar_shape_arr = grid.get(
            "bar_shape", np.full(N, int(fixed.get("bar_shape", 0)))
        ).astype(np.int32)
        beta_map = np.array(
            [cls._BAR_SHAPE_BETA[0], cls._BAR_SHAPE_BETA[1], cls._BAR_SHAPE_BETA[2]],
            dtype=np.float64,
        )
        beta_vals = beta_map[bar_shape_arr]  # fancy-index
        ratio_sb = np.where(b_mm > 0, s_mm / b_mm, 0.0)
        sb_factor = ratio_sb ** (4.0 / 3.0)
        xi = beta_vals * sb_factor
        h0 = xi * v_checked**2 / (2 * G) * sin_alpha
        h1 = h0 * 3.0

        # 栅后总高
        H = h + h1 + 0.3
        H_rounded = np.ceil(H / 0.1) * 0.1

        # 栅槽总长
        L1 = np.where(
            B_rounded > B1_rounded, (B_rounded - B1_rounded) / (2 * tan_alpha), 0.0
        )
        L2 = L1 / 2
        L = L1 + L2 + 1.0 + 0.5 + (0.2 + h) / tan_alpha
        L_rounded = np.ceil(L / 0.1) * 0.1

        # 每日栅渣量
        W = flow.Q_design * 86400 * cls._W1 / (flow.Kz * 1000)

        # 约束
        ok_v = (0.6 <= v_checked) & (v_checked <= 1.0)
        ok_v1 = (0.4 <= v1_checked) & (v1_checked <= 0.9)
        ok_B1_B = B1_rounded < B_rounded
        ok_h1_loss = h1 <= 0.3

        dtype = np.dtype(
            [
                ("n_gap", np.int32),
                ("B", np.float64),
                ("B1", np.float64),
                ("v_checked", np.float64),
                ("v1_checked", np.float64),
                ("xi", np.float64),
                ("beta_val", np.float64),
                ("sb_factor", np.float64),
                ("h1_loss", np.float64),
                ("H_total", np.float64),
                ("L_total", np.float64),
                ("W_slag", np.float64),
                ("q_single_Ls", np.float64),
                ("concrete_m3", np.float64),
                ("ok_v", np.bool_),
                ("ok_v1", np.bool_),
                ("ok_B1_B", np.bool_),
                ("ok_h1_loss", np.bool_),
                ("val_v", np.float64),
                ("val_v1", np.float64),
                ("val_B1_B", np.float64),
                ("val_h1_loss", np.float64),
            ]
        )
        result = np.empty(N, dtype=dtype)
        result["n_gap"] = n_gap
        result["B"] = B_rounded
        result["B1"] = B1_rounded
        result["v_checked"] = v_checked
        result["v1_checked"] = v1_checked
        result["xi"] = xi
        result["beta_val"] = beta_vals
        result["sb_factor"] = sb_factor
        result["h1_loss"] = h1
        result["H_total"] = H_rounded
        result["L_total"] = L_rounded
        result["W_slag"] = W
        result["q_single_Ls"] = q * 1000
        result["concrete_m3"] = L_rounded * B_rounded * H_rounded * n * 0.3
        result["ok_v"] = ok_v
        result["ok_v1"] = ok_v1
        result["ok_B1_B"] = ok_B1_B
        result["ok_h1_loss"] = ok_h1_loss
        result["val_v"] = v_checked
        result["val_v1"] = v1_checked
        result["val_B1_B"] = B_rounded - B1_rounded
        result["val_h1_loss"] = h1
        return result

    @property
    def _W1(self) -> float:
        """栅渣量标准 m³/10³m³ — 子类覆盖"""
        raise NotImplementedError

    @property
    def _s_default(self) -> float:
        """栅条宽度 mm — 子类覆盖"""
        raise NotImplementedError

    @property
    def _b_default(self) -> float:
        raise NotImplementedError

    @property
    def _b_range(self) -> tuple:
        raise NotImplementedError

    # 子类可覆盖的类属性
    _alpha_default: float = 75
    _h_default: float = 0.8


class FineBarScreenNode(_BarScreenBase):
    """细格栅"""

    NODE_TYPE = "xigeshan"
    NODE_NAME = "细格栅"
    NODE_CATEGORY = "一级处理"

    _b_default = 5.0
    _b_range = (1.5, 10)
    _s_default = 3.0
    _W1 = 0.08
    _alpha_default = 60.0
    _h_default = 0.5

    @classmethod
    def _default_removal_rates(cls) -> Dict[str, float]:
        return {
            "BOD5": 0.08,
            "COD": 0.08,
            "SS": 0.08,
            "NH3N": 0.0,
            "TN": 0.0,
            "TP": 0.0,
        }
