# 🔧 排水工程设计工具 — 模组编写规范 v5.4

> **类比**: Minecraft Forge/Fabric 模组开发。一个文件夹 = 一个模组，零框架修改。
> **原则**: 每个模组完全自包含。**不需要修改任何集中式 Python 文件**。
> **受众**: AI 编程助手、模组开发者、毕业设计维护者。

---

## 快速参考

| 你要做什么 | 需要创建/修改的文件 |
|-----------|-------------------|
| 新建一个处理单元 | `mod.json` + `__init__.py` + `discretization.json` + `labels.json` (4 文件) |
| 修改计算逻辑 | `__init__.py` (`_vectorized_compute` — 唯一计算源) |
| 修改可调参数 | `__init__.py` (_default_params + _build_param_defs) + `mod.json` (parameters) |
| 修改约束条件 | `discretization.json` (constraint_keys/names/limits) + `__init__.py` (ok_*/val_*) |
| 修改维度显示标签 | `labels.json` (dimensions + vec_fields) |
| 修改作用域前缀 | `labels.json` (dim_scopes) |
| 修改水头损失 | `mod.json` (elevation_loss) |

**v5.4 核心变更**:
- **calculate() 无需编写** — 自动委托 `_vectorized_compute(N=1)`, 只需实现 `_vectorized_compute`
- **mods/ 单目录** — 开发与运行时共用 `mods/`, 不再需要双目录同步
- **numpy 类型防护** — `add_check`/`add_dimension` 自动转换 numpy 类型为 Python 原生类型
- **安全除法** — `_vectorized_compute` 中所有除法须使用 `np.divide(..., where=cond)` 或 `np.maximum(denom, 1e-10)` 保护零分母
- **向后兼容别名** — `ModManager.COMPAT_NODE_TYPES` 支持 node_type 重命名后旧项目文件自动解析
- `import math` 可省略 — 向量化计算统一使用 `numpy`

---

## 1. 模组文件结构

```
mods/core/{mod_id}/               # 或 mods/community/{mod_id}/
├── mod.json                      # [必需] 元数据 + 参数 + 端口 + 水头损失
├── __init__.py                   # [必需] NodeBase 子类
├── discretization.json           # [必需] 自由/固定参数 + 约束定义
└── labels.json                   # [必需] 维度标签 + 向量化标签 + 作用域
```

---

## 2. __init__.py — NodeBase 子类实现 [v5.4 更新]

### 2.1 核心原则: calculate() 自动委托

v5.4 起, **无需手动编写 `calculate()`**。基类 `NodeBase.calculate()` 自动:

1. 从 `_params` 读取参数
2. 构建 1 元素 grid + fixed 字典
3. 调用 `self._vectorized_compute(grid, flow, quality, fixed)`
4. 将结果转换为 `NodeResult`

**你只需要实现 `_vectorized_compute()` — 这是唯一的计算源。**

### 2.2 类结构模板

```python
"""模块说明 — 公式来源: [规范引用]"""
import numpy as np
from typing import Dict, List
from models.base import (
    NodeBase, NodeResult, WaterFlow, WaterQuality,
    ParamDef,
)

class MyModuleNode(NodeBase):
    NODE_TYPE = "my_module"       # 与 mod.json node_type 一致
    NODE_NAME = "模块中文名"       # UI 显示
    NODE_CATEGORY = "一级处理"     # 与 mod.json category 一致

    # ── 1. 默认参数 ──
    @classmethod
    def _default_params(cls) -> Dict[str, float]:
        return {"n": 2, "HRT": 6.0, "h_eff": 4.0, "h_super": 0.5}

    # ── 2. UI 参数定义 ──
    def _build_param_defs(self) -> List[ParamDef]:
        return [
            ParamDef("池数", "n", value=2, default=2,
                     min_val=2, max_val=8, step=1, unit="座"),
            ParamDef("停留时间", "HRT", value=6, default=6,
                     min_val=4, max_val=12, step=0.5, unit="h"),
        ]

    # ── 3. 去除率 ──
    @classmethod
    def _default_removal_rates(cls) -> Dict[str, float]:
        return {"SS": 0.0, "BOD5": 0.0, "COD": 0.0}

    # ── 4. 向量化计算 (唯一计算源) ──
    @classmethod
    def _vectorized_compute(cls, grid, flow, quality, fixed) -> np.ndarray:
        """向量化批量计算 (N 个参数组合)

        grid 键来自 discretization.json["free"]
        fixed 键来自 discretization.json["fixed"]

        Returns: numpy 结构化数组, dtype 必须包含:
          - L, B, H (或 D), concrete_m3 — 标准字段 (缺则成本为 0)
          - ok_<key> (bool) + val_<key> (float64) — 每个约束键
          - 所有需要显示的尺寸值 (float64)
        """
        n = grid["n"].astype(np.int32)
        HRT = grid["HRT"]
        h_eff = grid.get("h_eff", np.full(len(n), fixed.get("h_eff", 4.0)))
        h_super = fixed.get("h_super", 0.5)
        N = len(n)

        Q_avg_h = flow.Q_avg_hourly
        V_eff = Q_avg_h * HRT / n
        B = np.ceil(np.sqrt(V_eff / h_eff / 1.5) / 0.5) * 0.5
        L = np.ceil(V_eff / B / h_eff / 0.5) * 0.5
        V_actual = L * B * h_eff
        HRT_actual = V_actual / (Q_avg_h / n)
        H_total = h_eff + h_super

        ok_HRT = (4.0 <= HRT_actual) & (HRT_actual <= 12.0)

        dtype = np.dtype([
            ("L", np.float64), ("B", np.float64), ("V_eff", np.float64),
            ("V_actual", np.float64), ("HRT_actual", np.float64),
            ("H_total", np.float64), ("H", np.float64),
            ("concrete_m3", np.float64),
            ("ok_HRT", np.bool_), ("val_HRT", np.float64),
        ])
        result = np.empty(N, dtype=dtype)
        result["L"] = L; result["B"] = B
        result["V_eff"] = V_eff; result["V_actual"] = V_actual
        result["HRT_actual"] = HRT_actual
        result["H_total"] = H_total; result["H"] = result["H_total"]
        result["concrete_m3"] = V_actual * 1.2
        result["ok_HRT"] = ok_HRT; result["val_HRT"] = HRT_actual
        return result
```

### 2.3 为什么不需要 calculate()?

v5.4 的 `NodeBase.calculate()` 自动完成转换:

```python
# 基类自动执行 (你不需要写):
def calculate(self, flow, quality):
    # 读取参数
    n = int(self.get_param("n"))
    HRT = self.get_param("HRT")
    ...
    # 构建 N=1 grid
    grid = {"n": np.array([n]), "HRT": np.array([HRT]), ...}
    fixed = {"h_super": h_super, ...}
    # 调用你的向量化计算
    res = self._vectorized_compute(grid, flow, quality, fixed)
    r = res[0]
    # 组装 NodeResult
    result = NodeResult(success=True)
    result.add_dimension("池数", n, "座")
    result.add_dimension("有效容积", round(float(r["V_actual"]), 1), "m³")
    result.add_check("HRT >= 4h", bool(r["ok_HRT"]), ...)
    return result
```

> **例外**: 如果模组需要特殊的标量逻辑 (如 input guard、warning), 可 override `calculate()` 并显式调用 `_vectorized_compute(N=1)`。

### 2.4 必须遵守的规则

| 规则 | 说明 |
|------|------|
| **`_vectorized_compute` 是唯一计算源** | 不重复实现标量计算的数学逻辑 |
| **向量化须含标准字段** | `L`, `B`, `H`(或`D`), `concrete_m3` — 缺则成本为零 |
| **向量化约束字段** | 每个 constraint_key 须有 `ok_<key>`(bool) + `val_<key>`(float64) |
| **numpy 类型自动转换** | `add_check`/`add_dimension` 自动将 numpy 类型转为 Python 类型 (v5.4) |
| **`result.params` 包含全部参数** | `{k: self.get_param(k) for k in self._default_params()}` |
| **维度名不含前缀** | 用 `scope=` 声明作用域，不要 `"[单池]有效容积"` |

---

## 3. mod.json — 完整规范

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `id` | string | ✅ | 小写英文+下划线 |
| `name` | string | ✅ | 中文显示名 |
| `version` | string | ✅ | 语义化版本 |
| `node_type` | string | ✅ | 与 NODE_TYPE 一致 |
| `node_class` | string | ✅ | Python 类名 |
| `process_stage` | string | ✅ | 处理阶段 (见下表) |
| `parameters` | array | ✅ | 参数列表 |
| `elevation_loss` | object | ✅ | 水头损失 `{"value": 0.30, "formula": "..."}` |
| `removal_rates` | object | ✅ | 污染物去除率 |
| `inputs` / `outputs` | array | ✅ | 端口定义 |

### process_stage 枚举

| 标识符 | 含义 | 方案浏览器 |
|--------|------|:--:|
| `io` | 输入/输出 | 跳过 |
| `primary` | 一级处理 | ✅ |
| `secondary` | 二级处理 | ✅ |
| `tertiary` | 深度处理 | ✅ |
| `sludge` | 污泥处理 | ✅ |
| `mine_water` | 矿井水 | ✅ |
| `collection` | 集配水 | — |
| `elevation` | 高程 | 跳过 |

---

## 4. discretization.json — 方案空间配置

```json
{
  "free": {"n": [2, 3, 4], "HRT": [6.0, 8.0, 10.0]},
  "fixed": {"h_super": 0.5},
  "constraint_keys": ["LB_ratio", "HRT_actual"],
  "constraint_names": ["长宽比 L/B", "实际 HRT"],
  "constraint_limits": {"长宽比 L/B": "2~4", "实际 HRT": "6~12"},
  "constraint_types": {"长宽比 L/B": "result", "实际 HRT": "result"}
}
```

**关键**: `constraint_keys` 后缀 = `_vectorized_compute` 的 `ok_<suffix>` / `val_<suffix>` 后缀。

---

## 5. labels.json — 维度标签

```json
{
  "dimensions": {
    "池数": ["n", "池数"],
    "有效容积": ["V_eff", "有效容积"]
  },
  "vec_fields": {
    "V_eff": ["V_eff", "有效容积", "m³"]
  },
  "dim_scopes": {
    "有效容积": "single"
  }
}
```

---

## 6. 注册清单 (创建新模组)

- [ ] **Step 1**: 创建文件夹 `mods/core/{mod_id}/`
- [ ] **Step 2**: 编写 `mod.json` — 所有字段完整
- [ ] **Step 3**: 编写 `__init__.py`
  - [ ] `_default_params()` 包含所有参数
  - [ ] `_build_param_defs()` 仅 UI 可见参数
  - [ ] `_vectorized_compute()`: dtype 含 L/B/H/concrete_m3 + ok_*/val_*
  - [ ] ~~`calculate()`~~ **不需要** (基类自动处理)
- [ ] **Step 4**: 编写 `labels.json` — dimensions + vec_fields + dim_scopes
- [ ] **Step 5**: 编写 `discretization.json` — 六项齐全
- [ ] **Step 6**: 运行 `pytest tests/` — 无回归
- [ ] **Step 7**: 重启应用验证

---

## 7. 常见陷阱

| 陷阱 | 预防 |
|------|------|
| 维度标签显示裸英文 | `labels.json["dimensions"]` 缺该维度条目 |
| 方案浏览器崩溃 | `_vectorized_compute` dtype 字段名与赋值变量不匹配 |
| Excel "无法提取尺寸" | 向量化 dtype 缺 L/B/H/D 标准字段 |
| 缺 concrete_m3 | 工程概算成本为 0 |
| 缺 val_\<key\> | 安全裕度恒为 0 |
| **旧写法**: 同时实现 calculate + _vectorized_compute | **v5.4 新写法**: 只实现 _vectorized_compute |
| **np.where 除零警告** | 用 `np.divide(a,b,where=b>0)` 或 `np.maximum(b,1e-10)` 保护 |
| **mod.json unit 错误** | 含水率/去除率用 `"-"`, 功率用 `"kW"`, 长度用 `"m"` — 注意复制模板时改 unit |
| **node_type 重命名后旧项目报错** | 在 `ModManager.COMPAT_NODE_TYPES` 添加 `{"旧名": "新名"}` 映射 |

### 7.1 安全除法规范 (v5.4-s5)

所有 `_vectorized_compute` 中的除法必须保护零分母:

```python
# ❌ 错误: np.where 仍会计算除法产生 RuntimeWarning
result = np.where(denom > 0, num / denom, 0.0)

# ✅ 方案 A: np.divide with where
result = np.divide(num, denom, where=denom > 0,
                   out=np.zeros_like(num))

# ✅ 方案 B: 安全分母 (标量+数组混合时推荐)
safe_denom = np.maximum(denom, 1e-10)
result = np.where(denom > 0, num / safe_denom, 0.0)
```

**CI 强制**: `tests/conftest.py` 的 autouse fixture 会将任何除零 RuntimeWarning 转为测试失败。

### 7.2 向后兼容别名 (v5.4-s5)

当 node_type 需要重命名时, 在 `ModManager.COMPAT_NODE_TYPES` 中添加映射:

```python
# mods/mod_manager.py (ModManager 类)
COMPAT_NODE_TYPES: Dict[str, str] = {
    "old_name": "new_name",
}
```

`get_node_class()` 和 `graph_executor.default_node_factory()` 都会自动解析别名，旧项目文件无需手动迁移。`get_node_class()` 和 `graph_executor.default_node_factory()` 都会自动解析别名，旧项目文件无需手动迁移。

---

## 8. 架构演进

| 版本 | 里程碑 |
|------|--------|
| v3.2 | MC式模组架构: 一个文件夹=一个模组 |
| v5.0 | labels.json 主要标签源, dim_scopes 作用域 |
| v5.1 | ceil_to 废弃, 公式下沉, 数据源统一, 97% 测试覆盖 |
| v5.3 | ModManager 拆分, 物理不变性测试, pre-commit |
| **v5.4** | **calculate() 自动委托, 单一计算源, 架构评分 8.1/10** |
| **v5.4-s5** | **工业级防御: RuntimeWarning→Error, CI全量, 安全除法规范, 向后兼容别名** |

---

> **版本**: v5.4-s5 | **最后更新**: 2026-05-28 | **维护者**: yyx
