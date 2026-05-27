# 📚 .sisyphus 学习记录分类索引

> **项目**: 排水工程设计工具 (Drainage Design Tool)
> **索引生成**: 2026-05-27 | **收录**: 27 条记录 / 7 个子目录
> **覆盖周期**: 2026-05-16 ~ 2026-05-27

---

## 一、架构与代码基础

### 1.1 代码库全景
| 文件 | 日期 | 摘要 |
|------|------|------|
| `codebase-comprehensive-2026-05-17.md` | 05-17 | v3.2 完整架构: 三层分层(UI/控制/模型)、17种节点类型清单、数据流、每个模块的详细代码级分析(854行) |
| `codebase-learning-2026-05-16.md` | 05-16 | 初次代码库学习: 文件结构、NodeBase基类、WaterFlow/WaterQuality模型、端口系统 |
| `mc-architecture-mapping-2026-05-18.md` | 05-18 | MC式模组架构三层映射: 类加载→资源标识→注册表，24模组详细剖析(629行) |

### 1.2 架构演进阶段
| 阶段 | 关键文件 | 里程碑 |
|------|---------|--------|
| v3.2 MC式 | `work-2026-05-18.md` | 自包含模组架构上线: mod.json + __init__.py 零框架修改 |
| v3.3 双水线 | `session-retrospective-2026-05-20.md` | 矿井水 8 模组 + 社区模组 + 标准化输出契约 L/B/D/H |
| v3.4 加固 | `session-retrospective-2026-05-20.md` | 消除硬编码→约定自动发现, 23模组迁移, 成本估算统一 |
| v3.5 高程+UI | `session-learnings-2026-05-23.md` | 高程计算系统, 集配水模组, 公式显示, 约束面板 |
| v4.2 硬编码消除 | `session-learnings-2026-05-24-s2.md` | DISCRETE_CONFIGS→JSON, CONSTRAINT_LIMITS→JSON, elevation_loss迁移, MC迁移完成 |
| v4.3 矿井水审计 | `session-learnings-2026-05-24-s3.md` | 4模组全量重写, 标签自包含(labels.json), gaomidu修复, elevation_loss迁移 |
| v4.3 参数完整性 | `session-learnings-2026-05-24-s4.md` | PARAM_TABLE清零, 31 mod.json参数补全, 符号/单位全线审计, 全局param_table污染修复, node_type感知参数查找 |
| v4.4 全链路修复 | `session-learnings-2026-05-25.md` | CASS长宽比诊断, 方案浏览器一致性, V型滤池14参数, 全局34模组dtype审计, 污水提升泵站 |
| v4.5 标签系统+矿井水 | `session-learnings-2026-05-25-s2.md` | 统一维度过滤(split_dimensions), 361标签+185向量化字段, 中英文双模式分类, 矿井水4模组修复, labels.json必需, 打包55MB |
| v4.5 合规审计+公式 | `session-learnings-2026-05-25-s3.md` | 47项参数不合规修复(空单位/缺键/缺中文名), 三层反漏标签防线, 83维度公式全覆盖, CI自动发现测试 |
| v4.5-s4 约束+QA+标注 | `session-learnings-2026-05-25-s4.md` | CASS θc' (4-79)替换+硝化校核, 全模组QA(Q=0.57), P0砂斗Bug/P1 CASS参数/P2 13模组[单池]/[总]标注, 418维度公式/单位运行时审计 |
| v5.0 架构升级 | `session-learnings-2026-05-26.md` | 作用域系统(scope=), 412条目标签迁移至 labels.json["dimensions"], V型滤池Q_g2 NameError修复, CASS约束+参数, 诊断去重, MOD_SPEC v5.0 重写 |
| v5.1 约束修复+验证器 | `session-learnings-2026-05-27.md` | 双路径不同步Bug根因+修复(_filter_feasible动态检查), 约束面板下拉收缩修复, 跨类别参数联动, Mod Validator嵌入式系统(170检查 0FAIL), aao/gdys Error修复, 13处ParamDef同步, 全项目生产审计(6.8/10) + plan.md |

---

## 二、Bug 修复记录

### 2.1 数据流 (P0)
| Bug | 文件 | 记录 | 日期 |
|-----|------|------|------|
| 流量传输: 零值传播导致全链报废 | `graph_executor.py` | `flow-fix-2026-05-19.md` | 05-19 |
| CombinerNode 面板始终显示 570 L/s | `main_window.py` | `flow-fix-2026-05-19.md` | 05-19 |
| 方案=0: 旋流沉砂池等无可行方案 | `main_window.py` | `session-retrospective-2026-05-20.md` | 05-20 |
| `NoneType.node_id`: 无法打开矿井水项目 | `node_registry.py` | `session-retrospective-2026-05-20.md` | 05-20 |

### 2.2 计算精度 (P1)
| Bug | 文件 | 记录 | 日期 |
|-----|------|------|------|
| 水头损失=0: 格栅 s 单位 m→mm 1000× 误差 | `geshan.py` / `discretization.json` | `session-retrospective-2026-05-20.md` | 05-20 |
| 巴氏计量槽崩溃: numpy array → dict 方法 | `cost_estimator.py` | `session-retrospective-2026-05-20.md` | 05-20 |
| 格栅 β 硬编码: 阻力系数计算偏小 | `geshan.py` | `session-learnings-2026-05-24.md` | 05-24 |

### 2.3 UI 交互 (P2)
| Bug | 文件 | 记录 | 日期 |
|-----|------|------|------|
| 新建节点缩放后位置漂移 | `canvas_view.py` | `session-learnings-2026-05-24.md` | 05-24 |
| 节点标题字体不随缩放变化 | `canvas_view.py` | `session-learnings-2026-05-24.md` | 05-24 |
| 结果面板崩溃: Text DISABLED 下 delete() | `main_window.py` | `session-learnings-2026-05-23.md` | 05-23 |
| 方案浏览器 3× 重复方案(bar_shape free) | `geshan.py` + `discretization.py` | `session-learnings-2026-05-24.md` | 05-24 |
| 方案浏览器与结果面板展示不同方案 | `solution_browser.py` | `session-learnings-2026-05-25.md` | 05-25 |
| 污泥线保存/加载丢失 | `file_manager.py` | `work-2026-05-18.md` | 05-18 |

### 2.4 构建/环境 (P3)
| Bug | 文件 | 记录 | 日期 |
|-----|------|------|------|
| SyntaxError: EXE 启动崩溃 | `mod_manager.py` | `session-retrospective-2026-05-20.md` | 05-20 |
| .pyc 缓存遮蔽源码 | — | `session-retrospective-2026-05-20.md` | 05-20 |
| 编码损坏 + 文件截断 | `unit_prices.py` + `water_quality_node.py` | `session-learnings-2026-05-23.md` | 05-23 |

---

## 三、新增功能

### 3.1 模组
| 模组 | 类型 | 记录 | 日期 |
|------|------|------|------|
| 集配水: jishuijing/peishuijing/jipeishuijing/peishuiqu | 新增 4 模组 | `session-learnings-2026-05-23.md` | 05-23 |
| 高程: jcws_smbg/gdys_stss | 新增 2 模组 | `session-learnings-2026-05-23.md` | 05-23 |
| 矿井水全流程: kw_* 8 模组 | 新增 | `session-retrospective-2026-05-20.md` | 05-20 |
| 社区: wuni_tisheng/bashi_jiliangcao | 新增 2 模组 | `work-2026-05-18.md` | 05-18 |

### 3.2 系统
| 功能 | 文件 | 记录 | 日期 |
|------|------|------|------|
| 全厂高程计算 | `elevation_calculator.py` | `session-learnings-2026-05-23.md` | 05-23 |
| 结果面板公式子行 | `main_window.py` | `session-learnings-2026-05-23.md` | 05-23 |
| 高程面板 (Tab) | `main_window.py` | `session-learnings-2026-05-23.md` | 05-23 |
| 约束面板下拉/确定按钮优化 | `constraint_panel.py` | `session-learnings-2026-05-24.md` | 05-24 |
| 枚举值可读显示 | `dimension_labels.py` | `session-learnings-2026-05-24.md` | 05-24 |

---

## 四、工程概算与成本系统

| 记录 | 关键内容 |
|------|---------|
| `codebase-comprehensive-2026-05-17.md` | 成本估算 5 模块架构: cost_estimator/fast_estimator/unit_prices/report_writer/pipe_network_cost |
| `work-2026-05-18.md` | 26 模组成本审计: 发现 3 缺陷并修复, `_val()` 5级匹配验证 |
| `session-retrospective-2026-05-20.md` | 标准化输出契约 L/B/D/H → 成本估算从 5 函数简化为 2 通用函数 |
| `pdf-knowledge/` | 2019黑龙江定额 OCR 提取, vol1/vol5/vol6 水处理工程量 |

---

## 五、规范与参考标准

| 标准 | 用途 |
|------|------|
| GB50014-2021 | 室外排水设计标准 (格栅、沉砂、初沉、CASS、滤池等) |
| GB 18918-2002 | 城镇污水处理厂污染物排放标准 (一级A) |
| GB 3838-2002 III类 | 地表水环境质量标准 (矿井水排放) |
| CJJ 131-2009 | 城镇污水处理厂污泥处理技术规程 |
| GB 50500-2013 | 建设工程工程量清单计价规范 |
| 2019 黑龙江省市政工程消耗量定额 | 成本估算单价来源 |

---

## 六、关键设计模式与约定

| 模式 | 说明 | 来源记录 |
|------|------|---------|
| **MC 自包含模组** | 一个文件夹 = 一个模组, mod.json + __init__.py | `mc-architecture-mapping-2026-05-18.md` |
| **约定自动发现** | snake_case → PascalCase+Node, 90%+模组无需注册 | `session-retrospective-2026-05-20.md` |
| **显示型自由变量** | 同时入 free(UI下拉) 和 fixed(实际值), get_free_keys 排除 | `session-learnings-2026-05-24.md` |
| **L/B/D/H 标准契约** | 向量化必须输出矩形(D=0)或圆形(L=B=0)标准字段 | `session-retrospective-2026-05-20.md` |
| **双 mods 目录同步** | mods/(测试) 和 ddesign_tool/mods/(运行时) 必须一致 | 多条记录 |
| **SludgeFlow 独立通道** | SLUDGE 端口类型 → execute_sludge() → 与水线隔离 | `session-learnings-2026-05-23.md` |
| **向量化 val_* 必须设置** | 缺少 val_* → robustness=0 → 方案排序退化 | `MOD_SPEC.md` |
| **[v4.5] 过滤单一源** | Excel/UI/概算报告共用 `split_dimensions()` | `session-learnings-2026-05-25-s2.md` |
| **[v4.5] 中英文双模式分类** | `get_dimension_category()` 中文关键字 + 英文字段名模式匹配 | `session-learnings-2026-05-25-s2.md` |
| **[v4.5] 参数零空单位** | 无量纲填 `"-"`, 绝不空字符串; MOD_SPEC §2.3 | `session-learnings-2026-05-25-s3.md` |
| **[v4.5] result.params 完整** | calculate() 的 result.params 必须包含 _default_params 全部键 | `session-learnings-2026-05-25-s3.md` |
| **[v4.5] 维度公式全覆盖** | 显式传 formula= 或 DIM_FORMULAS 有对应条目 | `session-learnings-2026-05-25-s3.md` |
| **[v4.5] CI 自动发现** | test_dimension_labels.py 自动扫描 280 字段验证标签 | `session-learnings-2026-05-25-s3.md` |

---

## 七、环境与工具

| 记录 | 内容 |
|------|------|
| `environment-fix/` | Python 环境修复: 路径配置、依赖安装、venv 设置 (4文件) |
| `packaging-guide-2026-05-19.md` | PyInstaller 打包指南: ddesign_tool.spec 配置、资源嵌入 |
| `usage-guide-2026-05-19.md` | 用户操作指南: 节点添加/连线/F5执行/导出流程 |
| `progress-2026-05-16.md` | 开发进度跟踪 |
| `debug-2026-05-17.md` | 调试记录 |
| `constraint-audit-2026-05-16.md` | 约束系统审计 |

---

## 八、用户反馈修复专题

| 目录 | 内容 |
|------|------|
| `user-feedback-fixes/` | 水质UI修复、连线Bug修复、综合反馈处理 (3文件) |
| `midterm-audit/` | 中期审计记录 |
| `mine-water-module/` | 矿井水模块专项 |
| `final-documentation/` | 最终文档整理 |
| `pdf-knowledge/` | PDF 定额知识提取: OCR管道、实现计划、成本估算 (含 OCR 输出) |

---

## 九、时间线总览

```
2026-05-16  代码库初次学习 · 约束审计 · 进展跟踪
2026-05-17  深度代码学习(854行) · Debug计划(373行) · 环境修复
2026-05-18  MC架构映射(629行) · 社区模组(2个) · 概算审计 · 打包(56.7MB)
2026-05-19  流量传输修复(3 Bug) · 打包指南 · 使用指南 · 架构流程图
2026-05-20  v3.3→v3.4 架构加固: 50+文件, 消除硬编码, 标准化契约
2026-05-23  v3.5: 高程系统 + 集配水模组 + UI优化(公式/约束/高程面板)
2026-05-24  Canvas修复 · 格栅β参数化 · 约束面板优化 · v4.0~v4.3 架构加固 · 矿井水4模组重写 · 参数完整性审计
2026-05-25  v4.4: 方案浏览器_select_applied一致化 · CASS长宽比诊断 · DAG三通道架构学习 · 高程约束溯源
2026-05-25  v4.5: 统一维度过滤(split_dimensions) · 361标签系统 · 中英文双模式分类 · 矿井水4模组修复 · labels.json必需 · 打包55MB
2026-05-25  v4.5-s3: 47项参数不合规修复 · 三层反漏标签防线 · 83维度公式全覆盖 · CI自动发现测试
2026-05-25  v4.5-s4: CASS θc' 约束(4-79) · 全模组QA · P0砂斗/P1 CASS/P2标注 · 418维度公式审计
2026-05-26  v5.0: 作用域系统 · 412标签迁移 · 诊断去重 · MOD_SPEC 重写
2026-05-26  v5.0-s2: UV公式(4-134~4-149)重写 · CASS污泥修正 · θc调优 · 打包
2026-05-27  v5.1: 约束双路径Bug修复 · 约束面板联动 · Mod Validator(170检查) · 生产审计(6.8/10) · plan.md
2026-05-27  v5.2: UI全面恢复 (水质编辑卡片/全流程水质追踪/三分类结果面板/公式独立行) · 生产级代码质量 (flake8 530→7, threading.Lock) · 约束系统修复 (3模组缺keys, 动态检查OR硬编码) · JSON Schema验证 · QualityPanel提取 · 内嵌自检模块 · KwInputNode进厂标高 · 全局约束审计 · 测试 433→565 · gdys_stss水泵扬程修复 · KwInputNode同步崩溃修复 · Canvas销毁保护
```

---

> **最后更新**: 2026-05-27 | **Sisyphus**
