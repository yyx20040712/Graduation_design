# 连线修复 + 水质UI + 表3-1验证 — 学习记录

> 日期: 2026-05-15

---

## 🔴 连线恢复验证

### 问题确认
graph_executor.from_dict() 中 port_id 解析 bug 已于上一轮修复
(改用 port_lookup 映射表替代 split("-")[0])。

### 额外加固
`_rebuild_canvas` 中的 port_map 构建从**按索引映射**改为**按 port_id 直接映射**:
```python
# 旧 (脆弱):
for i, bp in enumerate(be.input_ports):
    if i < len(ui.input_ports):
        port_map[bp.port_id] = ui.input_ports[i]

# 新 (稳健):
for p in ui.input_ports + ui.output_ports:
    port_map[p.port_id] = p
```
消除了后端端口与 UI 端口索引不一致的潜在风险。

### 验证结果
- save → load 往返测试: 3 connections → 3 connections ✓
- 蓝线 (WATER: pipe→combiner), 绿线 (QUALITY: wq→combiner), 橙线 (MIXED: combiner→tiaojiechi) 全部恢复

### 涉及文件
- `controller/graph_executor.py`: from_dict 连线重建 (已修)
- `ui/main_window.py`: _rebuild_canvas port_map 加固

---

## 🎨 水质输入 UI 重设计

### 设计理念
对齐方案浏览器的暗色主题 + 卡片式布局:
- 每个水质参数一张独立卡片
- 左侧: 彩色指示条 + 参数名 + 描述 + 出水标准
- 右侧: 大号数值显示 + 滑块 + 单位
- 6 种污染物各有独特颜色 (BOD蓝/COD橙/SS绿/NH3紫/TN粉/TP浅蓝)

### 默认值 (表3-1)
| 参数 | 默认值 | 出水标准(一级A) |
|------|--------|----------------|
| BOD₅ | 200 mg/L | ≤10 mg/L |
| COD | 400 mg/L | ≤50 mg/L |
| SS | 220 mg/L | ≤10 mg/L |
| NH₃-N | 35 mg/L | ≤5 mg/L |
| TN | 45 mg/L | ≤15 mg/L |
| TP | 5 mg/L | ≤0.5 mg/L |

以上与中期报告表3-1 及 GB18918-2002 一级A 标准一致。

### 交互
- 滑块实时更新大号数值显示
- 变更自动标记 dirty
- 适用于 WaterQualityNode 和 InputNode

### 涉及文件
- `ui/main_window.py`: _show_water_quality_card(), _on_wq_changed()
