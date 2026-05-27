"""
mods — 水处理工艺模组系统

提供可扩展的工艺模块管理框架.
核心模组位于 core/,社区模组位于 community/.

每个模组是一个文件夹,包含:
  - mod.json: 模组元数据(参数、去除率、公式等)
  - __init__.py: 计算逻辑(NodeBase 子类)

类似 Minecraft 的模组社区,用户可以自由添加自定义工艺模组.
"""

from .mod_manager import ModManager, ModInfo

__all__ = ["ModManager", "ModInfo"]
