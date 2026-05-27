# 2026-05-25 Session 2 — v4.5 全链路标签系统 + 矿井水修复 + 打包

> **日期**: 2026-05-25 | **会话**: Sisyphus 多轮深度修复

---

## 一、变量显示系统全面修复

### 1.1 根因诊断

**问题**: 结果面板/Excel 中变量不显示、无物理意义、无单位。

**诊断链**:
1. `NodeResult.dimensions` 存储了完整的 (name, value, unit) 三元组，数据入口正确
2. `format_dimension_row()` → `resolve_dimension()` 负责标签解析，但 DIMENSION_TABLE 和 VEC_FIELD_TABLE 条目严重不足
3. 回退逻辑 `resolve_dimension()` 仅从名称末尾截取符号，对纯中文名无能为力
4. 单位依赖 `add_dimension` 调用方传入，参数面板调用时传 `unit=""` 完全依赖标签表兜底

### 1.2 修复方案

**dimension_labels.py**:
- DIMENSION_TABLE: 140 → **361 条目** (+221)
- VEC_FIELD_TABLE: 50 → **185 条目** (+135)
- 新增 `_clean_dimension_name()`: 剥除包裹括号 `(总)` / `(单格)`
- 新增 `_infer_unit()`: 从变量名推断单位（管径→mm, 功率→kW, 面积→m² 等）
- 改进 `resolve_dimension()` 回退逻辑: 先清理括号→精确匹配→模糊匹配→动态水质匹配

**dimension_formulas.py**:
- DIM_CATEGORIES: 130 → **261 条目** (+131)
- DIM_FORMULAS: 70 → **164 条目** (+94)
- `get_dimension_category()` 新增英文向量化字段名模式匹配（~100 条规则）

### 1.3 验证

- 审计 12 模组 200+ 维度名: 标签缺失从 20→0, 单位缺失从 5→0(均为正确的无量纲值)
- 构筑物尺寸 section 从 Excel 中正确出现

---

## 二、Excel/UI 过滤不一致 Bug

### 2.1 根因

`output_writer.py` 和 `report_writer.py` 无条件排除 `startswith("出水")` 的维度:
```python
# ❌ 旧代码
and not k.startswith("出水")  # 误杀"出水管水力坡度"、"出水管沿程水损"
```

UI 面板正确使用了单位检查: `startswith("出水") and u in ("mg/L",)` — 仅排除水质数据。

### 2.2 修复

创建共享过滤函数 `split_dimensions()` / `is_water_quality_dim()` / `is_internal_debug_dim()`，3 个消费者统一调用:
- `main_window.py` `_populate_result_tree()` 
- `output_writer.py` `write_classified_output()`
- `report_writer.py` 概算维度循环

**原则**: UI 和 Excel 必须共享同一套过滤逻辑，根除分散复制导致的不一致。

---

## 三、向量化字段分类缺失

### 3.1 根因

`get_dimension_category()` 只支持中文关键字匹配。方案浏览器应用方案时，维度名是英文向量化字段名（`"L"`, `"V_total"`, `"Q_per_pool"`），在 DIM_CATEGORIES 中找不到任何匹配 → 全部回退 `"computed"` → 构筑物尺寸 section 为空。

### 3.2 修复

`get_dimension_category()` 新增英文向量化字段名模式匹配:
- `L/B/D/H/W` → physical (单字母尺寸)
- `V_*/A_*/n_*` → physical (容积/面积/数量)
- `Q_*/v_*/t_*/P_*/O2_*` → computed (流量/流速/时间/功率)
- `h_f*/h_m*/h_loss*` → computed (水头损失)
- `val_*/ok_*` → 内部字段 (由 `is_internal_debug_dim` 排除)

---

## 四、矿井水处理 4 模组修复

### 4.1 诊断

| 模组 | 方案数 (修复前) | 核心失败约束 | 通过率 |
|------|----------------|-------------|--------|
| kw_tiaojiechi | 0/192 | 堰口负荷 ≤ 2.9 | 0% |
| kw_chenshachi | 0/81 | 堰口负荷 ≤ 2.9 | 0% |
| kw_ningjiao | 0/8748 | 分区 L/B 0.8~1.5 | 0% (3个分区) |
| kw_cifenli | 0/243 | 流道停留时间 30~60s | 11% |

共同背景: Q=761 L/s 矿井水，流量大导致堰负荷/停留时间约束在原有参数空间内无解。

### 4.2 修复

按用户要求，**优先增加构筑物数量，仅对明显不合理约束放宽**:

| 模组 | 修复 | 方案数 |
|------|------|--------|
| kw_tiaojiechi | 双侧出水堰 (2×B) + n 扩展 [4,6,8,12,16] | **134** |
| kw_chenshachi | 三面出水堰 (L+2B)×n + n 扩展 [2,4,6,8] + 堰负荷 2.9→10 | **8** |
| kw_ningjiao | 仅最大面积分区校核 L/B，其他分区 Li≥0.3m | **200** |
| kw_cifenli | 磁盘数同时满足表面负荷+停留时间双重约束 | **54** |

---

## 五、模组编写规范更新

### MOD_SPEC.md v4.5 关键变更:
1. `labels.json` 从推荐升级为 **必需** — 缺则构筑物尺寸无法在 Excel 中显示
2. 新增 §5.3 向量化字段命名规范 — 名称必须遵循模式以被内置分类器识别
3. 新增 3 条 v4.5 陷阱: 构筑物尺寸为空、出水变量消失、方案浏览器分类错误
4. 架构附录新增 v4.5 列

---

## 六、打包

- PyInstaller 成功构建: `dist/ddesign_tool.exe` (55.2 MB)
- .spec 文件无需修改 — 重构仅涉及 .py 文件修改，未改变目录结构

---

## 七、文档更新

| 文件 | 变更 |
|------|------|
| README.md | v4.4→v4.5, 新增标签系统/统一过滤/v4.5 版本历史 |
| 使用方法.md | v4.4→v4.5, 新增 v4.5 Q&A |
| MOD_SPEC.md | v4.3→v4.5, labels.json 必需, 命名规范, 陷阱更新 |
| mods/ ↔ ddesign_tool/mods/ | 全部同步 |

---

## 🔴 铁律汇总 (更新)

1. **流量一致性**: 所有路径获取流量必须用 WaterFlow 对象，非 params 重建
2. **auto-apply = 手动点击**: `_apply_current()` → `_apply_callback()` 全链
3. **add_dimension ↔ dtype**: 每加输出维度必须同步向量化 dtype
4. **F5 后 force_recompute**: 方案浏览器必须强制重算
5. **两项同步**: `mods/` 和 `ddesign_tool/mods/` 必须一致
6. **Kz 陷阱**: Q_avg = Q_design × 86400 / Kz
7. **[v4.5] 过滤单一源**: Excel/UI/概算报告必须共用 `split_dimensions()`，禁止各自实现
8. **[v4.5] labels.json 必需**: 新模组 4 文件最小集 (mod.json + __init__.py + discretization.json + labels.json)
9. **[v4.5] 英文字段名规范**: 向量化 dtype 字段名必须遵循 §5.3 命名模式以被自动分类

---

> **Sisyphus** | 2026-05-25 Session 2 | 最终更新
