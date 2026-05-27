# 2026-05-25 Session 4 — CASS 约束校核 + 全模组 QA + 单池/总体标注 + 公式完整性审计

> **日期**: 2026-05-25 | **会话**: Sisyphus — 约束增强 + 质量保证 + 标注规范化
> **修改文件**: 15+ | **测试**: 228 passed

---

## 一、CASS 污泥龄校核 — 公式 (4-79) 替换

### 用户需求
> θc' = (V·X·f) / ΔXv，校核 θc' ≥ θc，硝化时 15~30d

### 旧公式 vs 新公式

| | 旧 (3-70) | 新 (4-79) |
|------|------|------|
| 公式 | `V_main × X_kg / Px_total` | `V_main × X_kg × f / Px_bio` |
| 分子 | 总MLSS (含惰性) | 挥发性MLSS (×f=0.75) |
| 分母 | 总污泥 (生物+非生物) | 挥发性污泥产量 ΔXv |
| 约束 | `≥ θc_design` (仅下界) | `θc_design ≤ θc' ≤ 30d` (上下界) |
| 默认值 | ~64 d (通过) | **87.2 d (失败)** ← 新增上界30d |

### 修改文件
- `cass/__init__.py`: calculate() L207-227 (替换+新增), _vectorized_compute() dtype 新增 ok_nitrification/val_nitrification
- `cass/discretization.json`: constraint_keys +1 (nitrification), names/limits/types 更新
- `cass/labels.json`: vec_fields theta_c_actual 标签 θc→θc'

---

## 二、全局参数审计 — 正则陷阱

### 误报根因
v1 审计脚本使用正则 `r'^\s*"([^"]+)"\s*:\s*(.+?)\s*,?\s*$'` 逐行解析 `_default_params()`，但 CASS 等模组**同行多键**（如 `"n": 4, "Ns": 0.08, ...`），每行只匹配第一个键 → 漏检严重（CASS 19键仅捕获7个）。

### 修正
改用 Python 运行时直接调用 `cls._default_params()` 获取完整键集 → **全部 34 模组 `_default_params` 与 `mod.json` 键完全对称**，零遗漏。

### 关键架构洞察
`_default_params` 是**运行时唯一数据源**：
- `NodeBase.__init__` (L614): `self._params = dict(self._default_params())` — 初始化
- `NodeBase.reset_params` (L786): 同上 — 重置
- `get_param` (L754): `self._params.get(key, 0.0)` — 读取

**三个数据源的分工**：
| 来源 | 角色 | 内容 |
|------|------|------|
| `_default_params` | 运行时默认值 | `{key: default_value}` |
| `mod.json` | 元数据/UI信息 | `{key, symbol, name, unit, min, max, step}` |
| `_build_param_defs` | UI滑块子集 | `_default_params` 的子集 |

---

## 三、全模组 QA — Q=0.57 m³/s 逐模组测试

### 测试条件
- 市政线: Q_design=0.57 m³/s, Q_avg=34760.7 m³/d, Kz=1.4
- 矿井水线: Q_design=0.10 m³/s, Q_avg=8640 m³/d, Kz=1.0
- 水质: BOD5=200, COD=400, SS=220, NH3N=35, TN=45, TP=5

### 发现的问题

| 类别 | 修复前 | 修复后 |
|------|--------|--------|
| 歧义维度 (单池/总体不清) | 15 模组 | **4 模组** (↓73%) |
| 离谱数值 | 3 模组 (5 alerts) | **0 模组** |
| CASS 池长 L | 181m | **84m** (↓54%) |
| CASS 长宽比 | 18.1 | **7.0** |
| CASS θc' | 87.2d FAIL | **28.2d PASS** |
| kw_chenshachi h_斗 | 0.0m | **0.14m** |

### P0: kw_chenshachi 砂斗容积=0
**根因**: hopper_bottom=0.6 等于单格宽度 B=0.6 → `h_hopper = (B-b₂)/2×tan(α) = 0`

**修复**: hopper_bottom 0.6→0.4 (GB50014-2021 §7.4.6 建议下口 0.4~0.5m)，同步更新 _default_params / _build_param_defs / mod.json / discretization.json

**效果**: h_斗 0→0.14m，砂斗总容积 0→1.3m³ (36斗)，「砂斗容积足够」FAIL→PASS ✅

### P1: CASS 默认参数调整
**参考**: GB50014-2021 §7.6 — Ns=0.05~0.15, H=4.0~6.0m；实际工程 Ns=0.11~0.15

**修改**: Ns 0.08→0.12, H_max 5.0→6.0m
**效果**: V_main 31455→20970 m³, L 181→84m, θc' 87.2→28.2d

### P2: 单池/总体标注规范化
**标注约定**: 当模组有池数 n>1 时，每个维度加 `[单池]`/`[单格]`/`[单系列]`/`[总]` 前缀

**修改模组 (13个)**:
| 模组 | 新增标注 | 维度举例 |
|------|---------|---------|
| AAO | `[单系列]` | 厌氧/缺氧/好氧区容积, 池长L, 池宽B |
| CASS | `[单池]` | 选择区容积 |
| chenshachi | `[单池]` | 有效容积, 砂斗所需容积 |
| chuchenchi | `[单池]` | 沉淀面积 F |
| gaomidu | `[单池]` | 混合区/絮凝区容积, 沉淀区面积 |
| kw_gaomidu | `[单池]` | 同上 |
| vxinglvchi | `[单格]` | V型槽断面积 |
| jipeishuijing | `[总]` | 有效容积 V |
| jishuijing | `[总]` | 有效容积 V |
| peishuijing | `[总]` | 有效容积 V |
| peishuiqu | `[总]` | 过水面积 A |
| kw_chenshachi | `[总]` | 需砂斗容积 |
| kw_tiaojiechi | `[总]` | 日产湿泥体积, 贮泥容积需求 |
| wuni_tisheng | `[集水池]` | 集水池容积 |

**安全保证**: 所有改名维度均已有显式 `formula=` 参数，改名不影响公式显示。

---

## 四、公式/单位/分类运行时完整性审计

### 审计方法
运行每个模组 `calculate()` → 检查 `NodeResult.dimension_formulas` 和 `dimension_categories`

### 结果

| 指标 | 数值 |
|------|------|
| 测试模组 | 32 |
| 总维度数 | **418** |
| 缺失公式 | 5 (全部为设计意图) |
| 缺失分类 | **0** ✅ |
| 单位异常 | **0** ✅ |

### 修复
- chuchenchi: `出水堰长` 新增 `formula="L = 2π(D-1), 双侧堰"`
- erchunchi: `出水堰长` 新增 `formula="L = 2π(D-1), 双侧堰"`

### 5 项"缺失公式"均为设计意图
| 模组 | 维度 | 原因 |
|------|------|------|
| cass | 进水BOD5 | 进水水质参考值，非计算 |
| cass | 出水BOD5 | 一级A标准值 10 mg/L，非计算 |
| jipeishuijing | 出水方向数 | 用户设定参数 |
| peishuijing | 出水方向数 | 用户设定参数 |
| peishuiqu | 出水口数 | 用户设定参数 |

---

## 五、巴氏计量槽 + 污水提升泵站 — 误报警解除

### 初始审计误报
v1 审计脚本仅检查 `__init__.py`，但社区模组的实际代码在 `models/` 子模块中 → 误判 `bashi_jiliangcao.b` 和 `wuni_tisheng` 全部 6 参数为"未使用"

### 实际验证
- **bashi_jiliangcao**: `b` 在 `bashi_jiliangcao.py` L77 `get_param("b")` → L96 `B_channel = b × 3.0` ✅
- **wuni_tisheng**: 全部 6 参数 (n_work/H_st/v_suction/v_discharge/L_suction/L_discharge) 在 `wuni_tisheng.py` L84-89 读取 → L119-129 Manning 水头损失 + 总扬程计算 ✅

---

## 🔴 铁律汇总 (新增)

1. **正则审计不可靠**: 同行多键模式导致严重漏检，必须用 Python 运行时直接调用方法获取完整数据
2. **社区模组子模块**: 审计必须递归检查 `models/` 子目录中的 `.py` 文件
3. **公式完整性**: 改名 add_dimension 前确认已有显式 `formula=` 参数，否则需同步补公式
4. **单位审计用运行时**: regex 解析 add_dimension 极易漏检多行调用，运行时检查 `dimension_formulas`/`dimension_categories` 更可靠
5. **CASS 约束必须上下界**: 污泥龄仅下界会导致 87d 也通过，加上界 30d 后才真正有意义
6. **砂斗下口 < 格宽**: 平流沉砂池 hopper_bottom 必须小于单格宽度，否则 h_hopper=0

---

## 六、修改文件汇总

| 文件 | 改动 | 类型 |
|------|------|------|
| `cass/__init__.py` | θc' 公式替换 + 硝化校核 + Ns/H_max 默认值 | 约束+参数 |
| `cass/discretization.json` | constraint_keys +1, Ns grid +0.15 | 配置 |
| `cass/labels.json` | θc→θc' 标签 | 标签 |
| `kw_chenshachi/__init__.py` | hopper_bottom 0.6→0.4 | Bug修复 |
| `kw_chenshachi/discretization.json` | hopper_bottom 0.6→0.4 | 配置 |
| `kw_chenshachi/mod.json` | hopper_bottom 0.6→0.4 | 配置 |
| `cass/mod.json` | Ns 0.08→0.12, H_max 5.0→6.0 | 配置 |
| 13× `__init__.py` | add_dimension 前缀标注 | 标注 |
| `chuchenchi/__init__.py` | 出水堰长 +formula | 公式 |
| `erchunchi/__init__.py` | 出水堰长 +formula | 公式 |

---

> **记录者**: Sisyphus | **版本**: v4.5-s4 | **日期**: 2026-05-25
