"""
test_canvas_interaction.py — 画布交互 GUI 集成测试 (v5.3)

验证画布视口控制:
- 定位流程按钮: 重置缩放 + 视口归位
- fit_view 后画布滚动区域覆盖所有节点
"""

from __future__ import annotations

import os
import sys
import tkinter as tk

import pytest

_SRC = os.path.join(os.path.dirname(__file__), "..", "..", "ddesign_tool", "src")
_TOOL = os.path.join(os.path.dirname(__file__), "..", "..", "ddesign_tool")
for p in [_SRC, _TOOL]:
    if p not in sys.path:
        sys.path.insert(0, p)


@pytest.fixture(scope="module")
def main_window():
    """创建 MainWindow 实例并执行 F5 计算"""
    from ui.main_window import MainWindow

    win = MainWindow()
    win.withdraw()
    win._on_calc_all()
    yield win
    try:
        win.destroy()
    except tk.TclError:
        pass


class TestLocateFlow:
    """定位流程按钮测试"""

    def test_locate_flow_method_exists(self, main_window):
        """_on_locate_flow 方法存在且可调用"""
        assert hasattr(
            main_window, "_on_locate_flow"
        ), "MainWindow 缺少 _on_locate_flow 方法"
        assert callable(main_window._on_locate_flow)

    def test_locate_flow_does_not_crash(self, main_window):
        """调用定位流程不崩溃"""
        try:
            main_window._on_locate_flow()
        except Exception as e:
            pytest.fail(f"_on_locate_flow 崩溃: {e}")

    def test_locate_flow_resets_viewport(self, main_window):
        """定位后画布视口回到原点 (xview=0)"""
        canvas = main_window.canvas_view.canvas

        # 先模拟平移 — 将视口移动到中间位置
        canvas.xview_moveto(0.5)
        canvas.yview_moveto(0.5)
        main_window.update_idletasks()

        # 执行定位
        main_window._on_locate_flow()
        main_window.update_idletasks()

        # 验证视口已回到原点
        x0, x1 = canvas.xview()
        y0, y1 = canvas.yview()
        assert abs(x0) < 0.01, f"xview 未归零: x0={x0:.4f}"
        assert abs(y0) < 0.01, f"yview 未归零: y0={y0:.4f}"

    def test_locate_flow_after_zoom(self, main_window):
        """缩放后定位恢复 scale=1.0"""
        canvas = main_window.canvas_view.canvas

        # 先检查 canvas_view 是否有 _scale 属性
        if not hasattr(main_window.canvas_view, "_scale"):
            pytest.skip("canvas_view 无 _scale 属性")

        # 模拟缩放 (修改 _scale 并平移)
        main_window.canvas_view._scale = 2.0
        canvas.xview_moveto(0.3)
        canvas.yview_moveto(0.3)
        main_window.update_idletasks()

        # 执行定位
        main_window._on_locate_flow()
        main_window.update_idletasks()

        # 验证 scale 已重置
        assert (
            main_window.canvas_view._scale == 1.0
        ), f"scale 未重置: {main_window.canvas_view._scale}"
        # 验证视口归零
        x0, _ = canvas.xview()
        y0, _ = canvas.yview()
        assert abs(x0) < 0.01, f"zoom 后 xview 未归零: {x0:.4f}"
        assert abs(y0) < 0.01, f"zoom 后 yview 未归零: {y0:.4f}"

    def test_locate_flow_status_message(self, main_window):
        """定位后状态栏显示正确消息"""
        main_window._on_locate_flow()
        main_window.update_idletasks()
        status = main_window.status_var.get()
        assert "自动布局完成" in status, f"状态栏消息不正确: {status}"
