#!/usr/bin/env python3
"""
排水工程设计工具 — 程序入口

模式:
  GUI 模式 (默认):     ddesign_tool.exe
  CLI 验证模式:         ddesign_tool.exe --validate --all
  CLI 验证单个模组:     ddesign_tool.exe --validate --mod=tiaojiechi
  崩溃诊断:             ddesign_tool.exe --show-crash-log
  崩溃日志目录:         ddesign_tool.exe --crash-log-dir
"""

import os
import sys

# 源码模式: 添加 src/ 到 sys.path
_src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if os.path.isdir(_src) and _src not in sys.path:
    sys.path.insert(0, _src)

# ── 资源提取 (PyInstaller 打包环境: 首次运行自动释放资源到工作目录) ──
from src.bootstrap import extract_resources

extract_resources()

# ── 尽早安装崩溃处理器 ──
from crash_handler import install_crash_handler

install_crash_handler()


def _run_validator():
    """运行嵌入式模组验证器"""
    from validator import main as validator_main

    args = [a for a in sys.argv[1:] if a != "--validate"]
    return validator_main(args)


def main():
    # ── 崩溃诊断 CLI ──
    if "--show-crash-log" in sys.argv:
        from crash_handler import show_last_crash

        show_last_crash()
        return

    if "--crash-log-dir" in sys.argv:
        from crash_handler import open_crash_dir

        open_crash_dir()
        return

    # ── CLI 验证模式 ──
    if "--validate" in sys.argv:
        code = _run_validator()
        sys.exit(code)

    # ── 列出模组 ──
    if "--list-mods" in sys.argv:
        from mods.mod_manager import get_mod_manager

        mgr = get_mod_manager()
        mgr.load_all()
        from models.discretization import (
            _refresh_merged_configs,
            load_mod_discretizations,
        )

        _refresh_merged_configs()
        configs = load_mod_discretizations()
        for nt in sorted(configs.keys()):
            mod_info = mgr.get_mod_by_node_type(nt)
            name = mod_info.name if mod_info else nt
            print(f"  {nt:<25} {name}")
        return

    # ── 重新加载模组 (开发热更新) ──
    if "--reload-mods" in sys.argv:
        from mods.mod_manager import get_mod_manager

        mgr = get_mod_manager()
        mgr.reload()
        print(f"模组已重新加载: {mgr.get_load_summary()}")
        return

    # ── GUI 模式 ──
    from ui.main_window import MainWindow

    print("启动图形界面...")
    MainWindow.run()


if __name__ == "__main__":
    main()
