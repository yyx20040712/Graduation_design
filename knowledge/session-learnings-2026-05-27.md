# 2026-05-27 学习记录 — 约束系统修复 + 验证器 + 生产审计

> **会话**: 多轮 | **范围**: 全项目 | **关键成果**: 5 项修复 + Validator 系统 + 生产审计

---

## 一、约束系统双路径不同步 Bug (核心发现)

### 问题
`_vectorized_compute()` 中硬编码的 `ok_*` 边界（如 `ok_hrt = (6.0 <= HRT_actual) & (HRT_actual <= 12.0)`）与用户通过约束面板可调的 `constraint_limits` 完全脱节。用户修改限值后，方案筛选仍用硬编码边界。

### 根因分析 (软件演化视角)
```
v3.x:  只有 F5 重算，ok_* 是唯一约束路径 → 一切正常
v3.5:  新增方案浏览器 + 约束面板 + discretization.json
       constraint_limits 只连接到了「显示层」
       _filter_feasible 仍读取硬编码 ok_*
       两条路径从未打通
```
默认值恰好一致 (constraint_limits["实际 HRT"] = "6~12" 与硬编码完全相等)，只有用户修改时才暴露。缺乏「修改限值→重新枚举→验证解数变化」的集成测试。

### 修复
**文件**: `ddesign_tool/src/models/solution_space.py`

1. `_filter_feasible()` 新增 `constraint_names`, `constraint_limits`, `node_type` 参数。当存在动态限值时，用 `val_*` 字段 + 解析后的限值重算 `ok`，覆盖模组硬编码。
2. `_extract_checks()` 同步修改，`passed` 标志也动态计算。
3. `enumerate()` / `enumerate_sludge()` 传递新参数。

**效果**: 全 34 模组动态约束生效。tiaojiechi HRT 限值 6→2，解数从 24 跃升至 72。

### 次级发现: 参数变量边界回归
`vxinglvchi` / `kw_vxinglvchi` 中 `ok_force = v_force_actual <= v_force` 使用参数变量。用户改 `v_force` 但不更新 constraint_limits 时，动态检查用旧限值误杀方案（各 6 个）。

**修复**: `constraint_panel.py` 新增 `_PARAM_SYNC_MAP` + `_sync_param_to_constraint()`。修改映射表中的 fixed 参数时，自动同步对应 constraint_limits。支持三种规则：`<= {val}` (直接替换)、`lower` (展开下限)、`expand` (双向展开)。

---

## 二、约束面板 Bug 修复

### 2.1 自由参数下拉选项收缩
`_on_original_confirm` 将 `cfg["free"]["n"]` 从 `[2,4,6,8]` 收缩为 `[2]` 并持久化。下次打开面板时 Combobox 只有 1 个选项。

**修复**: `load_node()` 中 `copy.deepcopy(free)` 保存到 `self._original_free`。`_build_original_row` 用 `_original_free` 显示。`_persist_config` 用 `_original_free` 写入。

### 2.2 跨类别参数联动
用户改 HRT=4 时，"实际 HRT" 下限仍为 6。修复: `_PARAM_SYNC_MAP` 新增 `HRT` → `"实际 HRT"` 的 `lower` 规则。修改后 `_update_result_display()` 实时刷新结果约束输入框。

---

## 三、Mod Validator — 嵌入式验证系统

### 架构
```
ddesign_tool/src/validator/
├── engine.py           # ModValidator + BaselineManager + Severity
├── checks/
│   ├── config.py       # 配置完整性 (6 项检查)
│   ├── constraint.py   # 约束一致性 (ok_* vs constraint_limits)
│   ├── calculation.py  # 计算烟雾测试
│   ├── vectorized.py   # 向量化对标量一致性
│   └── ui_contract.py  # UI 契约 (ParamDef vs discretization)
├── reporters/
│   ├── console.py      # 终端彩色进度条
│   ├── html.py         # 可视化 HTML
│   └── json_report.py  # 机器可读 JSON
└── __init__.py         # CLI 入口 (--validate --all --deep --baseline)
```

### 关键特性
- **0 外部依赖**: 只用已打包在 EXE 中的模块
- **自动发现**: 新模组零配置继承全部 5 项检查
- **基线系统**: `--generate-baseline` / `--baseline` 抑制已知问题
- **设计决策标记**: `.validator-notes.json` (独立注解文件) + `.validator-baseline.json` (自动生成)
- **严重级别**: ERROR(0) > FAIL(1) > WARN(2) > PASS(3) > INFO(4)

### 最终结果: 34/34 健康, 170/170 PASS, 0 FAIL, 0 ERROR

---

## 四、Bug 修复

| Bug | 模组 | 修复 |
|-----|------|------|
| `Y_obs` not defined | aao `_vectorized_compute` | 添加 `Y_obs = fixed.get("Y_obs", 0.5)` |
| `Q_manual` crash | gdys_stss `_vectorized_compute` | 从 `fixed` 读取而非 `grid` |
| ParamDef 范围不匹配 | 13 模组 13 参数 | 扩展 min/max 覆盖 discretization 值 |
| constraint_limits 缺失 | kw_tiaojiechi | 补 `堰口负荷 ≤ 5.0 L/(s·m)` |

---

## 五、生产就绪度审计 (全项目)

### 评分: 6.8/10

| 维度 | 评分 | 关键问题 |
|------|------|---------|
| 架构设计 | 8/10 | MC 模组 + DAG 是亮点；God class (main_window.py 2191行) |
| 代码质量 | 6/10 | 69 处静默异常吞没；ceil_to/np.ceil 双轨 |
| 测试验证 | 7/10 | Validator 是亮点；单元测试覆盖不足 |
| 配置部署 | 6/10 | pre-commit 未激活；双 mods 目录需手动同步 |
| 安全健壮 | 5/10 | 输入验证不足；静默失败无诊断 |
| 可维护性 | 7/10 | 模组自包含；无技术债务标记 |

### 改进路线图
- P0 (毕业答辩前): 版本号统一、修复测试、CI 配置
- P1 (生产部署前): ceil_to 统一、异常处理统一、God Class 拆分
- P2 (持续改进): 单元测试补齐、JSON Schema 验证、自动化同步

详见 `plan.md`。

---

> **最后更新**: 2026-05-27 | **Sisyphus**
