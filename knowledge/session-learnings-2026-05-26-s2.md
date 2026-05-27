# 2026-05-26 Session 2 — 紫外消毒公式修正 + 接触时间约束 + v5.0 打包

> **日期**: 2026-05-26 | **会话**: Sisyphus — UV消毒公式重写 + 参数校准 + 文档更新

---

## 一、紫外消毒池 (ziwai / kw_ziwai) 公式修正

### 参照标准
- GB50014-2021 §7.13: 一级A剂量 20~25 mJ/cm²
- GB/T19837-2019: 老化系数≤0.8, 结垢系数, 灯管功率分级
- 用户公式 (4-134)~(4-149)

### 公式变更

| 公式 | 旧 | 新 | 依据 |
|------|-----|-----|------|
| I_avg | `P·N·η·T·C/(h·d_long)` W/m² | `P·N·η·T·C/(10·B·H)` mW/cm² | (4-140) 单位自洽 |
| dose_per_row | `I·d_long/v·0.1` | `I·d_long/v` | 因 I_avg 已是 mW/cm² |
| D_actual | `I·t·0.1` | `I·t` | 同上 |
| H 约束 | `N·d_vert+0.1+0.1` | `N·d_vert+h_upper+h_lower` | (4-137) 0.3+0.2m |

### 参数变更

| 参数 | 旧值 | 新值 | 依据 |
|------|------|------|------|
| D_UV | 40 mJ/cm² | **20** | GB50014 一级A 20~25 |
| n_T | 2.0 | **1.5** | (4-134) 常取 1.5 |
| N_layer | 4 | **6** | 增加层数 |
| d_vert | 0.2m | **0.08m** | (4-137) 0.08~0.12m |
| d_long | 0.15m | **0.12m** | 0.08~0.15m |
| xi_total | 2.0→3.0 | **3.0** | 2~4 |

### 接触时间约束
- 从硬约束（add_check → FAIL）改为软约束（add_warning）
- 逻辑: 剂量达标时 t<6s → "可接受" warning；剂量不达标时 → "建议调整" warning
- 依据: 用户公式注"此条件一般已通过剂量公式满足，但可作为辅助判断"
- kw_ziwai 渠内流速下限 0.15→0.05 (矿井水流量小)

---

## 二、CASS 污泥计算公式修正

### (4-76) 剩余生物污泥
旧: `Px_bio = Y·Q·ΔS - KdT·V·X·f` (缺 ÷θc)
新: `Px_bio = Y·Q·ΔS/1000 - KdT·V·X·f/θc` (正确)

### (4-77) 剩余非生物污泥
旧: `Q·(SS_in·(1-f_b)/1000 - SS_out/1000)`, f_b=0.6
新: `Q·(1-f·f_b)·(C0-Ce)/1000`, f_b=0.7, f=0.75

### θc 调优
- 默认 25→20 (迭代后稳定值)
- Ns 保持 0.08 (配合 θc=20 通过校核)

---

## 三、v5.0 架构升级

### 作用域系统 (scope)
- `add_dimension(name, ..., scope="single")` — 维度名干净，作用域独立
- `labels.json["dim_scopes"]` — 声明式作用域映射
- UI 渲染: `[单池]有效容积` 运行时组合

### 标签自包含
- 412 条目从 `DIMENSION_TABLE` 迁移到各模组 `labels.json["dimensions"]`
- 新模组标签只需写自己的 `labels.json`，不碰全局表

### 新增 43 条 DIMENSION_TABLE
- 泵站/脱水/干化/向量化字段标签全覆盖
- 验证: 327 checked, 0 missing

---

## 四、连锁 Bug 修复

| Bug | 修复 |
|-----|------|
| V型滤池 0 可行方案 | `Q_g2_val = q_g2 * A_actual` |
| 启动诊断轰炸 | `_loading_project` 守卫 + `_diagnosed` 去重 |
| `_get_scope_prefix` TypeError | `@staticmethod` 与 `self` 冲突 |
| kw_chenshachi 砂斗容积=0 | hopper_bottom 0.6→0.4 |
| 紫外剂量约束限值不匹配 | discretization ">= 30"→">= 20" |
| kw_ziwai 渠内流速全部失败 | 下限 0.15→0.05 |

---

> **记录者**: Sisyphus | **版本**: v5.0 | **日期**: 2026-05-26
