# 排水工程设计工具 v3 — 项目学习记录

> 最后更新: 2026-05-14
> 记录相当于"程序员的项目笔记"，用于后续修改时快速理解架构

---

## 一、项目概况

**入口**: `ddesign_tool/main.py` → `ui/main_window.py::MainWindow.run()`
**启动**: 双击 `run.bat` (自动查找 Python)
**日志**: `ddesign_tool/logs/ddesign_YYYYMMDD.log`

### 文件清单

```
ddesign_tool/
├── main.py                          # 入口, --cli 切换 CLI 模式
├── run.bat                          # 一键启动器 (自动查找 python)
├── src/
│   ├── models/                      # 业务模型层
│   │   ├── base.py                  # ★ 核心基类: NodeBase, ParamDef, WaterFlow, WaterQuality, NodeResult
│   │   ├── input_node.py            # 旧版输入节点 (流量+水质合体, 逐步废弃)
│   │   ├── pipe_network.py          # 管网 Excel 输入 (WATER 端口)
│   │   ├── water_quality_node.py    # 独立水质节点 (QUALITY 端口, 默认鹤岗数据)
│   │   ├── combiner.py              # 合并节点 WATER+QUALITY→MIXED
│   │   ├── tiaojiechi.py            # 调节池
│   │   ├── geshan.py                # 粗格栅+细格栅 (共享 _BarScreenBase 基类)
│   │   ├── chenshachi.py            # 旋流沉砂池 (钟氏)
│   │   ├── chuchenchi.py            # 辐流式初沉池
│   │   ├── cass.py                  # ★ CASS 反应器 (最复杂: BOD负荷法+需氧量+污泥龄)
│   │   ├── gaomidu.py               # 高密度沉淀池
│   │   ├── vxinglvchi.py            # V型滤池 (含反冲洗)
│   │   ├── ziwai.py                 # 紫外消毒池 (剂量迭代)
│   │   └── cost/                    # 工程概算模块
│   │       ├── unit_prices.py       # 单价数据库
│   │       ├── cost_estimator.py    # BOQ 工程量清单引擎
│   │       └── report_writer.py     # Excel 报告生成
│   ├── controller/                  # 控制层
│   │   ├── graph_executor.py        # ★ DAG 执行引擎 (拓扑排序+增量计算)
│   │   └── project_manager.py       # .ddesign.json 项目读写
│   └── ui/                          # UI 层 (tkinter)
│       ├── logger.py                # 日志系统
│       ├── main_window.py           # ★ 主窗口 (3 Tab: 参数/结果/水质)
│       └── canvas_view.py           # ★ 节点画布 (Blender 风格端口+贝塞尔连线)
```

---

## 二、关键架构决策

### 2.1 端口类型体系
```
PortType.WATER   → 蓝色外环端口 — 仅传递 WaterFlow
PortType.QUALITY → 绿色外环端口 — 仅传递 WaterQuality  
PortType.MIXED   → 橙色外环端口 — 传递两者
```

### 2.2 数据流 (典型管线)
```
[PipeNetworkNode] → WATER ─┐
                            ├→ [CombinerNode] → MIXED → [Tiaojiechi] → ... → [Ziwai]
[WaterQualityNode]→ QUALITY┘
```

### 2.3 Kz 处理
- 管网 Excel 输出的"设计流量"**已含 Kz**（峰值流量）
- 后端所有节点直接使用 `flow.Q_design`，**不重复乘 Kz**
- `flow.Q_avg_daily` 用于 CASS/沉砂池等需要日均流量的场合

### 2.4 水质追踪
- `NodeBase.execute()` 自动记录 `result.inlet_quality` 和 `result.outlet_quality`
- `outlet_quality = inlet.apply_removal(self._removal_rates)`
- UI 右侧面板"水质"Tab 以 `进水→出水` 格式展示

---

## 三、已知 Bug 及注意事项

### 3.1 已修复的 Bug
| Bug | 原因 | 修复 |
|-----|------|------|
| 拖拽节点文字消失 | Z-order: 只 raise 了矩形未 raise 文本 | 统一 tag 管理, `move()` 末尾 `raise_all()` |
| 缩放后连线漂移 | `canvas.scale("all")` 不更新 Python 坐标 | `_sync_all_positions()` 回读 Canvas 坐标 |
| `_id` 属性错误 | 端口重写时改名未同步 | `_id` → `_outer_id`/`_inner_id` |
| 全局滚轮泄露 | `bind_all` 在 `_refresh_params` 中累积 | 改用局部 `canvas.bind` |

### 3.2 潜在问题 (未修复, 需注意)
| 问题 | 位置 | 严重程度 |
|------|------|---------|
| `except Exception: pass` 吞异常 | pipe_network.py:142, input_node.py:155 | 低 — 仅影响 Excel 加载容错 |
| 删除"最后一个节点"在 Python<3.7 不保证是最后添加的 | main_window.py `_delete_selected` | 低 — 项目要求 Python 3.10+ |
| 参数面板 refresh 时旧 DoubleVar 对象残留 | main_window.py:236 | 低 — 仅内存不释放, 不影响功能 |
| 格栅 `_default_params()` 返回值被子类覆盖 | geshan.py | 无 — 设计如此, 子类覆写 |

### 3.3 禁止操作
- 不要在 `NodeBase.calculate()` 中修改 `flow` 或 `quality` 参数(它们是上游数据)
- 不要用 `bind_all` 绑定全局事件(用局部 `canvas.bind` 代替)
- 端口改名后必须同步 `raise_all()`、`remove_node()` 中的引用

---

## 四、UI 交互速查

| 操作 | 快捷键/鼠标 |
|------|-----------|
| 选中节点 | 左键点击 |
| 移动节点 | 左键拖拽 |
| 创建连线 | 右键从端口拖到另一端口 |
| 断开连线 | 右键从已连接端口拖到空白处 |
| 平移视角 | 中键拖拽 (手型光标) |
| 缩放 | Ctrl+滚轮 |
| 添加节点 | 画布空白处右键 / 工具栏"➕添加节点" |
| 删除节点 | 节点上右键→删除 / 工具栏"🗑删除" |
| 计算全部 | F5 |
| 切换面板 | 点击 [参数] [结果] [水质] Tab |

---

## 五、修改指南

### 添加新处理单元
1. 在 `models/` 创建 `new_module.py`，继承 `NodeBase`
2. 必须实现: `NODE_TYPE`, `NODE_NAME`, `NODE_CATEGORY`, `_default_params()`, `_build_param_defs()`, `_default_removal_rates()`, `calculate()`
3. 在 `main_window.py` 的 `NODE_REGISTRY` 和 `FORMULAS` 中注册
4. 在 `canvas_view.py._show_canvas_menu()` 的 `categories` 中添加

### 修改计算公式
- 找到对应 `models/xxx.py` 的 `calculate()` 方法
- 公式来源对照实现计划的 §10 公式索引表
- 修改后运行 `python -c "from models.xxx import *; ..."` 验证

### 调试技巧
- 查看日志: `ddesign_tool/logs/` 目录
- 在 `calculate()` 中打印变量时用 `log.debug()` 而非 `print()`
- UI 崩溃时先检查 `logs/` 中是否有 Python traceback
