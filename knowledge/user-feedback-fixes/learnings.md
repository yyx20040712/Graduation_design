# 用户反馈修复 — 学习记录

> 日期: 2026-05-15
> 触发: 用户实际使用后的三项反馈

---

## 一、污染物去除率对照与 UI (Task 1)

### 中期报告表 3-2 去除率对照

| 工艺 | BOD5 | COD | SS | NH3N | TN | TP |
|------|------|-----|-----|------|-----|-----|
| 粗格栅 | 5% | 5% | 5% | — | — | — |
| 细格栅 | 8% | 8% | 8% | — | — | — |
| 沉砂池 | 5% | 5% | 10% | — | — | — |
| 初沉池 | 30% | 30% | 50% | 5% | 5% | 5% |
| CASS | 92% | 88% | 70% | 90% | 75% | 65% |
| 高密度沉淀池 | 20% | 60% | 90% | — | — | 85% |
| V型滤池 | 15% | 25% | 65% | — | — | 80% |
| 紫外消毒 | — | — | — | — | — | — |

以上值与中期报告 §3.2~§3.8 各节中的去除率范围一致（取中值）。

### UI 实现

在「手动微调」模式的参数面板底部添加了「🧪 污染物去除率」区域：
- 每个污染物一个滑块，范围 0~100%，精度 1%
- 变更后标记 `_dirty = True`
- 颜色为绿色（#55cc55）以区分设计参数（橙色）

### 涉及文件
- `ui/main_window.py`: `_show_manual_mode()` 末尾 + `_on_rate_changed()` 方法

---

## 二、保存/退出 Bug 修复 (Task 2)

### 问题根因
`_on_close` 无条件弹出"是否保存"对话框，即使用户刚刚保存过。

### 修复方案
增加 `_dirty` 标志位：
- `True`: 有未保存修改（参数变更、节点增删、方案应用）
- `False`: 已保存或加载后无修改

涉及修改点：
1. `__init__`: 初始化 `self._dirty = False`
2. `_on_param_changed`: `self._dirty = True`
3. `_add_node`: `self._dirty = True`
4. `_on_solution_applied`: `self._dirty = True`
5. `_on_save` / `_on_save_as`: `self._dirty = False`
6. `_on_close`: 仅 `self._dirty and node_count > 0` 时弹窗
7. `_load_default_demo` / `_open_recent`: `self._dirty = False`

---

## 三、最近文件功能 (Task 3)

### 设计
参考 Blender 启动界面：
1. **启动对话框**: 有最近文件时弹出 `_show_recent_dialog()`，列出最近 10 个项目
2. **文件菜单**: "最近文件" 子菜单，动态更新
3. **保存时**: 自动记录到 `ProjectManager` 的最近文件列表

### 实现细节
- `_show_recent_dialog()`: 创建 `Toplevel` 模态对话框，显示文件列表
- `_update_recent_menu()`: 每次保存/打开后刷新菜单
- `_open_recent(path)`: 加载指定项目
- `_on_recent_click()`: 对话框内点击文件
- 新建/浏览按钮在对话框底部

### 涉及文件
- `ui/main_window.py`: 新增 6 个方法，修改 3 处

---

## 四、连带修复

- 在 `_on_open` 后也刷新 `_update_recent_menu()`
- `_load_demo` 拆分为 `_load_demo` → 对话框 → `_load_default_demo`
