# 2026-05-24 会话学习记录 — UI修复 + 格栅模组增强 + 约束面板优化

> **日期**: 2026-05-24 | **测试**: 251 passed | **修改文件**: 12+

---

## 一、Canvas 画布 Bug 修复

### Bug 1: 新建节点位置缩放后漂移
| 项目 | 内容 |
|------|------|
| 文件 | `src/ui/canvas_view.py` — `_on_add_node_callback` |
| 根因 | 右键菜单 `_canvas_xy(event)` 返回 Canvas 坐标，但 `add_node()` 将其当作世界坐标再次乘以 `self._scale` → 每次缩放后漂移累积 |
| 修复 | `wx = x / self._scale; wy = y / self._scale` → 先转换为世界坐标再传递 |

### Bug 2: 节点标题字体不随缩放变化
| 项目 | 内容 |
|------|------|
| 根因 | `tkinter.Canvas.scale()` 只变换几何坐标，不改变 `itemconfig` 中的 `font` 大小 |
| 修复 | ① `NodeItem` 新增 `_title_id`/`_type_id` 属性 + `update_text_fonts(scale)` 方法 ② `NodeCanvas._sync_text_fonts()` 在每次缩放和新建节点后调用 ③ 字体钳制: title 6~32pt, type/result 5~24pt |

---

## 二、格栅模组增强

### 1. 栅条形状系数 β 参数化
| 模块 | 数值 |
|------|------|
| 矩形断面 | β=2.42 |
| 半圆形断面 | β=1.97 |
| 圆形断面 | β=1.83 |

**改动**:
- `src/models/geshan.py`: 新增 `_BAR_SHAPE_BETA` 字典 + `_get_beta()` 方法
- `_build_param_defs`: 新增 `bar_shape` 参数 (0/1/2, step=1)
- `calculate()`: 用 `self._get_beta(bar_shape)` 替代硬编码 `beta_val=2.42`
- `_vectorized_compute`: `beta_map = np.array([2.42, 1.97, 1.83]); beta_vals = beta_map[bar_shape_arr]` 向量化查表

### 2. 输出维度新增
| 维度名 | 说明 |
|--------|------|
| `栅条形状系数 β` | β 值 |
| `阻力系数 ξ` | ξ = β×(s/b)^(4/3) |
| `(s/b)^(4/3)` | 间隙比指数 |

`dimension_labels.py` 添加 DIMENSION_TABLE + VEC_FIELD_TABLE 双映射。

### 3. bar_shape 显示型变量机制
| 问题 | 方案 |
|------|------|
| bar_shape 在 `free` 中导致方案数 3× (576 组合) | 同时放入 `free`(提供下拉值) 和 `fixed`(存实际值) |
| `get_free_keys` 排除同时出现于 fixed 的键 | 枚举引擎不遍历 bar_shape，方案数保持 192 |

**修改**: `discretization.py` 的 `get_free_keys/get_free_values/grid_size` 三函数增加固定键排除逻辑。

### 4. 枚举参数值可读显示
`dimension_labels.py` 新增:
```python
_PARAM_VALUE_DISPLAY = {
    "bar_shape":  {0: "0_矩形断面",   1: "1_半圆形断面",   2: "2_圆形断面"},
    "equip_type": {0: "0_带式压滤机", 1: "1_离心脱水机"},
    "method":     {0: "0_热干化",     1: "1_太阳能干化"},
}
```
`format_param_value(key, value)` → main_window + solution_browser 参数行统一使用。

---

## 三、约束面板优化

### 1. 确定按钮持久绿色
| 状态 | 颜色 | 触发 |
|------|------|------|
| 已应用 | #55cc55 绿 | 加载时 / 点击确定后 |
| 已修改 | #555555 灰 | 输入框/下拉框内容变化 |

**实现**: `constraint_panel.py`
- 新增 `_applied_states` 字典 + `_on_original_dirty/_on_result_dirty/_set_applied` 方法
- Entry 绑定 `sv.trace_add("write", ...)`, Combobox 绑定 `<<ComboboxSelected>>`
- 移除旧的 `_flash_green` (2秒定时变灰)

### 2. 约束面板与已应用方案同步
- `load_node()` 新增 `applied_params` 参数 → 方案参数覆盖 config 默认值
- `main_window._on_constraint_changed()`: 清除 `be._result=None` + `be.state=DIRTY`
- `solution_browser._get_applied_params()`: 节点 DIRTY 时返回空 → 取消"✓ 已应用"高亮

---

## 四、关键架构洞察

| 洞察 | 详情 |
|------|------|
| **双 mods 目录必须同步** | `mods/` (测试) + `ddesign_tool/mods/` (运行时) — 每次修改 JSON 须两处同步 |
| **显示型自由变量模式** | 同时入 free(UI用) 和 fixed(值用), get_free_keys 排除 → Combobox 显示但不枚举 |
| **tkinter scale 不缩放字体** | Canvas.scale() 仅变换坐标, font 需手动 itemconfig 更新 |
| **canvas vs world 坐标** | Canvas 坐标 = world × scale; `_canvas_xy` 回 Canvas 坐标; 传递前需 `/scale` |
| **VEC_FIELD_TABLE 是关键** | 方案浏览器维度来自 numpy 字段名, 需此表映射到中文显示 |

---

## 五、改动文件汇总

| 文件 | 改动行 | 类型 |
|------|--------|------|
| `src/ui/canvas_view.py` | +20 | 坐标修复 + 字体缩放 |
| `src/models/geshan.py` | +35 | bar_shape 参数化 + 维度输出 + 向量化修复 |
| `src/ui/dimension_labels.py` | +30 | PARAM_VALUE_DISPLAY + VEC_FIELD_TABLE + format_param_value |
| `src/models/discretization.py` | +15 | get_free_keys/get_free_values/grid_size 排除逻辑 |
| `src/ui/constraint_panel.py` | +40 | 按钮状态 + applied_params + dirty 检测 |
| `src/ui/main_window.py` | +10 | NodeState 导入 + applied_params 传递 + 约束变更清除 |
| `src/ui/solution_browser.py` | +5 | format_param_value + dirty 检查 |
| 6× `discretization.json` | +3 each | bar_shape 在 free+fixed 双位置 |

---

> **记录者**: Sisyphus | **版本**: v3.5 | **测试**: 251 passed

---

## 六、旋流沉砂池 Bug 修复 (3个)

### Bug 1: 实际停留时间 ≡ 设计停留时间
| 项目 | 内容 |
|------|------|
| 文件 | `mods/core/chenshachi/__init__.py` |
| 根因 | `V_eff = Q_single × t` → `t_actual = V_eff / Q_single ≡ t` 循环论证 |
| 修复 | `V_eff = π×(D/2)²×h2` (用取整后实际尺寸)；`t_actual = V_eff / Q_single` |

### Bug 2: 砂斗所需容积计算
| 项目 | 内容 |
|------|------|
| 根因 | `V_hopper` 除以 n 后每池只存半量；且 `h_cyl` 未取整 → `V_storage ≡ V_hopper` |
| 修复 | ① `V_sand_daily = (Q_avg/n)×X/1e6` 全程单池 ② `h_cyl = ceil_to(h_cyl_exact, 0.1)` → V_storage > V_hopper |

### Bug 3: 渠道维度公式错误 + 维度不显示
| 项目 | 内容 |
|------|------|
| 根因 | `startswith("进水")` 过滤误伤渠道维度；`_dim_formula()` 中 `if "进水" in name` 太宽 |
| 修复 | 过滤改为 `startswith("进水") and u=="mg/L"`；公式匹配改为 `re.match(r"进水(BOD|COD|...)", name)` |

### 新增: 进出水渠道设计
- 新增公式 (4-26)~(4-29): A渠, h渠, L直, B出
- 新增参数: B_channel (显示型自由变量), v_channel (固定)
- 新增约束: 进水渠水深 ≥ 0.2m, 宽深比 1.0~3.0

---

## 七、v4.0 公式系统重构 — 消除模糊匹配

### 问题
`add_dimension()` 丢弃公式信息 → `_dim_formula()` 用 80+ 条 patterns 字典"猜回来" → 新增维度需手动维护字典

### 方案
```
add_dimension(formula=...) → NodeResult.dimension_formulas → UI 直接读取
    │ formula=None (自动回退)
    │       ↓
    │  get_formula(name) → DIM_FORMULAS 子串匹配
```

### 实施
| 文件 | 改动 |
|------|------|
| `models/dimension_formulas.py` | **新建** — 单一数据源 DIM_FORMULAS 字典 (90+ 条) + `get_formula()` |
| `models/base.py` | `add_dimension(formula=)` 自动回退；`NodeResult.dimension_formulas` 字段 |
| `ui/main_window.py` | `_dim_formula()` 精简为关键词回退；优先读 `dimension_formulas`；删除 80 行重复 patterns |
| `mods/core/chenshachi/__init__.py` | 示范: 20 个 `add_dimension` 显式传 `formula=` |

---

## 八、v4.1 分类系统重构 — 消除模糊匹配 (第二轮)

### 问题
`output_writer.py` 的 `_is_physical_dimension()` 用 50+ 关键词猜测维度属于"构筑物尺寸"还是"计算结果"
`main_window.py` 的 `DIM_CATS` 10条正则规则分类参数 → `_cat()` 死代码从未被调用

### 方案
```
add_dimension(category="physical"|"computed")
    │ category=None (自动回退)
    │       ↓
    │  get_dimension_category(name) → DIM_CATEGORIES 子串匹配
    │       ↓
    NodeResult.dimension_categories[name] → UI + Excel 直接读取
```

### 实施
| 文件 | 改动 |
|------|------|
| `models/dimension_formulas.py` | +DIM_CATEGORIES(130条) + PARAM_CATEGORIES(70条) + `get_dimension_category()` + `get_param_category()` |
| `models/base.py` | `NodeResult.dimension_categories` + `add_dimension(category=)` 自动回退 |
| `output_writer.py` | `_is_physical_dimension(k)` → `r.dimension_categories.get(k)` |
| `ui/main_window.py` | 参数分三组(基本/构筑物/运行)；维度分两节(计算结果/构筑物尺寸)；删除 DIM_CATS + `_cat()` |
| `MODS_GUIDE.md` | v4.0 → v4.1，新增分类系统章节 |

### 分类体系
| 类型 | 分类 | 显示位置 |
|------|------|---------|
| 维度 | `physical` / `computed` | 结果面板 + Excel |
| 参数 | `basic` / `physical` / `operating` | 结果面板设计参数 |

---

## 九、关键架构洞察 (新增)

| 洞察 | 详情 |
|------|------|
| **模糊匹配是万恶之源** | 公式(`_dim_formula`)、分类(`_is_physical_dimension`)、参数(`DIM_CATS`) — 三套独立模糊匹配，信息在 `add_dimension()` 处已存在却被丢弃 |
| **单一数据源原则** | `dimension_formulas.py` 是公式+分类的唯一权威来源，mod 可显式覆盖、默认自动回退 |
| **零破坏性迁移** | `formula=None` / `category=None` 时自动回退字典 → 31 个旧模组无需修改 |
| **双重数据源陷阱** | discretization.json ↔ discretization.py、constraint_limits ↔ CONSTRAINT_LIMITS、mods/ ↔ ddesign_tool/mods/ — 每次不一致都导致 bug |
| **显示型自由变量** | B_channel 同时入 free(UI下拉) 和 fixed(实际值) → 约束面板显示但不枚举 |

---

## 十、改动文件汇总 (本轮新增)

| 文件 | 改动行 | 类型 |
|------|--------|------|
| `models/dimension_formulas.py` | +260 | **新建** — 公式+分类单一数据源 |
| `models/base.py` | +15 | add_dimension(formula=, category=) 自动回退 |
| `ui/main_window.py` | +40/-70 | 公式优先读 dimension_formulas；分类分组；删 DIM_CATS |
| `output_writer.py` | -55 | 删除 _is_physical_dimension()；改用 dimension_categories |
| `models/discretization.py` | +8 | chenshachi 同步新约束 |
| `models/solution_space.py` | +2/-1 | CONSTRAINT_LIMITS 同步 |
| `ui/dimension_labels.py` | +10 | 渠道维度 + VEC_FIELD_TABLE 映射 |
| `mods/core/chenshachi/__init__.py` | 重写 | 3 bug修复 + 渠道公式 + 显式 formula=/category= |
| `mods/core/chenshachi/mod.json` | +2 | B_channel, v_channel 参数 |
| `mods/core/chenshachi/discretization.json` | +6 | 新约束 + B_channel |
| `MODS_GUIDE.md` | 重写 | v4.0 → v4.1 |

> **记录者**: Sisyphus | **版本**: v4.1 | **本轮修改文件**: 11+

---

## 十一、辐流式初沉池 Bug 修复 + 污泥原则确立

### Bug 1: T_sludge 单位歧义导致贮泥容积偏小 12 倍
| 项目 | 内容 |
|------|------|
| 根因 | mod.json `"unit": "h"`, default=4, 代码 `V_sludge = S_wet * (T_sludge / 24) / n` |
| 修复 | 改为 `"unit": "d"`, default=2, 去 `/24`；`V_sludge = S_wet * T_sludge / n` |

### Bug 2: 向量化 SS 去除率硬编码
| 根因 | `SS_out = SS_in * 0.50` (硬编码)，标量版用 `removal_ss` |
| 修复 | 统一为 `SS_out = SS_in * (1 - removal_ss)` |

### 污泥计算原则确立
```
内部计算全部按单池 → SludgeFlow 输出 ×n 汇总到下游污泥合并节点
```
- chuchenchi: S_dry/S_wet 改单池（/n），SludgeFlow ×n 汇总
- chenshachi: SludgeFlow ×n 汇总（之前输出了单池值）

### 径深比约束修正
- chuchenchi: D/h2 = 4~15 → **6~12**
- chuchenchi: 有效水深 h2 ≥ 2.0 → **2.0~4.0**

---

## 十二、约束持久化 — 用户调整保存到 discretization.json

### 实现
`constraint_panel.py` 新增 `_persist_config()` 方法，在原始/结果约束"确定"后自动写回：
```
mods/core/{id}/discretization.json  ← 写回
ddesign_tool/mods/core/{id}/discretization.json  ← 同步
```

### 启动时自动生效
`_get_merged_configs()`: DISCRETE_CONFIGS (Python) → load_mod_discretizations() (JSON 覆盖) → 用户上次保存的约束自动加载。

---

## 十三、models/ 清理 — 消除双重代码源

### 背景
31 个模组的 `models/{id}.py` 为旧架构遗留。ModManager 从 `mods/core/{id}/__init__.py` 加载后，这些文件永不执行。

### 清理
- 删除 29 个 `models/{id}.py`（对应已迁移的 MC 模组）
- 删除 `_CONVENTION_OVERRIDES` 和 `_resolve_by_convention()` 死代码
- `node_registry.py` resolve_class() 三步简化为单步
- `models/__init__.py` 删除失效 `from . import` 块
- `ddesign_tool.spec` 更新 pathex 和 collect_submodules

### 保留
仅 4 个 IO 节点（pipe_network, water_quality_node, combiner, input_node）+ 引擎文件

---

## 十四、6 个集配水/高程模组 MC 迁移

### 问题
v3.5 新增的 6 个模组（jishuijing, peishuijing, jipeishuijing, peishuiqu, gdys_stss, jcws_smbg）的 `__init__.py` 只是 3 行桥接 import，从未完成 MC 迁移。

### 过程
1. 删 `models/*.py` 后这些模组失效
2. 改 mod.json 时 PowerShell `Set-Content` 破坏 UTF-8 编码 → 12 个 mod.json 全部损坏
3. 从 `.pyc` 缓存反汇编 + 手动重建 6 个 `models/*.py`
4. 用 Python `json.dump` 重写全部 12 个 mod.json
5. `gdys_stss` API 错误修正：`designer.design(Q, n=, xi=, ...)` → `designer.design(Q_Ls, D_min=300, ...)`
6. 将代码从 `models/` 搬到 `__init__.py` → 全部 31 个模组完成 MC 迁移

### 教训
- **PowerShell `Set-Content` 默认写 UTF-16LE**，会破坏 UTF-8 JSON。始终用 Python 或 Write 工具处理编码敏感文件。
- **删除文件前确认无引用** — `main_window.py` 有 19 个硬编码 `from models.xxx import`
- **`run.bat` 逐错误修复**：GraphExecutor、ProjectManager、get_project_manager 导入缺失

---

## 十五、改动文件汇总 (本轮新增)

| 文件 | 改动行 | 类型 |
|------|--------|------|
| `mods/core/chuchenchi/__init__.py` | 重写 | T_sludge 单位 + 径深比 + 单池污泥 |
| `mods/core/chuchenchi/discretization.json` | 重写 | 约束名/限值更新 |
| `mods/core/chenshachi/__init__.py` | +2 | SludgeFlow ×n |
| `mods/core/{6个}/__init__.py` | 重写 | MC 迁移 — 自包含 |
| `mods/core/{6个}/mod.json` | 重写 | module_path→"" + 编码修复 |
| `ddesign_tool/mods/core/{6个}/*` | 同步 | 全部 18 个文件 |
| `models/*.py` (29个) | 删除 | 旧架构遗留 |
| `models/__init__.py` | -15 | 删除失效 import 块 |
| `models/node_registry.py` | -50 | 删除 CONVENTION_OVERRIDES + _resolve_by_convention |
| `ui/constraint_panel.py` | +35 | _persist_config() |
| `ui/main_window.py` | +5/-15 | 导入修复 + classify 分组 |
| `models/discretization.py` | +5 | chuchenchi 同步 |
| `models/solution_space.py` | +1/-1 | CONSTRAINT_LIMITS 同步 |
| `ddesign_tool.spec` | +5 | pathex + collect_submodules('mods') |
| `MODS_GUIDE.md` | 重写 | v4.1 |

> **记录者**: Sisyphus | **版本**: v4.1 | **本轮修改文件**: 50+
