# 连线丢失 + 最近文件 + 去除率保存 — 修复记录

> 日期: 2026-05-15

---

## 🔴 Bug 1: 保存文件重开后连线消失

### 根因
`graph_executor.py::GraphExecutor.from_dict()` 第 386 行：
```python
from_node_id = from_pid.split("-")[0]
```
端口 ID 格式为 `pipe_network-45e82552-wout`，
node_id 为 `pipe_network-45e82552`（含连字符）。
`split("-")[0]` 只取到 `"pipe_network"`，丢失了 UUID 部分，
导致 `executor.get_node(from_node_id)` 返回 None。

### 修复
改为构建 `port_id → Port` 全局映射表，直接通过 port_id 查找：
```python
port_lookup = {}
for node in executor._nodes.values():
    for p in node.input_ports + node.output_ports:
        port_lookup[p.port_id] = p

for conn in d.get("connections", []):
    from_port = port_lookup.get(conn["from"])
    to_port = port_lookup.get(conn["to"])
    if from_port and to_port:
        executor.connect(from_port, to_port)
```
○(N) 时间，正确性由 port_id 唯一性保证。

### 涉及文件
`controller/graph_executor.py`: 第 381-401 行

---

## 🟡 Issue 2: 启动时弹出最近文件对话框

### 问题
之前添加的 Blender 风格启动对话框每次启动都弹窗，干扰性太强。

### 修复
回归静默模式：启动时自动恢复最近项目（失败则加载示例），
文件菜单中保留「最近文件」子菜单供手动切换。

启动对话框相关代码（`_show_recent_dialog`、`_on_recent_click` 等）已删除。

### 涉及文件
`ui/main_window.py`: `_load_demo()` 简化

---

## 🟢 Issue 3: 去除率修改后的保存

### 验证结果
去除率保存机制已正确实现：
1. `NodeBase.set_removal_rate()` → 更新 `self._removal_rates` 字典
2. `NodeBase.to_dict()` → 序列化 `removal_rates`
3. `NodeBase.from_dict()` → 反序列化恢复
4. `_on_rate_changed()` → 标记 `_dirty = True`

不保存的可能原因是：用户修改去除率后未按 Ctrl+S。
建议后续添加状态栏提示「有未保存修改」。
