"""
elevation_calculator.py — 高程计算后处理引擎

在 DAG 执行完成后,沿拓扑顺序计算每个节点的水面标高、池底标高和水头损失.
高程数据沿 MIXED 连接线传播,与管道运输水头损失模组(gdys_stss)交互.

设计依据:
  - GB50014-2021《室外排水设计标准》§5 排水管渠和附属构筑物
  - CJJ 131-2009《城镇污水处理厂污泥处理技术规程》
  - 《给水排水设计手册》第1册(常用资料)、第5册(城镇排水)

计算公式:
  沿程水头损失: h_f = (n·v / R^(2/3))² × L    (Manning公式)
  局部水头损失: h_m = ξ · v² / (2g)
  总水头损失:   h_total = h_f + h_m
  堰流水头损失: 按薄壁堰/宽顶堰公式
  跌水判定:     ΔZ > 1.0m → 设跌水井
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from _logging import get_logger
from models.base import (
    GRAVITY,
    ElevationData,
    NodeResult,
    PortType,
)

from mods.mod_manager import get_mod_manager

_log = get_logger(__name__)
# ═════════════════════════════════════════════════════════════════════
# 水头损失回退值 (m) — 当 mod.json 未配置 elevation_loss 时使用
# 来源: 《给水排水设计手册》第5册 + 课程设计经验值
# ═════════════════════════════════════════════════════════════════════

_DEFAULT_FALLBACK_HEAD_LOSS: float = 0.2  # 保守回退, 实际应以 mod.json 为准


class ElevationCalculator:
    """高程后处理引擎

    在 DAG 执行完成后调用,沿拓扑顺序:
    1. 从上游收集水面标高
    2. 查找本节点的水头损失(从 mod.json elevation_loss 或默认经验值)
    3. 计算: 水面标高 = 上游水面标高 - 水头损失
    4. 计算: 池底标高 = 水面标高 - 有效水深
    5. 将 ElevationData 写入 NodeResult.elevation
    """

    def __init__(self, executor, mod_manager=None):
        """初始化高程计算器

        Args:
            executor: GraphExecutor 实例 (用于读取拓扑和节点)
            mod_manager: ModManager 实例 (可选, 用于读取 elevation_loss 配置)
        """
        self._executor = executor
        self._mgr = mod_manager or get_mod_manager()
        self._errors: List[str] = []

    # ── 公共入口 ──

    def compute(
        self, results: Optional[Dict[str, NodeResult]] = None
    ) -> Dict[str, ElevationData]:
        """执行全流程高程计算

        Args:
            results: {node_id: NodeResult} — 若为 None, 从 executor 的节点缓存中获取

        Returns:
            {node_id: ElevationData} — 每个节点的高程数据
            若计算失败, 返回空 dict 并记录错误日志
        """
        self._errors.clear()

        try:
            order = self._executor.topological_order()
        except RuntimeError as e:
            _log.error("高程计算失败: 拓扑排序错误 - %s", e)
            self._errors.append(f"拓扑排序失败: {e}")
            return {}

        # 构建 port→node 映射
        port_to_node: Dict[str, str] = {}
        for nid, node in self._executor._nodes.items():
            for p in node.input_ports + node.output_ports:
                port_to_node[p.port_id] = nid

        # 构建上游映射
        predecessors = self._build_predecessors(order, port_to_node)

        # 存储每个节点的上游水面标高和地面标高
        upstream_water: Dict[str, float] = {}
        upstream_ground: Dict[str, float] = {}
        elevation_data: Dict[str, ElevationData] = {}

        for nid in order:
            node = self._executor._nodes.get(nid)
            if not node:
                continue

            try:
                elev = self._compute_node_elevation(
                    nid,
                    node,
                    predecessors,
                    upstream_water,
                    upstream_ground,
                    results,
                    port_to_node,
                    elevation_data,
                )
                if elev is not None:
                    elevation_data[nid] = elev
                    upstream_water[nid] = elev.water_elevation
                    upstream_ground[nid] = elev.ground_elevation

                    # 写入 NodeResult 并添加高程约束校核
                    if results and nid in results:
                        results[nid].elevation = elev
                        self._add_elevation_checks(results[nid], elev, node.NODE_NAME)

            except Exception as e:
                _log.error("高程计算 [%s](%s) 失败: %s", node.NODE_NAME, nid, e)
                self._errors.append(f"{node.NODE_NAME}({nid}): {e}")

        if self._errors:
            _log.warning(
                "高程计算完成, %d 个节点出错: %s",
                len(self._errors),
                "; ".join(self._errors[:5]),
            )

        return elevation_data

    # ── 单节点计算 ──

    def _compute_node_elevation(
        self,
        nid: str,
        node,
        predecessors: Dict[str, List[str]],
        upstream_water: Dict[str, float],
        upstream_ground: Dict[str, float],
        results: Optional[Dict[str, NodeResult]],
        port_to_node: Dict[str, str],
        elevation_data: Dict[str, "ElevationData"],
    ) -> Optional[ElevationData]:
        """计算单个节点的高程数据"""
        node_type = node.NODE_TYPE

        # 1. 收集上游水面标高
        pred_ids = predecessors.get(nid, [])
        up_water_vals = [
            upstream_water[pid] for pid in pred_ids if pid in upstream_water
        ]
        up_ground_vals = [
            upstream_ground[pid] for pid in pred_ids if pid in upstream_ground
        ]

        if node_type == "jcws_smbg":
            # 起始节点: 始终从自身参数读取, 不从上游继承
            up_water = node.get_param("Z_water_inlet")
        elif up_water_vals:
            up_water = max(up_water_vals)
        else:
            Z_ground = self._extract_ground_elevation(node)
            up_water = Z_ground - 2.0
            _log.debug(
                "节点 [%s] 无上游高程数据,估算上游水面=%.2f", node.NODE_NAME, up_water
            )

        # 2. 地面标高: 起始节点用自身 → 上游传播 → 节点自身参数 → 默认
        if node_type == "jcws_smbg":
            Z_ground = node.get_param("Z_ground")
        elif up_ground_vals:
            Z_ground = max(up_ground_vals)
        else:
            Z_ground = self._extract_ground_elevation(node)

        # 2. 查找水头损失
        head_loss, loss_detail, loss_formula = self._get_head_loss(
            node_type,
            node,
            results.get(nid) if results else None,
        )

        # 3. 计算水面标高 / 池底标高
        if node_type == "wuni_hebing":
            # 污泥合并: 池底标高 = min(上游池底) - 运输损耗
            transport_loss = (
                node.get_param("h_loss_transport")
                if hasattr(node, "get_param")
                else 0.5
            )
            up_bottom_vals = []
            for pid in pred_ids:
                if pid in elevation_data:
                    up_bottom_vals.append(elevation_data[pid].bottom_elevation)
                elif pid in upstream_water and pid in upstream_ground:
                    # 从上游推算
                    up_h_eff = 0.0
                    up_node = self._executor._nodes.get(pid)
                    if up_node:
                        up_h_eff = self._extract_effective_depth(
                            up_node, results.get(pid) if results else None
                        )
                    up_bottom_vals.append(upstream_water[pid] - up_h_eff)
            if up_bottom_vals:
                bottom_elev = min(up_bottom_vals) - transport_loss
            else:
                bottom_elev = Z_ground - 2.0
            water_elev = bottom_elev  # 合并节点水面=池底(无有效水深)
            h_eff = 0.0
            head_loss = transport_loss
            loss_detail = f"运输损耗 {transport_loss:.2f}m"
            loss_formula = "池底 = min(上游池底) - 运输损耗"
        else:
            water_elev = up_water - head_loss
            h_eff = self._extract_effective_depth(
                node, results.get(nid) if results else None
            )
            bottom_elev = water_elev - h_eff

        # 5. 计算超高
        h_super = Z_ground - water_elev if Z_ground > water_elev else 0.5

        return ElevationData(
            ground_elevation=round(Z_ground, 3),
            bottom_elevation=round(bottom_elev, 3),
            water_elevation=round(water_elev, 3),
            effective_depth=round(h_eff, 3),
            super_elevation=round(h_super, 3),
            head_loss=round(head_loss, 3),
            head_loss_detail=loss_detail,
            upstream_water_elevation=round(up_water, 3),
            formula=loss_formula,
        )

    # ── 水头损失获取 ──

    # ═══════════════ 查询/获取 ═══════════════
    def _get_head_loss(
        self,
        node_type: str,
        node,
        result: Optional[NodeResult],
    ) -> Tuple[float, str, str]:
        """获取节点的水头损失值 (m)

        正值 = 水面下降 (水头损失), 负值 = 水面升高 (泵站提升)

        优先级:
        1. 泵站节点: 从参数 H_pump / H_st 读取扬程 → 返回负值
        2. mod.json elevation_loss.value (若为数字)
        3. 从 dimensions 提取 (如 "水头损失", "过栅水头损失 h1")
        4. 默认经验值 _DEFAULT_HEAD_LOSS
        5. 0.2m (保守默认)
        """
        # 0. 泵站节点 — 读取扬程参数, 返回负值 (水面升高)
        pump_head_keys = ["H_pump", "H_st", "H_lift"]
        for key in pump_head_keys:
            try:
                H = node.get_param(key)
                if H > 0:
                    return (
                        -float(H),
                        f"泵扬程 {H:.1f}m (水面升高)",
                        f"H_pump = {H:.1f}m",
                    )
            except Exception as e:
                _log.warning("operation failed: %s", e, exc_info=True)
        try:
            mod_info = self._mgr.get_mod_by_node_type(node_type)
            if mod_info and mod_info.elevation_loss:
                el = mod_info.elevation_loss
                if isinstance(el, dict):
                    val = el.get("value", None)
                    if isinstance(val, (int, float)) and val >= 0:
                        return float(val), el.get("formula", ""), el.get("formula", "")
        except Exception as e:
            _log.warning("operation failed: %s", e, exc_info=True)

        # 2. gdys_stss 专项处理 — 优先提取分项水头损失(含沿程+局部分解)
        #    必须放在通用维度提取之前,否则"总水头损失 h_total"会被通用逻辑先匹配走
        if node_type == "gdys_stss":
            if result and result.dimensions:
                h_total = result.dimensions.get("总水头损失 h_total", (0.0, ""))[0]
                h_f = result.dimensions.get("沿程水头损失 h_f", (0.0, ""))[0]
                h_m = result.dimensions.get("局部水头损失 h_m", (0.0, ""))[0]
                # 兼容新旧键名
                v_val = (
                    result.dimensions.get("设计流速 v")
                    or result.dimensions.get("满管流速 v_full")
                    or result.dimensions.get("满管流速 v")
                    or (0.0, "")
                )[0]
                i_val = (
                    result.dimensions.get("设计坡度 i")
                    or result.dimensions.get("管底坡度 i")
                    or (0.0, "")
                )[0]
                L_val = (
                    result.params.get("L_pipe", 0)
                    if hasattr(result, "params") and result.params
                    else 0
                )
                detail = (
                    f"Manning公式: i={i_val:.4f}, v={v_val:.2f}m/s → "
                    f"沿程{i_val:.4f}×{L_val:.0f}m = {h_f:.3f}m, "
                    f"局部{h_m:.3f}m, 合计{h_total:.3f}m"
                )
                return float(h_total), detail, "h_total = i×L + ξ×v²/(2g)"
            return 0.3, "管道运输水头损失(估算)", "默认0.3m"

        # 3. 从 NodeResult.dimensions 通用提取
        if result and result.dimensions:
            for dim_name in [
                "水头损失",
                "过栅水头损失 h1",
                "总水头损失 h_total",
                "水头损失 h1",
                "h_loss",
            ]:
                if dim_name in result.dimensions:
                    val, _ = result.dimensions[dim_name]
                    return (
                        float(val),
                        f"从计算结果提取: {dim_name}={val}m",
                        f"{dim_name}",
                    )

        # 4. 回退值 (mod.json 应已配置 elevation_loss)
        return (
            _DEFAULT_FALLBACK_HEAD_LOSS,
            f"回退值: {_DEFAULT_FALLBACK_HEAD_LOSS}m",
            f"默认 {node_type} 水头损失",
        )

    # ── 辅助方法 ──

    def _extract_effective_depth(self, node, result: Optional[NodeResult]) -> float:
        """从节点参数或计算结果中提取有效水深"""
        # 尝试从参数获取
        for key in ["h_eff", "h2", "h"]:
            try:
                val = node.get_param(key)
                if val > 0:
                    return val
            except Exception as e:
                _log.warning("operation failed: %s", e, exc_info=True)

        # 从 dimensions 获取
        if result and result.dimensions:
            for dim_name in [
                "有效水深 h_eff",
                "有效水深 h2",
                "有效水深",
                "有效水深 h",
                "h_eff",
                "管内水深 h",
                "管内水深",
            ]:
                if dim_name in result.dimensions:
                    val, _ = result.dimensions[dim_name]
                    return float(val)

        return 3.0  # 默认

    def _extract_ground_elevation(self, node) -> float:
        """提取地面标高"""
        for key in ["Z_ground", "ground_elevation"]:
            try:
                val = node.get_param(key)
                if val > 0:
                    return val
            except Exception as e:
                _log.warning("operation failed: %s", e, exc_info=True)
        return 102.0  # 默认

    # ── 高程约束校核 ──

    @staticmethod

    # ═══════════════ 状态检查 ═══════════════
    def _add_elevation_checks(
        result: NodeResult, elev: ElevationData, node_name: str
    ) -> None:
        """向 NodeResult 添加高程相关约束校核

        检查项:
        - 超高 ≥ 0.3m (GB50014)
        - 水面标高 > 池底标高
        - 水头损失 ≤ 3.0m (单个构筑物)
        - 跌水检测 (ΔZ > 1.0m → 提示)
        """
        # 超高检查
        super_ok = elev.super_elevation >= 0.3
        result.add_check(
            "高程-超高≥0.3m", super_ok, round(elev.super_elevation, 2), ">= 0.3", "m"
        )

        # 水面标高合理性 (仅对有有效水深的构筑物)
        if elev.effective_depth > 0.1:
            water_ok = elev.water_elevation > elev.bottom_elevation
            result.add_check(
                "高程-水面>池底",
                water_ok,
                round(elev.water_elevation - elev.bottom_elevation, 2),
                "> 0",
                "m",
            )

        # 水头损失不能过大 (跳过起始节点和泵站)
        if elev.head_loss > 0:
            hl_ok = elev.head_loss <= 3.0
            result.add_check(
                "高程-水头损失≤3m", hl_ok, round(elev.head_loss, 2), "<= 3.0", "m"
            )
            if not hl_ok:
                result.add_warning(
                    f"高程: {node_name} 水头损失 {elev.head_loss:.2f}m > 3.0m"
                )

        # 跌水提示
        if elev.head_loss > 1.0 and not elev.formula.startswith("起始"):
            result.add_warning(
                f"高程: {node_name} 水头损失 {elev.head_loss:.2f}m > 1.0m, 建议设跌水井"
            )

    # ── 拓扑辅助 ──

    # ═══════════════ UI 构建 ═══════════════
    def _build_predecessors(
        self,
        order: List[str],
        port_to_node: Dict[str, str],
    ) -> Dict[str, List[str]]:
        """构建前驱映射 {node_id: [前驱节点ID列表]}

        只追踪 MIXED、WATER 和 SLUDGE 类型端口的连接.
        """
        predecessors: Dict[str, List[str]] = {nid: [] for nid in order}

        for from_pid, to_pid in self._executor._connections:
            from_nid = port_to_node.get(from_pid, "")
            to_nid = port_to_node.get(to_pid, "")

            if not from_nid or not to_nid:
                continue

            from_node = self._executor._nodes.get(from_nid)
            to_node = self._executor._nodes.get(to_nid)
            if not from_node or not to_node:
                continue

            from_port = self._find_port(from_node, from_pid)
            to_port = self._find_port(to_node, to_pid)
            if from_port and to_port:
                if from_port.port_type in (
                    PortType.MIXED,
                    PortType.WATER,
                    PortType.SLUDGE,
                ):
                    if from_nid not in predecessors.get(to_nid, []):
                        predecessors.setdefault(to_nid, []).append(from_nid)

        return predecessors

    @staticmethod

    # ═══════════════ 查询/获取 ═══════════════
    def _find_port(node, port_id: str):
        """在节点端口中查找指定 ID 的端口"""
        for p in node.input_ports + node.output_ports:
            if p.port_id == port_id:
                return p
        return None

    # ── 公共静态方法: 水力计算工具 ──

    @staticmethod
    def manning_friction(Q: float, n: float, D: float, L: float) -> float:
        """Manning公式沿程水头损失

        Args:
            Q: 流量 m³/s
            n: 粗糙系数 (混凝土0.013~0.014)
            D: 管径 m
            L: 管长 m

        Returns:
            沿程水头损失 m
        """
        if D <= 0 or Q <= 0:
            return 0.0
        R = D / 4.0  # 满流
        A = math.pi * D * D / 4.0
        v = Q / A
        i_friction = (n * v / (R ** (2.0 / 3.0))) ** 2
        return i_friction * L

    @staticmethod
    def local_loss(xi: float, v: float) -> float:
        """局部水头损失: h_m = ξ · v² / (2g)"""
        return xi * (v**2) / (2.0 * GRAVITY)

    @staticmethod
    def weir_head_loss(Q: float, b: float, m: float = 0.42) -> float:
        """堰上水头 (实用堰)
        Q = m · b · √(2g) · H^(3/2) → H = (Q / (m·b·√(2g)))^(2/3)"""
        if b <= 0 or Q <= 0:
            return 0.0
        return (Q / (m * b * math.sqrt(2.0 * GRAVITY))) ** (2.0 / 3.0)

    @staticmethod
    def orifice_head_loss(Q: float, A: float, mu: float = 0.62) -> float:
        """孔口出流水头: Q = μ · A · √(2gH) → H = (Q/(μ·A))² / (2g)"""
        if A <= 0 or Q <= 0:
            return 0.0
        return (Q / (mu * A)) ** 2 / (2.0 * GRAVITY)


# ── 便捷函数 ──


# ═══════════════ 计算引擎 ═══════════════
def compute_elevations(
    executor, results: Optional[Dict[str, NodeResult]] = None
) -> Dict[str, ElevationData]:
    """便捷函数: 执行高程计算并将结果写入 NodeResult

    Args:
        executor: GraphExecutor 实例
        results: {node_id: NodeResult} (可选)

    Returns:
        {node_id: ElevationData}
    """
    calc = ElevationCalculator(executor)
    return calc.compute(results)
