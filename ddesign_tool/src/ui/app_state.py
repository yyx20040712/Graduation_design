"""
app_state.py — 集中化 UI 状态管理 (v5.4)

将散落在 MainWindow 各处的状态标志统一到单个 dataclass,
提供单一真相源, 便于调试和测试.

工业参考: Qt QSettings 简化版 — 带类型的属性容器 + 受控访问.
"""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class AppState:
    """MainWindow 全局 UI 状态

    替代原先散落的:
      - self._selected_id  → selected_node_id
      - self._browse_mode  → browse_mode
      - self._dirty        → is_dirty
      - self._slider_vars  → slider_vars
      - _loading_project   → is_loading_project
    """

    selected_node_id: Optional[str] = None
    browse_mode: bool = True  # True=方案浏览, False=手动微调
    is_dirty: bool = False  # 是否有未保存的修改
    is_loading_project: bool = False  # 正在加载项目 (防重入)
    current_project_path: Optional[str] = None
    slider_vars: Dict[str, tk.DoubleVar] = field(default_factory=dict)
