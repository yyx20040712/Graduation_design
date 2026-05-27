"""
base.py — 基础数据模型与节点基类

定义排水工程设计工具中所有模块共用的:
  - 水质水量数据类 (WaterQuality, WaterFlow)
  - 计算结果数据类 (NodeResult)
  - 可调参数定义 (ParamDef)
  - 端口定义 (Port, PortType)
  - 节点基类 (NodeBase) 与节点状态枚举 (NodeState)
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, ClassVar, Dict, List, Optional, Tuple

import numpy as np  # noqa: F401 — used in string type annotations

from _logging import get_logger

from .dimension_formulas import get_dimension_category, get_formula
from .param_mixin import ParamMixin
from .sludge_mixin import SludgeMixin

_log = get_logger(__name__)

# ── 水质属性列表（在 WaterQuality、NodeBase.execute()、GraphExecutor 中复用）──
WATER_QUALITY_ATTRS = ["BOD5", "COD", "SS", "NH3N", "TN", "TP"]
# ═════════════════════════════════════════════════════════════════════
# 物理常数
# ═════════════════════════════════════════════════════════════════════
GRAVITY = 9.81  # 重力加速度 m/s²
PI = math.pi
WATER_DENSITY = 1000.0  # 水密度 kg/m³
WET_SLUDGE_DENSITY = 1000.0  # 湿污泥密度 kg/m³


# ═════════════════════════════════════════════════════════════════════
# 枚举类型
# ═════════════════════════════════════════════════════════════════════


class PortType(Enum):
    """端口类型 — 不同类型不能互连"""

    WATER = auto()  # 水量传递端口
    QUALITY = auto()  # 水质传递端口
    MIXED = auto()  # 水量+水质复合端口(通常用于输入/输出节点)
    SLUDGE = auto()  # 污泥传递端口(含湿泥量/干固量/含水率/VS比)


class NodeState(Enum):
    """节点计算状态"""

    CLEAN = auto()  # 计算完成,结果有效
    DIRTY = auto()  # 参数已修改,需重算

    COMPUTING = auto()  # 正在计算中
    ERROR = auto()  # 计算失败,有错误信息


# ═════════════════════════════════════════════════════════════════════
# 数据类: 参数定义
# ═════════════════════════════════════════════════════════════════════


@dataclass
class ParamDef:
    """可调参数的定义

    每个节点通过定义 ParamDef 列表来声明用户可以调整的参数.
    UI 层读取这些定义来生成滑块+输入框.

    Attributes:
        name: 参数显示名称(中文)
        key: 代码中使用的键名(英文)
        value: 当前值
        default: 默认值
        min_val: 最小值(含)
        max_val: 最大值(含)
        step: 步进值(滑块精度)
        unit: 单位(如 "m", "h", "m³/h")
        description: 参数说明 tooltip
    """

    name: str
    key: str
    value: float
    default: float
    min_val: float
    max_val: float
    step: float = 0.01
    unit: str = ""
    description: str = ""

    def reset(self) -> None:
        """恢复为默认值"""
        self.value = self.default

    # ═══════════════ 设置 ═══════════════
    def set_value(self, v: float) -> None:
        """设置值,自动钳制到 [min_val, max_val]"""
        self.value = max(self.min_val, min(self.max_val, v))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "key": self.key,
            "value": self.value,
            "default": self.default,
            "min": self.min_val,
            "max": self.max_val,
            "step": self.step,
            "unit": self.unit,
            "description": self.description,
        }

    @classmethod

    # ═══════════════ 反序列化 ═══════════════
    def from_dict(cls, d: Dict[str, Any]) -> "ParamDef":
        return cls(
            name=d["name"],
            key=d["key"],
            value=d["value"],
            default=d["default"],
            min_val=d["min"],
            max_val=d["max"],
            step=d.get("step", 0.01),
            unit=d.get("unit", ""),
            description=d.get("description", ""),
        )


# ═════════════════════════════════════════════════════════════════════
# 数据类: 水质
# ═════════════════════════════════════════════════════════════════════


@dataclass
class WaterQuality:
    """水质参数 — 所有浓度单位均为 mg/L

    Attributes:
        BOD5: 五日生化需氧量
        COD:  化学需氧量
        SS:   悬浮固体
        NH3N: 氨氮
        TN:   总氮
        TP:   总磷
        pH:   pH 值
    """

    BOD5: float = 200.0
    COD: float = 400.0
    SS: float = 220.0
    NH3N: float = 35.0
    TN: float = 45.0
    TP: float = 5.0
    pH: float = 7.0

    # 出水标准(一级A,GB18918-2002)
    EFFLUENT_STANDARD: Dict[str, float] = field(
        default_factory=lambda: {
            "BOD5": 10.0,
            "COD": 50.0,
            "SS": 10.0,
            "NH3N": 5.0,
            "TN": 15.0,
            "TP": 0.5,
        },
        init=False,
        repr=False,
    )

    def apply_removal(self, rates: Dict[str, float]) -> "WaterQuality":
        """应用去除率,返回新的 WaterQuality

        Args:
            rates: 各指标的去除率(小数,如 0.40 = 40%)
                   未指定的指标保持原值

        Returns:
            去除后的新水质对象
        """
        return WaterQuality(
            BOD5=self.BOD5 * (1 - rates.get("BOD5", 0)),
            COD=self.COD * (1 - rates.get("COD", 0)),
            SS=self.SS * (1 - rates.get("SS", 0)),
            NH3N=self.NH3N * (1 - rates.get("NH3N", 0)),
            TN=self.TN * (1 - rates.get("TN", 0)),
            TP=self.TP * (1 - rates.get("TP", 0)),
            pH=self.pH,  # pH 不通过简单去除率计算
        )

    # ═══════════════ 状态检查 ═══════════════
    def check_effluent(self) -> Dict[str, Tuple[bool, float]]:
        """检查是否达到一级A出水标准

        Returns:
            {指标: (是否达标, 差值)} 例如 {"BOD5": (True, -5.3)}
            差值 ≤0 表示达标(实际值 ≤ 标准值)
        """
        result = {}
        checks = ["BOD5", "COD", "SS", "NH3N", "TN", "TP"]
        for key in checks:
            actual = getattr(self, key)
            standard = self.EFFLUENT_STANDARD[key]
            diff = actual - standard
            result[key] = (diff <= 0, round(diff, 2))
        return result

    # ═══════════════ 序列化 ═══════════════
    def to_dict(self) -> Dict[str, float]:
        return {
            "BOD5": self.BOD5,
            "COD": self.COD,
            "SS": self.SS,
            "NH3N": self.NH3N,
            "TN": self.TN,
            "TP": self.TP,
            "pH": self.pH,
        }

    @classmethod

    # ═══════════════ 反序列化 ═══════════════
    def from_dict(cls, d: Dict[str, float]) -> "WaterQuality":
        return cls(
            BOD5=d.get("BOD5", 200.0),
            COD=d.get("COD", 400.0),
            SS=d.get("SS", 220.0),
            NH3N=d.get("NH3N", 35.0),
            TN=d.get("TN", 45.0),
            TP=d.get("TP", 5.0),
            pH=d.get("pH", 7.0),
        )

    # 浓度单位转换辅助
    @staticmethod
    def mgL_to_kgm3(val_mgL: float) -> float:
        """mg/L → kg/m³"""
        return val_mgL / 1000.0

    @staticmethod
    def kgm3_to_mgL(val_kgm3: float) -> float:
        """kg/m³ → mg/L"""
        return val_kgm3 * 1000.0


# ═════════════════════════════════════════════════════════════════════
# 数据类: 水量
# ═════════════════════════════════════════════════════════════════════


@dataclass
class WaterFlow:
    """水量参数

    核心设计数据(来自中期报告):
      Q_design = 0.57 m³/s (最大设计流量)
      Q_avg_daily = 34760.7 m³/d (平均日流量)
      Kz = 1.4 (总变化系数)

    Attributes:
        Q_design:    最大设计流量 m³/s
        Q_avg_daily: 平均日流量 m³/d
        Kz:          总变化系数
    """

    Q_design: float = 0.57
    Q_avg_daily: float = 34760.7
    Kz: float = 1.4

    @property
    def Q_avg_hourly(self) -> float:
        """平均时流量 m³/h"""
        return self.Q_avg_daily / 24.0

    @property
    def Q_avg_second(self) -> float:
        """平均秒流量 m³/s"""
        return self.Q_avg_daily / 86400.0

    @property
    def Q_design_Ls(self) -> float:
        """最大设计流量 L/s"""
        return self.Q_design * 1000.0

    # ── 便捷单位转换 ──
    def Q_design_as(self, unit: str) -> float:
        """返回指定单位的设计流量"""
        conversions = {
            "m3/s": self.Q_design,
            "L/s": self.Q_design * 1000,
            "m3/h": self.Q_design * 3600,
            "m3/d": self.Q_design * 86400,
        }
        if unit not in conversions:
            raise ValueError(f"不支持的单位: {unit},支持: {list(conversions.keys())}")
        return conversions[unit]

    # ═══════════════ 序列化 ═══════════════
    def to_dict(self) -> Dict[str, float]:
        return {
            "Q_design": self.Q_design,
            "Q_avg_daily": self.Q_avg_daily,
            "Kz": self.Kz,
        }

    @classmethod

    # ═══════════════ 反序列化 ═══════════════
    def from_dict(cls, d: Dict[str, float]) -> "WaterFlow":
        return cls(
            Q_design=d.get("Q_design", 0.57),
            Q_avg_daily=d.get("Q_avg_daily", 34760.7),
            Kz=d.get("Kz", 1.4),
        )


# ═════════════════════════════════════════════════════════════════════
# 数据类: 污泥流量
# ═════════════════════════════════════════════════════════════════════


@dataclass
class SludgeFlow:
    """污泥流量参数 — 用于污泥处理线的数据传递

    污泥处理各单元通过 SLUDGE 端口传递此类对象.

    Attributes:
        Q_wet:       湿污泥量 m³/d
        DS:          干固体量 kg/d
        P_moisture:  含水率(小数,0~1,如 0.96 = 96%)
        VS_ratio:    挥发性固体占比(小数,0~1,如 0.60 = 60%)
    """

    Q_wet: float = 0.0
    DS: float = 0.0
    P_moisture: float = 0.96
    VS_ratio: float = 0.60

    def __post_init__(self):
        """钳制含水率和 VS 比到 [0, 1]"""
        self.P_moisture = max(0.0, min(1.0, self.P_moisture))

        self.VS_ratio = max(0.0, min(1.0, self.VS_ratio))

    @property
    def Q_wet_m3h(self) -> float:
        """湿污泥量 m³/h"""
        return self.Q_wet / 24.0

    @property
    def DS_ton(self) -> float:
        """干固体量 t/d"""
        return self.DS / 1000.0

    # ═══════════════ 序列化 ═══════════════
    def to_dict(self) -> Dict[str, float]:
        return {
            "Q_wet": self.Q_wet,
            "DS": self.DS,
            "P_moisture": self.P_moisture,
            "VS_ratio": self.VS_ratio,
        }

    @classmethod

    # ═══════════════ 反序列化 ═══════════════
    def from_dict(cls, d: Dict[str, float]) -> "SludgeFlow":
        return cls(
            Q_wet=d.get("Q_wet", 0.0),
            DS=d.get("DS", 0.0),
            P_moisture=d.get("P_moisture", 0.96),
            VS_ratio=d.get("VS_ratio", 0.60),
        )

    @classmethod
    def from_dry_solids(
        cls, DS: float, P_moisture: float = 0.96, VS_ratio: float = 0.60
    ) -> "SludgeFlow":
        """从干固体量 + 含水率反算湿污泥量

        Args:
            DS: 干固体量 kg/d
            P_moisture: 含水率(如 0.96)
            VS_ratio: VS 占比

        Returns:
            SludgeFlow 对象
        """
        if P_moisture >= 1.0:
            return cls(
                Q_wet=float("inf"), DS=DS, P_moisture=P_moisture, VS_ratio=VS_ratio
            )
        Q_wet = DS / ((1.0 - P_moisture) * 1000.0)
        return cls(Q_wet=Q_wet, DS=DS, P_moisture=P_moisture, VS_ratio=VS_ratio)


# ═════════════════════════════════════════════════════════════════════
# 数据类: 高程计算结果
# ═════════════════════════════════════════════════════════════════════


@dataclass
class ElevationData:
    """单节点高程计算结果


    由 ElevationCalculator 后处理引擎填充,存入 NodeResult.elevation.

    Attributes:
        ground_elevation:       地面标高 m (绝对或相对)
        bottom_elevation:       池底/管内底标高 m
        water_elevation:        水面标高 m
        effective_depth:        有效水深 m
        super_elevation:        超高 m
        head_loss:              本节点水头损失 m
        head_loss_detail:       水头损失明细 (如 "格栅+局部0.25m")
        upstream_water_elevation: 上游水面标高 m (用于校核)
        formula:                高程计算公式说明
    """

    ground_elevation: float = 0.0
    bottom_elevation: float = 0.0
    water_elevation: float = 0.0
    effective_depth: float = 0.0
    super_elevation: float = 0.0
    head_loss: float = 0.0
    head_loss_detail: str = ""
    upstream_water_elevation: float = 0.0
    formula: str = ""

    # ═══════════════ 序列化 ═══════════════
    def to_dict(self) -> Dict[str, Any]:
        return {
            "ground_elevation": self.ground_elevation,
            "bottom_elevation": self.bottom_elevation,
            "water_elevation": self.water_elevation,
            "effective_depth": self.effective_depth,
            "super_elevation": self.super_elevation,
            "head_loss": self.head_loss,
            "head_loss_detail": self.head_loss_detail,
            "upstream_water_elevation": self.upstream_water_elevation,
            "formula": self.formula,
        }

    @classmethod

    # ═══════════════ 反序列化 ═══════════════
    def from_dict(cls, d: Optional[Dict[str, Any]]) -> Optional["ElevationData"]:
        if not d:
            return None
        return cls(
            ground_elevation=d.get("ground_elevation", 0.0),
            bottom_elevation=d.get("bottom_elevation", 0.0),
            water_elevation=d.get("water_elevation", 0.0),
            effective_depth=d.get("effective_depth", 0.0),
            super_elevation=d.get("super_elevation", 0.0),
            head_loss=d.get("head_loss", 0.0),
            head_loss_detail=d.get("head_loss_detail", ""),
            upstream_water_elevation=d.get("upstream_water_elevation", 0.0),
            formula=d.get("formula", ""),
        )


# ═════════════════════════════════════════════════════════════════════
# 数据类: 计算结果
# ═════════════════════════════════════════════════════════════════════


@dataclass
class NodeResult:
    """节点的完整计算结果

    Attributes:
        success:    计算是否成功
        params:     本次使用的输入参数 {key: value}
        dimensions: 构筑物尺寸 {名称: (数值, 单位)}
        checks:     校核结果 {约束名称: (是否通过, 实际值, 限值, 单位)}
        warnings:   警告信息列表
        error_msg:  错误信息(计算失败时)
        removal_rates: 本节点实际使用的污染物去除率
    """

    success: bool = True
    params: Dict[str, Any] = field(default_factory=dict)
    dimensions: Dict[str, Tuple[float, str]] = field(default_factory=dict)
    checks: Dict[str, Tuple[bool, float, str, str]] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    error_msg: str = ""
    removal_rates: Dict[str, float] = field(default_factory=dict)
    # 公式追踪 — mod 自带公式,避免 UI 模糊匹配
    dimension_formulas: Dict[str, str] = field(default_factory=dict)
    # 分类追踪 — mod 自带分类 (physical/computed/water_quality)
    dimension_categories: Dict[str, str] = field(default_factory=dict)
    # 作用域追踪 — 维度是单池/单格还是总体 (如 "single","total","per_unit")
    dimension_scopes: Dict[str, str] = field(default_factory=dict)
    # 水质追踪
    inlet_quality: Optional["WaterQuality"] = None
    outlet_quality: Optional["WaterQuality"] = None
    # 污泥追踪
    sludge_output: Optional["SludgeFlow"] = None
    # 高程计算结果 (由 ElevationCalculator 后处理填充)
    elevation: Optional["ElevationData"] = None
    # 安全系数 (0~1, 越大越远离约束边界)
    robustness: float = 0.0

    # 作用域 → 显示前缀映射 (类属性, 非实例字段)
    SCOPE_PREFIX: ClassVar[Dict[str, str]] = {
        "single": "[单池]",
        "total": "[总]",
        "per_unit": "[单格]",
        "per_series": "[单系列]",
        "per_pump": "[单泵]",
        "per_hopper": "[单斗]",
        "per_hole": "[单孔]",
        "sump": "[集水池]",
    }

    # ═══════════════ 查询/获取 ═══════════════
    def get_display_name(self, dim_name: str) -> str:
        """返回维度带作用域前缀的显示名"""
        scope = self.dimension_scopes.get(dim_name, "")
        prefix = self.SCOPE_PREFIX.get(scope, "")
        return f"{prefix}{dim_name}" if prefix else dim_name

    # ═══════════════ 节点管理 ═══════════════
    def add_dimension(
        self,
        name: str,
        value: float,
        unit: str = "m",
        formula: Optional[str] = None,
        category: Optional[str] = None,
        scope: Optional[str] = None,
    ) -> None:
        """添加构筑物尺寸

        Args:
            name: 尺寸名称(不含作用域前缀,如 "有效容积" 而非 "[单池]有效容积")

            value: 数值
            unit: 单位
            formula: 计算公式说明(可选.若为 None,自动从 DIM_FORMULAS 查找)
            category: 分类 ("physical"|"computed"|"water_quality").
                      若为 None,自动从 DIM_CATEGORIES 查找
            scope: 作用域标记 ("single"|"total"|"per_unit").
                   用于渲染时添加 [单池]/[总] 等前缀
        """
        self.dimensions[name] = (value, unit)
        if scope:
            self.dimension_scopes[name] = scope
        # 公式自动回退（v5.3: 模块级导入，消除懒加载开销）
        if formula is None:
            formula = get_formula(name, getattr(self, "node_type", ""))
        if formula:
            self.dimension_formulas[name] = formula
        # 分类自动回退
        if category is None:
            category = get_dimension_category(name)
        if category:
            self.dimension_categories[name] = category

    # ═══════════════ 状态检查 ═══════════════
    def add_check(
        self, name: str, passed: bool, actual: float, limit: str, unit: str = ""
    ) -> None:
        """添加校核结果

        Args:
            name: 约束名称(如 "径深比 D/h2")
            passed: 是否通过
            actual: 实际值
            limit: 限值描述(如 "6~12")
            unit: 单位
        """
        self.checks[name] = (passed, actual, limit, unit)

    # ═══════════════ 节点管理 ═══════════════
    def add_warning(self, msg: str) -> None:
        """添加警告"""
        self.warnings.append(msg)

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "success": self.success,
            "params": self.params,
            "dimensions": {k: list(v) for k, v in self.dimensions.items()},
            "checks": {k: list(v) for k, v in self.checks.items()},
            "warnings": self.warnings,
            "error_msg": self.error_msg,
            "removal_rates": self.removal_rates,
            "robustness": self.robustness,
            "sludge_output": (
                self.sludge_output.to_dict() if self.sludge_output else None
            ),
            "elevation": self.elevation.to_dict() if self.elevation else None,
        }
        if self.dimension_formulas:
            result["dimension_formulas"] = dict(self.dimension_formulas)
        if self.dimension_categories:

            result["dimension_categories"] = dict(self.dimension_categories)
        if self.dimension_scopes:
            result["dimension_scopes"] = dict(self.dimension_scopes)
        # 水质追踪数据 (可选,用于 save/load 恢复)
        if self.inlet_quality is not None:
            result["inlet_quality"] = self.inlet_quality.to_dict()
        if self.outlet_quality is not None:
            result["outlet_quality"] = self.outlet_quality.to_dict()
        return result

    @classmethod
    def failed(cls, error_msg: str) -> "NodeResult":
        """快速创建失败结果"""
        return cls(success=False, error_msg=error_msg)


# ═════════════════════════════════════════════════════════════════════
# 端口定义
# ═════════════════════════════════════════════════════════════════════


@dataclass
class Port:
    """节点的输入/输出端口

    Attributes:
        port_id: 唯一标识
        name: 端口显示名称
        port_type: 端口类型(水量/水质/混合)
        direction: "input" 或 "output"
        node_id: 所属节点 ID
        connections: 已连接的端口 ID 列表
    """

    port_id: str
    name: str
    port_type: PortType
    direction: str  # "input" | "output"
    node_id: str = ""
    connections: List[str] = field(default_factory=list)

    @property
    def is_input(self) -> bool:
        return self.direction == "input"

    @property
    def is_output(self) -> bool:
        return self.direction == "output"

    def can_connect(self, other: "Port") -> bool:
        """检查两个端口是否可以连接"""
        # 必须一个输入一个输出
        if self.direction == other.direction:
            return False
        # 类型必须兼容
        if self.port_type != other.port_type and PortType.MIXED not in (
            self.port_type,
            other.port_type,
        ):
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "port_id": self.port_id,
            "name": self.name,
            "port_type": self.port_type.name,
            "direction": self.direction,
            "node_id": self.node_id,
            "connections": self.connections,
        }

    @classmethod

    # ═══════════════ 反序列化 ═══════════════
    def from_dict(cls, d: Dict[str, Any]) -> "Port":
        return cls(
            port_id=d["port_id"],
            name=d["name"],
            port_type=PortType[d["port_type"]],
            direction=d["direction"],
            node_id=d.get("node_id", ""),
            connections=d.get("connections", []),
        )


# ═════════════════════════════════════════════════════════════════════
# 节点基类
# ═════════════════════════════════════════════════════════════════════


class NodeBase(ParamMixin, SludgeMixin):
    """所有处理节点的抽象基类

    每个处理单元(调节池、格栅、CASS...)继承此类,
    实现 calculate() 方法.

    子类需要定义:
      - NODE_TYPE: 节点类型标识字符串
      - NODE_NAME: 节点中文名称
      - NODE_CATEGORY: 节点分类(用于UI节点库分组)
      - input_ports / output_ports: 端口列表
      - _default_params: 参数默认值 {key: value}
      - _param_defs: 可调参数定义列表
      - _removal_rates: 默认污染物去除率

    自 v5.1 起参数管理和污泥管理分离到 ParamMixin / SludgeMixin.
    """

    # ── 子类必须覆盖的类属性 ──
    NODE_TYPE: str = "base"
    NODE_NAME: str = "基础节点"
    NODE_CATEGORY: str = "未分类"

    def __init__(self, node_id: Optional[str] = None):
        self.node_id = node_id or f"{self.NODE_TYPE}-{uuid.uuid4().hex[:8]}"
        self._state = NodeState.DIRTY
        self._result: Optional[NodeResult] = None
        self._sludge_output: Optional["SludgeFlow"] = None

        # 参数 (delegated to ParamMixin)
        self._init_params()

        # 端口
        self.input_ports: List[Port] = []
        self.output_ports: List[Port] = []
        self._init_ports()

        # 画布位置(UI 使用)
        self.x: float = 0.0
        self.y: float = 0.0

    def _init_ports(self) -> None:
        """初始化端口 — 子类重写以添加自定义端口"""
        self.input_ports.append(
            Port(
                port_id=f"{self.node_id}-in",
                name="进水",
                port_type=PortType.MIXED,
                direction="input",
                node_id=self.node_id,
            )
        )
        self.output_ports.append(
            Port(
                port_id=f"{self.node_id}-out",
                name="出水",
                port_type=PortType.MIXED,
                direction="output",
                node_id=self.node_id,
            )
        )

    # ═══════════════ 计算引擎 ═══════════════
    def calculate(self, flow: WaterFlow, quality: WaterQuality) -> NodeResult:
        """核心计算逻辑 — 子类必须重写

        Args:
            flow: 上游汇入的水量
            quality: 上游汇入的水质

        Returns:
            NodeResult 计算结果
        """
        raise NotImplementedError(
            f"{self.NODE_NAME}({self.NODE_TYPE}) 必须实现 calculate() 方法"
        )

    @classmethod
    def _vectorized_compute(
        cls, grid: dict, flow: "WaterFlow", quality: "WaterQuality", fixed: dict
    ) -> "np.ndarray":
        """向量化批量计算 — 子类覆盖以启用方案空间枚举

        Args:
            grid: {param_key: np.ndarray of shape (N,)}  自由变量网格
            flow: WaterFlow 标量(上游水量,不随 grid 变化)
            quality: WaterQuality 标量(上游水质)
            fixed: {param_key: float}  固定参数值

        Returns:
            numpy 结构化数组,字段包含:
              - 所有尺寸值 (float)
              - ok_<约束名> (bool)  各约束是否通过
              - cost_* (float)  成本估算相关字段
        """
        raise NotImplementedError(
            f"{cls.NODE_NAME}({cls.NODE_TYPE}) 未实现 _vectorized_compute()"
        )

    @classmethod

    # ═══════════════ 事件回调 ═══════════════
    def get_solution_space(cls, flow: "WaterFlow", quality: "WaterQuality") -> "List":
        """枚举当前流量/水质下的所有可行解

        依赖 _vectorized_compute() 的实现.
        返回按成本排序的 Solution 列表(最多 200 个).
        """
        from .solution_space import enumerate_solutions

        return enumerate_solutions(cls.NODE_TYPE, flow, quality)

    # ── 公共方法 ──

    @property
    def state(self) -> NodeState:
        return self._state

    @state.setter
    def state(self, s: NodeState) -> None:
        self._state = s
        if s == NodeState.DIRTY:
            self._result = None

    @property
    def result(self) -> Optional[NodeResult]:
        return self._result

    @property
    def is_dirty(self) -> bool:
        return self._state in (NodeState.DIRTY, NodeState.ERROR)

    # ═══════════════ 执行引擎 ═══════════════
    def execute(
        self, flow: WaterFlow, quality: WaterQuality
    ) -> Tuple[Optional[NodeResult], WaterFlow, WaterQuality]:
        """执行计算并返回结果+下游数据

        这是 GraphExecutor 调用的入口.
        计算成功后,应用去除率生成下游水质.
        同时记录 inlet_quality 和 outlet_quality 用于水质追踪.

        Returns:
            (result, downstream_flow, downstream_quality)
        """
        self.state = NodeState.COMPUTING
        try:
            result = self.calculate(flow, quality)
            self._result = result
            result.node_type = self.NODE_TYPE  # for per-mod formula lookup
            # 记录水质追踪数据
            result.inlet_quality = WaterQuality(
                BOD5=quality.BOD5,
                COD=quality.COD,
                SS=quality.SS,
                NH3N=quality.NH3N,
                TN=quality.TN,
                TP=quality.TP,
                pH=quality.pH,
            )
            if result.success:
                self.state = NodeState.CLEAN
                result.sludge_output = self._sludge_output
                # 应用去除率生成下游水质
                downstream_quality = quality.apply_removal(self._removal_rates)
                result.outlet_quality = downstream_quality
                # 添加水质维度到结果
                for attr in WATER_QUALITY_ATTRS:
                    in_val = getattr(quality, attr)
                    out_val = getattr(downstream_quality, attr)
                    removal = (in_val - out_val) / in_val * 100 if in_val > 0 else 0
                    result.add_dimension(f"进水{attr}", round(in_val, 2), "mg/L")
                    result.add_dimension(f"出水{attr}", round(out_val, 2), "mg/L")
                    result.add_dimension(f"{attr}去除率", round(removal, 2), "%")
                return result, flow, downstream_quality
            else:
                self.state = NodeState.ERROR
                return result, flow, quality
        except Exception as e:
            self.state = NodeState.ERROR
            failed = NodeResult.failed(str(e))
            self._result = failed
            return failed, flow, quality

    # ── 序列化 ──

    # ═══════════════ 序列化 ═══════════════
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "id": self.node_id,
            "type": self.NODE_TYPE,
            "name": self.NODE_NAME,
            "category": self.NODE_CATEGORY,
            "position": {"x": self.x, "y": self.y},
            "params": dict(self._params),
            "removal_rates": dict(self._removal_rates),
            "ports": {
                "input": [p.to_dict() for p in self.input_ports],
                "output": [p.to_dict() for p in self.output_ports],
            },
            "cached_result": self._result.to_dict() if self._result else None,
            "state": self._state.name,
        }

    @classmethod

    # ═══════════════ 反序列化 ═══════════════
    def from_dict(cls, d: Dict[str, Any]) -> "NodeBase":
        """从字典反序列化(子类应覆盖以处理特定逻辑)"""
        node = cls(node_id=d["id"])
        node.x = d["position"]["x"]
        node.y = d["position"]["y"]
        for key, value in d.get("params", {}).items():
            node._params[key] = value
        for key, value in d.get("removal_rates", {}).items():
            node._removal_rates[key] = value
        # 恢复缓存的计算结果
        cached = d.get("cached_result")
        if cached:
            inlet_q = cached.get("inlet_quality")
            outlet_q = cached.get("outlet_quality")
            node._result = NodeResult(
                success=cached.get("success", True),
                params=cached.get("params", {}),
                dimensions={
                    k: tuple(v) for k, v in cached.get("dimensions", {}).items()
                },
                checks={k: tuple(v) for k, v in cached.get("checks", {}).items()},
                warnings=cached.get("warnings", []),
                error_msg=cached.get("error_msg", ""),
                removal_rates=cached.get("removal_rates", {}),
                dimension_formulas=cached.get("dimension_formulas", {}),
                dimension_categories=cached.get("dimension_categories", {}),
                inlet_quality=WaterQuality.from_dict(inlet_q) if inlet_q else None,
                outlet_quality=WaterQuality.from_dict(outlet_q) if outlet_q else None,
                sludge_output=(
                    SludgeFlow.from_dict(cached["sludge_output"])
                    if cached.get("sludge_output")
                    else None
                ),
                elevation=ElevationData.from_dict(cached.get("elevation")),
            )
        # 恢复状态 — 加载后始终标记为 DIRTY, 确保下次F5重算 (防止计算逻辑更新后缓存过期)
        node._state = NodeState.DIRTY
        return node

    def __repr__(self) -> str:
        return f"<{self.NODE_NAME} id={self.node_id} state={self._state.name}>"


# ═════════════════════════════════════════════════════════════════════
# 工具函数: 取整
# ═════════════════════════════════════════════════════════════════════


def ceil_to(value: float, precision: float = 0.1) -> float:
    """[DEPRECATED] 向上取整到指定精度

    自 v5.1 起已废弃.请直接使用 math.ceil(value / precision) * precision.
    保留此函数仅为向后兼容,将在 v6.0 中移除.

    Args:
        value: 原始值
        precision: 精度(如 0.1 = 取整到0.1m, 0.5 = 取整到0.5m)

    Examples:
        ceil_to(3.14159, 0.1) → 3.2
        ceil_to(3.14159, 0.5) → 3.5
    """
    import warnings

    warnings.warn(
        "ceil_to() is deprecated since v5.1. Use math.ceil(value / precision) * precision instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return math.ceil(value / precision) * precision


def round_to(value: float, precision: float = 0.1) -> float:
    """四舍五入到指定精度"""
    return round(value / precision) * precision
