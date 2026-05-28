# 🏭 排水工程设计工具 v5.4

> **作者**: yyx | **毕业设计**: 哈尔滨工业大学 环境工程
> **双线支持**: 市政污水 (Q=34,760 m³/d, GB18918-2002 一级A) + 矿井水 (Q=43,836 m³/d, GB3838-2002 III类)
> **模组架构**: 🎮 Minecraft式 — 完全自包含, 一个文件夹 = 一个模组, 零框架修改
> **测试覆盖**: 34/34 模组 (100%) | 640+ tests | 物理不变性 36 项 (0 skip)
> **架构评分**: 8.1/10 | pre-commit 4 钩子 | PyInstaller 56MB EXE 验证通过

## 概述

基于 Python 的城镇污水处理厂全流程工艺设计一体化工具。采用 **DAG 有向无环图执行引擎** + **MC式自包含模组架构**，严格遵循 GB50014-2021《室外排水设计标准》和 CJJ 131-2009《城镇污水处理厂污泥处理技术规程》。

### v5.4 核心改进

| 改进项 | 说明 |
|--------|------|
| 🏗️ **架构重构** | main_window 2478→1654行 (-33%), 提取 ResultPanel/ParamPanel/layout_engine/AppState |
| 🔀 **计算路径统一** | 34 模组 calculate()→_vectorized_compute(N=1), 消除双路径不一致 Bug 类别 |
| 📁 **mods/ 统一** | 单目录管理, 消除双目录同步风险 |
| 🎛️ **状态集中化** | AppState dataclass 替代 6 处散落状态 |
| 🔧 **关键 Bug 修复** | 滑块不回写/Panel初始化顺序/numpy JSON序列化/方案浏览器旧方案残留 |
| 📐 **自动布局** | Sugiyama 分层 + 蛇形网格 (📐 按钮 / Ctrl+L) |

### v5.3 核心改进

| 改进项 | 说明 |
|--------|------|
| 🏗️ **ModManager 拆分** | 1751行 God Class → 4模块 (discovery/validation/config + core 871行) |
| 🧪 **物理不变性测试** | 34 项工程规律验证 (非负/单调/守恒/约束/边界) |
| 🔧 **代码质量** | E702 分号 378→0, F401 未使用导入→0, 静默异常修复 |
| 📐 **工程基础设施** | Git 12 commits, pre-commit 4钩子, PyInstaller 56MB 验证通过 |
| 🛡️ **生产可靠性** | crash_handler 崩溃报告, GUI 输入校验, argparse CLI |
| 📊 **性能基准** | DAG<2s, 加载<1s, 枚举<1s, 冷启动<500ms |

### v5.2 核心改进

| 改进项 | 说明 |
|--------|------|
| 🎨 **UI 全面恢复** | 水质编辑卡片 (6色紧凑表格) + 全流程水质追踪 (按流程序列, 点击跳转) + 三分类结果面板 (对齐Excel) |
| 🧹 **代码质量** | flake8 530→7 (-99%), ModManager threading.Lock, JSON Schema 验证 |
| 🔧 **约束系统修复** | 全局审计 3 模组缺 constraint_keys, 动态检查 OR 硬编码, 参数重复冲突修复 |
| 🧪 **测试体系** | 433→565 tests, 内嵌自检模块 (10项, 可随EXE打包), QualityPanel 提取 |
| 📐 **功能增强** | KwInputNode 进厂管道标高, 公式完整显示不截断, 约束去重 |

### v5.1 核心改进

| 改进项 | 说明 |
|--------|------|
| 🔧 `ceil_to()` 废弃 | 25 模组统一替换为 `math.ceil(x/step)*step`，消除向量化/标量不一致根因 |
| 📝 统一日志 | `_logging.py` 提供 `get_logger()`，30+ 静默异常消灭，`DDESIGN_LOG_LEVEL` 可控 |
| 🧪 测试覆盖 97% | 33/34 模组有专属测试，427 tests, 0 failures |
| 🏗️ God Class 拆分 | main_window 2197→1822 行 (提取 3 模块)，NodeBase 提取 2 Mixin |
| 📐 公式下沉 | 公式从全局字典迁移到各模组 `labels.json`，新增模组无需改全局文件 |
| 🔗 数据源统一 | 节点注册/公式/离散化配置全部走 ModManager 单一路径 |
| 🔄 热重载 | `--reload-mods` CLI 支持，开发时无需重启 |
| 📋 版本迁移 | 项目文件 `format_version: "5.1"` 标记，支持前向兼容 |
| 🎨 black/isort | 全项目代码风格标准化

### 核心能力

| 功能 | 说明 |
|------|------|
| 🏗️ **31 核心模组 + 3 社区** | 市政污水、矿井水、污泥处理、集配水、高程 — 全部自包含 |
| 🔀 **DAG 拓扑执行** | 自动拓扑排序 → 增量计算 → 水线+污泥线+高程三通道 |
| 🛢️ **污泥全流程** | SLUDGE 端口独立通道 → 多股合并 → 浓缩/消化/脱水/干化 |
| 📏 **全厂高程计算** | 进厂标高 → 沿程水头损失传播 → 各构筑物水面/池底/埋深 |
| 🔍 **方案空间枚举** | 向量化批量计算 → 安全裕度排序 → 一键应用 |
| 📐 **管网水力计算** | 曼宁公式 → 并联优化 → 跌水井自动判定 |
| 💰 **BOQ 工程概算** | 分部分项工程量清单 → 间接费自动汇总 → 多 sheet Excel |
| 📊 **分类 Excel 输出** | 按构筑物分 sheet → 原始参数/计算结果/构筑物尺寸/水质/约束校核 — UI与Excel共用 `split_dimensions()` 过滤逻辑 |
| 🌊 **双水线支持** | 市政污水(一级A) + 矿井水(III类) → 自动出水标准匹配 |
| 📐 **公式展示** | 每个尺寸项下方显示专属计算公式 → 约束绿色/红色标记 |
| 🏷️ **完整标签系统** | 361 维度标签 + 185 向量化字段标签 + 261 分类规则 + 164 公式条目 |

### 工艺流程

```
市政污水线:
  管网输入 → 调节池 → 粗格栅 → 细格栅 → 旋流沉砂池 → 辐流初沉池
    → CASS反应器 → 高密度沉淀池 → V型滤池 → 紫外消毒池 → 达标排放

矿井水线:
  矿井水输入 → 矿井水调节池 → 平流沉砂池 → 混凝反应器 → 磁分离
    → 矿井水高密度沉淀池 → 矿井水V型滤池 → 矿井水紫外消毒池 → 达标排放

污泥线:
  产泥节点(格栅/沉砂池/初沉池/CASS/高密池)
    → [合并] → [浓缩池] → [消化池] → [脱水间] → [干化]
```

## 技术架构

```
ddesign_tool/
├── main.py                 # 入口 (GUI)
├── src/
│   ├── ui/                 # 视图层
│   │   ├── main_window.py  # 主控制器 (~2000行)
│   │   ├── canvas_view.py  # Blender风格节点画布
│   │   ├── solution_browser.py  # 方案浏览器 (枚举/排序/应用)
│   │   ├── dimension_labels.py   # 维度标签映射 (361条目) + 共享过滤函数
│   │   └── constraint_panel.py  # 约束面板
│   ├── controller/         # 控制层
│   │   ├── graph_executor.py    # DAG执行引擎 (810行, 三通道)
│   │   └── project_manager.py   # 项目管理
│   ├── models/             # 模型层
│   │   ├── base.py         # 核心基类 (921行)
│   │   ├── dimension_formulas.py  # 公式+分类库 (562行, 中英文双模式)
│   │   ├── solution_space.py # 向量化方案枚举
│   │   ├── elevation_calculator.py # 全厂高程后处理
│   │   └── cost/           # 工程概算子包 (5模块)
│   ├── pipe_hydraulic.py   # 管网水力计算
│   └── output_writer.py    # 分类Excel输出 (UI/Excel共用split_dimensions)
├── mods/                   # 模组系统
│   ├── mod_manager.py      # 模组加载器 (836行单例)
│   ├── mod_schema.json     # 模组清单JSON Schema
│   ├── mod_tools.py        # CLI工具 (scaffold/validate/list)
│   ├── MOD_SPEC.md         # 模组编写规范 v4.5
│   ├── core/               # 31 核心模组
│   └── community/          # 3 社区模组
└── data/                   # 管网Excel数据
```

**数据流**: `GraphExecutor.execute()` → `{nid: NodeResult}` → UI面板 / Excel / 概算

## 快速开始

```bash
pip install -r requirements.txt
python ddesign_tool/main.py
```

### 操作流程

```
1. 打开项目 → 添加节点 → 右键拖拽连线
2. ▶ F5 → 全流程构筑物设计计算
3. 方案浏览器 → 选方案 → 应用 → 结果面板同步
4. 📤 全部输出 → 分类 Excel 报告
5. 💰 导出概算 → BOQ 工程概算报告
```

## 模组清单

| process_stage | 模组 |
|---------------|------|
| 输入/输出 | pipe_network, water_quality, combiner, input_node, kw_input |
| 一级处理 | tiaojiechi, cugeshan, xigeshan, chenshachi, chuchenchi |
| 二级处理 | cass, aao |
| 深度处理 | gaomidu, vxinglvchi, ziwai |
| 污泥处理 | wuni_hebing, wuni_shusong, wuni_bengzhan, wuni_nongsuo, wuni_xiaohua, wuni_tuoshui, wuni_ganhua |
| 矿井水处理 | kw_tiaojiechi, kw_chenshachi, kw_ningjiao, kw_cifenli, kw_gaomidu, kw_vxinglvchi, kw_ziwai |
| 集配水 | jishuijing, peishuijing, jipeishuijing, peishuiqu |
| 高程 | jcws_smbg, gdys_stss |
| 社区 | erchunchi, bashi_jiliangcao, wuni_tisheng |

## 依赖

```
pandas, numpy, scipy, openpyxl
```

开发: `pytest, flake8, black, isort, mypy`

## 参考标准

- GB50014-2021《室外排水设计标准》
- GB 18918-2002《城镇污水处理厂污染物排放标准》一级A
- GB 3838-2002《地表水环境质量标准》III类 — 矿井水
- CJJ 131-2009《城镇污水处理厂污泥处理技术规程》
- GB 50500-2013《建设工程工程量清单计价规范》
- 2019 黑龙江省市政工程消耗量定额
- 煤炭矿井水处理设计规范

## 版本历史

| 版本 | 里程碑 |
|------|--------|
| v5.4 | 架构重构: God Class -33%, 34模组统一N=1路径, AppState集中化, 4新模块, 架构评分 7.3→8.1 |
| v5.3 | ModManager 拆分 (4模块) + 物理不变性测试 34项 + E702 清零 + pre-commit + PyInstaller 验证 |
| v5.2 | UI 全面恢复 + 生产级代码质量 (flake8 7) + 565 tests + 内嵌自检 + 约束审计 |
| v5.1 | 生产部署级重构: ceil_to 废弃, 日志统一, 97% 测试覆盖, God Class 拆分, 公式下沉, 数据源统一, black/isort |
| v4.5 | 统一维度过滤, 矿井水修复, 361 标签 + 185 向量化字段 + 261 分类 + 164 公式 |
| v4.3 | 参数完整性审计, PARAM_TABLE 清零, node_type 感知查找 |
| v4.4 | 方案浏览器一致性修复, 流量追踪 Q_avg 偏差修复 |
| v3.5 | 全厂高程计算 + 集配水模组 + UI 公式/约束面板 |
| v3.2 | MC式模组架构: 一个文件夹=一个模组，零框架修改 |
| v3.3 | 双水线(矿井水8模组) + 标准化输出契约 |

> **维护者**: yyx | **版本**: v5.4 | **更新**: 2026-05-28 | **31 核心 + 3 社区 = 34 模组**
