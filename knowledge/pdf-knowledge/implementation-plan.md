# 排水工程设计工具 - 详细实现规划

> 基于中期答辩报告（2026.03.20）、现有代码模块、及 2019 黑龙江市政定额

---

## 目录
1. [系统架构总览](#1-系统架构总览)
2. [数据模型与流图](#2-数据模型与流图)
3. [UI 交互层 — 用户界面与操作体验](#3-ui-交互层--用户界面与操作体验)
   - 3.0 [参考软件与设计语言](#30-参考软件与设计语言)
   - 3.1 [主窗口布局](#31-主窗口布局)
   - 3.2 [节点编辑器核心交互](#32-节点编辑器核心交互)
   - 3.3 [右侧面板（多Tab）](#33-右侧面板多tab)
   - 3.4 [全局功能](#34-全局功能)
   - 3.5 [项目文件系统](#35-项目文件系统)
   - 3.6 [数据可视化增强](#36-数据可视化增强)
   - 3.7 [工程概算可视化](#37-工程概算可视化)
   - 3.8 [错误处理与用户引导](#38-错误处理与用户引导)
   - 3.9 [配置文件系统](#39-配置文件系统)
4. [数据输入与解析模块](#4-数据输入与解析模块)
5. [业务逻辑层 - 污水处理厂计算](#5-业务逻辑层---污水处理厂计算)
6. [工程概算模块](#6-工程概算模块)
7. [结果输出与报告模块](#7-结果输出与报告模块)
8. [实现路线图](#8-实现路线图)
9. [附录A：单位换算速查表](#9-附录a单位换算速查表)
10. [附录B：公式索引对照表](#10-附录b公式索引对照表)

---

## 1. 系统架构总览

### 1.1 分层架构

```
┌─────────────────────────────────────────────┐
│              UI 层 (PyQt6)                    │
│  ┌─────────────────┐  ┌───────────────────┐  │
│  │ 节点编辑器 Canvas │  │ 参数面板/结果面板  │  │
│  └─────────────────┘  └───────────────────┘  │
├─────────────────────────────────────────────┤
│           应用控制层 (controller)              │
│  ┌────────────────┐  ┌──────────────────┐    │
│  │ GraphExecutor   │  │ CostEstimator    │    │
│  └────────────────┘  └──────────────────┘    │
├─────────────────────────────────────────────┤
│           业务逻辑层 (models)                  │
│  ┌──────────┬──────────┬──────────┬───────┐  │
│  │ tiaojiechi│ geshan  │chenshachi│ ...   │  │
│  └──────────┴──────────┴──────────┴───────┘  │
├─────────────────────────────────────────────┤
│           基础设施层 (infra)                   │
│  ┌──────────┬──────────┬──────────────────┐  │
│  │Excel I/O │ Logging  │  Cost DB (定额)   │  │
│  └──────────┴──────────┴──────────────────┘  │
└─────────────────────────────────────────────┘
```

### 1.2 目录结构（新增/修改）

```
ddesign_tool/
├── main.py                    # 改为启动 UI
├── config.ini                 # 增强版设计参数配置（含UI设置）
├── src/
│   ├── __init__.py
│   ├── ui/                    # 【新增】UI 层
│   │   ├── __init__.py
│   │   ├── main_window.py     # 主窗口 + 菜单栏 + 工具栏
│   │   ├── node_canvas.py     # 节点编辑器画布 (QGraphicsScene)
│   │   ├── node_widgets.py    # 节点控件 (基类 + 各类型)
│   │   ├── node_library.py    # 左侧节点库面板（树形可搜索）
│   │   ├── connection.py      # 连线/端口系统（自动正交路由）
│   │   ├── port_widget.py     # 端口控件（拖拽连线起点/终点）
│   │   ├── param_panel.py     # 参数面板（Tab: 参数）
│   │   ├── result_panel.py    # 结果面板（Tab: 结果+校核）
│   │   ├── quality_panel.py   # 水质变化面板（Tab: 水质）含图表
│   │   ├── cost_panel.py      # 概算面板（Tab: 概算）含饼图
│   │   ├── minimap.py         # 小地图导航
│   │   ├── search_popup.py    # Tab键弹出节点搜索
│   │   ├── theme_manager.py   # 暗色/亮色主题切换
│   │   ├── shortcut_manager.py# 快捷键注册与管理
│   │   └── welcome_dialog.py  # 首次启动引导
│   ├── models/                # 【新增】业务模型
│   │   ├── __init__.py
│   │   ├── base.py            # 基类：NodeBase + ParamDef + Port
│   │   ├── input_node.py      # 输入节点（水量+水质）
│   │   ├── tiaojiechi.py      # 调节池
│   │   ├── geshan.py          # 格栅（粗+细）[重写]
│   │   ├── chenshachi.py      # 旋流沉砂池 [重写]
│   │   ├── chuchenchi.py      # 辐流式初沉池 [重写]
│   │   ├── cass.py            # CASS 反应器 [新增]
│   │   ├── gaomidu.py         # 高密度沉淀池 [新增]
│   │   ├── vxinglvchi.py      # V型滤池 [新增]
│   │   ├── ziwai.py           # 紫外消毒池 [新增]
│   │   └── cost/              # 工程概算子模块
│   │       ├── __init__.py
│   │       ├── pipe_cost.py   # 管网概算
│   │       └── plant_cost.py  # 污水厂概算
│   ├── controller/            # 【新增】控制器
│   │   ├── __init__.py
│   │   ├── graph_executor.py  # DAG 执行引擎（拓扑+并行调度）
│   │   ├── cost_estimator.py  # 概算引擎
│   │   └── project_manager.py # 项目文件读写(.ddesign.json)
│   ├── visualization/         # 【新增】可视化
│   │   ├── __init__.py
│   │   ├── sankey_chart.py    # 水质桑基图
│   │   ├── comparison_view.py # 方案对比视图
│   │   └── cost_charts.py     # 概算图表（饼图/柱状图）
│   ├── io/                    # 【保留+增强】
│   │   ├── __init__.py
│   │   ├── data_loader.py     # Excel 读取 [保留]
│   │   └── result_writer.py   # Excel 输出 [增强多sheet报告]
│   ├── legacy/                # 【归档】旧管道计算模块
│   │   ├── calculate_pipes.py
│   │   ├── pipe_calculation.py
│   │   ├── design_engine.py
│   │   ├── stom_pipes.py
│   │   └── task_manager.py
│   ├── cli.py                 # 【保留】CLI 模式
│   └── utils.py               # 通用工具函数
├── data/                      # 输入数据 + 定额数据库
├── output/                    # 输出结果
├── projects/                  # 用户项目存档(.ddesign.json)
├── templates/                 # 预置项目模板
└── logs/                      # 日志
```

---

## 2. 数据模型与流图

### 2.1 核心数据类

```python
# ========== 基础数据类型 ==========
@dataclass
class WaterQuality:
    """水质参数，所有浓度单位 mg/L"""
    BOD5: float        # 生化需氧量
    COD: float         # 化学需氧量
    SS: float          # 悬浮固体
    NH3N: float        # 氨氮
    TN: float          # 总氮
    TP: float          # 总磷
    pH: float = 7.0    # pH值

@dataclass
class WaterFlow:
    """水量参数"""
    Q_design: float    # 设计流量，m³/s (Qmax = 0.57)
    Q_avg_daily: float # 平均日流量，m³/d (34760.7)
    Kz: float          # 总变化系数 (1.4)
    Q_avg_hourly: float # 平均时流量，m³/h (= Q_avg_daily/24)

@dataclass
class NodeResult:
    """节点计算结果"""
    success: bool
    params: Dict[str, Any]     # 输入参数
    dimensions: Dict[str, Any] # 构筑物尺寸
    checks: Dict[str, Any]     # 校核结果
    warnings: List[str]        # 警告信息
```

### 2.2 节点间数据流

```
[输入节点] → {WaterFlow, WaterQuality}
    ↓
[调节池]   → {WaterFlow (不变), WaterQuality (均化)}
    ↓
[粗格栅]   → {WaterFlow, WaterQuality (去除SS/BOD)}
    ↓
[细格栅]   → {WaterFlow, WaterQuality (进一步去除)}
    ↓
[旋流沉砂池] → {WaterFlow, WaterQuality (去除砂粒/SS)}
    ↓
[辐流式初沉池] → {WaterFlow, WaterQuality (去除SS 40-60%, BOD 25-35%)}
    ↓
[CASS反应器] → {WaterFlow, WaterQuality (去除BOD/COD/NH3N/TN/TP)}
    ↓
[高密度沉淀池] → {WaterFlow, WaterQuality (去除SS 85-95%, TP 80%+)}
    ↓
[V型滤池]   → {WaterFlow, WaterQuality (去除SS 45-85%)}
    ↓
[紫外消毒池] → {WaterFlow, WaterQuality (灭菌，出水达标)}
    ↓
[出水节点]  → 最终出水水质
```

### 2.3 污染物逐级去除模型

每个处理模块从上游接收 `WaterQuality`，应用自身去除率（可调），输出新的 `WaterQuality`：

```python
def apply_removal(inlet: WaterQuality, removal_rates: Dict[str, float]) -> WaterQuality:
    """去除率以小数表示，如 0.40 表示去除 40%"""
    return WaterQuality(
        BOD5 = inlet.BOD5 * (1 - removal_rates.get('BOD5', 0)),
        COD  = inlet.COD  * (1 - removal_rates.get('COD', 0)),
        SS   = inlet.SS   * (1 - removal_rates.get('SS', 0)),
        NH3N = inlet.NH3N * (1 - removal_rates.get('NH3N', 0)),
        TN   = inlet.TN   * (1 - removal_rates.get('TN', 0)),
        TP   = inlet.TP   * (1 - removal_rates.get('TP', 0)),
        pH   = inlet.pH,  # pH不通过简单去除率计算
    )
```

**默认去除率参考表（来自中期报告表3-2）：**

| 工艺单元 | SS | BOD5 | COD | NH3-N | TN | TP |
|---------|-----|------|-----|-------|----|-----|
| 调节池 | 0% | 0% | 0% | 0% | 0% | 0% |
| 粗格栅 | 5% | 5% | 5% | 0% | 0% | 0% |
| 细格栅 | 8% | 8% | 8% | 0% | 0% | 0% |
| 旋流沉砂池 | 10% | 5% | 5% | 0% | 0% | 0% |
| 辐流初沉池 | 50% | 30% | 30% | 5% | 5% | 5% |
| CASS反应器 | 70% | 92% | 88% | 90% | 75% | 65% |
| 高密度沉淀池 | 90% | 20% | 60% | 0% | 0% | 85% |
| V型滤池 | 65% | 15% | 25% | 0% | 0% | 80% |
| 紫外消毒池 | 0% | 0% | 0% | 0% | 0% | 0% |

---

## 3. UI 交互层 — 用户界面与操作体验

### 3.0 参考软件与设计语言

本软件 UI/UX 参考以下成熟产品的最佳实践：

| 参考软件 | 借鉴特性 |
|---------|---------|
| **Blender Shader Editor** | 节点画布缩放/平移/框选手感、连线吸附、端口颜色编码 |
| **Unreal Engine Blueprint** | 节点分类面板（左侧可折叠树）、节点搜索（Tab弹出）、执行引脚vs数据引脚区分 |
| **Davinci Resolve Fusion** | 节点缩略图预览、多节点框选后批量移动、对齐/分布工具 |
| **ComfyUI** | 节点加载状态指示器（旋转动画）、队列执行进度条、节点组模板保存/加载 |
| **Obsidian Canvas** | 自由画布布局、嵌入卡片式结果显示、Markdown 笔记内嵌 |
| **MATLAB/Simulink** | 连线自动路由（避障正交布线）、子系统封装、库浏览器 |
| **AutoCAD Civil 3D** | 属性面板（Property Palette）可停靠/浮动、右键上下文菜单模式切换 |
| **EPANET / SWMM** | 管网可视化预览、图例与色阶映射 |

### 3.1 主窗口布局

```
┌─────────────────────────────────────────────────────────────┐
│  菜单栏: 文件 | 编辑 | 视图 | 计算 | 报告 | 帮助               │
├──────────┬──────────────────────────┬───────────────────────┤
│ 工具栏   │ 快速操作: 新建 打开 保存 │ 撤销 重做 │ 计算 ▶ │
├────┬─────┴──────────────────────────┴───────────────────────┤
│ 左 │                                                        │
│ 侧 │              节点画布 (Node Canvas)                     │
│ 节 │         ┌──────┐    ┌──────┐    ┌──────┐              │
│ 点 │   [输入]→│调节池│→┬─→│粗格栅│→┬─→│细格栅│→...          │
│ 库 │         └──────┘ │  └──────┘ │  └──────┘              │
│    │                  │           │                          │
│ ▼  │                  └───────────┘                          │
│ 输 │                                                        │
│ 入 │    (支持鼠标中键平移, 滚轮缩放, 右键框选)               │
│ 节 │                                                        │
│ 点 │  ┌────────────────────┐                                │
│ 调 │  │      小地图        │                                │
│ 节 │  │     (minimap)     │                                │
│ 池 │  └────────────────────┘                                │
│ 粗 ├──────────────────────────┬─────────────────────────────┤
│ 格 │   底部状态栏              │ 右下: 缩放 100% │ 节点数: 9 │
│ 栅 │   就绪 │ 上次计算: 12s    │ 画布: 2345×1678            │
├────┴──────────────────────────┴─────────────────────────────┤
│ 右侧可折叠面板 (Tab 切换)                                    │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ [参数] [结果] [校核] [水质] [概算]                        │ │
│ │─────────────────────────────────────────────────────────│ │
│ │ 当前节点: 辐流式初沉池                                    │ │
│ │                                                         │ │
│ │ 沉淀池座数 n:     [2]  ←──→  范围: 2-4                  │ │
│ │ 表面负荷 q':      [2.0] ←──→  范围: 1.5-3.0 m³/(m²·h)  │ │
│ │ 沉淀时间 T:       [1.5] ←──→  范围: 1.0-2.0 h           │ │
│ │ 污泥含水率 P:     [0.96]←──→  范围: 0.95-0.97           │ │
│ │ ...                                                     │ │
│ │ 去除率调节:                                     │ │
│ │   SS:  [50]% ←──────→        (默认50%)                  │ │
│ │   BOD: [30]% ←──────→        (默认30%)                  │ │
│ │                                                         │ │
│ │ [重置默认值]  [应用]                                      │ │
│ └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 节点编辑器核心交互

#### 3.2.1 节点画布操作

| 操作 | 鼠标/键盘 | 说明 |
|------|----------|------|
| 平移画布 | 鼠标中键拖拽 / Space+左键拖拽 | Blender 风格 |
| 缩放 | Ctrl+滚轮 / 两指捏合 | 范围 10%~400%，步进 10% |
| 聚焦全部 | Home 键 / 双击空白 | 自动适配所有节点到视口 |
| 聚焦选中 | . (句点) 键 | Blender 风格，聚焦到选中节点 |
| 框选 | 右键拖拽 (Blender 风格) 或左键拖拽 | 可配置 |
| 添加节点 | Shift+A 弹出搜索菜单 / 从左侧节点库拖入 | 支持拼音首字母搜索 |
| 删除节点 | Delete / X 键 | 同时删除关联连线 |
| 复制节点 | Ctrl+C → Ctrl+V | 保留参数设置 |
| 复制+粘贴连线 | Ctrl+Shift+V | 粘贴时保留上游连线关系 |
| 框选+移动 | 选中后 G 键 (Grab) / 直接拖拽 | 选中的节点组整体移动 |
| 对齐 | 选中多个节点 → 右键 → 对齐 | 左对齐/右对齐/水平居中/垂直居中/均匀分布 |
| 撤销/重做 | Ctrl+Z / Ctrl+Shift+Z | 全操作历史栈（100步） |

#### 3.2.2 连线系统

```python
# 连线规则
# 1. 同色端口才能连接: 蓝色(水量)↔蓝色, 绿色(水质)↔绿色
# 2. 输出→输入单向连接, 输入端口只接受一条连线
# 3. 连线自动正交路由 (避障, 可手动调整路径点)
# 4. 悬停连线显示流速/浓度预览 tooltip
# 5. 拖动连线端点可断开重连
# 6. Ctrl+点击连线添加路径控制点
```

连线视觉编码:
```
蓝色实线 ────  水量传递 (WaterFlow)
绿色虚线 ----  水质传递 (WaterQuality)
红色闪烁     计算中/错误
灰色         上游未计算 (无数据)
橙色粗线     用户手动选中的连线
```

#### 3.2.3 节点视觉状态

```
┌─────────────────────┐     ┌─────────────────────┐
│ ● 调节池      [干净] │     │ ● CASS       [脏]    │
│ ┌─────────────────┐ │     │ ┌─────────────────┐ │
│ │ ✓ 计算完成       │ │     │ │ ⚠ 参数已修改     │ │
│ │ V=1738 m³       │ │     │ │ 点击"计算"更新   │ │
│ └─────────────────┘ │     │ └─────────────────┘ │
│    ●──── (蓝色正常)   │     │    ●──── (橙色闪烁)   │
└─────────────────────┘     └─────────────────────┘

┌─────────────────────┐     ┌─────────────────────┐
│ ● 沉砂池      [错误] │     │ ● 格栅     [计算中]  │
│ ┌─────────────────┐ │     │ ┌─────────────────┐ │
│ │ ✗ D/h2超限       │ │     │ │ ◌ 45% ...       │ │
│ │ 建议增大D或减小h2 │ │     │ │                 │ │
│ └─────────────────┘ │     │ └─────────────────┘ │
│    ●──── (红色虚线)   │     │    ●──── (蓝色动画)   │
└─────────────────────┘     └─────────────────────┘
```

#### 3.2.4 节点库面板（左侧）

```
┌──────────────────────┐
│ 🔍 搜索节点...        │  ← 输入拼音/中文/英文即时筛选
├──────────────────────┤
│ ▼ 输入/输出           │
│   📥 进水节点         │
│   📤 出水节点         │
│ ▼ 预处理              │
│   🔲 调节池           │
│   🔲 粗格栅           │
│   🔲 细格栅           │
│   🔲 旋流沉砂池       │
│ ▼ 一级处理            │
│   🔵 辐流式初沉池     │
│ ▼ 二级处理            │
│   🟢 CASS反应器       │
│ ▼ 深度处理            │
│   🟡 高密度沉淀池     │
│   🟡 V型滤池          │
│   🟣 紫外消毒池       │
│ ▼ 经济分析            │
│   💰 工程概算         │
├──────────────────────┤
│ ▼ 我的模板            │
│   📁 城市污水标准流程  │
│   📁 工业废水方案A     │
│   📁 上次使用的流程    │
└──────────────────────┘
```

### 3.3 右侧面板（多Tab）

#### 3.3.1 参数面板 Tab

选中节点时显示，包含：
- **滑块+数字输入组合**：每个参数双控（拖动滑块粗调 + 直接键入精确值）
- **范围指示**：滑块两端显示 min/max，滑块颜色从绿(推荐值)渐变到黄(边界值)到红(超限)
- **去除率子面板**：每个污染物独立滑块，旁注"当前进水浓度→预计出水浓度"
- **[重置默认值]** 按钮：恢复该节点的所有默认参数
- **[应用]** 按钮：标记节点为 dirty，等待全局计算

#### 3.3.2 结果面板 Tab

```
选中: CASS反应器 (已完成)
═══════════════════════════
📐 构筑物尺寸
  池数: 4 座
  单池尺寸: 42.0 × 21.0 × 5.5 m
  有效水深: 5.0 m
  总有效容积: 17640 m³

📊 设计校核
  宽高比 B/H: 4.20  ✓ [2,4]  ← 绿色√
  长宽比 L/B: 2.00  ✓ [2,4]
  BOD负荷 Ns: 0.08  ✓ [0.05,0.15]
  污泥龄 θc: 18.2d  ✓ [10,30]
  安全距离: 0.62m   ✓ ≥0.5m

⚙ 运行参数
  曝气量: 3528 kgO2/d
  剩余污泥: 2147 kg/d
  滗水器堰长: 12.5 m

⚠ 警告
  · 充水比偏差 8.2%（接近10%上限）
```

#### 3.3.3 水质变化 Tab

选中整个流程后，显示逐级水质变化的表格+折线图：

```
        进水   调节池  粗格栅  ...  紫外消毒  出水  标准
BOD5   200     200    190    ...   8.5     8.5  ≤10 ✓
COD    400     400    380    ...   42      42   ≤50 ✓
SS     220     220    202    ...   4.8     4.8  ≤10 ✓
NH3-N   35      35     35    ...   3.2     3.2  ≤5  ✓
TN      45      45     45    ...   11      11   ≤15 ✓
TP       5       5      5    ...   0.3     0.3  ≤0.5✓
```

同时在节点画布下方显示堆叠柱状图（每个污染物一个色带，逐级变窄 = 被去除）。

### 3.4 全局功能

#### 3.4.1 快捷键速查表（按 H 键弹出）

| 快捷键 | 功能 | 参考 |
|--------|------|------|
| Shift+A | 添加节点 | Blender |
| Tab | 节点搜索弹出框 | UE Blueprint |
| G | 移动选中节点 | Blender |
| X / Delete | 删除选中 | 通用 |
| Ctrl+C/V | 复制/粘贴 | 通用 |
| Ctrl+Z / Ctrl+Shift+Z | 撤销/重做 | 通用 |
| Home | 聚焦全部 | Blender |
| . | 聚焦选中 | Blender |
| F5 | 全局计算 | - |
| F6 | 仅计算选中节点及下游 | - |
| Ctrl+S | 保存项目 | 通用 |
| Ctrl+E | 导出报告 | - |
| H | 快捷键帮助 | - |
| 1/2/3/4/5 | 切换右侧Tab | - |
| Ctrl+1~5 | 切换预设视口布局 | Blender |

#### 3.4.2 工具栏按钮

```
[📁 新建] [📂 打开] [💾 保存]  │  [↩ 撤销] [↪ 重做]  │  [▶ 计算] [⏹ 停止]
```

- **计算按钮下拉菜单**：全部计算 / 仅计算修改的 / 计算选中及下游
- **计算进度**：底部状态栏显示进度条 "正在计算 CASS反应器 (5/9)... [████████░░] 56%"

#### 3.4.3 暗色/亮色主题

- 参考 VS Code / Blender 主题系统
- 默认暗色（护眼，适合长时间工程设计）
- 可通过菜单 `视图 → 主题` 切换
- 颜色方案存储为 JSON，支持用户自定义

### 3.5 项目文件系统

```python
# 项目文件格式: .ddesign.json (单文件，包含所有设置)
{
    "version": "2.0",
    "metadata": {
        "name": "鹤岗市污水处理厂设计",
        "author": "杨元鑫",
        "created": "2026-05-15T10:30:00",
        "modified": "2026-05-15T14:22:00",
        "description": "基于中期报告的设计方案"
    },
    "nodes": [
        {
            "id": "node-001",
            "type": "input_node",
            "position": {"x": 100, "y": 300},
            "params": {
                "Q_design": 0.57,
                "Q_avg_daily": 34760.7,
                "Kz": 1.4,
                "water_quality": {"BOD5": 200, "COD": 400, ...}
            }
        },
        {
            "id": "node-002", 
            "type": "tiaojiechi",
            "position": {"x": 400, "y": 300},
            "params": {"n": 4, "HRT": 6, ...}
        },
        ...
    ],
    "connections": [
        {"from_node": "node-001", "from_port": "out", 
         "to_node": "node-002", "to_port": "in"}
    ],
    "view_state": {
        "zoom": 1.0,
        "pan_x": 0, "pan_y": 0,
        "theme": "dark"
    }
}
```

**项目功能**：
- **自动保存**：每 2 分钟 / 每次计算前自动保存到 `.autosave/`
- **最近文件**：文件菜单显示最近 10 个项目
- **项目模板**：预置"城市污水标准流程"等可直接加载的模板
- **版本兼容**：新版本可读取旧版本文件，自动迁移

### 3.6 数据可视化增强

#### 3.6.1 工艺流程图模式

按 Ctrl+Tab 或点击工具栏按钮，画布切换为"只读流程图模式"：
- 节点自动左→右排列（基于拓扑排序）
- 连线显示实际流量值和污染物浓度标注
- 每个节点卡片显示关键结果（池数、尺寸、去除率）
- 适合截图用于报告/答辩展示

#### 3.6.2 水质桑基图

在"水质变化"Tab 中，除了折线图，还可选桑基图（Sankey Diagram）模式：
- 每个污染物一条彩色流带
- 流带经过每个处理单元被"截断"一部分（=被去除）
- 直观展示各单元的去除贡献占比

技术实现：使用 `pyecharts` 或 `matplotlib` 的 Sankey 模块，嵌入 QWebEngineView。

#### 3.6.3 方案对比模式

当用户调整参数产生不同的计算结果时：
- 每个节点可以"固定"（pin）一个计算结果
- 修改参数重新计算后，结果面板并排显示 "当前结果 | 固定结果"
- 差异用 Δ 标注（如 "Δ V = +125 m³", "Δ D = +0.5 m"）
- 可保存多个方案快照，在"方案管理"面板中切换对比

### 3.7 工程概算可视化

在概算 Tab 中：
- **费用构成饼图**：建筑工程费 / 设备购置费 / 安装工程费 / 其他费用
- **构筑物费用柱状图**：X轴=各构筑物，Y轴=费用（万元）
- **管网费用热力图**：在管道平面示意上用颜色表示不同管段的造价密度
- 支持导出高分辨率 PNG/SVG 用于报告

### 3.8 错误处理与用户引导

#### 3.8.1 计算失败时的反馈

```
┌────────────────────────────────────────────────┐
│ ⚠ CASS反应器 计算失败                           │
│                                                │
│ 违反约束: 安全距离不足                          │
│  当前值: H_safe = 0.32 m                       │
│  要求值: H_safe ≥ 0.50 m                       │
│                                                │
│ 💡 建议解决方案 (按优先级):                      │
│  1. 减少充水比 λ (当前 0.30 → 建议 ≤ 0.26)     │
│     [点击应用建议值]                            │
│  2. 降低 MLSS 浓度 X (当前 3500 → 建议 ≤ 3200) │
│     [点击应用建议值]                            │
│  3. 增大有效水深 H_max (当前 5.0 → 建议 ≥ 5.5) │
│     [点击应用建议值]                            │
│                                                │
│ [忽略警告继续]  [自动修复]  [手动调整]          │
└────────────────────────────────────────────────┘
```

#### 3.8.2 新手引导

首次打开软件：
1. 显示欢迎对话框，可选 "加载示例项目" / "新建空白项目" / "打开最近项目"
2. 加载示例后，画布上显示带编号的引导步骤箭头
3. 状态栏常驻 "💡 提示: 按 Shift+A 添加节点, 按 F5 计算全部"

### 3.9 配置文件系统

```ini
# config.ini (增强版)
[general]
language = zh_CN
theme = dark
autosave_interval = 120
undo_history_size = 100
default_project_path = ./projects

[ui]
node_snap_grid = 10           # 节点对齐网格间距(px)
connection_style = orthogonal # orthogonal / straight / curved
show_minimap = true
show_grid = true
default_zoom = 1.0

[calculation]
timeout_per_node = 60         # 单节点计算超时(秒)
parallel_execution = false    # 是否并行计算独立分支
numeric_precision = 4         # 显示小数位数

[export]
excel_engine = openpyxl       # openpyxl / xlsxwriter
chart_dpi = 150               # 导出图表分辨率
default_output_dir = ./output

[paths]
# 定额数据库路径
quota_db = ./data/heilongjiang_quota_2019.json
# Excel输入数据目录
data_dir = ./data
# 日志目录
log_dir = ./logs
```

---

## 4. 数据输入与解析模块

### 4.1 输入文件

| 文件 | 用途 | 格式 |
|------|------|------|
| `pipe_final.xlsx` | 污水管网方案一 | 8列管道数据 + 计算结果sheet |
| `pipe_final2.xlsx` | 污水管网方案二 | 同上 |
| `yushui.xlsx` | 雨水管网方案 | 同上（雨水参数） |
| `chenshachi.xlsx` | 沉砂池输入参数 | D1-D3格式 |
| `chuchenchi.xlsx` | 初沉池输入参数 | 4行×4列 |
| `geshan.xlsx` | 格栅输入参数 | 列格式 |

### 4.2 输入节点设计

UI 中的"输入节点"包含：
- 水量设置：Q_design (m³/s), Q_avg_daily (m³/d), Kz
- 水质设置：BOD5, COD, SS, NH3-N, TN, TP, pH（默认值来自表3-1）
- 进水水质默认值：
  ```
  BOD5=200, COD=400, SS=220, NH3-N=35, TN=45, TP=5, pH=7.0
  ```
- 可选择"从Excel读取"或"手动输入"

---

## 5. 业务逻辑层 - 污水处理厂计算

### 5.1 全局设计参数

```python
# 设计流量（用户强调）
Q_DESIGN = 0.57  # m³/s，最大设计流量
KZ = 1.4         # 总变化系数
Q_AVG_DAILY = 34760.7  # m³/d，平均日流量
Q_AVG_HOURLY = Q_AVG_DAILY / 24  # m³/h
```

---

### 5.2 调节池 (tiaojiechi.py)

#### 5.2.1 输入参数
| 参数 | 符号 | 默认值 | 范围 | 单位 |
|------|------|--------|------|------|
| 调节池个数 | n | 4 | 2-8 | 座 |
| 水力停留时间 | HRT | 6 | 4-12 | h |
| 有效水深 | h_eff | 4 | 3-5 | m |
| 超高 | h_super | 0.5 | 0.3-0.5 | m |
| 长宽比 | ratio_LB | 2 | 1.5-3 | - |
| 搅拌功率密度 | P_density | 12 | 10-15 | W/m³ |

#### 5.2.2 计算公式

```python
# 1) 单池设计流量
Q_per_pool = Q_AVG_HOURLY / n  # m³/h

# 2) 单池有效容积（基本公式）
V_eff = Q_per_pool * HRT  # m³

# 3) 有效水面面积
A_eff = V_eff / h_eff  # m²

# 4) 池体尺寸（按长宽比）
# L / B = ratio_LB, L * B = A_eff
B = sqrt(A_eff / ratio_LB)  # 池宽，m
L = ratio_LB * B            # 池长，m

# 5) 取整：向上取整到 0.5m（便于施工）
B_rounded = ceil(B * 2) / 2
L_rounded = ceil(L * 2) / 2

# 6) 实际有效容积（取整后）
V_actual = L_rounded * B_rounded * h_eff  # m³
HRT_actual = V_actual / Q_per_pool  # h
# 校核: HRT_actual >= HRT (或误差在10%以内)

# 7) 总高度
H_total = h_eff + h_super  # m，向上取整到0.1m

# 8) 搅拌总功率
P_total = P_density * V_actual * n  # W → 向上取整 kW

# 9) 总容积（所有池）
V_total = V_actual * n  # m³
```

#### 5.2.3 约束条件
- `L_rounded / B_rounded ∈ [1.5, 3]`（布水均匀性）
- `HRT_actual ≥ HRT - 0.5h`

#### 5.2.4 输出结果
```
调节池计算结果:
  池数: n 座
  单池尺寸: L × B × H = __ × __ × __ m
  单池有效容积: __ m³
  总容积: __ m³
  实际HRT: __ h
  搅拌总功率: __ kW
```

---

### 5.3 格栅 (geshan.py) [重写]

**注意**：现有 `geshan.py` 已实现完整计算，但基于旧公式。新版本需：
1. 拆分为粗格栅（b=25-40mm）和细格栅（b=16-25mm）两个节点
2. 水头损失公式保持：`h1 = β*(s/b)^(4/3) * v²/(2g) * sin(α) * k`
3. 保留现有迭代寻优逻辑

#### 5.3.1 粗格栅参数

| 参数 | 符号 | 默认值 | 范围 | 单位 |
|------|------|--------|------|------|
| 格栅台数 | n | 3 | 2-4 | 台 |
| 栅条间隙 | b | 30 | 25-40 | mm |
| 格栅倾角 | α | 75 | 60-90 | ° |
| 栅前水深 | h | 0.8 | 0.4-1.0 | m |
| 过栅流速 | v | 0.8 | 0.6-1.0 | m/s |
| 栅前流速 | v1 | 0.7 | 0.4-0.9 | m/s |
| 栅条宽度 | s | 10 | - | mm |
| 栅渣量标准 | W1 | 0.02 | 0.01-0.03 | m³/10³m³ |

#### 5.3.2 计算公式（与现有geshan.py一致+取整要求）

```python
# 单台设计流量
q = Q_DESIGN / n  # m³/s

# 1) 栅条间隙数
sin_alpha = sin(radians(α))
b_m = b / 1000  # mm → m
n_gap = ceil(q * sqrt(sin_alpha) / (b_m * h * v))  # 个，向上取整

# 2) 栅槽宽度
B = s/1000 * (n_gap - 1) + b_m * n_gap + 0.2  # m
B_rounded = ceil(B * 10) / 10  # 向上取整到0.1m

# 3) 进水渠宽
B1 = q / (h * v1)  # m
B1_rounded = ceil(B1 * 10) / 10  # 向上取整到0.1m
# 校核: B1_rounded < B_rounded

# 4) 过栅水头损失
β = 2.42  # 锐边矩形
ξ = β * (s / b) ** (4/3)
h0 = ξ * v² / (2 * 9.81) * sin_alpha
h1 = h0 * 3  # k=3

# 5) 栅后总高
H = h + h1 + 0.3  # m
H_rounded = ceil(H * 10) / 10

# 6) 栅槽总长度
α_rad = radians(α)
L1 = (B_rounded - B1_rounded) / (2 * tan(α_rad))
L2 = L1 / 2
L = L1 + L2 + 1.0 + 0.5 + (0.2 + h) / tan(α_rad)
L_rounded = ceil(L * 10) / 10

# 7) 每日栅渣量
W = Q_DESIGN * 86400 * W1 / (KZ * 1000)  # m³/d

# 8) 清渣方式判断
cleaning = "机械清渣" if W > 0.2 else "人工清渣"
```

#### 5.3.3 细格栅差异
- `b ∈ [16, 25]` mm
- `W1 ∈ [0.05, 0.10]` m³/10³m³
- `α ∈ [60, 90]`°

---

### 5.4 旋流沉砂池 (chenshachi.py) [重写]

**注意**：现有 `chenshachi.py` 实现的是**曝气沉砂池**（平流式），中期报告改为**旋流沉砂池**（钟氏）。需完全重写。

#### 5.4.1 输入参数

| 参数 | 符号 | 默认值 | 范围 | 单位 |
|------|------|--------|------|------|
| 沉砂池座数 | n | 2 | 2-4 | 座 |
| 表面水力负荷 | q_surf | 180 | 150-200 | m³/(m²·h) |
| 水力停留时间 | t | 45 | 30-60 | s |
| 超高 | h1 | 0.3 | 0.3 | m |
| 沉砂量 | X | 30 | - | m³/10⁶m³ |
| 清砂间隔 | T | 2 | 1-3 | d |
| 砂斗壁倾角 | θ | 55 | 55-60 | ° |
| 排沙口直径 | dr | 0.5 | 0.4-0.6 | m |

#### 5.4.2 计算公式

**公式来源对照**：直径公式 (3-21)、有效水深 (3-22)、有效容积 (3-23)、每日沉砂量 (3-24)、砂斗容积 (3-25)、砂斗锥体高度 (3-27)、池总高度 (3-25(II))

```python
# 单池设计流量（总流量/池数）
Q_single = Q_DESIGN / n  # m³/s

# ===== 1) 沉砂池直径 (3-21) =====
# 公式: D = sqrt(4 * Q_max / (π * q_surf))
# Q_max 单位需统一为 m³/h (单位换算: m³/s × 3600 = m³/h)
Q_single_m3h = Q_single * 3600  # m³/s → m³/h
D_theory = sqrt(4 * Q_single_m3h / (pi * q_surf))  # m
D = ceil(D_theory * 10) / 10  # 向上取整到0.1m

# ===== 2) 有效水深 (3-22) =====
# 公式: h2 = q_surf * t / 3600
# q_surf: m³/(m²·h), t: s → 除以3600转为小时
h2 = q_surf * t / 3600  # m
# 校核: D/h2 ∈ [2.5, 5.0] （报告要求）

# ===== 3) 沉砂区有效容积 (3-23) =====
# 公式: V_eff = Q_max * t
V_eff = Q_single * t  # m³
# （Q_single: m³/s, t: s → m³）

# ===== 4) 停留时间校核 =====
t_actual = V_eff / Q_single  # s
# 约束: t_actual ∈ [30, 60] s

# ===== 5) 每日沉砂量 (3-24) =====
# 公式: V_sand_daily = Q_avg * X / 10⁶
# Q_AVG_DAILY: 平均日流量 m³/d
# X: 城市污水沉砂量 = 30 m³/(10⁶ m³ 污水)
V_sand_daily = Q_AVG_DAILY * X / 1e6  # m³/d

# ===== 6) 砂斗容积 (3-25) =====
# 清砂间隔 T=2 d，安全系数 1.5
V_sand_total = V_sand_daily * T  # m³ (清砂间隔内总沉砂量)
V_hopper = V_sand_total * 1.5 / n  # 单池砂斗所需容积 m³

# ===== 7) 砂斗上口直径 (3-26) =====
# d = 0.5 * D (取池径的0.5倍)
d = 0.5 * D  # m

# ===== 8) 砂斗锥体高度 (3-27) =====
# 圆锥段高度: h4 = (d - dr) / (2 * tan(θ))
# θ ≥ 55°（砂斗壁倾角）
h4 = (d - dr) / (2 * tan(radians(θ)))  # m

# ===== 9) 砂斗容积校核 =====
# 圆锥台容积公式: V = π*h/3 * (R² + R*r + r²)
V_cone = pi * h4 / 3 * ((d/2)**2 + (d/2)*(dr/2) + (dr/2)**2)  # m³
# 注意: 公式中 d 为上口直径，需除以2得半径

# 若 V_cone < V_hopper，则需增加圆柱段高度 (3-28)(3-29)
if V_cone < V_hopper:
    h_cyl = (V_hopper - V_cone) / (pi * (d/2)**2)  # 圆柱段高度 m
else:
    h_cyl = 0

# ===== 10) 缓冲层高度 =====
h3 = 0.5  # m（报告取0.5m）

# ===== 11) 池总高度 =====
# H = h1 + h2 + h3 + h4 + h_cyl
H = h1 + h2 + h3 + h4 + h_cyl  # m
H_rounded = ceil(H * 10) / 10  # 向上取整到0.1m

# ===== 12) 进水渠道 =====
v_in = 0.8  # 进水渠设计流速 m/s
A_in = Q_single / v_in  # 进水渠过水断面面积 m²
```

---

### 5.5 辐流式初沉池 (chuchenchi.py) [重写]

**注意**：现有 `chuchenchi.py` 已实现基本计算，但需增强以下内容：
1. 污泥产量计算（基于SS进出水浓度）
2. 出水堰设计
3. 进水中心管设计
4. 刮泥机线速校核
5. **尺寸向上取整**

#### 5.5.1 输入参数

| 参数 | 符号 | 默认值 | 范围 | 单位 |
|------|------|--------|------|------|
| 沉淀池座数 | n | 2 | 2-4 | 座 |
| 表面水力负荷 | q_prime | 2.0 | 1.5-3.0 | m³/(m²·h) |
| 沉淀时间 | T_settle | 1.5 | 1.0-2.0 | h |
| 超高 | h1 | 0.3 | 0.3-0.5 | m |
| 缓冲层高度 | h3 | 0.3 | 0.3-0.5 | m |
| 池底坡度 | i | 0.05 | 0.03-0.08 | - |
| 泥斗上口半径 | R1 | 1.8 | 1.5-2.0 | m |
| 泥斗下口半径 | R2 | 0.8 | 0.6-1.0 | m |
| 泥斗高度 | h5 | 1.5 | 1.2-2.0 | m |
| 污泥含水率 | P_sludge | 0.96 | 0.95-0.97 | - |
| 排泥周期 | T_sludge | 4 | 2-8 | h |
| 设计人口当量 | N | 100000 | - | 人 |
| 进水SS | SS_in | 220 | - | mg/L |
| 出水SS | SS_out | 110 | - | mg/L (去除50%) |
| 中心管流速 | v_center | 0.3 | 0.2-0.5 | m/s |
| 堰负荷限值 | q_weir_max | 2.9 | - | L/(s·m) |

#### 5.5.2 计算公式

**公式来源对照**：
- 沉淀面积 (3-27)、直径 (3-28)、单池面积 (3-29)、实际表面负荷 (3-30)
- 有效水深 (3-31)、实际停留时间 (3-32)
- 干污泥量 (3-33)、湿污泥体积 (3-34)、污泥区总容积 (3-35)、单池容积 (3-36)
- 泥斗高度 (3-37)、泥斗容积 (3-38)、池底坡降 (3-40)(3-41)
- 堰负荷 (3-44)-(3-48)、中心管 (3-50)、反射板 (3-51)、总高度 (3-52)

```python
# 单池设计流量（总流量/池数）
Q_single = Q_DESIGN / n  # m³/s
Q_single_m3h = Q_single * 3600  # m³/h

# ===== (A) 沉淀区 (3-27)(3-28) =====
# 1) 沉淀面积: F = Q_max / q' 
# Q_max: m³/h, q': m³/(m²·h)
F = Q_single_m3h / q_prime  # m²

# 2) 直径: D = sqrt(4F / π)
D_theory = sqrt(4 * F / pi)  # m
D = ceil(D_theory * 2) / 2  # 向上取整到0.5m (大型构筑物)
# 校核：D >= 16 m (最小直径要求)

# 3) 单池实际面积 (3-29)
F_actual = pi * D**2 / 4  # m²

# 4) 实际表面负荷校核 (3-30)
q_prime_actual = Q_single_m3h / F_actual  # m³/(m²·h)
# 校核: q_prime_actual ∈ [1.5, 3.0]

# ===== (B) 有效水深 (3-31)(3-32) =====
# h2 = q'_actual * T（实际表面负荷 × 沉淀时间）
h2 = q_prime_actual * T_settle  # m
# 校核: h2 >= 2.0, D/h2 ∈ [6, 12]

# 实际水力停留时间
T_actual = V_eff / Q_single_m3h  # h (V_eff = F_actual * h2)
# 应与设计值 T_settle 相近

# ===== (C) 污泥计算 (3-33)-(3-36) =====
# 每日干污泥量 (3-33): S_dry = Q_avg * (C_in - C_out)
# Q_avg: m³/d, C: mg/L
# 单位推导: m³/d × mg/L = m³/d × g/m³ = g/d → ÷1000 = kg/d
S_dry = Q_AVG_DAILY * (SS_in - SS_out) / 1000  # kg/d

# 每日湿污泥体积 (3-34): V_wet = S_dry / [(1 - P) * ρ]
# P: 污泥含水率(如0.96), ρ: 湿污泥密度(取1000 kg/m³)
S_wet = S_dry / ((1 - P_sludge) * 1000)  # m³/d

# 污泥区总容积 (3-35): V_total = V_wet * (T_sludge / 24)
# T_sludge: 排泥周期 h
V_sludge_total = S_wet * (T_sludge / 24)  # m³

# 单池所需污泥区容积 (3-36)
V_sludge = V_sludge_total / n  # m³

# ===== (D) 泥斗尺寸 =====
R = D / 2  # 池半径，m

# 中心泥斗容积（倒置圆台）
h5_angle = (R1 - R2) * tan(radians(60))  # 倾角60°
h5_actual = min(h5, h5_angle)  # 使用实际泥斗高度
V1 = pi * h5_actual / 3 * (R1**2 + R1*R2 + R2**2)  # m³

# 池底坡降
h4 = i * (R - R1)  # m
h4_rounded = ceil(h4 * 10) / 10  # 向上取整到0.1m

# 坡降部分容积（截头圆锥体）
V2 = pi * h4_rounded / 3 * (R**2 + R*R1 + R1**2)  # m³

# 总贮存容积
V_total = V1 + V2  # m³
# 校核: V_total >= V_sludge

# ===== (E) 出水堰 =====

# 周边堰长
weir_perimeter = pi * (D - 2*0.5)  # 堰距池壁0.5m

# 堰负荷计算
# 注意单位: Q_single m³/s → L/s = *1000
q_weir = Q_single * 1000 / weir_perimeter  # L/(s·m)
# 校核: q_weir <= 2.9 L/(s·m)

# 若不满足，增设内侧环形堰
if q_weir > 2.9:
    D_inner = D * 0.7  # 内侧堰直径=0.7D
    weir_inner = pi * D_inner
    weir_total = weir_perimeter + weir_inner
    q_weir = Q_single * 1000 / weir_total

# ===== (F) 进水中心管 =====
d_center_theory = sqrt(4 * Q_single / (pi * v_center))  # m
d_center = ceil(d_center_theory * 10) / 10  # m
# 反射板直径
d_reflector = 1.35 * d_center  # m

# ===== (G) 总高度 =====
H = h1 + h2 + h3 + h4_rounded + h5_actual  # m
H_rounded = ceil(H * 10) / 10  # m

# ===== (H) 刮泥机线速 =====
v_peripheral = pi * D * 1 / 60  # m/min (转速1r/h)
# 校核: v_peripheral <= 3 m/min
```

#### 5.5.3 输出结果
- 池径 D (m)、池深 H (m)
- 有效水深 h2 (m)
- 表面负荷 q' (m³/(m²·h))
- 径深比 D/h2
- 堰负荷 (L/(s·m))
- 污泥区容积及校核
- 刮泥机线速 (m/min)

---

### 5.6 CASS反应器 (cass.py) [新增]

这是最复杂的模块。基于中期报告 3.5 节。

#### 5.6.1 设计参数

| 参数 | 符号 | 默认值 | 范围 | 单位 |
|------|------|--------|------|------|
| CASS池个数 | n | 4 | 2-8 | 座 |
| BOD-污泥负荷 | Ns | 0.08 | 0.05-0.15 | kgBOD5/(kgMLSS·d) |
| MLSS | X | 3500 | 2500-4500 | mg/L |
| f (MLVSS/MLSS) | f | 0.75 | 0.7-0.8 | - |
| 污泥龄 | θc | 15 | 10-30 | d |
| 产率系数 | Y | 0.6 | 0.4-0.8 | kgVSS/kgBOD5 |
| 20℃衰减系数 | Kd20 | 0.05 | 0.04-0.075 | d⁻¹ |
| 温度修正系数 | θt | 1.04 | - | - |
| 设计水温 | T_design | 12 | 8-25 | ℃ |
| 工作周期 | Tc | 6 | 4-8 | h |
| 充水比 | λ | 0.3 | 0.2-0.4 | - |
| 最大有效水深 | H_max | 5.0 | 4.0-6.0 | m |
| 超高 | h_super | 0.5 | 0.5 | m |
| 宽高比 min | B_H_min | 1 | 1-2 | - |
| 宽高比 max | B_H_max | 2 | 1-2 | - |
| 长宽比 min | L_B_min | 2 | 2-4 | - |
| 长宽比 max | L_B_max | 4 | 2-4 | - |
| 生物选择区比例 | r_selector | 0.15 | 0.10-0.20 | - |
| SVI | SVI | 120 | 80-150 | mL/g |
| 安全距离 | ΔH_safe | 0.5 | 0.3-0.8 | m |

**周期时间分配** (Tc=6h)：
- 曝气时间 t_a = 3h
- 沉淀时间 t_s = 1h
- 滗水时间 t_d = 1h
- 闲置时间 t_i = 1h

#### 5.6.2 计算公式

**公式来源对照**：
- (3-53) 温度修正衰减系数: KdT = Kd20 × θt^(T-20)
- (3-54) 主反应区容积（BOD-污泥负荷法）: V = Q×(S0-Se)/(Ns×X×f)
- (3-55) 单池容积、(3-56) 选择区容积、(3-57) 总有效容积
- (3-58)-(3-60) 平面尺寸与长宽比
- (3-61)(3-62) 滗水高度与充水比校核
- (3-63)-(3-65) 泥面高度与安全距离
- (3-66) 池体总高度
- (3-67)-(3-69) 剩余污泥量（生物+非生物）
- (3-70) 污泥龄校核
- (3-71)-(3-74) 需氧量（碳化+硝化-反硝化）
- (3-75)(3-76) 滗水器设计

```python
# ===== 单位换算 =====
X_kg = X / 1000  # mg/L → kg/m³
Q_avg = Q_AVG_DAILY  # m³/d

# 进水/出水 BOD5 (来自上游节点)
BOD5_in = inlet.BOD5   # mg/L → 需要转 kg/m³ = mg/L / 1000
BOD5_out = 20          # mg/L (一级A标准)

# ===== (1) 温度修正衰减系数 =====
KdT = Kd20 * (θt ** (T_design - 20))  # d⁻¹

# ===== (2) 主反应区有效容积（BOD-污泥负荷法）=====
# V_main = Q_avg * (S0 - Se) / (Ns * X * f)
# 注意单位统一：
# Q_avg: m³/d
# S0, Se: kg/m³ (BOD5浓度，除以1000从mg/L转换)
# Ns: kgBOD5/(kgMLSS·d)
# X: kg/m³
# f: 无量纲

S0_kg = BOD5_in / 1000   # mg/L → kg/m³
Se_kg = BOD5_out / 1000  # mg/L → kg/m³

V_main = Q_avg * (S0_kg - Se_kg) / (Ns * X_kg * f)  # m³

# ===== (3) 单池主反应区容积 =====
V_main_single = V_main / n  # m³

# ===== (4) 生物选择区容积 =====
V_selector_single = V_main_single * r_selector  # m³

# ===== (5) 单池总有效容积 =====
V_eff_single = V_main_single + V_selector_single  # m³

# ===== (6) 平面尺寸 =====
A_single = V_eff_single / H_max  # m²

# 设池宽 B（需同时满足宽高比和长宽比）
# B/H_max ∈ [B_H_min, B_H_max]
# 取中间值试算
B_try = H_max * 1.5  # 取宽高比1.5
B = ceil(B_try)  # 向上取整到整数米

L_try = A_single / B  # m
L = ceil(L_try)

# 校核长宽比
ratio_LB = L / B
assert B_H_min <= B / H_max <= B_H_max, f"宽高比不满足: {B/H_max}"
assert L_B_min <= ratio_LB <= L_B_max, f"长宽比不满足: {ratio_LB}"

# 实际面积和容积
A_actual = L * B  # m²
V_eff_actual = A_actual * H_max  # m³

# ===== (7) 滗水高度与容积校核 =====
# 滗水高度 (3-61): H_decant = H_max * λ
H_decant = H_max * λ  # m

# 充水比校核 (3-62): λ = Q_avg * Tc / (24 * n * V_eff)
# 此式用于验证有效容积与周期/充水比是否匹配
λ_check = Q_avg * Tc / (24 * n * V_eff_actual)
# 若 |λ_check - λ| / λ > 0.1，需调整 V_eff_actual 或 Tc

# ===== (8) 滗水结束时泥面高度校核 (3-63) =====
# H_sludge = H_max * X * SVI / 10⁶
# X: mg/L (如3500), SVI: mL/g (如120)
# 公式推导: 污泥沉降体积 = MLSS浓度 × SVI × 体积
#           H_sludge/H_max = X(mg/L) * SVI(mL/g) / 10⁶
#           因为 1 mg/L × 1 mL/g = 1×10⁻⁶ (单位自洽)
H_sludge = H_max * X * SVI / 1e6  # m

# 安全距离 (3-64)(3-65): ΔH = H_max - H_decant - H_sludge
H_safe_actual = H_max - H_decant - H_sludge  # m
assert H_safe_actual >= ΔH_safe, f"安全距离不足: {H_safe_actual:.2f} < {ΔH_safe}"

# ===== (9) 池体总高度 =====
H_total = H_max + h_super  # m

# ===== (10) 剩余污泥量 =====
# ① 剩余生物污泥量（以VSS计）
Px_bio = Y * Q_avg * (S0_kg - Se_kg) - KdT * V_main * X_kg * f  # kgVSS/d

# ② 剩余非生物污泥量
# 取进水VSS中可生化系数 f_b = 0.6
f_b = 0.6
Px_nbio = Q_avg * (SS_in/1000 * (1 - f_b) - SS_out/1000)  # kgSS/d

# ③ 剩余污泥总量
Px_total = Px_bio + Px_nbio  # kg/d

# ===== (11) 污泥龄校核 =====
θc_actual = V_main * X_kg / Px_total  # d
# 校核: θc_actual >= θc

# ===== (12) 需氧量 (3-71)-(3-74) =====
# ① 碳化需氧量 (3-71): O2_C = a' * Q * (S0 - Se) + b' * V * X * f
# a'=0.5 kgO2/kgBOD5, b'=0.12 kgO2/(kgMLVSS·d)
# Q: m³/d, S0,Se: kg/m³, V: m³, X: kg/m³
# → 第一项: kgO2/d, 第二项: kgO2/d
O2_carbon = (a_prime * Q_avg * (S0_kg - Se_kg) 
             + b_prime * V_main * X_kg * f)  # kgO2/d

# ② 硝化需氧量 (3-72): O2_N = 4.57 * [Q*(N_in-N_out) - 0.124*Px_bio]
# 4.57: kgO2/kgNH3-N (硝化耗氧系数)
# 扣除细胞合成所用氨氮: N_synth ≈ 0.124 × Px_bio (kgN/d)
# 简化: 若不扣除细胞合成，偏于安全
N_synth = 0.124 * Px_bio  # 细胞合成消耗的氮 kgN/d
NH3_load = Q_avg * (NH3_in - NH3_out) / 1000  # kgN/d (Q m³/d, NH3 mg/L)
O2_nitrification = 4.57 * max(0, NH3_load - N_synth)  # kgO2/d

# ③ 反硝化产氧量 (3-73): O2_DN = 2.86 * Q * (TN_in - TN_out - N_synth)
# 2.86: kgO2/kgNO3-N (每kg硝态氮反硝化回收的氧量)
TN_load = Q_avg * (TN_in - TN_out) / 1000  # kgN/d
O2_denitrification = 2.86 * max(0, TN_load - N_synth)  # kgO2/d

# ④ 总需氧量 (3-74): O2_total = O2_C + O2_N - O2_DN
O2_total = O2_carbon + O2_nitrification - O2_denitrification  # kgO2/d
# 注意: 反硝化是回收氧，所以减去

# ===== (13) 滗水器 =====
# 单池滗水流量
Q_decant = V_eff_single * λ / t_d  # m³/h

# 堰口负荷 (旋转式滗水器 ≤ 30 L/(s·m))
q_weir_limit = 30  # L/(s·m)
Q_decant_Ls = Q_decant * 1000 / 3600  # L/s
L_weir_min = Q_decant_Ls / q_weir_limit  # m
```

#### 5.6.3 约束条件汇总
| 约束 | 公式 | 条件 |
|------|------|------|
| 宽高比 | B / H_max | ∈ [1, 2] |
| 长宽比 | L / B | ∈ [2, 4] |
| 充水比一致性 | λ ≈ Q_avg*Tc/(24*n*V_eff) | 偏差 < 10% |
| 安全距离 | H_max - H_decant - H_sludge | ≥ 0.5m |
| 污泥龄 | θc_actual | ≥ 设计θc |
| 堰口负荷 | Q_decant / L_weir | ≤ 30 L/(s·m) |

---

### 5.7 高密度沉淀池 (gaomidu.py) [新增]

#### 5.7.1 设计参数

| 参数 | 符号 | 默认值 | 范围 | 单位 |
|------|------|--------|------|------|
| 沉淀池座数 | n | 4 | 2-6 | 座 |
| 混合时间 | t_mix | 1 | 0.5-2 | min |
| 絮凝时间 | t_floc | 10 | 8-15 | min |
| 污泥回流比 | R_sludge | 0.05 | 0.03-0.10 | - |
| 斜管区表面负荷 | q_surf | 8 | 6-12 | m³/(m²·h) |
| 斜管长度 | L_tube | 1.0 | 0.8-1.5 | m |
| 斜管倾角 | α_tube | 60 | 55-65 | ° |
| 清水区高度 | h_clear | 1.0 | 0.8-1.5 | m |
| 配水区高度 | h_dist | 1.5 | 1.0-2.0 | m |
| 超高 | h_super | 0.5 | 0.3-0.5 | m |
| 污泥浓缩时间 | t_thicken | 8 | 4-12 | h |
| 浓缩污泥含水率 | P_out | 0.96 | 0.95-0.98 | - |
| PAC投加量 | D_PAC | 20 | 15-30 | mg/L |
| PAC产泥系数 | k_PAC | 0.5 | 0.4-0.6 | kgDS/kgPAC |

#### 5.7.2 计算公式

```python
# 单池设计流量
Q_single = Q_DESIGN / n  # m³/s
Q_single_m3h = Q_single * 3600  # m³/h

# ===== (A) 快速混合区 =====
V_mix = Q_single * t_mix * 60  # m³ (Q_single: m³/s, t_mix: min→s=*60)

# ===== (B) 絮凝区 =====
Q_sludge_return = Q_single * R_sludge  # 回流污泥量 m³/s
Q_floc_total = Q_single + Q_sludge_return  # 进入絮凝区总流量 m³/s
V_floc = Q_floc_total * t_floc * 60  # m³

# ===== (C) 斜管沉淀区 =====
A_settle = Q_single_m3h / q_surf  # 沉淀区面积 m²

# 检查斜管内轴向流速
# v_axial = q_surf / (3600 * sin(α))
v_axial = q_surf / (3600 * sin(radians(α_tube)))  # m/s
# 应 < 0.005 m/s (5 mm/s)

# ===== (D) 池体尺寸 =====
# 总沉淀区面积 = A_settle
# 设长宽比 LB_ratio ≈ 1.5
LB_ratio = 1.5
B_pool = sqrt(A_settle / LB_ratio)  # m
L_pool = LB_ratio * B_pool  # m
# 向上取整到0.5m
B_pool = ceil(B_pool * 2) / 2
L_pool = ceil(L_pool * 2) / 2
A_actual = L_pool * B_pool

# ===== (E) 污泥产量 =====
# SS去除干污泥
SS_removed = SS_in - SS_out  # mg/L (来自上游节点)
S_dry_SS = Q_AVG_DAILY * SS_removed / 1000  # kg/d

# 化学污泥 (PAC)
S_dry_chem = Q_AVG_DAILY * (D_PAC/1000) * k_PAC  # kg/d
# D_PAC: mg/L → kg/m³ = /1000

# 总干泥
S_dry_total = S_dry_SS + S_dry_chem  # kg/d

# 湿污泥体积 (进入浓缩区含水率99.5%)
P_in = 0.95  # 进浓缩区污泥含水率
V_sludge_wet = S_dry_total / ((1 - P_in) * 1000)  # m³/d

# ===== (F) 污泥浓缩区 =====
# 浓缩区容积
V_thicken = V_sludge_wet * t_thicken / 24  # m³

# 浓缩区高度
h_thicken = V_thicken / A_actual  # m
# 最小高度 0.5m

# 固体通量校核
solid_flux = S_dry_total / A_actual  # kgDS/(m²·d)
# 应 ≤ 150 kgDS/(m²·d) (一般限值)

# ===== (G) 总高度 =====
H_total = h_super + h_clear + h_dist + h_thicken  # m
# 斜管区垂直高度 = L_tube * sin(α)
h_tube_vertical = L_tube * sin(radians(α_tube))
H_total += h_tube_vertical
H_total = ceil(H_total * 10) / 10  # m

# ===== (H) 出水堰 =====
# 堰负荷限值 2.9 L/(s·m)
q_weir_actual = Q_single * 1000 / (2 * (L_pool + B_pool))  # L/(s·m)
# 周边出水
```

---

### 5.8 V型滤池 (vxinglvchi.py) [新增]

#### 5.8.1 设计参数

| 参数 | 符号 | 默认值 | 范围 | 单位 |
|------|------|--------|------|------|
| 设计滤速 | v_filter | 6 | 5-8 | m/h |
| 强制滤速 | v_force | 8 | 7-10 | m/h |
| 过滤周期 | T_filter | 24 | 12-36 | h |
| 滤池格数 | n | 4 | 2-6 | 格 |
| 自用水系数 | k_self | 1.05 | 1.03-1.08 | - |
| 滤层厚度 | h_media | 1.2 | 1.0-1.5 | m |
| 滤料有效粒径 | d10 | 0.95 | 0.9-1.35 | mm |
| 滤层上水深 | h_water | 1.2 | 1.0-1.5 | m |
| 超高 | h_super | 0.5 | 0.3-0.5 | m |
| 滤板厚度 | h_plate | 0.1 | - | m |
| 布水区高度 | h_under | 0.9 | 0.8-1.0 | m |

**反冲洗参数：**
| 阶段 | 气冲强度 L/(m²·s) | 水冲强度 L/(m²·s) | 历时 min |
|------|-------------------|-------------------|---------|
| 气冲 | 15 | - | 2 |
| 气水同冲 | 15 | 3 | 4 |
| 水冲 | - | 5 | 5 |
| 表面扫洗 | - | 2.0 | 全程(11 min) |

#### 5.8.2 计算公式

**公式来源对照**：
- (3-95) 设计总流量、(3-96) 有效工作时间
- (3-98) 总过滤面积、(3-99) 单格面积、(3-100) 强制滤速校核
- (3-101) 滤池总高度
- (3-102)-(3-112) 反冲洗系统计算
- (3-113) 滤头布置、(3-114)-(3-122) 进出水系统
- (3-123) 水头损失

```python
# ===== (1) 设计总流量 (3-95) =====
# Q_total = k * Q_design
# k: 自用水系数(1.05)
Q_total = Q_DESIGN * k_self  # m³/s
Q_total_m3h = Q_total * 3600  # m³/h

# ===== (2) 滤池有效工作时间 (3-96) =====
# T_eff = 24 - t_bw * (n_groups / T_filter)
# 每格反冲洗历时 t_bw = 11 min = 0.183 h
# 简化: T_eff = 24 - 0.183 * n_groups / (T_filter/24) 
# 更常用简化: 直接取 T_eff = 23.5 ~ 23.8 h
T_eff = 24  # h（简化，反冲洗水量在自用水系数中考虑）

# ===== (3) 总过滤面积 (3-98) =====
# A_total = Q / v_filter
# Q: m³/h, v_filter: m/h
A_total = Q_total_m3h / v_filter  # m²

# ===== (4) 单格面积 (3-99) =====
A_single = A_total / n  # m²

# ===== (5) 强制滤速校核 (3-100) =====
# 当一格反冲洗停运，其余 n-1 格承担全部流量
v_force_actual = Q_total_m3h / (A_single * (n - 1))  # m/h
assert v_force_actual <= v_force, f"强制滤速超限: {v_force_actual:.1f} > {v_force}"

# ===== (6) 单格尺寸 =====
# 设计规范: 单格宽度 B ≤ 4.5m
B = min(sqrt(A_single / 2), 4.5)  # 取长宽比约2:1
B = ceil(B * 10) / 10  # 向上取整到0.1m
L = ceil(A_single / B * 10) / 10  # m

A_actual = L * B  # m² (实际单格面积)

# ===== (7) 滤池总高度 (3-101) =====
# H = h_super + h_water + h_media + h_plate + h_under
H_total = h_super + h_water + h_media + h_plate + h_under  # m
H_total = ceil(H_total * 10) / 10

# ===== (8) 反冲洗系统 (3-102)-(3-112) =====
# 各阶段流量 = 冲洗强度 × 单格面积
# 气冲阶段: q_air = 15 * A_actual (L/s)
# 气水同冲: 气 15 L/(m²·s)、水 3 L/(m²·s)
# 水冲阶段: 5 L/(m²·s)
# 表面扫洗: 2.0 L/(m²·s)，贯穿全程(11 min)

# 单次反冲洗水总量 (3-107)
# V_bw = (q_ag+air * t_ag+air + q_water * t_water + q_sweep * t_total) / 1000
# 各流量 L/s × 时间 s → L → /1000 = m³
V_bw = (
    3 * A_actual * 4 * 60    # 气水同冲阶段水: 3 L/(m²·s) × 4min
    + 5 * A_actual * 5 * 60  # 水冲阶段: 5 L/(m²·s) × 5min
    + 2.0 * A_actual * 11 * 60  # 表面扫洗: 2 L/(m²·s) × 11min
) / 1000  # m³

# 冲洗水占产水量比例 (3-108)
V_produced_per_cycle = Q_DESIGN * 3600 * T_filter  # m³
ratio_bw = V_bw / V_produced_per_cycle
# 一般应 < 5%，若超限调整冲洗强度或周期

# ===== (9) 滤头布置 (3-113) =====
# N_head = ρ_head * A_actual
N_head = ceil(ρ_head * A_actual)  # 个
# ρ_head: 滤头布置密度 50-60 个/m²
```

---

### 5.9 紫外消毒池 (ziwai.py) [新增]

#### 5.9.1 设计参数

| 参数 | 符号 | 默认值 | 范围 | 单位 |
|------|------|--------|------|------|
| 渠道数 | n | 2 | 1-3 | 条 |
| 紫外剂量 | D_UV | 40 | 30-50 | mJ/cm² |
| 灯管老化系数 | k_aging | 0.7 | 0.6-0.8 | - |
| 结垢系数 | k_foul | 0.8 | 0.7-0.9 | - |
| 综合衰减系数 | k_total | 0.56 | - | - (k_aging×k_foul) |
| 紫外透光率 | T254 | 65 | 55-75 | % |
| 透光率修正指数 | n_T | 2 | 1.5-2.5 | - |
| 几何效率 | η_geo | 0.7 | 0.6-0.8 | - |
| 渠道流速 | v_channel | 0.4 | 0.3-0.5 | m/s |
| 有效水深 | h_channel | 1.0 | 0.8-1.5 | m |
| 超高 | h_super | 0.3 | 0.3-0.5 | m |
| 灯管有效长度 | L_lamp | 1.5 | 1.2-1.8 | m |
| 灯管安装间隙 | gap | 0.1 | 0.05-0.15 | m |
| 灯管垂直层数 | N_layer | 4 | 3-6 | 层 |
| 灯管垂直中心距 | d_vert | 0.2 | 0.15-0.25 | m |
| 灯管纵向中心距 | d_long | 0.15 | 0.1-0.2 | m |
| 单灯UVC功率 | P_lamp | 250 | 200-300 | W |
| 进口过渡段 | L_in | 1.0 | 0.8-1.5 | m |
| 出口过渡段 | L_out | 1.0 | 0.8-1.5 | m |
| 局部阻力系数 | ξ_total | 0.5 | 0.3-0.8 | - |

#### 5.9.2 计算公式

**公式来源对照**：
- (3-124) 综合衰减系数 k = k_aging × k_foul
- (3-125) 透光率修正: T254_eff = (T254/100)^n_T
- (3-126)-(3-130) 渠道几何尺寸与流速校核
- (3-131) 平均紫外光强: I_avg = P_lamp × N_layer × η_geo × T254_eff × k / (h × d_long)
- (3-132)-(3-135) 接触时间与有效剂量
- (3-136)-(3-128) 灯管总数与渠道长度
- (3-129) 水头损失: h_loss = ξ × v² / (2g)
- (3-130) 总高度: H = h + h_super

```python
# 单渠道设计流量 (3-126)
Q_single = Q_DESIGN / n  # m³/s

# ===== 综合衰减系数 (3-124) =====
k_total = k_aging * k_foul  # 无量纲

# ===== 透光率修正 (3-125) =====
T_eff = (T254 / 100) ** n_T  # 无量纲

# ===== 渠道几何尺寸 =====
# 渠宽由灯管有效长度和安装间隙决定 (3-127)
B_channel = L_lamp + 2 * gap  # m

# 有效水深校核 (3-128)
# h >= N_layer * d_vert + h_top_min + h_bottom_min
# h_top_min = 0.1m (灯管上端距水面)，h_bottom_min = 0.1m (灯管下端距池底)
h_channel_max = N_layer * d_vert + 0.1 + 0.1  # 所需最小水深
h_channel = max(h_channel, h_channel_max)  # 取较大值

# 过流断面 (3-129)
A_channel = B_channel * h_channel  # m²

# 实际流速校核 (3-130)
v_actual = Q_single / A_channel  # m/s
# 约束: v_actual ∈ [0.3, 0.5] m/s

# ===== 平均紫外光强 (3-131) =====
# I_avg = P_lamp × N_layer × η_geo × T_eff × k_total / (h × d_long)
# P_lamp: W/支, 系数1000将W转为mW (因为 D_UV 单位是 mJ/cm²)
# I_avg = P_lamp × 1000 × N_layer × η_geo × T_eff × k_total / (h × d_long × 10000)
# (除以10000: cm²转换，h和d_long为m→cm需×100=10000)
I_avg = (P_lamp * N_layer * η_geo * T_eff * k_total) / (h_channel * d_long)  # W/m²

# ===== 有效剂量与灯管排数 (3-132)-(3-135) =====
# 接触时间: t_contact = N_rows * d_long / v (3-132)
# 有效剂量: D_actual = I_avg * t_contact (3-133)
# 联立解得所需排数: N_rows = D_UV * v * h / (P_lamp*N_layer*η_geo*T_eff*k_total) (3-134)
# 简化计算：先用假设排数迭代
N_rows = ceil(D_UV * v_actual * h_channel * 1000 
              / (P_lamp * N_layer * η_geo * T_eff * k_total))  # 向上取整

# 实际接触时间
t_actual = N_rows * d_long / v_actual  # s

# 实际剂量校核 (3-135)
D_actual = I_avg * t_actual * 10  # 转为 mJ/cm² (W/m²×s = J/m² → mJ/cm² = ×0.1?)
# 注意单位: 需要仔细换算
# I_avg (W/m²) = J/(s·m²), t_actual (s) 
# → I_avg × t_actual = J/m²
# 1 J/m² = 0.1 mJ/cm², 所以 D_mJ = I × t × 0.1
D_actual_mJ = I_avg * t_actual * 0.1  # mJ/cm²
assert D_actual_mJ >= D_UV, f"紫外剂量不足: {D_actual_mJ:.1f} < {D_UV}"

# ===== 灯管总数与渠道长度 (3-136)-(3-128) =====
# 灯管总数: N_total = N_rows * N_layer (3-136)
N_lamps = N_rows * N_layer  # 支

# 灯管区长度: L_uv = N_rows * d_long (3-127)
L_uv = N_rows * d_long  # m

# 渠道总长: L_total = L_in + L_uv + L_out (3-128)
L_total = L_in + L_uv + L_out  # m

# ===== 水头损失 (3-129) =====
# h_loss = ξ_total * v² / (2g)
h_loss = ξ_total * v_actual**2 / (2 * 9.81)  # m

# ===== 池体总高度 (3-130) =====
H_total = h_channel + h_super  # m
H_total = ceil(H_total * 10) / 10  # 向上取整到0.1m
```

---

## 6. 工程概算模块

### 6.1 设计依据
- 2019年版《黑龙江省市政工程消耗量定额》(已OCR学习)
- 《建设工程工程量清单计价规范》GB 50500-2013
- 黑龙江省建设工程造价信息

### 6.2 概算组成

#### A. 污水管网概算 (pipe_cost.py)
从 `pipe_final.xlsx` 的"计算结果"sheet读取各管段数据：

```python
# 管沟土方量 (参考定额第一册)
# V_trench = (B_bottom + B_top) / 2 * H_depth * L  # m³
# B_bottom = D_m + 2*0.5  # 管径+工作面
# B_top = B_bottom + 2 * H_depth * slope_ratio

# 管道铺设费用 (参考定额第五册)
# 按管径查对应定额编号 5-xxx
# 费用 = 定额人工×人工单价 + 材料消耗×材料单价 + 机械台班×台班单价

# 检查井费用 (定额第五册第三章)
# 按井类型/规格查定额
```

#### B. 污水处理厂构筑物概算 (plant_cost.py)
基于各模块计算结果（混凝土量、钢筋量、设备等）：

```python
# 土石方 (第一册) = Σ(构筑物体积 × 扩大系数)
# 混凝土 (第六册/定额) = Σ(各部位混凝土量 × 定额子目)
# 钢筋 (第九册) = 混凝土量 × 含钢量系数 (kg/m³)
# 模板 (第十一册) = 混凝土接触面积
# 设备购置 = Σ(设备清单 × 设备单价)
# 安装工程 = 设备费 × 安装费率
```

### 6.3 费用汇总表格式

```
┌──────────────────┬──────────┬──────────┬──────────┐
│   费用名称        │ 建筑工程费│ 设备购置费│ 安装工程费│
├──────────────────┼──────────┼──────────┼──────────┤
│ 一、管网工程      │          │          │          │
│   1. 土石方       │    xxx   │    -     │    -     │
│   2. 管道铺设     │    xxx   │   xxx    │   xxx    │
│   3. 检查井       │    xxx   │    -     │    -     │
│ 二、污水处理厂    │          │          │          │
│   1. 调节池       │    xxx   │   xxx    │   xxx    │
│   2. 格栅间       │    xxx   │   xxx    │   xxx    │
│   ...             │    ...   │   ...    │   ...    │
├──────────────────┼──────────┼──────────┼──────────┤
│ 三、其他费用      │          │          │          │
│ 四、预备费        │          │          │          │
├──────────────────┼──────────┼──────────┼──────────┤
│ 合计              │    xxx   │   xxx    │   xxx    │
└──────────────────┴──────────┴──────────┴──────────┘
```

---

## 7. 结果输出与报告模块

### 7.1 输出文件清单

| 文件名 | 内容 | 格式 |
|--------|------|------|
| `output/tiaojiechi.xlsx` | 调节池计算结果 | 参数表+尺寸表+校核表 |
| `output/cugeshan.xlsx` | 粗格栅设计方案 | 多方案排序 |
| `output/xigeshan.xlsx` | 细格栅设计方案 | 多方案排序 |
| `output/chenshachi.xlsx` | 旋流沉砂池结果 | 单方案详细表 |
| `output/chuchenchi.xlsx` | 辐流初沉池结果 | 参数+尺寸+校核 |
| `output/cass.xlsx` | CASS反应器结果 | 多sheet详细表 |
| `output/gaomidu.xlsx` | 高密度沉淀池结果 | 参数+尺寸 |
| `output/vxinglvchi.xlsx` | V型滤池结果 | 过滤+反冲洗 |
| `output/ziwai.xlsx` | 紫外消毒池结果 | 消毒+渠道 |
| `output/shuzhi.xlsx` | 各构筑物水质汇总 | 逐级水质变化 |
| `output/gaisuan.xlsx` | 工程概算总表 | 分部分项费用 |
| `output/gaisuan_baogao.xlsx` | 概算报告 | 规范格式表格 |

### 7.2 日志系统
```python
import logging
logger = logging.getLogger('ddesign')
# 异常时自动记录到 logs/error_YYYYMMDD.log
# 计算过程记录到 logs/calc_YYYYMMDD.log
```

---

## 8. 实现路线图

### Phase 1: 基础重构 (Week 1)
- [ ] 创建 `src/models/base.py` 节点基类
- [ ] 创建 `src/models/input_node.py` 输入节点
- [ ] 创建 `src/controller/graph_executor.py` DAG执行引擎
- [ ] 创建 `src/controller/project_manager.py` 项目文件读写
- [ ] 统一数据类 (`WaterFlow`, `WaterQuality`, `NodeResult`, `ParamDef`)
- [ ] 将现有 `legacy/` 模块归档

### Phase 2: 处理单元重写 (Week 2-3)
- [ ] 重写 `tiaojiechi.py` (调节池) - 基于5.2节
- [ ] 重写 `geshan.py` (粗格栅+细格栅) - 基于5.3节
- [ ] 重写 `chenshachi.py` (旋流沉砂池) - 基于5.4节
- [ ] 重写 `chuchenchi.py` (辐流初沉池) - 基于5.5节
- [ ] 新增 `cass.py` (CASS反应器) - 基于5.6节
- [ ] 新增 `gaomidu.py` (高密度沉淀池) - 基于5.7节
- [ ] 新增 `vxinglvchi.py` (V型滤池) - 基于5.8节
- [ ] 新增 `ziwai.py` (紫外消毒池) - 基于5.9节

### Phase 3: UI 核心开发 (Week 3-4)
- [ ] PyQt6 主窗口框架 + 菜单栏 + 工具栏 + 状态栏
- [ ] 节点编辑器画布 (QGraphicsScene + QGraphicsView)
  - [ ] 平移/缩放/框选/对齐
  - [ ] 网格吸附 + 小地图
- [ ] 节点控件（输入节点+9个处理单元+出水节点）
  - [ ] 4种视觉状态（干净/脏/错误/计算中）
- [ ] 连线与端口系统
  - [ ] 拖拽连线 + 颜色编码
  - [ ] 正交自动路由
- [ ] 左侧节点库面板（树形可折叠 + 搜索筛选）
- [ ] 右侧多Tab面板
  - [ ] 参数面板（滑块+数字双控 + 去除率面板）
  - [ ] 结果面板（尺寸/校核/警告分类显示）
  - [ ] 水质面板（表格 + 折线图）
- [ ] Tab键搜索弹出框
- [ ] 快捷键系统 (Shift+A/G/Delete/F5/Home/.等)
- [ ] 暗色/亮色主题

### Phase 4: UI 增强与可视化 (Week 4)
- [ ] 项目文件系统 (.ddesign.json 读写)
  - [ ] 自动保存 + 最近文件
  - [ ] 项目模板（城市污水标准流程等）
- [ ] 撤销/重做系统 (QUndoStack, 100步)
- [ ] 新手引导对话框 + 状态栏提示
- [ ] 水质桑基图 (pyecharts → QWebEngineView)
- [ ] 方案对比模式（pin固定 + Δ差异显示 + 快照管理）
- [ ] 工艺流程图导出（用于报告截图）
- [ ] 错误诊断面板（计算失败时自动给出修改建议）
- [ ] 欢迎页 + 最近项目列表

### Phase 5: 工程概算 (Week 5)
- [ ] 定额数据库 JSON 化
- [ ] 管网概算 (基于 pipe_final 计算结果)
- [ ] 构筑物概算 (基于各模块输出尺寸)
- [ ] 概算可视化面板（费用饼图 + 柱状图）
- [ ] 生成规范格式概算报告 Excel

### Phase 6: 集成测试与收尾 (Week 5-6)
- [ ] 端到端集成测试
- [ ] UI 交互测试
- [ ] 案例验证（用中期报告手动计算结果校验）
- [ ] 编写用户文档 + 内嵌帮助
- [ ] 代码注释与 docstring 补全
- [ ] 打包发布 (PyInstaller)

---

## 9. 附录：单位换算速查表

### 9.1 流量
| 从 | 到 | 乘以 |
|----|----|------|
| m³/s | L/s | 1000 |
| m³/s | m³/h | 3600 |
| m³/s | m³/d | 86400 |
| L/s | m³/h | 3.6 |
| L/s | m³/d | 86.4 |
| m³/d | m³/h | 1/24 |
| m³/d | L/s | 1/86.4 |

### 9.2 浓度
| 从 | 到 | 乘以 |
|----|----|------|
| mg/L | kg/m³ | 1/1000 |
| kg/m³ | mg/L | 1000 |
| mg/L | g/m³ | 1 |

### 9.3 面积
| 从 | 到 | 乘以 |
|----|----|------|
| m² | ha | 1/10000 |
| ha | m² | 10000 |

### 9.4 角度
| 从 | 到 | 公式 |
|----|----|------|
| ° | rad | ×π/180 |
| rad | ° | ×180/π |

### 9.5 关键常量
```python
g = 9.81       # 重力加速度，m/s²
pi = 3.14159   # 圆周率
ρ_water = 1000 # 水密度，kg/m³
ρ_wet_sludge = 1000  # 湿污泥密度，kg/m³
```

---

> **文档版本**: v1.1 (已与中期报告公式逐条核对)  
> **编写日期**: 2026-05-14  
> **基于**: 毕设中期答辩.docx (2026.03.20) + 现有代码 + 2019黑龙江市政定额 (OCR)

---

## 10. 附录B：公式索引对照表

| 中期报告编号 | 公式描述 | 实现位置 |
|------------|---------|---------|
| (3-1) | 调节池设计流量 Q_single = Q_avg/n | §5.2.2 |
| (3-2) | 调节池容积 V = Q × HRT | §5.2.2 |
| (3-3)-(3-6) | 水量累积曲线法（可选，不强制实现） | - |
| (3-7) | 水质均化池容积（经验法，可选） | - |
| (3-8) | 按处理规模比例估算（可选） | - |
| (3-9) | 有效面积 A = V / h | §5.2.2 |
| (3-10) | 总高度 H = h_eff + h_super | §5.2.2 |
| (3-11) | 搅拌功率 P = P_density × V | §5.2.2 |
| (3-12) | 栅条间隙数 n = q×√(sinα) / (b×h×v) | §5.3.2 |
| (3-13) | 栅槽宽度 B = s(n-1) + bn + 0.2 | §5.3.2 |
| (3-14)-(3-15) | 过栅水头损失 h1 = β(s/b)^(4/3)×v²/(2g)×sinα×k | §5.3.2 |
| (3-16) | 栅后总高 H = h + h1 + 0.3 | §5.3.2 |
| (3-17)-(3-19) | 栅槽总长度 | §5.3.2 |
| (3-20) | 每日栅渣量 W = Q×86400×W1/(Kz×1000) | §5.3.2 |
| (3-21) | 沉砂池直径 D = √(4Q/(πq)) | §5.4.2 |
| (3-22) | 有效水深 h2 = q × t / 3600 | §5.4.2 |
| (3-23) | 有效容积 V = Q × t | §5.4.2 |
| (3-24) | 每日沉砂量 V = Q_avg × X / 10⁶ | §5.4.2 |
| (3-25) | 砂斗容积 V_hopper = V × 1.5 / n | §5.4.2 |
| (3-26) | 砂斗上口径 d = 0.5D | §5.4.2 |
| (3-27) | 砂斗锥体高度 h4 = (d-dr)/(2tanθ) | §5.4.2 |
| (3-28)-(3-29) | 砂斗圆柱段高度 | §5.4.2 |
| (3-25 II) | 池总高度 H = h1+h2+h3+h4+h_cyl | §5.4.2 |
| (3-27) | 沉淀面积 F = Q/q' | §5.5.2 |
| (3-28) | 池径 D = √(4F/π) | §5.5.2 |
| (3-31) | 有效水深 h2 = q' × T | §5.5.2 |
| (3-33) | 干污泥量 S_dry = Q_avg×(C_in-C_out) | §5.5.2 |
| (3-34) | 湿污泥体积 V_wet = S_dry/[(1-P)×ρ] | §5.5.2 |
| (3-35)-(3-36) | 污泥区容积 | §5.5.2 |
| (3-37)-(3-38) | 泥斗尺寸 | §5.5.2 |
| (3-40)-(3-41) | 池底坡降 | §5.5.2 |
| (3-44)-(3-48) | 出水堰设计 | §5.5.2 |
| (3-50)-(3-51) | 中心管/反射板 | §5.5.2 |
| (3-52) | 池总高 H = h1+h2+h3+h4+h5 | §5.5.2 |
| (3-53) | 温度修正 KdT = Kd20 × θt^(T-20) | §5.6.2 |
| (3-54) | 主反应区容积 V = Q(S0-Se)/(Ns×X×f) | §5.6.2 |
| (3-61) | 滗水高度 H_decant = H_max × λ | §5.6.2 |
| (3-62) | 充水比校核 λ = Q×Tc/(24×n×V) | §5.6.2 |
| (3-63) | 泥面高度 H_sludge = H_max×X×SVI/10⁶ | §5.6.2 |
| (3-64)-(3-65) | 安全距离校核 | §5.6.2 |
| (3-67) | 剩余生物污泥 Px = YQ(S0-Se)-Kd×V×X×f | §5.6.2 |
| (3-68)-(3-69) | 剩余非生物污泥+总量 | §5.6.2 |
| (3-70) | 污泥龄校核 θc = V×X/Px | §5.6.2 |
| (3-71) | 碳化需氧量 O2 = a'Q(S0-Se)+b'VXf | §5.6.2 |
| (3-72) | 硝化需氧量 O2 = 4.57[Q(N_in-N_out)-N_synth] | §5.6.2 |
| (3-73) | 反硝化产氧 O2 = 2.86[Q(TN_in-TN_out)-N_synth] | §5.6.2 |
| (3-74) | 总需氧量 O2_total = O2_C+O2_N-O2_DN | §5.6.2 |
| (3-75)-(3-76) | 滗水器设计 | §5.6.2 |
| (3-77)-(3-78) | 快速混合区 | §5.7.2 |
| (3-79)-(3-82) | 絮凝区（含污泥回流） | §5.7.2 |
| (3-83)-(3-84) | 斜管沉淀区 | §5.7.2 |
| (3-85)-(3-88) | 污泥产量（SS+化学） | §5.7.2 |
| (3-89)-(3-92) | 污泥浓缩区 | §5.7.2 |
| (3-93)-(3-94) | 池总高+堰负荷 | §5.7.2 |
| (3-95)-(3-96) | 滤池设计总流量+有效工作时间 | §5.8.2 |
| (3-98) | 总过滤面积 A = Q/v | §5.8.2 |
| (3-100) | 强制滤速校核 v_force = Q/[(n-1)×A_single] | §5.8.2 |
| (3-101) | 滤池总高 | §5.8.2 |
| (3-102)-(3-112) | 反冲洗系统（气/水冲） | §5.8.2 |
| (3-113) | 滤头布置 N = ρ × A | §5.8.2 |
| (3-123) | 过滤水头损失 | §5.8.2 |
| (3-124) | 紫外综合衰减系数 k = k_aging × k_foul | §5.9.2 |
| (3-125) | 透光率修正 T_eff = (T254/100)^n | §5.9.2 |
| (3-126)-(3-130) | 渠宽、水深、流速校核 | §5.9.2 |
| (3-131) | 平均光强 I_avg | §5.9.2 |
| (3-132)-(3-135) | 接触时间+有效剂量+排数 | §5.9.2 |
| (3-136)-(3-128) | 灯管总数+渠道长度 | §5.9.2 |
| (3-129) | 水头损失 h = ξ×v²/(2g) | §5.9.2 |
| (3-130) | 总高度 H = h + h_super | §5.9.2 |
