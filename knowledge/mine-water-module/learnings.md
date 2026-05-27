# 矿井水处理模块 — 学习记录

> 日期: 2026-05-16
> 来源: docs/dlc.docx — 煤炭矿井水处理站设计计算
> 新增: 5 个模块文件 + 6 处注册修改

---

## 一、模块清单

| 文件 | NODE_TYPE | 中文名 | 核心功能 |
|------|-----------|--------|---------|
| `kw_input.py` | kw_input | 矿井水输入 | 涌水量/水质输入节点 |
| `kw_tiaojiechi.py` | kw_tiaojiechi | 矿井水调节池 | HRT≥6h, SS去除~30%, 煤颗粒沉降 |
| `kw_chenshachi.py` | kw_chenshachi | 平流沉砂池 | 水平流速 0.15~0.3m/s, 停留 30~60s |
| `kw_ningjiao.py` | kw_ningjiao | 混凝反应池 | 快速混合 + 絮凝, PAC/PAM 投加 |
| `kw_cifenli.py` | kw_cifenli | 磁分离 | 磁盘高梯度磁分离, 磁种回收 |

所有模块 NODE_CATEGORY = "矿井水处理"，UI 菜单独立分组。

## 二、关键设计参数

### 矿井水调节池 vs 市政调节池
| 参数 | 矿井水 | 市政 | 原因 |
|------|--------|------|------|
| HRT | 6~12h (8h) | 4~12h (6h) | 矿井水流量波动大 |
| SS去除 | 30% | 0% | 煤粉预沉淀 |
| 搅拌功率 | ≥5 W/m³ | ≥12 W/m³ | 避免打碎煤颗粒 |
| 池底坡度 | ≥1% | 无要求 | 煤泥收集 |

### 平流沉砂池 vs 旋流沉砂池
| 参数 | 平流 | 旋流 | 
|------|------|------|
| 池型 | 矩形 | 圆形 |
| 水平流速 | 0.15~0.3 m/s | N/A |
| 停留时间 | 30~60s | 30~60s |
| 表面负荷 | N/A | 150~200 m³/(m²·h) |
| 砂斗形式 | 多斗式棱台 | 圆锥台 |

### 混凝反应池
- 混合 G=300~800 s⁻¹, t=30~120s
- 絮凝 G=30~80 s⁻¹, t=15~30min
- GT 校核: 混合 1e4~5e4, 絮凝 1e4~1e5
- PAC 30mg/L + PAM 0.5mg/L

### 磁分离
- 磁盘过滤速度 200~500 m/h
- 磁种 50mg/L, 回收率≥95%
- SS 去除~85%, TP 去除~70%

## 三、注册位置

| 文件 | 修改内容 |
|------|---------|
| `ui/main_window.py` | +5 imports, +5 NODE_REGISTRY, +4 FORMULAS, +1 菜单分类 |
| `models/discretization.py` | +4 DISCRETE_CONFIGS 条目 |
| `models/cost/unit_prices.py` | +4 EQUIPMENT 条目 |
| `models/cost/cost_estimator.py` | kw_input 加入跳过列表 |
| `models/cost/report_writer.py` | +4 FLOW_ORDER 条目 |

## 四、测试结果

- 10 个文件语法检查全部通过
- 4 个模块创建、计算、校核均正常
- 离散化网格: 81 / 72 / 144 / 24 组合
- 约束校核正常触发（水深、堰负荷）
