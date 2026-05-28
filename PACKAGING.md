# 📦 打包指南 — ddesign_tool v5.3

> **打包方式**: PyInstaller (单目录 EXE, ~56 MB)
> **最后更新**: 2026-05-28
> **构建命令**: `pyinstaller ddesign_tool.spec --clean --log-level=WARN`

---

## 1. 快速开始

```powershell
# 确保虚拟环境已激活
.\.venv\Scripts\activate

# 构建 EXE
pyinstaller ddesign_tool.spec --clean --log-level=WARN

# 验证
dist\ddesign_tool\ddesign_tool.exe validate --all
```

---

## 2. 打包架构

```
ddesign_tool.spec
  ├── Analysis: ddesign_tool/main.py
  │   ├── datas: config.ini, mods/, output_templates, test projects
  │   ├── hiddenimports: openpyxl, models.*, mods.core.*, mods.community.*
  │   └── collect_all: openpyxl, pandas
  ├── PYZ: pure Python bytecode
  └── EXE: ddesign_tool.exe (~56 MB)
```

**关键**: mods/ 既作为 data files 嵌入, 也通过 hiddenimports 收集 Python 子模块. ModManager 通过 `importlib.import_module()` 动态加载, PyInstaller 静态分析无法追踪.

---

## 3. 嵌入资源清单

| 源路径 | 目标路径 | 说明 |
|--------|---------|------|
| `ddesign_tool/config.ini` | `.` | 设计参数配置 |
| `ddesign_tool/mods/` | `mods/` | 全部 34 模组 |
| `output/*.tex` | `output_template/` | LaTeX 模板 |
| `output/*.txt` | `output_template/` | 计算逻辑文档 |
| `tests/yyx.ddesign.json` | `.` | 演示项目 |
| `tests/kuangjing.ddesign.json` | `.` | 矿井水演示 |
| `使用方法.txt` | `.` | 使用指南 |
| `README.md` | `.` | 项目说明 |

---

## 4. 路径解析 (源码 vs EXE)

```python
# _paths.py 自动检测运行环境
def get_mods_dir():
    if is_frozen():         # PyInstaller EXE
        return os.path.join(os.getcwd(), "mods")
    return os.path.join(get_app_root(), "mods")  # 源码
```

---

## 5. 验证清单

- [ ] `dist/ddesign_tool/ddesign_tool.exe validate --all` → 121 PASS
- [ ] EXE 大小 ~56 MB
- [ ] 冷启动 < 3s
- [ ] 所有 34 模组可加载
- [ ] GUI 可正常启动
- [ ] 崩溃日志写入 `%APPDATA%/ddesign_tool/crash_logs/`

---

## 6. Docker 构建 (可选)

```bash
docker build -t ddesign_tool .
docker run ddesign_tool validate --all --ci
```

---

## 7. 故障排查

| 问题 | 解决 |
|------|------|
| `ModuleNotFoundError: models` | 确认 `pathex` 包含 `ddesign_tool/src` |
| EXE 找不到 mods | 确认 mods 目录与 EXE 同级 |
| pandas 导入错误 | 添加 `collect_all('pandas')` |
| 模组加载失败 | 检查 `hiddenimports` 是否包含该模组 |

---

> **维护者**: yyx | **版本**: v5.3 | **更新**: 2026-05-28
