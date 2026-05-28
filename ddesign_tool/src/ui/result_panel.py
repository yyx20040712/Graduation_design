"""
result_panel.py — 结果面板组件 (v5.4 extracted from main_window.py)

管理结果 Tab (4列 Treeview) + 高程 Tab 的 UI 和数据填充。
"""
from __future__ import annotations

import re
import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict, Optional

from _logging import get_logger

_log = get_logger(__name__)


# ── 模块级常量: Treeview 标签名 (用于自检脚本的运行时验证, 替代源码 grep) ──
RESULT_TREE_TAGS = frozenset({
    "section_banner",   # 章节标题 — 整行居中深灰底色横幅
    "formula_sub",      # 公式子行 — 浅色斜体
    "check_pass",       # 约束校核通过 — 绿色
    "check_fail",       # 约束校核失败 — 红色
    "row_odd",          # 奇数行背景
    "row_even",         # 偶数行背景
    "param",            # 原始设计参数行
    "dimension",        # 维度数据行
})


class ResultPanel:
    """结果面板 — 管理计算结果 Treeview 和高程面板。

    从 MainWindow 中分离, 通过 getter/setter 与主窗口通信。
    """

    def __init__(
        self,
        parent_frame: tk.Frame,
        executor,
        get_selected_id: Callable[[], Optional[str]],
        get_node_items: Callable[[], Dict],
        status_var: tk.StringVar,
        tab_var: tk.StringVar,
        get_solution_browser: Callable[[], Optional[object]],
        on_refresh_params: Callable[[], None],
        quality_panel_getter: Callable[[], object],
        constraint_panel_getter: Callable[[], object],
        params_frame: tk.Frame,
        quality_text: tk.Frame,
        constraint_frame: tk.Frame,
    ):
        self._executor = executor
        self._get_selected_id = get_selected_id
        self._get_node_items = get_node_items
        self._status_var = status_var
        self._tab_var = tab_var
        self._get_solution_browser = get_solution_browser
        self._on_refresh_params = on_refresh_params
        self._get_quality_panel = quality_panel_getter
        self._get_constraint_panel = constraint_panel_getter
        self._params_frame = params_frame
        self._quality_text = quality_text
        self._constraint_frame = constraint_frame

        self._build_result_frame(parent_frame)
        self._build_elevation_frame(parent_frame)

    # ── Public API ──────────────────────────────────────────────

    @property
    def result_frame(self) -> tk.Frame:
        return self._result_frame

    @property
    def elevation_frame(self) -> tk.Frame:
        return self._elevation_frame

    def show_node(self, backend, solution_browser=None) -> None:
        """显示指定节点的计算结果。"""
        self._populate_result_tree(backend)
        self._result_frame.pack(
            side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5
        )

    def refresh(self) -> None:
        """刷新当前选中节点的结果显示 (4列 Treeview)。"""
        selected_id = self._get_selected_id()
        node_items = self._get_node_items()
        if selected_id and selected_id in node_items:
            be = node_items[selected_id].backend
            if be:
                self._populate_result_tree(be)
                return
        # 无选中节点
        for item in self._tree.get_children():
            self._tree.delete(item)
        self._check_text.configure(state=tk.NORMAL)
        self._check_text.delete("1.0", tk.END)
        self._check_text.configure(state=tk.DISABLED)
        self._tree.insert(
            "",
            tk.END,
            values=("←", "点击节点查看计算结果", "", ""),
            tags=("hint",),
        )

    def clear(self) -> None:
        """清除所有结果展示。"""
        for item in self._tree.get_children():
            self._tree.delete(item)
        self._check_text.configure(state=tk.NORMAL)
        self._check_text.delete("1.0", tk.END)
        self._check_text.configure(state=tk.DISABLED)

    def view_results(self) -> None:
        """切换到结果 tab 查看当前节点计算结果。"""
        self._status_var.set("参数已修改,按 F5 重新计算")
        self._tab_var.set("results")

    def refresh_elevation(self) -> None:
        """刷新高程面板。"""
        self._refresh_elevation_view()

    # ── Tab 切换 ────────────────────────────────────────────────

    def _on_tab_changed(self) -> None:
        """Tab 切换回调 (从 main_window 的 radiobutton 触发)。"""
        self._params_frame.pack_forget()
        self._result_frame.pack_forget()
        self._quality_text.pack_forget()
        self._constraint_frame.pack_forget()
        self._elevation_frame.pack_forget()
        sb = self._get_solution_browser()
        if sb:
            sb.pack_forget()
        tab = self._tab_var.get()
        if tab == "params":
            self._on_refresh_params()
        elif tab == "results":
            self.refresh()
            self._params_frame.pack_forget()
            sb = self._get_solution_browser()
            if sb:
                sb.pack_forget()
            self._result_frame.pack(
                side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5
            )
        elif tab == "quality":
            self._params_frame.pack_forget()
            sb = self._get_solution_browser()
            if sb:
                sb.pack_forget()
            self._quality_text.pack(
                side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5
            )
            selected_id = self._get_selected_id()
            node_items = self._get_node_items()
            if selected_id and selected_id in node_items:
                be = node_items[selected_id].backend
                if be:
                    from models.node_registry import is_water_quality_node

                    if is_water_quality_node(be.NODE_TYPE):
                        self._get_quality_panel().show_water_quality_card(be)
                    else:
                        self._get_quality_panel().build_full_quality_flow(
                            scroll_to_node_id=selected_id
                        )
            else:
                self._get_quality_panel().build_full_quality_flow()
        elif tab == "constraints":
            self._constraint_frame.pack(
                side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5
            )
            selected_id = self._get_selected_id()
            node_items = self._get_node_items()
            if selected_id and selected_id in node_items:
                be = node_items[selected_id].backend
                if be:
                    applied = (
                        be.result.params if be.result and be.result.success else None
                    )
                    self._get_constraint_panel().load_node(be, applied)
        elif tab == "elevation":
            self._elevation_frame.pack(
                side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5
            )
            self._refresh_elevation_view()

    # ═══════════════════ UI 构建 ═══════════════════

    def _build_result_frame(self, parent: tk.Frame) -> None:
        """构建结果面板 (4列 Treeview + 约束校核 Text)。"""
        self._result_frame = tk.Frame(parent, bg="#1a1a1a")
        # 容器 frame 实现双向滚动
        self._container = tk.Frame(self._result_frame, bg="#1a1a1a")
        self._container.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self._tree = ttk.Treeview(
            self._container,
            columns=("symbol", "meaning", "unit", "value"),
            show="headings",
            height=18,
        )
        self._tree.heading("symbol", text="符号")
        self._tree.heading("meaning", text="物理意义 / 计算公式")
        self._tree.heading("unit", text="单位")
        self._tree.heading("value", text="取值")
        self._tree.column("symbol", width=75, anchor="center", stretch=False)
        self._tree.column("meaning", width=140, anchor="w")
        self._tree.column("unit", width=55, anchor="center", stretch=False)
        self._tree.column("value", width=110, anchor="e", stretch=False)
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
            "原始参数": ("#0d3b66", "#66aaff"),
            "构筑物尺寸": ("#1a3d2e", "#55cc88"),
            "计算结果": ("#3d1a4a", "#cc88ff"),
            "约束校核": ("#4a2a1a", "#ff9966"),
            "进水水质": ("#0d3b66", "#66aaff"),
            "出水水质": ("#1a3d2e", "#55cc88"),
            "去除率": ("#3d1a4a", "#cc88ff"),
        }
        for name, (bg, fg) in SECTION_STYLES.items():
            self._tree.tag_configure(
                f"header_{name}",
                background=bg,
                foreground=fg,
                font=("Microsoft YaHei", 10, "bold"),
            )
        # 参数分类标题行 — 彩色区分 basic/physical/operating
        self._tree.tag_configure(
            "cat_basic",
            background="#0d3b66",
            foreground="#66aaff",
            font=("Microsoft YaHei", 10, "bold"),
        )
        self._tree.tag_configure(
            "cat_physical",
            background="#1a3d2e",
            foreground="#55cc88",
            font=("Microsoft YaHei", 10, "bold"),
        )
        self._tree.tag_configure(
            "cat_operating",
            background="#3d1a4a",
            foreground="#cc88ff",
            font=("Microsoft YaHei", 10, "bold"),
        )
        # 交替行背景
        self._tree.tag_configure("row_odd", background="#1e1e1e")
        self._tree.tag_configure("row_even", background="#252525")
        # 章节标题 — 整行居中横幅
        self._tree.tag_configure(
            "section_banner",
            background="#2d2d2d",
            foreground="#ffaa44",
            font=("Microsoft YaHei", 10, "bold"),
            anchor="center",
        )
        # 公式子行 — 浅色斜体
        self._tree.tag_configure(
            "formula_sub",
            foreground="#888888",
            font=("Microsoft YaHei", 8, "italic"),
        )
        # 约束校核行 — 通过/失败 颜色区分
        self._tree.tag_configure(
            "check_pass",
            foreground="#55cc88",
            font=("Microsoft YaHei", 9),
        )
        self._tree.tag_configure(
            "check_fail",
            foreground="#ff5555",
            font=("Microsoft YaHei", 9),
        )
        # 纵向滚动条
        self._scroll_y = ttk.Scrollbar(
            self._container, orient=tk.VERTICAL, command=self._tree.yview
        )
        # 横向滚动条
        self._scroll_x = ttk.Scrollbar(
            self._result_frame, orient=tk.HORIZONTAL, command=self._tree.xview
        )
        self._tree.configure(
            yscrollcommand=self._scroll_y.set,
            xscrollcommand=self._scroll_x.set,
        )
        self._tree.grid(row=0, column=0, sticky="nsew")
        self._scroll_y.grid(row=0, column=1, sticky="ns")
        self._container.grid_rowconfigure(0, weight=1)
        self._container.grid_columnconfigure(0, weight=1)
        self._scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        # 约束校核区域 (Treeview 下方)
        self._check_text = tk.Text(
            self._result_frame,
            bg="#1a1a1a",
            fg="#ccc",
            font=("Consolas", 9),
            wrap=tk.WORD,
            relief=tk.FLAT,
            borderwidth=0,
            height=6,
        )
        self._check_text.pack(side=tk.BOTTOM, fill=tk.X)

    def _build_elevation_frame(self, parent: tk.Frame) -> None:
        """构建高程面板 frame (容器)。"""
        self._elevation_frame = tk.Frame(parent, bg="#1a1a1a")
        self._build_elevation_view()

    # ═══════════════════ 数据填充 ═══════════════════

    def _populate_result_tree(self, backend) -> None:
        """将节点计算结果填充到 4 列 Treeview: 符号 | 物理意义 | 单位 | 取值."""
        for item in self._tree.get_children():
            self._tree.delete(item)

        node = backend
        result = node.result
        if not result or not result.success:
            self._tree.insert(
                "",
                tk.END,
                values=("✗", "计算失败", "", result.error_msg if result else ""),
            )
            self._check_text.configure(state=tk.NORMAL)
            self._check_text.delete("1.0", tk.END)
            self._check_text.configure(state=tk.DISABLED)
            return

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
            self._tree.insert(
                "",
                tk.END,
                values=("", "── 原始设计参数 ──", "", ""),
                tags=("section_banner",),
            )
            for sym, meaning, unit, val_str in param_items:
                self._tree.insert(
                    "",
                    tk.END,
                    values=(sym, meaning, unit, val_str),
                    tags=("param",),
                )

        # ── 2. 计算结果 (不含水质) ──
        if computed:
            self._tree.insert(
                "",
                tk.END,
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
                self._tree.insert(
                    "", tk.END, values=(sym, meaning, unit, self._fmt_val(val))
                )
                formula = result.dimension_formulas.get(key, "")
                if formula:
                    self._tree.insert(
                        "",
                        tk.END,
                        values=("", f"↳ {formula}", "", ""),
                        tags=("formula_sub",),
                    )

        # ── 3. 构筑物尺寸 ──
        if physical:
            self._tree.insert(
                "",
                tk.END,
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
                self._tree.insert(
                    "", tk.END, values=(sym, meaning, unit, self._fmt_val(val))
                )
                formula = result.dimension_formulas.get(key, "")
                if formula:
                    self._tree.insert(
                        "",
                        tk.END,
                        values=("", f"↳ {formula}", "", ""),
                        tags=("formula_sub",),
                    )

        # ── 4. 约束校核 (仅底部 Text 窗口) ──
        self._check_text.configure(state=tk.NORMAL)
        self._check_text.delete("1.0", tk.END)
        if result.warnings:
            self._check_text.insert(tk.END, "⚠ 警告:\n", ("bold",))
            for w in result.warnings:
                self._check_text.insert(tk.END, f"  • {w}\n")
            self._check_text.insert(tk.END, "\n")
        if result.checks:
            self._check_text.insert(tk.END, "约束校核:\n", ("bold",))
            for check_name, (passed, actual, limit, unit) in result.checks.items():
                icon = "✓" if passed else "✗"
                tag_name = "check_pass" if passed else "check_fail"
                self._check_text.tag_configure(
                    tag_name, foreground="#55cc88" if passed else "#ff5555"
                )
                self._check_text.insert(
                    tk.END, f"  [{icon}] {check_name}: ", (tag_name,)
                )
                self._check_text.insert(
                    tk.END,
                    f"{actual:.2f}{unit} vs {limit}{unit}\n",
                )
            self._check_text.configure(state=tk.DISABLED)

    # ═══════════════════ 高程面板 ═══════════════════

    def _build_elevation_view(self) -> None:
        """构建高程面板 Treeview (暗色主题)."""
        self._elevation_tree = ttk.Treeview(
            self._elevation_frame,
            columns=("symbol", "meaning", "unit", "value"),
            show="headings",
            height=10,
        )
        self._elevation_tree.heading("symbol", text="符号")
        self._elevation_tree.heading("meaning", text="物理意义")
        self._elevation_tree.heading("unit", text="单位")
        self._elevation_tree.heading("value", text="取值")
        self._elevation_tree.column(
            "symbol", width=75, anchor="center", stretch=False
        )
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

    def _refresh_elevation_view(self) -> None:
        """刷新高程面板 — 从选中节点的 ElevationData 填充."""
        for item in self._elevation_tree.get_children():
            self._elevation_tree.delete(item)

        selected_id = self._get_selected_id()
        node_items = self._get_node_items()

        if not selected_id or selected_id not in node_items:
            self._elevation_tree.insert(
                "", tk.END, values=("←", "点击节点查看高程", "", "")
            )
            return

        backend = node_items[selected_id].backend
        if not backend or not backend.result or not backend.result.elevation:
            self._elevation_tree.insert(
                "", tk.END, values=("—", "无高程数据", "", "")
            )
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

        # ── v5.4: 泵站特殊显示 ──
        if backend.NODE_TYPE in ("wuni_bengzhan", "wuni_shusong", "wushui_tisheng"):
            # water_elevation 已是出水标高, 反推集水池水面
            sump_water = elev.water_elevation - abs(elev.head_loss)
            rows.insert(3, ("Z_sump", "集水池水面", "m", sump_water))
            rows.append(("note", "说明", "", "集水池=上游-0.2m, 出水=集水池+扬程"))

        for sym, meaning, unit, val in rows:
            self._elevation_tree.insert(
                "", tk.END, values=(sym, meaning, unit, self._fmt_val(val))
            )

    # ═══════════════════ 辅助方法 ═══════════════════

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

    def _suggest_fix(self, check_name: str, actual, limit) -> str:
        """根据约束名称给出修改建议."""
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
