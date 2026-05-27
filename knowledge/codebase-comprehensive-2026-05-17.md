# 排水工程设计工具 v3.2 — 完整学习记录

> 最后更新: 2026-05-18
> 状态: v3.2 MC式模组架构上线
> 测试: 177 passed, 3 skipped, 0 failed

---

## 一、架构全景

```
main.py (19L)
  └─ MainWindow.run() — tkinter 主窗口 (1500x850, 暗色主题)

     ┌──────────────────────────────────────────────────┐
     │  ui/ (视图层)                                     │
     │  main_window.py (1333L) — 主控制器                │
     │  canvas_view.py (427L) — Blender风节点画布         │
     │  solution_browser.py (628L) — 方案浏览器+导出      │
     │  file_manager.py (211L) — 文件I/O管理器            │
     │  dimension_labels.py (583L) — 维度→4列映射表       │
     │  logger.py (51L) — 日志                           │
     ├──────────────────────────────────────────────────┤
     │  controller/ (控制层)                              │
     │  graph_executor.py (486L) — DAG执行引擎            │
     │  project_manager.py (189L) — 项目文件管理           │
     ├──────────────────────────────────────────────────┤
     │  models/ (模型层, 15个处理单元)                     │
     │  base.py (719L) — NodeBase基类+数据模型             │
     │  discretization.py (350L) — 离散化配置              │
     │  solution_space.py (404L) — 方案枚举引擎            │
     │  cost/ (工程概算, 6文件, ~1900L)                    │
     └──────────────────────────────────────────────────┘

     ┌──────────────────────────────────────────────────┐
     │  mods/ (模组系统)                                  │
     │  mod_manager.py (420L) — 扫描/加载/注册引擎        │
     │  MOD_SPEC.md (580L) — 模组编写完整规范              │
     │  core/ — 14个内置核心模组 (mod.json+__init__.py)    │
     │  community/ — 用户模组空间                          │
     └──────────────────────────────────────────────────┘
```

---

## 二、模块清单 (17 种节点类型)

| NODE_TYPE | 中文名 | process_stage | category | 文件 | 行数 |
|-----------|--------|---------------|----------|------|------|
| `pipe_network` | 管网输入 | — | 输入/输出 | pipe_network.py | 207 |
| `water_quality` | 进水水质 | — | 输入/输出 | water_quality_node.py | 159 |
| `combiner` | 合并 | — | 输入/输出 | combiner.py | 60 |
| `input_node` | 输入节点(旧) | — | 输入/输出 | input_node.py | 123 |
| `tiaojiechi` | 调节池 | primary | 市政污水处理 | tiaojiechi.py | 245 |
| `cugeshan` | 粗格栅 | primary | 市政污水处理 | geshan.py | 222 |
| `xigeshan` | 细格栅 | primary | 市政污水处理 | geshan.py | — |
| `chenshachi` | 旋流沉砂池 | primary | 市政污水处理 | chenshachi.py | 192 |
| `chuchenchi` | 辐流初沉池 | primary | 市政污水处理 | chuchenchi.py | 231 |
| `cass` | CASS反应器 | secondary | 市政污水处理 | cass.py | 306 |
| `gaomidu` | 高密度沉淀池 | tertiary | 市政污水处理 | gaomidu.py | 193 |
| `vxinglvchi` | V型滤池 | tertiary | 市政污水处理 | vxinglvchi.py | 162 |
| `ziwai` | 紫外消毒池 | tertiary | 市政污水处理 | ziwai.py | 251 |
| `kw_input` | 矿井水输入 | mine_water | 矿井水处理 | kw_input.py | 127 |
| `kw_tiaojiechi` | 矿井水调节池 | mine_water | 矿井水处理 | kw_tiaojiechi.py | 174 |
| `kw_chenshachi` | 平流沉砂池 | mine_water | 矿井水处理 | kw_chenshachi.py | 184 |
| `kw_ningjiao` | 混凝反应池 | mine_water | 矿井水处理 | kw_ningjiao.py | 197 |
| `kw_cifenli` | 磁分离 | mine_water | 矿井水处理 | kw_cifenli.py | 156 |

---

## 三、数据流

```
┌──────────────┐     ┌──────────────┐
│ PipeNetwork  │     │WaterQuality  │
│ (Excel读取)  │     │ (用户设定)    │
│ Q_design=0.57│     │ BOD5=200...  │
└──────┬───────┘     └──────┬───────┘
       │ WATER               │ QUALITY
       └──────────┬──────────┘
                  ▼
            ┌──────────┐
            │ Combiner │  ← 合并: 流量=WATER, 水质=QUALITY
            └────┬─────┘
                 │ MIXED (flow + quality)
                 ▼
        ┌────────────────┐
        │  处理单元链      │  ← 调节池→格栅→沉砂→CASS→...
        │  execute() 调用  │     每个节点:
        │  1. calculate() │       - 输入流量+水质 计算尺寸
        │  2. apply_removal│      - 检查约束
        │  3. 生成下游水质  │       - 生成下游水质(去除率)
        └────────┬───────┘
                 │
        ┌────────▼───────┐
        │  GraphExecutor │  ← Kahn拓扑排序
        │  execute()     │     上游流量求和/水质加权
        │  → {nid: NodeResult} │
        └────────┬───────┘
                 │
     ┌───────────┼───────────┐
     ▼           ▼           ▼
 ┌───────┐ ┌────────┐ ┌──────────┐
 │Result │ │水质Tab │ │Excel输出 │
 │Panel  │ │(卡片式)│ │4列格式    │
 │Treeview│ │        │ │output/    │
 └───────┘ └────────┘ └──────────┘
```

---

## 四、关键 API

### 4.1 NodeBase (base.py:408)

```python
class NodeBase:
    # 子类必须覆盖
    NODE_TYPE: str      # "tiaojiechi"
    NODE_NAME: str      # "调节池"
    NODE_CATEGORY: str  # "一级处理"

    # 核心方法
    calculate(flow, quality) → NodeResult           # [必须覆盖] 标量计算
    _vectorized_compute(grid, flow, quality, fixed) → np.ndarray  # [可选] 向量化
    execute(flow, quality) → (result, downstream_flow, downstream_quality)

    # 参数管理
    get_param(key) → float
    set_param(key, value) → marks DIRTY
    reset_params() → restores defaults
    get_removal_rates() → dict

    # 序列化
    to_dict() → dict  # 含 cached_result (inlet/outlet quality)
    from_dict(d) → NodeBase
```

### 4.2 WaterFlow (base.py:211)

```python
@dataclass
class WaterFlow:
    Q_design: float = 0.57      # 最大设计流量 m³/s
    Q_avg_daily: float = 34760.7 # 平均日流量 m³/d
    Kz: float = 1.4              # 总变化系数

    # 属性
    Q_avg_hourly → float   # m³/h
    Q_avg_second → float   # m³/s
    Q_design_Ls → float    # L/s

    # 转换
    Q_design_as(unit) → float  # "m3/s"|"L/s"|"m3/h"|"m3/d"
```

### 4.3 WaterQuality (base.py:115)

```python
@dataclass
class WaterQuality:
    BOD5: 200.0, COD: 400.0, SS: 220.0
    NH3N: 35.0, TN: 45.0, TP: 5.0, pH: 7.0

    apply_removal(rates) → WaterQuality  # 应用去除率
    check_effluent() → {pollutant: (passed, diff)}
    mgL_to_kgm3(val) → float
    kgm3_to_mgL(val) → float
```

### 4.4 NodeResult (base.py:277)

```python
@dataclass
class NodeResult:
    success: bool = True
    params: dict           # 输入参数 {key: value}
    dimensions: dict       # 尺寸 {name: (value, unit)}
    checks: dict           # 校核 {name: (passed, actual, limit, unit)}
    warnings: list         # 警告信息
    inlet_quality: WaterQuality | None   # 进水水质(水质追踪)
    outlet_quality: WaterQuality | None  # 出水水质(水质追踪)
    robustness: float = 0.0

    add_dimension(name, value, unit)
    add_check(name, passed, actual, limit, unit)
    add_warning(msg)
    failed(error_msg) → NodeResult  # 工厂方法
```

### 4.5 GraphExecutor (graph_executor.py:38)

```python
class GraphExecutor:
    add_node(node) / remove_node(node_id)
    connect(from_port, to_port) → bool
    topological_order() → List[str]  # Kahn算法
    execute(force_all=False) → {node_id: NodeResult}
    to_dict() / from_dict(d, node_factory)
    node_count → int
    get_node(node_id) → NodeBase | None
```

### 4.6 ModManager (mods/mod_manager.py:130)

```python
class ModManager:  # 单例
    node_registry → {node_type: (class, display_name)}
    formulas → {node_type: formula_string}
    categories → {category: [node_type, ...]}
    mods → {mod_id: ModInfo}

    load_all() → 加载并注册所有模组
    get_node_class(node_type) → Type | None
    get_mods_by_stage(stage) → List[ModInfo]
    STAGE_ORDER = {"io":0, "primary":1, "secondary":2, "tertiary":3, "mine_water":10}
```

---

## 五、工程概算体系

### 5.1 费率标准 (unit_prices.py)

| 费率项 | 基数 | 费率 |
|--------|------|------|
| 安装费 | 设备费 | 15% |
| 管理费 | 建安费 | 5% |
| 设计费 | 建安费 | 4% |
| 监理费 | 建安费 | 2.5% |
| 前期工作费 | 建安费 | 1% |
| 预备费 | 小计 | 10% |
| 增值税 | (小计+预备费) | 9% |

### 5.2 土建计算公式

**矩形池**: 土方→垫层→底板→池壁→钢筋→模板→防水
- 池壁高度 = H - tf (已扣除底板厚度)
- 土方 = (L+2)(B+2)(H+tf+0.5)×n×1.2 (含工作面+放坡)
- 墙厚/底板厚由 `wall_t(V)`, `floor_t(V)` 查表

**圆形池**: 同上 + π 公式
- 土方 = π(R+1)²(H+tf+0.5)×n×1.3

### 5.3 尺寸提取逻辑 (cost_estimator.py:_structure_civil)

```
通用: D=池径D | L=池长L/单格长度L | B=池宽B/单格宽度B | H=总高度H/总高度/滤池总高度
格栅: L=栅槽总长L | B=栅槽宽度B | H=栅后总高H
UV:   L=渠道总长 | B=渠宽 | H=总高度
跳过: pipe_network, water_quality, combiner, input_node, kw_input, kw_cifenli
```

---

## 六、模组系统

### 6.1 目录结构

```
ddesign_tool/mods/
├── mod_manager.py         # ModManager 单例
├── MOD_SPEC.md            # 模组编写完整规范(12章)
├── core/                  # 14个内置模组
│   ├── tiaojiechi/        # 每个模组 = mod.json + __init__.py
│   ├── cass/
│   └── ...
└── community/             # 用户自定义模组
    └── README.md          # 5分钟快速开始指南
```

### 6.2 mod.json 结构

```json
{
  "id": "tiaojiechi", "name": "调节池", "version": "1.0.0",
  "category": "市政污水处理", "process_stage": "primary",
  "node_type": "tiaojiechi", "node_class": "TiaojiechiNode",
  "module_path": "models.tiaojiechi",
  "inputs": [{"type": "MIXED", "name": "进水"}],
  "outputs": [{"type": "MIXED", "name": "出水"}],
  "parameters": [...], "removal_rates": {...},
  "formula": "V = Q_single × HRT", "tags": ["预处理", "调节"]
}
```

### 6.3 处理阶段 (process_stage)

| 阶段 ID | 含义 | 模组数 |
|---------|------|--------|
| `io` | 输入/输出 | (基础设施) |
| `primary` | 一级处理(含预处理) | 5 (调节池,粗格栅,细格栅,沉砂池,初沉池) |
| `secondary` | 二级处理 | 1 (CASS) |
| `tertiary` | 深度处理 | 3 (高密度沉淀池,V型滤池,紫外消毒) |
| `mine_water` | 矿井水处理 | 5 (kw_*) |

---

## 七、修复历史

### 已修复 (2026-05-16 ~ 2026-05-17)

| 日期 | Bug | 修复 |
|------|-----|------|
| 05-16 | Combiner 流量翻倍 | WaterQualityNode 输出流量=0 |
| 05-16 | F5 覆盖向量化缓存 | force_all=False, CLEAN 节点保留 |
| 05-16 | UV N_rows 量纲错误 | ceil(D_UV/dose_per_row) |
| 05-16 | 沉砂池 V_storage 公式 | V_cone + V_cyl |
| 05-16 | 池壁高度未扣底板 | H → H-tf |
| 05-16 | 格栅间隙范围错误 | 粗50~100mm, 细1.5~10mm |
| 05-16 | UV n≥2 约束缺失 | n ∈ [2, 3] |
| 05-17 | 保存按钮崩溃 | ProjectManager._add_to_recent Path类型 |
| 05-17 | UV 无法提取尺寸 | 添加渠道型尺寸映射 |
| 05-17 | CASS 方案显示滞后 | _on_apply 后调用 _refresh_table |
| 05-17 | 水质面板全空白 | 跳过 I/O 类节点而非去除率检查 |
| 05-17 | inlet/outlet_quality 丢失 | 序列化/反序列化支持 |
| 05-17 | kw_cifenli 无尺寸警告 | 加入成本估算跳过列表 |

### 架构优化

| 日期 | 变更 | 影响 |
|------|------|------|
| 05-16 | 创建 Mod 系统 | 14个 core 模组 + ModManager |
| 05-16 | main_window.py 提取 FileManager | 1333→1151行 (-21%) |
| 05-16 | 120 个单元测试 | 覆盖 base + 3处理单元 + executor |
| 05-16 | MOD_SPEC.md 规范 | 12章完整模组编写指南 |
| 05-17 | 输出表格优化 | 146维度全部有显式标签映射 |

---

## 八、文件清单 (按目录)

```
ddesign_tool/
├── main.py (19L)                    # 入口
├── config.ini                       # 设计参数配置
├── mods/                            # 🆕 模组系统
│   ├── mod_manager.py (420L)        # 扫描/加载/注册引擎
│   ├── MOD_SPEC.md (580L)           # 编写规范
│   ├── core/ (14 folders)           # 内置模组
│   └── community/README.md          # 社区指南
├── src/
│   ├── ui/
│   │   ├── main_window.py (1333L)   # 主窗口
│   │   ├── canvas_view.py (427L)    # 画布
│   │   ├── solution_browser.py (628L)# 方案浏览器
│   │   ├── file_manager.py (211L)   # 🆕 文件管理
│   │   ├── dimension_labels.py (583L)# 维度映射
│   │   └── logger.py (51L)          # 日志
│   ├── controller/
│   │   ├── graph_executor.py (486L) # DAG引擎
│   │   └── project_manager.py (189L)# 项目管理
│   ├── models/
│   │   ├── base.py (719L)           # 基类+数据模型
│   │   ├── discretization.py (350L) # 离散化配置
│   │   ├── solution_space.py (404L) # 方案枚举
│   │   ├── tiaojiechi.py (245L)     # 调节池
│   │   ├── geshan.py (222L)         # 粗格栅+细格栅
│   │   ├── chenshachi.py (192L)     # 旋流沉砂池
│   │   ├── chuchenchi.py (231L)     # 辐流初沉池
│   │   ├── cass.py (306L)           # CASS反应器
│   │   ├── gaomidu.py (193L)        # 高密度沉淀池
│   │   ├── vxinglvchi.py (162L)     # V型滤池
│   │   ├── ziwai.py (251L)          # 紫外消毒池
│   │   ├── kw_input.py (127L)       # 矿井水输入
│   │   ├── kw_tiaojiechi.py (174L)  # 矿井水调节池
│   │   ├── kw_chenshachi.py (184L)  # 平流沉砂池
│   │   ├── kw_ningjiao.py (197L)    # 混凝反应池
│   │   ├── kw_cifenli.py (156L)     # 磁分离
│   │   └── cost/
│   │       ├── cost_estimator.py (446L) # 概算引擎
│   │       ├── report_writer.py (873L)  # Excel报告
│   │       ├── unit_prices.py (154L)    # 单价数据库
│   │       ├── pipe_network_cost.py (295L) # 管网概算
│   │       └── fast_estimator.py (155L) # 快速估算
│   ├── output_writer.py (308L)      # 分类输出
│   ├── result_writer.py (170L)      # 管网结果
│   └── pipe_hydraulic.py (104L)     # 水力计算
├── tests/
│   ├── conftest.py (210L)           # 共享 fixtures
│   ├── test_base.py (550L)          # 78 tests
│   ├── test_processing.py (208L)    # 22 tests
│   ├── test_graph_executor.py (110L)# 10 tests
│   └── test_sample.py (125L)        # 13 tests
└── .sisyphus/notepads/              # 学习记录
```

---

## 九、UI 操作流程

```
1. 启动 → _load_demo() 加载默认管网节点
2. 📁文件 → 打开/保存/另存为/最近文件
3. ➕添加节点 → 按处理阶段分组选择
4. 画布连线 → 端口类型自动匹配(WATER/QUALITY/MIXED)
5. 右侧面板 → [参数] [结果] [水质] 三个Tab
   - 参数Tab: 📊方案浏览 / 🎚手动微调 双模式
   - 结果Tab: 4列Treeview (符号|物理意义|单位|取值)
   - 水质Tab: 卡片式展示 (进水→出水→去除率→标准)
6. ▶F5 计算 → GraphExecutor.execute() → 更新状态灯
7. 📤全部输出 → Excel (汇总+各构筑物独立sheet)
8. 💰导出概算 → Excel (工程量清单+间接费+增值税)
```

---

## 十、已知限制 & 待优化

| 项目 | 优先级 | 说明 |
|------|--------|------|
| main_window.py 仍 1333 行 | P2 | 可继续提取 ExportHandler, ParameterPanel |
| CASS 默认参数 2 项硬约束不通过 | P2 | 用户需手动选方案或调整参数 |
| 格栅/渠道概算偏高 20~30% | P3 | 按矩形箱体估算，实际为开放渠道 |
| 无新建项目向导 | P3 | 首次使用引导 |
| 无 mypy strict 检查 | P3 | 类型标注不完整 |

---

> **维护提示**: 每次修改后运行 `pytest tests/ -q` 确认 120 测试通过。
> **模组开发**: 参照 `mods/MOD_SPEC.md` 和 `mods/community/README.md`。

---
## 十一、2026-05-17 修复日志

### Phase 1 — 重构残留 Bug
| # | 文件 | 问题 | 修复 |
|---|------|------|------|
| 1 | file_manager.py:86 | `self._update_recent_menu()` 不存在 | → `self.update_recent_menu()` |
| 2 | file_manager.py | `on_save_as()`/`on_open()`/`open_recent()` 未刷新最近文件菜单 | 新增 `update_recent_menu()` 调用 |

### Phase 2 — 沉砂池砂斗约束 & 输出完整性
| # | 文件 | 问题 | 修复 |
|---|------|------|------|
| 3 | chenshachi.py | "砂斗容积足够" 恒成立 (h_cyl 由 V_hopper 反算) | 移除冗余约束; 新增 V_storage 输出 |
| 4 | chenshachi.py | V_cyl 仅 h_cyl>0 时输出 | 始终输出 |
| 5 | discretization.py | chenshachi constraint_keys 移除 "sand" | |

### Phase 3 — 约束校核值显示异常 (9 处)
| # | 问题 | 根因 | 影响模块 |
|---|------|------|---------|
| 6 | val_* 字段缺失 → 显示 0.0 | solution_space.py:363 静默回退 | chuchenchi (val_D_min) |
| 7 | constraint_key 名不匹配 | discretization.py key vs dtype field | chuchenchi(sludge_vol→sludge), cass(lam_consistency→lam, safe_dist→safe) |
| 8 | 矿井水模块 constraint_keys 含 ok_ 前缀 | 查找 ok_ok_* → 完全缺失 | kw_tiaojiechi, kw_chenshachi, kw_ningjiao, kw_cifenli |

### Phase 4 — 输出维度遗漏
| # | 模块 | 新增输出 |
|---|------|---------|
| 9 | geshan | 清渣方式 value 从 0 改为字符串 |
| 10 | chuchenchi | +泥斗高度 h5, 出水堰长, 单池需贮泥容积 V_sludge |
| 11 | cass | +长宽比 L/B, 宽高比 B/H (标量输出) |
| 12 | gaomidu | +日湿污泥量, PAC日耗量 |
| 13 | dimension_labels.py | +5 个新标签映射 |

### Phase 5 — 工程概算 _val() 键匹配失败
| # | 问题 | 根因 | 影响 |
|---|------|------|------|
| 14 | 多个模块土建费用为 0 | _val() 子串匹配无法处理 "池长 L"→"单池长度 L" 等变体 | tiaojiechi, vxinglvchi, kw_tiaojiechi, kw_chenshachi 等 |
| 15 | 修复 | _val() 升级为 5 级匹配: 精确→中文基础名→别名扩展→英文→后缀 |
| 16 | fast_estimator | +kw_tiaojiechi, kw_chenshachi, kw_ningjiao 专用估算器 |

### Phase 6 — 进水水质数据流断裂
| # | 问题 | 根因 | 修复 |
|---|------|------|------|
| 17 | 下游模块收到进水水质=0 | _merge_upstream() 流量加权平均: WaterQualityNode 输出 Q=0 → 权重=0 | 识别 QUALITY-only 节点, 直接设值不参与加权 |

### Phase 7 — 进水水质显示层 (8 处修复)
| # | 问题 | 文件 | 修复 |
|---|------|------|------|
| 18 | _default_params() 返回 {} → set_param 静默失败 | water_quality_node.py | 返回实际默认值 |
| 19 | reset_params() 不重置 water_quality | water_quality_node.py | override 同步 |
| 20 | WaterQualityNode.execute() 用空上游覆写 inlet_quality 和维度 | water_quality_node.py | 改从 self.water_quality 读取 |
| 21 | _trace_upstream_context 同样流量加权 bug | main_window.py | 同 Fix 17 逻辑 |
| 22 | _show_browse_mode inlet_quality=None → WaterQuality() | main_window.py | 回退 _trace_upstream_context |
| 23 | solution_browser._on_apply 不设 inlet/outlet_quality | solution_browser.py | 从 self._quality 填充 |
| 24 | _auto_apply_recommended 不设 inlet/outlet_quality | main_window.py | 从 _trace_upstream_context 填充 |

### Phase 8 — 增量计算陈旧数据传播 (3 处)
| # | 问题 | 文件 | 修复 |
|---|------|------|------|
| 25 | CLEAN 节点 dimensions("进水BOD5") 不随 inlet_quality 更新 | graph_executor.py | 同步更新维度字典 |
| 26 | _find_dirty_with_downstream 不传播到下游 | graph_executor.py | BFS 传播: DIRTY → 全部下游 |
| 27 | PipeNetworkNode._load_excel_data 不标记 DIRTY | pipe_network.py | 成功后 self.state = DIRTY |

### Phase 9 — 输出表格重构
| # | 改动 | 文件 |
|---|------|------|
| 28 | 每构筑物 sheet 从 3 表改为 5 表: 原始设计参数→计算结果→构筑物尺寸→水质追踪→约束校核 | output_writer.py |
| 29 | 新增 _is_physical_dimension() — 基于 60+ 中文关键词分类物理尺寸 vs 计算值 | output_writer.py |
| 30 | 修复 _write_section 被覆盖 bug | output_writer.py |

### Phase 10 — 工程概算修复
| # | 问题 | 文件 | 修复 |
|---|------|------|------|
| 31 | _val() 子串匹配无法处理 "池长 L"→"单池长度 L" 等 11 种变体 | cost_estimator.py | 5 级匹配: 精确→中文基础名→别名表→英文→后缀 |
| 32 | 矿井水模块 fast_estimator 缺失 | fast_estimator.py | +kw_tiaojiechi/kw_chenshachi/kw_ningjiao |

### Phase 11 — 约束校核值显示 (9 处)
| # | 问题 | 根因 | 文件 |
|---|------|------|------|
| 33 | val_* 字段缺失→显示 0.0 | solution_space.py:363 静默回退 | chuchenchi + cass + 4 kW modules |
| 34 | 矿井水模块 constraint_keys 含 ok_ 前缀→双重前缀 | discretization.py | 去掉 ok_ 前缀 |

### Phase 12 — 输出维度完整性
| # | 模块 | 新增输出 |
|---|------|---------|
| 35 | geshan | 清渣方式 value 从 0 改字符串 |
| 36 | chuchenchi | +泥斗高度 h5, 出水堰长, 单池需贮泥容积 |
| 37 | cass | +长宽比 L/B, 宽高比 B/H (标量) |
| 38 | gaomidu | +日湿污泥量, PAC日耗量 |
| 39 | chenshachi | 移除冗余砂斗约束, +V_storage, 圆柱储砂容积始终输出 |

### Phase 13 — 管网水力计算修复
| # | 问题 | 文件 | 修复 |
|---|------|------|------|
| 40 | data_loader 固定 8 列, 雨水 6 列全部跳过 | data_loader.py | 兼容 6/8 列 |
| 41 | Excel 空单元格 NaN 传播 → Q=NaN | data_loader.py | pd.notna() 守卫 |
| 42 | Q=0 设计失败 | pipe_hydraulic.py | 流量推算: q=面积×比流量 |
| 43 | result_writer 跌水 NoneType 崩溃 | result_writer.py | None 守卫 |
| 44 | set_excel 不兼容 .xlsx 后缀 | pipe_network.py | 自动剥离后缀 |
| 45 | 管网下拉表硬编码 3 项 | main_window.py | 动态扫描 data/ 目录 |

### Phase 14 — 输出表格优化
| # | 改动 | 文件 |
|---|------|------|
| 46 | 每构筑物 sheet 从 3 表改为 5 表 | output_writer.py |
| 47 | 硬约束失败不再跳过整表, 改为标题 ⚠ 标注 | output_writer.py |
| 48 | 汇总 sheet 新增「输出日志」— 列出所有模块成功/失败状态 | output_writer.py |

### Phase 15 — PyInstaller 自解压打包 (2026-05-18)
| # | 改动 | 文件 |
|---|------|------|
| 49 | 新建 bootstrap.py — 首次运行从 MEIPASS 提取资源到 cwd | `ddesign_tool/src/bootstrap.py` (106L) |
| 50 | `_paths.py` frozen 模式：data/mods/config 路径指向 cwd | `ddesign_tool/src/_paths.py` (+30L) |
| 51 | `.spec` datas 从 3 项扩至 8 项 (knowledge/output_template/md/json) | `ddesign_tool.spec` |
| 52 | main.py GUI 启动前调用 `extract_resources()` | `ddesign_tool/main.py` |
| 53 | 修复 7 处 `__file__` 引用 → `_paths` 函数 | 6 文件 (mod_manager/logger/pipe_hydraulic/pipe_network/project_manager/solution_space/report_writer) |
| 54 | 单元测试 `test_bootstrap.py` — 7 用例覆盖 source/frozen/skip/force/missing | `tests/test_bootstrap.py` |
| 55 | 构建 52MB 自包含 EXE → `dist/ddesign_tool.exe` | PyInstaller 6.20.0 |

### Phase 15 — 打包架构

```
ddesign_tool.exe (52MB, one-file mode)
├── [启动] bootstrap.extract_resources()
│   ├── 检测 sys.frozen → True
│   ├── 遍历 RESOURCE_MANIFEST (8 项)
│   ├── os.path.exists(dst) → skip (保留用户修改)
│   └── shutil.copytree/copy2(MEIPASS → cwd)
├── [路径] _paths.py frozen 分支
│   ├── get_data_dir()    → cwd/data/
│   ├── get_mods_dir()    → cwd/mods/
│   ├── get_config_path() → cwd/config.ini
│   └── get_knowledge_dir() → cwd/knowledge/  (新增)
└── [GUI] main_window.py 正常启动
    ├── 读取本地 mods/data/config (用户可编辑)
    ├── 写入 output/logs/projects/cache (cwd)
    └── 模组管理器扫描本地 mods/ 目录
```

### Phase 16 — 矿井水 UI + 方案浏览修复 (2026-05-18)
| # | 问题 | 根因 | 修复 |
|---|------|------|------|
| 56 | kw_input 无滑块 | 不在 UI 排除/包含列表中 | 添加 `kw_input` 到 solution browser 排除列表 + WQ card 包含列表 |
| 57 | 矿井水方案浏览器不显示 | `solution_space.py` module_map/class_map 缺少 4 个 kw_ 模块 | 添加 kw_tiaojiechi/kw_chenshachi/kw_ningjiao/kw_cifenli 注册 |
| 58 | kw_input 添加后下游无法追踪流量 | 未自动计算，result=None | `_add_node` 中 auto-execute kw_input |
| 59 | WQ card 标题硬编码 | 固定显示"鹤岗市A区城市污水" | 动态标题：kw_input → "矿井水" |
| 60 | kw_input 水质流量可调 | SS/TDS/pH/COD 硬编码 | 新增 7 个 ParamDef (3 流量 + 4 水质) |

**验证**: 4 矿井水模块方案枚举通过 (kw_tj=68, kw_cs=72, kw_nj=200, kw_cf=40)。全量测试 153 passed。

**嵌入资源清单 (8 项)**:

| MEIPASS 路径 | 提取目标 | 类型 |
|-------------|---------|------|
| `config.ini` | `config.ini` | 文件 |
| `mods/` | `mods/` | 目录 (14 core mods) |
| `data/` | `data/` | 目录 (6 xlsx) |
| `knowledge/` | `knowledge/` | 目录 (4 md) |
| `output_template/` | `output/` | 目录 (模板输出) |
| `MODS_GUIDE.md` | `MODS_GUIDE.md` | 文件 (案例) |
| `README.md` | `README.md` | 文件 (案例) |
| `yyx.ddesign.json` | `yyx.ddesign.json` | 文件 (案例) |

### Phase 17 — AAO 工艺模组 (2026-05-18)
| # | 改动 | 文件 |
|---|------|------|
| 61 | 新建 AAO 模组 (A2O 厌氧-缺氧-好氧) | mod.json + __init__.py + aao.py (192L) |
| 62 | 离散化配置: 6 自由变量 (n/tp/tn/to/Ls/X_MLSS) | discretization.json + discretization.py |
| 63 | 方案空间: 200 可行解 | solution_space.py 注册 |
| 64 | 成本/报告/标签自动注册 | fast_estimator + report_writer + dimension_labels |

### Phase 18 — 模组架构重构: 单文件夹注册 (2026-05-18)
| # | 改动 | 文件 |
|---|------|------|
| 65 | ModManager 扩展: 11 新方法 (配置加载 + 查询) | mod_manager.py (+140L) |
| 66 | solution_space eliminiate module_map/class_map | solution_space.py (→ 自动发现) |
| 67 | discretization 双读: 优先 mod 文件夹 | discretization.py |
| 68 | dimension_labels 自动生成 (从 mod.json) | dimension_labels.py |
| 69 | FLOW_ORDER 自动推导 (从 process_stage) | report_writer.py |
| 70 | UI skip lists 通用化 (is_io_node) | output_writer.py + main_window.py |
| 71 | UI 菜单自动生成 (get_category_menu) | main_window.py + canvas_view.py |
| 72 | 14 个 discretization.json 迁移到各自 mod 文件夹 | 14 文件 |
| 73 | AAO UI 可见 + 地表水 III 类标准展示 | main_window.py |

**重构效果**: 添加新模组从 8 分散文件 → 4 文件 (全在一文件夹)。UI 菜单、方案空间、流程排序、维度标签全部自动发现。

### Phase 19 — 矿井水排放标准 + 输入节点增强 (2026-05-18)
| # | 改动 | 文件 |
|---|------|------|
| 74 | GB3838-2002 地表水 III 类排放标准展示 | main_window.py (kw_input WQ card) |
| 75 | kw_input 水质可调: SS_in/TDS/pH/COD | kw_input.py + mod.json + dimension_labels |
| 76 | kw_input mod.json 与代码参数同步 | mod.json (7 params) |
| 77 | 矿井水 UI + 方案浏览修复 | main_window.py + solution_space.py |

**设计原则**:
- 资源随 EXE 分发 (零配置启动)
- 首次运行提取到本地 (可编辑、可扩展)
- 幂等: 已存在则跳过 (保留用户修改)
- output_template → output 重命名 (避免与运行时冲突)

---

## 十二、v3.1 — 污泥处理全流程模块 (2026-05-18)

### Phase 20 — SludgeFlow + SLUDGE 端口类型
| # | 改动 | 文件 |
|---|------|------|
| 61 | 新增 SludgeFlow 数据类 (Q_wet/DS/P_moisture/VS_ratio) | base.py (+55行) |
| 62 | 新增 SLUDGE 端口类型 (PortType.SLUDGE) | base.py |
| 63 | 新增 "sludge" process_stage (STAGE_ORDER=4) | mod_manager.py |
| 64 | 新增 "污泥处理" 中文阶段名 | mod_manager.py |

### Phase 21 — 现有模块污泥输出端口
| # | 改动 | 文件 |
|---|------|------|
| 65 | chuchenchi: +SLUDGE 排泥端口 (初沉污泥) | chuchenchi.py + mod.json |
| 66 | cass: +SLUDGE 剩余污泥端口 | cass.py + mod.json |
| 67 | aao: +SLUDGE 剩余污泥端口 | aao.py + mod.json |
| 68 | gaomidu: +SLUDGE 排泥端口 (化学污泥) | gaomidu.py + mod.json |
| 69 | cugeshan/xigeshan: +SLUDGE 栅渣端口 | geshan.py + 2 mod.json |
| 70 | chenshachi: +SLUDGE 沉砂端口 | chenshachi.py + mod.json |

### Phase 22 — 6 个污泥处理模组
| # | 模组 | 功能 | 文件 |
|---|------|------|------|
| 71 | wuni_shusong | 污泥输送泵站 (汇集+泵送) | mod.json + __init__.py + models/ |
| 72 | wuni_nongsuo | 污泥浓缩池 (重力浓缩 96%→94%) | mod.json + __init__.py + models/ |
| 73 | wuni_xiaohua | 污泥消化池 (厌氧消化+沼气) | mod.json + __init__.py + models/ |
| 74 | wuni_tuoshui | 污泥脱水间 (带式/离心 96%→78%) | mod.json + __init__.py + models/ |
| 75 | wuni_ganhua | 污泥干化 (热干化/太阳能) | mod.json + __init__.py + models/ |
| 76 | wuni_bengzhan | 污泥泵站 (加压+管道) | mod.json + __init__.py + models/ |

### Phase 23 — GraphExecutor 污泥路由
| # | 改动 | 文件 |
|---|------|------|
| 77 | NodeBase 增加 is_sludge_only 属性 + execute_sludge() 方法 | base.py |
| 78 | GraphExecutor 增加 _execute_sludge_pass() 污泥线独立执行 | graph_executor.py (+130行) |
| 79 | GraphExecutor 增加 _merge_sludge_upstream() 污泥流合并 | graph_executor.py |
| 80 | execute() 水线跳过纯污泥节点 | graph_executor.py |
| 81 | 6 污泥节点注册到 compat_modules | graph_executor.py |

### Phase 24 — 离散化 + 序列化
| # | 改动 | 文件 |
|---|------|------|
| 82 | 6 个 discretization.json 配置文件 | mods/core/wuni_*/ |
| 83 | NodeResult 增加 sludge_output 字段 | base.py |
| 84 | sludge_output 序列化/反序列化支持 | base.py |

### Phase 25 — Bug 修复
| # | 问题 | 修复 |
|---|------|------|
| 85 | get_ui_behavior() 无 legacy 节点处理 → 水质滑块消失 | mod_manager.py: 增加 5 个 legacy IO 节点硬编码 |
| 86 | main_window.py 4处 try/except fallback 永不触发 | 改为 or 模式 |
| 87 | output_writer.py 3处 同类型 bug | 改为 or 模式 |
| 88 | canvas_view.py 缺少 sludge 端口颜色 | 添加棕色配色 (#cc8844) |

### v3.1 模块清单 (22 种节点类型)

| NODE_TYPE | 中文名 | process_stage | 新增 |
|-----------|--------|---------------|------|
| wuni_shusong | 污泥输送泵站 | sludge | ✅ |
| wuni_nongsuo | 污泥浓缩池 | sludge | ✅ |
| wuni_xiaohua | 污泥消化池 | sludge | ✅ |
| wuni_tuoshui | 污泥脱水间 | sludge | ✅ |
| wuni_ganhua | 污泥干化 | sludge | ✅ |
| wuni_bengzhan | 污泥泵站 | sludge | ✅ |

### 污泥处理链验证

```
输入: DS=4000 kg/d, Q_wet=100 m³/d, P=96%
输送泵站 → 100.0 m³/d (透传)
浓缩池  →  66.7 m³/d (P=94%, 33%减量)
消化池  →  36.5 m³/d (P=92%, VS降解45%, 沼气产出)
脱水间  →  18.2 m³/d (P=78%, 82%减量)
干化    →   5.3 m³/d (P=25%, 95%减量)
```

### Phase 26 — PyInstaller 打包修复 (2026-05-18)
| # | 问题 | 根因 | 修复 |
|---|------|------|------|
| 89 | 打包后污泥节点点击新建无反应 | ModManager 用 importlib 动态加载 models/wuni_*.py，PyInstaller 静态分析无法追踪 | hiddenimports 加 6 个 wuni_* 模块 |
| 90 | 手动维护 hiddenimports 不可持续 | 每次新增模组都需手动加，遗漏就触发 bug | `hiddenimports += collect_submodules('models')` — 自动扫描 models/ 下所有子模块 |
| 91 | spec 中 output/ 和 data/ 含 ~$ 临时 Excel 文件导致打包权限错误 | Excel 锁定的临时文件无法读取 | data 改用 glob 筛选排除 ~$*；output 改为单独指定 .tex 文件 |

### Phase 27 — 社区模组运行时加载验证 (2026-05-18)
| # | 结论 | 机制 |
|---|------|------|
| 92 | EXE 运行时支持社区模组热加载，无需重打包 | bootstrap 提取 mods/ → ModManager 扫描 community/ → module_path 为空时走备选路径 → sys.path 加入 community/ → importlib 从文件系统加载 __init__.py |
| 93 | 核心模组 (module_path="models.xxx") 仍需重打包 | models/*.py 在 PYZ 归档中，新增需 PyInstaller rebuild |
| 94 | 社区模组 __init__.py 须 inline 定义 NodeBase 子类 | `from models.base` 始终可用（base 在 PYZ 中），独立 .py 文件无法被 frozen 环境 import |

### Phase 28 — PyInstaller 静态导入 + 动态模组最终验证 (2026-05-18)
| # | 问题 | 根因 | 修复 |
|---|------|------|------|
| 95 | collect_submodules 返回 34 模块但未进 PYZ | PyInstaller 在某些条件下忽略 hiddenimports 中由 collect_submodules 返回的条目 | models/__init__.py 增加 6 个 wuni_* 显式 `from . import` |
| 96 | bootstrap 旧 mods/ 目录导致新模组未提取 | 旧版 EXE 提取后跳过新版 EXE 的提取 | bootstrap.py 新增 `_merge_directory()` 合并模式 |
| 97 | 社区模组运行时动态加载验证 | 模拟 frozen 环境测试通过 | `importlib` 从文件系统加载 `__init__.py`，FrozenImporter 处理 `models.base` 导入 |

### 社区模组动态加载机制 (终版)

```
EXE 启动
  → bootstrap: merge_directory(MEPASS/mods → cwd/mods)  # 合并缺失文件
  → ModManager.scan(mods/community/)
  → 发现 my_mod/mod.json (无 module_path 字段)
  → sys.path += mods/community/
  → importlib.import_module("my_mod")             # PathFinder → 文件系统
  → __init__.py: from models.base import ...       # FrozenImporter → PYZ
  → __init__.py: from .calculator import MyNode    # 相对导入 → 同目录 .py
  → 注册 → UI 菜单出现
```

### Phase 29 — 新模组兼容性系统性修复 (2026-05-18)
| # | 问题 | 根因 | 修复 |
|---|------|------|------|
| 98 | 污泥节点被路由到方案浏览器 → 无参数面板/无结果 | `get_ui_behavior().skip_solution_browser` 仅对 io 阶段为 True | `skip_solution_browser` 改为对非水处理阶段(io/sludge/未来新增)自动为 True |
| 99 | `_auto_apply_recommended()` 对污泥节点调用方案枚举 | 同上，is_io=False 导致落入方案枚举分支 | 统一使用 `skip_solution_browser` 标志 |
| 100 | `get_config()` 对污泥节点可能 KeyError (若 ModManager 未就绪) | discretization.json 仅在 ModManager 加载后可用 | 6 个 wuni_* 离散化配置直接写入 DISCRETE_CONFIGS 作为安全网 |
| 101 | output_writer.py 1 处 try/except 模式遗漏 | 缩进不一致导致 replaceAll 未覆盖 | 手动修复 |

**架构原则 (Phase 29 确立)**:
- `get_ui_behavior().skip_solution_browser` = 非水处理阶段自动 True
- 水处理阶段白名单: `{primary, secondary, tertiary, mine_water}`
- 新增 process_stage 自动继承安全默认值，无需修改 UI 代码

### Phase 30 — 污泥方案空间枚举 + 多连接口 + 合并节点 (2026-05-18)
| # | 问题 | 根因 | 修复 |
|---|------|------|------|
| 102 | 污泥节点完全无待选方案 | `_vectorized_compute` 仅返回 dummy 零数组，solution_space 不接受 SludgeFlow | solution_space 新增 `enumerate_sludge()`；4 个污泥模块实现完整 `_vectorized_compute` |
| 103 | 方案浏览器不显示污泥方案 | `skip_sb=True` 跳过了污泥节点 | sludge 加入 solution_stages 白名单，`_show_browse_mode()` 支持 sludge 上下文 |
| 104 | 多端口汇集节点难看 | 6 个输入端在画布上拥挤 | 新建 `wuni_hebing` (污泥合并) 专用节点，1 输入端口允许多连 |
| 105 | 画布端无法多连到同一端口 | canvas_view 连接前清除已有线 | `connect_ports()` 对 sludge 端口免清除 |
| 106 | F5 后污泥节点结果不显示 | `_execute_sludge_pass()` 未写 `node._result` | 增加 `node._result = s_result` + `node.state = CLEAN` |
| 107 | nongsuo 变量重命名遗漏 | h_eff→h_eff_calc 后引用未更新 | 修复 2 处引用 |
| 108 | 污泥参数范围不符合 GB50014 | q_solid max=80→60, P_out 0.94→0.96, v_pipe min=0.6/0.8→1.0 | 对照标准修正 4 个模块参数 |

### 污泥方案空间

| 模块 | 自由变量 | 可行方案数 |
|------|---------|-----------|
| 污泥浓缩池 | n, q_solid, T_thicken | 48 |
| 污泥消化池 | n, θ_digest, η_VS, biogas_rate | 36 |
| 污泥脱水间 | n_machines, q_capacity, P_out | 104 |
| 污泥干化 | P_out, q_evap, η_thermal | 128 |

### v3.1 最终模块清单 (23 种)

| NODE_TYPE | 中文名 | process_stage | 方案空间 |
|-----------|--------|---------------|---------|
| wuni_hebing | 污泥合并 | sludge | — (无参数) |
| wuni_shusong | 污泥输送泵站 | sludge | — |
| wuni_nongsuo | 污泥浓缩池 | sludge | 48 |
| wuni_xiaohua | 污泥消化池 | sludge | 36 |
| wuni_tuoshui | 污泥脱水间 | sludge | 104 |
| wuni_ganhua | 污泥干化 | sludge | 128 |
| wuni_bengzhan | 污泥泵站 | sludge | — |

---

## 十三、v3.2 — MC式模组架构重构 (2026-05-18)

### Phase 31 — UI修复 + 回归测试
| # | 问题 | 修复 |
|---|------|------|
| 101 | solution_browser.py SyntaxError — load_node try无except | 补回缺失except块，清理悬挂except |
| 102 | self._get_free_keys() 方法不存在 | 改为 get_free_keys(node_type) 模块函数 |
| 103 | self._build_result_table() 方法不存在 | 表由 _build_ui() 构建，删除此调用 |
| 104 | _build_filter_ui 参数类型错误 | List[str] → List[Solution] |
| 105 | 新增 test_ui_import.py (6 tests) + test_mod_system.py (10 tests) | 169 tests |

### Phase 32 — 集中注册表 + 消除硬编码
| # | 变更 | 文件 |
|---|------|------|
| 106 | 创建 node_registry.py — 统一查询API: is_io_node/has_solution_space/resolve_class | new file |
| 107 | main_window.py 4处 try/except → _safe_ui_behavior → registry | main_window.py |
| 108 | output_writer.py 3处 try/except → _safe_is_io_node → registry | output_writer.py |
| 109 | solution_space.py 80行硬编码 compat maps → registry.resolve_class() | solution_space.py |
| 110 | graph_executor.py 50行 compat_modules → registry.resolve_class() | graph_executor.py |
| 111 | ModManager.load_all() → registry.register_from_mod_manager() | mod_manager.py |

### Phase 33 — 模组验证 + 安全加载
| # | 变更 | 文件 |
|---|------|------|
| 112 | mod_schema.json — JSON Schema 验证规范 | new file |
| 113 | _validate_mod_json() — 启动时自动验证 mod.json | mod_manager.py |
| 114 | ModManager.get_load_errors() / get_load_summary() | mod_manager.py |
| 115 | _validate_vectorized_output() — 检查 ok_*/val_*/concrete_m3 | mod_manager.py |
| 116 | UI 启动时检查模组状态 (_check_mod_status) | main_window.py |
| 117 | mod_tools.py — scaffold / validate / list CLI | new file |
| 118 | 新增 test_mod_validation.py (5 tests) | tests/ |

### Phase 34 — 污泥模块修复
| # | 问题 | 修复 |
|---|------|------|
| 119 | wuni_shusong/bengzhan _vectorized_compute 全零 → 0方案 | 完整实现向量化计算 |
| 120 | enumerate_sludge 参数顺序颠倒 → checks为空 | 交换 constraint_keys/names 参数 |
| 121 | CONSTRAINT_LIMITS 缺少全部污泥约束 → robustness=0 | 添加8个污泥约束条目 |
| 122 | tuoshui/ganhua/shusong/bengzhan 缺 concrete_m3 → cost=0 | 添加混凝土量估算 |

### Phase 35 — MC三层架构实现
| # | MC层 | 我们实现 | 文件 |
|---|------|---------|------|
| 123 | 类加载隔离 (ASM/Mixin) | importlib动态加载__init__.py | mod_manager.py |
| 124 | 资源命名空间 (modid:path) | node_type + per-mod discretization.json | discretization.json |
| 125 | constraint_limits内联 → 无需编辑 solution_space.py | discretization.json |
| 126 | estimator_type内联 → 无需编辑 fast_estimator.py | discretization.json |
| 127 | discover_all 始终扫描 community/ | mod_manager.py |
| 128 | _get_merged_configs 缓存失效刷新 | discretization.py |
| 129 | 注册与事件 (Event Bus) | on_register 生命周期钩子 | node_registry.py |
| 130 | 成本跳过列表 → NodeRegistry.is_io_node() | cost_estimator.py |

### Phase 36 — 二沉池社区模组 (MC式验证)
| # | 变更 | 结果 |
|---|------|------|
| 131 | mods/community/erchunchi/ — 仅3文件, 零源码修改 | 72可行方案, robust=0.335, cost=87-175w |
| 132 | 酸测试: 新鲜进程 → enumerate('erchunchi') → 72 sols ✅ | 无需手动 load_all() |
| 133 | 修复 kw_ningjiao 缺少 val_gt → 0 warnings | 23/23 mods, 0 errors |

### v3.2 模块清单 (24种)
| NODE_TYPE | 中文名 | process_stage | 来源 |
|-----------|--------|---------------|------|
| erchunchi | 辐流式二沉池 | secondary | 🆕 社区模组 |

### 添加新模组 — 仅需3文件
```
mods/community/my_mod/
├── mod.json              ← 元数据 + 端口 + 参数
├── __init__.py           ← NodeBase 子类
└── discretization.json   ← 离散化 + 约束 + 限值 + 估算器类型
```
零源代码修改: main_window.py ❌ output_writer.py ❌ discretization.py ❌
solution_space.py ❌ graph_executor.py ❌ cost_estimator.py ❌
