"""
param_panel.py — 参数面板组件 (v5.4 extracted from main_window.py)

管理参数 Tab 的全部 UI: 方案浏览 + 手动微调滑块/输入框。
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict

from _logging import get_logger

# ── 模块级导入 (提前加载, 避免 EXE 打包后动态导入失败) ──
from models.discretization import get_allowed_values
from models.node_registry import has_solution_space
from models.node_registry import is_io_node as _is_io_node
from models.node_registry import is_water_quality_node

from .app_state import AppState

_log = get_logger(__name__)


def _get_formulas() -> Dict[str, str]:
    """获取公式说明 (全部来自 ModManager)."""
    from mods.mod_manager import get_mod_manager

    mgr = get_mod_manager()
    mgr.load_all()
    return dict(mgr.formulas)


def _register_infra_nodes() -> None:
    """注册基础设施节点到 ModManager (数据源自节点类自身)."""
    from models.combiner import CombinerNode
    from models.pipe_network import PipeNetworkNode
    from models.water_quality_node import WaterQualityNode

    from mods.mod_manager import get_mod_manager

    mgr = get_mod_manager()
    if mgr._node_registry:
        return
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


def _ensure_infra_registered():
    """确保基础设施节点已注册(幂等)."""
    from mods.mod_manager import get_mod_manager

    mgr = get_mod_manager()
    mgr.load_all()
    _register_infra_nodes()
    return mgr


class ParamPanel:
    """参数面板 — 管理方案浏览和手动微调滑块.

    从 MainWindow 中分离, 通过回调与主窗口通信.
    """

    # ── 输入校验: 验证 Entry 内容是否为合法浮点数 ──
    @staticmethod
    def _validate_float_entry(value: str) -> bool:
        """Entry validatecommand: 允许空/部分输入 (如 '-', '1.', '1e')"""
        if value == "" or value == "-":
            return True
        try:
            float(value)
            return True
        except ValueError:
            return False

    @staticmethod
    def _set_entry_valid(entry: tk.Entry, valid: bool):
        """无效输入: 红底; 有效输入: 恢复默认"""
        entry.configure(bg="#3a1a1a" if not valid else "#1a1a1a")

    def __init__(
        self,
        parent_frame: tk.Frame,
        executor,
        state: AppState,
        solution_browser,
        quality_panel,
        mode_btn: tk.Button,
        on_dirty: Callable[[], None],
        on_recompute: Callable[[], None],
        on_view_results: Callable[[], None],
        status_var: tk.StringVar,
        trace_upstream: Callable,
        get_pipe_node: Callable,
    ):
        self.parent_frame = parent_frame
        self.executor = executor
        self._state = state
        self._solution_browser = solution_browser
        self._quality_panel = quality_panel
        self._mode_btn = mode_btn
        self._on_dirty = on_dirty
        self._on_recompute = on_recompute
        self._on_view_results = on_view_results
        self.status_var = status_var
        self._trace_upstream = trace_upstream
        self._get_pipe_node = get_pipe_node

        self._current_backend = None

        # Tk register for entry validation
        self._tk_register = parent_frame.winfo_toplevel().register

        # 确保基础设施已注册 (公式查询用)
        _ensure_infra_registered()

    # ═══════════════ 公共接口 ═══════════════

    def load_node(self, backend) -> None:
        """Show params for the selected node"""
        self._current_backend = backend

        # 隐藏两个面板
        self.parent_frame.pack_forget()
        if self._solution_browser:
            self._solution_browser.pack_forget()

        if not backend:
            self.parent_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
            tk.Label(
                self.parent_frame,
                text="← 点击节点查看参数",
                bg="#252525",
                fg="#888",
                font=("Microsoft YaHei", 10),
            ).pack(pady=40)
            return

        if self._state.browse_mode:
            self._show_browse_mode(backend)
        else:
            self._show_manual_mode(backend)

    def clear(self) -> None:
        """Clear param display"""
        self.parent_frame.pack_forget()
        if self._solution_browser:
            self._solution_browser.pack_forget()
        self._current_backend = None

    def refresh(self) -> None:
        """Re-render without clearing (re-read current backend params)"""
        if self._current_backend:
            self.load_node(self._current_backend)
        else:
            self.clear()

    # ═══════════════ 面板显示 ═══════════════

    def _show_browse_mode(self, be, force_recompute=False):
        """显示方案浏览器

        v5.4: 始终强制重新枚举 — 缓存方案可能基于旧流量/水质,
        导致陈旧方案排在第一位, 混淆用户判断.
        """
        if not self._solution_browser:
            return
        # 输入/合并节点和非水处理阶段节点没有方案空间, 走手动卡片模式
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

        # 获取当前上下文的水量水质 — 从上游追踪, 而非读节点自身参数
        flow, quality = self._trace_upstream(be.node_id)
        # 水质优先使用缓存结果中的进水水质
        if be.result and be.result.inlet_quality:
            quality = be.result.inlet_quality
        # 水量优先使用缓存结果中的流量(若上游追踪返回零流量则回退到节点参数)
        if flow.Q_design <= 0 and be.result:
            for name, (val, unit) in be.result.dimensions.items():
                if "设计流量" in name and "m³/s" in unit and val > 0:
                    flow.Q_design = val
                    break
        if flow.Q_design <= 0:
            pipe_node = self._get_pipe_node()
            if pipe_node and pipe_node._total_flow > 0:
                flow.Q_design = pipe_node._total_flow
                flow.Q_avg_daily = pipe_node._total_avg_daily
        if flow.Q_design <= 0:
            from models.base import WaterFlow

            flow = WaterFlow(Q_design=0.57, Q_avg_daily=34760.7, Kz=1.4)
        self._solution_browser.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        # v5.4: force_recompute=True — 确保始终显示当前流量/水质下的最新方案
        self._solution_browser.load_node(be, flow, quality, force_recompute=True)

        # ── 诊断日志: 方案为空时输出上下文 ──
        if not self._solution_browser._solutions:
            from ui.logger import log

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
                "  参数: %s",
                dict(be._params) if hasattr(be, "_params") else "N/A",
            )
            log.warning(
                "  节点状态: %s",
                be.state.name if hasattr(be, "state") else "N/A",
            )
            if be.result:
                log.warning("  缓存结果: success=%s", be.result.success)

    def _show_manual_mode(self, be):
        """显示旧版滑块面板(取值约束为离散值)"""
        # ── 水质节点特殊处理 ──
        show_wq = is_water_quality_node(be.NODE_TYPE)
        if show_wq:
            self.parent_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
            self._quality_panel.show_water_quality_card(
                be, parent_frame=self.parent_frame
            )
            # kw_input: 在水量水质卡片下方额外显示流量 + 高程参数
            if be.NODE_TYPE == "kw_input":
                self._show_kw_engineering_params(be)
            return

        self.parent_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        # 清理 parent_frame 内的旧控件
        for w in self.parent_frame.winfo_children():
            w.destroy()
        self._state.slider_vars.clear()

        # 标题
        tk.Label(
            self.parent_frame,
            text=f"▎{be.NODE_NAME}",
            bg="#252525",
            fg="#fff",
            font=("Microsoft YaHei", 12, "bold"),
        ).pack(anchor="w", padx=10, pady=(10, 2))
        tk.Label(
            self.parent_frame,
            text=f"类型: {be.NODE_CATEGORY} | 状态: {be.state.name}",
            bg="#252525",
            fg="#888",
            font=("Microsoft YaHei", 8),
        ).pack(anchor="w", padx=10)

        # 公式
        formula = _get_formulas().get(be.NODE_TYPE, "")
        if formula:
            ff = tk.Frame(self.parent_frame, bg="#1a1a1a", bd=1, relief=tk.SUNKEN)
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
                self.parent_frame,
                text="无可调参数",
                bg="#252525",
                fg="#666",
            ).pack(pady=20)
            return

        canvas = tk.Canvas(self.parent_frame, bg="#252525", highlightthickness=0)
        scrollbar = tk.Scrollbar(
            self.parent_frame, orient=tk.VERTICAL, command=canvas.yview, width=8
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
            self._state.slider_vars[pd.key] = var

            # 如果有离散值约束, 使用 Combobox 而非 Entry+Scale
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
                # StringVar for Entry — Excel-like editing
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
                # 输入校验: 阻止非数字输入
                vcmd = (self._tk_register(self._validate_float_entry), "%P")
                entry.configure(validate="key", validatecommand=vcmd)

                def _sync_entry_to_scale(k=pd.key, sv=str_var, dv=var):
                    """Entry → Scale: parse text, update DoubleVar + params"""
                    try:
                        val = float(sv.get())
                        dv.set(val)
                        self._on_param_changed(k, val)
                        self._set_entry_valid(entry, True)
                    except (ValueError, tk.TclError):
                        self._set_entry_valid(entry, False)

                def _sync_scale_to_entry(k=pd.key, sv=str_var, dv=var):
                    """Scale → Entry: update display + params"""
                    val = dv.get()
                    sv.set(str(round(val, 6)).rstrip("0").rstrip("."))
                    self._on_param_changed(k, val)

                entry.bind("<Return>", lambda e, f=_sync_entry_to_scale: f())

                def _on_focus_out(e, f=_sync_entry_to_scale):
                    self.parent_frame.after(
                        10,
                        lambda: (
                            f() if self.parent_frame.focus_get() is not None else None
                        ),
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
                rvar = tk.DoubleVar(value=rates[pk] * 100)
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
        ttk.Button(
            btn_frame,
            text="查看此节点结果",
            command=self._on_view_results,
        ).pack(side=tk.LEFT, padx=4)
        ttk.Button(
            btn_frame,
            text="重置默认值",
            command=lambda: self._reset_params(be),
        ).pack(side=tk.LEFT, padx=4)

    # ═══════════════ 事件回调 ═══════════════

    def _on_toggle_mode(self):
        """切换方案浏览 / 手动微调"""
        self._state.browse_mode = not self._state.browse_mode
        self._mode_btn.config(
            text="📊 方案浏览" if self._state.browse_mode else "🎚 手动微调",
            bg="#3a5a1a" if self._state.browse_mode else "#5a3a1a",
        )
        self.refresh()

    def _on_solution_applied(self, solutions, selected_idx=None):
        """方案应用回调 — 标记节点为 CLEAN, 触发下游重算"""
        self._on_recompute()

    def _on_constraint_changed(self, node_type: str):
        """约束限值变更回调 — 刷新方案空间 + 标记相关节点需重算

        关键修复: 约束参数通过面板"确定"按钮提交后, 必须标记所有同类型节点
        为 DIRTY, 否则 F5 计算时 executor.execute(force_all=False) 找不到 DIRTY
        节点, 导致使用陈旧缓存结果而非新参数重算.
        """
        from models.base import NodeState

        # 标记所有同 node_type 的节点为 DIRTY (discretization config 是
        # 按 nodetype 共享的, 修改约束影响该类型所有节点实例)
        for nid, node in self.executor._nodes.items():
            if getattr(node, "NODE_TYPE", "") == node_type:
                node.state = NodeState.DIRTY
        self.status_var.set(f"约束限值已更新 — {node_type} 方案空间需刷新")
        self._state.is_dirty = True

    def _on_rate_changed(self, pollutant: str, rate: float, be):
        """去除率滑块变更"""
        be.set_removal_rate(pollutant, rate)
        self._state.is_dirty = True

    def _on_param_changed(self, key, var):
        """参数滑块变更回调 — v5.3-s2 关键修复: 必须回写 backend."""
        self._state.is_dirty = True
        if self._current_backend:
            # ⚠️ v5.3-s2 P0 Fix: slider → set_param → _params 更新
            # 缺少此行则 F5 时读取旧参数值 (v5.4 agent 提取时遗漏)
            self._current_backend.set_param(key, float(var))
            self.status_var.set(
                f"{self._current_backend.NODE_NAME} 参数已变更: {key} = {var}"
            )

    def _show_kw_engineering_params(self, be):
        """kw_input 专用: 在水质卡片下方显示流量 + 高程工程参数.

        矿井水输入节点既需要编辑水质 (由 quality_panel 负责),
        也需要编辑流量和高程参数 (此方法负责).
        """
        # 水质相关的参数键 (已在水质卡片中编辑, 不再重复显示)
        _wq_keys = {"SS_in", "COD", "BOD5", "NH3N", "TN", "TP", "TDS", "pH"}

        param_defs = [pd for pd in be.get_param_defs() if pd.key not in _wq_keys]
        if not param_defs:
            return

        # ── 分隔线 ──
        sep = tk.Frame(self.parent_frame, bg="#444", height=2)
        sep.pack(fill=tk.X, padx=8, pady=(8, 4))
        tk.Label(
            self.parent_frame,
            text="▎工程参数 (流量/高程)",
            bg="#252525",
            fg="#ffaa44",
            font=("Microsoft YaHei", 10, "bold"),
        ).pack(anchor="w", padx=10, pady=(2, 4))

        # ── 滑块容器 (带滚动) ──
        kw_frame = tk.Frame(self.parent_frame, bg="#252525")
        kw_frame.pack(fill=tk.X, padx=5, pady=(0, 8))

        # 获取离散值约束
        allowed = {}
        try:
            allowed = {
                pd.key: get_allowed_values(be.NODE_TYPE, pd.key) for pd in param_defs
            }
        except KeyError:
            pass

        for pd in param_defs:
            row = tk.Frame(kw_frame, bg="#2d2d2d", bd=1, relief=tk.GROOVE)
            row.pack(fill=tk.X, padx=2, pady=1)
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
            self._state.slider_vars[pd.key] = var

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
                vcmd = (self._tk_register(self._validate_float_entry), "%P")
                entry.configure(validate="key", validatecommand=vcmd)

                def _sync_entry(k=pd.key, sv=str_var, dv=var):
                    try:
                        val = float(sv.get())
                        dv.set(val)
                        self._on_param_changed(k, val)
                        self._set_entry_valid(entry, True)
                    except (ValueError, tk.TclError):
                        self._set_entry_valid(entry, False)

                def _sync_scale(k=pd.key, sv=str_var, dv=var):
                    val = dv.get()
                    sv.set(str(round(val, 6)).rstrip("0").rstrip("."))
                    self._on_param_changed(k, val)

                entry.bind("<Return>", lambda e, f=_sync_entry: f())
                entry.bind(
                    "<FocusOut>",
                    lambda e, f=_sync_entry: self.parent_frame.after(
                        10,
                        lambda: (
                            f() if self.parent_frame.focus_get() is not None else None
                        ),
                    ),
                )
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
                scale.bind("<ButtonRelease-1>", lambda e, f=_sync_scale: f())
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

    def _reset_params(self, be):
        """重置为默认值"""
        be.reset_params()
        self.refresh()

    # ═══════════════ 自动应用推荐方案 ═══════════════

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
            flow, quality = self._trace_upstream(node.node_id)

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
                    success=True,
                    params=dict(sol.params),
                    robustness=sol.robustness,
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
                self._state.is_dirty = True
                self.status_var.set(
                    f"已添加: {node.NODE_NAME} (自动应用推荐方案, {len(sols)} 个可用)"
                )
                from ui.logger import log

                log.info(
                    "Auto-applied solution for %s: " "flow=%.3f m3/s, %d available",
                    node.NODE_NAME,
                    flow.Q_design,
                    len(sols),
                )
        except Exception as e:
            from ui.logger import log

            log.debug("Auto-apply skipped for %s: %s", node.NODE_NAME, e)
