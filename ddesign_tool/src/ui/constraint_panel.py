"""
constraint_panel.py — 约束条件调节面板

v3.5 新增: 在右侧面板"约束"Tab中显示当前节点的约束条件,
分为"原始约束"(固定设计参数,单值输入)和"结果约束"(校核阈值,上下限输入).

每个约束行包含: 名称标签、输入框(单值或上下限)、"确定"按钮.
点击确定后:
  1. 按钮变绿 (#55cc55) 2秒后恢复
  2. 更新 discretization 配置中的 fixed 参数或 constraint_limits
  3. 触发回调 → 主窗口清除缓存 + 重新枚举方案空间
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict, Optional

from _logging import get_logger

_log = get_logger(__name__)


class ConstraintPanel(tk.Frame):
    """约束条件调节面板

    用法:
        panel = ConstraintPanel(parent, on_constraint_changed=callback)
        panel.load_node(backend_node)  # 加载选中节点的约束
    """

    def __init__(
        self,
        parent,
        on_constraint_changed: Optional[Callable[[str], None]] = None,
        bg: str = "#252525",
        **kwargs,
    ):
        super().__init__(parent, bg=bg, **kwargs)
        self._on_constraint_changed = on_constraint_changed
        self._bg = bg
        self._node_type: Optional[str] = None
        self._node_name: str = ""
        self._confirm_buttons: Dict[str, tk.Button] = {}
        self._applied_states: Dict[str, bool] = {}  # 约束是否处于"已应用"状态
        self._original_entries: Dict[str, dict] = (
            {}
        )  # {key: {"entry": tk.Entry, "sv": tk.StringVar}}
        self._result_entries: Dict[str, dict] = (
            {}
        )  # {key: {"lo_entry", "lo_sv", "hi_entry", "hi_sv"}}
        self._original_free: Dict[str, list] = {}  # 原始自由参数列表(不被收缩影响)

        # 空状态提示
        self._empty_label = tk.Label(
            self,
            text="← 点击节点查看约束条件",
            bg=bg,
            fg="#888",
            font=("Microsoft YaHei", 10),
        )
        self._empty_label.pack(pady=40)

    def load_node(self, backend_node, applied_params: Optional[Dict] = None) -> None:
        """加载节点的约束条件到面板

        Args:
            backend_node: NodeBase 实例
            applied_params: 当前已应用方案的参数 dict (用于初始化显示值)
        """
        # 清除旧内容
        self._clear()
        self._node_type = backend_node.NODE_TYPE
        self._node_name = backend_node.NODE_NAME
        self._applied_params = applied_params or {}

        # ── IO 节点、合并节点等无约束配置 → 友好提示 ──
        try:
            from models.node_registry import is_io_node

            if is_io_node(self._node_type) or self._node_type in (
                "combiner",
                "wuni_hebing",
            ):
                self._show_empty(f"「{self._node_name}」为输入/合并节点,无可调约束")
                return
        except ImportError:
            pass

        # 获取约束配置
        try:
            from models.discretization import (
                get_config,
                get_constraint_types,
                get_result_constraints,
            )

            cfg = get_config(self._node_type)
        except (KeyError, ImportError):
            self._show_empty(f"「{self._node_name}」无可调约束")
            return

        fixed = cfg.get("fixed", {})
        free = cfg.get("free", {})
        # ── 保存原始自由参数值(深拷贝,避免被 _on_original_confirm 收缩后丢失选项)──
        import copy

        self._original_free = copy.deepcopy(free)
        constraint_types = get_constraint_types(self._node_type)
        result_names = get_result_constraints(self._node_type)
        constraint_limits = cfg.get("constraint_limits", {})

        if not fixed and not constraint_types:
            self._show_empty(f"「{self._node_name}」无可调约束")
            return

        # 创建可滚动画布
        canvas = tk.Canvas(self, bg=self._bg, highlightthickness=0)
        scrollbar = tk.Scrollbar(
            self, orient=tk.VERTICAL, command=canvas.yview, width=8
        )
        scroll_frame = tk.Frame(canvas, bg=self._bg)
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
        scroll_frame.bind(
            "<MouseWheel>", lambda e: canvas.yview_scroll(int(-e.delta / 120), "units")
        )

        # ── 标题 ──
        tk.Label(
            scroll_frame,
            text=f"▎约束条件 — {self._node_name}",
            bg=self._bg,
            fg="#fff",
            font=("Microsoft YaHei", 12, "bold"),
        ).pack(anchor="w", padx=10, pady=(10, 4))
        tk.Label(
            scroll_frame,
            text=f"类型: {backend_node.NODE_CATEGORY} | 原始约束调整固定设计值 | 结果约束调整校核阈值",
            bg=self._bg,
            fg="#888",
            font=("Microsoft YaHei", 8),
        ).pack(anchor="w", padx=10)

        # ── 原始约束 (所有 fixed 参数 + 离散值 free 参数) ──
        if fixed or free:
            self._build_section_header(scroll_frame, "原始约束 (固定设计参数)")
            # 1. fixed 参数
            for param_key in fixed:
                current_val = fixed[param_key]
                allowed_vals = free.get(param_key, None)
                display_name = self._param_key_to_name(param_key)
                unit = self._param_key_to_unit(param_key)
                self._build_original_row(
                    scroll_frame,
                    display_name,
                    param_key,
                    current_val,
                    allowed_vals,
                    unit,
                )
            # 2. 离散值 free 参数(如巴氏计量槽喉宽 b)
            shown = set(fixed.keys())
            for param_key in free:
                if param_key in shown:
                    continue
                vals = free[param_key]
                # ── 使用原始值列表显示(避免收缩后选项变少)──
                display_vals = self._original_free.get(param_key, vals)
                if isinstance(vals, list) and len(vals) > 0:
                    display_name = self._param_key_to_name(param_key)
                    unit = self._param_key_to_unit(param_key)
                    self._build_original_row(
                        scroll_frame,
                        display_name,
                        param_key,
                        vals[0],
                        display_vals,
                        unit,
                    )

        # ── 结果约束 (校核阈值) ──
        if result_names:
            self._build_section_header(scroll_frame, "结果约束 (校核阈值)")
            for name in result_names:
                self._build_result_row(scroll_frame, name, constraint_limits)

        # ── 递归滚轮绑定 ──
        def _bind_wheel(widget, canvas_ref):
            widget.bind(
                "<MouseWheel>",
                lambda e: canvas_ref.yview_scroll(int(-e.delta / 120), "units"),
            )
            for child in widget.winfo_children():
                _bind_wheel(child, canvas_ref)

        _bind_wheel(scroll_frame, canvas)

    def _clear(self) -> None:
        """清除所有子组件,保留 _empty_label 用于空状态提示"""
        self._empty_label.pack_forget()
        for w in list(self.winfo_children()):
            if w is not self._empty_label:
                w.destroy()
        self._confirm_buttons.clear()
        self._applied_states.clear()
        self._original_entries.clear()
        self._result_entries.clear()
        self._original_free.clear()
        self._node_type = None

    # ═══════════════ 面板显示 ═══════════════
    def _show_empty(self, msg: str) -> None:
        """显示空状态提示,安全处理已销毁的 label"""
        try:
            self._empty_label.config(text=msg)
        except tk.TclError:
            # widget 已被外部销毁,重建
            self._empty_label = tk.Label(
                self,
                text=msg,
                bg=self._bg,
                fg="#888",
                font=("Microsoft YaHei", 10),
            )
        self._empty_label.pack(pady=40)

    # ═══════════════ UI 构建 ═══════════════
    def _build_section_header(self, parent, text: str) -> None:
        """构建分区标题"""
        sep = tk.Frame(parent, bg="#444", height=1)
        sep.pack(fill=tk.X, padx=8, pady=(10, 4))
        tk.Label(
            parent,
            text=f"── {text} ──",
            bg=self._bg,
            fg="#ffaa44",
            font=("Microsoft YaHei", 9, "bold"),
        ).pack(anchor="w", padx=10, pady=(0, 4))

    def _build_original_row(
        self,
        parent,
        display_name: str,
        param_key: str,
        current_val: float,
        allowed_vals=None,
        unit: str = "",
    ) -> None:
        """构建原始约束行: 名称 | 输入框/下拉框 | [确定]

        Args:
            display_name: 中文显示名
            param_key: fixed 字典中的键名
            current_val: 当前值 (config 默认值)
            allowed_vals: 离散允许值列表 (来自 free), None=自由输入
            unit: 单位字符串
        """
        # 如果有已应用方案的参数, 使用方案值覆盖 config 默认值
        if self._applied_params and param_key in self._applied_params:
            current_val = self._applied_params[param_key]
        row = tk.Frame(parent, bg="#2d2d2d", bd=1, relief=tk.GROOVE)
        row.pack(fill=tk.X, padx=6, pady=1)

        # 名称
        tk.Label(
            row,
            text=f" {display_name}",
            bg="#2d2d2d",
            fg="#ccc",
            font=("Microsoft YaHei", 9, "bold"),
            width=22,
            anchor="w",
        ).pack(side=tk.LEFT, padx=4)

        if allowed_vals and len(allowed_vals) > 0:
            # ── 离散值: 使用 Combobox 下拉选择 ──
            sv = tk.StringVar(value=str(current_val))
            cb = ttk.Combobox(
                row,
                values=[str(v) for v in allowed_vals],
                textvariable=sv,
                state="readonly",
                width=12,
            )
            cb.pack(side=tk.LEFT, padx=2)
            cb.bind(
                "<<ComboboxSelected>>",
                lambda e, k=param_key: self._on_original_dirty(k),
            )
            self._original_entries[param_key] = {
                "sv": sv,
                "widget": cb,
                "is_combo": True,
            }
        else:
            # ── 自由值: 使用 Entry 输入 ──
            sv = tk.StringVar(value=str(current_val))
            entry = tk.Entry(
                row,
                textvariable=sv,
                width=10,
                bg="#1a1a1a",
                fg="#ffaa44",
                insertbackground="#fff",
                font=("Consolas", 9),
                justify=tk.RIGHT,
            )
            entry.pack(side=tk.LEFT, padx=2)
            sv.trace_add(
                "write", lambda name, idx, mode, k=param_key: self._on_original_dirty(k)
            )
            self._original_entries[param_key] = {
                "sv": sv,
                "widget": entry,
                "is_combo": False,
            }

        # 单位
        if unit:
            tk.Label(
                row, text=unit, bg="#2d2d2d", fg="#888", font=("Microsoft YaHei", 8)
            ).pack(side=tk.LEFT)

        # 确定按钮 — 初始绿色 (约束已应用)
        btn_key = f"original_{param_key}"
        self._applied_states[btn_key] = True
        btn = tk.Button(
            row,
            text="确定",
            bg="#55cc55",
            fg="#fff",
            font=("Microsoft YaHei", 8),
            relief=tk.FLAT,
            width=5,
            height=1,
            command=lambda k=param_key, sv=sv: self._on_original_confirm(k, sv),
        )
        btn.pack(side=tk.RIGHT, padx=4)
        self._confirm_buttons[btn_key] = btn

    def _build_result_row(
        self, parent, name: str, constraint_limits: Dict[str, str]
    ) -> None:
        """构建结果约束行: 名称 | 下限输入框 | ~ | 上限输入框 | [确定]"""
        row = tk.Frame(parent, bg="#2d2d2d", bd=1, relief=tk.GROOVE)
        row.pack(fill=tk.X, padx=6, pady=1)

        # 名称
        tk.Label(
            row,
            text=f" {name}",
            bg="#2d2d2d",
            fg="#ccc",
            font=("Microsoft YaHei", 9, "bold"),
            width=24,
            anchor="w",
        ).pack(side=tk.LEFT, padx=4)

        # 解析当前限制值
        limit_str = constraint_limits.get(name, "")
        lo_val, hi_val = self._parse_limit(limit_str)

        # 下限
        lo_sv = tk.StringVar(value=str(lo_val) if lo_val is not None else "")
        lo_entry = tk.Entry(
            row,
            textvariable=lo_sv,
            width=6,
            bg="#1a1a1a",
            fg="#55cc55",
            insertbackground="#fff",
            font=("Consolas", 9),
            justify=tk.RIGHT,
        )
        lo_entry.pack(side=tk.LEFT, padx=1)
        tk.Label(
            row, text="下限", bg="#2d2d2d", fg="#888", font=("Microsoft YaHei", 7)
        ).pack(side=tk.LEFT, padx=1)

        # 分隔符
        tk.Label(row, text="~", bg="#2d2d2d", fg="#aaa", font=("Consolas", 10)).pack(
            side=tk.LEFT, padx=3
        )

        # 上限
        hi_sv = tk.StringVar(value=str(hi_val) if hi_val is not None else "")
        hi_entry = tk.Entry(
            row,
            textvariable=hi_sv,
            width=6,
            bg="#1a1a1a",
            fg="#ff9955",
            insertbackground="#fff",
            font=("Consolas", 9),
            justify=tk.RIGHT,
        )
        hi_entry.pack(side=tk.LEFT, padx=1)
        tk.Label(
            row, text="上限", bg="#2d2d2d", fg="#888", font=("Microsoft YaHei", 7)
        ).pack(side=tk.LEFT, padx=1)

        # 确定按钮 — 初始绿色 (约束已应用)
        btn_key = f"result_{name}"
        self._applied_states[btn_key] = True
        btn = tk.Button(
            row,
            text="确定",
            bg="#55cc55",
            fg="#fff",
            font=("Microsoft YaHei", 8),
            relief=tk.FLAT,
            width=5,
            height=1,
            command=lambda n=name, ls=lo_sv, hs=hi_sv: self._on_result_confirm(
                n, ls, hs
            ),
        )
        btn.pack(side=tk.RIGHT, padx=4)
        self._confirm_buttons[btn_key] = btn
        self._result_entries[name] = {
            "lo_entry": lo_entry,
            "lo_sv": lo_sv,
            "hi_entry": hi_entry,
            "hi_sv": hi_sv,
        }
        # 绑定输入变化 → 标记为dirty
        lo_sv.trace_add("write", lambda n, i, m, b=btn_key: self._on_result_dirty(b))
        hi_sv.trace_add("write", lambda n, i, m, b=btn_key: self._on_result_dirty(b))

    # ── 事件处理 ──

    # ═══════════════ 事件回调 ═══════════════
    def _on_original_dirty(self, param_key: str) -> None:
        """原始约束输入变化 → 标记为dirty (按钮变灰)"""
        btn_key = f"original_{param_key}"
        self._applied_states[btn_key] = False
        btn = self._confirm_buttons.get(btn_key)
        if btn:
            btn.config(bg="#555555")

    def _on_result_dirty(self, btn_key: str) -> None:
        """结果约束输入变化 → 标记为dirty (按钮变灰)"""
        self._applied_states[btn_key] = False
        btn = self._confirm_buttons.get(btn_key)
        if btn:
            btn.config(bg="#555555")

    # ═══════════════ 设置 ═══════════════
    def _set_applied(self, btn_key: str) -> None:
        """标记约束为已应用 (按钮变绿)"""
        self._applied_states[btn_key] = True
        btn = self._confirm_buttons.get(btn_key)
        if btn:
            btn.config(bg="#55cc55")

    # ═══════════════ 事件回调 ═══════════════
    def _on_original_confirm(self, param_key: str, sv: tk.StringVar) -> None:
        """原始约束"确定"按钮回调 — 更新 fixed 或 free 参数值"""
        if not self._node_type:
            return
        try:
            val = float(sv.get())
        except (ValueError, tk.TclError):
            return

        try:
            from models.discretization import get_config

            cfg = get_config(self._node_type)
            # fixed 参数: 直接更新标量值
            if param_key in cfg.get("fixed", {}):
                cfg["fixed"][param_key] = val
                # ── 自动同步 constraint_limits ──
                # 当 fixed 参数本身是约束边界时 (如 v_force),
                # 自动更新对应的 constraint_limits,防止动态检查误杀方案
                self._sync_param_to_constraint(param_key, val, cfg)
            # free 参数: 确保值在允许列表中
            elif param_key in cfg.get("free", {}):
                allowed = cfg["free"][param_key]
                if isinstance(allowed, list):
                    if val not in allowed:
                        val = allowed[0]  # 回退到第一个值
                    cfg["free"][param_key] = [val]  # 收缩为单值
                # ── 自动同步 constraint_limits ──
                # 当 free 参数值超出对应约束范围时 (如 HRT),
                # 自动展开约束限值,防止方案被误杀
                self._sync_param_to_constraint(param_key, val, cfg)
        except (KeyError, ImportError):
            pass

        self._set_applied(f"original_{param_key}")
        self._notify_change()
        self._persist_config()

    # ═══════════════ 同步 ═══════════════
    def _sync_param_to_constraint(self, param_key: str, val: float, cfg: dict) -> bool:
        """当参数改变时,同步更新对应的 constraint_limits

        Returns:
            True 如果 constraint_limits 被修改(需要刷新显示)
        """
        sync_map = self._PARAM_SYNC_MAP.get(param_key, {})
        sync_info = sync_map.get(self._node_type)
        if not sync_info:
            return False
        constraint_name, rule = sync_info

        if "constraint_limits" not in cfg:
            cfg["constraint_limits"] = {}
        old_limit = cfg["constraint_limits"].get(constraint_name, "")

        if rule == "<= {val}":
            # 直接替换(v_force 等)
            new_limit = rule.format(val=val)
            if new_limit == old_limit:
                return False
            cfg["constraint_limits"][constraint_name] = new_limit
        elif rule == "lower":
            # 展开下限以包含 val(HRT 等)
            lo, hi = self._parse_limit(old_limit)
            new_lo = min(lo, val) if lo is not None else val
            if lo is not None and new_lo == lo:
                return False
            new_limit = f"{new_lo}~{hi}" if hi is not None else f">= {new_lo}"
            cfg["constraint_limits"][constraint_name] = new_limit
        elif rule == "expand":
            # 展开上下限以包含 val(G_mix, G_floc 等)
            lo, hi = self._parse_limit(old_limit)
            new_lo = min(lo, val) if lo is not None else val
            new_hi = max(hi, val) if hi is not None else val
            if lo is not None and hi is not None and new_lo == lo and new_hi == hi:
                return False
            new_limit = f"{new_lo}~{new_hi}"
            cfg["constraint_limits"][constraint_name] = new_limit
        else:
            return False

        # 通知 solution_space 的运行时覆盖表
        try:
            from models.solution_space import set_constraint_limits

            set_constraint_limits(
                self._node_type,
                {
                    constraint_name: new_limit,
                },
            )
        except ImportError:
            pass

        # ── 实时刷新结果约束行的显示 ──
        self._update_result_display(constraint_name, new_limit)
        return True

    def _update_result_display(self, constraint_name: str, limit_str: str) -> None:
        """实时更新指定结果约束行的输入框显示值

        当参数同步修改了 constraint_limits 后调用,无需重新加载整个面板.
        """
        entry_info = self._result_entries.get(constraint_name)
        if not entry_info:
            return

        lo_val, hi_val = self._parse_limit(limit_str)

        lo_sv = entry_info.get("lo_sv")
        if lo_sv is not None:
            try:
                lo_sv.set(str(lo_val) if lo_val is not None else "")
            except tk.TclError:
                pass

        hi_sv = entry_info.get("hi_sv")
        if hi_sv is not None:
            try:
                hi_sv.set(str(hi_val) if hi_val is not None else "")
            except tk.TclError:
                pass

        # 标记为已应用状态(绿色按钮)
        btn_key = f"result_{constraint_name}"
        self._set_applied(btn_key)

    # ═══════════════ 事件回调 ═══════════════
    def _on_result_confirm(
        self, name: str, lo_sv: tk.StringVar, hi_sv: tk.StringVar
    ) -> None:
        """结果约束"确定"按钮回调"""
        if not self._node_type:
            return

        lo_str = lo_sv.get().strip()
        hi_str = hi_sv.get().strip()

        # 组装 constraint_limits 格式
        has_lo = len(lo_str) > 0
        has_hi = len(hi_str) > 0

        if has_lo and has_hi:
            limit_str = f"{lo_str}~{hi_str}"
        elif has_hi:
            limit_str = f"<= {hi_str}"
        elif has_lo:
            limit_str = f">= {lo_str}"
        else:
            return

        # 更新 constraint_limits
        try:
            from models.discretization import get_config

            cfg = get_config(self._node_type)
            if "constraint_limits" not in cfg:
                cfg["constraint_limits"] = {}
            cfg["constraint_limits"][name] = limit_str
        except (KeyError, ImportError):
            pass

        # 通知 solution_space 更新
        try:
            from models.solution_space import set_constraint_limits

            set_constraint_limits(
                self._node_type,
                {
                    name: limit_str,
                },
            )
        except ImportError:
            pass

        self._set_applied(f"result_{name}")
        self._notify_change()
        self._persist_config()

    def _persist_config(self) -> None:
        """将当前约束配置持久化到模组的 discretization.json

        写入策略(原子写入):
        1. 写入临时文件 → 重命名(防止写入中断导致 JSON 损坏)
        2. 同时同步到 mods/ (测试) 和 ddesign_tool/mods/ (运行时) 两处
        3. 失败时记录日志,不阻塞 UI
        """
        if not self._node_type:
            return
        try:
            import json

            from models.discretization import get_config

            from mods.mod_manager import get_mod_manager

            cfg = get_config(self._node_type)
            mgr = get_mod_manager()
            mod_info = mgr.get_mod_by_node_type(self._node_type)
            if not mod_info or not mod_info.mod_dir:
                _log.warning("_persist_config: no mod_dir for %s", self._node_type)
                return

            save_data = {
                "free": (
                    self._original_free if self._original_free else cfg.get("free", {})
                ),
                "fixed": cfg.get("fixed", {}),
                "constraint_keys": cfg.get("constraint_keys", []),
                "constraint_names": cfg.get("constraint_names", []),
                "constraint_limits": cfg.get("constraint_limits", {}),
                "constraint_types": cfg.get("constraint_types", {}),
                "display_name": cfg.get("display_name", ""),
            }
            if "estimator_type" in cfg:
                save_data["estimator_type"] = cfg["estimator_type"]

            json_text = json.dumps(save_data, ensure_ascii=False, indent=2) + "\n"

            # ── 通过 ModManager 统一写入 (同时同步运行时+测试目录) ──
            success = mgr.save_discretization(mod_info.id, save_data)
            if not success:
                _log.warning("_persist_config: failed to save for %s", self._node_type)

        except Exception as e:
            _log.warning("_persist_config: unexpected error: %s", e)

    def _notify_change(self) -> None:
        """通知主窗口约束已变更"""
        if self._on_constraint_changed and self._node_type:
            self._on_constraint_changed(self._node_type)

    # ── 辅助方法 ──

    _KEY_NAME_MAP = {
        # fixed 参数
        "h_super": "超高",
        "P_density": "搅拌功率密度",
        "h1": "超高 h1",
        "h3": "缓冲层 h3",
        "i_slope": "池底坡度",
        "R1": "泥斗上口半径",
        "R2": "泥斗下口半径",
        "h5": "泥斗高度",
        "P_sludge": "污泥含水率",
        "T_sludge": "排泥周期",
        "v_center": "中心管流速",
        "v": "过栅流速 v",
        "v1": "栅前流速 v1",
        "s": "栅条宽度 s",
        "X": "沉砂量系数 X",
        "T_clean": "清砂间隔",
        "theta": "砂斗倾角",
        "dr": "排沙口直径",
        "f": "MLVSS/MLSS",
        "Y": "产率系数 Y",
        "Kd20": "衰减系数 Kd20",
        "theta_t": "温度系数",
        "T_design": "设计水温",
        "r_selector": "选择区比例",
        "SVI": "污泥体积指数",
        "delta_H_safe": "安全距离",
        "a_prime": "碳化需氧系数",
        "b_prime": "内源呼吸系数",
        "t_d": "滗水时间",
        "R_sludge": "污泥回流比",
        "L_tube": "斜管长度",
        "alpha_tube": "斜管倾角",
        "h_clear": "清水区高度",
        "h_dist": "配水区高度",
        "t_thicken": "浓缩时间",
        "P_out": "出泥含水率",
        "D_PAC": "PAC投加量",
        "k_PAC": "PAC产泥系数",
        "v_force": "强制滤速限值",
        "T_filter": "过滤周期",
        "k_self": "自用水系数",
        "h_plate": "滤板厚度",
        "h_under": "配水区高度",
        "rho_head": "滤头密度",
        "k_aging": "老化系数",
        "k_foul": "结垢系数",
        "T254": "紫外透光率",
        "n_T": "透光率指数",
        "eta_geo": "几何效率",
        "L_lamp": "灯管长度",
        "gap": "灯管间隙",
        "N_layer": "灯管层数",
        "d_vert": "垂直间距",
        "d_long": "纵向间距",
        "P_lamp": "灯管功率",
        "L_in": "进水区长度",
        "L_out": "出水区长度",
        "xi_total": "总阻力系数",
        "slope": "池底坡度",
        "hopper_angle": "砂斗倾角",
        "hopper_bottom": "砂斗下口宽",
        "PAC_dose": "PAC投加量",
        "PAM_dose": "PAM投加量",
        "field_strength": "磁场强度",
        "recovery_rate": "回收率",
        "magnetic_seed": "磁种投加量",
        "t_backwash": "反冲洗时间",
        "backwash_intensity": "反冲洗强度",
        "H_pump": "泵扬程",
        "T_digest": "消化温度",
        "dosage_PAM": "PAM投加量",
        "T_air": "热风温度",
        "eta_pump": "泵效率",
        "t_sump_min": "集水池停留",
        "h_outlet": "出水自由水头",
        "h_sump_eff": "集水池水深",
        "k_local": "局部损失系数",
        "n_rough": "粗糙系数",
        "L_suction": "吸水管长",
        "L_discharge": "出水管长",
        # free 参数 (离散值)
        "n": "数量",
        "b": "喉管宽度 b",
        "n_pumps": "泵台数",
        "Q_pump": "单泵流量",
        "v_pipe": "管道流速",
        "q_solid": "固体负荷",
        "T_thicken": "浓缩时间",
        "theta_digest": "消化时间",
        "eta_VS": "VS去除率",
        "biogas_rate": "沼气产率",
        "equip_type": "设备类型",
        "n_machines": "设备台数",
        "q_capacity": "处理能力",
        "method": "干化方式",
        "q_evap": "蒸发速率",
        "eta_thermal": "热效率",
    }

    @classmethod
    def _param_key_to_name(cls, key: str) -> str:
        """将 fixed 参数键名转为中文显示名"""
        return cls._KEY_NAME_MAP.get(key, key)

    @classmethod
    def _param_key_to_unit(cls, key: str) -> str:
        """返回参数的单位"""
        unit_map = {
            "h_super": "m",
            "h1": "m",
            "h3": "m",
            "h5": "m",
            "h_clear": "m",
            "h_dist": "m",
            "h_plate": "m",
            "h_under": "m",
            "L_lamp": "m",
            "L_in": "m",
            "L_out": "m",
            "L_suction": "m",
            "L_discharge": "m",
            "gap": "m",
            "d_vert": "m",
            "d_long": "m",
            "h_outlet": "m",
            "h_sump_eff": "m",
            "v": "m/s",
            "v1": "m/s",
            "v_center": "m/s",
            "s": "mm",
            "dr": "m",
            "R1": "m",
            "R2": "m",
            "i_slope": "",
            "slope": "",
            "alpha_tube": "°",
            "theta": "°",
            "hopper_angle": "°",
            "P_density": "W/m³",
            "t_thicken": "h",
            "T_filter": "h",
            "t_backwash": "min",
            "t_d": "h",
            "T_sludge": "h",
            "T_thicken": "h",
            "T_design": "°C",
            "T_digest": "°C",
            "T_air": "°C",
            "t_sump_min": "min",
            "D_PAC": "mg/L",
            "PAC_dose": "mg/L",
            "PAM_dose": "mg/L",
            "dosage_PAM": "kg/tDS",
            "magnetic_seed": "mg/L",
            "P_lamp": "W",
            "H_pump": "m",
            "P_out": "",
            "P_sludge": "",
            "T254": "%",
            "k_aging": "",
            "k_foul": "",
            "eta_geo": "",
            "k_PAC": "",
            "k_self": "",
            "k_local": "",
            "n_rough": "",
            "rho_head": "个/m²",
            "recovery_rate": "",
            "backwash_intensity": "L/(m²·s)",
            "field_strength": "T",
            "X": "m³/10⁶m³",
            "T_clean": "d",
            "SVI": "mL/g",
        }
        return unit_map.get(key, "")

    # ── 参数→约束自动同步映射 ──
    # 当用户修改这些参数时,自动更新对应的 constraint_limits
    # 格式: {param_key: {node_type: (constraint_display_name, sync_rule)}}
    #
    # sync_rule 类型:
    #   "<= {val}"     — 直接替换限值为格式化字符串 (用于 fixed 参数即边界值)
    #   "lower"        — 展开下限以包含参数值 (用于 free 参数如 HRT)
    #   "expand"       — 展开上下限以包含参数值 (用于 fixed 参数如 G_mix)
    _PARAM_SYNC_MAP: dict = {
        # ── fixed 参数即约束边界 ──
        "v_force": {
            "vxinglvchi": ("强制滤速 v_q ≤ 限值", "<= {val}"),
            "kw_vxinglvchi": ("强制滤速 v_q <= 限值", "<= {val}"),
        },
        "G_mix": {
            "gaomidu": ("混合区 G_mix 500~1000 s⁻¹", "expand"),
            "kw_gaomidu": ("混合区 G_mix 500~1000 s⁻¹", "expand"),
        },
        "G_floc": {
            "gaomidu": ("絮凝区 G_floc 50~100 s⁻¹", "expand"),
            "kw_gaomidu": ("絮凝区 G_floc 50~100 s⁻¹", "expand"),
        },
        # ── free 参数影响约束下限 ──
        "HRT": {
            "tiaojiechi": ("实际 HRT", "lower"),
            "kw_tiaojiechi": ("实际 HRT", "lower"),
        },
    }

    def _parse_limit(self, limit_str: str) -> tuple:
        """解析约束限值字符串 → (lower, upper)

        "2.0~2.5" → (2.0, 2.5)
        "<= 0.3" → (None, 0.3)
        ">= 16" → (16, None)
        "> 0" → (0, None)
        """
        limit_str = limit_str.strip()
        if not limit_str:
            return (None, None)

        # Two-sided
        if "~" in limit_str:
            parts = limit_str.replace(" ", "").split("~")
            try:
                return (float(parts[0]), float(parts[1]))
            except ValueError:
                pass

        # One-sided upper
        for prefix in ["<=", "<"]:
            if limit_str.startswith(prefix):
                try:
                    return (None, float(limit_str[len(prefix) :].strip()))
                except ValueError:
                    pass

        # One-sided lower
        for prefix in [">=", ">"]:
            if limit_str.startswith(prefix):
                try:
                    return (float(limit_str[len(prefix) :].strip()), None)
                except ValueError:
                    pass

        return (None, None)
