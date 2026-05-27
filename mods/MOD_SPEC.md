# 🔧 排水工程设计工具 — 模组编写规范 v5.1

> **类比**: Minecraft Forge/Fabric 模组开发。一个文件夹 = 一个模组，零框架修改。
> **原则**: 每个模组完全自包含。**不需要修改任何集中式 Python 文件**。
> **受众**: AI 编程助手、模组开发者、毕业设计维护者。

---

## 快速参考

| 你要做什么 | 需要创建/修改的文件 |
|-----------|-------------------|
| 新建一个处理单元 | `mod.json` + `__init__.py` + `discretization.json` + `labels.json` (4 文件) |
| 修改计算逻辑 | `__init__.py` (calculate + _vectorized_compute) |
| 修改可调参数 | `__init__.py` (_default_params + _build_param_defs) + `mod.json` (parameters) |
| 修改约束条件 | `discretization.json` (constraint_keys/names/limits) + `__init__.py` (add_check + ok_*/val_*) |
| 修改维度显示标签 | `labels.json` (dimensions + vec_fields) |
| 修改作用域前缀 | `labels.json` (dim_scopes) |
| 修改水头损失 | `mod.json` (elevation_loss) |
| 添加维度公式 | `labels.json` (formulas) — v5.1 新增，无需修改全局 DIM_FORMULAS |

**v5.1 核心变更**:
- `ceil_to()` 已废弃，统一使用 `math.ceil(x / step) * step`
- 公式已下沉到各模组 `labels.json["formulas"]`，新增模组无需修改全局 `dimension_formulas.py`
- 节点注册统一走 `ModManager.register_infra_node()`
- 新增 `_validate_param_consistency()` 自动检查 mod.json 与代码参数一致性
- 新增 `.validator-notes.json` 和 `.validator-baseline.json` 格式

---

## 1. 模组文件结构

```
mods/core/{mod_id}/               # 或 mods/community/{mod_id}/
├── mod.json                      # [必需] 元数据 + 参数 + 端口 + 水头损失
├── __init__.py                   # [必需] NodeBase 子类
├── discretization.json           # [必需] 自由/固定参数 + 约束定义
└── labels.json                   # [必需] 维度标签 + 向量化标签 + 作用域
```

**lables.json 结构**:
```json
{
  "dimensions": { ... },   // [v5.0] 标量维度名 → [符号, 中文名]
  "vec_fields":  { ... },  // 向量化字段名 → [符号, 中文名, 单位]
  "dim_scopes":  { ... },  // [v5.0] 维度名 → 作用域键
  "params":      { ... }   // (可选) 参数标签, mod.json 已自动生成
}
```

---

## 2. mod.json — 完整规范

### 2.1 全部字段一览

| 字段 | 类型 | 必需 | 说明 | 示例 |
|------|------|------|------|------|
| `id` | string | ✅ | 小写英文+下划线 | `"tiaojiechi"` |
| `name` | string | ✅ | 中文显示名 | `"调节池"` |
| `version` | string | ✅ | 语义化版本 | `"1.0.0"` |
| `author` | string | ✅ | 作者 | `"yyx"` |
| `description` | string | ✅ | 一句话功能 | `"基于HRT法的调节池"` |
| `category` | string | ✅ | UI 菜单分组 | `"市政污水处理"` |
| `process_stage` | string | ✅ | 处理阶段(见§2.2) | `"primary"` |
| `icon` | string | — | Emoji 图标 | `"🔄"` |
| `node_type` | string | ✅ | 节点类型标识(同id) | `"tiaojiechi"` |
| `node_class` | string | ✅ | Python 类名 | `"TiaojiechiNode"` |
| `module_path` | string | ✅ | 空字符串(MC式自包含) | `""` |
| `inputs` | array | ✅ | 输入端口 | `[{"type":"MIXED","name":"进水"}]` |
| `outputs` | array | ✅ | 输出端口 | `[{"type":"MIXED","name":"出水"}]` |
| `parameters` | array | ✅ | 参数列表(见§2.3) | |
| `removal_rates` | object | ✅ | 污染物去除率 | `{"SS":0.50,"BOD5":0.30}` |
| `formula` | string | ✅ | 核心公式(简要) | `"V = Q × HRT / n"` |
| `formula_detail` | string | — | 公式变量说明(公式缺失时的兜底) | |
| `elevation_formula` | string | — | 高程公式说明 | |
| `elevation_loss` | object | ✅ | 水头损失(见§2.4) | `{"value":0.30}` |
| `dependencies` | array | — | 依赖模组ID | `[]` |
| `tags` | array | — | 搜索标签 | `["预处理","调节"]` |
| `references` | array | — | 参考规范 | `["GB50014-2021 §4.2"]` |

### 2.2 process_stage — 处理阶段

| 标识符 | 含义 | 方案浏览器 | 典型模组 |
|--------|------|-----------|---------|
| `io` | 输入/输出 | 跳过 | pipe_network, water_quality, combiner, kw_input |
| `primary` | 一级处理(含预处理) | ✅ | 调节池, 粗/细格栅, 沉砂池, 初沉池 |
| `secondary` | 二级处理(生物) | ✅ | CASS, AAO, 二沉池 |
| `tertiary` | 深度处理 | ✅ | 高密度沉淀池, V型滤池, 紫外消毒 |
| `sludge` | 污泥处理 | ✅ | 浓缩池, 消化池, 脱水间, 干化 |
| `mine_water` | 矿井水处理 | ✅ | 矿井水调节池, 平流沉砂池, 磁混凝 |
| `collection` | 集配水模组 | — | 集水井, 配水井, 配水渠 |
| `elevation` | 高程模组 | 跳过 | 进厂水面标高, 管道水头损失 |

### 2.3 parameters — 参数定义

**规则**: `parameters` 数组必须与 `_default_params()` 返回的**全部键**一一对应。

```json
{
  "key": "HRT", "symbol": "HRT", "name": "水力停留时间",
  "unit": "h", "default": 8, "min": 6, "max": 12, "step": 1,
  "description": "≥6h，矿井水取8h"
}
```

| 字段 | 必需 | 说明 |
|------|:--:|------|
| `key` | ✅ | 与 `_default_params()` 键一致 |
| `symbol` | ✅ | 工程符号——**用键名本身，不用中文** |
| `name` | ✅ | 中文名称（≠ 键名） |
| `unit` | ✅ | 单位，必须非空，无量纲填 `"-"` |
| `default` | ✅ | 与 `_default_params()` 值一致 |
| `min` | ✅ | 与 `_build_param_defs()` 一致 |
| `max` | ✅ | 同上 |
| `step` | ✅ | 同上 |
| `description` | — | Tooltip 说明 |

### 2.4 elevation_loss — 水头损失

```json
{"elevation_loss": {"value": 0.30, "formula": "经验值: 0.30m"}}
```

| value | 含义 |
|-------|------|
| `> 0` | 水头损失 (m)，下游水面 = 上游 - value |
| `0.0` | 泵站节点 — 从参数读取扬程 |
| 不填 | 回退默认 0.2m |

### 2.5 端口类型

| 类型 | 含义 | 连通规则 |
|------|------|---------|
| `WATER` | 仅水量(WaterFlow) | 可连 WATER/MIXED |
| `QUALITY` | 仅水质(WaterQuality) | 可连 QUALITY/MIXED |
| `MIXED` | 水量+水质 | 万能端口 |
| `SLUDGE` | 污泥流(SludgeFlow) | 仅连 SLUDGE，允许多股合并 |

### 2.6 完整示例

```json
{
  "id": "kw_tiaojiechi", "name": "矿井水调节池", "version": "2.0.0",
  "author": "Graduation Design Team",
  "description": "矿井水专用调节池，HRT≥6h，兼顾煤粉预沉淀功能。",
  "category": "矿井水处理", "process_stage": "mine_water", "icon": "🪣",
  "node_type": "kw_tiaojiechi", "node_class": "KwTiaojiechiNode",
  "module_path": "",
  "inputs": [{"type": "MIXED", "name": "进水"}],
  "outputs": [{"type": "MIXED", "name": "出水"}],
  "parameters": [
    {"key": "n", "symbol": "n", "name": "池数量", "unit": "座", "default": 4, "min": 4, "max": 8, "step": 2},
    {"key": "HRT", "symbol": "HRT", "name": "水力停留时间", "unit": "h", "default": 8, "min": 6, "max": 12, "step": 1},
    {"key": "h_eff", "symbol": "h_eff", "name": "有效水深", "unit": "m", "default": 4.0, "min": 3.0, "max": 5.0, "step": 0.5}
  ],
  "removal_rates": {"BOD5": 0.05, "COD": 0.10, "SS": 0.30},
  "formula": "V = Q_avg × HRT × k / n",
  "elevation_loss": {"value": 0.30, "formula": "经验值: 0.30m"},
  "tags": ["矿井水", "调节"], "references": ["煤炭矿井水处理设计规范"]
}
```

---

## 3. __init__.py — NodeBase 子类实现

### 3.1 类结构模板

```python
"""模块说明 — 公式来源: [规范引用]"""
import math, numpy as np
from typing import Dict, List
from models.base import (
    NodeBase, NodeResult, WaterFlow, WaterQuality,
    ParamDef, ceil_to,
)

class MyModuleNode(NodeBase):
    NODE_TYPE = "my_module"       # 与 mod.json node_type 一致
    NODE_NAME = "模块中文名"       # UI 显示
    NODE_CATEGORY = "一级处理"     # 与 mod.json category 一致

    # ── 1. 默认参数 (完整参数集) ──
    @classmethod
    def _default_params(cls) -> Dict[str, float]:
        return {"n": 2, "HRT": 6.0, "h_eff": 4.0, "h_super": 0.5}

    # ── 2. UI 参数定义 (仅需滑块的参数) ──
    def _build_param_defs(self) -> List[ParamDef]:
        return [
            ParamDef("池数", "n", value=2, default=2,
                     min_val=2, max_val=8, step=1, unit="座"),
            ParamDef("停留时间", "HRT", value=6, default=6,
                     min_val=4, max_val=12, step=0.5, unit="h"),
        ]

    # ── 3. 默认去除率 ──
    @classmethod
    def _default_removal_rates(cls) -> Dict[str, float]:
        return {"SS": 0.0, "BOD5": 0.0, "COD": 0.0}

    # ── 4. 标量计算 (F5 执行) ──
    def calculate(self, flow: WaterFlow, quality: WaterQuality) -> NodeResult:
        n = int(self.get_param("n"))
        HRT = self.get_param("HRT")
        h_eff = self.get_param("h_eff")
        h_super = self.get_param("h_super")

        result = NodeResult(success=True)
        result.params = {"n": n, "HRT": HRT, "h_eff": h_eff, "h_super": h_super}

        Q_avg_h = flow.Q_avg_hourly
        V_eff = Q_avg_h * HRT / n

        # 维度名保持干净（不加前缀），作用域通过 scope= 声明
        result.add_dimension("池数", n, "座")
        result.add_dimension("有效容积", round(V_eff, 1), "m³",
                             formula="V = Q × HRT / n",
                             category="physical",
                             scope="single")       # 渲染时自动加 [单池]
        result.add_dimension("总有效容积", round(V_eff * n, 1), "m³",
                             formula="V_total = V_single × n",
                             category="physical",
                             scope="total")        # 渲染时自动加 [总]
        result.add_check("HRT >= 4h", HRT >= 4, round(HRT, 1), ">= 4", "h")

        return result

    # ── 5. 向量化计算 (方案浏览器) ──
    @classmethod
    def _vectorized_compute(cls, grid, flow, quality, fixed) -> np.ndarray:
        n = grid["n"].astype(np.int32)
        HRT = grid["HRT"]
        N = len(n)

        Q_avg_h = flow.Q_avg_hourly
        V_eff = Q_avg_h * HRT / n

        ok_HRT = HRT >= 4

        dtype = np.dtype([
            ("V_eff", np.float64), ("HRT_out", np.float64),
            ("L", np.float64), ("B", np.float64), ("H", np.float64),
            ("concrete_m3", np.float64),
            ("ok_HRT", np.bool_), ("val_HRT", np.float64),
        ])
        result = np.empty(N, dtype=dtype)
        result["V_eff"] = V_eff; result["HRT_out"] = HRT
        result["H"] = h_eff + h_super
        result["concrete_m3"] = V_eff * 1.2
        result["ok_HRT"] = ok_HRT; result["val_HRT"] = HRT
        return result
```

### 3.2 `add_dimension` 完整签名

```python
def add_dimension(self, name: str, value: float, unit: str = "m",
                  formula: Optional[str] = None,
                  category: Optional[str] = None,
                  scope: Optional[str] = None) -> None:
```

| 参数 | 必需 | 说明 |
|------|:--:|------|
| `name` | ✅ | **干净的维度名**（不加 `[单池]` 等前缀） |
| `value` | ✅ | 数值 |
| `unit` | ✅ | 单位 |
| `formula` | 强烈建议 | 公式。若为 None 则从 DIM_FORMULAS 子串匹配查找 |
| `category` | 强烈建议 | `"physical"` / `"computed"` / `"water_quality"` |
| `scope` | 推荐 | 作用域键，见 §5.3。UI 渲染时自动添加前缀 |

### 3.3 必须遵守的规则

| 规则 | 说明 |
|------|------|
| **`_default_params` 包含全部参数** | 包括无 UI 滑块的固定参数 |
| **`_build_param_defs` 仅含 UI 参数** | key/name/unit/default/min/max/step 全部填写 |
| **`result.params` 包含全部参数** | `{k: self.get_param(k) for k in self._default_params()}` |
| **维度名不含前缀** | 用 `scope=` 声明作用域，不要 `"[单池]有效容积"` |
| **`add_dimension(formula=, category=)`** | 显式传公式和分类 |
| **向量化须含标准字段** | `L`, `B`, `H`(或`D`), `concrete_m3` — 缺则成本为零 |
| **向量化约束字段** | 每个 constraint_key 须有 `ok_<key>`(bool) + `val_<key>`(float64) |
| **标量/向量化一致性** | 同一组参数下两者产生相同的约束判断结果 |

---

## 4. discretization.json — 方案空间配置

```json
{
  "free": {
    "n": [2, 3, 4],
    "HRT": [6.0, 8.0, 10.0, 12.0]
  },
  "fixed": {
    "h_super": 0.5,
    "P_density": 8
  },
  "constraint_keys": ["LB_ratio", "HRT_actual"],
  "constraint_names": [
    "长宽比 L/B",
    "实际 HRT"
  ],
  "constraint_limits": {
    "长宽比 L/B": "2~4",
    "实际 HRT": "6~12"
  },
  "constraint_types": {
    "长宽比 L/B": "result",
    "实际 HRT": "result"
  }
}
```

**关键规则**:
- `constraint_keys` 后缀 = `_vectorized_compute` 的 `ok_<suffix>` / `val_<suffix>` 后缀
- `constraint_names` = `add_check(name, ...)` 的 name **完全一致**（含空格、标点）
- `free` 变量每项 ≤6 个值 → 控制组合爆炸

---

## 5. labels.json — 维度标签 + 作用域 [v5.0]

### 5.1 完整格式

```json
{
  "dimensions": {
    "池数":           ["n", "池数"],
    "有效容积":       ["V_eff", "有效容积"],
    "总有效容积":     ["V_total", "总有效容积"],
    "设计水平流速":   ["v_h", "设计水平流速"]
  },
  "vec_fields": {
    "V_eff":         ["V_eff", "有效容积", "m³"],
    "HRT_actual":    ["HRT", "实际停留时间", "h"]
  },
  "dim_scopes": {
    "有效容积":       "single",
    "总有效容积":     "total"
  }
}
```

### 5.2 `dimensions` — 标量维度标签 [v5.0 主要标签源]

`calculate()` 中每个 `add_dimension` 的名称都应在此有对应条目。
格式: `"维度名": ["符号", "中文物理意义"]`

**新增模组时**: 只需将标签写在这里，**不需要修改 `dimension_labels.py`**。
系统通过 `_build_dynamic_labels()` 自动合并所有模组的 `labels.json["dimensions"]`。

### 5.3 `dim_scopes` — 作用域声明 [v5.0 新增]

UI 渲染时根据此声明自动添加 `[单池]` / `[总]` 等前缀。

| scope 键 | 显示前缀 | 适用场景 |
|----------|---------|---------|
| `single` | `[单池]` | 每池独立的值（如单池容积） |
| `total` | `[总]` | 全部池合计的值（如总需氧量） |
| `per_unit` | `[单格]` | 每格独立（如单格过滤面积） |
| `per_series` | `[单系列]` | 每系列独立（如 AAO 厌氧区容积） |
| `sump` | `[集水池]` | 集水池专用 |

### 5.4 `vec_fields` — 向量化字段标签

`_vectorized_compute` 的 dtype 字段名（非 `ok_`/`val_`）都应在此有条目。
格式: `"字段名": ["符号", "中文名", "单位"]`

---

## 6. 注册清单 (创建新模组)

- [ ] **Step 1**: 创建文件夹 `mods/core/{mod_id}/`
- [ ] **Step 2**: 编写 `mod.json`
  - [ ] 所有字段填写完整
  - [ ] `parameters` 数组 = `_default_params()` 全部键，每个含 symbol/name/unit
  - [ ] `elevation_loss` 已配置
- [ ] **Step 3**: 编写 `__init__.py`
  - [ ] `_default_params()` 包含所有参数
  - [ ] `_build_param_defs()` 仅 UI 可见参数
  - [ ] `calculate()`: `result.params` 包含全部键，`add_dimension` 含 `formula=/category=/scope=`
  - [ ] `_vectorized_compute()`: dtype 含 L/B/H/concrete_m3 + ok_*/val_*
- [ ] **Step 4**: 编写 `labels.json`
  - [ ] `dimensions`: 所有 `add_dimension` 的维度名 → `[符号, 中文名]`
  - [ ] `vec_fields`: 所有向量化 dtype 字段 → `[符号, 中文名, 单位]`
  - [ ] `dim_scopes`: 需加 `[单池]`/`[总]` 前缀的维度 → scope 键
- [ ] **Step 5**: 编写 `discretization.json`
  - [ ] free/fixed/constraint_keys/constraint_names/constraint_limits/constraint_types 六项齐全
  - [ ] constraint_names = add_check() name 完全一致
- [ ] **Step 6**: 同步到 `ddesign_tool/mods/core/{mod_id}/` (两目录内容一致)
- [ ] **Step 7**: 运行 `pytest tests/` — 无回归
- [ ] **Step 8**: 重启应用，验证菜单出现、结果面板标签正确、Excel 输出完整

---

## 7. 常见陷阱

| 陷阱 | 预防 |
|------|------|
| 维度标签显示裸英文 | `labels.json["dimensions"]` 缺该维度条目 |
| 向量化标签缺失 | `labels.json["vec_fields"]` 缺该 dtype 字段 |
| 方案浏览器崩溃 NameError | `_vectorized_compute` dtype 字段名与赋值变量名不匹配 |
| 参数符号/名称/单位空白 | `mod.json.parameters` 缺少该键 |
| Excel 输出"无法提取尺寸" | 向量化 dtype 缺 L/B/H/D 标准字段 |
| 缺 concrete_m3 | 工程概算成本为 0 |
| 缺 val_<key> | 安全裕度恒为 0 |
| **[v5.0]** 维度加了前缀但公式丢失 | 维度名应保持干净，前缀用 `scope=` 或 `dim_scopes` 声明 |
| **[v5.1]** 使用 ceil_to() | 已废弃，使用 `math.ceil(x / step) * step` 替换 |
| **[v5.1]** 缺少 .validator-notes.json | 对有意偏离的检查添加设计决策说明 |

---

## 8. v5.1 新增规范

### 8.1 ceil_to 废弃 (2026-05-27)

自 v5.1 起，`ceil_to()` 函数标记为 deprecated。所有模组必须使用：

```python
# ❌ 旧写法 (v5.0 及更早)
B = ceil_to(B_theory, 0.5)

# ✅ 新写法 (v5.1+)
B = math.ceil(B_theory / 0.5) * 0.5
```

`ceil_to()` 将在 v6.0 中移除。当前调用时输出 DeprecationWarning。

### 8.2 .validator-notes.json 格式

每个模组可选添加 `.validator-notes.json` 文件，用于标记有意偏离验证器的设计决策：

```json
{
  "notes": {
    "constraint_mismatch": "约束名称与代码不一致是有意的 — 为了UI显示简洁",
    "calc_failure": "默认参数在小流量下会失败，这是设计预期"
  }
}
```

### 8.3 .validator-baseline.json 格式

运行 `--generate-baseline` 后自动生成。包含当前所有 FAIL/WARN 的指纹，用于抑制已知问题。

```json
{
  "generated_at": "2026-05-27T12:00:00",
  "fingerprints": {
    "constraint_mismatch": "sha256:abc123..."
  }
}
```

### 8.5 公式下沉到模组 (2026-05-27)

自 v5.1 起，维度公式不再集中在全局 `dimension_formulas.py` 的 `DIM_FORMULAS` 字典。每个模组在自己的 `labels.json` 中定义公式：

```json
// mods/core/gaomidu/labels.json
{
  "dimensions": { ... },
  "vec_fields": { ... },
  "formulas": {
    "表面负荷": "q' = Q / (n × A_single)",
    "固体通量": "G = DS / A",
    "轴向流速": "v_axial = Q / A_cross"
  }
}
```

查找优先级: `labels.json["formulas"]` → 全局通用回退 `DIM_FORMULAS`。

### 8.6 参数一致性自动验证 (2026-05-27)

`ModManager._validate_param_consistency()` 在加载每个模组时自动对比 `mod.json` 参数与 `_build_param_defs()`，发现 default/min/max 不一致时记录 WARN。

### 8.7 完整性测试 (2026-05-27)

新增 `tests/unit/test_main_window_integrity.py` — AST 静态分析确保 `MainWindow` 类中所有 `self.xxx()` 调用都有对应的 `def xxx()` 定义。**新增 UI 方法后必须同步添加测试引用。**

### 8.8 日志规范 (2026-05-27)

统一使用 `from _logging import get_logger` + `_log = get_logger(__name__)`。
禁止模块内 `import logging; log = logging.getLogger("...")` 的旧模式。

---

## 9. 架构演进

| 版本 | 里程碑 |
|------|--------|
| v3.2 | MC式模组架构: 一个文件夹=一个模组 |
| v3.3 | 双水线 + 标准化输出契约 L/B/D/H |
| v3.5 | 全厂高程 + UI 公式/约束面板 |
| v4.3 | 参数完整性审计, PARAM_TABLE 清零, node_type 感知查找 |
| v4.5 | 统一维度过滤, 361标签, 中英文双模式分类 |
| v5.0 | labels.json 成为主要标签源, dim_scopes 作用域系统 |
| **v5.1** | **ceil_to 废弃, 公式下沉, 数据源统一, 日志统一, 参数自动验证, 97% 测试覆盖, black/isort** |

---

> **版本**: v5.1 | **最后更新**: 2026-05-27 | **维护者**: Graduation Design Team
