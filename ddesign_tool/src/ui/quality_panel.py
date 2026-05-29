"""
quality_panel.py — 水质面板组件 (v5.2 extracted from main_window.py)

管理水质 Tab 的全部 UI: 水质编辑卡片 + 全流程水质追踪。
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict, Optional

from _logging import get_logger

_log = get_logger(__name__)

# ── 模块级导入 (提前加载, 避免 EXE 打包后动态导入失败) ──
try:
    from models.base import NodeState  # noqa: F401 — used in _on_commit closure
except ImportError:
    NodeState = None  # type: ignore[assignment]
try:
    from models.node_registry import is_water_quality_node
except ImportError:
    def is_water_quality_node(_node_type: str) -> bool:
        return False

# 污染物颜色 & 标签 (模块级复用)
WQ_COLORS = {
    "BOD5": "#5599ff", "COD": "#ff9955", "SS": "#55cc55",
    "NH3N": "#cc55ff", "TN": "#ff55aa", "TP": "#55aaff",
}
WQ_LABELS = {
    "BOD5": "BOD₅", "COD": "COD", "SS": "SS",
    "NH3N": "NH₃-N", "TN": "TN", "TP": "TP",
}
WQ_INDICATORS = ["BOD5", "COD", "SS", "NH3N", "TN", "TP"]


class QualityPanel:
    """水质面板 — 管理水质编辑卡和全流程水质追踪.

    从 MainWindow 中分离, 通过回调与主窗口通信.
    """

    def __init__(
        self,
        parent_frame: tk.Frame,
        executor,
        status_var: tk.StringVar,
        node_items: dict,
        slider_vars: dict,
        on_view_results: Callable[[], None],
        on_reset_params: Callable[[object], None],
    ):
        self.parent = parent_frame
        self.executor = executor
        self.status_var = status_var
        self.node_items = node_items
        self._slider_vars = slider_vars

        self._on_view_results = on_view_results
        self._on_reset_params = on_reset_params

        self._dirty_callback: Optional[Callable[[], None]] = None
        self._quality_sections: Dict[str, tk.Frame] = {}
        self._quality_canvas: Optional[tk.Canvas] = None

    def set_dirty_callback(self, cb: Callable[[], None]) -> None:
        self._dirty_callback = cb

    def _mark_dirty(self) -> None:
        if self._dirty_callback:
            self._dirty_callback()

    # ═══════════════ 公开 API ═══════════════

    def show_water_quality_card(self, be, parent_frame=None):
        """水质编辑卡片 — 彩色卡片式水污染物参数编辑."""
        if parent_frame is None:
            parent_frame = self.parent

        for w in parent_frame.winfo_children():
            w.destroy()

        is_mine = be.NODE_TYPE == "kw_input"
        water_label = "进水水质 — 矿井水" if is_mine else "进水水质 — 城市污水"
        std_ref = (
            "GB3838-2002 地表水III类"
            if is_mine
            else "参考: 中期报告表3-1 | 出水执行一级A标准 (GB18918-2002)"
        )
        std_name = "GB3838-2002 地表水III类" if is_mine else "GB18918-2002 一级A"

        canvas = tk.Canvas(parent_frame, bg="#1a1a1a", highlightthickness=0)
        scrollbar = tk.Scrollbar(
            parent_frame, orient=tk.VERTICAL, command=canvas.yview, width=8
        )
        cards_frame = tk.Frame(canvas, bg="#1a1a1a")
        cards_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=cards_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.bind(
            "<MouseWheel>", lambda e: canvas.yview_scroll(int(-e.delta / 120), "units")
        )
        canvas.bind("<Enter>", lambda e: canvas.focus_set())
        cards_frame.bind(
            "<MouseWheel>", lambda e: canvas.yview_scroll(int(-e.delta / 120), "units")
        )

        tk.Label(
            cards_frame, text=f"▎{water_label}",
            bg="#1a1a1a", fg="#fff",
            font=("Microsoft YaHei", 12, "bold"),
        ).pack(anchor="w", padx=10, pady=(10, 2))
        tk.Label(
            cards_frame, text=std_ref,
            bg="#1a1a1a", fg="#888",
            font=("Microsoft YaHei", 8),
        ).pack(anchor="w", padx=10, pady=(0, 8))

        effluent_std = get_effluent_std(be, self.executor)
        WQ_RANGES = {
            "BOD5": (50, 500), "COD": (100, 1000), "SS": (50, 600),
            "NH3N": (5, 80), "TN": (10, 100), "TP": (1, 20),
        }

        for attr in WQ_INDICATORS:
            color = WQ_COLORS[attr]
            label = WQ_LABELS[attr]
            std_val = effluent_std.get(attr)
            min_v, max_v = WQ_RANGES.get(attr, (0, 1000))

            if hasattr(be, "water_quality"):
                current_val = getattr(be.water_quality, attr)
            else:
                current_val = be.get_param(attr)

            row = tk.Frame(cards_frame, bg="#2d2d2d", bd=1, relief=tk.GROOVE)
            row.pack(fill=tk.X, padx=6, pady=1)

            bar = tk.Frame(row, bg=color, width=4)
            bar.pack(side=tk.LEFT, fill=tk.Y)

            name_frame = tk.Frame(row, bg="#2d2d2d")
            name_frame.pack(side=tk.LEFT, padx=(6, 4))
            tk.Label(
                name_frame, text=label, bg="#2d2d2d", fg=color,
                font=("Microsoft YaHei", 9, "bold"), width=6, anchor="w",
            ).pack()
            if std_val is not None:
                tk.Label(
                    name_frame, text=f"≤{std_val}", bg="#2d2d2d", fg="#777",
                    font=("Microsoft YaHei", 7),
                ).pack()

            str_var = tk.StringVar(value=str(current_val))
            entry = tk.Entry(
                row, textvariable=str_var, width=6,
                bg="#1a1a1a", fg="#ffaa44", insertbackground="#fff",
                font=("Consolas", 10), justify=tk.RIGHT,
            )
            entry.pack(side=tk.LEFT, padx=4)

            var = tk.DoubleVar(value=current_val)
            self._slider_vars[attr] = var

            def _sync_entry(k=attr, sv=str_var, dv=var):
                try:
                    val = float(sv.get())
                    dv.set(val)
                except (ValueError, tk.TclError):
                    pass

            def _sync_slider(k=attr, sv=str_var, dv=var):
                val = dv.get()
                sv.set(str(round(val, 6)).rstrip("0").rstrip("."))

            def _on_commit(val_str, a=attr, be_node=be):
                val = float(val_str)
                if hasattr(be_node, "water_quality"):
                    setattr(be_node.water_quality, a, val)
                    # Sync to _params if method exists (WaterQualityNode);
                    # InputNode/KwInputNode may also have it after fix
                    if hasattr(be_node, "_sync_quality_to_params"):
                        be_node._sync_quality_to_params()
                    elif a in getattr(be_node, "_params", {}):
                        be_node._params[a] = val
                    # Mark node DIRTY so F5 will recalculate
                    if NodeState is not None:
                        try:
                            be_node.state = NodeState.DIRTY
                        except AttributeError:
                            pass
                else:
                    be_node.set_param(a, val)
                self._mark_dirty()
                self.status_var.set(
                    f"{be_node.NODE_NAME} {WQ_LABELS[a]}: {val:.1f} mg/L"
                )

            entry.bind("<Return>", lambda e, f=_sync_entry, g=_on_commit,
                       sv=str_var: (f(), g(sv.get())))

            def _on_focus(e, f=_sync_entry, g=_on_commit, sv=str_var):
                self.parent.after(10, lambda: (
                    f() if self.parent.focus_get() is not None else None,
                    g(sv.get()) if self.parent.focus_get() is not None else None,
                ))

            entry.bind("<FocusOut>", _on_focus)

            scale = tk.Scale(
                row, from_=min_v, to=max_v, resolution=0.5,
                orient=tk.HORIZONTAL, variable=var,
                bg="#2d2d2d", fg=color, troughcolor="#3a3a3a",
                highlightthickness=0, length=160,
            )
            scale.bind("<ButtonRelease-1>", lambda e, f=_sync_slider,
                       g=_on_commit, sv=str_var, dv=var: (f(), g(str(dv.get()))))
            scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)

            tk.Label(
                row, text="mg/L", bg="#2d2d2d", fg="#888",
                font=("Microsoft YaHei", 8),
            ).pack(side=tk.RIGHT, padx=4)

        # 底部: 排放标准参考
        sep = tk.Frame(cards_frame, bg="#444", height=1)
        sep.pack(fill=tk.X, padx=8, pady=(12, 6))
        tk.Label(
            cards_frame, text=f"▎排放标准参照 — {std_name}",
            bg="#1a1a1a", fg="#ffaa44",
            font=("Microsoft YaHei", 10, "bold"),
        ).pack(anchor="w", padx=10)

        for s_attr, s_lbl in [
            ("BOD5", "BOD₅"), ("COD", "COD"), ("SS", "SS"),
            ("NH3N", "NH₃-N"), ("TN", "TN"), ("TP", "TP"),
        ]:
            val = effluent_std.get(s_attr)
            if val is not None:
                r = tk.Frame(cards_frame, bg="#1a1a1a")
                r.pack(fill=tk.X, padx=16, pady=1)
                tk.Label(r, text=f"{s_lbl} ≤ {val} mg/L",
                         bg="#1a1a1a", fg="#aaa",
                         font=("Microsoft YaHei", 9)).pack(anchor="w")

        btn_frame = tk.Frame(cards_frame, bg="#1a1a1a")
        btn_frame.pack(fill=tk.X, padx=10, pady=(10, 8))
        ttk.Button(btn_frame, text="查看此节点结果",
                   command=self._on_view_results).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frame, text="重置默认值",
                   command=lambda: self._on_reset_params(be)).pack(side=tk.LEFT, padx=4)

    def build_full_quality_flow(self, scroll_to_node_id=None):
        """全流程水质追踪 — 按水流顺序排列所有工艺节点的水质变化表."""
        # ── v5.4-s7: 冷启动修复 — 强制父 frame 获得正确几何尺寸 ──
        # 第一次运行时 quality_text 可能未被 tkinter 分配实际像素
        # (> 1x1)，导致内部 canvas 不可见。
        # 手动读取 reqwidth/reqheight 并显式设置 config 强制分配。
        self.parent.update_idletasks()
        pw = self.parent.winfo_width()
        ph = self.parent.winfo_height()
        if pw <= 1:
            pw = self.parent.winfo_reqwidth()
        if ph <= 1:
            ph = self.parent.winfo_reqheight()
        if pw > 1 and ph > 1:
            self.parent.config(width=pw, height=ph)
        for w in self.parent.winfo_children():
            w.destroy()

        canvas = tk.Canvas(self.parent, bg="#1a1a1a", highlightthickness=0)
        scrollbar = tk.Scrollbar(
            self.parent, orient=tk.VERTICAL, command=canvas.yview, width=8
        )
        flow_frame = tk.Frame(canvas, bg="#1a1a1a")
        flow_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=flow_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.bind(
            "<MouseWheel>", lambda e: canvas.yview_scroll(int(-e.delta / 120), "units")
        )
        canvas.bind("<Enter>", lambda e: canvas.focus_set())
        flow_frame.bind(
            "<MouseWheel>", lambda e: canvas.yview_scroll(int(-e.delta / 120), "units")
        )

        tk.Label(
            flow_frame, text="▎全流程水质追踪",
            bg="#1a1a1a", fg="#fff",
            font=("Microsoft YaHei", 12, "bold"),
        ).pack(anchor="w", padx=10, pady=(10, 2))
        tk.Label(
            flow_frame, text="按水流方向依次排列 | 点击画布节点可快速跳转",
            bg="#1a1a1a", fg="#888",
            font=("Microsoft YaHei", 8),
        ).pack(anchor="w", padx=10, pady=(0, 8))

        try:
            order = self.executor.topological_order()
        except RuntimeError:
            order = list(self.executor._nodes.keys())

        self._quality_sections = {}
        has_any_data = False
        node_count = 0  # v5.4-s7: 诊断计数

        for nid in order:
            node = self.executor._nodes.get(nid)
            if not node or not node.result or not node.result.success:
                continue
            result = node.result
            inlet = result.inlet_quality
            outlet = result.outlet_quality
            if not inlet or not outlet:
                continue
            if is_water_quality_node(node.NODE_TYPE):
                continue
            node_count += 1

            has_any_data = True
            section = tk.Frame(flow_frame, bg="#1a1a1a", bd=0,
                               highlightbackground="#333", highlightthickness=1)
            section.pack(fill=tk.X, padx=6, pady=(6, 2))
            self._quality_sections[nid] = section

            hdr = tk.Frame(section, bg="#2d2d2d")
            hdr.pack(fill=tk.X)
            tk.Label(hdr, text=f" ▎{node.NODE_NAME} ",
                     bg="#2d2d2d", fg="#ffaa44",
                     font=("Microsoft YaHei", 10, "bold")).pack(side=tk.LEFT)
            tk.Label(hdr, text=f"  {node.NODE_CATEGORY}  ",
                     bg="#2d2d2d", fg="#888",
                     font=("Microsoft YaHei", 8)).pack(side=tk.LEFT)

            effluent_std = get_effluent_std(node, self.executor)
            cards_wrap = tk.Frame(section, bg="#1a1a1a")
            cards_wrap.pack(fill=tk.X, padx=4, pady=2)

            # 列标题行
            col_hdr = tk.Frame(cards_wrap, bg="#2d2d2d")
            col_hdr.pack(fill=tk.X, padx=2)
            for txt, w, anchor in [
                (" 指标", 8, "w"), ("进水水质", 12, "e"), ("出水水质", 12, "e"),
                ("去除率", 10, "e"), ("标准", 10, "e"),
            ]:
                tk.Label(col_hdr, text=txt, bg="#2d2d2d",
                         fg="#ffaa44" if txt == " 指标" else "#aaa",
                         font=("Microsoft YaHei", 8, "bold" if txt == " 指标" else "normal"),
                         width=w, anchor=anchor).pack(side=tk.LEFT)

            for attr in WQ_INDICATORS:
                color = WQ_COLORS[attr]
                label = WQ_LABELS[attr]
                in_val = getattr(inlet, attr)
                out_val = getattr(outlet, attr)
                removal = (in_val - out_val) / in_val * 100 if in_val > 0 else 0
                std_val = effluent_std.get(attr)
                ok = out_val <= std_val if std_val else True

                row = tk.Frame(cards_wrap, bg="#1a1a1a", bd=0,
                               highlightbackground="#333", highlightthickness=1)
                row.pack(fill=tk.X, padx=2, pady=1)

                tk.Frame(row, bg=color, width=3).pack(side=tk.LEFT, fill=tk.Y)
                tk.Label(row, text=f" {label}", bg="#252525", fg=color,
                         font=("Microsoft YaHei", 9, "bold"),
                         width=9, anchor="w").pack(side=tk.LEFT)
                tk.Label(row, text=f"{in_val:.1f} mg/L", bg="#252525", fg="#ccc",
                         font=("Consolas", 9), width=12, anchor="e").pack(side=tk.LEFT)
                tk.Label(row, text=f"{out_val:.1f} mg/L", bg="#252525", fg="#ccc",
                         font=("Consolas", 9), width=12, anchor="e").pack(side=tk.LEFT)
                tk.Label(row, text=f"{removal:.1f}%", bg="#252525", fg="#55cc88",
                         font=("Consolas", 9), width=10, anchor="e").pack(side=tk.LEFT)
                if std_val is not None:
                    status = "✓" if ok else "✗"
                    sc = "#55cc88" if ok else "#ff6666"
                    tk.Label(row, text=f"≤{std_val} {status}", bg="#252525",
                             fg=sc, font=("Consolas", 9, "bold"),
                             width=10, anchor="e").pack(side=tk.LEFT)
                else:
                    tk.Label(row, text="—", bg="#252525", fg="#888",
                             font=("Consolas", 9), width=10, anchor="e").pack(side=tk.LEFT)

        if not has_any_data:
            _log.warning(
                "build_full_quality_flow: no data — %d total nodes, "
                "%d with quality data",
                len(order), node_count
            )
            tk.Label(
                flow_frame, text="(请先按 F5 计算，仅显示处理单元的水质变化)",
                bg="#1a1a1a", fg="#888",
                font=("Microsoft YaHei", 10),
            ).pack(pady=40)

        # ── 递归滚轮绑定: 确保鼠标在任何子组件上滚轮都生效 ──
        def _bind_wheel(widget, canvas_ref):
            widget.bind(
                "<MouseWheel>",
                lambda e: canvas_ref.yview_scroll(int(-e.delta / 120), "units"),
            )
            for child in widget.winfo_children():
                _bind_wheel(child, canvas_ref)

        _bind_wheel(flow_frame, canvas)

        if scroll_to_node_id and scroll_to_node_id in self._quality_sections:
            self._quality_canvas = canvas
            self.parent.after(100, lambda: self._scroll_to(scroll_to_node_id))

    def _scroll_to(self, node_id: str):
        section = self._quality_sections.get(node_id)
        canvas = getattr(self, "_quality_canvas", None)
        if not section or not canvas:
            return
        try:
            canvas.update_idletasks()
            bbox = canvas.bbox("all")
            if bbox and bbox[3] > 0:
                y_offset = section.winfo_y()
                fraction = max(0.0, min(1.0, y_offset / bbox[3]))
                canvas.yview_moveto(fraction)
        except tk.TclError:
            pass  # canvas 已被销毁 (切换面板时重建)

    def scroll_to_section(self, node_id: str):
        """公开 API: 滚动到指定节点的水质节."""
        if hasattr(self, "_quality_sections") and self._quality_sections:
            if node_id in self._quality_sections:
                self._scroll_to(node_id)
            else:
                self.build_full_quality_flow(scroll_to_node_id=node_id)
        else:
            self.build_full_quality_flow(scroll_to_node_id=node_id)

    def build_quality_table(self, be, inlet, outlet):
        """单节点水质追踪 — 兼容旧接口."""
        self.build_full_quality_flow(scroll_to_node_id=be.node_id)


# ═══════════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════════


def get_effluent_std(node, executor) -> dict:
    """获取出水标准 — 按水类型自动选择."""
    is_mine = node.NODE_TYPE.startswith("kw_") or node.NODE_CATEGORY == "矿井水处理"
    if not is_mine and executor:
        for n in executor._nodes.values():
            if n.NODE_TYPE.startswith("kw_") or n.NODE_CATEGORY == "矿井水处理":
                is_mine = True
                break
    if is_mine:
        return {"BOD5": 4, "COD": 20, "SS": 70, "NH3N": 1.0, "TN": 1.0, "TP": 0.2}
    return {"BOD5": 10, "COD": 50, "SS": 10, "NH3N": 5, "TN": 15, "TP": 0.5}
