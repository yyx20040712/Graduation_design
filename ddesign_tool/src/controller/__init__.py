"""
controller — 应用控制层

包含:
  - GraphExecutor: DAG 执行引擎(拓扑排序 + 顺序计算)
  - ProjectManager: 项目文件读写
  - CostEstimator: 工程概算引擎(后续实现)
"""

from _logging import get_logger

from .graph_executor import GraphExecutor
from .project_manager import ProjectManager

_log = get_logger(__name__)
__all__ = ["GraphExecutor", "ProjectManager"]
