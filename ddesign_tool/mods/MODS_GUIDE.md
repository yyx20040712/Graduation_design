# 🤖 AI Vibe-Coding 模组创作指南 v4.2

> **You are an AI agent. This guide is written for YOU.**
> Follow it exactly. Do not improvise on structure. Copy the templates verbatim.
> **版本**: v4.2 | **更新**: 2026-05-24 | **架构**: MC式即放即用 + 单一数据源 (JSON-only)

---

## 🎯 What You're Building

A **water treatment process module** (mod) for a drainage engineering design tool.
Each mod = one treatment unit. The tool uses a **DAG executor** with typed ports (WATER/QUALITY/MIXED/SLUDGE).

---

## 📁 File Structure

```
mods/core/{module_id}/
├── mod.json                    # [REQUIRED] metadata contract
├── __init__.py                 # [REQUIRED] FULL NodeBase subclass
├── discretization.json         # [REQUIRED] free/fixed vars + constraints
└── tests/test_{module_id}.py   # [REQUIRED]
```

**Everything auto-discovered**: UI menu, solution space, class registration, **formulas**, **categories**.

> ⚠️ **v4.1: 公式和分类均自带。** 每个 `add_dimension()` 显式传入 `formula=` 和 `category=`。若不传，自动从 `models/dimension_formulas.py` 子串匹配。

---

## 🧬 NodeBase 子类模板

```python
"""MODULE_ID.py — 模块中文名"""
import math, numpy as np
from typing import Dict, List, Tuple, Optional
from models.base import (
    NodeBase, NodeResult, WaterFlow, WaterQuality,
    ParamDef, Port, PortType, ceil_to, PI,
)

class ModuleNameNode(NodeBase):
    NODE_TYPE = "module_id"
    NODE_NAME = "模块中文名"
    NODE_CATEGORY = "一级处理"

    @classmethod
    def _default_params(cls) -> Dict[str, float]:
        return {"n": 2, "param2": 1.0}

    def _build_param_defs(self) -> List[ParamDef]:
        return [
            ParamDef("池数量", "n", value=2, default=2,
                     min_val=1, max_val=8, step=1, unit="座"),
        ]

    @classmethod
    def _default_removal_rates(cls) -> Dict[str, float]:
        return {"BOD5": 0.05, "COD": 0.05, "SS": 0.10,
                "NH3N": 0.0, "TN": 0.0, "TP": 0.0}

    def calculate(self, flow: WaterFlow, quality: WaterQuality) -> NodeResult:
        n = int(self.get_param("n"))
        result = NodeResult(success=True, params=dict(self._params))

        # ── 计算 ──
        D = 2.0; h = 3.0

        # ── v4.1: 显式传入 formula= 和 category= ──
        result.add_dimension("池径 D", D, "m",
            formula="D = √(4A/π), ceil_to 0.1m",
            category="physical")
        result.add_dimension("有效水深 h2", h, "m",
            formula="h2 = q_surf × t / 3600",
            category="physical")
        result.add_dimension("实际停留时间", 45.2, "s",
            formula="t_actual = V_eff / Q_single",
            category="computed")

        # ── 约束 ──
        result.add_check("径深比 D/h", 1.5 <= D/h <= 5.0,
                         round(D/h, 2), "1.5~5.0", "")
        return result
```

---

## 📐 维度公式与分类 (v4.1 核心)

### 架构

```
add_dimension(name, value, unit, formula="...", category="physical")
    │  formula=None / category=None (未传入)
    │       ↓
    │  auto-lookup from models/dimension_formulas.py
    │       ↓
    NodeResult.dimension_formulas[name]   ← 结果面板公式行
    NodeResult.dimension_categories[name] ← "计算结果" vs "构筑物尺寸" 分组
```

### `add_dimension()` 完整签名

```python
def add_dimension(self, name: str, value: float, unit: str = "m",
                  formula: Optional[str] = None,
                  category: Optional[str] = None) -> None:
```

| 参数 | 说明 | 自动回退 |
|------|------|---------|
| `formula` | 计算公式描述 | `get_formula(name)` → `DIM_FORMULAS` 子串匹配 |
| `category` | `"physical"`(构筑物尺寸) / `"computed"`(计算结果) / `"water_quality"`(水质) | `get_dimension_category(name)` → `DIM_CATEGORIES` 子串匹配 |

### 分类规则

| category | 含义 | 显示位置 |
|----------|------|---------|
| `"physical"` | 施工建造所需的几何参数 | 结果面板"构筑物尺寸"节 / Excel"构筑物尺寸"节 |
| `"computed"` | 由公式导出的非几何变量 | 结果面板"计算结果"节 / Excel"计算结果"节 |
| `"water_quality"` | 水质浓度/去除率 | "水质处理效果"节（不参与普通分组） |

典型例子：

| 维度 | category |
|------|----------|
| 池径 D, 池长 L, 总高度 H, 有效水深, 有效容积 | `physical` |
| 实际停留时间, 表面负荷, 流速, 日产泥量, 需氧量 | `computed` |
| 进水BOD5, 出水COD, BOD5去除率 | `water_quality` |

### 新增维度到字典

`ddesign_tool/src/models/dimension_formulas.py`:

```python
# 公式
DIM_FORMULAS["你的新维度名"] = "公式描述"

# 分类
DIM_CATEGORIES["你的新维度名"] = "physical"  # 或 "computed"
```

---

## 📐 参数分类 (v4.1)

`result.params` 中的参数按 `PARAM_CATEGORIES` 分三组显示：

| category | 中文名 | 典型参数 key |
|----------|--------|-------------|
| `"basic"` | 基本参数 | n, n_pumps, n_machines, bar_shape, equip_type |
| `"physical"` | 构筑物参数 | h_eff, h_super, B_channel, ratio_LB, s, b, alpha |
| `"operating"` | 运行参数 | q_surf, t, v, HRT, Q_pump, H_pump, X, T_clean |

新参数注册：

```python
PARAM_CATEGORIES["new_param_key"] = "basic"  # 或 "physical" / "operating"
```

---

## 📐 标准化输出契约

每个 `_vectorized_compute` dtype **必须**包含 L/B/D/H 标准字段 + `concrete_m3`：

| 池型 | L | B | D | H |
|------|---|---|---|---|
| 矩形池 | >0 | >0 | 0 | >0 |
| 圆形池 | 0 | 0 | >0 | >0 |

约束校核字段：每个 constraint_key 需要 `ok_<key>` (bool) + `val_<key>` (float64) 对。

---

## 🏗️ 污泥模组

`process_stage=sludge`，端口类型 `SLUDGE`。核心计算在 `execute_sludge(sludge)`:

```python
def _init_ports(self) -> None:
    self.input_ports = [Port(..., port_type=PortType.SLUDGE, ...)]
    self.output_ports = [Port(..., port_type=PortType.SLUDGE, ...)]

def calculate(self, flow, quality) -> NodeResult:
    return NodeResult(success=True)  # 水处理线跳过

def execute_sludge(self, sludge: SludgeFlow) -> Tuple[Optional[NodeResult], SludgeFlow]:
    result = NodeResult(success=True, params={...})
    result.add_dimension("进泥湿泥量", round(sludge.Q_wet, 2), "m³/d",
                         formula="Q_wet = DS/((1-P)×1000)", category="computed")
    sludge_out = SludgeFlow(Q_wet=..., DS=..., P_moisture=..., VS_ratio=...)
    self._sludge_output = sludge_out
    return result, sludge_out
```

---

## 🤖 mod.json 规范 (摘要)

```json
{
  "id": "MODULE_ID", "name": "中文名", "version": "1.0.0",
  "process_stage": "primary|secondary|tertiary|sludge|mine_water|collection|elevation",
  "node_type": "MODULE_ID", "node_class": "ModuleNameNode",
  "module_path": "",
  "inputs": [{"type": "MIXED|SLUDGE", "name": "进水"}],
  "outputs": [{"type": "MIXED|SLUDGE", "name": "出水"}],
  "parameters": [
    {"key": "n", "symbol": "n", "name": "池数量", "unit": "座",
     "default": 2, "min": 1, "max": 8, "step": 1}
  ],
  "removal_rates": {"BOD5": 0.0, "COD": 0.0, "SS": 0.0,
                     "NH3N": 0.0, "TN": 0.0, "TP": 0.0},
  "formula": "核心公式简述",
  "elevation_loss": {"type": "structure", "value": 0.3, "formula": "..."}
}
```

- `id` 小写+下划线, `module_path` 留空 `""`
- `removal_rates` 必须含全部 6 个 key
- `elevation_loss.value` 数字直接使用, `"computed"` 动态计算

---

## 🔢 discretization.json

```json
{
  "free": {"n": [2, 3, 4], "param2": [1.0, 1.5, 2.0]},
  "fixed": {"h_super": 0.5, "display_only_param": 0.8},
  "constraint_keys": ["Dh2", "h2"],
  "constraint_names": ["径深比 D/h2", "有效水深 h2"],
  "constraint_limits": {"径深比 D/h2": "2.0~2.5", "有效水深 h2": "1.0~2.0"},
  "constraint_types": {"径深比 D/h2": "result", "有效水深 h2": "result"},
  "display_name": "模块中文名",
  "estimator_type": "circular|rectangular"
}
```

- 每个 free 变量至多 4 个值
- **显示型自由变量**: 同时入 free(UI下拉) 和 fixed(实际值) — 不增加方案空间
- `constraint_keys` 匹配向量化 `ok_*` 后缀
- `constraint_names` 匹配 `add_check()` 第一个参数 **精确一致**

---

## 📋 Checklist

- [ ] **Step 1**: `mods/core/{id}/` + `mod.json` + `__init__.py` + `discretization.json`
- [ ] **Step 2**: 所有 `add_dimension()` 显式传入 `formula=` 和 `category=`
- [ ] **Step 3**: 新维度/参数在 `dimension_formulas.py` 注册 (DIM_FORMULAS + DIM_CATEGORIES + PARAM_CATEGORIES)
- [ ] **Step 4**: `constraint_keys` 匹配 `_vectorized_compute` dtype 中的 `ok_<key>` 后缀 **精确一致**
- [ ] **Step 5**: `constraint_names` 匹配 `add_check()` 第一个参数 **精确一致**
- [ ] **Step 6**: L/B/D/H 标准字段 + `concrete_m3` + `ok_*`/`val_*` 全部存在
- [ ] **Step 7**: 新维度在 `ui/dimension_labels.py` 注册 `DIMENSION_TABLE` + `VEC_FIELD_TABLE` 映射
- [ ] **Step 8**: 测试通过 → 同步到 `ddesign_tool/mods/core/{id}/`
- [ ] **Step 9**: 重启应用验证 → `ModManager` 加载 0 errors

---

## 🔒 v4.2 单一数据源原则

> **v4.2 已彻底消除 `DISCRETE_CONFIGS` 和 `CONSTRAINT_LIMITS` 硬编码。**
> 每个模组的 `discretization.json` 是其离散化配置的**唯一权威来源**。
> 不再需要在 `discretization.py` 或 `solution_space.py` 中同步任何数据。

### 数据流向

```
discretization.json (模组自带)  ─── 唯一源
    │
    ├── load_mod_discretizations() → _get_merged_configs() → get_config()
    │
    └── _validate_vectorized_output() → 校验 vectorized dtype 字段匹配
```

### 只修改模组文件，不碰引擎代码

```
✅ 新增模组只需:  mods/core/{id}/mod.json + __init__.py + discretization.json
❌ 不需要修改:    discretization.py / solution_space.py / mod_manager.py
```

### 仍然保留的跨模组共享数据（非模组配置，合理保留）

| 数据 | 文件 | 原因 |
|------|------|------|
| DIM_FORMULAS / DIM_CATEGORIES | dimension_formulas.py | 公式自动回退字典，跨模组共享 |
| DIMENSION_TABLE / VEC_FIELD_TABLE | dimension_labels.py | UI显示映射，非单模组配置 |
| _DEFAULT_HEAD_LOSS | elevation_calculator.py | 工程经验参考值（后续可迁移到 mod.json） |
| 定额单价 | cost/unit_prices.py | 2019黑龙江定额标准数据 |

---

## 🔄 MC 模组迁移检查清单（从 models/{id}.py 搬迁到 mods/）

> **背景**: v4.1 完成了所有模组从 `models/{id}.py` 到 `mods/core/{id}/__init__.py` 的 MC 迁移。
> 迁移过程中曾引发 **3 类 NameError** 和 **6 个模组静默加载失败**，以下是完整的防回归检查清单。

### ⚠️ 迁移前必须检查的 4 类引用

| # | 检查项 | 搜索命令 | 常见遗漏 |
|---|--------|---------|---------|
| 1 | `from models.{id} import` 残留 | `grep "from models\.(tiaojiechi\|geshan\|...)" --include="*.py" -r` | 测试文件、conftest.py、test_full_dag.py |
| 2 | `main_window.py` 顶层 import 断链 | 检查所有 `from ui.xxx import` 是否完整 | `FileManager`, `NodeCanvas`, `SolutionBrowser`, `format_dimension_row`, `format_param_value` |
| 3 | 模组 `__init__.py` 的自身 import | 检查是否 import 自身已删除的 models 路径 | `from models.jcws_smbg import ...` 应改为直接定义类 |
| 4 | 双目录同步 | `mods/core/{id}/` 与 `ddesign_tool/mods/core/{id}/` 内容完全一致 | 修改任意文件后立即同步 |

### 🔧 正确的导入方式（迁移后）

```python
# ❌ WRONG — 旧架构，文件已删除
from models.tiaojiechi import TiaojiechiNode
from models.jcws_smbg import JcwsSmbgNode

# ✅ CORRECT — 使用 ModManager 动态加载
from mods.mod_manager import get_mod_manager
TiaojiechiNode = get_mod_manager().load_mod("tiaojiechi")

# ✅ CORRECT — 直接 import（mods/core/ 已在 sys.path）
# 前提：setup_import_paths() 已调用
from tiaojiechi import TiaojiechiNode  # 从 mods/core/tiaojiechi/__init__.py
```

### 🧪 迁移后验证命令

```bash
# 1. 模组加载测试 — 全部 34 模组必须加载成功 (0 errors)
python -c "
from mods.mod_manager import get_mod_manager
mgr = get_mod_manager(); mgr.load_all()
print(mgr.get_load_summary())
assert len(mgr.get_load_errors()) == 0
"

# 2. 全量单元测试
pytest tests/ -q

# 3. 全 DAG 端到端测试
python test_full_dag.py

# 4. 逐个模组计算验证（至少新修改的模组）
python -c "
from mods.mod_manager import get_mod_manager
from models.base import WaterFlow, WaterQuality
mgr = get_mod_manager(); mgr.load_all()
flow = WaterFlow(); quality = WaterQuality()
for mid in ['jishuijing','peishuijing','jipeishuijing','peishuiqu','gdys_stss','jcws_smbg']:
    cls = mgr.load_mod(mid)
    node = cls()
    r, _, _ = node.execute(flow, quality)
    assert r.success, f'{mid} failed: {r.error_msg}'
    print(f'{mid}: OK ({len(r.dimensions)} dims)')
print('ALL 6 MODS PASSED')
"
```

### 🛡️ 约束持久化规则

约束面板的用户修改通过 `_persist_config()` 写入 `discretization.json`。修改约束后：

1. **运行时立即生效** — 内存中的 config 已更新
2. **重启后自动加载** — JSON 文件在下次启动时被 `load_mod_discretizations()` 读取并覆盖硬编码配置
3. **双目录自动同步** — `_persist_config()` 同时写入 `mods/core/` 和 `ddesign_tool/mods/core/`
4. **原子写入** — 先写 `.tmp_xxx.json` 临时文件，`os.replace()` 重命名，防止写入中断导致 JSON 损坏

---

> **版本**: v4.2 | **维护者**: Graduation Design Team
