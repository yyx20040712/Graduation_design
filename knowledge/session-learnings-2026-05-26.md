# 2026-05-26 — v5.0 架构升级: 作用域分离 + 标签治理 + MC 自包含完成

> **日期**: 2026-05-26 | **会话**: Sisyphus — 维度标签系统重构 + 模组自包含闭环
> **修改文件**: 50+ | **测试**: 329 passed

---

## 一、作用域系统 (Scope System)

### 问题
维度名嵌入前缀如 `"[单池]有效容积"` → 名字被污染 → 所有消费者（标签查找、公式查找、Excel 输出）都需要知道如何剥离前缀 → 散弹式补丁蔓延。

### 方案: 元数据分离 (Plan A)
```
之前: add_dimension("[单池]有效容积", ...)
之后: add_dimension("有效容积", ..., scope="single")
      labels.json: {"dim_scopes": {"有效容积": "single"}}
      UI 渲染: [单池]有效容积 (运行时组合)
```

### 实现
- **`base.py`**: NodeResult 新增 `dimension_scopes: Dict[str, str]` + `SCOPE_PREFIX: ClassVar` + `get_display_name()` + `add_dimension(scope=)` 参数
- **27× labels.json**: 新增 `dim_scopes` 条目
- **14× __init__.py**: 剥离嵌入前缀，改为干净的维度名
- **`main_window.py`**: `_get_scope_prefix()` 读取 labels.json → 渲染前缀

### 作用域键映射
| 键 | 前缀 | 场景 |
|----|------|------|
| `single` | `[单池]` | 每池独立值 |
| `total` | `[总]` | 全部合计 |
| `per_unit` | `[单格]` | 每格独立 |
| `per_series` | `[单系列]` | 每系列独立 |
| `sump` | `[集水池]` | 集水池 |

---

## 二、标签系统治理

### 问题链
1. DIMENSION_TABLE 是 400+ 行硬编码全局字典 → 新模组标签必须改此文件
2. VEC_FIELD_TABLE 覆盖不全 → vec_fields 大量缺失 → 运行时 WARNING 泛滥
3. 标签查找用精确匹配 → 前缀嵌入破坏匹配 → 补丁越打越多

### 修复
- **412 条目从 DIMENSION_TABLE 迁移到 27 个模组的 `labels.json["dimensions"]`**
- **vxinglvchi labels.json 补全 18 条 vec_fields**（D_g, Q_blower, A_v_slot 等）
- **DIMENSION_TABLE 补全 43 条**（泵站/脱水/干化/通用维度）
- **验证: 327 checked, 0 missing**

### 架构效果
```
之前: 新模组标签 → 必须改 dimension_labels.py (集中式)
之后: 新模组标签 → 只改自己的 labels.json (自包含)
```

---

## 三、连锁 Bug 修复

| Bug | 根因 | 修复 |
|-----|------|------|
| V型滤池 0 可行方案 | `_vectorized_compute` 缺 `Q_g2_val = q_g2 * A_actual` → NameError | 补全赋值 |
| CASS 污泥龄审核不当 | 旧公式 `V·X/Px_total` 混合非生物污泥 → 错误通过 | 替换为 (4-79) `V·X·f/ΔXv`, 加上界 30d |
| kw_chenshachi 砂斗容积=0 | hopper_bottom=0.6 = 单格宽 B=0.6 → h_hopper=0 | hopper_bottom 0.6→0.4 |
| 启动诊断轰炸 | `_auto_apply_recommended` 对每个加载节点调用 → 100+ 行诊断 | `_loading_project` 守卫 + `_diagnosed` 去重 |
| `_get_scope_prefix` TypeError | `@staticmethod` 与 `self` 参数冲突 | 去除装饰器 |
| `_dim_formula` 参数错位 | 缺少 `self` 参数 → dim_name 被赋值为 MainWindow 实例 | 补加 `self` |
| kw_chenshachi mod.json 损毁 | PowerShell 正则替换匹配范围过大 | 修复 hopper_bottom 条目 |

---

## 四、CASS 约束校核 — 公式 (4-79)

### 替换
```
旧 (3-70): θc = V_main × X_kg / Px_total     → 默认 ~64d, 通过
新 (4-79): θc' = V_main × X_kg × f / Px_bio  → 默认 ~87d, 失败(>30d)

新增: 硝化污泥龄校核 15 ≤ θc' ≤ 30
```

### 参数调整
- Ns: 0.08 → 0.12 (GB50014-2021 §7.6, 参考实际工程 0.11~0.15)
- H_max: 5.0 → 6.0m (GB50014-2021 §7.6.41 建议 4.0~6.0m)
- 效果: L 181→84m, θc' 87.2→28.2d (PASS)

---

## 五、全模组 QA 审计

### 测试条件: Q=0.57 m³/s, Kz=1.4, BOD5=200

| 指标 | 修复前 | 修复后 |
|------|--------|--------|
| 歧义维度 | 15 模组 | 4 模组 |
| 离谱数值 | 3 模组 (5 alerts) | 0 |
| 公式缺失 | 7 维度 | 5 维度 (均为设计意图) |
| 标签缺失 | 大量 WARNING | 0 |

---

## 六、参数体系审计

### 发现
- 正则脚本逐行解析 `_default_params` 漏检严重（同行多键只匹配第一个）
- 改用 Python 运行时直接调用 `cls._default_params()` → **34 模组全部与 mod.json 键对称**
- `_default_params` 是运行时唯一数据源: `__init__` 初始化和 `reset_params` 都依赖它

---

## 🔴 铁律汇总 (v5.0 新增)

1. **维度名保持干净**: 不加 `[单池]` 等前缀，用 `scope=` 参数声明作用域
2. **标签自包含**: 新模组标签写 `labels.json["dimensions"]`，不碰 `dimension_labels.py`
3. **scope 元数据分离**: 作用域是维度的一等属性，不由名字编码
4. **公式显式传参**: `add_dimension(formula=..., category=...)` — 不依赖全局查找
5. **正则审计不可靠**: 解析 Python 源码用运行时调用，不用正则
6. **PowerShell 替换谨慎**: 处理 JSON 用 Python json 模块，不用正则→容易损毁文件
7. **CASS 约束必须上下界**: 仅下界会让 87d 也通过
8. **砂斗下口 < 格宽**: hopper_bottom 必须小于单格宽度
9. **`_trace_upstream_context` 需水线感知**: 多 IO 源时按 process_stage 选择正确流量
10. **`@staticmethod` 不能有 `self`**: 会导致参数错位，语法不报错但运行时逻辑全乱

---

## 七、修改文件汇总

| 类别 | 文件数 | 说明 |
|------|--------|------|
| 基类 | 1 | `base.py`: SCOPE_PREFIX, dimension_scopes, get_display_name, scope= |
| UI | 3 | `main_window.py`: scope 渲染, 诊断去重; `file_manager.py`: 加载守卫; `dimension_labels.py`: 43 条目 |
| 引擎 | 1 | `solution_space.py`: _diagnosed 去重 |
| 模组代码 | 16 | 14× 前缀剥离 + CASS θc' 公式 + kw_chenshachi hopper + vxinglvchi Q_g2 |
| labels.json | 27 | 412 dim 条目 + dim_scopes + 18 vec_fields |
| 文档 | 2 | MOD_SPEC.md v5.0 重写 + 本记录 |

---

> **记录者**: Sisyphus | **版本**: v5.0 | **日期**: 2026-05-26
