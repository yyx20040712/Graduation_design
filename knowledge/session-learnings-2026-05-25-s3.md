# 2026-05-25 Session 3 — v4.5 参数合规审计 + 公式全覆盖 + 反漏标签机制

> **日期**: 2026-05-25 | **会话**: Sisyphus 全参数合规 + 公式审计

---

## 一、全参数合规审计与修复

### 1.1 审计维度
编写全自动审计脚本 `_param_audit.py`，检查 34 模组的：
- `_default_params()` ↔ `mod.json parameters` 一致性
- `_build_param_defs()` 的 `ParamDef.unit` 是否为空
- `mod.json` 中 `name == key`（缺少中文名称）
- `calculate()` 的 `result.params` 是否包含全部 `_default_params` 键
- `discretization.json` 的 `free + fixed` 是否覆盖全部参数

### 1.2 初始审计结果：47 项不合规

| 类别 | 数量 | 说明 |
|------|------|------|
| PARAMDEF_EMPTY_UNIT | 18 个 | 无量纲参数单位为空，MOD_SPEC 要求填 `"-"` |
| NAME_EQ_KEY | 4 个 | mod.json 中 name 等于 key，缺少中文名 |
| RESULT_PARAMS_GAP | 7 模组 | result.params 遗漏 _default_params 中的键 |
| DISCRETIZATION_GAP | 4 模组 | discretization.json 未覆盖全部参数 |

### 1.3 修复清单

**PARAMDEF_EMPTY_UNIT** → 全部改为 `unit="-"`:
- chuchenchi: i_slope, P_sludge
- cugeshan/xigeshan: bar_shape (共享基类 `_BarScreenBase`)
- kw_chenshachi: slope, P_sand
- kw_tiaojiechi: k, ratio_LB, slope, P_sludge
- kw_input: Kz, pH
- wuni_ganhua: method, P_out, eta_thermal
- wuni_tuoshui: equip_type, P_out
- wuni_nongsuo: P_out

**NAME_EQ_KEY** → 修改 mod.json:
- aao: `y` → "产率系数"
- cass: `SVI` → "污泥容积指数"
- kw_input: `TDS` → "溶解性总固体", `pH` → "酸碱度"

**RESULT_PARAMS_GAP**:
- gaomidu: result.params 新增 `P_out`
- wuni_nongsuo: result.params 新增 `h_eff`

**DISCRETIZATION_GAP**:
- gaomidu: fixed 新增 `P_out`
- wuni_bengzhan/shusong: fixed 新增 `L_pipe`

### 1.4 修复后审计：22→1 (仅 kw_input 属预期 IO 节点)

---

## 二、反漏标签三层防线

### 2.1 根因分析

**为什么反复漏标签？**

`resolve_dimension()` 的兜底逻辑静默返回低质量结果：
```python
symbol = clean_name[:12]   # 截断名作符号
meaning = clean_name       # 裸键名作物理意义
unit = ""                  # 单位永远为空
```
无任何告警，每次新增变量都悄然通过。

### 2.2 三层防线

| 层级 | 机制 | 触发时机 |
|------|------|---------|
| **运行时告警** | `_warn_fallback()` — 兜底路径打 WARNING（每 key 仅一次） | `resolve_dimension()` 未命中 |
| **加载时校验** | `mod_manager.load_all()` 调用 `validate_dimension_labels()` | 程序启动 |
| **CI 测试** | `test_dimension_labels.py` 2 tests | `pytest` |

### 2.3 新增函数

`dimension_labels.py`:
- `_warn_fallback(key)` — 记录兜底告警
- `reset_fallback_warnings()` — 清除告警记录
- `get_fallback_warnings()` — 获取告警列表
- `validate_dimension_labels()` — 遍历 34 模组 280 向量化字段验证标签完整性

### 2.4 验证

```
test_all_vectorized_fields_have_labels      PASSED (280字段, 0缺失)
test_no_fallback_warnings_during_startup     PASSED
```

---

## 三、公式全覆盖

### 3.1 审计

遍历所有模组 `calculate()` / `execute_sludge()` 产生的维度，检查是否有公式（显式 `formula=` 或 `DIM_FORMULAS` 回退）。

**初始结果: 83 个维度无公式**，显示"详见设计规范及计算书"。

### 3.2 修复

新增 ~100 条 DIM_FORMULAS 条目，按类别组织：

| 类别 | 条目数 | 示例 |
|------|--------|------|
| AAO | 7 | 内回流比, 内回流量, 污泥龄, 总HRT |
| CASS | 8 | 剩余污泥, 滗水流量, 反硝化产氧, 安全距离 |
| 初沉池/二沉池 | 9 | 刮泥机线速, 每日干/湿污泥, 池底坡降, 回流比 |
| 格栅 | 4 | (s/b)^(4/3), 单台流量, 格栅台数 |
| 管道/高程 | 4 | 充满度, 管段长度, 设计坡度, 管底标高 |
| 矿井水通用 | 5 | 混凝土量估算, 砂斗总数, 磁盘间距 |
| 混凝反应池 | 5 | 混合区/絮凝区/熟化区/磁种混合区长度 |
| 滤池 | 4 | 单格宽度, 单格长度, 滤头数量, 渠道数 |
| 泵站/输送 | 5 | 单泵功率, 扬程, 电机功率, 进泥干固量 |
| 干化/脱水/消化 | 7 | 减量率, 总热耗, 折合标煤, 甲烷产量 |
| 巴氏计量槽 | 2 | 上游水深, 下游水深 |
| 紫外 | 3 | 实际剂量, 设计剂量, 接触时间 |
| 调节池 | 3 | 设计HRT, 单池设计流量, 搅拌总功率 |
| 其他 | 30+ | 覆盖剩余所有维度名 |

### 3.3 验证

```
修复前: 83 个维度无公式
修复后: 0 个维度无公式
```

---

## 四、修改文件清单

| 文件 | 变更 |
|------|------|
| `dimension_labels.py` | +4 函数 (fallback warn/validate), +51 VEC_FIELD_TABLE |
| `dimension_formulas.py` | +100 DIM_FORMULAS, 英文分类模式匹配 |
| `mod_manager.py` | `load_all()` 集成标签校验 |
| `tests/test_dimension_labels.py` | 新增 2 tests |
| `chuchenchi/__init__.py` | i_slope/P_sludge unit="-" |
| `cugeshan/__init__.py` | bar_shape unit="-" |
| `xigeshan/__init__.py` | bar_shape unit="-" |
| `kw_chenshachi/__init__.py` + `discretization.json` | unit fixes |
| `kw_tiaojiechi/__init__.py` | 4 params unit="-" |
| `kw_input/__init__.py` + `mod.json` | Kz/pH unit + name fix |
| `wuni_ganhua/__init__.py` | 3 params unit="-" |
| `wuni_tuoshui/__init__.py` | 2 params unit="-" |
| `wuni_nongsuo/__init__.py` | P_out unit + h_eff in result.params |
| `gaomidu/__init__.py` + `discretization.json` | P_out in params+discretization |
| `wuni_bengzhan/discretization.json` | L_pipe in fixed |
| `wuni_shusong/discretization.json` | L_pipe in fixed |
| `aao/mod.json` | y → 产率系数 |
| `cass/mod.json` | SVI → 污泥容积指数 |

---

## 🔴 铁律汇总 (v4.5 最终版)

1. **流量一致性**: 所有路径获取流量必须用 WaterFlow 对象
2. **auto-apply = 手动点击**: `_apply_current()` → `_apply_callback()` 全链
3. **add_dimension ↔ dtype**: 每加输出维度必须同步向量化 dtype
4. **F5 后 force_recompute**: 方案浏览器必须强制重算
5. **两项同步**: `mods/` ↔ `ddesign_tool/mods/` 必须一致
6. **Kz 陷阱**: Q_avg = Q_design × 86400 / Kz
7. **[v4.5] 过滤单一源**: Excel/UI/概算报告共用 `split_dimensions()`
8. **[v4.5] labels.json 必需**: 新模组 4 文件最小集
9. **[v4.5] 英文字段名规范**: 向量化 dtype 遵循 §5.3 模式
10. **[v4.5] 参数无空单位**: 无量纲填 `"-"`, 绝不空字符串
11. **[v4.5] result.params 完整**: 必须包含 `_default_params` 全部键
12. **[v4.5] 每个维度有公式**: 显式传 `formula=` 或确保 DIM_FORMULAS 有对应条目
13. **[v4.5] CI 兜底测试**: `test_dimension_labels.py` 自动发现标签缺失

---

> **Sisyphus** | 2026-05-25 Session 3 | v4.5 参数合规 + 公式全覆盖
