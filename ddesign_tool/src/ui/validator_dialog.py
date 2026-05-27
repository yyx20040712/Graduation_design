"""
validator_dialog.py — 模组验证器对话框 (extracted from main_window.py)

提供独立的验证器结果展示窗口,从主窗口解耦.
"""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk
from typing import Any


def run_validator_dialog(
    parent: tk.Toplevel, status_var: tk.StringVar, mode: str = "quick"
) -> None:
    """在后台线程运行验证器,完成后显示结果对话框.

    Args:
        parent: 父窗口 (MainWindow)
        status_var: 状态栏 StringVar
        mode: "quick" 或 "deep"
    """
    status_var.set(f"正在运行模组验证 ({mode})...")
    parent.update_idletasks()

    result_holder: dict[str, Any] = {}

    def _run() -> None:
        try:
            from validator.engine import ModValidator

            validator = ModValidator()
            total = validator.validate_all(mode)
            result_holder["total"] = total
        except Exception as e:
            result_holder["error"] = str(e)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    def _check_done() -> None:
        if "total" in result_holder:
            total = result_holder["total"]
            _show_result_dialog(parent, total, mode)
            status_var.set(
                f"验证完成: {total.healthy_mods}/{total.total_mods} 模组健康"
            )
            return
        if "error" in result_holder:
            status_var.set(f"验证失败: {result_holder['error']}")
            return
        parent.after(200, _check_done)

    parent.after(100, _check_done)


def _show_result_dialog(parent: tk.Toplevel, total: Any, mode: str) -> None:
    """显示验证结果对话框.

    Args:
        parent: 父窗口
        total: ValidationReport 对象
        mode: 验证模式名称
    """
    dialog = tk.Toplevel(parent)
    dialog.title(f"模组验证报告 — {mode}")
    dialog.geometry("800x600")
    dialog.configure(bg="#1e1e1e")

    # 汇总
    summary = tk.Frame(dialog, bg="#2d2d2d", padx=16, pady=12)
    summary.pack(fill=tk.X)

    tk.Label(
        summary,
        text="模组验证报告",
        bg="#2d2d2d",
        fg="#fff",
        font=("Microsoft YaHei", 14, "bold"),
    ).pack(anchor="w")
    tk.Label(
        summary,
        text=f"{total.total_mods} 模组 | "
        f"PASS: {total.total_passed} | WARN: {total.total_warnings} | "
        f"FAIL: {total.total_failures} | ERROR: {total.total_errors} | "
        f"{total.duration_ms:.0f}ms",
        bg="#2d2d2d",
        fg="#888",
    ).pack(anchor="w", pady=(4, 0))

    # 滚动列表
    canvas = tk.Canvas(dialog, bg="#1e1e1e", highlightthickness=0)
    scrollbar = ttk.Scrollbar(dialog, orient=tk.VERTICAL, command=canvas.yview)
    frame = tk.Frame(canvas, bg="#1e1e1e")
    frame.bind(
        "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )
    canvas.create_window((0, 0), window=frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=8)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    for report in total.reports:
        healthy = report.healthy
        bg = "#2d2d2d"
        border_color = "#4caf50" if healthy else "#f44336"

        card = tk.Frame(
            frame,
            bg=bg,
            bd=1,
            relief=tk.SOLID,
            highlightbackground=border_color,
            highlightthickness=1,
        )
        card.pack(fill=tk.X, pady=2, padx=4)

        header = tk.Frame(card, bg=bg, padx=10, pady=6)
        header.pack(fill=tk.X)
        status = "PASS" if healthy else "FAIL"
        status_c = "#4caf50" if healthy else "#f44336"

        tk.Label(
            header,
            text=f"{report.mod_name}",
            bg=bg,
            fg="#fff",
            font=("Microsoft YaHei", 10, "bold"),
        ).pack(side=tk.LEFT)
        tk.Label(
            header,
            text=f"({report.node_type})",
            bg=bg,
            fg="#888",
            font=("Microsoft YaHei", 8),
        ).pack(side=tk.LEFT, padx=6)
        tk.Label(
            header,
            text=f"P:{report.passed} W:{report.warnings} "
            f"F:{report.failures} E:{report.errors}",
            bg=bg,
            fg="#888",
            font=("Consolas", 9),
        ).pack(side=tk.RIGHT, padx=6)
        tk.Label(
            header,
            text=status,
            bg=status_c,
            fg="#fff",
            font=("Microsoft YaHei", 8, "bold"),
            padx=8,
        ).pack(side=tk.RIGHT)

        for result in report.results:
            if result.severity >= 2 and healthy:
                continue
            color_map = {0: "#f44336", 1: "#f44336", 2: "#ff9800", 3: "#4caf50"}
            icon_map = {0: "ERR ", 1: "FAIL", 2: "WARN", 3: "PASS"}
            c = color_map.get(result.severity, "#888")
            icon = icon_map.get(result.severity, "???")

            detail_frame = tk.Frame(card, bg="#252525", padx=10, pady=3)
            detail_frame.pack(fill=tk.X)
            tk.Label(
                detail_frame,
                text=f"  [{icon}]",
                bg="#252525",
                fg=c,
                font=("Consolas", 9, "bold"),
            ).pack(side=tk.LEFT)
            tk.Label(
                detail_frame,
                text=f" {result.name}: {result.message}",
                bg="#252525",
                fg="#aaa",
                font=("Microsoft YaHei", 9),
            ).pack(side=tk.LEFT)

    # 按钮
    btn_frame = tk.Frame(dialog, bg="#1e1e1e", padx=16, pady=10)
    btn_frame.pack(fill=tk.X)
    ttk.Button(btn_frame, text="关闭", command=dialog.destroy).pack(side=tk.RIGHT)
    ttk.Button(
        btn_frame, text="导出 HTML 报告", command=lambda: _export_html(total)
    ).pack(side=tk.RIGHT, padx=8)


def _export_html(total: Any) -> None:
    """导出验证报告为 HTML 文件."""
    from tkinter import filedialog

    filepath = filedialog.asksaveasfilename(
        defaultextension=".html",
        filetypes=[("HTML 报告", "*.html")],
        initialfile="validator_report.html",
    )
    if filepath:
        from validator.reporters.html import HTMLReporter

        HTMLReporter().save(total.reports, filepath)
