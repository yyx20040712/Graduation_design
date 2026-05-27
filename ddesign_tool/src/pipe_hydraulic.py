"""
pipe_hydraulic.py — 管网水力高程计算入口 (封装旧版模块)

调用旧版 data_loader → design_engine → task_manager → result_writer
完整流程, 独立于节点 DAG.
"""

import configparser
import os
from typing import Optional

from _logging import get_logger
from data_loader import (
    build_pipe_dependency,
    read_pipe_data,
    topological_sort,
)
from design_engine import DrainagePipeDesigner
from result_writer import write_results
from task_manager import process_pipe

_log = get_logger(__name__)


def _load_config() -> dict:
    """从 config.ini 读取设计参数"""
    from _paths import get_config_path

    config_path = get_config_path()
    cfg = configparser.ConfigParser()
    defaults = {
        "manning_n": 0.014,
        "pipe_type": "污水",
        "min_velocity": 0.6,
        "max_velocity": 1.0,
        "default_min_slope": 0.001,
        "min_recommended_fullness": 0.1,
        "initial_cover": 1.5,
        "drop_well_threshold": 1.0,
        "optimization_criterion": "slope",
        "D_max": 1500,
        "max_parallel_attempts": 10,
        # 流量推算参数 (Excel 中 q_local 为空时使用):
        "sewage_specific_flow": 0.85,  # 污水比流量 L/(s·ha)
        "runoff_coefficient": 0.6,  # 雨水径流系数
        "rainfall_intensity": 2.5,  # 暴雨强度 L/(s·ha)
    }
    if os.path.exists(config_path):
        cfg.read(config_path, encoding="utf-8")
        dp = cfg["design_parameters"] if "design_parameters" in cfg else {}
        for k in defaults:
            if k in dp:
                try:
                    defaults[k] = float(dp[k])
                except ValueError:
                    pass
    return defaults


def run_pipe_hydraulic(
    excel_path: str, pipe_type: str = "污水", log_callback=None
) -> Optional[str]:
    """执行管网水力高程计算

    Args:
        excel_path: 管网 Excel 文件路径
        pipe_type: "污水" 或 "雨水"
        log_callback: 日志回调 (msg: str) -> None

    Returns:
        成功时返回 Excel 路径, 失败返回 None
    """

    def log(msg: str):
        if log_callback:
            log_callback(msg)

    log(f"[{pipe_type}管网计算] 开始: {os.path.basename(excel_path)}")

    cfg = _load_config()
    cfg["pipe_type"] = pipe_type  # 覆盖配置文件中的类型

    try:
        pipes = read_pipe_data(excel_path)
    except Exception as e:
        log(f"[管网计算] 读取失败: {e}")
        return None

    if not pipes:
        log(
            "[管网计算] 未读取到有效管段数据 — 请确认 Excel 中有非输出 sheet 且每行 8 列"
        )
        return None

    log(f"[管网计算] 读取 {len(pipes)} 段管道")

    # 补充流量计算: Excel 中空缺的 q_local (NaN) → 由汇水面积推算
    # 污水: q = 面积(ha) × 比流量(L/(s·ha))
    # 雨水: q = 面积(ha) × 径流系数 × 暴雨强度 / 折算系数
    q0 = cfg.get("sewage_specific_flow", 0.85)  # 污水比流量 L/(s·ha)
    runoff_coef = cfg.get("runoff_coefficient", 0.6)
    rain_intensity = cfg.get("rainfall_intensity", 2.5)  # L/(s·ha) — 重现期1年
    computed = 0
    for p in pipes:
        if p["q_local"] <= 0 and p["catchment_area"] > 0:
            area_ha = p["catchment_area"] / 10000.0  # m² → ha
            if pipe_type == "雨水":
                p["q_local"] = area_ha * runoff_coef * rain_intensity
            else:
                p["q_local"] = area_ha * q0
            computed += 1
    if computed > 0:
        log(f"[管网计算] 从汇水面积推算 {computed} 段流量 (比流量={q0} L/(s·ha))")

    upstream_map, downstream_map, indegree = build_pipe_dependency(pipes)
    order = topological_sort(pipes, downstream_map, indegree)
    log(f"[管网计算] 拓扑排序完成, 计算 {len(order)} 段")

    designer = DrainagePipeDesigner(
        n=cfg["manning_n"],
        pipe_type=cfg["pipe_type"],
        min_velocity=cfg["min_velocity"],
        max_velocity=cfg["max_velocity"],
        default_min_slope=cfg["default_min_slope"],
        min_recommended_fullness=cfg["min_recommended_fullness"],
    )

    # 5. 逐段计算
    designs = [None] * len(pipes)
    elevations = [None] * len(pipes)

    for idx in order:
        design, elev = process_pipe(
            idx,
            pipes[idx],
            upstream_map,
            designs,
            elevations,
            designer,
            initial_cover=cfg["initial_cover"],
        )
        designs[idx] = design
        elevations[idx] = elev
        if design:
            log(
                f"  第{idx+1}段 DN{design['D']} i={design['slope']:.4f} "
                f"v={design['velocity']:.2f}m/s 并联={design.get('parallel',1)}"
            )
        else:
            log(f"  第{idx+1}段 设计失败")

    # 6. 写入结果
    try:
        out_path = write_results(
            excel_path,
            pipes,
            designs,
            elevations,
            drop_well_threshold=cfg["drop_well_threshold"],
        )
        log(f"[管网计算] 已写入: {os.path.basename(out_path)}")
        return out_path
    except Exception as e:
        log(f"[管网计算] 写入失败: {e}")
        return None
