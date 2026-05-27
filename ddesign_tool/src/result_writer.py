"""
模块4:结果输出

功能:将计算结果写入Excel文件,包含管道统计和跌水井统计
"""

import os
from typing import Dict, List, Optional

import pandas as pd
from _logging import get_logger

_log = get_logger(__name__)


def write_results(
    excel_path: str,
    pipes: List[Dict],
    designs: List[Optional[Dict]],
    elevations: List[Optional[Dict]],
    drop_well_threshold: float = 1.0,
):
    """将计算结果写入 Excel,包含管道统计(按管径汇总长度)和跌水井统计"""
    # 构建管道索引到下游管道索引的映射(用于跌水计算)
    start_to_pipes = {}
    end_to_pipes = {}
    for idx, p in enumerate(pipes):
        start_to_pipes.setdefault(p["start"], []).append(idx)
        end_to_pipes.setdefault(p["end"], []).append(idx)

    output_rows = []
    pipe_stats = {}  # 按管径统计总长度
    total_drop_wells = 0  # 跌水井总数

    for i, pipe in enumerate(pipes):
        design = designs[i]
        elev = elevations[i]

        upstream_inflow = (
            design["Q_design"] - pipe["q_local"] if design is not None else None
        )

        # 计算末端跌水高度(基于水面差)
        drop_height_record = None
        set_drop_well = 0
        downstream_idx_list = start_to_pipes.get(pipe["end"], [])
        if downstream_idx_list and elev is not None:
            downstream_idx = downstream_idx_list[0]  # 树状管网每个终点只有一个下游
            ds_elev = elevations[downstream_idx]
            if ds_elev is not None:
                # 检查下游管道是否有多个上游(即是否为汇流点)
                upstream_count = len(
                    end_to_pipes.get(pipes[downstream_idx]["start"], [])
                )
                if upstream_count > 1:
                    # 使用水面高度差
                    drop_height = elev["end_water"] - ds_elev["start_water"]
                    if drop_height > 0:
                        drop_height_record = round(drop_height, 3)
                        if drop_height > drop_well_threshold:
                            set_drop_well = 1
                            total_drop_wells += 1

        base_cols = {
            "起点编号": pipe["start"],
            "终点编号": pipe["end"],
            "长度(m)": pipe["length"],
            "起点地面标高(m)": pipe["ground_start"],
            "终点地面标高(m)": pipe["ground_end"],
            "本段汇水面积": pipe["catchment_area"],
            "本段产生流量(L/s)": pipe["q_local"],
            "上游汇入流量(L/s)": (
                round(upstream_inflow, 3) if upstream_inflow is not None else None
            ),
        }

        if design is None:
            extra_cols = {
                "设计流量(L/s)": None,
                "管径(mm)": None,
                "充满度": None,
                "坡度": None,
                "流速(m/s)": None,
                "并联数": None,
                "污水泵站扬程(m)": None,
                "主动跌水(m)": None,
                "末端跌水高度(m)": None,
                "是否设置跌水井": None,
                "起点管内底(m)": None,
                "终点管内底(m)": None,
                "起点水面(m)": None,
                "终点水面(m)": None,
                "起点埋深(m)": None,
                "起点覆土深度(m)": None,
                "终点埋深(m)": None,
                "终点覆土深度(m)": None,
                "连接方式": None,
                "来源": pipe["source"],
            }
        else:
            D = design["D"]
            parallel = design.get("parallel", 1)
            total_length = pipe["length"] * parallel  # 该逻辑管段总长度(并联数倍)

            # 统计管径总长度
            if D not in pipe_stats:
                pipe_stats[D] = 0.0
            pipe_stats[D] += total_length

            diff = elev["lift_diff"]
            pump_head = diff if diff > 0 else 0.0
            drop = -diff if diff < 0 else 0.0

            extra_cols = {
                "设计流量(L/s)": round(design["Q_design"], 3),
                "管径(mm)": D,
                "充满度": design["h_D"],
                "坡度": design["slope"],
                "流速(m/s)": design["velocity"],
                "并联数": parallel,
                "污水泵站扬程(m)": round(pump_head, 3),
                "主动跌水(m)": round(drop, 3),
                "末端跌水高度(m)": drop_height_record,
                "是否设置跌水井": set_drop_well,
                "起点管内底(m)": elev["start_invert"],
                "终点管内底(m)": elev["end_invert"],
                "起点水面(m)": elev["start_water"],
                "终点水面(m)": elev["end_water"],
                "起点埋深(m)": elev["start_cover"],
                "起点覆土深度(m)": elev["start_cover_depth"],
                "终点埋深(m)": elev["end_cover"],
                "终点覆土深度(m)": elev["end_cover_depth"],
                "连接方式": elev["connection"],
                "来源": pipe["source"],
            }

        row = {**base_cols, **extra_cols}
        output_rows.append(row)

    # 添加总计行(仅显示跌水井总数)
    total_row = {col: "" for col in output_rows[0].keys()}
    total_row["起点编号"] = "总计"
    total_row["是否设置跌水井"] = total_drop_wells
    output_rows.append(total_row)

    df_out = pd.DataFrame(output_rows)

    # 构建管道统计表(按管径汇总长度)
    stat_rows = []
    for D in sorted(pipe_stats.keys()):
        stat_rows.append(
            {
                "管径(mm)": D,
                "总长度(m)": round(pipe_stats[D], 2),
            }
        )
    df_stat = pd.DataFrame(stat_rows)

    # 写入独立输出文件 (避免 pd.ExcelWriter append 模式破坏原始数据)
    from datetime import datetime

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base, ext = os.path.splitext(excel_path)
    out_path = f"{base}_计算结果_{ts}{ext}"
    with pd.ExcelWriter(out_path, engine="openpyxl", mode="w") as writer:
        df_out.to_excel(writer, sheet_name="计算结果", index=False)
        df_stat.to_excel(writer, sheet_name="管道统计", index=False)
    print(
        f'结果已写入 {out_path} 的"计算结果"和"管道统计"工作表,共 {len(output_rows)-1} 条记录(不含总计).'
    )
    return out_path


if __name__ == "__main__":
    print("结果输出模块测试...")
    # 测试代码可以在这里添加
