# 2026-05-25 学习记录 — 全链路修复

> **日期**: 2026-05-25 | **修改文件**: 20+

---

## 一、CASS 长宽比 + 流量偏差诊断

### 用户报告
> "方案页面 L=61 ratio=5.08，结果页面 L=43 ratio=3.58，参数相同但结果不同"

### 诊断链
1. 标量 vs 向量化公式一致 → 排除计算 bug
2. 方案浏览器未选中已应用方案 → 新增 `_select_applied()`
3. `_select_applied` 缺 `_apply_callback` → 面板不刷新
4. **根因**: `_trace_upstream_context` 递归后从 Combiner 空 params 重算 Q_avg:
   - Kz=1.0 → Q_avg = 0.57×86400 = 49248 (应为 35177)
   - V_main 差 1.4× → ratio_LB 从 5.08 翻为 3.58

---

## 二、修复: `_trace_upstream_context` + Combiner

- **修复 1**: 递归后用 `rec_flow` 全字段，不从中间节点 params 重算
- **修复 2**: Combiner `result.params` 保存 Q_design/Kz/Q_avg_daily

---

## 三、修复: 方案浏览器一致性

- 新增 `_select_applied()` — 自动定位已应用方案
- 新增 `_apply_current()` — 核心逻辑复用
- 递归 guard `_selecting` 防止无限循环
- F5 后 `_show_browse_mode(force_recompute=True)` 强制刷新缓存
- F5 后自动应用可行方案，确保结果面板不显示违约束方案

---

## 四、CASS 安全距离 1.5~2.0m + λ 自动调整

- 约束改: `>= delta_H_safe` → `1.5 <= H_safe <= 2.0`
- 不满足时 λ 自动调整: `λ_new = 1 - H_sludge/H_max - 1.75/H_max`
- 充水比一致性校核移到 λ 调整之后
- 向量化同步: `ok_safe = (1.5 <= H_safe) & (H_safe <= 2.0)`

---

## 五、gaomidu 斜管轴向流速 + t_thicken 修正

- v_axial: m/s → mm/s (×1000)，Excel 不再显示 0.00
- t_thicken 单位: mod.json "min" → "h"
- 约束: `<= 0.005` m/s → `<= 5.0` mm/s

---

## 六、V型滤池参数 + 反冲洗 + 扫洗孔

- UI 参数 6→14: +k_self, h_super, h_plate, h_under, rho_head, q_g1, q_g2, q_w3
- 输出维度 +6: Q_g1, Q_g2, Q_w2, Q_w3, Q_s, A_V
- 扫洗孔 (4-116~4-118): d_hole, v_hole, A_孔, a_孔, n_孔, 约束 ≥20 个/侧
- 修复 dtype 重复 L/B/H 和 val_H_loss

---

## 七、泵站出水管水头损失

- wuni_bengzhan + wuni_shusong: 新增 L_pipe 参数 + Manning 水头损失
- wuni_tisheng: 对照规格书修正，n_rough 0.014, L/B 2.0
- 向量化 dtype 补全 h_f_suction/h_f_discharge/h_loss 等

---

## 八、全局向量化 dtype 审计

审计 34 个模组的 `add_dimension` ↔ `_vectorized_compute` dtype 一致性:

| 修复批次 | 模组 | 新增字段 |
|---------|------|---------|
| 市政 | AAO | V_total_series, Px, O2_total, Q_r, Q_ri |
| 市政 | vxinglvchi | Q_g1~Q_s, A_v_slot, A_hole, a_hole |
| 污泥 | wuni_bengzhan | h_f, h_m, h_loss |
| 污泥 | wuni_shusong | h_f, h_m, h_loss |
| 污水提升 | wuni_tisheng | h_f_suction, h_f_discharge, i_suction, i_discharge |
| 矿井水 | kw_vxinglvchi | T_w, Q_d |
| 矿井水 | kw_chenshachi | +8 fields |
| 矿井水 | kw_ningjiao | +10 fields |
| 矿井水 | kw_cifenli | +5 fields |

---

## 九、污水提升泵站对照规格书

- L_suction/L_discharge: 硬编码 → 可调参数
- n_rough: 0.013 → 0.014 (混凝土管)
- 长宽比: 1.8 → 2.0 (规格书 2:1)

---

## 十、文档更新

- `README.md`: v4.4, 34模组清单, 版本历史
- `使用方法.md`: 精简重构

---

## 🔴 铁律汇总

1. **流量一致性**: 所有路径获取流量必须用 WaterFlow 对象，非 params 重建
2. **auto-apply = 手动点击**: `_apply_current()` → `_apply_callback()` 全链
3. **add_dimension ↔ dtype**: 每加输出维度必须同步向量化 dtype，否则 Excel/方案浏览器空白
4. **F5 后 force_recompute**: 方案浏览器必须强制重算，否则 dtype 变更后缓存过期
5. **两项同步**: `mods/` 和 `ddesign_tool/mods/` 必须一致
6. **logger 继承**: `logging.getLogger("CASS")` 不继承 "ddesign" handler
7. **Kz 陷阱**: Q_avg = Q_design × 86400 / Kz，空 params 导致 Kz=1.0 → 40% 偏差

---

> **Sisyphus** | 2026-05-25 | 最终更新
