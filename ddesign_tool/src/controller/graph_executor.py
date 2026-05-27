"""
graph_executor.py — DAG 执行引擎

功能:
  1. 根据节点间的端口连接关系,构建有向无环图 (DAG)
  2. 拓扑排序确定计算顺序
  3. 按序执行每个节点的 calculate()
  4. 将上游结果(水量+水质)传递给下游节点
  5. 支持增量计算(仅重算 dirty 节点及其下游)

使用方式:
    executor = GraphExecutor()
    executor.add_node(input_node)
    executor.add_node(tiaojiechi_node)
    executor.connect(input_node.output_ports[0], tiaojiechi_node.input_ports[0])
    results = executor.execute()
"""

from __future__ import annotations

from collections import deque
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from _logging import get_logger
from models.base import (
    NodeBase,
    NodeResult,
    NodeState,
    Port,
    PortType,
    SludgeFlow,
    WATER_QUALITY_ATTRS,
    WaterFlow,
    WaterQuality,
)
from models.input_node import InputNode

_log = get_logger(__name__)
# 进度回调类型
ProgressCallback = Callable[[int, int, str], None]
# (已完成数, 总数, 当前节点名)


class GraphExecutor:
    """DAG 执行引擎

    Attributes:
        nodes: 所有节点 {node_id: NodeBase}
        connections: 所有连线 {(from_port_id, to_port_id)}
        progress_callback: 进度回调(可选,用于 UI 更新)
    """

    def __init__(self):
        self._nodes: Dict[str, NodeBase] = {}

        self._connections: Set[Tuple[str, str]] = set()  # (from_port_id, to_port_id)
        self.progress_callback: Optional[ProgressCallback] = None

    # ── 节点/连线管理 ──

    def add_node(self, node: NodeBase) -> None:
        """添加节点"""
        self._nodes[node.node_id] = node

    def remove_node(self, node_id: str) -> None:
        """删除节点及其所有连线"""
        if node_id in self._nodes:
            del self._nodes[node_id]
        # 通过 port_id → node_id 映射查找关联连线 (避免 split 截断含连字符的 ID)
        port_to_node: Dict[str, str] = {}
        for nid, node in self._nodes.items():
            for p in node.input_ports + node.output_ports:
                port_to_node[p.port_id] = nid
        to_remove = {
            (f, t)
            for (f, t) in self._connections
            if port_to_node.get(f) == node_id or port_to_node.get(t) == node_id
        }
        self._connections -= to_remove

    def connect(self, from_port: Port, to_port: Port) -> bool:
        """连接两个端口

        Args:
            from_port: 上游输出端口
            to_port: 下游输入端口

        Returns:
            True 若连接成功
        """
        if not from_port.is_output:
            raise ValueError(f"端口 {from_port.port_id} 不是输出端口")
        if not to_port.is_input:
            raise ValueError(f"端口 {to_port.port_id} 不是输入端口")
        if not from_port.can_connect(to_port):
            raise ValueError(
                f"端口类型不兼容: {from_port.port_type.name} vs {to_port.port_type.name}"
            )
        # SLUDGE 输入端允许多条连线 (用于污泥合并), 其他类型只允许一条
        if to_port.port_type != PortType.SLUDGE:
            self._connections = {
                (f, t) for (f, t) in self._connections if t != to_port.port_id
            }
            to_port.connections.clear()
        self._connections.add((from_port.port_id, to_port.port_id))
        from_port.connections.append(to_port.port_id)
        to_port.connections.append(from_port.port_id)
        return True

    def disconnect(self, from_port: Port, to_port: Port) -> None:
        """断开两个端口的连接"""
        key = (from_port.port_id, to_port.port_id)
        self._connections.discard(key)
        if to_port.port_id in from_port.connections:
            from_port.connections.remove(to_port.port_id)
        if from_port.port_id in to_port.connections:
            to_port.connections.remove(from_port.port_id)

    # ═══════════════ 查询/获取 ═══════════════
    def get_node(self, node_id: str) -> Optional[NodeBase]:
        return self._nodes.get(node_id)

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    # ── 拓扑排序 ──

    # ═══════════════ UI 构建 ═══════════════
    def _build_adjacency(
        self,
    ) -> Tuple[Dict[str, List[str]], Dict[str, List[str]], Dict[str, int]]:
        """构建邻接表和入度

        Returns:
            (successors, predecessors, indegree)
            successors[node_id] = [下游节点ID列表]
            predecessors[node_id] = [上游节点ID列表]
            indegree[node_id] = 入度(上游节点数)
        """
        successors: Dict[str, List[str]] = {nid: [] for nid in self._nodes}
        predecessors: Dict[str, List[str]] = {nid: [] for nid in self._nodes}
        indegree: Dict[str, int] = {nid: 0 for nid in self._nodes}

        # 构建 port_id → node_id 映射 (node_id 含连字符,不能用 split("-")[0])
        port_to_node: Dict[str, str] = {}
        for nid, node in self._nodes.items():
            for p in node.input_ports + node.output_ports:
                port_to_node[p.port_id] = nid

        for from_pid, to_pid in self._connections:
            from_node_id = port_to_node.get(from_pid, "")
            to_node_id = port_to_node.get(to_pid, "")
            if from_node_id in successors and to_node_id in successors:
                successors[from_node_id].append(to_node_id)
                predecessors[to_node_id].append(from_node_id)
                indegree[to_node_id] += 1

        return successors, predecessors, indegree

    def topological_order(self) -> List[str]:
        """返回拓扑排序后的节点ID列表

        Raises:
            RuntimeError: 若图中存在环路
        """
        successors, predecessors, indegree = self._build_adjacency()

        # Kahn 算法
        queue = deque([nid for nid, deg in indegree.items() if deg == 0])
        order = []

        while queue:
            u = queue.popleft()
            order.append(u)
            for v in successors.get(u, []):
                indegree[v] -= 1
                if indegree[v] == 0:
                    queue.append(v)

        if len(order) != len(self._nodes):
            # 存在环路
            remaining = set(self._nodes.keys()) - set(order)
            raise RuntimeError(f"图中存在环路,无法拓扑排序.未处理节点: {remaining}")

        return order

    # ── 执行 ──

    # ═══════════════ 执行引擎 ═══════════════
    def execute(self, force_all: bool = False) -> Dict[str, NodeResult]:
        """执行全部计算

        Args:
            force_all: True = 强制全部重算,False = 仅计算 dirty 节点及下游

        Returns:
            {node_id: NodeResult}
        """
        try:
            order = self.topological_order()
        except RuntimeError as e:
            return {"_error": NodeResult.failed(str(e))}

        # 确定需要计算的节点集合
        if force_all:
            dirty_set = set(order)
            for nid in order:
                self._nodes[nid].state = NodeState.DIRTY
        else:
            dirty_set = self._find_dirty_with_downstream(order)

        upstream_data: Dict[str, Tuple[WaterFlow, WaterQuality]] = {}
        results: Dict[str, NodeResult] = {}
        total = len(dirty_set)
        completed = 0

        for nid in order:
            node = self._nodes[nid]
            if node.is_sludge_only:
                continue

            completed = self._process_water_node(
                nid,
                order,
                dirty_set,
                force_all,
                upstream_data,
                results,
                completed,
                total,
            )

        # ── 污泥处理线独立执行 ──
        self._execute_sludge_pass(results)

        # ── 高程计算后处理 ──
        try:
            self._execute_elevation_pass(results)
        except Exception as e:
            _log.warning("高程计算后处理失败: %s", e)

        return results

    # ═══════════════ 内部处理 ═══════════════
    def _process_water_node(
        self,
        nid: str,
        order: List[str],
        dirty_set: Set[str],
        force_all: bool,
        upstream_data: Dict[str, Tuple[WaterFlow, WaterQuality]],
        results: Dict[str, NodeResult],
        completed: int,
        total: int,
    ) -> int:
        """处理单个水处理节点的计算.

        Returns:
            更新后的 completed 计数
        """
        node = self._nodes[nid]
        predecessors = self._get_predecessors(nid)

        # ── 判断是否为"流量源"节点 ──
        is_flow_source = not any(
            p.port_type in (PortType.WATER, PortType.MIXED) for p in node.input_ports
        ) and any(
            p.port_type in (PortType.WATER, PortType.MIXED) for p in node.output_ports
        )

        if is_flow_source:
            input_flow = WaterFlow(Q_design=0.0, Q_avg_daily=0.0, Kz=1.0)
            input_quality = WaterQuality(
                BOD5=0.0,
                COD=0.0,
                SS=0.0,
                NH3N=0.0,
                TN=0.0,
                TP=0.0,
                pH=7.0,
            )
        else:
            input_flow, input_quality = self._merge_upstream(
                nid, predecessors, upstream_data
            )

        # ── 执行计算 ──
        needs_execution = (
            nid in dirty_set
            or force_all
            or not any(
                p.port_type in (PortType.WATER, PortType.MIXED)
                for p in node.input_ports
            )
        )

        if needs_execution:
            result, out_flow, out_quality = node.execute(input_flow, input_quality)
            results[nid] = result
            upstream_data[nid] = (out_flow, out_quality)
            completed += 1

            if self.progress_callback:
                self.progress_callback(completed, total, node.NODE_NAME)

            if not result.success:
                self._mark_downstream_error(nid, order, results)
        else:
            # 干净节点 — 使用缓存结果
            completed = self._process_cached_node(
                nid,
                node,
                input_flow,
                input_quality,
                upstream_data,
                results,
                completed,
                total,
            )

        return completed

    def _process_cached_node(
        self,
        nid: str,
        node: NodeBase,
        input_flow: WaterFlow,
        input_quality: WaterQuality,
        upstream_data: Dict[str, Tuple[WaterFlow, WaterQuality]],
        results: Dict[str, NodeResult],
        completed: int,
        total: int,
    ) -> int:
        """处理使用缓存结果的干净节点,更新水质追踪和维度."""
        if not node.result:
            return completed

        results[nid] = node.result
        new_inlet = WaterQuality(
            BOD5=input_quality.BOD5,
            COD=input_quality.COD,
            SS=input_quality.SS,
            NH3N=input_quality.NH3N,
            TN=input_quality.TN,
            TP=input_quality.TP,
            pH=input_quality.pH,
        )
        new_outlet = input_quality.apply_removal(node.get_removal_rates())
        node.result.inlet_quality = new_inlet
        node.result.outlet_quality = new_outlet

        for attr in WATER_QUALITY_ATTRS:
            in_val = getattr(new_inlet, attr)
            out_val = getattr(new_outlet, attr)
            removal = (in_val - out_val) / in_val * 100 if in_val > 0 else 0

            node.result.add_dimension(f"进水{attr}", round(in_val, 2), "mg/L")
            node.result.add_dimension(f"出水{attr}", round(out_val, 2), "mg/L")
            node.result.add_dimension(f"{attr}去除率", round(removal, 2), "%")

        # 同步更新流量相关维度
        _FLOW_DIM_UPDATES = [
            ("m³/s", "设计流量", lambda f: round(f.Q_design, 3)),
            ("L/s", "设计流量", lambda f: round(f.Q_design * 1000, 1)),
            ("m³/d", "平均日", lambda f: round(f.Q_avg_daily, 1)),
            ("m³/h", "平均时", lambda f: round(f.Q_avg_hourly, 1)),
        ]
        for dim_name in list(node.result.dimensions.keys()):
            unit = node.result.dimensions[dim_name][1]
            for dim_unit, dim_keyword, dim_fn in _FLOW_DIM_UPDATES:
                if unit == dim_unit and dim_keyword in dim_name:
                    node.result.dimensions[dim_name] = (dim_fn(input_flow), unit)
                    break

        downstream_quality = input_quality.apply_removal(node.get_removal_rates())
        all_quality = all(p.port_type == PortType.QUALITY for p in node.output_ports)
        out_flow = (
            WaterFlow(Q_design=0.0, Q_avg_daily=0.0, Kz=1.0)
            if all_quality
            else input_flow
        )
        upstream_data[nid] = (out_flow, downstream_quality)

        return completed

    # ═══════════════ 查询/获取 ═══════════════
    def _find_dirty_with_downstream(self, order: List[str]) -> Set[str]:
        """找出需要重算的节点: DIRTY 节点及其所有下游

        水质/水量变化会影响下游节点的进/出水水质维度和部分校核值
        (如污泥产量、需氧量), 因此 DIRTY 节点的下游也必须重算.
        """
        dirty = set()
        # BFS: 从 DIRTY 节点出发, 沿拓扑方向传播
        successors, _, _ = self._build_adjacency()
        queue = []
        for nid in order:
            if self._nodes[nid].is_dirty:
                dirty.add(nid)
                queue.append(nid)
        while queue:
            nid = queue.pop(0)
            for succ in successors.get(nid, []):
                if succ not in dirty:
                    dirty.add(succ)
                    queue.append(succ)
        return dirty

    def _get_predecessors(self, node_id: str) -> List[str]:
        """获取某个节点的所有上游节点ID"""
        _, predecessors, _ = self._build_adjacency()
        return predecessors.get(node_id, [])

    # ═══════════════ 内部合并 ═══════════════
    def _merge_upstream(
        self,
        node_id: str,
        predecessors: List[str],
        upstream_data: Dict[str, Tuple[WaterFlow, WaterQuality]],
    ) -> Tuple[WaterFlow, WaterQuality]:
        """合并多个上游的水量和水质

        水量: 各上游流量之和
        水质: WATER 型上游按流量加权平均, QUALITY-only 上游直接设值
        """
        if not predecessors:
            # 没有有效上游 → 返回零流量/空水质而非硬编码默认值
            # 避免 0.57 m³/s 等默认值在无上游数据时静默传播
            return WaterFlow(Q_design=0.0, Q_avg_daily=0.0, Kz=1.0), WaterQuality(
                BOD5=0.0,
                COD=0.0,
                SS=0.0,
                NH3N=0.0,
                TN=0.0,
                TP=0.0,
                pH=7.0,
            )

        total_flow = 0.0
        weighted_quality: Dict[str, float] = {
            "BOD5": 0,
            "COD": 0,
            "SS": 0,
            "NH3N": 0,
            "TN": 0,
            "TP": 0,
        }

        # 收集 QUALITY-only 上游节点的直接水质
        # (WaterQualityNode 输出 Q=0, 不应被流量加权平均忽略)
        direct_quality: Optional[WaterQuality] = None

        for pred_id in predecessors:
            if pred_id not in upstream_data:
                continue
            flow, quality = upstream_data[pred_id]

            # 判断是否为 QUALITY-only 节点 (输出端口全为 QUALITY 类型)
            pred_node = self._nodes.get(pred_id)
            is_quality_only = (
                pred_node is not None
                and len(pred_node.output_ports) > 0
                and all(p.port_type == PortType.QUALITY for p in pred_node.output_ports)
            )

            if is_quality_only:
                direct_quality = quality  # QUALITY-only: 直接使用, 不参与流量加权
            else:
                q = flow.Q_design
                total_flow += q
                for key in weighted_quality:
                    weighted_quality[key] += q * getattr(quality, key)

        if total_flow > 0:
            merged_quality = WaterQuality(
                **{k: v / total_flow for k, v in weighted_quality.items()}
            )
        else:
            merged_quality = WaterQuality()

        # QUALITY-only 节点的水质直接覆盖 (进水水质由 WaterQualityNode 设定)
        if direct_quality is not None:
            for attr in WATER_QUALITY_ATTRS:
                setattr(merged_quality, attr, getattr(direct_quality, attr))

        # 水量汇总(Kz 取上游最大值,Q_avg 累加)
        max_Kz = 1.0
        total_avg = 0.0
        for pred_id in predecessors:
            if pred_id in upstream_data:
                f, _ = upstream_data[pred_id]
                max_Kz = max(max_Kz, f.Kz)
                total_avg += f.Q_avg_daily

        merged_flow = WaterFlow(
            Q_design=total_flow,
            Q_avg_daily=total_avg,
            Kz=max_Kz,
        )

        return merged_flow, merged_quality

    def _mark_downstream_error(
        self, failed_nid: str, order: List[str], results: Dict[str, NodeResult]
    ) -> None:
        """标记失败节点的所有下游为 '上游计算失败'"""
        successors, _, _ = self._build_adjacency()
        failed_set = set()

        queue = deque([failed_nid])
        while queue:
            u = queue.popleft()
            if u in failed_set:
                continue
            failed_set.add(u)
            for v in successors.get(u, []):
                if v not in failed_set:
                    queue.append(v)

        for nid in order:
            if nid in failed_set and nid != failed_nid:
                results[nid] = NodeResult.failed(
                    f"上游节点 '{self._nodes[failed_nid].NODE_NAME}' 计算失败"
                )

    # ── 污泥线执行 ──

    # ═══════════════ 执行引擎 ═══════════════
    def _execute_sludge_pass(self, results: Dict[str, NodeResult]) -> None:
        """执行污泥处理线的独立 DAG 通道

        在水处理线完成后运行.收集所有 SLUDGE 输出端口的数据,
        沿 SLUDGE 端口连线传递给下游纯污泥节点.

        路由逻辑:
        1. 找出所有有 SLUDGE 输入端口的节点
        2. 按拓扑序执行,合并上游污泥流
        3. 调用 node.execute_sludge(sludge) 进行计算
        """
        # 构建 port_id → node_id 映射
        port_to_node: Dict[str, str] = {}
        for nid, node in self._nodes.items():
            for p in node.input_ports + node.output_ports:
                port_to_node[p.port_id] = nid

        # 找出所有 SLUDGE 端口连线
        sludge_edges: Dict[str, List[str]] = {}  # {from_nid: [to_nid, ...]}
        sludge_indegree: Dict[str, int] = {}
        sludge_nodes: Set[str] = set()

        for nid in self._nodes:
            sludge_nodes.add(nid)
            sludge_edges[nid] = []
            sludge_indegree[nid] = 0

        for from_pid, to_pid in self._connections:
            from_nid = port_to_node.get(from_pid, "")
            to_nid = port_to_node.get(to_pid, "")
            if not from_nid or not to_nid:
                continue
            # 仅处理 SLUDGE 类型连线
            from_node = self._nodes.get(from_nid)
            to_node = self._nodes.get(to_nid)
            if not from_node or not to_node:
                continue
            # 检查是否为 SLUDGE 端口
            from_port = next(
                (p for p in from_node.output_ports if p.port_id == from_pid), None
            )
            to_port = next(
                (p for p in to_node.input_ports if p.port_id == to_pid), None
            )
            if from_port and to_port and from_port.port_type == PortType.SLUDGE:
                sludge_edges[from_nid].append(to_nid)
                sludge_indegree[to_nid] += 1

        # 如果没有污泥连线,直接返回
        has_sludge_edges = any(edges for edges in sludge_edges.values())
        if not has_sludge_edges:
            return

        # Kahn 拓扑排序 (污泥子图)
        queue = deque([nid for nid, deg in sludge_indegree.items() if deg == 0])
        sludge_order: List[str] = []
        visited: Set[str] = set()

        while queue:
            u = queue.popleft()
            if u in visited:
                continue
            visited.add(u)
            sludge_order.append(u)
            for v in sludge_edges.get(u, []):
                sludge_indegree[v] -= 1
                if sludge_indegree[v] == 0:
                    queue.append(v)

        # 存储上游污泥流 {node_id: SludgeFlow}
        sludge_upstream: Dict[str, SludgeFlow] = {}

        for nid in sludge_order:
            node = self._nodes[nid]

            # 仅处理有 SLUDGE 输入端口的节点
            has_sludge_input = any(
                p.port_type == PortType.SLUDGE and p.direction == "input"
                for p in node.input_ports
            )
            if not has_sludge_input:
                # 污泥生产节点 (chuchenchi, cass, ...): 收集其 sludge_output
                if node.sludge_output is not None:
                    sludge_upstream[nid] = node.sludge_output
                continue

            # ── 合并上游污泥流 ──
            merged_sludge = self._merge_sludge_upstream(
                nid, sludge_upstream, port_to_node
            )
            if merged_sludge is None:
                continue  # 无上游污泥数据,跳过

            # ── 执行污泥计算 ──
            try:
                s_result, s_out = node.execute_sludge(merged_sludge)
                if s_result is not None:
                    results[nid] = s_result
                    node._result = s_result  # 写入节点缓存, UI 结果面板依赖此字段
                    node.state = NodeState.CLEAN  # 标记计算完成
                sludge_upstream[nid] = s_out
            except Exception as e:
                failed = NodeResult.failed(f"污泥计算失败: {e}")
                results[nid] = failed
                node._result = failed
                node.state = NodeState.ERROR

    # ═══════════════ 内部合并 ═══════════════
    def _merge_sludge_upstream(
        self,
        node_id: str,
        sludge_upstream: Dict[str, SludgeFlow],
        port_to_node: Dict[str, str],
    ) -> Optional[SludgeFlow]:
        """合并多股上游污泥流

        - 湿泥量 Q_wet: 累加
        - 干固量 DS: 累加
        - 含水率: DS 加权平均
        - VS 比: DS 加权平均
        """
        # 找出上游节点 (通过 SLUDGE 连线)
        predecessors: List[str] = []
        node = self._nodes[node_id]
        for in_port in node.input_ports:
            if in_port.port_type != PortType.SLUDGE:
                continue
            for from_pid, to_pid in self._connections:
                if to_pid == in_port.port_id:
                    pred_nid = port_to_node.get(from_pid)
                    if pred_nid and pred_nid in sludge_upstream:
                        predecessors.append(pred_nid)

        if not predecessors:
            return None

        total_DS = 0.0
        total_Q_wet = 0.0
        weighted_P = 0.0
        weighted_VS = 0.0

        for pred_id in predecessors:
            s = sludge_upstream[pred_id]
            total_Q_wet += s.Q_wet
            total_DS += s.DS
            weighted_P += s.P_moisture * max(s.DS, 0.001)
            weighted_VS += s.VS_ratio * max(s.DS, 0.001)

        if total_DS > 0:
            avg_P = weighted_P / total_DS
            avg_VS = weighted_VS / total_DS
        else:
            avg_P = 0.96
            avg_VS = 0.60

        return SludgeFlow(
            Q_wet=total_Q_wet,
            DS=total_DS,
            P_moisture=avg_P,
            VS_ratio=avg_VS,
        )

    def trace_sludge_upstream(self, node_id: str) -> Optional["SludgeFlow"]:
        """公开方法: 追踪某节点的上游污泥流 (用于方案浏览器)

        遍历 SLUDGE 端口连线, 收集并合并所有上游污泥产源的数据.
        如果上游节点尚未计算, 则使用其默认 sludge_output (可能为 None).
        """
        from models.base import PortType as PT
        from models.base import SludgeFlow as SF

        # 构建 port_to_node 映射
        port_to_node: Dict[str, str] = {}
        for nid, node in self._nodes.items():
            for p in node.input_ports + node.output_ports:
                port_to_node[p.port_id] = nid

        node = self._nodes.get(node_id)
        if not node:
            return None

        # 收集通过 SLUDGE 连线连接的上游节点
        sludge_data: Dict[str, SludgeFlow] = {}
        for in_port in node.input_ports:
            if in_port.port_type != PT.SLUDGE:
                continue
            for from_pid, to_pid in self._connections:
                if to_pid == in_port.port_id:
                    pred_nid = port_to_node.get(from_pid)
                    if pred_nid and pred_nid not in sludge_data:
                        pred_node = self._nodes.get(pred_nid)
                        if pred_node and pred_node.sludge_output is not None:
                            sludge_data[pred_nid] = pred_node.sludge_output

        if not sludge_data:
            return None

        # 合并
        total_DS = sum(s.DS for s in sludge_data.values())
        total_Q = sum(s.Q_wet for s in sludge_data.values())

        if total_DS > 0:
            avg_P = sum(s.DS * s.P_moisture for s in sludge_data.values()) / total_DS
            avg_VS = sum(s.DS * s.VS_ratio for s in sludge_data.values()) / total_DS
        else:
            avg_P = 0.96
            avg_VS = 0.60
        return SF(Q_wet=total_Q, DS=total_DS, P_moisture=avg_P, VS_ratio=avg_VS)

    # ── 高程计算后处理 ──

    # ═══════════════ 事件回调 ═══════════════
    def _execute_elevation_pass(self, results: Dict[str, NodeResult]) -> None:
        """高程计算后处理: 沿DAG拓扑顺序计算各节点水面标高

        在 execute() 和 _execute_sludge_pass() 完成后调用.
        从进厂污水水面标高节点(jcws_smbg)开始,沿 MIXED/WATER 连接线
        向下游传播水面标高,累计水头损失.

        结果写入 results[nid].elevation.
        """
        from models.elevation_calculator import ElevationCalculator

        try:
            calc = ElevationCalculator(self)
            elevation_data = calc.compute(results)

            n_computed = len(elevation_data)
            n_with_elevation = sum(
                1
                for r in results.values()
                if not (isinstance(r, dict) and r.get("_error"))
                and hasattr(r, "elevation")
                and r.elevation is not None
            )
            _log.info("高程计算完成: %d 个节点有高程数据", n_with_elevation)

            if calc._errors:
                _log.warning(
                    "高程计算有 %d 个警告: %s",
                    len(calc._errors),
                    "; ".join(calc._errors[:3]),
                )
        except ImportError as e:
            _log.debug("高程计算模块未就绪, 跳过: %s", e)
        except Exception as e:
            _log.warning("高程计算后处理失败 (非致命): %s", e)

    # ── 序列化 ──

    # ═══════════════ 序列化 ═══════════════
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "nodes": [n.to_dict() for n in self._nodes.values()],
            "connections": [{"from": f, "to": t} for f, t in self._connections],
        }

    @classmethod

    # ═══════════════ 反序列化 ═══════════════
    def from_dict(
        cls,
        d: Dict[str, Any],
        node_factory: Optional[Callable[[str, Dict], NodeBase]] = None,
    ) -> "GraphExecutor":
        """从字典反序列化

        Args:
            d: 序列化字典
            node_factory: 根据 type 创建节点的工厂函数
                          签名: (node_type: str, node_dict: dict) -> NodeBase
        """
        executor = cls()

        # 重建节点
        for nd in d.get("nodes", []):
            if node_factory:
                node = node_factory(nd["type"], nd)
            else:
                # 默认仅支持 InputNode
                if nd["type"] == "input_node":
                    node = InputNode.from_dict(nd)
                else:
                    continue
            if node is not None:
                executor.add_node(node)
            else:
                _log.warning(
                    "Skipping unknown node type: %s (id=%s)",
                    nd.get("type"),
                    nd.get("id"),
                )

        # 重建连线 — 先构建 port_id → Port 映射
        port_lookup: Dict[str, "Port"] = {}
        for node in executor._nodes.values():
            for p in node.input_ports + node.output_ports:
                port_lookup[p.port_id] = p

        for conn in d.get("connections", []):
            from_pid = conn["from"]
            to_pid = conn["to"]
            from_port = port_lookup.get(from_pid)
            to_port = port_lookup.get(to_pid)
            if from_port and to_port:
                executor.connect(from_port, to_port)

        return executor


# ── 节点工厂(用于反序列化)──

# 基础设施节点的 from_dict 映射(非模组节点)
_INFRA_FACTORY = {
    "input_node": "models.input_node.InputNode",
    "pipe_network": "models.pipe_network.PipeNetworkNode",
    "water_quality": "models.water_quality_node.WaterQualityNode",
    "combiner": "models.combiner.CombinerNode",
}


def default_node_factory(node_type: str, node_dict: Dict) -> Optional[NodeBase]:
    """默认节点工厂 — 从类型字符串创建节点

    优先级:
    1. 统一注册表 (ModManager + 兼容映射)
    2. 基础设施节点(pipe_network, water_quality, combiner, input_node)
    """
    from models.node_registry import resolve_class

    # 1. 统一注册表
    node_cls = resolve_class(node_type)
    if node_cls is not None:
        try:
            return node_cls.from_dict(node_dict)
        except Exception as e:
            _log.warning("operation failed: %s", e, exc_info=True)
            _log.warning("from_dict failed for %s, trying fallback", node_type)

    # 2. 基础设施节点
    if node_type in _INFRA_FACTORY:
        parts = _INFRA_FACTORY[node_type].rsplit(".", 1)
        import importlib

        try:
            module = importlib.import_module(parts[0])
            cls = getattr(module, parts[1], None)
            if cls:
                return cls.from_dict(node_dict)
        except Exception as e:
            _log.warning("operation failed: %s", e, exc_info=True)

    return None
