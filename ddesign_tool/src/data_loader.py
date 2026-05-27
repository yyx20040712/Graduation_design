"""
模块1:数据输入与解析

功能:读取Excel数据文件,解析管道数据,构建数据结构
"""

import os
from typing import Any, Dict, List, Tuple

import pandas as pd
from _logging import get_logger

_log = get_logger(__name__)


def read_pipe_data(excel_path: str) -> List[Dict[str, Any]]:
    """
    读取所有非'计算结果'/'管道统计'的工作表.

    支持两种列格式:
      8列 (污水): 起点编号, 终点编号, 长度(m), 起点地面标高(m), 终点地面标高(m),
                  本段汇水面积, 本段产生流量(L/s), 污水提升(m)
      6列 (雨水): 起点编号, 终点编号, 长度(m), 起点地面标高(m), 终点地面标高(m),
                  本段汇水面积(m²)
    第8列(如存在)表示提升后覆土深度(0=不提升).
    """
    if not os.path.exists(excel_path):
        raise FileNotFoundError(f"文件不存在:{excel_path}")

    all_pipes = []
    xl = pd.ExcelFile(excel_path)
    skip_sheets = {"计算结果", "管道统计"}
    for sheet_name in xl.sheet_names:
        if sheet_name in skip_sheets:
            continue
        df = pd.read_excel(excel_path, sheet_name=sheet_name, header=None, dtype=str)
        if df.empty:
            print(f"警告:工作表 {sheet_name} 为空,已跳过")
            continue

        for idx, row in df.iterrows():
            if idx < 1:
                continue
            first_col = row.iloc[0]
            if pd.isna(first_col) or str(first_col).strip() == "":
                break

            row_list = row.tolist()
            ncols = len(row_list)
            if ncols < 6:
                print(f"警告:工作表 {sheet_name} 第 {idx+1} 行数据列不足6列,已跳过")
                continue
            try:
                # 8列(污水) 或 6列(雨水) 兼容
                pipe = {
                    "source": f"{sheet_name}_第{idx+1}行",
                    "start": str(row_list[0]).strip(),
                    "end": str(row_list[1]).strip(),
                    "length": float(row_list[2]) if pd.notna(row_list[2]) else 0.0,
                    "ground_start": (
                        float(row_list[3]) if pd.notna(row_list[3]) else 0.0
                    ),
                    "ground_end": float(row_list[4]) if pd.notna(row_list[4]) else 0.0,
                    "catchment_area": (
                        float(row_list[5]) if pd.notna(row_list[5]) else 0.0
                    ),
                    "q_local": (
                        float(row_list[6])
                        if ncols >= 7 and pd.notna(row_list[6])
                        else 0.0
                    ),
                    "lift_cover": (
                        float(row_list[7])
                        if ncols >= 8 and pd.notna(row_list[7]) and row_list[7]
                        else 0.0
                    ),
                }
                all_pipes.append(pipe)
            except ValueError as e:
                print(f"错误:工作表 {sheet_name} 第 {idx+1} 行数据格式不正确 - {e}")
                continue
    return all_pipes


def build_pipe_dependency(
    pipes: List[Dict],
) -> Tuple[Dict[int, List[int]], Dict[int, List[int]], List[int]]:
    """构建上下游映射及入度"""
    n = len(pipes)
    start_to_pipes = {}
    end_to_pipes = {}
    for idx, p in enumerate(pipes):
        start_to_pipes.setdefault(p["start"], []).append(idx)
        end_to_pipes.setdefault(p["end"], []).append(idx)

    upstream_map = {i: [] for i in range(n)}
    downstream_map = {i: [] for i in range(n)}
    indegree = [0] * n

    for i, p in enumerate(pipes):
        up_idxs = end_to_pipes.get(p["start"], [])
        for up in up_idxs:
            if up != i:
                upstream_map[i].append(up)
                downstream_map[up].append(i)
                indegree[i] += 1
    return upstream_map, downstream_map, indegree


def topological_sort(
    pipes: List[Dict], downstream_map: Dict[int, List[int]], indegree: List[int]
) -> List[int]:
    """拓扑排序,返回计算顺序"""
    indegree_copy = indegree[:]
    from collections import deque

    q = deque([i for i in range(len(pipes)) if indegree_copy[i] == 0])
    order = []
    while q:
        u = q.popleft()
        order.append(u)
        for v in downstream_map[u]:
            indegree_copy[v] -= 1
            if indegree_copy[v] == 0:
                q.append(v)
    if len(order) != len(pipes):
        raise RuntimeError("管网中存在环路,请检查起点/终点编号.")
    return order


if __name__ == "__main__":
    # 测试代码
    import sys

    if len(sys.argv) > 1:
        test_file = sys.argv[1]
        try:
            pipes = read_pipe_data(test_file)
            print(f"成功读取 {len(pipes)} 条管道数据")
            upstream_map, downstream_map, indegree = build_pipe_dependency(pipes)
            order = topological_sort(pipes, downstream_map, indegree)
            print(f"拓扑排序完成,计算顺序:{order}")
        except Exception as e:
            print(f"错误:{e}")
    else:
        print("使用方法:python data_loader.py <excel文件路径>")
