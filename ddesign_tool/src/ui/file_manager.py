"""
file_manager.py — 项目文件管理

从 main_window.py 提取的文件操作逻辑,负责:
- 新建/打开/保存/另存为/关闭项目
- 最近文件列表管理
- 画布清理与重建
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import TYPE_CHECKING

from _logging import get_logger
from controller.graph_executor import GraphExecutor
from controller.project_manager import ProjectManager
from models.pipe_network import PipeNetworkNode
from ui.logger import log

_log = get_logger(__name__)
if TYPE_CHECKING:
    from .main_window import MainWindow


class FileManager:
    """项目文件管理器

    封装所有文件 I/O 操作,通过 parent 引用访问主窗口状态.
    """

    def __init__(self, parent: "MainWindow"):
        self._parent = parent

    @property
    def main(self) -> "MainWindow":
        return self._parent

    # ═══════════════════ 新建 ═══════════════════

    def on_new(self) -> None:
        """新建项目 — 清空画布"""
        if self.main.executor.node_count > 0:
            if not messagebox.askyesno("新建项目", "当前项目未保存,是否继续？"):
                return
        self._do_clear()
        self.main.executor = GraphExecutor()
        self.main._sync_executor_refs()
        self.main._pm.new_project()
        self.main._pipe_node = None
        self.main._selected_id = None
        self.main._refresh_params()
        self.main._refresh_selected_result()
        self.main.title("排水工程设计工具 v3 — 未命名")
        self.main.status_var.set("新项目已创建")

    # ═══════════════════ 打开 ═══════════════════

    def on_open(self) -> None:
        """打开项目文件"""
        path = filedialog.askopenfilename(
            title="打开项目",
            filetypes=[("排水设计项目", "*.ddesign.json"), ("所有文件", "*.*")],
        )
        if not path:
            return
        try:
            self._do_clear()
            executor = self.main._pm.load(Path(path))
            self.main.executor = executor
            self.main._sync_executor_refs()
            self._rebuild_canvas()
            self.update_recent_menu()
            self.main.title(f"排水工程设计工具 v5.4-s7 — {Path(path).name}")
            self.main.status_var.set(f"已打开: {Path(path).name}")
        except Exception as e:
            log.error("Open failed: %s", e)
            messagebox.showerror("打开失败", str(e))

    # ═══════════════════ 保存 ═══════════════════

    def on_save(self) -> None:
        """保存到当前路径,若无路径则另存为"""
        if self.main._pm.current_path:
            try:
                self.main._pm.save(
                    self.main.executor, filepath=self.main._pm.current_path
                )
                self.main._dirty = False
                self.update_recent_menu()
                self.main.status_var.set(f"已保存: {self.main._pm.current_path.name}")
            except Exception as e:
                messagebox.showerror("保存失败", str(e))
        else:
            self.on_save_as()

    def on_save_as(self) -> None:
        """另存为"""
        path = filedialog.asksaveasfilename(
            title="另存为",
            defaultextension=".ddesign.json",
            filetypes=[("排水设计项目", "*.ddesign.json"), ("所有文件", "*.*")],
            initialfile="未命名项目.ddesign.json",
        )
        if not path:
            return
        try:
            self.main._pm.save(self.main.executor, filepath=Path(path))
            self.main._dirty = False
            self.update_recent_menu()
            self.main.title(f"排水工程设计工具 v3 — {Path(path).name}")
            self.main.status_var.set(f"已保存: {Path(path).name}")
        except Exception as e:
            messagebox.showerror("保存失败", str(e))

    # ═══════════════════ 关闭 ═══════════════════

    def on_close(self) -> None:
        """窗口关闭 — 仅在有未保存修改时提示"""
        if self.main._dirty and self.main.executor.node_count > 0:
            result = messagebox.askyesnocancel("保存项目", "退出前是否保存当前项目？")
            if result is None:  # Cancel
                return
            if result:  # Yes
                self.on_save()
        self.main.destroy()

    # ═══════════════════ 最近文件 ═══════════════════

    def update_recent_menu(self) -> None:
        """更新最近文件子菜单"""
        self.main._recent_menu.delete(0, tk.END)
        recent = ProjectManager.get_recent_files()
        valid = [r for r in recent if Path(r).exists()]
        if not valid:
            self.main._recent_menu.add_command(label="(无最近文件)", state=tk.DISABLED)
            return
        for rp in valid[:10]:
            p = Path(rp)
            label = f"{p.stem}  ({p.parent.name})"
            self.main._recent_menu.add_command(
                label=label,
                command=lambda rp=rp: self.open_recent(rp),
            )

    def open_recent(self, path_str: str) -> None:
        """打开最近文件"""
        try:
            self._do_clear()
            executor = self.main._pm.load(Path(path_str))
            self.main.executor = executor
            self.main._sync_executor_refs()
            self._rebuild_canvas()
            self.update_recent_menu()
            self.main._dirty = False
            self.main.title(f"排水工程设计工具 v5.4-s7 — {Path(path_str).name}")
            self.main.status_var.set(f"已打开: {Path(path_str).name}")
        except Exception as e:
            log.error("Open recent failed: %s", e)
            messagebox.showerror("打开失败", str(e))

    # ═══════════════════ 画布管理 ═══════════════════

    def _do_clear(self) -> None:
        """清空画布上所有节点"""
        for nid in list(self.main.node_items.keys()):
            self.main.canvas_view.remove_node(nid)
        self.main.node_items.clear()
        self.main._pipe_node = None
        self.main._selected_id = None
        if self.main._solution_browser:
            self.main._solution_browser._solutions = []
            self.main._solution_browser._clear_all()

    def _rebuild_canvas(self) -> None:
        """从 executor 数据重建整个画布"""
        self.main.canvas_view.reset_scale()
        self.main._loading_project = True  # 抑制 auto-apply 对每个节点的触发
        try:
            for nid, node in self.main.executor._nodes.items():
                display_name = node.NODE_NAME
                node_type = node.NODE_TYPE
                ui = self.main.canvas_view.add_node(
                    display_name, node_type, node, node.x, node.y
                )
                self.main.node_items[nid] = ui
                if isinstance(node, PipeNetworkNode):
                    self.main._pipe_node = node

            # 重建连线
            port_map = {}
            for nid, ui in self.main.node_items.items():
                for p in ui.input_ports + ui.output_ports:
                    port_map[p.port_id] = p

            seen_inputs = set()
            for from_pid, to_pid in list(self.main.executor._connections):
                # SLUDGE merge ports allow multi-input (e.g. wuni_hebing)
                tp = port_map.get(to_pid)
                if tp and tp.port_type == "sludge":
                    continue
                if to_pid in seen_inputs:
                    self.main.executor._connections.discard((from_pid, to_pid))
                else:
                    seen_inputs.add(to_pid)

            for from_pid, to_pid in self.main.executor._connections:
                fp = port_map.get(from_pid)
                tp = port_map.get(to_pid)
                if fp and tp:
                    self.main.canvas_view.connect_ports(fp, tp)
                else:
                    log.warning(
                        "Connection not rebuilt: %s -> %s (fp=%s, tp=%s)",
                        from_pid,
                        to_pid,
                        "OK" if fp else "MISS",
                        "OK" if tp else "MISS",
                    )

            self.main._selected_id = None
            self.main._refresh_params()
            self.main._refresh_selected_result()
            self.main.canvas_view.fit_view()
        finally:
            self.main._loading_project = False
