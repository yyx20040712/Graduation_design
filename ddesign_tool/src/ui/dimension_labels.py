"""
dimension_labels.py — 维度标签解析与格式化 (v5.1)

数据表已移至 dimension_data.py.
为「结果」面板和 Excel 输出提供 4 列显示:
  符号(字母) | 物理意义 | 单位 | 取值
"""

from typing import Dict, List, Tuple

from _logging import get_logger

# 从 dimension_data 导入数据表
from .dimension_data import (
    DIMENSION_TABLE,
    PARAM_TABLE,
    VEC_FIELD_TABLE,
)

_log = get_logger(__name__)


def _clean_dimension_name(name: str) -> str:
    """清理维度名中的包裹括号和标注前缀:

    '设计总流量 Q_d(总)' → '设计总流量 Q_d'

    '[单池]有效容积' → '有效容积'

    '[总]有效容积 V' → '有效容积 V'

    """

    import re

    # 移除末尾的 (...)

    cleaned = re.sub(r"\([^)]*\)$", "", name).strip()

    # 移除开头的 [单池] [单格] [单系列] [总] [集水池] 等标注前缀

    cleaned = re.sub(
        r"^\[(?:单池|单格|单系列|单斗|单孔|总|集水池)\]", "", cleaned
    ).strip()

    return cleaned

    # ═══════════════ 标签解析 ═══════════════


def resolve_dimension(name: str) -> Tuple[str, str, str]:
    """解析维度名/参数键 → (符号, 物理意义, 单位)



    优先查 param_table (参数键), 其次 vec_table (向量化字段名),

    然后 dim_table (维度名), 最后动态匹配/回退.

    """

    param_table, dim_table, vec_table = _get_dynamic_labels()

    # 0. 参数键精确匹配

    if name in param_table:

        return param_table[name]

    # 0.5. 向量化字段名匹配

    if name in vec_table:

        return vec_table[name]

    # 1. 维度名精确匹配

    if name in dim_table:

        symbol, meaning = dim_table[name]

        return symbol, meaning, ""

    # 1.5. 模糊匹配: 先清理包裹内容再试 (如 "有效水深 H(单池)" → "有效水深 H")

    clean_name = _clean_dimension_name(name)

    if clean_name != name and clean_name in dim_table:

        symbol, meaning = dim_table[clean_name]

        return symbol, meaning, ""

    # 1.6. 模糊匹配: 去掉末尾的变量名再试 (如 "有效水深 h" → "有效水深")

    parts = name.rsplit(" ", 1)

    if (
        len(parts) == 2
        and parts[1]
        and not any("\u4e00" <= c <= "\u9fff" for c in parts[1])
    ):

        base_name = parts[0]

        if base_name in dim_table:

            symbol, meaning = dim_table[base_name]

            return symbol, meaning, ""

    # 1.7. 清理后再模糊匹配

    clean_parts = clean_name.rsplit(" ", 1)

    if (
        len(clean_parts) == 2
        and clean_parts[1]
        and not any("\u4e00" <= c <= "\u9fff" for c in clean_parts[1])
    ):

        base_name = clean_parts[0]

        if base_name in dim_table:

            symbol, meaning = dim_table[base_name]

            return symbol, meaning, ""

    # 2. 动态水质/去除率匹配

    if name.startswith("进水") and len(name) > 2:

        pollutant = name[2:]

        pollutant_labels = {
            "BOD5": ("BOD₅", "五日生化需氧量"),
            "COD": ("COD", "化学需氧量"),
            "SS": ("SS", "悬浮固体"),
            "NH3N": ("NH₃-N", "氨氮"),
            "TN": ("TN", "总氮"),
            "TP": ("TP", "总磷"),
            "pH": ("pH", "酸碱度"),
            "TDS": ("TDS", "总溶解固体"),
        }

        if pollutant in pollutant_labels:

            sym, meaning = pollutant_labels[pollutant]

            return f"{sym}_in", f"进水 {meaning}", "mg/L"

    if name.startswith("出水") and len(name) > 2:

        pollutant = name[2:]

        if pollutant in {"BOD5", "COD", "SS", "NH3N", "TN", "TP"}:

            sym_map = {
                "BOD5": "BOD₅",
                "COD": "COD",
                "SS": "SS",
                "NH3N": "NH₃-N",
                "TN": "TN",
                "TP": "TP",
            }

            meaning_map = {
                "BOD5": "五日生化需氧量",
                "COD": "化学需氧量",
                "SS": "悬浮固体",
                "NH3N": "氨氮",
                "TN": "总氮",
                "TP": "总磷",
            }

            return f"{sym_map[pollutant]}_out", f"出水 {meaning_map[pollutant]}", "mg/L"

    if "去除率" in name:

        pollutant = name.replace("去除率", "")

        sym_map = {
            "BOD5": "η_BOD",
            "COD": "η_COD",
            "SS": "η_SS",
            "NH3N": "η_NH₃",
            "TN": "η_TN",
            "TP": "η_TP",
        }

        meaning_map = {
            "BOD5": "BOD₅去除率",
            "COD": "COD去除率",
            "SS": "SS去除率",
            "NH3N": "氨氮去除率",
            "TN": "总氮去除率",
            "TP": "总磷去除率",
        }

        if pollutant in sym_map:

            return sym_map[pollutant], meaning_map[pollutant], "%"

    # 3. DN管道长度

    if name.startswith("DN") and "管道长度" in name:

        dn = name[2:].split("管道")[0].strip()

        return f"L_DN{dn}", f"DN{dn} 管道长度", "m"

    # 4. 尝试从名称末尾提取符号 (如 "池长 L")

    # 先清理包裹括号

    clean_name = _clean_dimension_name(name)

    parts = clean_name.rsplit(" ", 1)

    if (
        len(parts) == 2
        and len(parts[1]) <= 8
        and not any("\u4e00" <= c <= "\u9fff" for c in parts[1])
    ):

        # 末尾是英文/符号

        symbol = parts[1]

        meaning = parts[0]

    else:

        # 纯中文名: 截取前12字符作为符号, 全名作为物理意义

        symbol = clean_name[:12]

        meaning = clean_name

    # ═══ 兜底告警: 标签未在 DIMENSION_TABLE / VEC_FIELD_TABLE / labels.json 中找到 ═══

    _warn_fallback(name)

    return symbol, meaning, ""


# ── 兜底告警(每个键仅告警一次,避免刷屏)──

_fallback_warned: set = set()


def _warn_fallback(key: str) -> None:
    """当维度名未命中任何标签表时,记录 WARNING 日志(每个 key 仅一次)."""

    if key in _fallback_warned:

        return

    _fallback_warned.add(key)

    _log.warning(
        "维度 '%s' 未在标签表中找到,使用兜底符号."
        "请在 DIMENSION_TABLE / VEC_FIELD_TABLE 或模组 labels.json 中添加条目.",
        key,
    )

    # ═══════════════ 设置 ═══════════════


def reset_fallback_warnings() -> None:
    """清除兜底告警记录(用于测试重置)."""

    _fallback_warned.clear()

    # ═══════════════ 查询/获取 ═══════════════


def get_fallback_warnings() -> list:
    """返回所有产生兜底告警的维度名列表."""

    return sorted(_fallback_warned)

    # ═══════════════ 事件回调 ═══════════════


def validate_dimension_labels() -> dict:
    """校验所有已加载模组的维度标签完整性.



    遍历每个模组的标量 add_dimension 名称和向量化 dtype 字段名,

    检查是否在 DIMENSION_TABLE / VEC_FIELD_TABLE / labels.json 中有对应条目.



    Returns:

        {

            "total": 检查总数,

            "missing": [{"mod": 模组ID, "key": 维度名, "path": "scalar"|"vectorized"}],

            "ok": True 若全部通过

        }

    """

    from mods.mod_manager import get_mod_manager

    mgr = get_mod_manager()

    mgr.load_all()

    missing = []

    checked = 0

    # 1. 检查标量维度名(来自各 mod 的 calculate() 中的 add_dimension 调用)

    #    通过扫描源代码太复杂,改用向量化字段间接推断.

    #    实际校验重点在向量化字段(这是漏标签的重灾区).

    # 2. 检查向量化字段名(来自 _vectorized_compute dtype 和 labels.json)

    for mod_id, mod_info in mgr.mods.items():

        labels = mgr.load_labels(mod_id)

        vec_labels = labels.get("vec_fields", {}) if labels else {}

        # 获取该模组的节点类以读取向量化 dtype

        node_cls = mgr.get_node_class(mod_id)

        if node_cls is None:

            continue

        # 通过临时实例化获取参数 → 枚举一个方案 → 检查维度名

        try:

            from models.base import WaterFlow, WaterQuality
            from models.solution_space import get_engine

            engine = get_engine()

            # 用默认流量水质枚举

            flow = WaterFlow(Q_design=0.1, Q_avg_daily=8640, Kz=1.0)

            quality = WaterQuality()

            sols = engine.enumerate(mod_id, flow, quality)

            if not sols:

                continue

            sol = sols[0]

            for k in sol.dimensions.keys():

                checked += 1

                sym, meaning, unit = resolve_dimension(k)

                if meaning == k:

                    # 未命中任何标签表

                    missing.append(
                        {
                            "mod": mod_id,
                            "key": k,
                            "path": "vectorized",
                            "hint": f"请在 VEC_FIELD_TABLE 或 {mod_id}/labels.json 中添加 '{k}' 条目",
                        }
                    )

        except Exception as e:

            _log.warning("operation failed: %s", e, exc_info=True)

    return {
        "total": checked,
        "missing": missing,
        "ok": len(missing) == 0,
    }


def format_dimension_row(
    name: str, value, unit: str = "", node_type: str = ""
) -> Tuple[str, str, str]:
    """将维度项格式化为: (符号, 物理意义, 单位)



    Args:

        name: 维度名 (如 "单池长度 L")

        value: 维度值 (数字或字符串) — 用于水质等动态匹配

        unit: 调用方传入的单位 (如 "m")

        node_type: 节点类型 (用于模组级参数查找, 避免共享键冲突)



    Returns:

        (symbol, meaning, unit_str) — 取值由调用方自行格式化

    """

    # 1. Try per-mod parameter lookup (most accurate)

    if node_type:

        try:

            from mods.mod_manager import get_mod_manager

            mgr = get_mod_manager()

            mod_info = mgr.get_mod_by_node_type(node_type)

            if mod_info:

                for p in mod_info.parameters:

                    if p.key == name:

                        u = unit or p.unit or ""

                        return (p.key, p.name, u)

        except Exception as e:

            _log.warning("operation failed: %s", e, exc_info=True)

    # 2. Fall back to global table

    symbol, meaning, default_unit = resolve_dimension(name)

    u = unit or default_unit

    # 2.5. Unit inference for unnamed units (common patterns for params)

    if not u:

        u = _infer_unit(name)

    return symbol, meaning, u


def _infer_unit(name: str) -> str:
    """从变量名推断单位(用于参数显示的兜底逻辑)"""

    n = name.lower()

    # 管径

    if any(kw in n for kw in ["管径", "dn", "d_", "孔径"]):

        if "mm" in n:
            return "mm"

        return "m"

    # 流量

    if any(kw in n for kw in ["流量", "q_", "风量", "扬程"]):

        if "l/s" in n:
            return "L/s"

        if "m³/h" in n:
            return "m³/h"

        if "m³/d" in n:
            return "m³/d"

        return "m³/s"

    # 功率

    if any(kw in n for kw in ["功率", "轴功率"]):

        return "kW"

    # 面积

    if any(kw in n for kw in ["面积", "占地"]):

        return "m²"

    # 容积

    if any(kw in n for kw in ["容积", "贮泥", "集水"]):

        return "m³"

    # 长度/宽度/高度/深度

    if any(
        kw in n
        for kw in [
            "长度",
            "宽度",
            "高度",
            "深度",
            "渠宽",
            "堰长",
            "池长",
            "池宽",
            "渠长",
            "管长",
            "段长",
            "超高",
            "水深",
            "标高",
            "埋深",
            "间距",
            "坡降",
            "间隙",
            "覆盖",
            "覆土",
        ]
    ):

        return "m"

    # 流速/速度/负荷

    if any(kw in n for kw in ["流速", "速度", "线速"]):

        return "m/s"

    # 时间

    if any(
        kw in n for kw in ["hrt", "停留时间", "历时", "周期", "工作时间", "泥龄", "龄"]
    ):

        return "h"

    # 浓度

    if any(
        kw in n
        for kw in ["mlss", "浓度", "bod", "cod", "ss ", "氨氮", "总氮", "总磷", "tds"]
    ):

        return "mg/L"

    # 负荷率

    if any(kw in n for kw in ["负荷", "通量"]):

        return "kg/(m²·d)"

    # 需氧量

    if any(kw in n for kw in ["需氧量", "产氧"]):

        return "kgO₂/d"

    # 产量

    if any(kw in n for kw in ["产泥", "污泥量", "泥量", "砂量", "渣量"]):

        return "kg/d"

    # 药剂

    if any(kw in n for kw in ["pac", "pam", "耗量", "补充量"]):

        return "kg/d"

    # 污泥

    if any(
        kw in n
        for kw in [
            "含水率",
            "回收率",
            "占比",
            "比 ",
            "系数",
            "指数",
            "比例",
            "比 l/b",
            "比 b/h",
            "比 d/h",
            "充水比",
            "变化系数",
        ]
    ):

        return ""

    # 数量

    if any(kw in n for kw in ["数", "台", "个", "格", "排", "盘"]):

        return ""

    return ""


# ═══════════════════════════════════════════════════════════════════

# 参数枚举值 → 显示名称映射 (用于 result.params 的可读显示)

# ═══════════════════════════════════════════════════════════════════


_PARAM_VALUE_DISPLAY: Dict[str, Dict] = {
    # 格栅 — 栅条形状系数 β
    "bar_shape": {0: "0_矩形断面", 1: "1_半圆形断面", 2: "2_圆形断面"},
    # 污泥脱水 — 设备类型
    "equip_type": {0: "0_带式压滤机", 1: "1_离心脱水机"},
    # 污泥干化 — 干化方式
    "method": {0: "0_热干化", 1: "1_太阳能干化"},
}


# ═══════════════ 格式化 ═══════════════
def format_param_value(key: str, value) -> str:
    """将参数键值对格式化为可读显示字符串.



    对于枚举型参数(如 bar_shape=0), 返回 "0_矩形断面";

    对于浮点数, 返回保留2位小数的字符串;

    其他类型返回 str(value).

    """

    if key in _PARAM_VALUE_DISPLAY:

        mapping = _PARAM_VALUE_DISPLAY[key]

        try:

            int_val = int(value)

            if int_val in mapping:

                return mapping[int_val]

        except (ValueError, TypeError):

            pass

    if isinstance(value, float):

        return f"{value:.2f}"

    return str(value)


# ── 动态标签自动生成 ──


# ═══════════════ UI 构建 ═══════════════
def _build_dynamic_labels():
    """Build merged label tables from mod.json auto-generation + per-mod labels.json.

    Returns (param_table, dim_table, vec_table) — extended copies of the static tables.

    """

    try:

        from mods.mod_manager import get_mod_manager

        mgr = get_mod_manager()

        mgr.discover_all()

        param_table = dict(PARAM_TABLE)

        dim_table = dict(DIMENSION_TABLE)

        vec_table = dict(VEC_FIELD_TABLE)

        for mod_id, mod_info in mgr.mods.items():

            # Try per-mod labels.json

            labels = mgr.load_labels(mod_id)

            if labels:

                if "params" in labels:

                    param_table.update(labels["params"])

                if "dimensions" in labels:

                    dim_table.update(labels["dimensions"])

                if "vec_fields" in labels:

                    vec_table.update(labels["vec_fields"])

            # Always auto-generate param labels from mod.json (for keys not yet in table)

            for p in mod_info.parameters:

                if p.key not in param_table:

                    param_table[p.key] = (p.key, p.name, p.unit)

        return param_table, dim_table, vec_table

    except Exception as e:

        _log.warning("operation failed: %s", e, exc_info=True)

        return dict(PARAM_TABLE), dict(DIMENSION_TABLE), dict(VEC_FIELD_TABLE)


# Lazy cache

_dynamic_labels_cache = None


# ═══════════════ 查询/获取 ═══════════════
def _get_dynamic_labels():

    global _dynamic_labels_cache

    if _dynamic_labels_cache is None:

        _dynamic_labels_cache = _build_dynamic_labels()

    return _dynamic_labels_cache


# ═══════════════════════════════════════════════════════════════════

# 共享维度过滤器 — UI 和 Excel 输出共用同一逻辑,避免过滤不一致

# ═══════════════════════════════════════════════════════════════════


def is_water_quality_dim(key: str, unit: str) -> bool:
    """判断一个维度项是否属于水质数据(应在独立的水质表格中显示)



    水质数据的特征:

      - 含"去除率"字样(如 BOD5去除率)

      - 以"进水"/"出水"开头 且 单位为 mg/L(如 进水BOD5, 出水COD)



    Returns:

        True 若该维度应归入水质处理效果区,False 若应归入计算结果/构筑物尺寸区.

    """

    if "去除率" in key:

        return True

    if (key.startswith("进水") or key.startswith("出水")) and unit in ("mg/L",):

        return True

    return False


def is_internal_debug_dim(key: str) -> bool:
    """判断一个维度项是否为内部调试字段(val_*/ok_* 前缀)"""

    return key.startswith("val_") or key.startswith("ok_")


def split_dimensions(
    dimensions: "Dict[str, Tuple[float, str]]",
    dimension_categories: "Dict[str, str]",
) -> "Tuple[List, List, List, List]":
    """将 NodeResult.dimensions 拆分为 4 组.



    UI 结果面板 和 Excel 分类输出 均使用此函数,保证过滤逻辑唯一.



    Args:

        dimensions: NodeResult.dimensions {名称: (数值, 单位)}

        dimension_categories: NodeResult.dimension_categories {名称: "physical"|"computed"}



    Returns:

        (computed, physical, water_quality_in_out, water_quality_removal)

        每个元素为 [(key, value, unit), ...] 列表.

    """

    computed: list = []

    physical: list = []

    wq_in_out: list = []

    wq_removal: list = []

    for k, (v, u) in dimensions.items():

        # 1. 去除率 → 水质区

        if "去除率" in k:

            wq_removal.append((k, v, u))

            continue

        # 2. 进水/出水水质 → 水质区

        if (k.startswith("进水") or k.startswith("出水")) and u in ("mg/L",):

            wq_in_out.append((k, v, u))

            continue

        # 3. 内部调试字段 → 不显示

        if is_internal_debug_dim(k):

            continue

        # 4. 按分类分到物理尺寸 / 计算结果

        cat = dimension_categories.get(k, "computed")

        if cat == "physical":

            physical.append((k, v, u))

        else:

            computed.append((k, v, u))

    return computed, physical, wq_in_out, wq_removal
