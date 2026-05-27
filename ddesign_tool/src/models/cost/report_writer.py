"""
report_writer.py — 工程概算报告生成 (re-export from v5.1 split)

自 v5.1 起,报告生成逻辑拆分为:
  - cost_report_writer.py: 工程概算报告
  - pipe_report_writer.py: 管网概算报告
"""

from .cost_report_writer import write_cost_report
from .pipe_report_writer import write_pipe_network_report

__all__ = ["write_cost_report", "write_pipe_network_report"]
