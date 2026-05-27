"""
sludge_mixin.py — 污泥管理 Mixin (extracted from base.py)

从 NodeBase 中分离污泥处理逻辑.避免循环依赖: 运行时导入 PortType.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Tuple

if TYPE_CHECKING:
    from .base import NodeResult, SludgeFlow  # noqa: F401


class SludgeMixin:
    """污泥管理 Mixin — 管理节点的污泥输出和污泥计算."""

    _sludge_output: Optional["SludgeFlow"] = None  # type: ignore[name-defined]
    input_ports: list = []

    @property
    def sludge_output(self) -> Optional["SludgeFlow"]:  # type: ignore[name-defined]
        return self._sludge_output

    @property
    def is_sludge_only(self) -> bool:
        if not self.input_ports:
            return False
        from .base import PortType

        return all(p.port_type == PortType.SLUDGE for p in self.input_ports)

    def execute_sludge(
        self, sludge: "SludgeFlow"  # type: ignore[name-defined]
    ) -> Tuple[Optional["NodeResult"], "SludgeFlow"]:  # type: ignore[name-defined]
        return None, sludge
