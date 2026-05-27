"""
main_window.py v3 — 主窗口 (参数面板 + 公式 + 约束反馈)
"""

from __future__ import annotations

import os
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Optional

try:
    from _paths import get_data_dir, get_output_dir, setup_import_paths
except ImportError:
    from src._paths import get_data_dir, setup_import_paths  # type: ignore
setup_import_paths()
from _logging import get_logger
from controller.graph_executor import GraphExecutor
from controller.project_manager import ProjectManager, get_project_manager
from models.base import NodeState, WaterFlow, WaterQuality
from models.combiner import CombinerNode
from models.discretization import get_allowed_values
from models.node_registry import (
    has_solution_space,
)
from models.node_registry import is_io_node as _is_io_node
from models.node_registry import (
    is_water_quality_node,
)
from models.pipe_network import PipeNetworkNode
from models.water_quality_node import WaterQualityNode
from ui.canvas_view import NodeCanvas
from ui.export_handlers import (
    calc_pipe_cost_report,
    export_all_results,
    export_cost_report,
)
from ui.file_manager import FileManager
from ui.logger import log
from ui.quality_panel import QualityPanel, get_effluent_std
from ui.solution_browser import SolutionBrowser
from ui.validator_dialog import run_validator_dialog

from mods.mod_manager import get_mod_manager

_log = get_logger(__name__)


def _register_infra_nodes() -> None:
    """注册基础设施节点到 ModManager (数据源自节点类自身, 消除硬编码)."""
    mgr = get_mod_manager()
    if mgr._node_registry:
        return  # 已注册
    mgr.register_infra_node(
        "pipe_network",
        PipeNetworkNode,
        "管网输入",
        formula="从 Excel「计算结果」sheet 读取管网末端的累计设计流量 (L/s)\n"
        "Q_design = 读取值/1000 (m³/s, 已含Kz)\n管道统计: 按管径汇总铺设长度",
    )
    mgr.register_infra_node(
        "water_quality",
        WaterQualityNode,
        "进水水质",
        formula="设置进水水质指标 (mg/L):\n"
        "BOD5(生化需氧量), COD(化学需氧量), SS(悬浮固体),\n"
        "NH3N(氨氮), TN(总氮), TP(总磷)",
        show_water_quality_card=True,
    )
    mgr.register_infra_node(
        "combiner",
        CombinerNode,
        "合并",
        formula="合并: WATER(上游水量) + QUALITY(上游水质) → MIXED(下游输入)",
    )

    # ═══════════════ 查询/获取 ═══════════════


def _get_node_registry() -> Dict[str, tuple]:
    """获取完整的节点注册表 (全部来自 ModManager)."""
    mgr = get_mod_manager()
    mgr.load_all()
    _register_infra_nodes()
    return dict(mgr.node_registry)


def _get_formulas() -> Dict[str, str]:
    """获取公式说明 (全部来自 ModManager, 无硬编码)."""
    mgr = get_mod_manager()
    mgr.load_all()
    _register_infra_nodes()
    return dict(mgr.formulas)


class MainWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("排水工程设计工具 v3")
        self.geometry("1500x850")
        self.configure(bg="#1a1a1a")
        self.executor = GraphExecutor()
        self._pm = get_project_manager()
        self.node_items: Dict[str, "NodeItem"] = {}  # noqa: F821 — forward ref via annotations
        self._pipe_node: Optional[PipeNetworkNode] = None
        self._selected_id: Optional[str] = None
        self._slider_vars: Dict[str, tk.DoubleVar] = {}
        self._browse_mode = True  # True=方案浏览, False=手动微调
        self._solution_browser: Optional[SolutionBrowser] = None
        self._dirty = False  # 是否有未保存的修改
        self.file_manager = FileManager(self)
        self._build_ui()
        self._load_demo()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # 子面板 (v5.2 提取)
        self._quality_panel = QualityPanel(
            parent_frame=self.quality_text,
            executor=self.executor,
            status_var=self.status_var,
            node_items=self.node_items,
            slider_vars=self._slider_vars,
            on_view_results=self._view_results,
            on_reset_params=self._reset_params,
        )
        self._quality_panel.set_dirty_callback(lambda: setattr(self, '_dirty', True))

    # ═══════════════════ UI 构建 ═══════════════════

    def _build_ui(self):
        tb = tk.Frame(self, bg="#2d2d2d", height=42)
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
        file_menu.add_command(label="新建  Ctrl+N", command=self._on_new)
        file_menu.add_command(label="打开...  Ctrl+O", command=self._on_open)
        file_menu.add_separator()
        file_menu.add_command(label="保存  Ctrl+S", command=self._on_save)
        file_menu.add_command(label="另存为...  Ctrl+Shift+S", command=self._on_save_as)
        file_menu.add_separator()
        # 最近文件子菜单
        self._recent_menu = tk.Menu(
            file_menu,
            tearoff=0,
            bg="#333",
            fg="#ccc",
            activebackground="#555",
            activeforeground="#fff",
        )
        file_menu.add_cascade(label="最近文件", menu=self._recent_menu)
        self._update_recent_menu()
        file_btn.config(menu=file_menu)
        file_btn.pack(side=tk.LEFT, padx=2, pady=4)
        ttk.Separator(tb, orient=tk.VERTICAL).pack(
            side=tk.LEFT, fill=tk.Y, padx=2, pady=4
        )
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
            label="模组验证器 (快速)", command=self._on_validate_quick
        )
        tool_menu.add_command(label="模组验证器 (深度)", command=self._on_validate_deep)
        tool_menu.add_separator()
        tool_menu.add_command(label="🔍 系统自检", command=self._on_self_test)
        tool_btn.config(menu=tool_menu)
        tool_btn.pack(side=tk.LEFT, padx=2, pady=4)
        ttk.Separator(tb, orient=tk.VERTICAL).pack(
            side=tk.LEFT, fill=tk.Y, padx=2, pady=4
        )
        self.bind_all("<Control-n>", lambda e: self._on_new())
        self.bind_all("<Control-o>", lambda e: self._on_open())
        self.bind_all("<Control-s>", lambda e: self._on_save())
        self.bind_all("<Control-S>", lambda e: self._on_save_as())
        # ── 计算按钮 ──
        ttk.Button(tb, text="▶ 全部计算 (F5)", command=self._on_calc_all).pack(
            side=tk.LEFT, padx=4, pady=4
        )
        ttk.Button(tb, text="🗑 清除缓存", command=self._on_clear_cache).pack(
            side=tk.LEFT, padx=4, pady=4
        )
        ttk.Button(
            tb, text="📏 污水水力计算", command=lambda: self._on_pipe_hydraulic("污水")
        ).pack(side=tk.LEFT, padx=4, pady=4)
        ttk.Button(
            tb, text="🌧 雨水水力计算", command=lambda: self._on_pipe_hydraulic("雨水")
        ).pack(side=tk.LEFT, padx=4, pady=4)
        ttk.Separator(tb, orient=tk.VERTICAL).pack(
            side=tk.LEFT, fill=tk.Y, padx=4, pady=4
        )
        ttk.Button(tb, text="💰 管网概算报告", command=self._on_calc_pipe_cost).pack(
            side=tk.LEFT, padx=4, pady=4
        )
        ttk.Button(tb, text="📊 导出概算", command=self._on_export_cost).pack(
            side=tk.LEFT, padx=4, pady=4
        )
        ttk.Button(tb, text="📤 全部输出", command=self._on_export_all).pack(
            side=tk.LEFT, padx=4, pady=4
        )
        ttk.Label(tb, text="管网:", background="#2d2d2d", foreground="#aaa").pack(
            side=tk.LEFT, padx=(8, 2)
        )
        self.pipe_var = tk.StringVar(value="pipe_final.xlsx")
        pipe_files = self._get_data_pipe_files()
        self._pipe_cb = ttk.Combobox(
            tb,
            textvariable=self.pipe_var,
            values=pipe_files,
            state="readonly",
            width=16,
        )
        self._pipe_cb.pack(side=tk.LEFT, padx=2)
        self._pipe_cb.bind("<<ComboboxSelected>>", self._on_pipe_changed)
        ttk.Button(tb, text="浏览...", command=self._browse_pipe).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Separator(tb, orient=tk.VERTICAL).pack(
            side=tk.LEFT, fill=tk.Y, padx=8, pady=4
        )
        self._add_btn = tk.Menubutton(
            tb,
            text="➕ 添加节点",
            bg="#3a3a3a",
            fg="#ccc",
            activebackground="#555",
            font=("Microsoft YaHei", 9),
        )
        self._add_menu = tk.Menu(
            self._add_btn,
            tearoff=0,
            bg="#333",
            fg="#ccc",
            activebackground="#555",
            activeforeground="#fff",
        )
        # Auto-derive menu from ModManager categories
        from mods.mod_manager import get_mod_manager

        mgr = get_mod_manager()
        for cat, items in mgr.get_category_menu().items():
            sub = tk.Menu(
                self._add_menu,
                tearoff=0,
                bg="#3a3a3a",
                fg="#ccc",
                activebackground="#555",
                activeforeground="#fff",
            )
            for nm, ky in items:
                sub.add_command(label=nm, command=lambda k=ky: self._add_node(k))
            self._add_menu.add_cascade(label=cat, menu=sub)
        self._add_btn.config(menu=self._add_menu)
        self._add_btn.pack(side=tk.LEFT, padx=2, pady=4)
        ttk.Button(tb, text="🗑 删除节点", command=self._delete_selected).pack(
            side=tk.LEFT, padx=2, pady=4
        )

        mf = tk.Frame(self, bg="#1a1a1a")
        mf.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.canvas_view = NodeCanvas(mf)
        self.canvas_view.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.canvas_view.on_connection_made = self._on_ui_connection
        self.canvas_view.on_add_node = self._on_canvas_add_node
        self.canvas_view.on_delete_node = self._on_canvas_delete_node
        self.canvas_view.on_node_selected = self._on_node_selected

        rp = tk.Frame(mf, bg="#252525", width=460)
        rp.pack(side=tk.RIGHT, fill=tk.Y)
        rp.pack_propagate(False)
        self.tab_var = tk.StringVar(value="params")
        tf = tk.Frame(rp, bg="#2d2d2d")
        tf.pack(fill=tk.X)
        for txt, val in [
            ("参数", "params"),
            ("结果", "results"),
            ("水质", "quality"),
            ("约束", "constraints"),
            ("高程", "elevation"),
        ]:
            tk.Radiobutton(
                tf,
                text=txt,
                variable=self.tab_var,
                value=val,
                bg="#2d2d2d",
                fg="#ccc",
                selectcolor="#444",
                indicatoron=False,
                command=self._on_tab_changed,
            ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.params_frame = tk.Frame(rp, bg="#252525")

        # ── 结果面板 (4列 Treeview: 符号|物理意义|单位|取值) ──
        self.result_frame = tk.Frame(rp, bg="#1a1a1a")
        # 容器 frame 实现双向滚动
        self._result_container = tk.Frame(self.result_frame, bg="#1a1a1a")
        self._result_container.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.result_tree = ttk.Treeview(
            self._result_container,
            columns=("symbol", "meaning", "unit", "value"),
            show="headings",
            height=18,
        )
        self.result_tree.heading("symbol", text="符号")
        self.result_tree.heading("meaning", text="物理意义 / 计算公式")
        self.result_tree.heading("unit", text="单位")
        self.result_tree.heading("value", text="取值")
        self.result_tree.column("symbol", width=75, anchor="center", stretch=False)
        self.result_tree.column("meaning", width=140, anchor="w")
        self.result_tree.column("unit", width=55, anchor="center", stretch=False)
        self.result_tree.column("value", width=110, anchor="e", stretch=False)
        # 暗色主题
        style = ttk.Style()
        style.configure(
            "Treeview",
            background="#1a1a1a",
            foreground="#ccc",
            fieldbackground="#1a1a1a",
            rowheight=22,
        )
        style.configure(
            "Treeview.Heading",
            background="#2d2d2d",
            foreground="#ffaa44",
            font=("Microsoft YaHei", 9, "bold"),
        )
        style.map("Treeview", background=[("selected", "#3a5a1a")])
        # 分组标题行样式 — 每个板块不同冷色调浅色
        SECTION_STYLES = {
            "原始参数": ("#0d3b66", "#66aaff"),  # 深蓝底 + 亮蓝字
            "构筑物尺寸": ("#1a3d2e", "#55cc88"),  # 深绿底 + 亮绿字
            "计算结果": ("#3d1a4a", "#cc88ff"),  # 深紫底 + 亮紫字
            "约束校核": ("#4a2a1a", "#ff9966"),  # 深橙底 + 亮橙字
            "进水水质": ("#0d3b66", "#66aaff"),  # 蓝
            "出水水质": ("#1a3d2e", "#55cc88"),  # 绿
            "去除率": ("#3d1a4a", "#cc88ff"),  # 紫
        }
        for name, (bg, fg) in SECTION_STYLES.items():
            self.result_tree.tag_configure(
                f"header_{name}",
                background=bg,
                foreground=fg,
                font=("Microsoft YaHei", 10, "bold"),
            )
        # 参数分类标题行 — 彩色区分 basic/physical/operating
        self.result_tree.tag_configure(
            "cat_basic",
            background="#0d3b66",
            foreground="#66aaff",
            font=("Microsoft YaHei", 10, "bold"),
        )
        self.result_tree.tag_configure(
            "cat_physical",
            background="#1a3d2e",
            foreground="#55cc88",
            font=("Microsoft YaHei", 10, "bold"),
        )
        self.result_tree.tag_configure(
            "cat_operating",
            background="#3d1a4a",
            foreground="#cc88ff",
            font=("Microsoft YaHei", 10, "bold"),
        )
        # 交替行背景
        self.result_tree.tag_configure("row_odd", background="#1e1e1e")
        self.result_tree.tag_configure("row_even", background="#252525")
        # 章节标题 — 整行居中横幅
        self.result_tree.tag_configure(
            "section_banner",
            background="#2d2d2d",
            foreground="#ffaa44",
            font=("Microsoft YaHei", 10, "bold"),
            anchor="center",
        )
        # 公式子行 — 浅色斜体
        self.result_tree.tag_configure(
            "formula_sub",
            foreground="#888888",
            font=("Microsoft YaHei", 8, "italic"),
        )
        # 约束校核行 — 通过/失败 颜色区分
        self.result_tree.tag_configure(
            "check_pass",
            foreground="#55cc88",
            font=("Microsoft YaHei", 9),
        )
        self.result_tree.tag_configure(
            "check_fail",
            foreground="#ff5555",
            font=("Microsoft YaHei", 9),
        )
        # 纵向滚动条
        self._result_scroll_y = ttk.Scrollbar(
            self._result_container, orient=tk.VERTICAL, command=self.result_tree.yview
        )
        # 横向滚动条
        self._result_scroll_x = ttk.Scrollbar(
            self.result_frame, orient=tk.HORIZONTAL, command=self.result_tree.xview
        )
        self.result_tree.configure(
            yscrollcommand=self._result_scroll_y.set,
            xscrollcommand=self._result_scroll_x.set,
        )
        self.result_tree.grid(row=0, column=0, sticky="nsew")
        self._result_scroll_y.grid(row=0, column=1, sticky="ns")
        self._result_container.grid_rowconfigure(0, weight=1)
        self._result_container.grid_columnconfigure(0, weight=1)
        self._result_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        # 约束校核区域 (Treeview 下方)
        self.result_check_text = tk.Text(
            self.result_frame,
            bg="#1a1a1a",
            fg="#ccc",
            font=("Consolas", 9),
            wrap=tk.WORD,
            relief=tk.FLAT,
            borderwidth=0,
            height=6,
        )
        self.result_check_text.pack(side=tk.BOTTOM, fill=tk.X)

        self.quality_text = tk.Frame(rp, bg="#1a1a1a")

        # ── 高程面板 ──
        self.elevation_frame = tk.Frame(rp, bg="#1a1a1a")
        self._build_elevation_view()

        # ── 模式切换按钮 ──
        mode_frame = tk.Frame(rp, bg="#333", height=28)
        mode_frame.pack(fill=tk.X, padx=6, pady=(4, 0))
        self._mode_btn = tk.Button(
            mode_frame,
            text="📊 方案浏览",
            bg="#3a5a1a",
            fg="#fff",
            font=("Microsoft YaHei", 9),
            relief=tk.FLAT,
            command=self._on_toggle_mode,
        )
        self._mode_btn.pack(fill=tk.X, padx=2, pady=2)

        # ── 方案浏览器(方案浏览模式时显示)──
        self._solution_browser = SolutionBrowser(
            rp,
            on_apply=self._on_solution_applied,
            bg="#252525",
        )

        self.params_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # ── 约束面板 ──
        self.constraint_frame = tk.Frame(rp, bg="#252525")
        from .constraint_panel import ConstraintPanel

        self._constraint_panel = ConstraintPanel(
            self.constraint_frame,
            on_constraint_changed=self._on_constraint_changed,
            bg="#252525",
        )
        self._constraint_panel.pack(fill=tk.BOTH, expand=True)

        self.status_var = tk.StringVar(
            value="左键选中节点查看参数 | 右键端口拖拽连线 | F5 计算其余全部"
        )
        tk.Label(
            self,
            textvariable=self.status_var,
            bg="#2d2d2d",
            fg="#888",
            anchor="w",
            font=("Microsoft YaHei", 9),
        ).pack(side=tk.BOTTOM, fill=tk.X, ipady=2)
        self.bind("<F5>", lambda e: self._on_calc_all())
        log.info("MainWindow initialized")
        # 延迟检查模组加载状态(不阻塞启动)
        self.after(300, self._check_mod_status)

    # ═══════════════════ 示例 ═══════════════════
    def _load_demo(self):
        # 尝试自动恢复最近项目(静默,失败则加载示例)

        recent = ProjectManager.get_recent_files()
        valid_recent = [r for r in recent if Path(r).exists()]
        if valid_recent:
            try:
                executor = self._pm.load(Path(valid_recent[0]))
                self.executor = executor
                self._rebuild_canvas()
                self._dirty = False
                self.title(f"排水工程设计工具 v3 — {Path(valid_recent[0]).name}")
                self.status_var.set(
                    f"已恢复: {Path(valid_recent[0]).name}  |  文件→最近文件 可切换"
                )
                return
            except Exception as e:
                log.warning(f"Failed to load recent: {e}")

        # 回退:加载示例
        self._load_default_demo()

    def _load_default_demo(self):
        """加载默认示例流程"""
        TiaojiechiNode = get_mod_manager().get_node_class("tiaojiechi")

        pipe = PipeNetworkNode()
        pipe.x, pipe.y = 100, 200
        pipe.set_excel("pipe_final")
        self._pipe_node = pipe
        wq = WaterQualityNode()
        wq.x, wq.y = 100, 370
        comb = CombinerNode()
        comb.x, comb.y = 350, 285
        tjc = TiaojiechiNode()
        tjc.x, tjc.y = 600, 285
        for n in [pipe, wq, comb, tjc]:
            self.executor.add_node(n)
        self.executor.connect(pipe.output_ports[0], comb.input_ports[0])
        self.executor.connect(wq.output_ports[0], comb.input_ports[1])
        self.executor.connect(comb.output_ports[0], tjc.input_ports[0])
        for n, nm, tp, x, y in [
            (pipe, "管网输入", "pipe_network", pipe.x, pipe.y),
            (wq, "进水水质", "water_quality", wq.x, wq.y),
            (comb, "合并", "combiner", comb.x, comb.y),
            (tjc, "调节池", "tiaojiechi", tjc.x, tjc.y),
        ]:
            ui = self.canvas_view.add_node(nm, tp, n, x, y)
            self.node_items[ui.node_id] = ui
        self.canvas_view.connect_ports(
            list(self.node_items.values())[0].output_ports[0],
            list(self.node_items.values())[2].input_ports[0],
        )
        self.canvas_view.connect_ports(
            list(self.node_items.values())[1].output_ports[0],
            list(self.node_items.values())[2].input_ports[1],
        )
        self.canvas_view.connect_ports(
            list(self.node_items.values())[2].get_output_port(),
            list(self.node_items.values())[3].get_input_port(),
        )
        self._dirty = False
        self.status_var.set("示例已加载 | 左键选中节点查看参数 | F5 计算其余全部")

    # ═══════════════ 状态检查 ═══════════════
    def _check_mod_status(self):
        """延迟检查模组加载状态,如有错误弹窗提示"""
        try:
            from mods.mod_manager import get_mod_manager

            mgr = get_mod_manager()
            errors = mgr.get_load_errors()
            if errors:
                msg = f"{len(errors)} 个模组加载失败:\n\n"
                for e in errors[:5]:  # 最多显示 5 个
                    msg += f"  [{e.get('mod_id', '?')}] {e.get('severity', 'error').upper()}\n"
                    for err in e.get("errors", [])[:2]:
                        msg += f"    - {err}\n"
                if len(errors) > 5:
                    msg += f"\n  ... 共 {len(errors)} 个错误,详见日志"
                log.warning("Mod load errors: %s", msg)
                messagebox.showwarning("模组加载警告", msg, parent=self)
            else:
                log.debug("All mods loaded successfully")
        except Exception as e:
            _log.warning("operation failed: %s", e, exc_info=True)
            pass  # 静默 — ModManager 不可用是预期场景

    # ═══════════════════ 参数面板 ═══════════════════

    def _on_node_selected(self, node_id: str):
        self._selected_id = node_id
        self._refresh_params()
        if self.tab_var.get() == "results":
            self._refresh_selected_result()
        elif self.tab_var.get() == "constraints":
            if self._selected_id and self._selected_id in self.node_items:
                be = self.node_items[self._selected_id].backend
                if be:
                    applied = (
                        be.result.params if be.result and be.result.success else None
                    )
                    self._constraint_panel.load_node(be, applied)
        elif self.tab_var.get() == "elevation":
            self._refresh_elevation_view()
        elif self.tab_var.get() == "quality":
            if self._selected_id and self._selected_id in self.node_items:
                be = self.node_items[self._selected_id].backend
                if be and hasattr(be, "NODE_TYPE"):
                    from models.node_registry import is_water_quality_node
                    if is_water_quality_node(be.NODE_TYPE):
                        self._quality_panel.show_water_quality_card(be)
                    else:
                        # 委托给 QualityPanel 的滚动功能
                        self._quality_panel.scroll_to_section(node_id)

    # ═══════════════ 面板刷新 ═══════════════
    def _refresh_params(self):
        """根据当前模式显示方案浏览器或手动滑块

        仅在参数Tab激活时打包UI内容,避免与约束/结果/水质Tab冲突
        """
        # 隐藏两个面板
        self.params_frame.pack_forget()
        if self._solution_browser:
            self._solution_browser.pack_forget()

        # 非参数Tab时不渲染内容(切换节点时避免误显示)
        if self.tab_var.get() != "params":
            return

        if not self._selected_id or self._selected_id not in self.node_items:
            self.params_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
            tk.Label(
                self.params_frame,
                text="← 点击节点查看参数",
                bg="#252525",
                fg="#888",
                font=("Microsoft YaHei", 10),
            ).pack(pady=40)
            return

        ui = self.node_items[self._selected_id]
        be = ui.backend
        if not be:
            self.params_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
            tk.Label(self.params_frame, text="无参数", bg="#252525", fg="#888").pack(
                pady=40
            )
            return

        if self._browse_mode:
            # ── 方案浏览模式 ──
            self._show_browse_mode(be)
        else:
            # ── 手动微调模式 ──
            self._show_manual_mode(be)

    # ═══════════════ 面板显示 ═══════════════
    def _show_browse_mode(self, be, force_recompute=False):
        """显示方案浏览器"""
        if not self._solution_browser:
            return
        # 输入/合并节点和非水处理阶段节点没有方案空间,走手动卡片模式
        is_io = _is_io_node(be.NODE_TYPE)
        skip_sb = not has_solution_space(be.NODE_TYPE)
        if is_io or skip_sb:
            self._show_manual_mode(be)
            return
        # ── 污泥节点: 使用上游污泥流 ──
        if be.is_sludge_only:
            sludge = self.executor.trace_sludge_upstream(be.node_id)
            if sludge is None:
                from models.base import SludgeFlow

                sludge = SludgeFlow(Q_wet=100, DS=4000, P_moisture=0.96, VS_ratio=0.60)
            self._solution_browser.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
            self._solution_browser.load_sludge_node(be, sludge)
            return

        # 获取当前上下文的水量水质 — 从上游追踪,而非读节点自身参数
        flow, quality = self._trace_upstream_context(be.node_id)
        # 水质优先使用缓存结果中的进水水质
        if be.result and be.result.inlet_quality:
            quality = be.result.inlet_quality
        # 水量优先使用缓存结果中的流量(若上游追踪返回零流量则回退到节点参数)
        if flow.Q_design <= 0 and be.result:
            # 从已缓存结果中提取设计流量
            for name, (val, unit) in be.result.dimensions.items():
                if "设计流量" in name and "m³/s" in unit and val > 0:
                    flow.Q_design = val
                    break
        if flow.Q_design <= 0:
            # 无缓存也无上游 → 尝试从管网节点获取流量
            if self._pipe_node and self._pipe_node._total_flow > 0:
                flow.Q_design = self._pipe_node._total_flow
                flow.Q_avg_daily = self._pipe_node._total_avg_daily
        if flow.Q_design <= 0:
            # 最后回退: 使用 WaterFlow 默认值 (城镇污水标准)
            flow = WaterFlow(Q_design=0.57, Q_avg_daily=34760.7, Kz=1.4)
        self._solution_browser.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self._solution_browser.load_node(
            be, flow, quality, force_recompute=force_recompute
        )

        # ── 诊断日志: 方案为空时输出上下文 ──
        if not self._solution_browser._solutions:
            log.warning("[方案浏览器] %s 无可行方案", be.NODE_NAME)
            log.warning(
                "  上游流量: Q_design=%.4f m³/s  Q_avg=%.1f m³/d  Kz=%.1f",
                flow.Q_design,
                flow.Q_avg_daily,
                flow.Kz,
            )
            log.warning(
                "  水质: BOD5=%.0f  COD=%.0f  SS=%.0f  NH3N=%.0f",
                quality.BOD5,
                quality.COD,
                quality.SS,
                quality.NH3N,
            )
            log.warning(
                "  参数: %s", dict(be._params) if hasattr(be, "_params") else "N/A"
            )
            log.warning(
                "  节点状态: %s", be.state.name if hasattr(be, "state") else "N/A"
            )
            if be.result:
                log.warning("  缓存结果: success=%s", be.result.success)

    def _show_manual_mode(self, be):
        """显示旧版滑块面板(取值约束为离散值)"""
        # ── 水质节点特殊处理 ──
        show_wq = is_water_quality_node(be.NODE_TYPE)
        if show_wq:
            # 水质编辑卡片委托给 QualityPanel
            self.params_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
            self._quality_panel.show_water_quality_card(be, parent_frame=self.params_frame)
            return

        self.params_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        # 清理 params_frame 内的旧控件
        for w in self.params_frame.winfo_children():
            w.destroy()
        self._slider_vars.clear()

        # 标题
        tk.Label(
            self.params_frame,
            text=f"▎{be.NODE_NAME}",
            bg="#252525",
            fg="#fff",
            font=("Microsoft YaHei", 12, "bold"),
        ).pack(anchor="w", padx=10, pady=(10, 2))
        tk.Label(
            self.params_frame,
            text=f"类型: {be.NODE_CATEGORY} | 状态: {be.state.name}",
            bg="#252525",
            fg="#888",
            font=("Microsoft YaHei", 8),
        ).pack(anchor="w", padx=10)

        # 公式
        formula = _get_formulas().get(be.NODE_TYPE, "")
        if formula:
            ff = tk.Frame(self.params_frame, bg="#1a1a1a", bd=1, relief=tk.SUNKEN)
            ff.pack(fill=tk.X, padx=8, pady=6)
            tk.Label(
                ff,
                text="📐 计算公式",
                bg="#1a1a1a",
                fg="#ffaa44",
                font=("Microsoft YaHei", 10, "bold"),
            ).pack(anchor="w", padx=8, pady=(6, 2))
            tk.Label(
                ff,
                text=formula,
                bg="#1a1a1a",
                fg="#ddd",
                font=("Consolas", 9),
                justify=tk.LEFT,
            ).pack(anchor="w", padx=8, pady=(0, 6))

        # 滑块
        param_defs = be.get_param_defs()
        if not param_defs:
            tk.Label(
                self.params_frame, text="无可调参数", bg="#252525", fg="#666"
            ).pack(pady=20)
            return

        canvas = tk.Canvas(self.params_frame, bg="#252525", highlightthickness=0)
        scrollbar = tk.Scrollbar(
            self.params_frame, orient=tk.VERTICAL, command=canvas.yview, width=8
        )
        scroll_frame = tk.Frame(canvas, bg="#252525")
        scroll_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.bind(
            "<MouseWheel>", lambda e: canvas.yview_scroll(int(-e.delta / 120), "units")
        )
        canvas.bind("<Enter>", lambda e: canvas.focus_set())
        # 绑定到 scroll_frame 而非抢焦点:Entry 有焦点时滚轮仍可用
        scroll_frame.bind(
            "<MouseWheel>", lambda e: canvas.yview_scroll(int(-e.delta / 120), "units")
        )

        # 获取该参数的允许离散值
        allowed = {}
        try:
            allowed = {
                pd.key: get_allowed_values(be.NODE_TYPE, pd.key) for pd in param_defs
            }
        except KeyError:
            pass

        for pd in param_defs:
            row = tk.Frame(scroll_frame, bg="#2d2d2d", bd=1, relief=tk.GROOVE)
            row.pack(fill=tk.X, padx=4, pady=1)
            hdr = tk.Frame(row, bg="#2d2d2d")
            hdr.pack(fill=tk.X, padx=6, pady=(3, 0))
            tk.Label(
                hdr,
                text=pd.name,
                bg="#2d2d2d",
                fg="#ccc",
                font=("Microsoft YaHei", 9, "bold"),
            ).pack(side=tk.LEFT)
            var = tk.DoubleVar(value=pd.value)
            self._slider_vars[pd.key] = var

            # 如果有离散值约束,使用 Combobox 而非 Entry+Scale
            vals = allowed.get(pd.key, [])
            if vals and len(vals) > 0:
                cb = ttk.Combobox(
                    hdr,
                    values=[str(v) for v in vals],
                    textvariable=var,
                    state="readonly",
                    width=10,
                )
                cb.pack(side=tk.RIGHT, padx=2)
                cb.bind(
                    "<<ComboboxSelected>>",
                    lambda e, k=pd.key: self._on_param_changed(k, float(var.get())),
                )
            else:
                # StringVar for Entry — Excel-like editing (no cursor reset, partial input ok)
                str_var = tk.StringVar(value=str(pd.value))
                entry = tk.Entry(
                    hdr,
                    textvariable=str_var,
                    width=7,
                    bg="#1a1a1a",
                    fg="#ffaa44",
                    insertbackground="#fff",
                    font=("Consolas", 9),
                    justify=tk.RIGHT,
                )
                entry.pack(side=tk.RIGHT, padx=2)

                def _sync_entry_to_scale(k=pd.key, sv=str_var, dv=var):
                    """Entry → Scale: parse text, update DoubleVar + params"""
                    try:
                        val = float(sv.get())
                        dv.set(val)
                        self._on_param_changed(k, val)
                    except (ValueError, tk.TclError):
                        pass  # ignore invalid partial input

                def _sync_scale_to_entry(k=pd.key, sv=str_var, dv=var):
                    """Scale → Entry: update display + params"""
                    val = dv.get()
                    sv.set(str(round(val, 6)).rstrip("0").rstrip("."))
                    self._on_param_changed(k, val)

                entry.bind("<Return>", lambda e, f=_sync_entry_to_scale: f())

                # FocusOut + 延迟检查: 仅当焦点仍在app内时才提交 (Alt-Tab不触发)
                def _on_focus_out(e, f=_sync_entry_to_scale):
                    self.after(
                        10, lambda: f() if self.focus_get() is not None else None
                    )

                entry.bind("<FocusOut>", _on_focus_out)
                scale = tk.Scale(
                    row,
                    from_=pd.min_val,
                    to=pd.max_val,
                    resolution=pd.step,
                    orient=tk.HORIZONTAL,
                    bg="#2d2d2d",
                    fg="#ffaa44",
                    troughcolor="#444",
                    highlightthickness=0,
                    length=280,
                    variable=var,
                )
                scale.bind("<ButtonRelease-1>", lambda e, f=_sync_scale_to_entry: f())
                scale.set(pd.value)
                scale.pack(fill=tk.X, padx=6, pady=(0, 2))

            if pd.unit:
                tk.Label(
                    hdr,
                    text=pd.unit,
                    bg="#2d2d2d",
                    fg="#888",
                    font=("Microsoft YaHei", 8),
                ).pack(side=tk.RIGHT)

        # ── 污染物去除率 ──
        rates = be.get_removal_rates()
        if rates:
            sep = tk.Frame(scroll_frame, bg="#444", height=1)
            sep.pack(fill=tk.X, padx=8, pady=(8, 4))
            tk.Label(
                scroll_frame,
                text="🧪 污染物去除率",
                bg="#252525",
                fg="#ffaa44",
                font=("Microsoft YaHei", 10, "bold"),
            ).pack(anchor="w", padx=10, pady=(4, 2))

            rate_labels = {
                "BOD5": "BOD₅",
                "COD": "COD",
                "SS": "SS",
                "NH3N": "NH₃-N",
                "TN": "TN",
                "TP": "TP",
            }
            for pk, label in rate_labels.items():
                if pk not in rates:
                    continue
                rrow = tk.Frame(scroll_frame, bg="#2d2d2d", bd=1, relief=tk.GROOVE)
                rrow.pack(fill=tk.X, padx=6, pady=1)
                tk.Label(
                    rrow,
                    text=label,
                    bg="#2d2d2d",
                    fg="#ccc",
                    font=("Microsoft YaHei", 9),
                    width=6,
                    anchor="e",
                ).pack(side=tk.LEFT, padx=4)
                rvar = tk.DoubleVar(value=rates[pk] * 100)  # 转为百分比显示
                rscale = tk.Scale(
                    rrow,
                    from_=0,
                    to=100,
                    resolution=1,
                    orient=tk.HORIZONTAL,
                    variable=rvar,
                    bg="#2d2d2d",
                    fg="#55cc55",
                    troughcolor="#444",
                    highlightthickness=0,
                    length=200,
                    command=lambda v, pk=pk, be=be: self._on_rate_changed(
                        pk, float(v) / 100, be
                    ),
                )
                rscale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
                tk.Label(
                    rrow,
                    text="%",
                    bg="#2d2d2d",
                    fg="#888",
                    font=("Consolas", 9),
                    width=3,
                ).pack(side=tk.RIGHT)

        # 按钮
        btn_frame = tk.Frame(scroll_frame, bg="#252525")
        btn_frame.pack(fill=tk.X, padx=10, pady=8)
        ttk.Button(btn_frame, text="查看此节点结果", command=self._view_results).pack(
            side=tk.LEFT, padx=4
        )
        ttk.Button(
            btn_frame, text="重置默认值", command=lambda: self._reset_params(be)
        ).pack(side=tk.LEFT, padx=4)

    # ═══════════════ 事件回调 ═══════════════
    def _on_toggle_mode(self):
        """切换方案浏览 / 手动微调"""
        self._browse_mode = not self._browse_mode
        self._mode_btn.config(
            text="📊 方案浏览" if self._browse_mode else "🎚 手动微调",
            bg="#3a5a1a" if self._browse_mode else "#5a3a1a",
        )

        self._refresh_params()

    def _on_solution_applied(self, solutions, selected_idx=None):
        """方案应用回调 — 标记节点为 CLEAN, 触发下游重算"""
        self._on_calc_rest()

    def _on_constraint_changed(self, node_type: str):
        """约束限值变更回调 — 刷新方案空间"""
        self.status_var.set(f"约束限值已更新 — {node_type} 方案空间需刷新")
        self._dirty = True

    def _on_rate_changed(self, pollutant: str, rate: float, be):
        """去除率滑块变更"""

        be.set_removal_rate(pollutant, rate)
        self._dirty = True

    # ═══════════════ 面板显示 ═══════════════
    def _show_water_quality_card(self, be, parent_frame=None):
        """水质编辑卡片 — 彩色卡片式水污染物参数编辑 (v5.1 从旧版 EXE 恢复).

        支持 WaterQualityNode (城市污水) 和 KwInputNode (矿井水).
        每项污染物独立卡片: 左侧彩色指示条 + 参数信息, 右侧大号数值 + 滑块编辑.

        Args:
            be: backend node (WaterQualityNode or KwInputNode)
            parent_frame: 父容器 Frame. 为 None 时使用 self.quality_text (质量Tab);
                          传入 self.params_frame 时用于参数Tab手动模式.
        """
        if parent_frame is None:
            parent_frame = self.quality_text

        for w in parent_frame.winfo_children():
            w.destroy()

        # ── 判断水类型 ──
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
        # 鼠标进入Canvas时获取焦点,确保滚轮始终有效
        canvas.bind("<Enter>", lambda e: canvas.focus_set())
        cards_frame.bind(
            "<MouseWheel>", lambda e: canvas.yview_scroll(int(-e.delta / 120), "units")
        )

        # ── 标题 ──
        tk.Label(
            cards_frame,
            text=f"▎{water_label}",
            bg="#1a1a1a",
            fg="#fff",
            font=("Microsoft YaHei", 12, "bold"),
        ).pack(anchor="w", padx=10, pady=(10, 2))
        tk.Label(
            cards_frame,
            text=std_ref,
            bg="#1a1a1a",
            fg="#888",
            font=("Microsoft YaHei", 8),
        ).pack(anchor="w", padx=10, pady=(0, 8))

        # ── 获取排放标准 ──
        effluent_std = self._get_effluent_std(be)

        # ── 污染物颜色 & 标签 & 范围 ──
        WQ_COLORS = {
            "BOD5": "#5599ff",
            "COD": "#ff9955",
            "SS": "#55cc55",
            "NH3N": "#cc55ff",
            "TN": "#ff55aa",
            "TP": "#55aaff",
        }
        WQ_LABELS = {
            "BOD5": "BOD₅",
            "COD": "COD",
            "SS": "SS",
            "NH3N": "NH₃-N",
            "TN": "TN",
            "TP": "TP",
        }
        WQ_RANGES = {
            "BOD5": (50, 500),
            "COD": (100, 1000),
            "SS": (50, 600),
            "NH3N": (5, 80),
            "TN": (10, 100),
            "TP": (1, 20),
        }

        # ── 污染物紧凑表格 (每行一参数,仿 manual_mode 滑块布局) ──
        for attr in ["BOD5", "COD", "SS", "NH3N", "TN", "TP"]:
            color = WQ_COLORS[attr]
            label = WQ_LABELS[attr]
            std_val = effluent_std.get(attr)
            min_v, max_v = WQ_RANGES.get(attr, (0, 1000))

            if hasattr(be, "water_quality"):
                current_val = getattr(be.water_quality, attr)
            else:
                current_val = be.get_param(attr)

            # 单行紧凑布局: 色条 | 名称 | 数值 | 滑块 | 单位
            row = tk.Frame(cards_frame, bg="#2d2d2d", bd=1, relief=tk.GROOVE)
            row.pack(fill=tk.X, padx=6, pady=1)

            # 左侧彩色指示条
            bar = tk.Frame(row, bg=color, width=4)
            bar.pack(side=tk.LEFT, fill=tk.Y)

            # 参数名称
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

            # 数值输入 (StringVar + Entry, 仿 manual_mode)
            str_var = tk.StringVar(value=str(current_val))
            entry = tk.Entry(
                row, textvariable=str_var, width=6,
                bg="#1a1a1a", fg="#ffaa44", insertbackground="#fff",
                font=("Consolas", 10), justify=tk.RIGHT,
            )
            entry.pack(side=tk.LEFT, padx=4)

            # 滑块
            var = tk.DoubleVar(value=current_val)
            self._slider_vars[attr] = var

            def _sync_entry_to_slider(k=attr, sv=str_var, dv=var):
                try:
                    val = float(sv.get())
                    dv.set(val)
                except (ValueError, tk.TclError):
                    pass

            def _sync_slider_to_entry(k=attr, sv=str_var, dv=var):
                val = dv.get()
                sv.set(str(round(val, 6)).rstrip("0").rstrip("."))

            def _on_wq_commit(val_str, a=attr, be_node=be):
                val = float(val_str)
                if hasattr(be_node, "water_quality"):
                    setattr(be_node.water_quality, a, val)
                    be_node._sync_quality_to_params()
                else:
                    be_node.set_param(a, val)
                self._dirty = True
                self.status_var.set(
                    f"{be_node.NODE_NAME} {WQ_LABELS[a]}: {val:.1f} mg/L"
                )

            entry.bind("<Return>", lambda e, f=_sync_entry_to_slider, g=_on_wq_commit,
                       sv=str_var: (f(), g(sv.get())))

            def _on_focus_out(e, f=_sync_entry_to_slider, g=_on_wq_commit, sv=str_var):
                self.after(10, lambda: (
                    f() if self.focus_get() is not None else None,
                    g(sv.get()) if self.focus_get() is not None else None,
                ))

            entry.bind("<FocusOut>", _on_focus_out)

            scale = tk.Scale(
                row, from_=min_v, to=max_v, resolution=0.5,
                orient=tk.HORIZONTAL, variable=var,
                bg="#2d2d2d", fg=color, troughcolor="#3a3a3a",
                highlightthickness=0, length=160,
            )
            scale.bind("<ButtonRelease-1>", lambda e, f=_sync_slider_to_entry,
                       g=_on_wq_commit, sv=str_var, dv=var: (f(), g(str(dv.get()))))
            scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)

            # 单位
            tk.Label(
                row, text="mg/L", bg="#2d2d2d", fg="#888",
                font=("Microsoft YaHei", 8),
            ).pack(side=tk.RIGHT, padx=4)

        # ── 底部: 排放标准参考 ──
        sep = tk.Frame(cards_frame, bg="#444", height=1)
        sep.pack(fill=tk.X, padx=8, pady=(12, 6))

        tk.Label(
            cards_frame,
            text=f"▎排放标准参照 — {std_name}",
            bg="#1a1a1a",
            fg="#ffaa44",
            font=("Microsoft YaHei", 10, "bold"),
        ).pack(anchor="w", padx=10)

        std_items = [
            ("BOD5", "BOD₅"),
            ("COD", "COD"),
            ("SS", "SS"),
            ("NH3N", "NH₃-N"),
            ("TN", "TN"),
            ("TP", "TP"),
        ]
        for s_attr, s_lbl in std_items:
            val = effluent_std.get(s_attr)
            if val is not None:
                row = tk.Frame(cards_frame, bg="#1a1a1a")
                row.pack(fill=tk.X, padx=16, pady=1)
                tk.Label(
                    row,
                    text=f"{s_lbl} ≤ {val} mg/L",
                    bg="#1a1a1a",
                    fg="#aaa",
                    font=("Microsoft YaHei", 9),
                ).pack(anchor="w")

        # ── 底部按钮 ──
        btn_frame = tk.Frame(cards_frame, bg="#1a1a1a")
        btn_frame.pack(fill=tk.X, padx=10, pady=(10, 8))
        ttk.Button(btn_frame, text="查看此节点结果", command=self._view_results).pack(
            side=tk.LEFT, padx=4
        )
        ttk.Button(
            btn_frame, text="重置默认值", command=lambda: self._reset_params(be)
        ).pack(side=tk.LEFT, padx=4)

    # ═══════════════ 水质全流程追踪 ═══════════════

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

    def _build_full_quality_flow(self, scroll_to_node_id: Optional[str] = None):
        """全流程水质追踪 — 按水流顺序排列所有工艺节点的水质变化表.

        每个处理节点一节: 节标题(节点名) + 6项污染物进出水卡片.
        点击画布上某节点时,自动滚动到对应节.
        """
        for w in self.quality_text.winfo_children():
            w.destroy()

        canvas = tk.Canvas(self.quality_text, bg="#1a1a1a", highlightthickness=0)
        scrollbar = tk.Scrollbar(
            self.quality_text, orient=tk.VERTICAL, command=canvas.yview, width=8
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

        # ── 总标题 ──
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

        # ── 获取水流拓扑顺序 ──
        try:
            order = self.executor.topological_order()
        except RuntimeError:
            order = list(self.executor._nodes.keys())

        # ── 存储节 frame 映射,用于滚动定位 ──
        self._quality_sections: Dict[str, tk.Frame] = {}
        has_any_data = False

        for nid in order:
            node = self.executor._nodes.get(nid)
            if not node or not node.result or not node.result.success:
                continue
            result = node.result
            inlet = result.inlet_quality
            outlet = result.outlet_quality
            if not inlet or not outlet:
                continue
            # 跳过纯水质输入节点 — 它们的水质由编辑面板管理
            if is_water_quality_node(node.NODE_TYPE):
                continue

            has_any_data = True

            # ── 节容器 ──
            section = tk.Frame(flow_frame, bg="#1a1a1a", bd=0,
                               highlightbackground="#333", highlightthickness=1)
            section.pack(fill=tk.X, padx=6, pady=(6, 2))
            self._quality_sections[nid] = section

            # 节标题 (节点名)
            hdr = tk.Frame(section, bg="#2d2d2d")
            hdr.pack(fill=tk.X)
            tk.Label(
                hdr, text=f" ▎{node.NODE_NAME} ",
                bg="#2d2d2d", fg="#ffaa44",
                font=("Microsoft YaHei", 10, "bold"),
            ).pack(side=tk.LEFT)
            tk.Label(
                hdr, text=f"  {node.NODE_CATEGORY}  ",
                bg="#2d2d2d", fg="#888",
                font=("Microsoft YaHei", 8),
            ).pack(side=tk.LEFT)

            # 污染物表格 (列标题 + 数据行)
            effluent_std = self._get_effluent_std(node)
            cards_wrap = tk.Frame(section, bg="#1a1a1a")
            cards_wrap.pack(fill=tk.X, padx=4, pady=2)

            # 列标题行
            col_hdr = tk.Frame(cards_wrap, bg="#2d2d2d")
            col_hdr.pack(fill=tk.X, padx=2)
            tk.Label(col_hdr, text=" 指标", bg="#2d2d2d", fg="#ffaa44",
                     font=("Microsoft YaHei", 8, "bold"), width=8, anchor="w").pack(side=tk.LEFT)
            tk.Label(col_hdr, text="进水水质", bg="#2d2d2d", fg="#aaa",
                     font=("Microsoft YaHei", 8), width=12, anchor="e").pack(side=tk.LEFT)
            tk.Label(col_hdr, text="出水水质", bg="#2d2d2d", fg="#aaa",
                     font=("Microsoft YaHei", 8), width=12, anchor="e").pack(side=tk.LEFT)
            tk.Label(col_hdr, text="去除率", bg="#2d2d2d", fg="#aaa",
                     font=("Microsoft YaHei", 8), width=10, anchor="e").pack(side=tk.LEFT)
            tk.Label(col_hdr, text="标准", bg="#2d2d2d", fg="#aaa",
                     font=("Microsoft YaHei", 8), width=10, anchor="e").pack(side=tk.LEFT)

            for attr in self.WQ_INDICATORS:
                color = self.WQ_COLORS[attr]
                label = self.WQ_LABELS[attr]
                in_val = getattr(inlet, attr)
                out_val = getattr(outlet, attr)
                removal = (in_val - out_val) / in_val * 100 if in_val > 0 else 0
                std_val = effluent_std.get(attr)
                ok = out_val <= std_val if std_val else True

                row = tk.Frame(cards_wrap, bg="#1a1a1a", bd=0,
                               highlightbackground="#333", highlightthickness=1)
                row.pack(fill=tk.X, padx=2, pady=1)

                # 左侧色条 + 指标名
                tk.Frame(row, bg=color, width=3).pack(side=tk.LEFT, fill=tk.Y)
                tk.Label(row, text=f" {label}", bg="#252525", fg=color,
                         font=("Microsoft YaHei", 9, "bold"),
                         width=9, anchor="w").pack(side=tk.LEFT)

                # 进水水质
                tk.Label(row, text=f"{in_val:.1f} mg/L", bg="#252525", fg="#ccc",
                         font=("Consolas", 9), width=12, anchor="e").pack(side=tk.LEFT)

                # 出水水质
                tk.Label(row, text=f"{out_val:.1f} mg/L", bg="#252525", fg="#ccc",
                         font=("Consolas", 9), width=12, anchor="e").pack(side=tk.LEFT)

                # 去除率
                tk.Label(row, text=f"{removal:.1f}%", bg="#252525", fg="#55cc88",
                         font=("Consolas", 9), width=10, anchor="e").pack(side=tk.LEFT)

                # 标准
                if std_val is not None:
                    status = "✓" if ok else "✗"
                    status_color = "#55cc88" if ok else "#ff6666"
                    tk.Label(row, text=f"≤{std_val} {status}", bg="#252525",
                             fg=status_color, font=("Consolas", 9, "bold"),
                             width=10, anchor="e").pack(side=tk.LEFT)
                else:
                    tk.Label(row, text="—", bg="#252525", fg="#888",
                             font=("Consolas", 9), width=10, anchor="e").pack(side=tk.LEFT)

        if not has_any_data:
            tk.Label(
                flow_frame, text="(请先按 F5 计算，仅显示处理单元的水质变化)",
                bg="#1a1a1a", fg="#888",
                font=("Microsoft YaHei", 10),
            ).pack(pady=40)

        # ── 滚动到指定节点 ──
        if scroll_to_node_id and scroll_to_node_id in self._quality_sections:
            self._quality_canvas = canvas
            self.after(100, lambda: self._scroll_to_section(scroll_to_node_id))

    def _scroll_to_section(self, node_id: str):
        """滚动水质面板到指定节点的节."""
        section = self._quality_sections.get(node_id)
        canvas = getattr(self, "_quality_canvas", None)
        if not section or not canvas:
            return
        # 计算 section 在 canvas 中的相对位置
        y_offset = section.winfo_y()  # section 在 flow_frame 中的 y 坐标
        # 获取 canvas 中 window 的位置
        canvas.update_idletasks()
        bbox = canvas.bbox("all")
        if bbox and bbox[3] > 0:
            fraction = max(0.0, min(1.0, y_offset / bbox[3]))
            canvas.yview_moveto(fraction)

    def _build_quality_table(self, be, inlet, outlet):
        """单节点水质追踪 — 兼容旧接口,委托给全流程视图."""
        self._build_full_quality_flow(scroll_to_node_id=be.node_id)

    def _view_results(self):
        """切换到结果tab查看当前节点计算结果"""
        self.status_var.set("参数已修改,按 F5 重新计算")
        self.tab_var.set("results")

    # ═══════════════ 设置 ═══════════════
    def _reset_params(self, be):
        be.reset_params()
        self._refresh_params()

    def _on_param_changed(self, key, var):
        """参数滑块变更回调."""
        self._dirty = True
        if self._selected_id and self._selected_id in self.node_items:
            be = self.node_items[self._selected_id].backend
            if be:
                self.status_var.set(f"{be.NODE_NAME} 参数已变更: {key} = {var}")

    # ═══════════════════ 其他操作 ═══════════════════
    def _get_data_pipe_files(self) -> List[str]:
        """扫描 data/ 目录, 返回所有非计算结果管网的 Excel 文件名"""
        data_dir = get_data_dir()
        files = []
        if os.path.isdir(data_dir):
            for f in sorted(os.listdir(data_dir)):
                if (
                    f.endswith(".xlsx")
                    and "_计算结果" not in f
                    and not f.startswith("~$")
                ):
                    files.append(f)
        # 确保内置文件在列表中
        for key in ["pipe_final.xlsx", "pipe_final2.xlsx", "yushui.xlsx"]:
            if key not in files:
                files.append(key)
        return files

    # ═══════════════ 面板刷新 ═══════════════
    def _refresh_pipe_files(self):
        """刷新管网下拉列表"""
        files = self._get_data_pipe_files()
        self._pipe_cb["values"] = files

    # ═══════════════ 事件回调 ═══════════════
    def _on_pipe_changed(self, e=None):
        if self._pipe_node:
            name = self.pipe_var.get()
            ok = self._pipe_node.set_excel(name)
            self.status_var.set(f"管网: {name} {'OK' if ok else 'FAIL'}")

    def _browse_pipe(self):

        path = filedialog.askopenfilename(
            title="选择管网 Excel", filetypes=[("Excel", "*.xlsx *.xls")]
        )
        if path and self._pipe_node:
            ok = self._pipe_node.set_excel(path)
            self.status_var.set(
                f"管网: {os.path.basename(path)} {'OK' if ok else 'FAIL'}"
            )

    # ═══════════════ 节点管理 ═══════════════
    def _add_node(self, key: str, x=None, y=None):
        registry = _get_node_registry()
        cls, name = registry[key]
        node = cls()
        if x is None or y is None:
            # 智能定位: 扫描现有节点, 新节点放在最右侧+间距, 避免重叠
            if self.node_items:
                existing_xs = [ni.x for ni in self.node_items.values()]
                existing_ys = [ni.y for ni in self.node_items.values()]
                max_x = max(existing_xs) if existing_xs else 500
                # y 取现有节点 y 的中位数附近, 加小偏移避免完全覆盖
                mid_y = (
                    sorted(existing_ys)[len(existing_ys) // 2] if existing_ys else 300
                )
                offset_y = (len(self.node_items) % 5 - 2) * 60  # -120, -60, 0, 60, 120
                node.x = x if x is not None else max_x + 200
                node.y = y if y is not None else mid_y + offset_y
            else:
                node.x = x if x is not None else 500
                node.y = y if y is not None else 300
        else:
            node.x = x
            node.y = y
        self.executor.add_node(node)
        ui = self.canvas_view.add_node(name, key, node, node.x, node.y)
        self.node_items[ui.node_id] = ui
        self._dirty = True
        # 管网节点特殊处理: 尝试加载默认 Excel
        if key == "pipe_network":
            self._pipe_node = node
            if not node._excel_path:
                node.set_excel("pipe_final")
        if key == "water_quality":
            pass  # 默认值已在构造函数设置
        # 矿井水输入: 自动计算以便下游节点追踪流量水质

        if key == "kw_input":
            flow = WaterFlow()
            quality = WaterQuality()
            result, out_flow, out_quality = node.execute(flow, quality)
        # 处理节点: 自动应用推荐方案, 确保默认参数通过约束
        self._auto_apply_recommended(node)
        self.status_var.set(f"已添加: {name}")
        log.info(f"Node added: {name} ({key}) at ({node.x:.0f}, {node.y:.0f})")

    def _auto_apply_recommended(self, node):
        """对新增的处理节点自动枚举方案空间并应用推荐解

        追踪上游管线获取真实的流量水质上下文, 确保方案适配当前位置.
        """
        nt = node.NODE_TYPE
        is_io = _is_io_node(nt)
        skip_sb = not has_solution_space(nt)
        if is_io or skip_sb:
            return
        try:
            from models.base import NodeResult, NodeState, WaterQuality
            from models.solution_space import get_engine

            # 追踪上游获取真实流量水质
            flow, quality = self._trace_upstream_context(node.node_id)

            engine = get_engine()
            sols = engine.enumerate(nt, flow, quality)
            if sols:
                # 选择安全裕度最高的方案 (而非成本最低)
                sol = max(sols, key=lambda s: s.robustness)
                for k, v in sol.params.items():
                    try:
                        node.set_param(k, v)
                    except Exception as e:
                        _log.warning("operation failed: %s", e, exc_info=True)
                result = NodeResult(
                    success=True, params=dict(sol.params), robustness=sol.robustness
                )
                for k, (v, u) in sol.dimensions.items():
                    result.add_dimension(k, v, u)
                for cn, (passed, actual, limit, unit) in sol.checks.items():
                    result.add_check(cn, passed, actual, limit, unit)
                # 记录进/出水水质 — 避免下游节点在 F5 前看到空水质
                result.inlet_quality = WaterQuality(
                    BOD5=quality.BOD5,
                    COD=quality.COD,
                    SS=quality.SS,
                    NH3N=quality.NH3N,
                    TN=quality.TN,
                    TP=quality.TP,
                    pH=7.0,
                )
                result.outlet_quality = quality.apply_removal(node.get_removal_rates())
                node._result = result
                node.state = NodeState.CLEAN
                self._dirty = True
                self.status_var.set(
                    f"已添加: {node.NODE_NAME} (自动应用推荐方案, {len(sols)} 个可用)"
                )
                log.info(
                    f"Auto-applied solution for {node.NODE_NAME}: "
                    f"flow={flow.Q_design:.3f} m3/s, {len(sols)} available"
                )
        except Exception as e:
            log.debug(f"Auto-apply skipped for {node.NODE_NAME}: {e}")

    def _trace_upstream_context(self, node_id: str):
        """沿图反向追踪, 获取某个节点的上游汇入流量和水质"""
        from models.base import PortType, WaterFlow, WaterQuality

        successors, predecessors, indegree = self.executor._build_adjacency()
        preds = predecessors.get(node_id, [])

        if not preds:
            # 无上游: 使用管网默认值或全局默认
            if self._pipe_node and self._pipe_node._total_flow > 0:
                pipe_kz = self._pipe_node.get_param("Kz") or 1.4
                return (
                    WaterFlow(
                        Q_design=self._pipe_node._total_flow,
                        Q_avg_daily=self._pipe_node._total_avg_daily,
                        Kz=pipe_kz,
                    ),
                    WaterQuality(),
                )
            return WaterFlow(), WaterQuality()

        # 收集上游节点的计算结果
        total_flow = 0.0
        max_Kz = 1.0
        total_avg = 0.0
        weighted_q = {"BOD5": 0, "COD": 0, "SS": 0, "NH3N": 0, "TN": 0, "TP": 0}
        has_quality = False
        direct_quality = None  # QUALITY-only 节点直接水质

        for pid in preds:
            upstream = self.executor.get_node(pid)
            if not upstream:
                continue

            # ── 判断是否为 IO 节点(流量源)──
            is_io_node = not any(
                p.port_type in (PortType.WATER, PortType.MIXED)
                for p in upstream.input_ports
            )

            # ── 优先使用已缓存的计算结果 ──
            if upstream.result and upstream.result.success:
                r = upstream.result

                # 判断 QUALITY-only 节点
                is_quality_only = len(upstream.output_ports) > 0 and all(
                    p.port_type == PortType.QUALITY for p in upstream.output_ports
                )

                if is_quality_only and r.outlet_quality:
                    direct_quality = r.outlet_quality
                    continue

                q = r.params.get("Q_design", 0) or 0.0
                if q <= 0 and is_io_node:
                    # IO 节点: 从维度中搜索流量(仅限源节点,处理节点无总流量维度)
                    for k, (v, u) in r.dimensions.items():
                        is_m3s = "m3/s" in u or "m\u00b3/s" in u
                        if (is_m3s or "L/s" in u) and v > 0:
                            q = max(q, v if is_m3s else v / 1000.0)

                # 处理节点: 始终递归到 IO 源获取总流量(避免取到单格流量)
                if not is_io_node:
                    rec_flow, rec_quality = self._trace_upstream_context(pid)
                    q = rec_flow.Q_design
                    total_flow += q
                    if rec_flow.Kz > 1.0:
                        max_Kz = max(max_Kz, rec_flow.Kz)
                    if rec_flow.Q_avg_daily > 0:
                        total_avg += rec_flow.Q_avg_daily
                    elif q > 0 and rec_flow.Kz > 0:
                        total_avg += q * 86400.0 / rec_flow.Kz
                    # 水质直接用递归结果
                    if rec_quality and any(
                        getattr(rec_quality, a, 0) > 0 for a in ["BOD5", "COD"]
                    ):
                        has_quality = True
                        for pk in weighted_q:
                            weighted_q[pk] += q * getattr(rec_quality, pk, 0)
                else:
                    total_flow += q
                    upstream_Kz = r.params.get("Kz", 1.0)
                    if upstream_Kz > 1.0:
                        max_Kz = max(max_Kz, upstream_Kz)
                    upstream_Qad = r.params.get("Q_avg_daily", 0)
                    if upstream_Qad > 0:
                        total_avg += upstream_Qad
                    elif q > 0 and upstream_Kz > 0:
                        total_avg += q * 86400.0 / upstream_Kz

                    if r.outlet_quality:
                        has_quality = True
                        for pk in weighted_q:
                            weighted_q[pk] += q * getattr(r.outlet_quality, pk, 0)

            # ── 回退: IO 节点未计算时直接从参数推算流量 ──
            elif is_io_node:
                q = upstream.get_param("Q_design")
                if q <= 0:
                    # 矿井水输入: Q_design 由 Q_avg_daily/Kz 自动计算
                    q_avg = upstream.get_param("Q_avg_daily")
                    kz = upstream.get_param("Kz") or 1.0
                    if q_avg > 0:
                        q = q_avg / 86400.0 * kz
                if q > 0:
                    total_flow += q
                    kz_val = upstream.get_param("Kz") or 1.0
                    if kz_val > 1.0:
                        max_Kz = max(max_Kz, kz_val)
                    qad = upstream.get_param("Q_avg_daily")
                    if qad > 0:
                        total_avg += qad
                    # 从 water_quality 属性提取水质
                    if hasattr(upstream, "water_quality"):
                        wq = upstream.water_quality
                        has_quality = True
                        for pk in weighted_q:
                            weighted_q[pk] += q * getattr(wq, pk, 0)

            # ── 回退: 未计算的处理节点 → 递归追踪其上游 ──
            else:
                rec_flow, rec_quality = self._trace_upstream_context(pid)
                if rec_flow.Q_design > 0:
                    total_flow += rec_flow.Q_design
                    if rec_flow.Kz > 1.0:
                        max_Kz = max(max_Kz, rec_flow.Kz)
                    total_avg += rec_flow.Q_avg_daily
                    has_quality = True
                    for pk in weighted_q:
                        weighted_q[pk] += rec_flow.Q_design * getattr(
                            rec_quality, pk, 0
                        )

        if total_flow > 0 and has_quality:
            merged_q = WaterQuality(
                **{k: v / total_flow for k, v in weighted_q.items()}
            )
        else:
            merged_q = WaterQuality()

        # QUALITY-only 节点水质直接覆盖
        if direct_quality is not None:
            for pk in weighted_q:
                setattr(merged_q, pk, getattr(direct_quality, pk))

        return (
            WaterFlow(Q_design=total_flow, Q_avg_daily=total_avg, Kz=max_Kz),
            merged_q,
        )

    # ═══════════════════ 管网水力计算 ═══════════════════
    def _on_pipe_hydraulic(self, pipe_type: str = "污水"):
        """管网水力高程计算 — 对 UI 中选择的管网文件执行曼宁公式设计"""
        # 优先使用已加载的完整路径, 其次用 UI 下拉框选择的文件名
        pipe_node = self._pipe_node
        excel_path = (pipe_node._excel_path if pipe_node else "") or ""
        if not excel_path or not os.path.exists(excel_path):
            file_key = self.pipe_var.get()
            data_dir = get_data_dir()
            excel_path = os.path.join(data_dir, f"{file_key}.xlsx")
        if not os.path.exists(excel_path):
            messagebox.showwarning(
                "提示",
                f"文件不存在:\n{excel_path}\n\n请先通过管网下拉框或浏览按钮加载 Excel",
            )
            return

        self.status_var.set(
            f"正在执行{pipe_type}管网水力计算: {os.path.basename(excel_path)}..."
        )
        self.update_idletasks()
        try:
            from pipe_hydraulic import run_pipe_hydraulic

            def pipe_log(msg):
                log.info(msg)

            result = run_pipe_hydraulic(
                excel_path,
                pipe_type=pipe_type,
                log_callback=pipe_log,
            )
            if result:
                messagebox.showinfo(
                    "管网计算完成",
                    f"输出文件:\n{result}\n\n"
                    f"管网节点已自动切换到此文件\n后续构筑物设计将使用此表中的设计流量",
                )
                self.status_var.set(
                    f"{pipe_type}管网水力计算完成 → {os.path.basename(result)}"
                )
                if self._pipe_node:
                    self._pipe_node._excel_path = result
                    self._pipe_node._load_excel_data()
                self._refresh_pipe_files()
            else:
                log.error(f"Pipe hydraulic failed for {excel_path}")
                messagebox.showerror(
                    "管网计算失败",
                    f"请检查:\n"
                    f"1. Excel 中除「计算结果」「管道统计」外还有数据 sheet\n"
                    f"2. 每行包含 8 列: 起点编号/终点编号/长度/地面标高/...\n\n"
                    f"文件: {os.path.basename(excel_path)}",
                )
        except Exception as e:
            log.error(f"Hydraulic calculation failed: {e}")
            messagebox.showerror("管网计算失败", str(e))

    def _on_ui_connection(self, fp, tp):
        """用户手动连线 → 同步到 executor"""
        fn, tn = fp.node, tp.node
        if not (fn.backend and tn.backend):
            return
        # 按端口类型匹配后端端口 (canvas 用小写 "water", backend 用大写 PortType.WATER)
        fbp = next(
            (
                p
                for p in fn.backend.output_ports
                if p.port_type.name.lower() == fp.port_type
            ),
            None,
        )
        tbp = next(
            (
                p
                for p in tn.backend.input_ports
                if p.port_type.name.lower() == tp.port_type
            ),
            None,
        )
        if fbp and tbp:
            try:
                self.executor.connect(fbp, tbp)
                self.status_var.set(f"连线: {fn.name} → {tn.name}")
            except ValueError as e:
                messagebox.showwarning("连线错误", str(e))

    def _on_canvas_add_node(self, key, x, y):
        registry = _get_node_registry()
        if key not in registry:
            return
        cls, name = registry[key]
        node = cls()
        node.x, node.y = x, y
        self.executor.add_node(node)
        ui = self.canvas_view.add_node(name, key, node, x, y)
        self.node_items[ui.node_id] = ui
        if key == "pipe_network":
            self._pipe_node = node
            if not node._excel_path:
                node.set_excel("pipe_final")
        # 项目加载时 (rebuild_canvas) 批量处理, 跳过单节点 auto-apply
        if not getattr(self, "_loading_project", False):
            self._auto_apply_recommended(node)
        self._dirty = True
        self.status_var.set(f"已添加: {name}")

    def _on_canvas_delete_node(self, nid):
        self._do_delete(nid)

    # ═══════════════ 节点管理 ═══════════════
    def _delete_selected(self):
        if not self.node_items:
            messagebox.showinfo("提示", "无节点")
            return
        if self._selected_id and self._selected_id in self.node_items:
            self._do_delete(self._selected_id)
        else:
            messagebox.showinfo("提示", "请先在画布上选中一个节点")
            return

    def _do_delete(self, nid):
        if nid not in self.node_items:
            return
        ui = self.node_items[nid]
        name = ui.name
        self.canvas_view.remove_node(nid)
        self.executor.remove_node(nid)
        del self.node_items[nid]

        # 清除管网节点引用
        if self._pipe_node and self._pipe_node.node_id == nid:
            self._pipe_node = None
        if self._selected_id == nid:
            self._selected_id = None
            self._refresh_params()
        self._dirty = True
        self.status_var.set(f"已删除: {name}")

    # ═══════════════════ 计算 ═══════════════════
    def _on_calc_pipe(self):
        """仅计算管网输入节点(快速刷新Excel数据)"""
        pipe_node = self._pipe_node
        if not pipe_node:
            self.status_var.set("无管网节点")
            return
        self.status_var.set("计算管网中...")
        self.update_idletasks()
        flow = WaterFlow()
        quality = WaterQuality()
        result, _, _ = pipe_node.execute(flow, quality)
        ui = self.node_items.get(pipe_node.node_id)
        if ui:
            ui.set_status("#44cc44" if (result and result.success) else "#ee4444")
        self.status_var.set(
            "管网计算完成" if (result and result.success) else "管网计算失败"
        )
        if self._selected_id and self._selected_id == pipe_node.node_id:
            self._refresh_selected_result()

    # ═══════════════ 查询/获取 ═══════════════
    def _get_effluent_std(self, node=None):
        """获取出水标准 — 按水类型自动选择"""
        # 从节点或全局图判断水类型
        is_mine_water = False
        if node:
            is_mine_water = (
                node.NODE_TYPE.startswith("kw_") or node.NODE_CATEGORY == "矿井水处理"
            )
        else:
            for n in self.executor._nodes.values():
                if n.NODE_TYPE.startswith("kw_") or n.NODE_CATEGORY == "矿井水处理":
                    is_mine_water = True
                    break
        if is_mine_water:
            return {"BOD5": 4, "COD": 20, "SS": 70, "NH3N": 1.0, "TN": 1.0, "TP": 0.2}
        return {"BOD5": 10, "COD": 50, "SS": 10, "NH3N": 5, "TN": 15, "TP": 0.5}

    # ═══════════════ 事件回调 ═══════════════
    def _on_calc_all(self):
        """统一计算: 通过 DAG 执行引擎全图计算

        所有节点(包括管网输入)由 GraphExecutor 统一管理.
        不再预先直接调用 pipe_node.execute() — 这会过早将节点标记为
        CLEAN,导致 GraphExecutor 无法检测参数变更并传播到下游,
        造成 CombinerNode 等下游节点走清洁路径、面板流量显示停滞.
        """
        self._on_calc_rest()

    def _on_clear_cache(self):
        """清除所有缓存: 方案空间 + 节点状态 + 标签缓存 → 强制下次 F5 全量重算"""
        import gc

        # 1. 清除方案空间枚举缓存
        try:
            from models.solution_space import get_engine

            engine = get_engine()
            engine._cache.clear()
        except (ImportError, AttributeError):
            pass
        # 2. 所有节点标记为 DIRTY (强制 F5 全量重算)
        for node in self.executor._nodes.values():
            node.state = NodeState.DIRTY
        # 3. 清除动态标签缓存
        try:

            # 清除模块级缓存
            import ui.dimension_labels as dl

            dl._dynamic_labels_cache = None
        except (ImportError, AttributeError):
            pass
        # 4. 强制垃圾回收清除残留

        gc.collect()
        self._dirty = True
        self.status_var.set("缓存已清除 — 请按 F5 重新计算")

    def _on_validate_quick(self):
        """运行快速模组验证 (delegated to validator_dialog)"""
        run_validator_dialog(self, self.status_var, mode="quick")

    def _on_validate_deep(self):
        """运行深度模组验证 (delegated to validator_dialog)"""
        run_validator_dialog(self, self.status_var, mode="deep")

    def _on_self_test(self):
        """运行系统自检 (delegated to self_test module)"""
        self.status_var.set("正在运行系统自检...")
        self.update_idletasks()
        try:
            from self_test import run_self_test, format_report
            report = run_self_test()
            text = format_report(report)
            self.status_var.set(
                f"自检完成: {report.passed}/{report.total} 通过"
                if report.healthy
                else f"自检: {report.failed} 项失败"
            )
            # 弹窗显示结果
            dialog = tk.Toplevel(self)
            dialog.title("系统自检报告")
            dialog.geometry("700x550")
            dialog.configure(bg="#1e1e1e")
            txt = tk.Text(dialog, bg="#1e1e1e", fg="#ccc",
                          font=("Consolas", 10), wrap=tk.WORD)
            txt.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            txt.insert("1.0", text)
            txt.configure(state=tk.DISABLED)
            btn = ttk.Button(dialog, text="关闭", command=dialog.destroy)
            btn.pack(pady=(0, 10))
        except Exception as e:
            self.status_var.set(f"自检失败: {e}")
            messagebox.showerror("自检错误", f"无法运行自检:\n{e}")

    def _on_export_cost(self):
        """导出完整工程概算报告 (delegated to export_handlers)"""
        export_cost_report(self.executor, self._pipe_node, self.status_var, self)

    def _on_calc_pipe_cost(self):
        """生成管网概算报告 (delegated to export_handlers)"""
        calc_pipe_cost_report(self._pipe_node, self.status_var, self)

    def _on_export_all(self):
        """分类输出全部计算结果 (delegated to export_handlers)"""
        export_all_results(self.executor, self.status_var, self)

    # ═══════════════ 面板刷新 ═══════════════
    def _refresh_selected_result(self):
        """刷新当前选中节点的结果显示 (4列 Treeview)"""
        if self._selected_id and self._selected_id in self.node_items:
            be = self.node_items[self._selected_id].backend
            if be:
                self._populate_result_tree(be)
                return
        # 无选中节点
        for item in self.result_tree.get_children():
            self.result_tree.delete(item)
        self.result_check_text.configure(state=tk.NORMAL)
        self.result_check_text.delete("1.0", tk.END)

        self.result_check_text.configure(state=tk.DISABLED)
        self.result_tree.insert(
            "",
            tk.END,
            values=(
                "←",
                "点击节点查看计算结果",
                "",
                "",
            ),
            tags=("hint",),
        )

    # ═══════════════ 事件回调 ═══════════════
    def _on_calculate(self):
        """保留旧接口兼容"""
        self._on_calc_rest()

    def _suggest_fix(self, check_name: str, actual, limit) -> str:
        """根据约束名称给出修改建议"""
        suggestions = {
            "长宽比": "调整池宽B或池长L,使L/B在约束范围内",
            "宽高比": "调整池宽B或有效水深",
            "径深比": "增大池径D或减小有效水深h2",
            "停留时间": "调整池体尺寸或流量",
            "安全距离": "降低MLSS浓度或减小充水比λ",
            "污泥龄": "增大有效容积或减少排泥量",
            "强制滤速": "增加滤池格数或降低设计滤速",
            "堰负荷": "增加堰长(增设内侧堰)或降低流量",
            "充水比": "调整有效容积或工作周期Tc",
            "表面负荷": "增大沉淀面积或降低流量",
            "固体通量": "增大沉淀区面积",
            "紫外剂量": "增加灯管排数或降低渠道流速",
            "砂斗容积": "增大砂斗上口直径或池径",
            "过栅流速": "调整栅前水深h或栅条间隙b",
            "斜管轴向流速": "降低表面负荷或增大斜管倾角",
            "冲洗水占比": "降低反冲洗强度或延长过滤周期",
            "实际HRT": "增大池体尺寸或减少池数",
        }
        for key, sug in suggestions.items():
            if key in check_name:
                return sug
        return ""

    # ═══════════════ UI 构建 ═══════════════
    def _build_elevation_view(self):
        """构建高程面板 Treeview (暗色主题)."""
        self._elevation_tree = ttk.Treeview(
            self.elevation_frame,
            columns=("symbol", "meaning", "unit", "value"),
            show="headings",
            height=10,
        )
        self._elevation_tree.heading("symbol", text="符号")
        self._elevation_tree.heading("meaning", text="物理意义")
        self._elevation_tree.heading("unit", text="单位")
        self._elevation_tree.heading("value", text="取值")
        self._elevation_tree.column("symbol", width=75, anchor="center", stretch=False)
        self._elevation_tree.column("meaning", width=220, anchor="w")
        self._elevation_tree.column("unit", width=55, anchor="center", stretch=False)
        self._elevation_tree.column("value", width=100, anchor="e", stretch=False)
        # 暗色主题 (与结果面板一致)
        style = ttk.Style()
        style.configure(
            "Elevation.Treeview",
            background="#1a1a1a",
            foreground="#ccc",
            fieldbackground="#1a1a1a",
            rowheight=22,
        )
        style.configure(
            "Elevation.Treeview.Heading",
            background="#2d2d2d",
            foreground="#ffaa44",
            font=("Microsoft YaHei", 9, "bold"),
        )
        style.map("Elevation.Treeview", background=[("selected", "#3a5a1a")])
        # 蓝色分组标题行
        self._elevation_tree.tag_configure(
            "section_header",
            background="#1a3a5a",
            foreground="#88bbff",
            font=("Microsoft YaHei", 9, "bold"),
        )
        self._elevation_tree.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    # ═══════════════ 面板刷新 ═══════════════
    def _refresh_elevation_view(self):
        """刷新高程面板 — 从选中节点的 ElevationData 填充."""
        for item in self._elevation_tree.get_children():
            self._elevation_tree.delete(item)

        if not self._selected_id or self._selected_id not in self.node_items:
            self._elevation_tree.insert(
                "", tk.END, values=("←", "点击节点查看高程", "", "")
            )
            return

        backend = self.node_items[self._selected_id].backend
        if not backend or not backend.result or not backend.result.elevation:
            self._elevation_tree.insert("", tk.END, values=("—", "无高程数据", "", ""))
            return

        elev = backend.result.elevation
        rows = [
            ("Z_ground", "地面标高", "m", elev.ground_elevation),
            ("Z_bottom", "池底/管内底标高", "m", elev.bottom_elevation),
            ("Z_water", "水面标高", "m", elev.water_elevation),
            ("h_eff", "有效水深", "m", elev.effective_depth),
            ("h_super", "超高", "m", elev.super_elevation),
            ("h_loss", "本节点水头损失", "m", elev.head_loss),
            ("Z_upstream", "上游水面标高", "m", elev.upstream_water_elevation),
        ]

        if elev.head_loss_detail:
            rows.append(("detail", "水头损失明细", "", elev.head_loss_detail))
        if elev.formula:
            rows.append(("formula", "计算公式", "", elev.formula))

        for sym, meaning, unit, val in rows:
            self._elevation_tree.insert(
                "", tk.END, values=(sym, meaning, unit, self._fmt_val(val))
            )

    @staticmethod
    def _fmt_val(val):
        """Format a value for Treeview display."""
        if isinstance(val, float):
            return f"{val:.2f}"
        return str(val)

    def _get_scope_prefix(self, dim_name: str, node_type: str) -> str:
        """从模组 labels.json 读取维度的作用域前缀."""
        try:
            from mods.mod_manager import get_mod_manager

            mgr = get_mod_manager()
            labels = mgr.load_labels(node_type)
            if labels and "dim_scopes" in labels:
                scope = labels["dim_scopes"].get(dim_name, "")
                from models.base import NodeResult

                return NodeResult.SCOPE_PREFIX.get(scope, "")
        except Exception:
            pass
        return ""

    def _dim_formula(self, dim_name: str, node_type: str) -> str:
        """维度公式回退查询."""
        import re

        clean = re.sub(
            r"^\[(?:单池|单格|单系列|单斗|单孔|总|集水池)\]", "", dim_name
        ).strip()

        if "去除率" in dim_name:
            return "η = (进水-出水)/进水 × 100%"
        if re.match(r"进水(BOD|COD|SS|NH|TN|TP|pH)", dim_name):
            return "上游来水水质，流量加权平均"
        if re.match(r"出水(BOD|COD|SS|NH|TN|TP|pH)", dim_name):
            return "进水水质 × (1 - 去除率)"
        if "功率" in dim_name:
            return "P = P_density × V"
        if "浓度" in dim_name:
            return "X = 设计规范推荐值或用户设定"
        if any(kw in dim_name for kw in ["数量", "台数", "格数", "个数"]):
            return "用户设定或设计规范推荐"
        from models.dimension_formulas import get_formula as gf

        mod_formula = gf(dim_name, node_type)
        return mod_formula[:100] if mod_formula else "详见设计规范及计算书"

    def _on_calc_rest(self):
        """Calculate remaining (non-primary) nodes after auto-apply."""
        self.status_var.set("正在重算下游...")
        self.update_idletasks()
        try:
            self.executor.execute(force_all=False)
            self._refresh_selected_result()
            self._update_all_node_statuses()
            self.status_var.set("计算完成")
        except Exception as e:
            self.status_var.set(f"计算失败: {e}")

    def _update_all_node_statuses(self):
        """Update canvas status lights for all nodes based on calculation results."""
        for nid, node in self.executor._nodes.items():
            ui = self.node_items.get(nid)
            if ui and node.result:
                color = "#44cc44" if node.result.success else "#ee4444"
                ui.set_status(color)

    # ═══════════════ 数据填充 ═══════════════
    def _populate_result_tree(self, backend):
        """将节点计算结果填充到 4 列 Treeview: 符号 | 物理意义 | 单位 | 取值."""
        for item in self.result_tree.get_children():
            self.result_tree.delete(item)

        node = backend
        result = node.result
        if not result or not result.success:
            self.result_tree.insert(
                "",
                tk.END,
                values=("✗", "计算失败", "", result.error_msg if result else ""),
            )
            self.result_check_text.configure(state=tk.NORMAL)
            self.result_check_text.delete("1.0", tk.END)
            self.result_check_text.configure(state=tk.DISABLED)
            return

        from models.dimension_formulas import get_param_category
        from ui.dimension_labels import (
            format_dimension_row,
            format_param_value,
            resolve_dimension,
            split_dimensions,
        )

        computed, physical, wq_in_out, wq_removal = split_dimensions(
            result.dimensions, result.dimension_categories
        )

        # ── 1. 原始设计参数 (合并 basic/physical/operating, 对齐 Excel 输出) ──
        param_items = []
        for key, val in result.params.items():
            sym, meaning, unit = resolve_dimension(key)
            val_str = format_param_value(key, val) if val is not None else ""
            param_items.append((sym, meaning, unit, val_str))

        if param_items:
            self.result_tree.insert(
                "", tk.END,
                values=("", "── 原始设计参数 ──", "", ""),
                tags=("section_banner",),
            )
            for sym, meaning, unit, val_str in param_items:
                self.result_tree.insert(
                    "", tk.END,
                    values=(sym, meaning, unit, val_str),
                    tags=("param",),
                )

        # ── 2. 计算结果 (不含水质) ──
        if computed:
            self.result_tree.insert(
                "", tk.END,
                values=("", "── 计算结果 ──", "", ""),
                tags=("section_banner",),
            )
            for key, val, unit in computed:
                display_name = (
                    result.get_display_name(key)
                    if hasattr(result, "get_display_name")
                    else key
                )
                sym, meaning, _ = format_dimension_row(display_name, val, unit)
                self.result_tree.insert(
                    "", tk.END, values=(sym, meaning, unit, self._fmt_val(val))
                )
                formula = result.dimension_formulas.get(key, "")
                if formula:
                    self.result_tree.insert(
                        "", tk.END,
                        values=("", f"↳ {formula}", "", ""),
                        tags=("formula_sub",),
                    )

        # ── 3. 构筑物尺寸 ──
        if physical:
            self.result_tree.insert(
                "", tk.END,
                values=("", "── 构筑物尺寸 ──", "", ""),
                tags=("section_banner",),
            )
            for key, val, unit in physical:
                display_name = (
                    result.get_display_name(key)
                    if hasattr(result, "get_display_name")
                    else key
                )
                sym, meaning, _ = format_dimension_row(display_name, val, unit)
                self.result_tree.insert(
                    "", tk.END, values=(sym, meaning, unit, self._fmt_val(val))
                )
                formula = result.dimension_formulas.get(key, "")
                if formula:
                    self.result_tree.insert(
                        "", tk.END,
                        values=("", f"↳ {formula}", "", ""),
                        tags=("formula_sub",),
                    )

        # ── 4. 约束校核 (仅底部 Text 窗口) ──
        self.result_check_text.configure(state=tk.NORMAL)
        self.result_check_text.delete("1.0", tk.END)
        if result.checks:
            self.result_check_text.insert(tk.END, "约束校核:\n", ("bold",))
            for check_name, (passed, actual, limit, unit) in result.checks.items():
                icon = "✓" if passed else "✗"
                tag_name = "check_pass" if passed else "check_fail"
                self.result_check_text.tag_configure(
                    tag_name, foreground="#55cc88" if passed else "#ff5555"
                )
                self.result_check_text.insert(
                    tk.END, f"  [{icon}] {check_name}: ", (tag_name,)
                )
                self.result_check_text.insert(
                    tk.END,
                    f"{actual:.2f}{unit} vs {limit}{unit}\n",
                )
            self.result_check_text.configure(state=tk.DISABLED)

    def _on_tab_changed(self):
        # 隐藏所有内容面板
        self.params_frame.pack_forget()
        self.result_frame.pack_forget()
        self.quality_text.pack_forget()
        self.constraint_frame.pack_forget()
        self.elevation_frame.pack_forget()
        if self._solution_browser:
            self._solution_browser.pack_forget()
        tab = self.tab_var.get()
        if tab == "params":
            self._refresh_params()
        elif tab == "results":
            self._refresh_selected_result()
            self.params_frame.pack_forget()
            if self._solution_browser:
                self._solution_browser.pack_forget()
            self.result_frame.pack(
                side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5
            )
        elif tab == "quality":
            self.params_frame.pack_forget()
            if self._solution_browser:
                self._solution_browser.pack_forget()
            self.quality_text.pack(
                side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5
            )
            # 委托给 QualityPanel
            if self._selected_id and self._selected_id in self.node_items:
                be = self.node_items[self._selected_id].backend
                if be:
                    from models.node_registry import is_water_quality_node
                    if is_water_quality_node(be.NODE_TYPE):
                        self._quality_panel.show_water_quality_card(be)
                    else:
                        self._quality_panel.build_full_quality_flow(
                            scroll_to_node_id=self._selected_id
                        )
            else:
                self._quality_panel.build_full_quality_flow()
        elif tab == "constraints":
            self.constraint_frame.pack(
                side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5
            )
            if self._selected_id and self._selected_id in self.node_items:
                be = self.node_items[self._selected_id].backend
                if be:
                    applied = (
                        be.result.params if be.result and be.result.success else None
                    )
                    self._constraint_panel.load_node(be, applied)
        elif tab == "elevation":
            self.elevation_frame.pack(
                side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5
            )
            self._refresh_elevation_view()

    # ═══════════════════ 文件操作 ═══════════════════
    def _on_new(self):
        self.file_manager.on_new()

    def _on_open(self):
        self.file_manager.on_open()

    def _on_save(self):
        self.file_manager.on_save()

    def _on_save_as(self):
        self.file_manager.on_save_as()

    def _on_close(self):
        self.file_manager.on_close()

    def _update_recent_menu(self):
        self.file_manager.update_recent_menu()

    def _open_recent(self, path_str):
        self.file_manager.open_recent(path_str)

    def _clear_canvas(self):
        self.file_manager._do_clear()

    # ═══════════════ UI 构建 ═══════════════
    def _rebuild_canvas(self):
        self.file_manager._rebuild_canvas()

    # ═══════════════════ 启动 ═══════════════════
    @staticmethod
    def run():
        MainWindow().mainloop()
