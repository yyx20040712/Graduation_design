# 2026-05-19 打包学习记录

> **目的**: 记录打包流程的关键知识，防止未来 AI 会话遗忘
> **关联**: `PACKAGING.md` (详细指南) | `ddesign_tool.spec` (构建配置)

---

## 一、核心命令

```powershell
# 在项目根目录执行，使用 venv 中的 pyinstaller:
& ".venv\Scripts\pyinstaller.exe" ddesign_tool.spec --clean --noconfirm
```

- **不能省略 `--clean`** — 否则旧缓存可能导致文件遗漏
- **必须在项目根目录执行** — spec 中的相对路径依赖此工作目录
- **构建耗时约 2-3 分钟** — 主要时间花在 pandas 隐式导入分析

## 二、打包架构要点

### EXE 是自解压单文件
- PyInstaller 将 Python 解释器 + 所有依赖 + 数据文件打包为单个 EXE
- 首次运行时自动解压到 `%TEMP%\_MEIxxxxx\`
- `_paths.py` 提供 frozen 模式下的路径重定向

### 两类资源嵌入方式

| 类型 | 机制 | 示例 |
|------|------|------|
| **Python 模块** | `hiddenimports` + PYZ 归档 | mods/core/*.py, models/*.py |
| **数据文件** | `datas` 列表 → PKG 归档 | .md, .xlsx, .tex, .json, .ini |

### 动态导入陷阱
- `ModManager` 使用 `importlib.import_module()` 动态加载模组
- PyInstaller 静态分析**完全无法追踪**这类导入
- 解决方案: `hiddenimports += collect_submodules('models')`

## 三、spec 文件中的 datas 完整清单

**⚠️ 以下 2 项曾在上一次打包中被遗漏，必须包含:**

```
('使用方法.md', '.')                        ← 曾被遗漏！
('output/file_inventory.xlsx', '.')          ← 曾被遗漏！
```

完整 datas 清单 (14 项 + data/*.xlsx):

1. `('ddesign_tool/config.ini', '.')`
2. `('ddesign_tool/mods', 'mods')`
3. `('.sisyphus/notepads', 'knowledge')`
4. `('MODS_GUIDE.md', '.')`
5. `('README.md', '.')`
6. `('使用方法.md', '.')` ← 不要漏
7. `('tests/yyx.ddesign.json', '.')`
8. `('tests/kuangjing.ddesign.json', '.')` ← **2026-05-20 新增**
9. `('output/engineering_cost_estimation.tex', 'output_template')`
10. `('output/system_design_manual.tex', 'output_template')`
11. `('output/mod_calculation_formulas.tex', 'output_template')`
12. `('output/污水计算逻辑.txt', 'output_template')`
13. `('output/雨水计算逻辑.txt', 'output_template')`
14. `('output/file_inventory.xlsx', '.')` ← 不要漏
15+. `data/*.xlsx` (glob 自动收集)

## 四、打包前检查清单

在运行 pyinstaller 之前:

- [ ] `使用方法.md` 是否在 **spec datas** 中? (第 6 项)
- [ ] `output/file_inventory.xlsx` 是否在 **spec datas** 中? (第 13 项)
- [ ] `使用方法.md` 是否在 **bootstrap.py RESOURCE_MANIFEST** 中?
- [ ] `file_inventory.xlsx` 是否在 **bootstrap.py RESOURCE_MANIFEST** 中?
- [ ] 所有 Excel 文件是否已关闭? (避免 ~$ 临时文件)
- [ ] 新增的 Python 模块是否在 `hiddenimports` 中?
- [ ] 新增的社区模组是否需要 `mods/community/` 已包含在 datas 第 2 项中?

## 五、打包后验证

### 1. 检查文件大小
```powershell
Get-Item "dist\ddesign_tool.exe" | Select-Object Name, @{N='MB';E={[math]::Round($_.Length/1MB,1)}}
# 预期: ~54 MB
```

### 2. 验证嵌入文件 (关键!)
```python
from PyInstaller.archive.readers import CArchiveReader
reader = CArchiveReader(r'dist\ddesign_tool.exe')
for name in reader.toc:
    name_str = name.decode('utf-8', errors='replace') if isinstance(name, bytes) else name
    if 'file_inventory' in name_str: print(f'[OK] {name_str}')
    if '使用方法' in name_str: print(f'[OK] {name_str}')
```

### 3. **端到端验证 (关键!)** — 确认文件被 bootstrap 实际提取
```powershell
# 必须实际启动 EXE 验证文件是否被提取到 CWD!
$td = "$env:TEMP\pkg_test"; mkdir $td -Force
cp dist\ddesign_tool.exe $td
$p = Start-Process "$td\ddesign_tool.exe" -WorkingDirectory $td -PassThru
Start-Sleep -Seconds 8
# 检查文件是否在 CWD 中
Test-Path "$td\使用方法.md"      # 应为 True
Test-Path "$td\output\file_inventory.xlsx"  # 应为 True
$p.Kill(); rm $td -Recurse -Force
```
> ⚠️ **仅检查 TOC 不够** — TOC 只证明文件在归档中，不代表 bootstrap 会释放它们!

### 4. 冒烟测试
```powershell
$proc = Start-Process "dist\ddesign_tool.exe" -PassThru
Start-Sleep -Seconds 5
if (-not $proc.HasExited) { "OK - EXE running" } else { "FAILED" }
$proc.Kill()
```

## 六、历史错误记录

| 日期 | 问题 | 根因 | 修复 |
|------|------|------|------|
| 2026-05-18 | 污泥节点点击无反应 | `wuni_*` 模组 importlib 动态加载，PyInstaller 未追踪 | `hiddenimports += collect_submodules('models')` |
| 2026-05-18 | 打包权限错误 | data/ 中 Excel 被 WPS 打开产生 ~$ 临时文件 | glob 筛选排除 `~$*` |
| 2026-05-19 | **`使用方法.md` 和 `file_inventory.xlsx` 打包后用户找不到** | 文件在 spec datas 中(嵌入 EXE)，但 **不在 bootstrap.py 的 RESOURCE_MANIFEST 中**(未释放到 CWD)。TOC 验证通过但运行时无效。 | 在 RESOURCE_MANIFEST 中添加 2 个条目后重打包 |
| **2026-05-19** | **关键教训: datas != 可访问** | PyInstaller datas 只负责嵌入 EXE → 解压到 `_MEIPASS`(临时目录)。`bootstrap.py` 的 RESOURCE_MANIFEST 才是将文件复制到用户可见工作目录的机制。两者缺一不可。 | 打包后必须端到端测试：启动 EXE 并检查文件是否在 CWD 中出现 |
| **2026-05-20** | **新增 kuangjing.ddesign.json 矿井水演示项目** | 新项目文件需要同时加入 spec datas 和 bootstrap RESOURCE_MANIFEST。与 yyx.ddesign.json 处理方式完全一致。 | spec + bootstrap 各加 1 行；TOC 验证确认嵌入 |
| **2026-05-20** | **MC式约定自动发现 (Phase 3)** | `_COMPAT_MODULE_MAP` 24 条硬编码替换为 `_resolve_by_convention()` — models/{node_type} → {PascalCase}Node。仅 4 条例外 (cugeshan/xigeshan/cass/aao) 需 override。新增模组零注册。 | node_registry.py 重写；graph_executor.py 加 None 防御 |
| **2026-05-20** | **`'NoneType' object has no attribute 'node_id'` 崩溃** | kw_gaomidu/kw_vxinglvchi/kw_ziwai 不在 _COMPAT_MODULE_MAP 中，ModManager 降级时 default_node_factory 返回 None → add_node(None) → 崩溃。 | 2 处修复: (1) 约定自动发现自动覆盖 3 类型 (2) from_dict() 加 None 检查 |

### 根因分析图

```
spec datas:  embedding    sys._MEIPASS    RESOURCE_MANIFEST    os.getcwd()
  ──────────→  into EXE  ──────────→  (temp dir)  ──────────→  (user visible)
                                     ↑                          ↑
                              文件在这里但                    用户只能看到
                              用户看不到                      这里的文件
                              
                              ⚠️ 文件在 datas 中但不在 MANIFEST 中 = 存在但不可见!
```

## 七、路径函数速查 (`_paths.py`)

```python
# 在 frozen (EXE) 模式下获取嵌入资源的真实路径:
from _paths import get_config_path, get_mods_dir, get_data_dir

# 等效于:
# get_config_path()    → sys._MEIPASS + '/config.ini'
# get_mods_dir()       → sys._MEIPASS + '/mods'
# get_data_dir()       → sys._MEIPASS + '/data'
```

---

> **记录者**: Sisyphus | **日期**: 2026-05-19 (更新: 2026-05-20) | **EXE**: dist/ddesign_tool.exe (54.1 MB)
> **下次打包提醒**: 
> 1. 检查 spec datas 中是否有 `使用方法.md` 和 `file_inventory.xlsx`
> 2. **检查 bootstrap.py RESOURCE_MANIFEST 中是否有这两项** (2026-05-19 教训!)
> 3. 新增项目文件 → spec datas + bootstrap MANIFEST **各加一行**
> 4. **新增模组 → 只需遵循命名约定**: models/{id}.py, 类名 {PascalCase}Node, mods/core/{id}/mod.json — node_registry 自动发现
