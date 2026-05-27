# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_submodules
import glob as _glob

# Collect data files excluding Excel temp files (~$*)
_data_files = [f for f in _glob.glob('ddesign_tool/data/*.xlsx') if '~$' not in f]

datas = [
    ('ddesign_tool/config.ini', '.'),
    ('ddesign_tool/mods', 'mods'),
    ('.sisyphus/notepads', 'knowledge'),
    ('MODS_GUIDE.md', '.'),
    ('README.md', '.'),
    ('使用方法.md', '.'),
    ('tests/yyx.ddesign.json', '.'),
    ('tests/kuangjing.ddesign.json', '.'),
    ('output/engineering_cost_estimation.tex', 'output_template'),
    ('output/system_design_manual.tex', 'output_template'),
    ('output/mod_calculation_formulas.tex', 'output_template'),
    ('output/污水计算逻辑.txt', 'output_template'),
    ('output/雨水计算逻辑.txt', 'output_template'),
    ('output/file_inventory.xlsx', '.'),
] + [(f, 'data') for f in _data_files]
binaries = []
hiddenimports = ['openpyxl.cell._writer']

# ── 自动发现 models/ 下所有引擎子模块 ──
hiddenimports += collect_submodules('models')

# ── 模组模块 (ddesign_tool/mods/core/) ──
# ModManager 通过 importlib.import_module() 动态加载，
# PyInstaller 静态分析无法追踪 → 必须显式声明。
# mods/ 作为数据文件嵌入 (见 datas)，但 __init__.py 需要作为 Python 模块收集。
hiddenimports += collect_submodules('mods.core')
hiddenimports += collect_submodules('mods.community')

tmp_ret = collect_all('openpyxl')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('pandas')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['ddesign_tool\\main.py'],
    pathex=['ddesign_tool/src', 'ddesign_tool'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ddesign_tool',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
