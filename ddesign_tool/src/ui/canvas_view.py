"""
canvas_view.py — 节点画布 (tkinter Canvas)

特性:
  - 节点拖拽 (文字不消失)
  - Blender 风格贝塞尔连线 (自动水平切线)
  - 右键端口拖拽创建连线
  - 滚轮缩放/平移
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Dict, List, Optional, Tuple

from _logging import get_logger

_log = get_logger(__name__)
# ═══════════════════════════════
# 常量
# ═══════════════════════════════
GRID_SIZE = 20
NODE_W = 190
NODE_H = 110
PORT_R = 7
PORT_COLORS = {
    "water": "#5599ff",
    "quality": "#55cc55",
    "mixed": "#ff9955",
    "sludge": "#9966cc",
}
CONN_COLORS = {
    "water": "#4488ff",
    "quality": "#44cc44",
    "mixed": "#ff8844",
    "sludge": "#7744aa",
}


class PortItem:
    """Blender 风格端口: 外环 + 内圆"""

    def __init__(
        self,
        canvas: tk.Canvas,
        x: float,
        y: float,
        port_type: str,
        direction: str,
        port_id: str,
    ):
        self.canvas = canvas
        self.x = x
        self.y = y
        self.port_type = port_type
        self.direction = direction
        self.port_id = port_id
        self.node: Optional["NodeItem"] = None
        color = PORT_COLORS.get(port_type, "#888")
        tag = f"port_{port_id}"
        # 外环 (稍大,半透明边框)
        self._outer_id = canvas.create_oval(
            x - 10,
            y - 10,
            x + 10,
            y + 10,
            outline=color,
            width=2,
            fill="",
            tags=("port", tag),
        )
        # 内圆 (小实心)
        self._inner_id = canvas.create_oval(
            x - 5, y - 5, x + 5, y + 5, fill=color, outline="", tags=("port", tag)
        )

    def contains(self, px: float, py: float) -> bool:
        return abs(px - self.x) <= 12 and abs(py - self.y) <= 12

    def move(self, dx: float, dy: float):
        self.x += dx
        self.y += dy
        self.canvas.move(self._outer_id, dx, dy)
        self.canvas.move(self._inner_id, dx, dy)

    def highlight(self, on: bool):
        r = 12 if on else 10
        self.canvas.coords(
            self._outer_id, self.x - r, self.y - r, self.x + r, self.y + r
        )
        self.canvas.itemconfig(self._outer_id, width=3 if on else 2)


class NodeItem:
    """节点卡片 — 所有子项用统一 tag 管理 z-order"""

    def __init__(
        self,
        canvas: tk.Canvas,
        x: float,
        y: float,
        name: str,
        node_type: str,
        node_id: str,
        backend_node=None,
    ):
        self.canvas = canvas
        self.x = x
        self.y = y
        self.w = NODE_W
        self.h = NODE_H
        self.name = name
        self.node_type = node_type
        self.node_id = node_id
        self.backend = backend_node
        self.input_ports: List[PortItem] = []
        self.output_ports: List[PortItem] = []
        self._items: List[int] = []  # 所有 canvas item ID

        tag = f"ng_{node_id}"
        self._tag = tag

        # 阴影
        sid = canvas.create_rectangle(
            x + 3,
            y + 3,
            x + NODE_W + 3,
            y + NODE_H + 3,
            fill="#0a0a0a",
            outline="",
            tags=(tag,),
        )
        self._items.append(sid)

        # 主体
        rid = canvas.create_rectangle(
            x,
            y,
            x + NODE_W,
            y + NODE_H,
            fill="#2d2d2d",
            outline="#555",
            width=2,
            tags=(tag,),
        )
        self._items.append(rid)

        # 标题栏 (gdys_stss 蓝色标识)
        title_fill = "#2a4a7a" if node_type == "gdys_stss" else "#3a3a3a"
        tid = canvas.create_rectangle(
            x, y, x + NODE_W, y + 28, fill=title_fill, outline="", tags=(tag,)
        )
        self._items.append(tid)

        # 名称
        lid = canvas.create_text(
            x + 10,
            y + 6,
            text=name,
            fill="#fff",
            anchor="nw",
            font=("Microsoft YaHei", 10, "bold"),
            tags=(tag,),
        )
        self._title_id = lid  # 用于动态字体缩放
        self._items.append(lid)

        # 类型
        yid = canvas.create_text(
            x + 10,
            y + 34,
            text=node_type,
            fill="#999",
            anchor="nw",
            font=("Microsoft YaHei", 8),
            tags=(tag,),
        )
        self._type_id = yid  # 用于动态字体缩放
        self._items.append(yid)

        # 状态灯
        self._status_id = canvas.create_oval(
            x + NODE_W - 20,
            y + 8,
            x + NODE_W - 8,
            y + 20,
            fill="#666",
            outline="",
            tags=(tag,),
        )
        self._items.append(self._status_id)

        # 结果摘要
        self._result_id = canvas.create_text(
            x + 10,
            y + 54,
            text="",
            fill="#888",
            anchor="nw",
            font=("Consolas", 8),
            width=NODE_W - 20,
            tags=(tag,),
        )
        self._items.append(self._result_id)

        # 端口
        self._create_ports()

    def update_text_fonts(self, scale: float):
        """根据当前缩放因子动态更新文本字体大小.

        tkinter Canvas.scale() 只变换坐标, 不改变字体大小.
        此方法在每次缩放操作后调用, 使文本与节点矩形同步缩放.
        """
        title_sz = max(6, min(32, int(10 * scale)))
        type_sz = max(5, min(24, int(8 * scale)))
        result_sz = max(5, min(24, int(8 * scale)))
        self.canvas.itemconfig(
            self._title_id, font=("Microsoft YaHei", title_sz, "bold")
        )
        self.canvas.itemconfig(self._type_id, font=("Microsoft YaHei", type_sz))
        self.canvas.itemconfig(self._result_id, font=("Consolas", result_sz))

    def _create_ports(self):
        if not self.backend:
            return
        for i, port in enumerate(self.backend.input_ports):
            py = self.y + 38 + (i + 1) * 18
            pi = PortItem(
                self.canvas,
                self.x,
                py,
                port.port_type.name.lower(),
                "input",
                port.port_id,
            )
            pi.node = self
            self.input_ports.append(pi)
        for i, port in enumerate(self.backend.output_ports):
            py = self.y + 38 + (i + 1) * 18
            pi = PortItem(
                self.canvas,
                self.x + NODE_W,
                py,
                port.port_type.name.lower(),
                "output",
                port.port_id,
            )
            pi.node = self
            self.output_ports.append(pi)

    def contains(self, px: float, py: float) -> bool:
        return self.x <= px <= self.x + NODE_W and self.y <= py <= self.y + NODE_H

    # ═══════════════ 查询/获取 ═══════════════
    def get_port_at(self, px: float, py: float) -> Optional[PortItem]:
        for p in self.input_ports + self.output_ports:
            if p.contains(px, py):
                return p
        return None

    def raise_all(self):
        """把所有子项提升到最顶层"""
        for iid in self._items:
            self.canvas.tag_raise(iid)
        for p in self.input_ports + self.output_ports:
            self.canvas.tag_raise(p._outer_id)
            self.canvas.tag_raise(p._inner_id)

    def move(self, dx: float, dy: float):
        self.x += dx
        self.y += dy
        for iid in self._items:
            self.canvas.move(iid, dx, dy)
        for p in self.input_ports + self.output_ports:
            p.move(dx, dy)
        # 后端同步由 NodeCanvas._release() 统一处理 (含 scale 补偿)
        self.raise_all()

    # ═══════════════ 设置 ═══════════════
    def set_status(self, color: str):
        self.canvas.itemconfig(self._status_id, fill=color)

    def set_result_summary(self, text: str):
        self.canvas.itemconfig(self._result_id, text=text)

    # ═══════════════ 查询/获取 ═══════════════
    def get_output_port(self) -> Optional[PortItem]:
        return self.output_ports[0] if self.output_ports else None

    def get_input_port(self) -> Optional[PortItem]:
        return self.input_ports[0] if self.input_ports else None


class NodeCanvas(tk.Frame):
    """节点画布"""

    def __init__(self, parent, **kw):
        super().__init__(parent, **kw)
        self.nodes: Dict[str, NodeItem] = {}
        # (from, to, line_id, port_type)
        self.connections: List[Tuple[PortItem, PortItem, int, str]] = []
        self._drag_node: Optional[NodeItem] = None
        self._drag_port: Optional[PortItem] = None
        self._temp_line: Optional[int] = None
        self._lmx: float = 0
        self._lmy: float = 0
        self._selected_node: Optional[NodeItem] = None
        self.on_connection_made: Optional[Callable] = None
        self._scale: float = 1.0  # 累积缩放因子, 用于 canvas↔world 坐标转换

        # 滚动条
        hs = tk.Scrollbar(self, orient=tk.HORIZONTAL)
        hs.pack(side=tk.BOTTOM, fill=tk.X)
        vs = tk.Scrollbar(self, orient=tk.VERTICAL)
        vs.pack(side=tk.RIGHT, fill=tk.Y)

        self.canvas = tk.Canvas(
            self,
            bg="#1a1a1a",
            xscrollcommand=hs.set,
            yscrollcommand=vs.set,
            scrollregion=(0, 0, 4000, 3000),
        )
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        hs.config(command=self.canvas.xview)
        vs.config(command=self.canvas.yview)

        self._draw_grid()

        # 回调
        self.on_add_node: Optional[Callable] = None  # (node_type_key, x, y)
        self.on_delete_node: Optional[Callable] = None  # (node_id)
        self.on_node_selected: Optional[Callable] = None  # (node_id)

        # 事件
        self.canvas.bind("<Button-1>", self._click)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.canvas.bind("<Button-3>", self._rclick)
        self.canvas.bind("<B3-Motion>", self._rdrag)
        self.canvas.bind("<ButtonRelease-3>", self._rrelease)
        self.canvas.bind("<MouseWheel>", self._scroll)
        # 中键平移
        self.canvas.bind("<Button-2>", self._mid_click)
        self.canvas.bind("<B2-Motion>", self._mid_drag)
        self.canvas.bind("<ButtonRelease-2>", self._mid_release)
        self._mid_pan_start: Tuple[float, float] = (0, 0)

        # 默认手型光标
        self.canvas.config(cursor="hand2")

    def _draw_grid(self):
        for x in range(0, 4000, GRID_SIZE):
            self.canvas.create_line(x, 0, x, 3000, fill="#1e1e1e", tags=("grid",))
        for y in range(0, 3000, GRID_SIZE):
            self.canvas.create_line(0, y, 4000, y, fill="#1e1e1e", tags=("grid",))
        self.canvas.tag_lower("grid")

    # ═══════════════════════════════════════════════════════════════
    # 坐标系统 (Blender 风格)
    #
    #   世界坐标 (canonical):  backend.x / backend.y   → 保存到 JSON
    #   Canvas 坐标 (derived): NodeItem.x / NodeItem.y  → 渲染用
    #   变换关系:   canvas = world × _scale
    #
    #   _scale 是视口属性, 不影响数据. 缩放通过 canvas.scale() 改变
    #   画布元素几何尺寸, 通过 update_text_fonts() 同步字体大小.
    # ═══════════════════════════════════════════════════════════════

    # ── 节点 ──

    # ═══════════════ 节点管理 ═══════════════
    def add_node(
        self,
        name: str,
        node_type: str,
        backend_node=None,
        x: float = 100,
        y: float = 100,
    ) -> NodeItem:
        """创建节点并放置在画布上.

        Args:
            x, y: 世界坐标 (backend 位置), 内部转换为 canvas = world × _scale.
                  右键菜单传入的坐标已经由 _on_add_node_callback 做了 /_scale 转换.
        """
        nid = backend_node.node_id if backend_node else f"ui-{len(self.nodes)}"
        # 防御: 坐标极端值或 NaN 时回退到合理默认值
        try:
            if not (isinstance(x, (int, float)) and isinstance(y, (int, float))):
                x, y = 100.0, 100.0
            if abs(x) > 1e6 or abs(y) > 1e6:
                x, y = 100.0, 100.0
        except (TypeError, ValueError):
            x, y = 100.0, 100.0
        # ① 世界坐标 → Canvas 坐标
        cx, cy = x * self._scale, y * self._scale
        item = NodeItem(self.canvas, cx, cy, name, node_type, nid, backend_node)

        # ② 若视口已缩放, 将新建节点同步到当前缩放级别
        #    canvas.scale(origin=cx,cy) 对矩形是纯尺寸缩放 (原点不变),
        #    对文本/端口则是位置+尺寸同步缩放.
        if self._scale != 1.0:
            for iid in item._items:
                self.canvas.scale(iid, cx, cy, self._scale, self._scale)
            for p in item.input_ports + item.output_ports:
                self.canvas.scale(p._outer_id, cx, cy, self._scale, self._scale)
                self.canvas.scale(p._inner_id, cx, cy, self._scale, self._scale)
            # canvas.scale 只更新渲染, 需同步 Python 对象的坐标
            for p in item.input_ports + item.output_ports:
                outer = self.canvas.coords(p._outer_id)
                if outer:
                    p.x = (outer[0] + outer[2]) / 2
                    p.y = (outer[1] + outer[3]) / 2
            coords = self.canvas.coords(item._items[1])
            if coords:
                item.x, item.y = coords[0], coords[1]

        # ③ 字体同步 (tkinter Canvas.scale 不改变字体大小)
        item.update_text_fonts(self._scale)
        self.nodes[nid] = item
        return item

    # ── 视口控制 ──

    # ═══════════════ 设置 ═══════════════
    def reset_scale(self):
        """重置缩放因子为 1.0, 将所有画布元素移回世界坐标位置.

         不使用 canvas.scale() 还原 — 因为多次不同中心的缩放无法用单次
         scale 精确逆转. 改为从 backend 世界坐标 (始终正确的规范源) 直接
         move() 每个元素到目标位置.

         注意: 即使 scale==1.0 也需执行 — 自动布局可能改变了 backend 坐标,
         必须同步移动 canvas 图形.
         """
        for node in self.nodes.values():
            if not node.backend:
                continue
            tx, ty = node.backend.x, node.backend.y
            coords = self.canvas.coords(node._items[1])
            if not coords:
                continue
            dx, dy = tx - coords[0], ty - coords[1]
            for iid in node._items:
                self.canvas.move(iid, dx, dy)
            for p in node.input_ports + node.output_ports:
                self.canvas.move(p._outer_id, dx, dy)
                self.canvas.move(p._inner_id, dx, dy)
                p.x += dx
                p.y += dy
            node.x, node.y = tx, ty
        self._scale = 1.0
        self._update_connections()
        self._sync_text_fonts()

    def fit_view(self):
        """重置视口到内容区域并居中 (v5.4-s7: 强制更新布局后居中)"""
        # ── 强制完成所有待处理的几何计算 ──
        self.canvas.update_idletasks()
        bbox = self.canvas.bbox("all")
        if bbox:
            self.canvas.configure(scrollregion=bbox)
            cw = self.canvas.winfo_width()
            ch = self.canvas.winfo_height()
            content_w = bbox[2] - bbox[0]
            content_h = bbox[3] - bbox[1]
            # ── 如果视口能容纳全部内容, 居中显示; 否则从左上角开始 ──
            if cw >= content_w and ch >= content_h:
                # 内容比视口小 → 居中
                offset_x = (cw - content_w) / 2
                offset_y = (ch - content_h) / 2
                self.canvas.configure(scrollregion=(
                    bbox[0] - offset_x, bbox[1] - offset_y,
                    bbox[2] + offset_x, bbox[3] + offset_y
                ))
                self.canvas.xview_moveto(0)
                self.canvas.yview_moveto(0)
            elif cw > 1 and ch > 1:
                # 视口尺寸有效 → 尝试居中
                cx = (bbox[0] + bbox[2]) / 2
                cy = (bbox[1] + bbox[3]) / 2
                tx = max(0.0, min(1.0, (cx - cw / 2) / max(content_w, 1)))
                ty = max(0.0, min(1.0, (cy - ch / 2) / max(content_h, 1)))
                self.canvas.xview_moveto(tx)
                self.canvas.yview_moveto(ty)
            else:
                # 视口尺寸未知 → 回退左上角
                self.canvas.xview_moveto(0)
                self.canvas.yview_moveto(0)
        else:
            self.canvas.configure(scrollregion=(0, 0, 4000, 3000))
            self.canvas.xview_moveto(0)
            self.canvas.yview_moveto(0)

    # ═══════════════ 节点管理 ═══════════════
    def remove_node(self, node_id: str):
        if node_id not in self.nodes:
            return
        node = self.nodes[node_id]
        to_remove = []
        for fp, tp, lid, _ in self.connections:
            if (fp.node and fp.node.node_id == node_id) or (
                tp.node and tp.node.node_id == node_id
            ):
                self.canvas.delete(lid)
                to_remove.append((fp, tp, lid, _))
        for item in to_remove:
            self.connections.remove(item)
        for iid in node._items:
            self.canvas.delete(iid)
        for p in node.input_ports + node.output_ports:
            self.canvas.delete(p._outer_id)
            self.canvas.delete(p._inner_id)
        del self.nodes[node_id]

    # ── Blender 风格贝塞尔连线 ──
    def _bezier_coords(
        self, x1: float, y1: float, x2: float, y2: float, direction: str = "output"
    ) -> List[float]:
        dx = abs(x2 - x1) * 0.5
        if direction == "output" or x1 < x2:
            return [x1, y1, x1 + dx, y1, x2 - dx, y2, x2, y2]
        else:
            return [x1, y1, x1 - dx, y1, x2 + dx, y2, x2, y2]

    def connect_ports(self, from_port: PortItem, to_port: PortItem):
        # SLUDGE 输入端允许多连 (污泥合并), 其他类型只允许一根
        if to_port.port_type != "sludge":
            self._remove_connections_for_port(to_port, "input")
        # 断开输出端口已有连线(可选, 允许一对多则注释掉)
        # self._remove_connections_for_port(from_port, "output")
        color = CONN_COLORS.get(from_port.port_type, "#4488ff")
        pts = self._bezier_coords(
            from_port.x, from_port.y, to_port.x, to_port.y, direction="output"
        )
        lid = self.canvas.create_line(
            *pts,
            fill=color,
            width=2,
            smooth=True,
            splinesteps=32,
            tags=("connection",),
            capstyle=tk.ROUND,
        )
        self.connections.append((from_port, to_port, lid, from_port.port_type))
        # 连线放在节点之上,确保可见 (不使用 tag_lower 避免被网格覆盖)

    def _remove_connections_for_port(self, port: PortItem, which: str):
        """删除指定端口的所有连线 (which='input'|'output'|'any')"""
        to_remove = []
        for fp, tp, lid, pt in self.connections:
            match = (
                (which == "input" and tp == port)
                or (which == "output" and fp == port)
                or (which == "any" and (fp == port or tp == port))
            )
            if match:
                self.canvas.delete(lid)
                to_remove.append((fp, tp, lid, pt))
        for item in to_remove:
            self.connections.remove(item)

    def _update_connections(self):
        for fp, tp, lid, _ in self.connections:
            pts = self._bezier_coords(fp.x, fp.y, tp.x, tp.y, direction="output")
            self.canvas.coords(lid, *pts)

    # ── 中键平移 ──
    def _mid_click(self, event):
        self._mid_pan_start = (event.x, event.y)
        self.canvas.config(cursor="fleur")  # 抓取手势
        self.canvas.scan_mark(event.x, event.y)

    def _mid_drag(self, event):
        self.canvas.scan_dragto(event.x, event.y, gain=1)

    def _mid_release(self, event):
        self.canvas.config(cursor="hand2")  # 恢复手型

    def _canvas_xy(self, event) -> Tuple[float, float]:
        return self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)

    def _select_node(self, node: Optional[NodeItem]):
        """选中节点,高亮边框"""
        if self._selected_node:
            self.canvas.itemconfig(self._selected_node._items[1], outline="#555")
        self._selected_node = node
        if node:
            self.canvas.itemconfig(node._items[1], outline="#ffaa44")
            if self.on_node_selected:
                self.on_node_selected(node.node_id)

    def _click(self, event):
        x, y = self._canvas_xy(event)
        self._lmx, self._lmy = x, y

        # 端口 → 拖拽连线 (Blender 风格: 先断开已有连接,任意方向端口均可)
        for node in self.nodes.values():
            port = node.get_port_at(x, y)
            if port:
                self._remove_connections_for_port(port, "any")
                self._drag_port = port
                return

        # 节点 → 选中 (单点 = 选中,拖拽 = 移动)
        for node in self.nodes.values():
            if node.contains(x, y):
                self._drag_node = node
                node.raise_all()
                self._select_node(node)
                return

        # 空白 → 取消选中
        self._select_node(None)

    def _drag(self, event):
        x, y = self._canvas_xy(event)
        dx, dy = x - self._lmx, y - self._lmy
        self._lmx, self._lmy = x, y

        if self._drag_node:
            self._drag_node.move(dx, dy)
            self._update_connections()
        elif self._drag_port:
            pts = self._bezier_coords(self._drag_port.x, self._drag_port.y, x, y)
            if self._temp_line:
                self.canvas.coords(self._temp_line, *pts)
            else:
                self._temp_line = self.canvas.create_line(
                    *pts,
                    fill="#ffaa44",
                    width=2,
                    dash=(6, 4),
                    smooth=True,
                    splinesteps=24,
                    tags=("temp",),
                )

    def _release(self, event):
        if self._drag_port:
            x, y = self._canvas_xy(event)
            # 查找目标端口(方向相反)
            target_dir = "input" if self._drag_port.direction == "output" else "output"
            target = None
            for node in self.nodes.values():
                port = node.get_port_at(x, y)
                if (
                    port
                    and port.direction == target_dir
                    and port.node != self._drag_port.node
                ):
                    target = port
                    break
            if target:
                if self._drag_port.direction == "output":
                    self.connect_ports(self._drag_port, target)
                    if self.on_connection_made:
                        self.on_connection_made(self._drag_port, target)
                else:
                    self.connect_ports(target, self._drag_port)
                    if self.on_connection_made:
                        self.on_connection_made(target, self._drag_port)

        # 拖拽完成后同步后端位置 (含 scale 补偿)
        if self._drag_node:
            self._sync_all_positions()

        self._drag_node = None
        self._drag_port = None
        if self._temp_line:
            self.canvas.delete(self._temp_line)
            self._temp_line = None

    def _rclick(self, event):
        x, y = self._canvas_xy(event)
        self._lmx, self._lmy = x, y

        # 右键 → 仅上下文菜单(连线通过左键拖拽完成)
        for nid, node in list(self.nodes.items()):
            if node.contains(x, y):
                self._show_node_menu(event, nid, node)
                return "break"

        self._show_canvas_menu(event, x, y)
        return "break"

    # ═══════════════ 面板显示 ═══════════════
    def _show_node_menu(self, event, node_id: str, node: NodeItem):
        """节点右键菜单: 删除 / 选中"""
        menu = tk.Menu(
            self,
            tearoff=0,
            bg="#333",
            fg="#ccc",
            activebackground="#555",
            activeforeground="#fff",
        )
        menu.add_command(
            label=f"删除「{node.name}」", command=lambda: self._delete_node(node_id)
        )
        menu.add_separator()
        menu.add_command(label="取消", command=lambda: None)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _show_canvas_menu(self, event, x: float, y: float):
        """画布右键菜单: 分类添加节点"""
        menu = tk.Menu(
            self,
            tearoff=0,
            bg="#333",
            fg="#ccc",
            activebackground="#555",
            activeforeground="#fff",
        )

        # 分类结构: {分类名: [(显示名, node_type_key)]}
        # Auto-derive categories from ModManager
        from mods.mod_manager import get_mod_manager

        mgr = get_mod_manager()
        categories = mgr.get_category_menu()

        for cat_name, items in categories.items():
            sub = tk.Menu(
                menu,
                tearoff=0,
                bg="#3a3a3a",
                fg="#ccc",
                activebackground="#555",
                activeforeground="#fff",
            )
            for display_name, key in items:
                sub.add_command(
                    label=display_name,
                    command=lambda k=key, cx=x, cy=y: self._on_add_node_callback(
                        k, cx, cy
                    ),
                )
            menu.add_cascade(label=cat_name, menu=sub)

        menu.add_separator()
        menu.add_command(label="取消", command=lambda: None)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    # ═══════════════ 事件回调 ═══════════════
    def _on_add_node_callback(self, key: str, x: float, y: float):
        """右键菜单添加节点 — x,y 为 Canvas 坐标, 转换为世界坐标后回调"""
        if self.on_add_node:
            wx = x / self._scale if self._scale > 0 else x
            wy = y / self._scale if self._scale > 0 else y
            self.on_add_node(key, wx, wy)

    # ═══════════════ 节点管理 ═══════════════
    def _delete_node(self, node_id: str):
        if self.on_delete_node:
            self.on_delete_node(node_id)

    def _rdrag(self, event):
        x, y = self._canvas_xy(event)
        if self._drag_port:
            pts = self._bezier_coords(self._drag_port.x, self._drag_port.y, x, y)
            if self._temp_line:
                self.canvas.coords(self._temp_line, *pts)
            else:
                self._temp_line = self.canvas.create_line(
                    *pts,
                    fill="#55ff55",
                    width=2,
                    dash=(6, 4),
                    smooth=True,
                    splinesteps=24,
                    tags=("temp",),
                )

    def _rrelease(self, event):
        # 右键释放 → 清理临时线(连线已统一由左键处理)
        if self._temp_line:
            self.canvas.delete(self._temp_line)
            self._temp_line = None
        self._drag_port = None

    def _scroll(self, event):
        """滚轮缩放 — 以鼠标所在 Canvas 坐标为中心"""
        s = 1.08 if event.delta > 0 else 0.93
        self._scale *= s  # 累积缩放因子
        # 必须用 canvas 坐标 (canvasx/canvasy) 而非 screen 坐标 (event.x/y)
        # 否则缩放中心会随滚动/历史缩放漂移
        cx, cy = self._canvas_xy(event)
        self.canvas.scale("all", cx, cy, s, s)
        # 同步 Python 坐标 (含 scale 补偿)
        self._sync_all_positions()
        # 同步文本字体 (Canvas.scale 不改变字体大小)
        self._sync_text_fonts()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    # ═══════════════ 同步 ═══════════════
    def _sync_all_positions(self):
        """从 Canvas 坐标回读, 同步 NodeItem 和 backend 坐标.

        调用时机:
          - _scroll:  canvas.scale 之后, 坐标系已变, 需要回读
          - _release: 拖拽完成后, 将 canvas 位移写入 backend 世界坐标

        不在 reset_scale 中调用 — 那里直接用 backend 位置移动元素,
        坐标已经是正确的, 无需回读.
        """
        for node in self.nodes.values():
            coords = self.canvas.coords(node._items[1])
            if coords:
                node.x, node.y = coords[0], coords[1]
            for p in node.input_ports + node.output_ports:
                outer = self.canvas.coords(p._outer_id)
                if outer:
                    p.x = (outer[0] + outer[2]) / 2
                    p.y = (outer[1] + outer[3]) / 2
            if node.backend and self._scale > 0:
                node.backend.x = node.x / self._scale
                node.backend.y = node.y / self._scale
        self._update_connections()

    def _sync_text_fonts(self):
        """同步所有节点文本字体大小到当前缩放因子.

        tkinter Canvas.scale() 只变换坐标而不会改变 itemconfig 中的 font 大小.
        每次缩放后调用此方法, 使标题/类型/结果文本与节点边框保持比例.
        """
        for node in self.nodes.values():
            node.update_text_fonts(self._scale)
