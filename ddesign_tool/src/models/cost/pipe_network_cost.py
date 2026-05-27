"""
pipe_network_cost.py — 管网工程概算

基于「计算结果」sheet 逐段计算管道造价,包括:
  - 管道材料+铺设 (综合单价)
  - 沟槽土方开挖与回填
  - 施工机械台班 (挖掘机、起重机、载重汽车)
  - 人工工时 (技工+普工)
  - 检查井摊销
  - 提升泵站 (如有)

数据来源: 2019地方定额第五册 + GB50500-2013
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import pandas as pd

from .unit_prices import CIVIL, get_pipe_price

from _logging import get_logger

_log = get_logger(__name__)

# ── 模块级日志 ──
# ═══════════════════════════════════════════════
# 定额参考数据 (2019地方定额第五册)
# ═══════════════════════════════════════════════

# 管道铺设人工+机械消耗 (工日/10m, 台班/10m) — 按管径分
_PIPE_LABOR_MACHINE = {
    # 管径: (技工/10m, 普工/10m, 汽车起重机/10m, 载重汽车/10m)
    300: (2.1, 4.2, 0.02, 0.03),
    400: (2.5, 5.0, 0.03, 0.04),
    500: (3.0, 6.0, 0.04, 0.05),
    600: (3.5, 7.0, 0.05, 0.06),
    700: (4.0, 8.0, 0.06, 0.08),
    800: (4.5, 9.0, 0.07, 0.10),
    900: (5.0, 10.0, 0.08, 0.12),
    1000: (5.6, 11.2, 0.09, 0.14),
    1100: (6.2, 12.4, 0.10, 0.16),
    1200: (6.8, 13.6, 0.12, 0.18),
    1400: (7.8, 15.6, 0.15, 0.22),
    1500: (8.5, 17.0, 0.17, 0.25),
}

# 人工单价 (元/工日) — 地方2019定额综合工日
LABOR_PRICE = 128.0  # 综合工日 (普工+技工加权)

# 机械台班单价 (元/台班)
MACHINE_PRICE = {
    "excavator": 2800.0,  # 挖掘机1m³
    "crane_truck": 1800.0,  # 汽车起重机12t
    "truck": 1200.0,  # 载重汽车8t
}

# 检查井综合单价 (元/座) — 按管径
_MANHOLE_PRICE = {
    300: 3500,
    400: 4200,
    500: 5000,
    600: 6000,
    700: 7200,
    800: 8500,
    900: 10000,
    1000: 12000,
    1100: 14000,
    1200: 16000,
    1400: 20000,
    1500: 24000,
}

# 提升泵站参考造价
PUMP_STATION_BASE = 70.0  # 万元 (基础造价)
PUMP_STATION_PER_METER = 0.5  # 万元/m (每米扬程增加)


@dataclass
class PipeSegmentCost:
    """单段管道造价明细"""

    seq: int = 0
    start_node: str = ""
    end_node: str = ""
    diameter: int = 0  # mm
    length: float = 0.0  # m
    depth_start: float = 0.0  # 起点埋深 m
    depth_end: float = 0.0  # 终点埋深 m
    slope: float = 0.0  # 坡度

    # 分项造价 (元)
    pipe_cost: float = 0.0  # 管道材料+铺设
    earthwork_cost: float = 0.0  # 土方开挖+回填
    machine_cost: float = 0.0  # 机械台班
    labor_cost: float = 0.0  # 人工费
    manhole_cost: float = 0.0  # 检查井摊销
    total: float = 0.0  # 合计


@dataclass
class PipeNetworkEstimate:
    """管网工程概算总表"""

    pipe_type: str = "污水"
    total_length: float = 0.0  # 总管长 m
    total_pipe_cost: float = 0.0  # 管道总价 元
    total_earthwork: float = 0.0  # 土方总价 元
    total_machine: float = 0.0  # 机械总价 元
    total_labor: float = 0.0  # 人工总价 元
    total_manhole: float = 0.0  # 检查井总价 元
    pump_station_cost: float = 0.0  # 提升泵站 元
    grand_total: float = 0.0  # 总造价 元
    grand_total_wan: float = 0.0  # 总造价 万元

    # 按管径汇总
    by_diameter: Dict[int, float] = field(default_factory=dict)  # {管径: 总长度m}
    segments: List[PipeSegmentCost] = field(default_factory=list)

    def summary_lines(self) -> List[str]:
        """生成摘要行列表"""
        lines = [
            "═══ 管网工程概算 ═══",
            f"管网类型: {self.pipe_type}",
            f"管道总长: {self.total_length:.0f} m",
            "",
            "  ── 分项造价 ──",
            f"  管道材料+铺设: {self.total_pipe_cost/10000:.1f} 万元",
            f"  土方开挖回填: {self.total_earthwork/10000:.1f} 万元",
            f"  施工机械台班: {self.total_machine/10000:.1f} 万元",
            f"  人工工时:     {self.total_labor/10000:.1f} 万元",
            f"  检查井:       {self.total_manhole/10000:.1f} 万元",
        ]
        if self.pump_station_cost > 0:
            lines.append(f"  提升泵站:     {self.pump_station_cost/10000:.1f} 万元")
        lines.append(f"  ───────────────")
        lines.append(f"  总造价:       {self.grand_total_wan:.1f} 万元")
        lines.append(
            f"  单位造价:     {self.grand_total/self.total_length:.0f} 元/m"
            if self.total_length > 0
            else ""
        )
        lines.append("")
        lines.append("  ── 按管径汇总 ──")
        for d in sorted(self.by_diameter.keys()):
            lines.append(f"  DN{d}: {self.by_diameter[d]:.0f} m")
        return [l for l in lines if l]

    def to_cost_items(self) -> List[Dict]:
        """转换为 cost_estimator 兼容的 BOQ 格式"""
        items = []
        items.append(
            {
                "name": "管道铺设(含材料)",
                "total": self.total_pipe_cost,
                "category": "建筑工程",
            }
        )
        items.append(
            {"name": "土方工程", "total": self.total_earthwork, "category": "建筑工程"}
        )
        items.append(
            {"name": "施工机械", "total": self.total_machine, "category": "建筑工程"}
        )
        items.append(
            {"name": "人工", "total": self.total_labor, "category": "建筑工程"}
        )
        items.append(
            {"name": "检查井", "total": self.total_manhole, "category": "建筑工程"}
        )
        if self.pump_station_cost > 0:
            items.append(
                {
                    "name": "提升泵站",
                    "total": self.pump_station_cost,
                    "category": "设备购置",
                }
            )
        return items


# ═══════════════════════════════════════════════
# 主估算函数
# ═══════════════════════════════════════════════


def estimate_pipe_network(pipe_node) -> Optional[PipeNetworkEstimate]:
    """从管网节点估算工程总造价

    Args:
        pipe_node: PipeNetworkNode 实例 (需已加载 Excel)

    Returns:
        PipeNetworkEstimate 或 None (如果无法加载数据)
    """
    excel_path = getattr(pipe_node, "_excel_path", "")
    if not excel_path or not os.path.exists(excel_path):
        _log.warning("管网Excel路径无效或文件不存在: %s", excel_path or "(空)")
        return None

    try:
        df = pd.read_excel(excel_path, sheet_name="计算结果")
    except Exception as e:
        _log.error("读取管网Excel失败 [%s]: %s", excel_path, e)
        return None

    est = PipeNetworkEstimate(
        pipe_type=getattr(pipe_node, "_pipe_type", "污水"),
    )

    # ── 逐段计算 ──
    skipped = 0
    for idx, row in df.iterrows():
        seg = _calc_segment(row, idx + 1)
        if seg.length <= 0:
            skipped += 1
            continue
        est.segments.append(seg)
        est.total_pipe_cost += seg.pipe_cost
        est.total_earthwork += seg.earthwork_cost
        est.total_machine += seg.machine_cost
        est.total_labor += seg.labor_cost
        est.total_manhole += seg.manhole_cost
        est.total_length += seg.length
        est.by_diameter[seg.diameter] = (
            est.by_diameter.get(seg.diameter, 0) + seg.length
        )

    # ── 提升泵站 (必须在 grand_total 之前计算) ──
    _estimate_pump_station(pipe_node, est)

    est.grand_total = (
        est.total_pipe_cost
        + est.total_earthwork
        + est.total_machine
        + est.total_labor
        + est.total_manhole
        + est.pump_station_cost
    )
    est.grand_total_wan = est.grand_total / 10000.0

    _log.info(
        "管网概算完成: %d段, 总长%.0fm, 总造价%.1f万元, 泵站%.1f万元",
        len(est.segments),
        est.total_length,
        est.grand_total_wan,
        est.pump_station_cost / 10000,
    )
    if skipped > 0:
        _log.warning("跳过 %d 段长度为零或无效的管道", skipped)

    return est


def _calc_segment(row: pd.Series, seq: int) -> PipeSegmentCost:
    """计算单段管道造价"""
    seg = PipeSegmentCost(seq=seq)

    # 管径
    if "管径(mm)" in row.index:
        seg.diameter = int(row["管径(mm)"]) if pd.notna(row["管径(mm)"]) else 300
    elif "管径" in row.index:
        seg.diameter = int(row["管径"]) if pd.notna(row["管径"]) else 300
    else:
        _log.warning("第%d段: 未找到管径列,默认DN300", seq)
        seg.diameter = 300

    # 长度
    if "长度(m)" in row.index:
        seg.length = float(row["长度(m)"]) if pd.notna(row["长度(m)"]) else 0
    elif "长度" in row.index:
        seg.length = float(row["长度"]) if pd.notna(row["长度"]) else 0
    else:
        _log.warning("第%d段: 未找到长度列,跳过", seq)

    if seg.length <= 0:
        return seg

    # 起点/终点
    for col_s, col_e, attr_s, attr_e in [
        ("起点编号", "终点编号", "start_node", "end_node"),
        ("起点", "终点", "start_node", "end_node"),
    ]:
        if col_s in row.index:
            seg.start_node = str(row[col_s]) if pd.notna(row[col_s]) else ""
        if col_e in row.index:
            seg.end_node = str(row[col_e]) if pd.notna(row[col_e]) else ""

    # 埋深 — 优先用预计算的埋深列,其次用地面标高-管内底标高
    depth_start = 1.5
    depth_end = 1.5

    # 方案A: 直接使用预计算的埋深列 (最可靠)
    for col in ["起点埋深(m)", "终点埋深(m)", "起点埋深", "终点埋深"]:
        if col in row.index and pd.notna(row[col]):
            val = float(row[col])
            if val > 0:
                if "起点" in col:
                    depth_start = val
                else:
                    depth_end = val

    # 方案B: 地面标高 - 管内底标高 (埋深列不存在时)
    if depth_start == 1.5 or depth_end == 1.5:
        ground_start = -1.0
        ground_end = -1.0
        invert_start = -1.0
        invert_end = -1.0

        for col, var in [
            ("起点地面标高(m)", "ground_start"),
            ("终点地面标高(m)", "ground_end"),
            ("起点地面标高", "ground_start"),
            ("终点地面标高", "ground_end"),
        ]:
            if col in row.index and pd.notna(row[col]):
                val = float(row[col])
                if var == "ground_start":
                    ground_start = val
                else:
                    ground_end = val

        for col, var in [
            ("起点管内底标高(m)", "invert_start"),
            ("终点管内底标高(m)", "invert_end"),
            ("起点管内底标高", "invert_start"),
            ("终点管内底标高", "invert_end"),
            ("起点管内底(m)", "invert_start"),
            ("终点管内底(m)", "invert_end"),
            ("起点管内底", "invert_start"),
            ("终点管内底", "invert_end"),
        ]:
            if col in row.index and pd.notna(row[col]):
                val = float(row[col])
                if var == "invert_start":
                    invert_start = val
                else:
                    invert_end = val

        if ground_start > 0 and invert_start > 0:
            depth_start = max(0.3, ground_start - invert_start)
        if ground_end > 0 and invert_end > 0:
            depth_end = max(0.3, ground_end - invert_end)

    seg.depth_start = depth_start
    seg.depth_end = depth_end
    avg_depth = (seg.depth_start + seg.depth_end) / 2.0

    # 警告: 使用了默认埋深
    if (
        depth_start == 1.5
        and depth_end == 1.5
        and (ground_start <= 0 or invert_start <= 0)
    ):
        _log.debug(
            "第%d段 DN%d: 无法计算埋深,使用默认1.5m (地面标高=%s 管内底=%s)",
            seq,
            seg.diameter,
            f"{ground_start:.2f}" if ground_start > 0 else "缺失",
            f"{invert_start:.2f}" if invert_start > 0 else "缺失",
        )

    # 坡度
    if "坡度" in row.index and pd.notna(row["坡度"]):
        seg.slope = float(row["坡度"])

    d = seg.diameter
    L = seg.length

    # ── 1. 管道材料+铺设 (综合单价 × 长度) ──
    pipe_price = get_pipe_price(d)  # 元/m
    seg.pipe_cost = pipe_price * L

    # ── 2. 土方工程 ──
    # 沟槽宽度 = 管外径 + 2×工作宽度 (≈管径/1000 + 1.2m)
    trench_width = d / 1000.0 + 1.2  # m
    trench_depth = avg_depth + 0.2  # 管底垫层
    V_excav = trench_width * trench_depth * L * 1.3  # 放坡系数1:0.5 → ×1.3
    V_backfill = V_excav * 0.85  # 85%回填
    seg.earthwork_cost = V_excav * CIVIL["excavation"] + V_backfill * CIVIL["backfill"]

    # ── 3. 机械台班 (管道吊装+运输, 不含挖掘机 — 挖掘机已含在土方综合单价中) ──
    ldm = _PIPE_LABOR_MACHINE.get(d, _PIPE_LABOR_MACHINE[600])
    _, _, crane_shift, truck_shift = ldm
    seg.machine_cost = (
        crane_shift * L / 10 * MACHINE_PRICE["crane_truck"]
        + truck_shift * L / 10 * MACHINE_PRICE["truck"]
    )

    # ── 4. 人工 ──
    tech_labor, general_labor, _, _ = ldm
    seg.labor_cost = (tech_labor + general_labor) * L / 10 * LABOR_PRICE

    # ── 5. 检查井摊销 ──
    mh_price = _MANHOLE_PRICE.get(d, 6000)
    manhole_spacing = 40.0  # 检查井间距 ≈ 40m
    n_manholes = max(1, L / manhole_spacing)
    seg.manhole_cost = mh_price * n_manholes

    seg.total = (
        seg.pipe_cost
        + seg.earthwork_cost
        + seg.machine_cost
        + seg.labor_cost
        + seg.manhole_cost
    )
    return seg


def _estimate_pump_station(pipe_node, est: PipeNetworkEstimate):
    """估算提升泵站造价"""
    excel_path = getattr(pipe_node, "_excel_path", "")
    if not excel_path or not os.path.exists(excel_path):
        return

    try:
        df = pd.read_excel(excel_path, sheet_name="计算结果")
    except Exception as e:
        _log.warning("operation failed: %s", e, exc_info=True)
        return

    # 检查是否有需要提升的管段 — 遍历所有可能的列名变体
    lift_meters = 0.0
    matched_col = None
    for col in [
        "污水泵站扬程(m)",
        "污水泵站扬程",
        "扬程(m)",
        "扬程",
        "污水提升(m)",
        "提升(m)",
        "提升高度",
        "泵站扬程",
    ]:
        if col in df.columns:
            vals = df[col].dropna()
            if len(vals) > 0:
                col_max = float(vals.max())
                if col_max > lift_meters:
                    lift_meters = col_max
                    matched_col = col

    if lift_meters > 0:
        est.pump_station_cost = (
            PUMP_STATION_BASE + PUMP_STATION_PER_METER * lift_meters
        ) * 10000  # 万元→元
        _log.info(
            "检测到提升泵站需求: 列=%s 最大扬程=%.2fm → 泵站造价=%.1f万元",
            matched_col,
            lift_meters,
            est.pump_station_cost / 10000,
        )
    else:
        _log.debug("未检测到提升泵站需求 (所有扬程列均为0或不存在)")
