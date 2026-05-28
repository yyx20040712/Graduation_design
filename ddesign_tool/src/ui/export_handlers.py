"""
export_handlers.py — 导出/概算处理器 (extracted from main_window.py)

提供独立的 Excel 导出、工程概算生成功能,从主窗口解耦.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from typing import Any


def export_cost_report(
    executor: Any, pipe_node: Any, status_var: tk.StringVar, parent: tk.Toplevel
) -> None:
    """导出完整工程概算报告.

    Args:
        executor: GraphExecutor 实例
        pipe_node: 管网节点 (PipeNetworkNode 或 None)
        status_var: 状态栏 StringVar
        parent: 父窗口
    """
    status_var.set("正在生成概算报告...")
    parent.update_idletasks()
    try:
        from models.cost.cost_estimator import CostEstimator

        results = executor.execute(force_all=False)
        estimator = CostEstimator()
        est = estimator.estimate(
            executor,
            pipe_node=pipe_node,
            project_name="污水处理厂",
            results=results,
        )
        from models.cost.report_writer import write_cost_report

        fp = write_cost_report(est, executor=executor, results=results)
        status_var.set(f"概算报告已导出: {fp}")
        messagebox.showinfo("导出完成", f"已保存到:\n{fp}")
    except Exception as e:
        status_var.set(f"概算导出失败: {e}")
        messagebox.showerror("导出失败", str(e))


def calc_pipe_cost_report(
    pipe_node: Any, status_var: tk.StringVar, parent: tk.Toplevel
) -> None:
    """生成管网概算报告.

    Args:
        pipe_node: 管网节点 (PipeNetworkNode)
        status_var: 状态栏 StringVar
        parent: 父窗口
    """
    if pipe_node is None:
        messagebox.showwarning("无管网", "请先在画布上添加管网输入节点")
        return

    from models.cost.pipe_network_cost import write_pipe_cost_report

    try:
        fp = write_pipe_cost_report(pipe_node, str(parent._pipe_var.get() or ""))
        status_var.set(f"管网报告已导出: {fp}")
        messagebox.showinfo("导出完成", f"已保存到:\n{fp}")
    except Exception as e:
        status_var.set(f"管网报告失败: {e}")
        messagebox.showerror("导出失败", str(e))


def export_all_results(
    executor: Any, status_var: tk.StringVar, parent: tk.Toplevel
) -> None:
    """分类输出全部计算结果到 output/ 目录.

    优先使用节点缓存,缺失水质数据时执行轻量重算补全.

    Args:
        executor: GraphExecutor 实例
        status_var: 状态栏 StringVar
        parent: 父窗口
    """
    status_var.set("正在输出计算结果...")
    parent.update_idletasks()
    try:
        results: dict[str, Any] = {}
        needs_recalc = False

        for nid, node in executor._nodes.items():
            if node.result and node.result.success:
                results[nid] = node.result
                if (
                    node.result.inlet_quality is None
                    or node.result.outlet_quality is None
                ):
                    needs_recalc = True

        if not results or needs_recalc:
            fresh_results = executor.execute(force_all=False)
            for nid in list(results.keys()):
                if nid in fresh_results:
                    results[nid] = fresh_results[nid]
            for nid, r in fresh_results.items():
                if nid not in results and not nid.startswith("_"):
                    results[nid] = r

        from output_writer import write_classified_output

        fp = write_classified_output(results, executor)
        status_var.set(f"输出完成: {fp}")
        messagebox.showinfo("输出完成", f"已保存到:\n{fp}")
    except Exception as e:
        status_var.set(f"输出失败: {e}")
        messagebox.showerror("输出失败", str(e))
