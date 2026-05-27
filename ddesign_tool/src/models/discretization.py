"""
discretization.py — 参数离散化配置

为每个处理单元定义:
  - free:  自由变量(用户可选,离散化为 ≤4 个施工友好值)
  - fixed: 固定变量(规范规定或经验值)
  - cost_dims: 用于快速成本估算的维度键名列表

设计原则:
  1. 每个自由变量至多 4 个离散值
  2. 取值便于施工(0.5 步长、标准工程值、偶数优先)
  3. n ≥ 2 强制冗余(除紫外消毒渠道数可为1)
  4. 固定变量取规范推荐值或行业经验值
"""

from typing import Any, Dict, List

from _logging import get_logger

_log = get_logger(__name__)
# ═══════════════════════════════════════════════════════════════════
# 类型定义
# ═══════════════════════════════════════════════════════════════════

DiscreteConfig = Dict[str, Any]  # {"free": {...}, "fixed": {...}}

# ═══════════════════════════════════════════════════════════════════
# 各模块离散化配置 — v4.2: 全部从 mods/*/discretization.json 加载,无硬编码
# ═══════════════════════════════════════════════════════════════════

DISCRETE_CONFIGS: Dict[str, DiscreteConfig] = {}  # 仅保留类型声明,数据全部来自 JSON


# ═══════════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════════

# Cached merged configs
_merged_configs = None


def _get_merged_configs():
    """v4.2: 全部从 mods/*/discretization.json 加载,无硬编码回退"""
    global _merged_configs
    if _merged_configs is None:
        _merged_configs = load_mod_discretizations()
    return _merged_configs


def _refresh_merged_configs():
    """强制刷新合并配置(社区模组热添加后调用)"""
    global _merged_configs
    _merged_configs = None
    return _get_merged_configs()


def get_config(node_type: str) -> DiscreteConfig:
    """获取某节点类型的离散化配置(含模组扩展)"""
    configs = _get_merged_configs()
    if node_type not in configs:
        # 缓存可能过期(社区模组在首次合并后添加),强制重新合并
        global _merged_configs
        _merged_configs = None
        configs = _get_merged_configs()
    if node_type not in configs:
        raise KeyError(f"未知节点类型: {node_type},可用: {list(configs.keys())}")
    return configs[node_type]


def get_free_keys(node_type: str) -> List[str]:
    """获取自由变量键名列表 (排除同时出现在 fixed 中的显示型变量)"""
    cfg = get_config(node_type)
    fixed_keys = set(cfg.get("fixed", {}).keys())
    return [k for k in cfg["free"] if k not in fixed_keys]


def get_free_values(node_type: str) -> List[List[float]]:
    """获取自由变量取值列表 (保持键顺序, 排除显示型变量)"""
    cfg = get_config(node_type)
    fixed_keys = set(cfg.get("fixed", {}).keys())
    return [cfg["free"][k] for k in cfg["free"] if k not in fixed_keys]


def grid_size(node_type: str) -> int:
    """计算网格总组合数"""
    cfg = get_config(node_type)
    fixed_keys = set(cfg.get("fixed", {}).keys())
    size = 1
    for k, vals in cfg["free"].items():
        if k not in fixed_keys:
            size *= len(vals)
    return size


# ═══════════════════════════════════════════════════════════════════
# 模块 -> 旧版 ParamDef 映射(用于向后兼容滑动条)
# 当用户在「手动微调」模式下调整滑块时,滑块的允许值
# 来自当前选中方案的 free 参数值.
# ═══════════════════════════════════════════════════════════════════


def get_allowed_values(node_type: str, param_key: str) -> List[float]:
    """获取某参数允许的离散值列表(用于滑块步进约束)

    仅 free 参数有离散值,fixed 参数使用自由输入(Entry+Scale).
    返回空列表 → UI 使用自由输入模式.
    """
    cfg = get_config(node_type)
    if param_key in cfg["free"]:
        return list(cfg["free"][param_key])
    # fixed 参数不禁用自由输入 —— 返回空列表
    return []


def get_constraint_types(node_type: str) -> Dict[str, str]:
    """获取约束类型分类 {display_name: 'original'|'result'}"""
    cfg = get_config(node_type)
    return cfg.get("constraint_types", {})


def get_original_constraints(node_type: str) -> List[str]:
    """获取原始约束名称列表(固定设计参数)"""
    types = get_constraint_types(node_type)
    return [k for k, v in types.items() if v == "original"]


def get_result_constraints(node_type: str) -> List[str]:
    """获取结果约束名称列表(校核阈值范围)"""
    types = get_constraint_types(node_type)
    return [k for k, v in types.items() if v == "result"]


# ═══════════════════════════════════════════════════════════════════
# 模组离散化配置加载
# ═══════════════════════════════════════════════════════════════════


def load_mod_discretizations() -> Dict[str, dict]:
    """v4.2: 从所有模组的 discretization.json 加载配置(core/ + community/)

    单一数据源: mods/core/{id}/discretization.json
    无硬编码回退,每个模组的 JSON 是其离散化配置的唯一来源.
    """
    try:
        from mods.mod_manager import get_mod_manager

        mgr = get_mod_manager()
        mgr.load_all()
        return mgr.get_all_discretizations()
    except Exception as e:
        _log.warning("operation failed: %s", e, exc_info=True)
        return {}
