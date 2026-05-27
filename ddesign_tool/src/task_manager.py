"""
模块3:任务管理与调度

功能:管道设计任务管理,包括单管道水力设计、高程计算和任务调度
"""

from typing import Dict, List, Optional, Tuple

from _logging import get_logger
from design_engine import DrainagePipeDesigner

_log = get_logger(__name__)


def design_pipe(
    designer: DrainagePipeDesigner,
    Q_lps: float,
    min_diameter: int = 0,
    max_attempts: int = 10,
    optimization_criterion: str = "slope",
    D_max: int = 1500,
) -> Optional[Dict]:
    """
    对单个流量进行水力设计,支持并联.
    返回字典包含:D, h_D, slope, velocity, Q_design, parallel
    """
    for parallel in range(1, max_attempts + 1):
        per_pipe_Q = Q_lps / parallel
        all_solutions = designer.design(
            Q=per_pipe_Q,
            return_all=True,
            optimization_criterion=optimization_criterion,
            D_max=D_max,
        )
        if not all_solutions:
            continue

        # 过滤出管径 ≥ min_diameter 的方案
        valid_solutions = [sol for sol in all_solutions if sol["D"] >= min_diameter]
        if not valid_solutions:
            continue

        # 根据优化准则排序
        if optimization_criterion == "diameter":
            valid_solutions.sort(key=lambda x: (x["D"], x["slope"]))
        else:  # "slope"
            valid_solutions.sort(key=lambda x: (x["slope"], x["D"]))

        best = valid_solutions[0]
        best["h_D"] = round(best["h_D"], 3)
        best["slope"] = round(best["slope"], 6)
        best["velocity"] = round(best["velocity"], 3)
        best["parallel"] = parallel
        best["Q_design"] = Q_lps
        return best

    return None


def process_pipe(
    idx: int,
    pipe: Dict,
    upstream_map: Dict[int, List[int]],
    designs: List[Optional[Dict]],
    elevations: List[Optional[Dict]],
    designer: DrainagePipeDesigner,
    initial_cover: float = 1.5,
) -> Tuple[Optional[Dict], Optional[Dict]]:
    """
    对单根管道进行水力设计和高程计算,返回 (design_dict, elevation_dict)
    其中 elevation_dict 包含:
        start_invert, end_invert, start_water, end_water,
        start_cover, end_cover, start_cover_depth, end_cover_depth,
        connection, lift_diff, lift_cover
    """
    # 1. 累计流量
    upstream_flows = []
    upstream_max_diameter = 0
    for up in upstream_map[idx]:
        if designs[up] is None:
            return None, None
        upstream_flows.append(designs[up]["Q_design"])
        up_d = designs[up]["D"]
        if up_d > upstream_max_diameter:
            upstream_max_diameter = up_d
    cum_flow = pipe["q_local"] + sum(upstream_flows)

    # 2. 水力设计
    design = design_pipe(designer, cum_flow, min_diameter=upstream_max_diameter)
    if design is None:
        print(f"错误:管道 {pipe['source']} 在尝试 {10} 根并联后仍无解")
        return None, None

    D_m = design["D"] / 1000.0
    h_D = design["h_D"]
    slope = design["slope"]
    length = pipe["length"]
    ground_start = pipe["ground_start"]
    ground_end = pipe["ground_end"]

    # 3. 计算候选起点管内底(无提升时的设计值)
    upstream_idxs = upstream_map[idx]
    if not upstream_idxs:
        # 起始管道:按初始覆土深度控制
        original_start_invert = ground_start - (initial_cover + D_m)
        connection = "起始管道"
    else:
        up_infos = []
        for up in upstream_idxs:
            up_design = designs[up]
            up_elev = elevations[up]
            if up_design is None or up_elev is None:
                continue
            up_D = up_design["D"] / 1000.0
            up_h = up_design["h_D"]
            up_invert_end = up_elev["end_invert"]
            up_water_end = up_elev["end_water"]
            up_parallel = up_design.get("parallel", 1)
            up_infos.append(
                {
                    "D": up_D,
                    "h": up_h,
                    "invert_end": up_invert_end,
                    "water_end": up_water_end,
                    "parallel": up_parallel,
                }
            )

        if not up_infos:
            original_start_invert = ground_start - (initial_cover + D_m)
            connection = "异常(上游无数据)"
        else:
            # 检查下游管径是否小于上游单根管径
            if any(up["D"] > D_m for up in up_infos):
                raise ValueError(f"管道 {pipe['source']} 下游管径小于上游管径,不允许!")

            candidates = []
            for up in up_infos:
                if up["parallel"] > 1:
                    # 并联上游:管底平接
                    candidates.append(up["invert_end"])
                else:
                    # 单管上游
                    if abs(up["D"] - D_m) < 1e-6:
                        # 水面平接
                        candidates.append(up["water_end"] - D_m * h_D)
                    else:
                        # 管顶平接
                        candidates.append((up["invert_end"] + up["D"]) - D_m)

            original_start_invert = min(candidates)

            # 连接方式描述
            if any(up["parallel"] > 1 for up in up_infos):
                connection = "管底平接(并联上游)"
            else:
                if all(abs(up["D"] - D_m) < 1e-6 for up in up_infos):
                    connection = "水面平接"
                else:
                    connection = "管顶平接"

    # 4. 污水提升处理(lift_cover 为提升后的覆土深度)
    lift_cover = pipe.get("lift_cover", 0.0)
    if lift_cover > 0:
        forced_start_invert = ground_start - (lift_cover + D_m)
        diff = forced_start_invert - original_start_invert  # 埋深差值
        start_invert = forced_start_invert
    else:
        diff = 0.0
        start_invert = original_start_invert

    # 5. 计算终点管内底
    end_invert = start_invert - slope * length

    # 6. 水深、水面、埋深、覆土深度
    depth = D_m * h_D
    start_water = start_invert + depth
    end_water = end_invert + depth

    start_cover = ground_start - start_invert  # 埋深
    end_cover = ground_end - end_invert
    start_cover_depth = start_cover - D_m  # 覆土深度
    end_cover_depth = end_cover - D_m

    elevation = {
        "start_invert": round(start_invert, 3),
        "end_invert": round(end_invert, 3),
        "start_water": round(start_water, 3),
        "end_water": round(end_water, 3),
        "start_cover": round(start_cover, 3),
        "end_cover": round(end_cover, 3),
        "start_cover_depth": round(start_cover_depth, 3),
        "end_cover_depth": round(end_cover_depth, 3),
        "connection": connection,
        "lift_diff": round(diff, 3),
        "lift_cover": lift_cover,
    }
    return design, elevation


if __name__ == "__main__":
    print("任务管理模块测试...")
    # 测试代码可以在这里添加
