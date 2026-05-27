# UI 配置技术审查报告

## 一、发现的问题及修正建议

### 🔴 P0 — 必须修正（会导致实现失败或不可用）

#### 1. 依赖过重: pyecharts + QWebEngineView → 改为 matplotlib 嵌入
**问题**: 计划使用 pyecharts+QWebEngineView 做图表。
- `PyQtWebEngine` 体积 ~60MB，安装复杂
- pyecharts 渲染 HTML→嵌入 WebView，链路脆弱
- 这两个都不是 requirements.txt 的已有依赖

**修正**: 使用 `matplotlib` + `FigureCanvasQTAgg` 嵌入 Qt
```python
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
# matplotlib 已在项目依赖中（通过 pandas/numpy）
```
桑基图可用 `matplotlib.sankey` 模块（内置）。

#### 2. 正交自动路由过于复杂 → 分阶段实现
**问题**: "连线自动正交路由(避障)" 需要 A* 寻路 + 碰撞检测，独立工作量约 2-3 天。

**修正**: 
- Phase 1: 贝塞尔曲线（起点→控制点→终点），Qt 内置 `QPainterPath::cubicTo`
- Phase 2: 手动添加路径控制点
- Phase 3(可选): 自动正交路由

#### 3. 节点编辑器从零实现 → 需要明确设计模式
**问题**: QGraphicsScene 节点编辑器看似简单，实际需要处理大量细节:
- Item 的 z-order 管理
- 连线端点跟随节点移动
- 框选时排除连线
- 端口拖拽时的视觉反馈
- 嵌套 item 的事件透传

**修正**: 采用成熟的设计模式（参考 Qt 官方 Diagram Scene Example + ryven 项目）:
```python
# 三层 item 架构:
QGraphicsScene
 ├── QGraphicsItem (Connection)  # z=0 底层
 ├── NodeWidget (QGraphicsProxyWidget)  # z=1 中层
 └── PortItem (QGraphicsEllipseItem)   # z=2 顶层（可点击）
```

### 🟡 P1 — 建议修正（提升健壮性）

#### 4. G 键移动与文本输入冲突
**问题**: Blender 风格 G 键在节点画布获取焦点时有效，但参数面板输入框获取焦点时应禁用。

**修正**: 仅在 `node_canvas` 获得焦点时启用 G 键；参数面板编辑时 G 为普通字符。

#### 5. 100 步撤销历史过深
**问题**: 每个 undo 步骤需序列化全场景状态，100 步对复杂流程可能占 ~10-20MB 内存。

**修正**: 默认 50 步，可在 config.ini 配置。或用增量快照（只存变化部分）。

#### 6. 项目文件缺少计算结果缓存
**问题**: 重新打开项目需要全部重算，对于 CASS 等迭代计算较慢。

**修正**: `.ddesign.json` 增加可选的 `cached_results` 字段:
```json
{
    "nodes": [...],
    "cached_results": {
        "node-003": {"dimensions": {...}, "checks": {...}},
        ...
    },
    "cache_timestamp": "2026-05-15T14:22:00"
}
```
打开时若上游节点参数未变，直接使用缓存。

#### 7. 计算线程模型缺失
**问题**: 计划未说明 UI 线程与计算线程的分离。若在主线程计算，UI 会冻结。

**修正**: 使用 `QThread` + 信号槽:
```python
class CalculateWorker(QThread):
    progress = Signal(int, str)  # 进度%, 当前节点名
    finished = Signal(dict)       # 结果
    error = Signal(str, str)      # 节点ID, 错误信息
```

### 🟢 P2 — 优化建议（锦上添花）

#### 8. 缩放步进应平滑
**问题**: 计划写"步进 10%"，实际实现中 Ctrl+滚轮应为平滑缩放（3-5% 步进）。

#### 9. 节点库搜索应支持中英文混合
当前已写"拼音首字母搜索"，但应同时支持: 中文全称、拼音全拼、英文、首字母缩写。

#### 10. 未提及单元测试
UI 组件（节点控件、连线、DAG 执行器）应优先写单元测试，避免回归。推荐 `pytest-qt`。

---

## 二、遗漏项补充

| 遗漏功能 | 重要性 | 补充位置 |
|---------|--------|---------|
| Excel 数据加载到输入节点 | P0 | §4 数据输入模块需与 UI 输入节点对接 |
| 配置文件 config.ini 读取 | P1 | 需在启动时加载，各模块引用 |
| 日志系统对接 UI | P1 | 状态栏可显示最近一条日志 |
| 节点端口类型检查 | P0 | 端口需标记类型(WATER/QUALITY)，不同类型禁止连线 |
| 多选节点批量修改参数 | P2 | 选中多节点时参数面板显示共同参数 |
| 管道计算模块的 UI 入口 | P1 | 需一个"管网计算"菜单项或按钮 |

---

## 三、修正后的技术栈

| 需求 | 原方案 | 修正方案 | 理由 |
|------|--------|---------|------|
| 图表渲染 | pyecharts + QWebEngineView | matplotlib + FigureCanvasQTAgg | 零额外依赖，Qt 原生嵌入 |
| 桑基图 | pyecharts Sankey | matplotlib.sankey | 内置模块，够用 |
| 连线样式 | 正交自动路由 | 贝塞尔曲线 + 手动控制点 | 分阶段实现 |
| 撤销深度 | 100 步 | 50 步(可配) | 内存可控 |
| 图表导出 | PNG/SVG | matplotlib 原生 savefig | 直接支持 |

---

## 四、评审结论

计划整体架构合理，核心交互设计参考了多个成熟产品。上述问题修正后即可进入实现阶段。
**评审结果: 通过 (附修正建议)**
