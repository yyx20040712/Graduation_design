# 2026-05-20 会话回顾 — MC 式架构全面加固

> **会话时长**: ~6 小时 | **修改文件**: 50+ | **架构版本**: v3.3 → v3.4

---

## 一、发现的 Bug 与根因

| # | Bug | 症状 | 根因 | 修复 |
|---|-----|------|------|------|
| 1 | `NoneType.node_id` | 打包后无法打开 kuangjing.ddesign.json | `_COMPAT_MODULE_MAP` 漏了 3 个矿井水类型 → `default_node_factory` 返回 None → `add_node(None)` 崩溃 | 替换为约定自动发现 + 添加 None 检查 |
| 2 | 方案=0 | 旋流沉砂池/初沉池/紫外消毒池无可行方案 | `_trace_upstream_context` 取到单格流量(190 L/s)而非总流量(570 L/s) | 非 IO 节点始终递归到源头 |
| 3 | 水头损失=0 | 格栅过栅水头 ~2.6×10⁻⁶m | `discretization.json` 中 `s` 用 m(0.01) 但代码期望 mm(10.0) — 1000× 误差 | 修正 mod `discretization.json` |
| 4 | 巴氏计量槽崩溃 | `numpy.ndarray.get()` | `_cost_generic_rect` 用 dict 方法访问 numpy 数组 | 重写成本估算器 → 标准字段契约 |
| 5 | SyntaxError | EXE 启动崩溃 | `mod_manager.py` 交换优先级时留下孤立 `finally:` | 删除孤立 finally |
| 6 | .pyc 缓存 | 源码修改不生效 | Python 字节码缓存遮蔽源文件 | 构建前清理 `__pycache__` |

---

## 二、架构演进

### Phase 1: 消除硬编码 → 约定自动发现

```
Before: _COMPAT_MODULE_MAP (24 条硬编码)
After:  _resolve_by_convention() → models.{type} → {PascalCase}Node
        仅 4 条例外 (cugeshan/xigeshan/cass/aao)
```

### Phase 2: MC 式自包含模组

```
Before: models/{id}.py ←─ bridge ── mods/core/{id}/__init__.py  (撕裂)
After:  mods/core/{id}/__init__.py  ← 完整类定义 (一个文件夹 = 一个模组)
```

- 23 个模组迁移
- `ModManager.load_mod()` 优先从 `__init__.py` 加载
- `mod.json` 中 `module_path` 清空

### Phase 3: 标准化输出契约

每个 `_vectorized_compute` 必须输出 L/B/D/H 标准字段：

| 池型 | L | B | D | H |
|------|---|---|---|---|
| 矩形池 | >0 | >0 | 0 | >0 |
| 圆形池 | 0 | 0 | >0 | >0 |

成本估算器从 5 个特殊函数简化为 2 个通用函数（`_cost_rectangular` / `_cost_circular`）。

### Phase 4: 数据流修复

- `_trace_upstream_context`: 非 IO 节点始终递归到源头（避免取单格流量）
- `graph_executor.from_dict()`: None 检查防止静默失败
- `discretization.json`: 所有 28 个模组均有 `estimator_type`

---

## 三、最终性能指标

| 指标 | 数值 |
|------|------|
| 模组加载 | 28/28 in 0.10s |
| 项目加载 (19 节点) | 0.36s |
| 图执行 (19 节点) | < 0.01s |
| 方案枚举 (26 类型) | 2507 方案 in 0.06s |
| EXE 大小 | 54.2 MB |
| 代码规模 | ~24,581 行 / 93 文件 |
| 模组数 | 28 (25 core + 3 community) |

---

## 四、关键教训

1. **双重数据源是万恶之源**: `_COMPAT_MODULE_MAP` + ModManager, `DISCRETE_CONFIGS` + mod `discretization.json` — 每次不一致都导致 bug
2. **隐式契约必然被违反**: 成本估算器猜字段名 → 新模组崩溃。必须显式契约（标准字段）
3. **缓存遮蔽一切**: `.pyc` 导致修改不生效 → 构建前必须清理
4. **单位不一致极隐蔽**: m vs mm 导致 1000× 误差但约束依然通过（因为值太小）
5. **模组自包含是唯一正道**: MC 的一个 JAR 原则 — 所有依赖在文件夹内，零外部文件

---

## 五、更新的文档

| 文件 | 更新内容 |
|------|---------|
| `README.md` | v3.3→v3.4, 架构描述, 模组数更新 |
| `PACKAGING.md` | 打包历史 +2 行 |
| `MODS_GUIDE.md` | 完全重写: 自包含模组, 标准字段契约, 新检查清单 |
| `node_registry.py` | Phase 3 约定自动发现 |
| `mod_manager.py` | MC 式加载优先级 |
| `fast_estimator.py` | v2 标准化输出契约 |
| `main_window.py` | `_trace_upstream_context` 修复 |
| `graph_executor.py` | None 检查 |
| `discretization.py` | 单位修正 (s: m→mm) |
| 28 个 `discretization.json` | 全部添加 `estimator_type` |
| 25 个 `__init__.py` | 自包含迁移 + L/B/D/H 标准字段 |

---

> **记录者**: Sisyphus | **日期**: 2026-05-20 | **版本**: v3.4
> **下次提醒**: 新模组遵循 MODS_GUIDE.md v3.4 契约，零框架修改
