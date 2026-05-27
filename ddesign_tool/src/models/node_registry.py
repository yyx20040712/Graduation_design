"""
node_registry.py — 统一节点类型注册表 (v4.1 — 纯 ModManager)

所有消费者通过此模块查询节点类型信息.
全部节点类通过 ModManager 从 mods/ 加载,无回退路径.

使用方式:
    from models.node_registry import is_io_node, has_solution_space, resolve_class
"""

from __future__ import annotations

from typing import Dict, List, Optional, Type

from _logging import get_logger

_log = get_logger(__name__)

# ═════════════════════════════════════════════════════════════════════
# 内置基础设施节点 (无 mod.json,固定注册)
# ═════════════════════════════════════════════════════════════════════

_INFRA_TYPES = frozenset(
    {
        "pipe_network",
        "water_quality",
        "combiner",
        "input_node",
        "kw_input",
        "wuni_hebing",
    }
)
_WQ_CARD_TYPES = frozenset({"water_quality", "input_node", "kw_input"})

_SOLUTION_STAGES = frozenset(
    {"primary", "secondary", "tertiary", "mine_water", "sludge", "collection"}
)
_NON_SOLUTION_TYPES = _INFRA_TYPES | {"wuni_hebing"}


class NodeRegistry:
    """统一节点类型注册表 — 模块级单例"""

    def __init__(self):
        self._types: Dict[str, dict] = (
            {}
        )  # node_type → {module_path, class_name, display_name, process_stage}
        self._class_cache: Dict[str, Optional[Type]] = {}
        self._populated = False

    # ── 注册 ──

    def register(
        self,
        node_type: str,
        module_path: str,
        class_name: str,
        display_name: str = "",
        process_stage: str = "",
    ) -> None:
        """注册一个节点类型(ModManager 调用)"""
        self._types[node_type] = {
            "module_path": module_path,
            "class_name": class_name,
            "display_name": display_name,
            "process_stage": process_stage,
        }

    def register_from_mod_manager(self, mgr) -> None:
        """从 ModManager 批量注册所有已加载模组"""
        for mod_id, mod_info in mgr.mods.items():
            if mod_info.loaded and mod_info.node_cls:
                self.register(
                    node_type=mod_info.node_type,
                    module_path=mod_info.module_path or "",
                    class_name=mod_info.node_class,
                    display_name=mod_info.name,
                    process_stage=mod_info.process_stage,
                )
        self._populated = True

    # ── 查询 ──

    def is_io_node(self, node_type: str) -> bool:
        """是否为输入/输出基础设施节点"""
        if node_type in _INFRA_TYPES:
            return True
        info = self._types.get(node_type, {})
        return info.get("process_stage") == "io"

    def has_solution_space(self, node_type: str) -> bool:
        """是否支持方案空间枚举"""
        if node_type in _INFRA_TYPES:
            return False
        # 已由 ModManager 填充 → 使用 stage 判断
        if self._populated:
            info = self._types.get(node_type, {})
            stage = info.get("process_stage", "")
            return stage in _SOLUTION_STAGES
        # 未填充 → 排除已知非处理节点,其余假定支持
        return node_type not in _NON_SOLUTION_TYPES

    def is_water_quality_node(self, node_type: str) -> bool:
        """是否为水质输入节点"""
        return node_type in _WQ_CARD_TYPES

    def get_display_name(self, node_type: str) -> str:
        """获取显示名称"""
        return self._types.get(node_type, {}).get("display_name", node_type)

    def get_process_stage(self, node_type: str) -> str:
        """获取处理阶段"""
        return self._types.get(node_type, {}).get("process_stage", "")

    def get_all_types(self) -> List[str]:
        """获取所有已注册的节点类型"""
        return list(self._types.keys())

    def resolve_class(self, node_type: str) -> Optional[Type]:
        """解析节点类 — 全部通过 ModManager 从 mods/ 加载"""
        if node_type in self._class_cache:
            return self._class_cache[node_type]

        try:
            import os
            import sys

            _app_root = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "..")
            )
            if _app_root not in sys.path:
                sys.path.insert(0, _app_root)
            from mods.mod_manager import get_mod_manager

            mgr = get_mod_manager()
            mgr.load_all()
            cls = mgr.get_node_class(node_type)
            if cls is not None:
                self._class_cache[node_type] = cls
                return cls
        except Exception as e:
            _log.warning("operation failed: %s", e, exc_info=True)

        self._class_cache[node_type] = None
        return None


# ═════════════════════════════════════════════════════════════════════
# 模块级单例 + 便捷函数
# ═════════════════════════════════════════════════════════════════════

_registry = NodeRegistry()


def get_registry() -> NodeRegistry:
    """获取全局注册表单例"""
    return _registry


# ── 模组生命周期钩子 (MC Event Bus 等价物) ──
_lifecycle_hooks: list = []


def on_register(callback):
    """装饰器: 注册模组生命周期回调.回调签名: callback(mod_id, node_type, node_cls)"""
    _lifecycle_hooks.append(callback)
    return callback


def _fire_register(mod_id: str, node_type: str, node_cls):
    """通知所有监听器: 新模组已注册"""
    for hook in _lifecycle_hooks:
        try:
            hook(mod_id, node_type, node_cls)
        except Exception as e:
            _log.warning("operation failed: %s", e, exc_info=True)


# 便捷函数 (零异常——永远返回 bool/Optional,不抛出异常)
def is_io_node(node_type: str) -> bool:
    """安全检测是否为 IO 节点.ModManager 不可用时自动降级."""
    return _registry.is_io_node(node_type)


def has_solution_space(node_type: str) -> bool:
    """安全检测是否支持方案空间枚举."""
    return _registry.has_solution_space(node_type)


def is_water_quality_node(node_type: str) -> bool:
    """安全检测是否为水质输入节点."""
    return _registry.is_water_quality_node(node_type)


def resolve_class(node_type: str) -> Optional[Type]:
    """安全解析节点类.失败返回 None (不抛出异常)."""
    return _registry.resolve_class(node_type)
