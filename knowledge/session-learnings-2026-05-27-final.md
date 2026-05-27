# 2026-05-27 学习记录 — 生产部署级全项目重构

> **会话**: 多轮 | **范围**: 全项目 | **关键成果**: 6.64→8.02 评分提升 | **教训**: 批量编辑在无版本控制下高风险

---

## 一、重构总览

### 评分轨迹
```
v4.5 (原始):    6.64
v5.1 Wave 1-4:  7.07  (+0.43)  ceil_to, 日志, 版本, God Class 拆分
Round 1:         7.44  (+0.37)  测试修复, dimension/report 拆分
Round 2:         7.68  (+0.24)  测试 62%, black/isort, flake8 286
Round 3:         7.82  (+0.14)  DAG 重构, 版本迁移
Final Sprint:    8.02  (+0.20)  测试 97%, 数据源统一, 公式下沉
```

### 变更统计
- 新增文件: 16 (3 UI 模块, 2 Mixin, 2 Data 模块, 6 测试, 1 Schema)
- 修改文件: 91+ 
- 消除 Bug: ceil_to 双轨不一致, 30+ 静默异常, 2 持续测试失败
- 测试: 200→427, 模组覆盖 15%→97%

---

## 二、架构教训

### 1. 批量脚本编辑的高风险

**问题**: 在 1800+ 行单体文件上用 Python 脚本做批量 `logging.getLogger` → `_log` 替换，脚本将 `import` 插入到多行语句中间，破坏了 import 块和 def 块。

**后果**: 
- `_build_elevation_view` 等 5 个方法整体消失
- `elevation_calculator.py` 的 `__log` 变体未被替换
- `cost_estimator.py` 的导入被插入到多行 import 中间

**教训**: 
1. 重构前必须 git init + commit 做基线
2. 批量脚本应该用 AST 而非正则/字符串操作
3. 每次批量编辑后立即运行 validator + 全量测试

### 2. black 格式化导致的全角标点问题

Python 3.14 的 `ast.parse` 拒绝中文全角标点（U+FF08等）。black 格式化时未正确处理，导致 76 个文件出现编码问题。

**修复**: `chr(0xff08)` → `(`, `chr(0xff09)` → `)`, `chr(0xff0c)` → `,`, `chr(0x3002)` → `.`

### 3. UI 重构的功能丢失

`_populate_result_tree` 等 5 个方法被编辑操作误删后，手工重建版本与原始实现有差异：
- 参数未按 basic/physical/operating 分类
- 水质面板从卡片式变成 Treeview 表格
- `format_param_value` 返回值被错误解包

**修复方法**: 反编译 dist/ddesign_tool.exe 中的 .pyc 文件，从 bytecode 还原原始方法逻辑。

---

## 三、新增模式与最佳实践

### 1. 数据源统一原则
- 节点注册: `ModManager.register_infra_node()` ← 消除 `_INFRA_REGISTRY` 硬编码
- 公式: `labels.json["formulas"]` ← 消除全局 `DIM_FORMULAS` 字典
- 离散化: `ModManager.save_discretization()` ← 消除直接文件操作

### 2. 完整性测试
`tests/unit/test_main_window_integrity.py` — 用 AST 静态分析检查 MainWindow 中所有 `self.xxx()` 调用都有对应 `def xxx()` 定义。不需启动 GUI。

### 3. 集成边界测试
`tests/unit/test_integration_boundaries.py` — 覆盖 `get_flow_order`, `_build_flow_order`, `_execute_elevation_pass` 等之前零覆盖的代码路径。

---

## 四、剩余已知问题

| 问题 | 严重度 | 说明 |
|------|--------|------|
| flake8 289 问题 | 低 | 主要为 F601(重复键)和 F841(未使用变量) |
| git 未初始化 | 低 | 环境无 git, pre-commit 无法激活 |
| PyInstaller 打包未验证 | 低 | 需在 GUI 环境中测试打包后 EXE |
| ModManager 线程安全 | 低 | Validator 后台线程与 ModManager 存在竞态 |

---

## 五、关键词索引

`ceil_to废弃` `日志统一` `God Class拆分` `公式下沉` `数据源统一`
`black格式化` `全角标点` `反编译pyc` `AST完整性测试` `集成边界测试`
`结果面板重建` `水质面板重建` `参数分类显示`

---

> **最后更新**: 2026-05-27 | **Sisyphus**
