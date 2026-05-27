#!/usr/bin/env python3
"""
排水工程设计工具 — 程序入口

用法:
  ddesign_tool                          GUI 模式 (默认)
  ddesign_tool validate --all           验证所有模组
  ddesign_tool validate --mod NAME      验证指定模组
  ddesign_tool list-mods                列出所有模组
  ddesign_tool reload-mods              热重载模组
  ddesign_tool crash-log                查看最近崩溃日志
  ddesign_tool crash-dir                打开崩溃日志目录
  ddesign_tool --version                显示版本号

兼容旧式调用:
  ddesign_tool --validate --all
  ddesign_tool --show-crash-log
"""

import argparse
import os
import sys

# 源码模式: 添加 src/ 到 sys.path
_src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if os.path.isdir(_src) and _src not in sys.path:
    sys.path.insert(0, _src)

# ── 资源提取 ──
from src.bootstrap import extract_resources

extract_resources()

# ── 尽早安装崩溃处理器 ──
from crash_handler import install_crash_handler

install_crash_handler()


def _cmd_validate(args):
    """验证模组"""
    from validator import main as validator_main

    argv = []
    if args.all_mods:
        argv.append("--all")
    if args.mod:
        argv.append(f"--mod={args.mod}")
    if args.deep:
        argv.append("--deep")
    if args.ci:
        argv.append("--ci")
    return validator_main(argv)


def _cmd_list_mods():
    """列出模组"""
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


def _cmd_reload_mods():
    """重载模组"""
    from mods.mod_manager import get_mod_manager

    mgr = get_mod_manager()
    mgr.reload()
    print(f"模组已重新加载: {mgr.get_load_summary()}")


def _cmd_crash_log():
    """查看崩溃日志"""
    from crash_handler import show_last_crash

    show_last_crash()


def _cmd_crash_dir():
    """崩溃日志目录"""
    from crash_handler import open_crash_dir

    open_crash_dir()


def _parse_args(argv: list[str] | None = None):
    """解析命令行参数 (argparse 子命令模式)"""
    parser = argparse.ArgumentParser(
        prog="ddesign_tool",
        description="排水工程设计工具 — 城镇污水处理厂全流程工艺设计",
    )
    parser.add_argument("--version", action="version", version="ddesign_tool v5.3.0")

    sub = parser.add_subparsers(dest="command", title="命令")

    # validate
    p_val = sub.add_parser("validate", help="运行模组验证器")
    p_val.add_argument(
        "--all", dest="all_mods", action="store_true", help="验证所有模组"
    )
    p_val.add_argument("--mod", help="验证指定模组 (node_type)")
    p_val.add_argument("--deep", action="store_true", help="深度验证模式")
    p_val.add_argument("--ci", action="store_true", help="CI 模式 (非零退出码)")

    # list-mods
    sub.add_parser("list-mods", help="列出所有模组")

    # reload-mods
    sub.add_parser("reload-mods", help="热重载模组")

    # crash-log
    sub.add_parser("crash-log", help="查看最近崩溃日志")

    # crash-dir
    sub.add_parser("crash-dir", help="打开崩溃日志目录")

    # ── 兼容旧式 --flag 风格调用 ──
    if argv is None:
        argv = sys.argv[1:]
    raw = " ".join(argv)

    # --show-crash-log → crash-log
    if "--show-crash-log" in raw and "crash-log" not in raw:
        return parser.parse_args(["crash-log"])
    # --crash-log-dir → crash-dir
    if "--crash-log-dir" in raw and "crash-dir" not in raw:
        return parser.parse_args(["crash-dir"])
    # --validate → validate
    if "--validate" in argv:
        compat = ["validate"]
        for a in argv:
            if a == "--validate":
                continue
            if a == "--all":
                compat.append("--all")
            elif a.startswith("--mod="):
                compat.append(a)
            elif a == "--deep":
                compat.append("--deep")
            elif a == "--ci":
                compat.append("--ci")
        return parser.parse_args(compat)
    # --list-mods → list-mods (兼容)
    if "--list-mods" in raw and "list-mods" not in raw:
        return parser.parse_args(["list-mods"])
    # --reload-mods → reload-mods (兼容)
    if "--reload-mods" in raw and "reload-mods" not in raw:
        return parser.parse_args(["reload-mods"])

    return parser.parse_args(argv)


def main():
    args = _parse_args()

    if args.command == "validate":
        code = _cmd_validate(args)
        sys.exit(code)
    elif args.command == "list-mods":
        _cmd_list_mods()
    elif args.command == "reload-mods":
        _cmd_reload_mods()
    elif args.command == "crash-log":
        _cmd_crash_log()
    elif args.command == "crash-dir":
        _cmd_crash_dir()
    else:
        # ── GUI 模式 ──
        from ui.main_window import MainWindow

        print("启动图形界面...")
        MainWindow.run()


if __name__ == "__main__":
    main()
