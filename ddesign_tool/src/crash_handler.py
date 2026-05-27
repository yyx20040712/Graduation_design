"""
crash_handler.py — 全局崩溃捕获与文件日志 (v5.3)

在 PyInstaller 打包后的 EXE 中, 用户看不到控制台输出。
此模块捕获所有未处理异常, 写入本地崩溃日志文件,
方便用户反馈问题时提供诊断信息。

使用:
    from crash_handler import install_crash_handler
    install_crash_handler()

CLI:
    ddesign_tool.exe --show-crash-log   # 查看最近一次崩溃日志
    ddesign_tool.exe --crash-log-dir    # 打开崩溃日志目录
"""

from __future__ import annotations

import os
import platform
import sys
import time
import traceback
from pathlib import Path


def _get_crash_dir() -> Path:
    """获取崩溃日志目录 (用户 AppData 下)"""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", os.path.expanduser("~")))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    crash_dir = base / "ddesign_tool" / "crash_logs"
    crash_dir.mkdir(parents=True, exist_ok=True)
    return crash_dir


def _get_version() -> str:
    """尝试获取 ddesign_tool 版本号"""
    try:
        import tomllib

        # 从打包后的 pyproject.toml 或源码路径查找
        candidates = [
            (
                Path(sys._MEIPASS) / "pyproject.toml"
                if getattr(sys, "frozen", False)
                else None
            ),
            Path(__file__).parent.parent / "pyproject.toml",
            Path.cwd() / "pyproject.toml",
        ]
        for p in candidates:
            if p and p.exists():
                with open(p, "rb") as f:
                    return tomllib.load(f)["project"].get("version", "unknown")
    except Exception:
        pass
    return "unknown"


def _get_mod_summary() -> str:
    """获取已加载模组的摘要"""
    try:
        from mods.mod_manager import get_mod_manager

        mgr = get_mod_manager()
        mgr.load_all()
        return mgr.get_load_summary()
    except Exception:
        return "unavailable"


def write_crash_log(exc_type, exc_value, exc_tb) -> Path | None:
    """将崩溃信息写入文件.

    Returns:
        日志文件路径, 写入失败返回 None
    """
    try:
        crash_dir = _get_crash_dir()
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        log_path = crash_dir / f"crash_{timestamp}.log"

        lines = []
        lines.append("=" * 72)
        lines.append("  ddesign_tool 崩溃报告")
        lines.append(f"  时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"  版本: {_get_version()}")
        lines.append("=" * 72)
        lines.append("")
        lines.append("── 系统信息 ──")
        lines.append(f"  OS:       {platform.system()} {platform.release()}")
        lines.append(f"  Python:   {sys.version}")
        lines.append(f"  Frozen:   {getattr(sys, 'frozen', False)}")
        lines.append(f"  Args:     {sys.argv}")
        lines.append(f"  CWD:      {os.getcwd()}")
        lines.append("")
        lines.append("── 模组状态 ──")
        lines.append(f"  {_get_mod_summary()}")
        lines.append("")
        lines.append("── 异常信息 ──")
        lines.append(f"  类型: {exc_type.__name__}")
        lines.append(f"  消息: {exc_value}")
        lines.append("")
        lines.append("── 调用栈 ──")
        lines.extend(traceback.format_tb(exc_tb))
        if exc_value:
            lines.append(f"{exc_type.__name__}: {exc_value}")

        with open(log_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        return log_path
    except Exception:
        return None


def _global_excepthook(exc_type, exc_value, exc_tb):
    """全局未处理异常钩子"""
    # 写入崩溃日志
    log_path = write_crash_log(exc_type, exc_value, exc_tb)

    # 尝试显示错误对话框 (tkinter 环境)
    msg = f"程序遇到未处理的错误:\n\n{exc_type.__name__}: {exc_value}"
    if log_path:
        msg += f"\n\n崩溃日志已保存到:\n{log_path}"
    msg += "\n\n请将此信息发送给开发者以协助修复。"

    try:
        import tkinter.messagebox as mb

        mb.showerror("ddesign_tool — 崩溃报告", msg)
    except Exception:
        # tkinter 不可用 (Headless/CLI 模式), 输出到 stderr
        print(msg, file=sys.stderr)

    # 调用默认处理 (打印 traceback)
    sys.__excepthook__(exc_type, exc_value, exc_tb)


def install_crash_handler():
    """安装全局崩溃处理器 (在 main.py 中尽早调用)"""
    sys.excepthook = _global_excepthook


def show_last_crash() -> str | None:
    """CLI: 显示最近一次崩溃日志内容"""
    crash_dir = _get_crash_dir()
    logs = sorted(crash_dir.glob("crash_*.log"), reverse=True)
    if not logs:
        print("没有找到崩溃日志。")
        return None
    latest = logs[0]
    print(f"最近崩溃: {latest.name}")
    print(
        f"时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(latest.stat().st_mtime))}"
    )
    print("-" * 60)
    with open(latest, encoding="utf-8") as f:
        content = f.read()
    print(content)
    return content


def open_crash_dir():
    """CLI: 打印崩溃日志目录路径"""
    crash_dir = _get_crash_dir()
    print(f"崩溃日志目录: {crash_dir}")
    logs = sorted(crash_dir.glob("crash_*.log"))
    if logs:
        print(f"共 {len(logs)} 个日志文件:")
        for log in logs:
            size = log.stat().st_size
            mtime = time.strftime("%Y-%m-%d %H:%M", time.localtime(log.stat().st_mtime))
            print(f"  {log.name}  ({size}B, {mtime})")
    else:
        print("  (空)")
    return str(crash_dir)
