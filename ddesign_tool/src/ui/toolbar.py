"""
toolbar.py — 工具栏构建器 (extracted from main_window.py)

提供独立的工具栏/菜单栏构建函数,从主窗口解耦.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable


def build_toolbar(
    parent: tk.Toplevel,
    callbacks: dict[str, Callable[[], None]],
    pipe_var: tk.StringVar,
    pipe_files: list[str],
    add_node_menu: tk.Menu,
    **kwargs: tk.Widget,
) -> tk.Frame:
    """构建主窗口工具栏.

    Args:
        parent: 父窗口 (MainWindow)
        callbacks: 回调函数映射 {
            "new", "open", "save", "save_as",
            "calc_all", "clear_cache",
            "pipe_hydraulic_sewage", "pipe_hydraulic_rain",
            "calc_pipe_cost", "export_cost", "export_all",
            "validate_quick", "validate_deep",
            "add_node": Callable[[str], None],
            "delete_node",
        }
        pipe_var: 管网文件选择 StringVar
        pipe_files: 可选的管网文件列表
        add_node_menu: 添加节点菜单 (从 ModManager 构建)

    Returns:
        工具栏 Frame
    """
    tb = tk.Frame(parent, bg="#2d2d2d", height=42)
    tb.pack(side=tk.TOP, fill=tk.X)
    tb.pack_propagate(False)

    # ── 文件菜单 ──
    file_btn = tk.Menubutton(
        tb,
        text="📁 文件",
        bg="#3a3a3a",
        fg="#ccc",
        activebackground="#555",
        font=("Microsoft YaHei", 9),
    )
    file_menu = tk.Menu(
        file_btn,
        tearoff=0,
        bg="#333",
        fg="#ccc",
        activebackground="#555",
        activeforeground="#fff",
    )
    file_menu.add_command(label="新建  Ctrl+N", command=callbacks.get("new"))
    file_menu.add_command(label="打开...  Ctrl+O", command=callbacks.get("open"))
    file_menu.add_separator()
    file_menu.add_command(label="保存  Ctrl+S", command=callbacks.get("save"))
    file_menu.add_command(
        label="另存为...  Ctrl+Shift+S", command=callbacks.get("save_as")
    )
    file_menu.add_separator()
    file_btn.config(menu=file_menu)
    file_btn.pack(side=tk.LEFT, padx=2, pady=4)

    ttk.Separator(tb, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=2, pady=4)

    # ── 工具菜单 ──
    tool_btn = tk.Menubutton(
        tb,
        text="🔧 工具",
        bg="#3a3a3a",
        fg="#ccc",
        activebackground="#555",
        font=("Microsoft YaHei", 9),
    )
    tool_menu = tk.Menu(
        tool_btn,
        tearoff=0,
        bg="#333",
        fg="#ccc",
        activebackground="#555",
        activeforeground="#fff",
    )
    tool_menu.add_command(
        label="模组验证器 (快速)", command=callbacks.get("validate_quick")
    )
    tool_menu.add_command(
        label="模组验证器 (深度)", command=callbacks.get("validate_deep")
    )
    tool_btn.config(menu=tool_menu)
    tool_btn.pack(side=tk.LEFT, padx=2, pady=4)

    ttk.Separator(tb, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=2, pady=4)

    # ── 操作按钮 ──
    ttk.Button(tb, text="▶ 全部计算 (F5)", command=callbacks.get("calc_all")).pack(
        side=tk.LEFT, padx=4, pady=4
    )
    ttk.Button(tb, text="🗑 清除缓存", command=callbacks.get("clear_cache")).pack(
        side=tk.LEFT, padx=4, pady=4
    )
    ttk.Button(
        tb, text="📏 污水水力计算", command=callbacks.get("pipe_hydraulic_sewage")
    ).pack(side=tk.LEFT, padx=4, pady=4)
    ttk.Button(
        tb, text="🌧 雨水水力计算", command=callbacks.get("pipe_hydraulic_rain")
    ).pack(side=tk.LEFT, padx=4, pady=4)
    ttk.Separator(tb, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=4, pady=4)
    ttk.Button(
        tb, text="💰 管网概算报告", command=callbacks.get("calc_pipe_cost")
    ).pack(side=tk.LEFT, padx=4, pady=4)
    ttk.Button(tb, text="📊 导出概算", command=callbacks.get("export_cost")).pack(
        side=tk.LEFT, padx=4, pady=4
    )
    ttk.Button(tb, text="📤 全部输出", command=callbacks.get("export_all")).pack(
        side=tk.LEFT, padx=4, pady=4
    )

    # ── 管网文件选择 ──
    ttk.Label(tb, text="管网:", background="#2d2d2d", foreground="#aaa").pack(
        side=tk.LEFT, padx=(8, 2)
    )
    pipe_cb = ttk.Combobox(
        tb, textvariable=pipe_var, values=pipe_files, state="readonly", width=16
    )
    pipe_cb.pack(side=tk.LEFT, padx=2)
    ttk.Button(tb, text="浏览...", command=callbacks.get("browse_pipe")).pack(
        side=tk.LEFT, padx=2
    )

    ttk.Separator(tb, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8, pady=4)

    # ── 添加节点菜单 ──
    add_btn = tk.Menubutton(
        tb,
        text="➕ 添加节点",
        bg="#3a3a3a",
        fg="#ccc",
        activebackground="#555",
        font=("Microsoft YaHei", 9),
    )
    add_btn.config(menu=add_node_menu)
    add_btn.pack(side=tk.LEFT, padx=2, pady=4)

    ttk.Button(tb, text="🗑 删除节点", command=callbacks.get("delete_node")).pack(
        side=tk.LEFT, padx=2, pady=4
    )

    return tb
