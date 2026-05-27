# 模组系统架构审视与多水源泛化修复 — 2026-05-20

## 🎮 与 Minecraft 模组系统的对比

| 维度 | Minecraft (Forge/Fabric) | 排水工程设计工具 |
|------|--------------------------|-------------------|
| **模组载体** | JAR 文件放入 `mods/` | 文件夹放入 `mods/core/` 或 `mods/community/` |
| **元数据** | `mods.toml` / `fabric.mod.json` | `mod.json`（单行紧凑 JSON） |
| **代码注册** | `@Mod` 注解 + 事件总线 | `ModManager.discover_all()` → `load_mod()` → `_register_node()` |
| **自动发现** | ClassLoader 扫描 `@Mod` | 目录遍历 `_scan_directory()` → 读取 `mod.json` |
| **UI 集成** | 注册 Item/Block → 自动出现在创造模式菜单 | 注册 node_type → 自动出现在右键菜单（按 process_stage 分组） |
| **热加载** | ❌ 需重启 | ⚠️ `community/` 每次扫描，`core/` 仅首次 |
| **依赖系统** | `depends`, `after`, `before` | ❌ 未实现（仅 `dependencies: []` 占位） |
| **版本兼容** | `versionRange` 语义化检查 | ❌ 未实现 |
| **模组 API** | 事件、mixin、capability | 通过 `NodeBase` 基类 + `PortType` 端口体系隐式约定 |
| **社区生态** | CurseForge/Modrinth 分发 | `community/` 目录（本地优先） |

### 结论

这个项目的模组系统在**核心循环**上完整复刻了 MC 模式：**"创建模组文件夹 → 编写 mod.json + 代码 → 放入目录 → 自动注册到 UI 菜单/方案浏览器/概算系统"**。28 个模组中 3 个为社区模组（`erchunchi` 辐流二沉池、`bashi_jiliangcao` 巴氏计量槽、`wuni_tisheng` 污泥提升泵站），证明社区模组路径已打通。

**缺失**：依赖管理、版本兼容检查、模组间 API。这些对当前规模（28 模组、单人开发）影响不大，但对于真正的社区生态是必需的。

---

## 🐛 本次会话修复的系统性 Bug（多水源泛化）

### 根因：系统最初为单一污水线设计，所有硬编码默认值和回退逻辑都假设 `Q_design=0.57, Kz=1.4`

添加矿井水模块后（`Q_design=0.761, Kz=1.5`），隐藏耦合全部暴露。

### 修复清单（10 项）

| # | 文件 | 行号 | 问题 | 修复 |
|---|------|------|------|------|
| 1 | `main_window.py` | 902 | `q = 0.57` fallback | 优先从 `r.params["Q_design"]` 读取 |
| 2 | `main_window.py` | 919 | `Kz=1.4` 硬编码 | 从 `r.params["Kz"]` 提取 |
| 3 | `main_window.py` | 919 | `Q_avg = total_flow * 86400 / 1.4` | 优先直接读 `r.params["Q_avg_daily"]` |
| 4 | `main_window.py` | 370 | `be.get_param("Q_design")` 读处理节点 | 改用 `_trace_upstream_context()` |
| 5 | `main_window.py` | 896 | `'m3/s' in u` 不匹配 `'m³/s'` (上标³) | 同时检查 `'m\u00b3/s'` |
| 6 | `main_window.py` | ~910 | 已计算处理节点 `q=0` 后放弃 | 递归追踪其上游 IO 节点 |
| 7 | `main_window.py` | 927 | 未计算处理节点不递归 | 添加 `else: rec_flow = self._trace_upstream_context(pid)` |
| 8 | `main_window.py` | 869 | `Kz=1.4` 无上游回退 | 从 `pipe_node.get_param("Kz")` 读取 |
| 9 | `main_window.py` | 1265,1415 | 出水标准硬编码一级A | `_get_effluent_std()` 按水类型选择 III类/一级A |
| 10 | `output_writer.py` | 197 | Excel 出水标准硬编码 | 按 `be.NODE_TYPE.startswith("kw_")` 判断 |

### 新增保护措施

- **10 个模块的零流量守卫**：`_vectorized_compute` 中 `if flow.Q_design <= 0: return np.zeros(N, dtype=dtype)`
- **MODS_GUIDE.md** 新增 3 处：CODE RULES、vectorized 模板、Common AI Mistakes
- **`_get_effluent_std()`** 辅助方法：按 `NODE_TYPE.startswith("kw_")` 或 `NODE_CATEGORY == "矿井水处理"` 自动选标准

---

## 📊 当前模组统计

```
总计: 28 模组 (25 core + 3 community)
  市政污水处理: 18 模组 (io/primary/secondary/tertiary/sludge)
  矿井水处理:   8 模组 (io + mine_water)
  社区模组:     3 模组 (community/)
```

### 市政污水处理（18）
| Stage | 模组 |
|-------|------|
| io | 管网输入 (pipe_network) |
| primary | 调节池, 粗格栅, 细格栅, 旋流沉砂池, 辐流初沉池 |
| secondary | CASS反应器, AAO反应器, 辐流式二沉池 (community) |
| tertiary | 高密度沉淀池, V型滤池, 紫外消毒池 |
| sludge | 污泥合并, 污泥输送泵站, 污泥浓缩池, 污泥消化池, 污泥脱水间, 污泥干化, 污泥提升泵站 (community) |

### 矿井水处理（8）
| Stage | 模组 |
|-------|------|
| io | 矿井水输入 (kw_input) |
| mine_water | 矿井水调节池, 平流沉砂池, 混凝反应器, 磁分离, 矿井水高密度沉淀池, 矿井水V型滤池, 矿井水紫外消毒池 |

### 社区模组（3）
| 模组 | 目录 |
|------|------|
| 辐流式二沉池 (erchunchi) | `community/erchunchi/` |
| 巴氏计量槽 (bashi_jiliangcao) | `community/bashi_jiliangcao/` |
| 污泥提升泵站 (wuni_tisheng) | `community/wuni_tisheng/` |

---

## 🏗️ 架构设计原则（固化到指南）

1. **IO 节点定义流量参数**（Q_design/Q_avg_daily/Kz），处理节点接收上游 flow 对象
2. **`_vectorized_compute` 必须包含零流量守卫**：`if flow.Q_design <= 0: return np.zeros(N, dtype=dtype)`
3. **禁止在 `_trace_upstream_context` 中硬编码流量默认值**：始终从上游节点追踪
4. **出水标准按水类型自动选择**：不硬编码一级A
5. **单位字符串匹配需兼容上标³**：同时检查 `m3/s` 和 `m³/s`
6. **递归上游追踪**：处理节点无流量时应递归到 IO 节点

---

## 🔮 待改进

| 优先级 | 项目 | 说明 |
|--------|------|------|
| 高 | 模组依赖系统 | `mod.json` 中 `dependencies` 字段目前仅占位 |
| 高 | 版本兼容检查 | 无 `min_app_version` 或语义化版本匹配 |
| 中 | 模组热加载 | `core/` 目录需要重启，应改为运行时检测 |
| 中 | 模组 API 文档 | 目前仅靠 `NodeBase` 基类约定，缺乏显式 API |
| 低 | 模组市场/分发 | 无远程仓库支持，仅本地 `community/` 目录 |
| 低 | 模组间事件系统 | 无 `on_node_calculated` 等生命周期钩子 |
