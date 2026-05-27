# 📦 打包指南 — ddesign_tool v3.3

> **打包方式**: PyInstaller (单文件 EXE, ~54 MB)
> **最后更新**: 2026-05-20
> **构建命令**: `pyinstaller ddesign_tool.spec --clean --noconfirm`

---

## 目录

1. [快速开始](#1-快速开始)
2. [打包架构](#2-打包架构)
3. [spec 文件详解](#3-spec-文件详解)
4. [嵌入资源清单](#4-嵌入资源清单)
5. [修改 spec 添加新文件](#5-修改-spec-添加新文件)
6. [构建与验证](#6-构建与验证)
7. [故障排查](#7-故障排查)
8. [打包历史](#8-打包历史)

---

## 1. 快速开始

### 前置条件

```powershell
# 确保虚拟环境已激活
.\.venv\Scripts\activate

# 确认 pyinstaller 已安装
pip show pyinstaller
# 如果未安装: pip install pyinstaller
```

### 一键构建

```powershell
# 在项目根目录 (D:\python_code\Graduation_design) 执行:
pyinstaller ddesign_tool.spec --clean --noconfirm
```

| 参数 | 作用 |
|------|------|
| `--clean` | 清除 PyInstaller 缓存，避免旧文件残留 |
| `--noconfirm` | 自动覆盖 dist/ 目录，无需手动确认 |

**输出**: `dist\ddesign_tool.exe` (~54 MB)

---

## 2. 打包架构

```
ddesign_tool.spec
    │
    ├── Analysis (扫描 ddesign_tool/main.py)
    │   ├── 自动追踪 import 链 → hiddenimports
    │   ├── datas → 嵌入数据文件 (非 Python 资源)
    │   ├── binaries → 嵌入二进制文件 (DLL/SO)
    │   └── pathex → 额外的 Python 搜索路径
    │
    ├── PYZ (编译 .pyc → 压缩归档)
    │   └── 所有纯 Python 模块
    │
    ├── PKG (CArchive — 数据文件归档)
    │   └── datas + binaries → 嵌入 EXE
    │
    └── EXE (最终输出)
        └── Bootloader + PYZ + PKG → 单文件
```

### 运行时文件释放

EXE 首次运行时自动将嵌入资源解压到临时目录 (`%TEMP%\_MEIxxxxx\`)，代码通过 `_paths.py` 中的路径函数访问这些资源。

| 嵌入路径 | 释放位置 | 说明 |
|---------|---------|------|
| `mods/` | `_MEIxxxxx/mods/` | 22 核心 + 3 社区模组 |
| `data/` | `_MEIxxxxx/data/` | 管网 Excel 数据 |
| `knowledge/` | `_MEIxxxxx/knowledge/` | `.sisyphus/notepads` 知识库 |
| `output_template/` | `_MEIxxxxx/output_template/` | LaTeX 模板 + 计算逻辑 |
| `config.ini` | `_MEIxxxxx/config.ini` | 设计参数 |
| `使用方法.md` | `_MEIxxxxx/使用方法.md` | 使用手册 |
| `file_inventory.xlsx` | `_MEIxxxxx/file_inventory.xlsx` | 文件清单 |

> **社区模组 (mods/community/)**: 解压到文件系统后，ModManager 可直接扫描 `community/` 目录加载新增模组，无需重打包。

---

## 3. spec 文件详解

文件: `ddesign_tool.spec`

```python
# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_submodules
import glob as _glob

# ── data/ 目录: 收集所有 .xlsx 文件，排除 Excel 临时文件 (~$*) ──
_data_files = [f for f in _glob.glob('ddesign_tool/data/*.xlsx') if '~$' not in f]

# ── datas: 嵌入非 Python 资源文件 ──
# 格式: (源路径, 目标路径) — 目标路径相对于 EXE 内部根目录
datas = [
    ('ddesign_tool/config.ini', '.'),           # 设计参数
    ('ddesign_tool/mods', 'mods'),               # 所有模组
    ('.sisyphus/notepads', 'knowledge'),         # AI 知识库
    ('MODS_GUIDE.md', '.'),                      # 模组开发指南
    ('README.md', '.'),                          # 项目说明
    ('使用方法.md', '.'),                         # 使用手册 ⚠️ 不要漏掉
    ('tests/yyx.ddesign.json', '.'),             # 示例项目
    ('output/engineering_cost_estimation.tex', 'output_template'),
    ('output/system_design_manual.tex', 'output_template'),
    ('output/mod_calculation_formulas.tex', 'output_template'),
    ('output/污水计算逻辑.txt', 'output_template'),
    ('output/雨水计算逻辑.txt', 'output_template'),
    ('output/file_inventory.xlsx', '.'),          # 文件清单 ⚠️ 不要漏掉
] + [(f, 'data') for f in _data_files]           # 所有管网数据 Excel

# ── hiddenimports: PyInstaller 无法自动检测的模块 ──
hiddenimports = ['openpyxl.cell._writer']

# ModManager 使用 importlib.import_module() 动态加载，
# PyInstaller 静态分析无法追踪 → 必须显式声明
hiddenimports += collect_submodules('models')

# ── 第三方库完整收集 ──
tmp_ret = collect_all('openpyxl')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('pandas')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

# ── EXE 配置 ──
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ddesign_tool',            # 输出文件名
    debug=False,                    # 生产模式
    strip=False,
    upx=True,                       # UPX 压缩 (减小体积)
    console=False,                  # 无控制台窗口 (GUI 应用)
    target_arch=None,               # 自动检测架构
)
```

### 关键设计决策

| 决策 | 原因 |
|------|------|
| `collect_submodules('models')` | ModManager 用 `importlib` 动态加载，静态分析无法追踪 |
| data/ 用 glob + 排除 `~$*` | Excel 打开时产生的临时文件会导致打包权限错误 |
| output/ 单独指定 .tex/.txt | 避免打包 Excel 输出文件 (~$ 临时文件问题) |
| `console=False` | GUI 应用，不需要黑窗口 |
| 知识库嵌入为 `knowledge/` | `.sisyphus/notepads` 在 EXE 中重命名为 `knowledge` |

---

## 4. 嵌入资源清单

| # | 源路径 | 目标路径 | 类型 | 用途 |
|---|--------|---------|------|------|
| 1 | `ddesign_tool/config.ini` | `.` | 配置 | 设计参数 |
| 2 | `ddesign_tool/mods/` | `mods/` | 目录 | 22 核心 + 3 社区模组 |
| 3 | `.sisyphus/notepads/` | `knowledge/` | 目录 | AI 知识库 |
| 4 | `MODS_GUIDE.md` | `.` | 文档 | 模组开发指南 |
| 5 | `README.md` | `.` | 文档 | 项目说明 |
| 6 | `使用方法.md` | `.` | 文档 | 使用手册 |
| 7 | `tests/yyx.ddesign.json` | `.` | 数据 | 示例项目 |
| 8 | `output/engineering_cost_estimation.tex` | `output_template/` | 模板 | 概算方法 |
| 9 | `output/system_design_manual.tex` | `output_template/` | 模板 | 系统设计说明 |
| 10 | `output/mod_calculation_formulas.tex` | `output_template/` | 模板 | 模组计算公式 |
| 11 | `output/污水计算逻辑.txt` | `output_template/` | 逻辑 | 污水管网计算 |
| 12 | `output/雨水计算逻辑.txt` | `output_template/` | 逻辑 | 雨水管网计算 |
| 13 | `output/file_inventory.xlsx` | `.` | 清单 | 文件清单 |
| 14+ | `ddesign_tool/data/*.xlsx` | `data/` | 数据 | 管网 Excel |

**共 13 个指定项 + N 个 data/ Excel 文件**

---

## 5. 修改 spec 添加新文件

### 添加单个文件

```python
# 在 datas 列表中添加一行:
datas = [
    # ... 现有条目 ...
    ('path/to/new_file.ext', 'target_dir'),  # ← 新增
]
```

### 添加整个目录

```python
datas = [
    # ... 现有条目 ...
    ('path/to/new_directory', 'target_name'),  # ← 递归包含
]
```

### 添加新的 hiddenimport

```python
hiddenimports += ['new_module.submodule']
# 或整个包:
hiddenimports += collect_submodules('new_package')
```

### ⚠️ 关键步骤: 同步更新 `bootstrap.py` 的 RESOURCE_MANIFEST

**添加文件到 `datas` 只完成了一半！** 文件会嵌入 EXE 并解压到 `sys._MEIPASS`（临时目录），但用户看不到。必须同时在 `bootstrap.py` 的 `RESOURCE_MANIFEST` 中添加条目，文件才会被复制到工作目录。

```python
# ddesign_tool/src/bootstrap.py
RESOURCE_MANIFEST: list[tuple[str, str, bool]] = [
    # ... 现有条目 ...
    ("新文件名.ext",        "目标路径/新文件名.ext",  False),  # ← 必须添加！
]
```

| 参数 | 含义 |
|------|------|
| `src_subpath` | 文件在 `_MEIPASS` 中的相对路径 (与 spec datas 的 target 一致) |
| `dst_subpath` | 复制到工作目录的目标路径 |
| `is_dir` | `True`=目录, `False`=文件 |

> **历史教训**: `使用方法.md` 和 `file_inventory.xlsx` 曾在 datas 中存在但未加入 RESOURCE_MANIFEST，导致打包后用户找不到这两个文件 (2026-05-19 发现并修复)。

### ⚠️ 常见陷阱

1. **文件在 datas 但不在 RESOURCE_MANIFEST** — 最隐蔽的 bug: 文件在 EXE 内部存在但不释放到 CWD
2. **Excel 文件在 WPS/Excel 中打开时打包会失败** — 使用 glob + 排除 `~$*`
3. **新增模组的 Python 文件需要 `collect_submodules`** — 否则 importlib 加载失败
4. **`使用方法.md` 和 `file_inventory.xlsx` 容易被遗漏** — 每次打包前检查 datas **和** RESOURCE_MANIFEST
5. **修改 spec 后必须 `--clean`** — 避免缓存导致旧文件残留

---

## 6. 构建与验证

### 完整构建流程

```powershell
# 1. 清理旧构建 (可选但推荐)
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "dist")  { Remove-Item -Recurse -Force "dist" }

# 2. 构建
pyinstaller ddesign_tool.spec --clean --noconfirm

# 3. 检查输出
Get-Item "dist\ddesign_tool.exe" | Select-Object Name, Length, LastWriteTime
```

### 验证嵌入文件

使用 Python 脚本检查 EXE 中的嵌入文件:

```python
import sys
sys.path.insert(0, r'.venv\Lib\site-packages\PyInstaller\utils\cliutils')
from PyInstaller.archive.readers import CArchiveReader

reader = CArchiveReader(r'dist\ddesign_tool.exe')
toc = reader.toc

# 检查目标文件
targets = ['file_inventory', '使用方法', 'README.md', 'MODS_GUIDE.md']
for name in toc:
    name_str = name.decode('utf-8', errors='replace') if isinstance(name, bytes) else name
    for t in targets:
        if t in name_str:
            print(f'  [OK] {name_str}')
```

### 冒烟测试

```powershell
# 启动 EXE 等待 5 秒确认不崩溃
$proc = Start-Process "dist\ddesign_tool.exe" -PassThru
Start-Sleep -Seconds 5
if (-not $proc.HasExited) {
    Write-Host "EXE 正常运行"
    $proc.Kill()
}
```

---

## 7. 故障排查

| 症状 | 可能原因 | 解决方案 |
|------|---------|---------|
| `PermissionError` 打包时 | Excel 文件在 WPS/Excel 中打开 | 关闭所有 Excel 文件后重试 |
| 模组加载失败 ("No module named") | `hiddenimports` 未包含动态导入的模块 | 添加 `collect_submodules('package')` |
| EXE 找不到 data/ 文件 | `datas` 中路径错误或 glob 未匹配 | 检查源文件是否存在，glob 是否正确 |
| 打包后缺少 使用方法.md | datas 中遗漏 | 确认 `('使用方法.md', '.')` 在 datas 中 |
| 打包后缺少 file_inventory.xlsx | datas 中遗漏 | 确认 `('output/file_inventory.xlsx', '.')` 在 datas 中 |
| 污泥节点点击无反应 | `wuni_*` 模组未在 hiddenimports 中 | 使用 `collect_submodules('models')` (已配置) |
| 构建速度极慢 (>10min) | pandas tests 被误包含 | 检查 spec 中是否有 `collect_submodules('pandas.tests')` |

---

## 8. 打包历史

| 日期 | EXE 大小 | 嵌入资源数 | 变更 |
|------|---------|-----------|------|
| 2026-05-16 | 52 MB | 5 项 | 初始打包: mods, data, config, 2md, 1json |
| 2026-05-18 | 54.1 MB | 8 项 | +knowledge, +output_template, +社区模组, +hiddenimports 修复 |
| 2026-05-18 (v2) | 56.7 MB | 11 项 | +mod_calculation_formulas.tex, +污水/雨水计算逻辑.txt |
| 2026-05-19 | 54.1 MB | 13 项 | +使用方法.md, +file_inventory.xlsx |
| 2026-05-20 | 54.1 MB | 14 项 | +kuangjing.ddesign.json; MC式约定自动发现 (node_registry v3) |
| 2026-05-20 (v2) | 54.2 MB | 14 项 | MC式自包含模组迁移; L/B/D/H标准输出契约; 成本估算器简化; MODS_GUIDE v3.4 |

> **学习记录**: `.sisyphus/notepads/packaging-guide-2026-05-19.md`  
> **spec 文件**: `ddesign_tool.spec`  
> **路径函数**: `ddesign_tool/src/_paths.py`

---

> **维护者**: yyx | **最后构建**: 2026-05-20 | **下次构建提醒**: 新增模组只需遵循命名约定 (models/{id}.py → {PascalCase}Node)，无需修改 node_registry
