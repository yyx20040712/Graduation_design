"""
cost_estimator.py — 工程量清单式工程概算引擎

按分部分项工程逐一计算: 土方 → 垫层 → 混凝土 → 钢筋 → 防水
每项列出: 工程量 × 综合单价 = 合价
严格区分"工程量"和"价格",不混用.

数据来源: 2019地方定额 + T/BCEBCA1-2023 造价指标 + 市场询价
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from _logging import get_logger

_log = get_logger(__name__)

from .unit_prices import (
    CIVIL,
    COMMON_EQUIP,
    EQUIPMENT,
    INDIRECT_RATES,
    REBAR_FLOOR,
    REBAR_WALL,
    floor_t,
    get_pipe_price,
    total_by_capacity,
    wall_t,
)


@dataclass
class BOQItem:
    """工程量清单项"""

    seq: int  # 序号
    code: str  # 定额编号(参考)
    name: str  # 项目名称
    unit: str  # 单位
    quantity: float  # 工程量
    unit_price: float  # 综合单价(元)
    total: float  # 合价(元) = quantity × unit_price
    category: str = ""  # 建筑工程/设备购置/安装工程
    node_type: str = ""  # 所属构筑物类型 (tiaojiechi/cass/pipe_network 等)


@dataclass
class EstimateResult:
    """概算结果"""

    project_name: str = ""
    q_daily: float = 0.0  # 处理规模 m³/d
    items: List[BOQItem] = field(default_factory=list)
    civil_cost: float = 0.0  # 建筑工程费 万元
    equip_cost: float = 0.0  # 设备购置费 万元
    install_cost: float = 0.0  # 安装工程费 万元
    other_cost: float = 0.0  # 其他费用 万元
    contingency: float = 0.0  # 预备费 万元
    total_cost: float = 0.0  # 总造价 万元
    unit_cost: float = 0.0  # 单位造价 元/(m³·d)
    check_msg: str = ""  # 合理性校验信息

    def to_dict(self) -> Dict:
        return {
            "project": self.project_name,
            "q_daily": self.q_daily,
            "civil": self.civil_cost,
            "equip": self.equip_cost,
            "install": self.install_cost,
            "other": self.other_cost,
            "contingency": self.contingency,
            "total": self.total_cost,
            "unit_cost": self.unit_cost,
            "check": self.check_msg,
            "items": [
                {
                    "seq": i.seq,
                    "code": i.code,
                    "name": i.name,
                    "unit": i.unit,
                    "qty": i.quantity,
                    "price": i.unit_price,
                    "total": i.total,
                    "category": i.category,
                    "node_type": i.node_type,
                }
                for i in self.items
            ],
        }


class CostEstimator:
    """工程量清单式概算引擎 — 含间接费

    费率来源于 unit_prices.INDIRECT_RATES (2024年标准):
      - 建设单位管理费 5%, 勘察设计费 4%, 工程监理费 2.5%, 前期工作费 1%
      - 基本预备费 10%, 增值税 9%
    """

    INSTALL_RATE = 0.15  # 安装费 = 设备费 × 15%

    def __init__(self):
        self._seq = 0

    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq

    def estimate(
        self,
        executor,
        pipe_node=None,
        project_name: str = "",
        results: Optional[Dict[str, "NodeResult"]] = None,  # noqa: F821 — forward ref
    ) -> EstimateResult:
        """执行概算

        Args:
            executor: GraphExecutor 实例
            pipe_node: 管网节点 (可选)
            project_name: 项目名称
            results: executor.execute() 返回的 {node_id: NodeResult} 字典.
                     提供时优先使用, 避免依赖 node._result 可能过期的缓存.
                     未提供时回退到 node.result (向后兼容).
        """
        self._seq = 0
        est = EstimateResult(project_name=project_name)
        items: List[BOQItem] = []

        # ── 一、各构筑物土建 ──
        skipped_nodes: List[str] = []
        for nid, node in executor._nodes.items():
            nt = node.NODE_TYPE
            # 使用统一注册表判断是否跳过 (IO节点 + 管网 + 无土建设备)
            # 跳过: 管网 / 无土建设备 / 纯设备型污泥模组
            _NO_CIVIL = {
                "pipe_network",
                "kw_cifenli",
                "wuni_shusong",
                "wuni_bengzhan",
                "wuni_tuoshui",
                "wuni_ganhua",
                "bashi_jiliangcao",
                "jcws_smbg",
                "gdys_stss",
            }
            if nt in _NO_CIVIL:
                continue
            try:
                from models.node_registry import is_io_node

                if is_io_node(nt):
                    continue
            except Exception as e:
                _log.warning("operation failed: %s", e, exc_info=True)
                if nt in ("input_node", "water_quality", "combiner", "kw_input"):
                    continue
            # 优先使用 results 字典中的结果, 回退到 node.result
            res = results.get(nid) if results else None
            node_items = self._structure_civil(node, result=res)
            items.extend(node_items)
            # 记录无有效计算结果的节点 (偶发: 第二次导出通常成功)
            if not node_items:
                skipped_nodes.append(getattr(node, "NODE_NAME", nt))

        if skipped_nodes:
            _log.info(
                "以下 %d 个构筑物缺少有效计算结果, 土建概算已跳过: %s",
                len(skipped_nodes),
                ", ".join(skipped_nodes),
            )
            _log.info(
                "💡 可尝试重新导出; 如仍不成功, 请按 F5 重新计算后检查节点状态灯是否为绿色"
            )

        # ── 二、管网 ──
        if pipe_node and hasattr(pipe_node, "_pipe_stats"):
            # 使用详细管网概算
            items.extend(self._pipe_network_detailed(pipe_node))
            # 提取流量用于规模校验
            est.q_daily = getattr(pipe_node, "_total_avg_daily", 0)

        # ── 三、设备 ──
        for nid, node in executor._nodes.items():
            nt = node.NODE_TYPE
            if nt in EQUIPMENT:
                name = getattr(node, "NODE_NAME", nt)
                for en, (qty, up) in EQUIPMENT[nt].items():
                    items.append(
                        BOQItem(
                            seq=self._next_seq(),
                            code=f"SB-{nt}",
                            name=f"{name}—{en}",
                            unit="台(套)",
                            quantity=qty,
                            unit_price=up * 10000,  # 万元→元
                            total=qty * up * 10000,  # 万元→元
                            category="设备购置",
                            node_type=nt,
                        )
                    )
        for en, cost in COMMON_EQUIP.items():
            items.append(
                BOQItem(
                    seq=self._next_seq(),
                    code="SB-COM",
                    name=en,
                    unit="套",
                    quantity=1,
                    unit_price=cost * 10000,
                    total=cost * 10000,
                    category="设备购置",
                )
            )

        # ── 三-2: 施工措施项目 ──
        civil_sum = sum(i.total for i in items if i.category == "建筑工程")
        # 施工降水 (按土方量估算, 约 15 元/m³ 开挖量)
        if civil_sum > 0:
            items.append(
                BOQItem(
                    self._next_seq(),
                    "CS-1",
                    "施工降水(井点降水)",
                    "项",
                    1,
                    civil_sum * 0.02,
                    civil_sum * 0.02,
                    "建筑工程",
                )
            )
            # 场地准备与临时设施
            items.append(
                BOQItem(
                    self._next_seq(),
                    "CS-2",
                    "场地准备及临时设施(含施工道路/围挡/临建)",
                    "项",
                    1,
                    civil_sum * 0.05,
                    civil_sum * 0.05,
                    "建筑工程",
                )
            )
            # 施工环保措施
            items.append(
                BOQItem(
                    self._next_seq(),
                    "CS-3",
                    "施工环保措施(扬尘/噪声/废水处理)",
                    "项",
                    1,
                    civil_sum * 0.015,
                    civil_sum * 0.015,
                    "建筑工程",
                )
            )
        # 调试与试运行 (设备费的 3%)
        equip_sum = sum(i.total for i in items if i.category == "设备购置")
        if equip_sum > 0:
            items.append(
                BOQItem(
                    self._next_seq(),
                    "CS-4",
                    "调试与试运行(含菌种培养/药剂)",
                    "项",
                    1,
                    equip_sum * 0.03,
                    equip_sum * 0.03,
                    "建筑工程",
                )
            )

        # ── 四、汇总 (含间接费) ──
        est.items = items
        base_civil = sum(i.total for i in items if i.category == "建筑工程") / 10000
        base_equip = sum(i.total for i in items if i.category == "设备购置") / 10000
        est.civil_cost = base_civil
        est.equip_cost = base_equip
        est.install_cost = round(base_equip * self.INSTALL_RATE, 2)

        # 间接费基数 = 建安费 (建筑工程 + 安装工程)
        base_ca = base_civil + est.install_cost
        mgmt = base_ca * INDIRECT_RATES["management"]
        design = base_ca * INDIRECT_RATES["design"]
        supervision = base_ca * INDIRECT_RATES["supervision"]
        preparation = base_ca * INDIRECT_RATES["preparation"]
        est.other_cost = round(mgmt + design + supervision + preparation, 2)

        subtotal = base_civil + base_equip + est.install_cost + est.other_cost
        est.contingency = round(subtotal * INDIRECT_RATES["contingency"], 2)
        tax = round((subtotal + est.contingency) * INDIRECT_RATES["tax"], 2)
        est.total_cost = round(subtotal + est.contingency + tax, 2)

        # ── 五、合理性校验 ──
        if est.q_daily > 0:
            est.unit_cost = round(est.total_cost * 10000 / est.q_daily, 0)
            lo, hi, _ = total_by_capacity(est.q_daily)
            if lo <= est.total_cost <= hi:
                est.check_msg = f"单位造价 {est.unit_cost} 元/(m³·d),在参考范围 [{lo:.0f}, {hi:.0f}] 内"
            else:
                est.check_msg = f"⚠ 单位造价 {est.unit_cost} 元/(m³·d),超出参考范围 [{lo:.0f}, {hi:.0f}]"

        return est

    # ═══════════════════════════════════════════════
    # 构筑物土建详算
    # ═══════════════════════════════════════════════

    def _structure_civil(self, node, result=None) -> List[BOQItem]:
        """按分部分项计算一个构筑物的土建造价

        Args:
            node: 节点实例 (用于获取 NODE_TYPE, NODE_NAME)
            result: 可选的 NodeResult. 提供时优先使用 (来自 executor.execute() 的 results 字典),
                    未提供时回退到 node.result.
        """
        items = []
        nt = node.NODE_TYPE
        # 优先使用传入的 result, 回退到 node.result
        res = result if result is not None else node.result
        if not res or not res.success:
            _log.warning("%s: 无有效计算结果,跳过概算", getattr(node, "NODE_NAME", nt))
            return items
        dims = dict(res.dimensions)
        name = getattr(node, "NODE_NAME", nt)

        # 提取尺寸
        D = self._val(dims, "池径 D")  # 圆形池直径
        L = self._val(dims, "池长 L") or self._val(dims, "单格长度 L")
        B = self._val(dims, "池宽 B") or self._val(dims, "单格宽度 B")
        H = (
            self._val(dims, "总高度 H")
            or self._val(dims, "总高度")
            or self._val(dims, "滤池总高度")
        )
        n_pools = (
            self._val(dims, "池数")
            or self._val(dims, "滤池格数")
            or self._val(dims, "渠道数")
            or 1
        )

        # 特殊处理: 格栅间
        if nt in ("cugeshan", "xigeshan"):
            L = self._val(dims, "栅槽总长 L")
            B = self._val(dims, "栅槽宽度 B")
            H = self._val(dims, "栅后总高 H")
            n_pools = self._val(dims, "格栅台数") or 1

        # 特殊处理: 紫外消毒池 (渠道型)
        if nt == "ziwai":
            L = self._val(dims, "渠道总长") or self._val(dims, "渠道长度")
            B = self._val(dims, "渠宽") or self._val(dims, "渠道宽度")
            H = self._val(dims, "总高度") or self._val(dims, "渠道总高度")
            n_pools = self._val(dims, "渠道数") or 1

        if not L or not B or not H:
            # 尝试圆形池
            if D and H:
                return self._circular_tank(name, nt, D, H, n_pools)
            _log.warning(
                "%s: 无法提取尺寸信息 (L=%s B=%s H=%s D=%s),跳过土建概算",
                name,
                L,
                B,
                H,
                D,
            )
            return items

        # 估算有效容积(用于确定壁厚等级)
        if D:
            V_eff = math.pi * (D / 2) ** 2 * H * n_pools
        else:
            V_eff = L * B * H * n_pools

        tw = wall_t(V_eff)
        tf = floor_t(V_eff)

        if D:  # 圆形池
            return self._circular_tank(name, nt, D, H, n_pools, result=result)
        else:  # 矩形池
            return self._rectangular_tank(
                name, nt, L, B, H, n_pools, tw, tf, result=result
            )

    def _circular_tank(
        self, name: str, nt: str, D: float, H: float, n: int, result=None
    ) -> List[BOQItem]:
        """圆形池 — 池壁高度 = H - tf, 土方量依据实际高程"""
        items = []
        R = D / 2
        tw = wall_t(math.pi * R * R * H)
        tf = floor_t(math.pi * R * R * H)
        H_wall = H - tf

        # 土方: 依据高程数据计算实际挖深
        excav_depth = self._excavation_depth(result, H, tf)
        V_excav = math.pi * (R + 1) ** 2 * excav_depth * n * 1.3
        items.append(
            BOQItem(
                self._next_seq(),
                "T1-1",
                f"{name}—机械挖土方",
                "m³",
                round(V_excav, 0),
                CIVIL["excavation"],
                round(V_excav * CIVIL["excavation"]),
                "建筑工程",
                nt,
            )
        )

        # 垫层
        V_pad = math.pi * (R + 0.3) ** 2 * 0.1 * n
        items.append(
            BOQItem(
                self._next_seq(),
                "T6-1",
                f"{name}—C15垫层",
                "m³",
                round(V_pad, 1),
                CIVIL["c15_pad"],
                round(V_pad * CIVIL["c15_pad"]),
                "建筑工程",
                nt,
            )
        )

        # 底板
        V_floor = math.pi * R**2 * tf * n
        items.append(
            BOQItem(
                self._next_seq(),
                "T6-2",
                f"{name}—C30底板",
                "m³",
                round(V_floor, 1),
                CIVIL["c30_floor"],
                round(V_floor * CIVIL["c30_floor"]),
                "建筑工程",
                nt,
            )
        )

        # 池壁 (高度 = H - tf)
        V_wall = 2 * math.pi * R * H_wall * tw * n
        items.append(
            BOQItem(
                self._next_seq(),
                "T6-3",
                f"{name}—C30池壁",
                "m³",
                round(V_wall, 1),
                CIVIL["c30_wall"],
                round(V_wall * CIVIL["c30_wall"]),
                "建筑工程",
                nt,
            )
        )

        # 钢筋
        W_rebar = (V_floor * REBAR_FLOOR + V_wall * REBAR_WALL) / 1000  # tons
        items.append(
            BOQItem(
                self._next_seq(),
                "T9-1",
                f"{name}—钢筋HRB400",
                "t",
                round(W_rebar, 2),
                CIVIL["rebar"],
                round(W_rebar * CIVIL["rebar"]),
                "建筑工程",
                nt,
            )
        )

        # 防水
        A_waterproof = (2 * math.pi * R * H_wall + math.pi * R**2) * n
        items.append(
            BOQItem(
                self._next_seq(),
                "T11-1",
                f"{name}—内防水",
                "m²",
                round(A_waterproof, 0),
                CIVIL["waterproof_inner"],
                round(A_waterproof * CIVIL["waterproof_inner"]),
                "建筑工程",
                nt,
            )
        )

        return items

    def _rectangular_tank(
        self,
        name: str,
        nt: str,
        L: float,
        B: float,
        H: float,
        n: int,
        tw: float,
        tf: float,
        result=None,
    ) -> List[BOQItem]:
        """矩形池 — 池壁高度 = H - tf, 土方量依据实际高程"""
        items = []
        H_wall = H - tf

        # 土方: 依据高程数据计算实际挖深
        excav_depth = self._excavation_depth(result, H, tf)
        V_excav = (L + 2) * (B + 2) * excav_depth * n * 1.2
        items.append(
            BOQItem(
                self._next_seq(),
                "T1-1",
                f"{name}—机械挖土方",
                "m³",
                round(V_excav, 0),
                CIVIL["excavation"],
                round(V_excav * CIVIL["excavation"]),
                "建筑工程",
                nt,
            )
        )

        # 垫层
        V_pad = (L + 0.6) * (B + 0.6) * 0.1 * n
        items.append(
            BOQItem(
                self._next_seq(),
                "T6-1",
                f"{name}—C15垫层",
                "m³",
                round(V_pad, 1),
                CIVIL["c15_pad"],
                round(V_pad * CIVIL["c15_pad"]),
                "建筑工程",
                nt,
            )
        )

        # 底板
        V_floor = L * B * tf * n
        items.append(
            BOQItem(
                self._next_seq(),
                "T6-2",
                f"{name}—C30底板",
                "m³",
                round(V_floor, 1),
                CIVIL["c30_floor"],
                round(V_floor * CIVIL["c30_floor"]),
                "建筑工程",
                nt,
            )
        )

        # 池壁 (高度 = H - tf, 不计底板厚)
        V_wall = 2 * (L + B) * H_wall * tw * n
        items.append(
            BOQItem(
                self._next_seq(),
                "T6-3",
                f"{name}—C30池壁",
                "m³",
                round(V_wall, 1),
                CIVIL["c30_wall"],
                round(V_wall * CIVIL["c30_wall"]),
                "建筑工程",
                nt,
            )
        )

        # 钢筋
        W_rebar = (V_floor * REBAR_FLOOR + V_wall * REBAR_WALL) / 1000
        items.append(
            BOQItem(
                self._next_seq(),
                "T9-1",
                f"{name}—钢筋HRB400",
                "t",
                round(W_rebar, 2),
                CIVIL["rebar"],
                round(W_rebar * CIVIL["rebar"]),
                "建筑工程",
                nt,
            )
        )

        # 模板 (池壁外表面)
        A_form = (2 * (L + B) * H_wall + L * B) * n
        items.append(
            BOQItem(
                self._next_seq(),
                "T11-2",
                f"{name}—模板",
                "m²",
                round(A_form, 0),
                CIVIL["formwork_wall"],
                round(A_form * CIVIL["formwork_wall"]),
                "建筑工程",
                nt,
            )
        )

        # 防水
        A_wp = (2 * (L + B) * H_wall + L * B) * n
        items.append(
            BOQItem(
                self._next_seq(),
                "T11-1",
                f"{name}—内防水",
                "m²",
                round(A_wp, 0),
                CIVIL["waterproof_inner"],
                round(A_wp * CIVIL["waterproof_inner"]),
                "建筑工程",
                nt,
            )
        )

        return items

    @staticmethod
    def _excavation_depth(result, H: float, tf: float) -> float:
        """依据高程数据计算实际挖方深度 (m)

        优先使用 ElevationData, 无高程数据时回退到传统估算 H+tf+0.5
        """
        if result and hasattr(result, "elevation") and result.elevation is not None:
            elev = result.elevation
            # 挖深 = 地面 - 池底 + 底板厚 + 垫层0.5m (含工作面)
            depth = elev.ground_elevation - elev.bottom_elevation + tf + 0.5
            return max(depth, 0.0)  # 地上池不挖方
        # 回退: 传统方法
        return H + tf + 0.5

    def _pipe_network_detailed(self, pipe_node) -> List[BOQItem]:
        """管网造价 — 详细版 (逐段计算, 分项汇总)

        直接使用 estimate_pipe_network() 的分项汇总结果,
        确保与独立管网概算报告完全一致.
        """
        from .pipe_network_cost import estimate_pipe_network

        est = estimate_pipe_network(pipe_node)
        if est is None:
            return self._pipe_network(pipe_node)  # 回退

        items = []
        # ── 按管径汇总 (展示用,不计入总价) ──
        for d in sorted(est.by_diameter.keys()):
            length = est.by_diameter[d]
            items.append(
                BOQItem(
                    self._next_seq(),
                    f"G-{d}",
                    f"DN{d}管道 (展示长度)",
                    "m",
                    round(length, 1),
                    0.0,
                    0.0,
                    "建筑工程",
                    "pipe_network",
                )
            )
        # ── 分项造价 (使用 est 汇总值,与独立概算完全一致) ──
        items.append(
            BOQItem(
                self._next_seq(),
                "G-MAT",
                "管道材料+铺设",
                "项",
                1,
                est.total_pipe_cost,
                est.total_pipe_cost,
                "建筑工程",
                "pipe_network",
            )
        )
        items.append(
            BOQItem(
                self._next_seq(),
                "G-EARTH",
                "沟槽土方开挖回填",
                "项",
                1,
                est.total_earthwork,
                est.total_earthwork,
                "建筑工程",
                "pipe_network",
            )
        )
        items.append(
            BOQItem(
                self._next_seq(),
                "G-MACH",
                "施工机械台班",
                "项",
                1,
                est.total_machine,
                est.total_machine,
                "建筑工程",
                "pipe_network",
            )
        )
        items.append(
            BOQItem(
                self._next_seq(),
                "G-LABOR",
                "人工工时",
                "项",
                1,
                est.total_labor,
                est.total_labor,
                "建筑工程",
                "pipe_network",
            )
        )
        items.append(
            BOQItem(
                self._next_seq(),
                "G-MH",
                "检查井",
                "项",
                1,
                est.total_manhole,
                est.total_manhole,
                "建筑工程",
                "pipe_network",
            )
        )
        # 泵站
        if est.pump_station_cost > 0:
            items.append(
                BOQItem(
                    self._next_seq(),
                    "SB-BZ",
                    "污水提升泵站",
                    "座",
                    1,
                    est.pump_station_cost,
                    est.pump_station_cost,
                    "设备购置",
                    "pipe_network",
                )
            )
        return items

    def _pipe_network(self, pipe_node) -> List[BOQItem]:
        """管网造价"""
        items = []
        stats = getattr(pipe_node, "_pipe_stats", {})
        for d, length in sorted(stats.items()):
            d = int(d)
            price = get_pipe_price(d)
            items.append(
                BOQItem(
                    self._next_seq(),
                    f"G-{d}",
                    f"DN{d}管道铺设(含土方+检查井)",
                    "m",
                    round(length, 1),
                    price,
                    round(length * price),
                    "建筑工程",
                    "pipe_network",
                )
            )
        return items

    @staticmethod
    def _val(dims: Dict, keyword: str) -> Optional[float]:
        """从维度字典中提取数值 — 4 级鲁棒匹配

        匹配顺序:
          1. 精确子串匹配 (keyword in chinese_key)
          2. 中文基础名剥离拉丁后缀后匹配
          3. 中文别名扩展表 (处理"池长"→"单池长度"/"单格长度"等变体)
          4. 英文简写匹配 (vectorized results 回退)
          5. 拉丁后缀单字符匹配
        """
        # Level 1: 精确子串
        for k, (v, u) in dims.items():
            if keyword in k:
                return v

        # Level 2: 剥离末尾拉丁后缀, 用中文核心词匹配
        # "总高度 H" → "总高度" → 匹配 "总高度" / "滤池总高度"
        parts = keyword.rsplit(" ", 1)
        if len(parts) == 2:
            cn_base, latin = parts
            if latin and all(c.isascii() for c in latin):
                for k, (v, u) in dims.items():
                    if cn_base in k:
                        return v

        # Level 3: 中文别名扩展 — 处理模块间命名差异
        CN_ALIASES = {
            "池径": ["池径", "井径"],
            "池长": ["池长", "单池长度", "单格长度", "渠长"],
            "池宽": ["池宽", "单池宽度", "单格宽度", "渠宽"],
            "总高度": ["总高度", "滤池总高度", "栅后总高"],
            "池数": [
                "池数",
                "格数",
                "系列数",
                "滤池格数",
                "渠道数",
                "格栅台数",
                "磁盘台数",
            ],
        }
        if len(parts) == 2:
            cn_base, latin = parts
            if cn_base in CN_ALIASES:
                for alias in CN_ALIASES[cn_base]:
                    for k, (v, u) in dims.items():
                        if alias in k:
                            return v

        # Level 4: 英文简写匹配 (vectorized/solution-browser 回退)
        ENG_FALLBACK = {
            "池径 D": ["D"],
            "井径 D": ["D"],
            "池长 L": ["L", "L_pool", "L_total"],
            "池宽 B": ["B", "B_pool", "B_channel"],
            "渠长 L": ["L"],
            "渠宽 B": ["B"],
            "总高度 H": ["H_total"],
            "总高度": ["H_total"],
            "单格长度 L": ["L", "L_total"],
            "单格宽度 B": ["B", "B_channel"],
            "滤池总高度": ["H_total"],
            "栅槽总长 L": ["L_total"],
            "栅槽宽度 B": ["B"],
            "栅后总高 H": ["H_total"],
            "池数": ["n"],
            "滤池格数": ["n"],
            "渠道数": ["n"],
            "格栅台数": ["n"],
            "磁盘台数": ["n"],
        }
        for eng in ENG_FALLBACK.get(keyword, []):
            if eng in dims:
                return dims[eng][0]

        # Level 5: 拉丁后缀单字符匹配
        # "池长 L" → suffix="L" → 匹配英文键 "L", "L_pool", ...
        suffix = keyword.split()[-1] if keyword else ""
        if len(suffix) <= 2 and suffix.isascii():
            for k, (v, u) in dims.items():
                if (
                    k == suffix
                    or k.startswith(suffix + "_")
                    or k.endswith("_" + suffix)
                ):
                    return v
        return None
