# 2026-05-24 (会话4-最终) 学习记录 — v4.3 参数完整性全线审计 + 全局表污染修复

> **日期**: 2026-05-24 | **测试**: 327 passed | **修改文件**: 60+

---

## 一、双重数据源根因分析

### 问题链

```
代码 _default_params() → 22 个参数 (全部)
代码 _build_param_defs() → 6 个参数 (仅 UI 滑块)
mod.json → 手工编写，只放了"重要"的 6 个
       ↓
审计脚本用 _build_param_defs 作为权威源 → 误判"已完整"
       ↓
Excel 输出时 resolve_dimension() 查键 → 16 个参数查不到 → 符号/名称/单位全空
```

### 修复

| 步骤 | 内容 |
|------|------|
| 1. 切换权威源 | `_build_param_defs()` → `_default_params()` |
| 2. 发现缺口 | 12 模组缺 97 项参数 (vxinglvchi 最严重: 缺 16) |
| 3. 批量补全 | 从 `_default_params()` + `_build_param_defs()` 生成完整 mod.json |
| 4. 值对齐 | default×15 + name×69 + unit×3 + min×19 + max×18 + step×12 |

---

## 二、全局 param_table 污染问题 🔥

### 根因

`_build_dynamic_labels()` 的 param_table 是**全局单例**，所有 31 模组共享：

```python
for mod_id, mod_info in mgr.mods.items():   # 字母序迭代
    for p in mod_info.parameters:
        if p.key not in param_table:        # ← 首模组获胜!
            param_table[p.key] = (p.symbol, p.name, p.unit)
```

**aao (字母序第一)** 污染了所有共享键：
- `X_MLSS`: aao unit=g/L → cass 本应 mg/L → 显示错误
- `h_super`: aao sym=超高(中文名) → cass 本应 sym=h_free → 显示错误  
- `HRT`: jipeishuijing unit=min → tiaojiechi 本应 h → 显示错误

### 另外两个 Bug

| Bug | 位置 | 影响 |
|-----|------|------|
| **labels.json 有 vec_fields 但无 params → 跳过自动生成** | `_build_dynamic_labels` | 11 个有 labels.json 的模组参数完全丢失 |
| **符号=中文名** | 批量补参脚本用 `name` 作 `symbol` | "混合时间"出现在符号列 |

### 三层修复

| 层 | 修复 |
|----|------|
| `_build_dynamic_labels` | 去 `else` → 始终运行自动生成，无论 labels.json 是否存在 |
| mod.json 符号 | 153 处中文名符号 → 还原为键名 |
| `format_dimension_row` | 新增 `node_type` 参数 → **优先查所属模组的 mod.json**，绕过全局表 |

```python
# 修复后: 参数显示不再依赖全局表, 直接从节点所属模组读取
def format_dimension_row(name, value, unit="", node_type=""):
    if node_type:
        mod_info = mgr.get_mod_by_node_type(node_type)
        for p in mod_info.parameters:
            if p.key == name:
                return (p.key, p.name, p.unit or unit)
    # fallback to global table
```

---

## 三、关键架构洞察 (新增)

| 洞察 | 详情 |
|------|------|
| **_default_params ≠ _build_param_defs** | `_default_params` 是完整参数集(22项)，`_build_param_defs` 仅 UI 可见参数(6项)。审计必须用前者 |
| **全局表 + 共享键 = 必然污染** | 31 模组共享一个 dict，首字母序决定一切。aao 的 X_MLSS=g/L 污染了 cass |
| **labels.json 副作用** | 有 vec_fields 但无 params 时，else 分支不执行 → 自动生成被跳过 → 参数丢失 |
| **node_type 感知是关键** | `format_dimension_row` 加 node_type 参数 → 每节点用自己的 mod.json → 消灭共享键冲突 |
| **AI 批量操作需审计** | 批量补参脚本"聪明地"用中文名作符号 → 152 处需回滚 |

---

## 四、改动文件汇总

| 文件 | 改动 | 类型 |
|------|------|------|
| `dimension_labels.py` | `_build_dynamic_labels`: 去 else, 始终自动生成 | Bug 修复 |
| `dimension_labels.py` | `format_dimension_row`: +node_type 参数 | 架构修复 |
| `output_writer.py` | 调用传 `be.NODE_TYPE` | 修复 |
| `main_window.py` | 调用传 `be.NODE_TYPE` | 修复 |
| `solution_browser.py` | 调用传 `self._node_type` | 修复 |
| 12× `mod.json` | 补全 97 项缺失参数 | 修复 |
| 15× `mod.json` | default/name/unit/min/max/step 对齐 (122 项) | 修复 |
| 31× `mod.json` | 153 处中文名符号 → 键名 | 修复 |

---

> **记录者**: Sisyphus | **版本**: v4.3 final | **测试**: 327 passed | **修改文件**: 60+
