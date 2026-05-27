# 2026-05-24 (会话2) 学习记录 — 模组全面审计 + 架构去硬编码

> **日期**: 2026-05-24 | **测试**: 327 passed | **修改文件**: 20+

---

## 一、run.bat 启动修复

| Bug | 文件 | 根因 | 修复 |
|-----|------|------|------|
| `NameError: FileManager` | main_window.py | MC迁移后import断链 | +`from ui.file_manager import FileManager` |
| `NameError: NodeCanvas` | main_window.py | 同上 | +`from ui.canvas_view import NodeCanvas` |
| `NameError: SolutionBrowser` | main_window.py | 同上 | +`from ui.solution_browser import SolutionBrowser` |
| `NameError: format_dimension_row` | main_window.py | 同上 | +`from ui.dimension_labels import format_dimension_row, format_param_value` |
| 测试文件 `models.{id}` 残留 | conftest.py, test_*.py | 删除models/后未更新 | 改用 `get_mod_manager().load_mod(id)` |

---

## 二、约束持久化加固

### 问题
`_persist_config()` 静默吞异常 → 写入失败无感知；非原子写入 → JSON可能损坏

### 修复
- ✅ 原子写入: 先写 `.tmp_*.json` → `os.replace()` 重命名
- ✅ 双目录同步: `mods/core/` + `ddesign_tool/mods/core/`
- ✅ 错误日志: 权限/路径错误分别记录

---

## 三、模组逐个核对

| 模组 | 问题数 | 关键修复 |
|------|--------|---------|
| **chuchenchi** | 1 | 新增排泥周期 T_sludge 1~2d 约束 |
| **CASS** | 3 | L/B 4~6, λ_design/λ_actual 双维度+公式, 滗水器堰口长度 L_w |
| **gaomidu** | 7 | t_thicken 8h→1.5h, P_in 0.95→0.99, +P_mix/P_floc/G_mix/G_floc/X_r/L_w/q_堰/H_loss |
| **vxinglvchi** | 10 | T_w缺失(F=Q/(v×T_w)), 反冲洗参数化, +D_g/D_w/D_out/Q_blower/Q_pump/滤头密度/V型槽/H_loss |
| **kw_vxinglvchi** | 2 | 同vxinglvchi的T_w/F_total bug |
| **bashi_jiliangcao** | 0 | 实现与规范完全一致 |
| **jishuijing** | 5 | +h_eff校核, 向量化ok_*/val_*, DISCRETE_CONFIGS |
| **peishuijing** | 6 | +HRT法计算(V=Q×HRT/60), +HRT/h_eff校核, DISCRETE_CONFIGS |

---

## 四、单池/总共流量审计（全31模组）

### 🔴 致命Bug
| 模组 | Bug | 影响 |
|------|-----|------|
| **gaomidu** | S_dry_total(总污泥) ÷ L_pool×B_pool(单池面积) → h_thicken/solid_flux 偏大 n× | 浓缩区高度和固体通量完全错误 |

### ✅ 正确的模式
- 尺寸计算: `Q_single = flow.Q_design / n` — chenshachi, chuchenchi, gaomidu, cass, ziwai 等
- 总量→单池分割: `V_total` 先算总量 → `V_single = V_total / n` — cass, vxinglvchi
- 集配水: 全厂总流量不分池 — jishuijing, peishuijing

---

## 五、架构去硬编码（🔥 消除历史遗留）

### 问题根源
`DISCRETE_CONFIGS` (559行硬编码) 与 `discretization.json` (模组自带) 双重数据源，反复出现 constraint_keys 不匹配、名称不一致、旧值覆盖新值等问题。

### v4.2 架构重构
```
之前（双重源）:
  DISCRETE_CONFIGS (559行Python硬编码) ─┐
                                         ├─ 合并 → 谁覆盖谁？
  discretization.json (模组自带)  ──────┘

之后（单一源）:
  discretization.json (模组自带) ─── 唯一权威源
```

### 修改
| 组件 | 删除 | 变更 |
|------|------|------|
| `discretization.py` DISCRETE_CONFIGS | **559行** → 0 | 改为空 `{}` |
| `discretization.py` _get_merged_configs | — | 仅从 JSON 加载，不合并硬编码 |
| `mod_manager.py` _validate_vectorized_output | — | `load_discretization()` 代替 `DISCRETE_CONFIGS.get()` |
| `solution_space.py` CONSTRAINT_LIMITS | **61行** → 0 | 全部从 discretization.json 加载 |
| `solution_space.py` _extract_checks | — | 移除 CONSTRAINT_LIMITS 回退逻辑 |
| `solution_space.py` set_constraint_limits | — | 不再写全局 CONSTRAINT_LIMITS |

### 新增 JSON
- `kw_input/discretization.json` — IO节点，空配置
- `wuni_hebing/discretization.json` — 污泥合并，空配置

---

## 六、关键架构洞察（新增）

| 洞察 | 详情 |
|------|------|
| **单一数据源是唯一解** | 双重源 = 持续出bug。每个配置项必须有且只有一个权威来源 |
| **_validate_vectorized_output 是"哨兵"** | 每次出现 validation warning 都意味着 constraint_keys 存在不一致——应追根溯源修复，而非忽略 |
| **DISCRETE_CONFIGS 已死** | v4.2起，新增/修改模组只需编辑 `discretization.json`，无需碰 Python 代码 |
| **CONSTRAINT_LIMITS 已死** | 约束限值随 discretization.json 自动加载，无需全局注册 |
| **_DEFAULT_HEAD_LOSS 待迁移** | 目前仅2个模组有 mod.json `elevation_loss`，其余29个依赖硬编码 → 后续可迁移 |
| **维度/公式字典保留** | DIM_FORMULAS/DIMENSION_TABLE 是跨模组共享的UI显示映射，非单模组配置，保留合理 |

---

## 七、改动文件汇总

| 文件 | 改动类型 |
|------|---------|
| `src/ui/main_window.py` | +4 import |
| `src/ui/constraint_panel.py` | 重写 `_persist_config()` |
| `tests/conftest.py` | 改用 ModManager 加载 |
| `tests/test_kw_input.py` | import + 断言更新 |
| `tests/test_processing.py` | import 更新 |
| `test_full_dag.py` | import 更新 |
| `mods/core/chuchenchi/__init__.py` | +T_sludge 约束 |
| `mods/core/chuchenchi/discretization.json` | +T_sludge |
| `mods/core/cass/__init__.py` | 重写 (L/B 4~6, λ双维度, L_w) |
| `mods/core/cass/discretization.json` | 重写 (7 constraints) |
| `mods/core/gaomidu/__init__.py` | 重写 (+P_mix/floc, G, X_r, L_w, q_堰, H_loss; 污泥单池修复) |
| `mods/core/gaomidu/discretization.json` | 重写 (7 constraints) |
| `mods/core/vxinglvchi/__init__.py` | 重写 (T_w, 反冲洗参数化, +D_g/w/out, Q_blower/pump, V型槽, H_loss) |
| `mods/core/vxinglvchi/discretization.json` | 重写 (7 constraints) |
| `mods/core/kw_vxinglvchi/__init__.py` | 重写 (T_w 修复) |
| `mods/core/kw_vxinglvchi/discretization.json` | 重写 (2 constraints, 匹配代码) |
| `mods/core/jishuijing/__init__.py` | +h_eff check, 向量化 ok_*/val_* |
| `mods/core/jishuijing/discretization.json` | 新建 |
| `mods/core/peishuijing/__init__.py` | 重写 (+HRT法) |
| `mods/core/peishuijing/discretization.json` | 新建 |
| `mods/core/kw_input/discretization.json` | 新建 (空) |
| `mods/core/wuni_hebing/discretization.json` | 新建 (空) |
| `src/models/discretization.py` | **-559行** DISCRETE_CONFIGS, _get_merged_configs 重写 |
| `src/models/solution_space.py` | **-61行** CONSTRAINT_LIMITS, _extract_checks/set_constraint_limits 简化 |
| `mods/mod_manager.py` | _validate_vectorized_output 改用 load_discretization() |
| `MODS_GUIDE.md` | v4.1 → v4.2 |
| `mods/core/jipeishuijing/__init__.py` | +h_eff check, 向量化 ok_*/val_* |
| `mods/core/jipeishuijing/discretization.json` | 重写 (constraint_keys HRT+h_eff) |
| `mods/core/peishuiqu/__init__.py` | 重写 (A=B×h_eff, v_actual=Q/A, L=v×60) |
| `mods/core/peishuiqu/discretization.json` | 重写 (constraint_keys v+h+B) |

---

## 八、集配水模组收尾

| 模组 | 问题 | 修复 |
|------|------|------|
| **jipeishuijing** | +h_eff 校核缺失, 向量化无 ok_*/val_* | 同 jishuijing 模式 |
| **peishuiqu** | 公式完全错误 (A=Q/v → 应为 A=B×h_eff), L=n×L_section → 应为 L=v×60, 参数范围偏窄 | 按规范重写 |

---

> **记录者**: Sisyphus | **版本**: v4.2 | **测试**: 327 passed | **修改文件**: 27+
