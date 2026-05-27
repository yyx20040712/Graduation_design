# 代码库全面学习 — 2026-05-16

> 完整通读 27 个源文件 + 所有历史学习记录后的综合笔记

---

## 一、项目全景

| 维度 | 数据 |
|------|------|
| 名称 | 排水工程设计工具 v3 |
| 入口 | `ddesign_tool/main.py` → `MainWindow.run()` |
| 启动 | `run.bat` (自动查找 Python) |
| GUI | tkinter (1500x850 暗色主题) |
| 总代码量 | ~5,800 行 (27 源文件) |
| 最大文件 | main_window.py (~970+ lines) |
| 最复杂模块 | cass.py (305 lines, 向量化 9216 组合) |
| Python | 3.10+ |

---

## 二、架构总览 (MVC + DAG)

```
                          ┌──────────────────────────┐
                          │     ui/main_window.py     │ ← 主控制器 (tk.Tk)
                          │  NODE_REGISTRY, FORMULAS  │
                          │  文件管理, 模式切换, 计算  │
                          └──────┬──────────┬────────┘
                                 │          │
                    ┌────────────┘          └────────────┐
                    ▼                                    ▼
    ┌──────────────────────────┐      ┌──────────────────────────┐
    │   ui/canvas_view.py      │      │ controller/               │
    │   NodeCanvas + NodeItem  │      │   graph_executor.py       │
    │   + PortItem (Blender风) │      │   project_manager.py      │
    │   贝塞尔连线+缩放平移     │      │                          │
    └──────────────────────────┘      └──────────┬───────────────┘
                                                 │
                    ┌────────────────────────────┘
                    ▼
    ┌──────────────────────────────────────────────────────────┐
    │                    models/ (业务层)                       │
    │  base.py → NodeBase (抽象基类)                           │
    │  ├── input_node.py (旧版, 逐步废弃)                      │
    │  ├── pipe_network.py (管网 Excel 输入, WATER 端口)       │
    │  ├── water_quality_node.py (水质输入, QUALITY 端口)      │
    │  ├── combiner.py (合并 WATER+QUALITY→MIXED)              │
    │  ├── tiaojiechi.py (调节池)                              │
    │  ├── geshan.py → CoarseBarScreenNode + FineBarScreenNode │
    │  ├── chenshachi.py (旋流沉砂池 钟氏)                     │
    │  ├── chuchenchi.py (辐流式初沉池)                        │
    │  ├── cass.py ★ (CASS反应器, 最复杂)                      │
    │  ├── gaomidu.py (高密度沉淀池)                           │
    │  ├── vxinglvchi.py (V型滤池 含反冲洗)                    │
    │  ├── ziwai.py (紫外消毒池 剂量迭代)                      │
    │  ├── discretization.py (参数离散化配置)                   │
    │  ├── solution_space.py (方案空间枚举引擎)                 │
    │  ├── cost/ (工程概算)                                     │
    │  │   ├── unit_prices.py (单价数据库)                      │
    │  │   ├── cost_estimator.py (BOQ 引擎)                     │
    │  │   ├── report_writer.py (Excel 报告)                    │
    │  │   └── pipe_network_cost.py (管网概算)                  │
    │  └── 矿井水模块:                                          │
    │      ├── kw_input.py, kw_tiaojiechi.py                   │
    │      ├── kw_chenshachi.py, kw_ningjiao.py, kw_cifenli.py │
    ├── visualization/ (图表层, matplotlib)                     │
    └── ui/solution_browser.py (方案浏览器 UI)                  │
```

---

## 三、核心数据流

### 3.1 端口体系
```
PortType.WATER   → 蓝色 — 仅 WaterFlow
PortType.QUALITY → 绿色 — 仅 WaterQuality
PortType.MIXED   → 橙色 — 两者
```

### 3.2 典型管线
```
[PipeNetworkNode] → WATER ─┐
                            ├→ [CombinerNode] → MIXED → [处理单元链...]
[WaterQualityNode]→ QUALITY┘
```

### 3.3 DAG 执行
1. `GraphExecutor.execute()` → 拓扑排序 (Kahn 算法)
2. 按序执行 `node.execute(flow, quality)`
3. 合并上游: 流量求和 / 水质加权平均
4. 支持增量计算 (force_all=False 时仅重算 dirty 节点及下游)
5. 失败时标记所有下游为错误

### 3.4 Kz 处理规则
- 管网 Excel "设计流量"已含 Kz (峰值流量)
- 后端所有节点直接使用 `flow.Q_design`，不重复乘 Kz
- `flow.Q_avg_daily` 用于 CASS/沉砂池等需要日均流量的场合

---

## 四、NodeBase 基类 API

### 子类必须覆盖:
- `NODE_TYPE` / `NODE_NAME` / `NODE_CATEGORY` (类属性)
- `_default_params()` → `{key: value}`
- `_build_param_defs()` → `List[ParamDef]`
- `_default_removal_rates()` → `{pollutant: rate}`
- `calculate(flow, quality)` → `NodeResult`
- `_vectorized_compute(grid, flow, quality, fixed)` → `np.ndarray` (方案空间用, 可选)
- `_init_ports()` (可选, 默认创建 1 MIXED in + 1 MIXED out)

### 关键方法:
- `execute(flow, quality)` → `(result, downstream_flow, downstream_quality)` — 自动应用去除率
- `set_param(key, value)` / `get_param(key)`
- `set_removal_rate(pollutant, rate)` / `get_removal_rates()`
- `reset_params()`
- `to_dict()` / `from_dict()` — 含 cached_result 恢复
- `get_solution_space(flow, quality)` — 方案枚举入口

---

## 五、main_window.py 核心结构

### 工具栏
- 📁文件 (新建/打开/保存/另存/最近文件)
- ▶计算管网 / 💰管网概算 / 📋导出管网报告 / 📊导出概算
- ▶计算其余(F5) / 📤全部输出
- 管网选择 Combobox + 浏览按钮
- ➕添加节点 (分类菜单) / 🗑删除节点

### 布局
- 左侧: NodeCanvas (画布, 4000×3000 可滚动)
- 右侧: 460px 面板
  - Tab: [参数] [结果] [水质]
  - 模式切换: 📊方案浏览 ↔ 🎚手动微调
  - SolutionBrowser (方案浏览模式)
  - 滑块面板 (手动微调模式, 含污染物去除率滑块)

### 模式
- **方案浏览**: 自由变量→Combobox筛选→Treeview表格→选择方案→应用
- **手动微调**: 传统滑块+输入框, 支持离散值约束, 污染物去除率独立调整

### 关键回调链
- `_on_node_selected` → `_refresh_params` → `_show_browse_mode`/`_show_manual_mode`
- `_on_ui_connection` → `executor.connect()` (端口类型匹配)
- `_on_calc_rest` → `executor.execute(force_all=True)` → 更新状态灯+结果面板

---

## 六、canvas_view.py 关键机制

### NodeItem 结构
- Canvas items 用统一 `tag=ng_{node_id}` 管理 z-order
- _items[1] = 主体矩形 (outline 高亮选中)
- 状态灯 (圆形, 绿/红/灰)
- 结果摘要文本

### 交互
- 左键点击端口 → 拖拽连线 (自动断开已有)
- 左键点击节点 → 选中+拖拽
- 左键空白 → 取消选中
- 右键节点 → 删除菜单
- 右键画布 → 分类添加节点
- 中键拖拽 → 平移 (fleur 光标)
- Ctrl+滚轮 → 缩放 (带 `_sync_all_positions`)

### 连线
- Blender 风格贝塞尔曲线 (自动水平切线)
- 颜色按端口类型: WATER=蓝, QUALITY=绿, MIXED=橙
- 缩放后 `_sync_all_positions()` 回读 Canvas 坐标→更新 Python 坐标→更新连线

### 已知 Bug (已修复)
- ✅ 拖拽文字消失 → 统一 tag 管理 + move() 末尾 raise_all()
- ✅ 缩放后连线漂移 → _sync_all_positions()
- ✅ _id 属性错误 → _outer_id / _inner_id
- ✅ 全局滚轮泄露 → 改用局部 canvas.bind
- ✅ 连线恢复失败 → port_lookup 映射表替代 split("-")

---

## 七、各处理单元核心参数

| 模块 | 自由变量 | 固定变量 | 组合数 | 关键约束 |
|------|---------|---------|--------|---------|
| 调节池 | n,HRT,h_eff,ratio_LB | h_super,P_density | 192 | L/B∈[1.5,3], HRT>=设计 |
| 粗格栅 | n,b,alpha,h | v=0.8,v1=0.7 | 192 | v∈[0.6,1.0],B1<B |
| 细格栅 | n,b,alpha,h | v=0.8,v1=0.7 | 192 | 同上, b=1.5~10mm |
| 沉砂池 | n,q_surf,t | h1,X,T_clean,θ,dr | 48 | 停留时间30~60s |
| 初沉池 | n,q',T_settle | 10个固定 | 36 | D≥16, D/h2∈[6,12] |
| CASS | n,Ns,X,θc,Tc,λ,H | 11个固定 | ~9216 | λ一致,安全距离,θc,O2 |
| 高密度沉淀池 | n,t_mix,t_floc,q_surf | 11个固定 | 96 | 轴向流速<5mm/s |
| V型滤池 | n,v,h_media,h_water | 7个固定 | 72 | 强制滤速≤8, 冲洗水<5% |
| 紫外消毒 | n,D,v,h | 14个固定 | 64 | n≥2, UV剂量通过 |

---

## 八、方案空间枚举引擎

- `discretization.py`: DISCRETE_CONFIGS 定义各模块自由/固定变量
- `solution_space.py`: SolutionSpace 类, `enumerate()` 批量计算+约束筛选+成本排序
- 每个模块的 `_vectorized_compute()` 返回 numpy 结构化数组
- 结果通过 SolutionBrowser UI 展示 (Combobox筛选 + Treeview表格)

---

## 九、工程概算

### 土建计算
- 矩形池: 土方 → 垫层 → 底板 → 池壁 → 钢筋 → 模板 → 防水
- 圆形池: 同上 + π 公式
- 池壁高度已扣底板厚度 (中期审计修复)
- 模板费已补 (圆形池+矩形池)

### 间接费
- 安装费 = 设备费 × 15%
- 管理费 = (建+安) × 5%
- 设计费 = (建+安) × 4%
- 监理费 = (建+安) × 2.5%
- 预备费 = 小计 × 10%
- 增值税 = 9%

### 数据来源
- 2019 黑龙江定额
- T/BCEBCA1-2023 造价指标
- 市场询价

---

## 十、项目文件格式 (.ddesign.json)

```json
{
  "version": "2.0",
  "metadata": { "name", "author", "created", "modified", "description" },
  "graph": {
    "nodes": [{ "id", "type", "name", "position", "params", "removal_rates",
                "ports": {"input": [...], "output": [...]},
                "cached_result": {...}, "state": "CLEAN|DIRTY|..." }],
    "connections": [{"from": "port_id", "to": "port_id"}]
  }
}
```

---

## 十一、已知问题 (来自历史审计)

### 已修复
- ✅ 格栅间隙范围 (粗50~100, 细1.5~10)
- ✅ UV n≥2 (渠道数不少于2条)
- ✅ 调节池有效水深 4~5m
- ✅ V型滤池 h_water ≥1.2m
- ✅ 池壁高度扣底板厚度
- ✅ 圆形池模板费
- ✅ 连线保存恢复 Bug
- ✅ _dirty 标志位防重复保存提示

### 尚存的近似 (概算精度 ±15%)
- 格栅/渠道按矩形箱体估算 (偏高 20~30%)
- 高密度沉淀池多仓简化为单箱 (偏高 10~15%)
- 内部结构未单独计算 (偏低 5~10%)

### 用户反馈待办
- [ ] 维度名称中文化 (L→长度, B→宽度)
- [ ] 方案浏览器增加导出全部方案到Excel
- [ ] 新建项目向导
- [ ] UV 流速不足时解释+建议
- [ ] 概算增加设备费汇总

---

## 十二、修改/扩展速查

### 添加新处理单元
1. `models/new_module.py` → 继承 `NodeBase`
2. 实现 NODE_TYPE/NODE_NAME/NODE_CATEGORY + calculate() + _vectorized_compute()
3. 在 `discretization.py` 添加 DISCRETE_CONFIGS 条目
4. 在 `main_window.py` 的 NODE_REGISTRY + FORMULAS + 添加菜单中注册
5. 在 `graph_executor.py` 的 `default_node_factory()` 注册反序列化
6. 在 `canvas_view.py._show_canvas_menu()` 的 categories 中添加
7. 在 `cost_estimator.py` 中添加跳过逻辑(如需要)
8. 在 `unit_prices.py` 中添加设备费(如需要)

### 修改计算公式
- 找到对应 `models/xxx.py` 的 `calculate()` + `_vectorized_compute()`
- 同步修改两者
- 运行单个模块测试: `python -c "from models.xxx import *; ..."`

### 调试
- 日志: `ddesign_tool/logs/ddesign_YYYYMMDD.log`
- UI crash → 先查日志
- 用 `log.debug()` 而非 `print()`
