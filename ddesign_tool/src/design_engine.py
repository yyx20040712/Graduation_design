"""
模块2:核心设计逻辑

功能:排水管道水力设计计算器(基于曼宁公式与GB50014-2021)
主要功能:给定设计流量,返回所有可行的管径、充满度、坡度、流速组合.
可自定义管材粗糙系数、管道类型(污水/雨水)以及流速限制.
"""

import math
from typing import Dict, List, Optional, Tuple, Union

from _logging import get_logger

_log = get_logger(__name__)


class DrainagePipeDesigner:
    """
    排水管道水力设计计算器(基于曼宁公式与GB50014-2021)

    主要功能:给定设计流量,返回所有可行的管径、充满度、坡度、流速组合.
    可自定义管材粗糙系数、管道类型(污水/雨水)以及流速限制.
    """

    # 规范最大充满度表 (GB50014-2021 表5.2.4)
    MAX_FULLNESS = {
        "污水": [
            (200, 300, 0.55),  # (管径下限, 管径上限, 最大充满度)
            (350, 450, 0.65),
            (500, 900, 0.70),
            (1000, float("inf"), 0.75),
        ],
        "雨水": [(0, float("inf"), 1.0)],  # 雨水管允许满流
    }

    # 最小管径及对应最小设计坡度 (GB50014-2021 表5.2.10)
    # 已删除1300管径
    MIN_SLOPE_BY_DIAMETER = {
        300: 0.003,
        400: 0.0015,
        500: 0.0012,
        600: 0.0010,
        700: 0.0010,
        800: 0.0008,
        900: 0.0008,
        1000: 0.0006,
        1100: 0.0006,
        1200: 0.0006,
        1400: 0.0005,
        1500: 0.0005,
    }

    def __init__(
        self,
        n: float = 0.014,
        pipe_type: str = "污水",
        min_velocity: float = 0.6,
        max_velocity: float = 1.5,
        default_min_slope: float = 0.001,
        min_recommended_fullness: float = 0.1,
        custom_max_fullness: Optional[Dict[str, List[Tuple]]] = None,
        custom_min_slope_dict: Optional[Dict[int, float]] = None,
    ):
        self.n = n
        self.pipe_type = pipe_type
        self.min_velocity = min_velocity
        self.max_velocity = max_velocity
        self.default_min_slope = default_min_slope
        self.min_recommended_fullness = min_recommended_fullness

        self.max_fullness_rules = self.MAX_FULLNESS.copy()
        if custom_max_fullness:
            self.max_fullness_rules.update(custom_max_fullness)

        self.min_slope_dict = self.MIN_SLOPE_BY_DIAMETER.copy()
        if custom_min_slope_dict:
            self.min_slope_dict.update(custom_min_slope_dict)

    # ----------------------------------------------------------------------
    # 几何计算辅助函数
    # ----------------------------------------------------------------------
    @staticmethod
    def _theta_from_depth(D: float, h: float) -> float:
        if h <= 0:
            return 0.0
        if h >= D:
            return 2 * math.pi
        arg = 1 - 2 * h / D
        arg = max(-1.0, min(1.0, arg))
        return 2 * math.acos(arg)

    @staticmethod
    def _area_from_depth(D: float, h: float) -> float:
        if h <= 0:
            return 0.0
        if h >= D:
            return math.pi * D * D / 4.0
        theta = DrainagePipeDesigner._theta_from_depth(D, h)
        area = (D * D / 8.0) * (theta - math.sin(theta))
        # 防止浮点误差导致极小负值
        if area < 0 and area > -1e-12:
            area = 0.0
        return area

    @staticmethod
    def _wetted_perimeter(D: float, h: float) -> float:
        if h <= 0:
            return 0.0
        if h >= D:
            return math.pi * D
        theta = DrainagePipeDesigner._theta_from_depth(D, h)
        return (D / 2.0) * theta

    @staticmethod
    def _hydraulic_radius(D: float, h: float) -> float:
        A = DrainagePipeDesigner._area_from_depth(D, h)
        if A <= 0:
            return 0.0
        chi = DrainagePipeDesigner._wetted_perimeter(D, h)
        if chi <= 0:
            return 0.0
        return A / chi

    @staticmethod
    def print_optimal_solution(result: Optional[Dict]) -> None:
        if result:
            print("最优设计方案:")
            print(f"管径 D = {result['D']} mm")
            print(f"充满度 h/D = {result['h_D']}")
            print(f"坡度 i = {result['slope']} ({result['slope']*100:.3f}%)")
            print(f"流速 v = {result['velocity']} m/s")
            print(f"流量 Q = {result['Q']} L/s")
        else:
            print("未找到可行方案,请放宽约束或增大管径范围.")

    @staticmethod
    def print_all_solutions(solutions: Optional[List[Dict]]) -> None:
        if solutions:
            print("\n各管径可行方案:")
            for sol in solutions:
                print(
                    f"D={sol['D']}mm, h/D={sol['h_D']}, i={sol['slope']:.6f}, v={sol['velocity']}m/s"
                )
        else:
            print("\n未找到任何可行方案.")

    # ----------------------------------------------------------------------
    # 水力计算核心函数
    # ----------------------------------------------------------------------
    def velocity(self, D: float, h: float, slope: float) -> float:
        if h <= 0 or slope <= 0:
            return 0.0
        R = self._hydraulic_radius(D, h)
        if R <= 0:
            return 0.0
        try:
            v = (1.0 / self.n) * (R ** (2.0 / 3.0)) * math.sqrt(slope)
        except (ValueError, OverflowError):
            v = float("nan")
        return v

    def flow_rate(self, D: float, h: float, slope: float) -> float:
        A = self._area_from_depth(D, h)
        if A == 0:
            return 0.0
        v = self.velocity(D, h, slope)
        return A * v

    def required_slope(self, D: float, h: float, Q: float) -> float:
        A = self._area_from_depth(D, h)
        if A <= 0:
            return float("inf")
        R = self._hydraulic_radius(D, h)
        if R <= 0:
            return float("inf")
        try:
            denominator = A * (R ** (2.0 / 3.0))
        except (ValueError, OverflowError):
            return float("inf")
        if denominator <= 0:
            return float("inf")
        return (Q * self.n / denominator) ** 2

    # ----------------------------------------------------------------------
    # 规范约束查询
    # ----------------------------------------------------------------------
    def get_max_fullness(self, D_mm: int) -> float:
        rules = self.max_fullness_rules.get(self.pipe_type, [])
        for low, high, val in rules:
            if low <= D_mm <= high:
                return val
        return 0.75 if self.pipe_type == "污水" else 1.0

    def get_min_construction_slope(self, D_mm: int) -> float:
        return self.min_slope_dict.get(D_mm, self.default_min_slope)

    # ----------------------------------------------------------------------
    # 主设计接口
    # ----------------------------------------------------------------------
    def design(
        self,
        Q: float,
        D_min: int = 300,
        D_max: int = 1000,
        D_step: int = 100,
        hD_step: float = 0.01,
        check_velocity: bool = True,
        check_min_slope: bool = True,
        min_recommended_fullness: Optional[float] = None,
        optimization_criterion: str = "slope",
        return_all: bool = False,
    ) -> Union[List[Dict], Dict, None]:
        # 基础最小充满度(用户设定或实例默认)
        base_min_hD = (
            min_recommended_fullness
            if min_recommended_fullness is not None
            else self.min_recommended_fullness
        )

        Q_m3s = Q / 1000.0
        feasible_solutions = []

        D_mm = D_min
        while D_mm <= D_max:
            # 跳过已被淘汰的1300管径
            if D_mm == 1300:
                D_mm += D_step
                continue

            D_m = D_mm / 1000.0
            max_hD = self.get_max_fullness(D_mm)

            # 根据管径确定有效最小充满度
            if D_mm == 300:
                effective_min_hD = 0.0  # 300mm 管不限制充满度
            else:
                effective_min_hD = max(base_min_hD, 0.4)  # 其他管径 ≥ 0.4

            hD = max_hD
            best_for_this_diameter = None
            while hD >= effective_min_hD - 1e-9:
                h = hD * D_m
                i = self.required_slope(D_m, h, Q_m3s)
                if math.isinf(i) or math.isnan(i):
                    hD -= hD_step
                    continue

                v = self.velocity(D_m, h, i)
                if math.isnan(v):
                    hD -= hD_step
                    continue

                valid = True
                if check_velocity and (
                    v < self.min_velocity - 1e-9 or v > self.max_velocity + 1e-9
                ):
                    valid = False
                if check_min_slope:
                    min_slope_constr = self.get_min_construction_slope(D_mm)
                    if i < min_slope_constr - 1e-9:
                        valid = False

                if valid:
                    best_for_this_diameter = {
                        "D": D_mm,
                        "h_D": round(hD, 4),
                        "slope": round(i, 6),
                        "velocity": round(v, 3),
                        "Q": Q,
                    }
                    break

                hD -= hD_step

            if best_for_this_diameter:
                feasible_solutions.append(best_for_this_diameter)

            D_mm += D_step

        if not feasible_solutions:
            return None if not return_all else []

        if not return_all:
            if optimization_criterion == "diameter":
                best = min(feasible_solutions, key=lambda x: (x["D"], x["slope"]))
            elif optimization_criterion == "slope":
                best = min(feasible_solutions, key=lambda x: (x["slope"], x["D"]))
            else:
                best = min(feasible_solutions, key=lambda x: (x["D"], x["slope"]))
            return best
        else:
            return feasible_solutions


if __name__ == "__main__":
    designer = DrainagePipeDesigner(
        n=0.009, pipe_type="污水", min_recommended_fullness=0.2
    )
    optimal = designer.design(
        Q=8.72, D_min=300, D_max=600, D_step=100, return_all=False
    )
    DrainagePipeDesigner.print_optimal_solution(optimal)

    all_solutions = designer.design(
        Q=8.72, D_min=300, D_max=600, D_step=100, return_all=True
    )
    DrainagePipeDesigner.print_all_solutions(all_solutions)
