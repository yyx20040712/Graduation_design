# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all, collect_submodules

datas = [
    ("ddesign_tool/mods", "mods"),
    ("ddesign_tool/data", "data"),
    ("ddesign_tool/resources", "resources"),
    (".sisyphus/notepads", "knowledge"),
]

hiddenimports = ["openpyxl.cell._writer"]
hiddenimports += collect_submodules("models")
hiddenimports += collect_submodules("mods.core")
hiddenimports += collect_submodules("mods.community")

binaries = []

tmp_ret = collect_all("openpyxl")
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all("pandas")
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ["ddesign_tool\\main.py"],
    pathex=["ddesign_tool/src", "ddesign_tool"],
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
    name="ddesign_tool",
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
