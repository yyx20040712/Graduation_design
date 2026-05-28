"""
layout_engine.py — 列式自动布局算法 (v5.4)

节点端口在左右两侧, 列式布局(左→右)比 Sugiyama(上→下)更适合.
纯算法, 零 UI 依赖 — 输入邻接表, 输出 {node_id: (x, y)}.
"""

from __future__ import annotations

import math
from collections import deque
from typing import Dict, List, Tuple

# ── 布局参数 ──
COL_SPACING = 320   # 列间距 (适应横向连线)
ROW_SPACING = 130   # 行间距
START_X = 50
START_Y = 50
MAX_PER_COLUMN = 6   # 每列最多节点数 (端口在左右, 列式更紧凑)


def column_layout(
    node_ids: List[str],
    successors: Dict[str, List[str]],
    predecessors: Dict[str, List[str]],
) -> Dict[str, Tuple[float, float]]:
    """列式布局: 主链路分列, 分支延展到右侧新列.

    算法:
      1. 拓扑排序 → 确定处理顺序
      2. 主链路节点依次填入列, 每列最多 MAX_PER_COLUMN 个
      3. 列内垂直排列 (端口在左右, 流水方向 = 左→右)
      4. 分支节点 (多入度或多出度) 分配到新列, 避免交叉

    Args:
        node_ids: 所有节点 ID 列表
        successors: {node_id: [下游节点ID列表]}
        predecessors: {node_id: [上游节点ID列表]}

    Returns:
        {node_id: (x, y)}  世界坐标

    Example (20 nodes → 4 columns):
        Col 0     Col 1     Col 2     Col 3
        N1  ───→  N6  ───→  N11 ───→  N16
        N2        N7        N12       N17
        N3        N8        N13       N18
        N4        N9        N14       N19
        N5  ───→  N10 ───→  N15 ───→  N20
    """
    if not node_ids:
        return {}

    n_total = len(node_ids)

    # ── 拓扑排序 ──
    indegree = {n: len(predecessors.get(n, [])) for n in node_ids}
    q = deque([n for n in node_ids if indegree.get(n, 0) == 0])
    topo: List[str] = []
    while q:
        u = q.popleft()
        topo.append(u)
        for v in successors.get(u, []):
            indegree[v] -= 1
            if indegree[v] == 0:
                q.append(v)
    for n in node_ids:
        if n not in topo:
            topo.append(n)

    # ── 列分配 ──
    # 动态计算每列大小: 使列数 ≈ sqrt(n) 或 4-6 列
    n_cols = max(2, min(8, math.ceil(n_total / MAX_PER_COLUMN)))
    per_col = max(1, math.ceil(n_total / n_cols))

    # 主链路: 沿拓扑顺序填入列
    column: Dict[str, int] = {}
    col_pos: Dict[str, float] = {}  # 列内垂直位置
    col_counts = [0] * n_cols  # 每列已用槽位数
    col_last_row = [0.0] * n_cols  # 每列最后一个节点位置

    for nid in topo:
        preds = predecessors.get(nid, [])
        succs = successors.get(nid, [])

        # 确定目标列
        if not preds:
            # 根节点 → 第 0 列
            target_col = 0
        elif len(preds) == 1 and col_counts[column.get(preds[0], 0)] < per_col:
            # 单上游, 上游列还有空间 → 同列
            target_col = column.get(preds[0], 0)
        elif len(preds) >= 1:
            # 多上游 (合并节点) 或上游列满 → 取上游最大列 + 1
            max_pred_col = max(column.get(p, 0) for p in preds)
            target_col = min(max_pred_col + 1, n_cols - 1)
        else:
            target_col = 0

        # 如果目标列已满, 移到下一列
        while target_col < n_cols and col_counts[target_col] >= per_col:
            target_col += 1
        if target_col >= n_cols:
            target_col = n_cols - 1

        column[nid] = target_col
        col_pos[nid] = float(col_counts[target_col])
        col_counts[target_col] += 1

    # ── 坐标计算 ──
    positions: Dict[str, Tuple[float, float]] = {}
    for nid in node_ids:
        col = column.get(nid, 0)
        row = col_pos.get(nid, 0.0)
        x = START_X + col * COL_SPACING
        y = START_Y + row * ROW_SPACING
        positions[nid] = (x, y)

    return positions


# ── 别名, 保持向后兼容 ──
sugiyama_layout = column_layout
