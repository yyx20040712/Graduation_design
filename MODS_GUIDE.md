# 🎮 排水工程设计工具 — 模组创作指南 v5.4

> **You are an AI agent. This guide is written for YOU.**
> Follow it exactly. Do not improvise on structure.
> **版本**: v5.4 | **更新**: 2026-05-28 | **架构**: MC式即放即用 + ModManager 委托模式

---

## What You're Building

A **water treatment process module** (mod) for a drainage engineering design tool.
Each mod = one treatment unit. The tool uses a **DAG executor** with typed ports.

---

## Quick Reference

| 你要做什么 | 创建/修改的文件 |
|-----------|---------------|
| 新建处理单元 | `mod.json` + `__init__.py` + `discretization.json` + `labels.json` (4 files) |
| 修改计算逻辑 | `__init__.py` (calculate + _vectorized_compute) |
| 修改可调参数 | `__init__.py` (_default_params + _build_param_defs) + `mod.json` (parameters) |
| 修改约束条件 | `discretization.json` (constraint_keys/names/limits) + `__init__.py` (add_check + ok_*/val_*) |
| 修改维度标签 | `labels.json` (dimensions + vec_fields + dim_scopes) |
| 修改水头损失 | `mod.json` (elevation_loss) |
| 添加维度公式 | `labels.json` (formulas) — 无需修改全局 dimension_formulas.py |

---

## Mod File Structure

```
mods/core/{mod_id}/             (or mods/community/{mod_id}/)
├── mod.json                    [REQUIRED] Metadata + params + ports + elevation_loss
├── __init__.py                 [REQUIRED] NodeBase subclass
├── discretization.json         [REQUIRED] Free/fixed params + constraints
└── labels.json                 [REQUIRED] Dimension labels + vec_fields + scopes + formulas
```

**Everything auto-discovered**: No global registry changes needed. ModManager discovers, validates, and registers automatically.

---

## mod.json — Required Fields

| 字段 | 类型 | 必需 | 说明 |
|------|------|:--:|------|
| `id` | string | ✅ | 小写英文+下划线, e.g. `"tiaojiechi"` |
| `name` | string | ✅ | 中文显示名 |
| `version` | string | ✅ | 语义化版本 |
| `author` | string | ✅ | 作者 |
| `description` | string | ✅ | 一句话功能 |
| `category` | string | ✅ | UI 菜单分组 |
| `process_stage` | string | ✅ | io/primary/secondary/tertiary/sludge/mine_water/collection/elevation |
| `node_type` | string | ✅ | 节点类型标识 (同 id) |
| `node_class` | string | ✅ | Python 类名 |
| `module_path` | string | ✅ | 空字符串 (MC式自包含) |
| `inputs` | array | ✅ | 端口列表 |
| `outputs` | array | ✅ | 端口列表 |
| `parameters` | array | ✅ | 参数列表 |
| `removal_rates` | object | ✅ | 污染物去除率 |
| `formula` | string | ✅ | 核心公式 |
| `elevation_loss` | object | ✅ | 水头损失 |

---

## Port Types

| 类型 | 含义 | 连通规则 |
|------|------|---------|
| `WATER` | 水量 (WaterFlow) | 可连 WATER/MIXED |
| `QUALITY` | 水质 (WaterQuality) | 可连 QUALITY/MIXED |
| `MIXED` | 水量+水质 | 万能端口 |
| `SLUDGE` | 污泥流 (SludgeFlow) | 仅连 SLUDGE, 允许多股合并 |

---

## __init__.py Template

```python
"""mod_id.py — Module description"""
from __future__ import annotations
import math
import numpy as np
from typing import Dict, List, Tuple
from models.base import NodeBase, NodeResult, WaterFlow, WaterQuality, ParamDef

class MyNode(NodeBase):
    NODE_TYPE = "my_mod"
    NODE_NAME = "我的模组"
    NODE_CATEGORY = "一级处理"

    @classmethod
    def _default_params(cls) -> Dict[str, float]:
        return {"param1": 1.0, "param2": 2.0}

    def _build_param_defs(self) -> List[ParamDef]:
        return [
            ParamDef("参数1", "param1", value=1.0, default=1.0,
                     min_val=0.5, max_val=3.0, step=0.1, unit="m"),
        ]

    @classmethod
    def _default_removal_rates(cls) -> Dict[str, float]:
        return {"BOD5": 0.3, "COD": 0.3, "SS": 0.5}

    def calculate(self, flow: WaterFlow, quality: WaterQuality) -> NodeResult:
        result = NodeResult(success=True)
        # ... calculation logic ...
        result.add_dimension("长度", L, "m", formula="L = sqrt(A × ratio_LB)")
        result.add_check("长宽比", 2 <= ratio <= 5, ratio, "2~5", "-")
        return result

    @classmethod
    def _vectorized_compute(cls, grid, flow, quality, fixed):
        """Vectorized computation for solution space enumeration"""
        # ... numpy-based batch calculation ...
        return structured_array
```

---

## Coding Standards (v5.4)

- **NO semicolons** — each statement on its own line (E702 enforced by pre-commit)
- **NO unused imports** (F401 enforced)
- **Use `math.ceil(value/step)*step`** — `ceil_to()` is deprecated since v5.1
- **Formulas go in `labels.json["formulas"]`** — not in global dimension_formulas.py
- **Constraints use `add_check(name, passed, actual, limit, unit)`**
- **Vectorized output MUST include**: `ok_{constraint}`, `val_{constraint}`, `concrete_m3`

---

## Version

| 版本 | 变更 |
|------|------|
| v5.4 | ModManager拆分为4模块, 委托模式, 零导入变更 |
| v5.3 | labels.json自带公式, 向量化输出验证 |
| v5.0 | 作用域系统, 标签自包含 |

---

> **维护者**: yyx | **版本**: v5.4 | **更新**: 2026-05-28
