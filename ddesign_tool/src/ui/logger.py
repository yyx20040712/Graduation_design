"""
logger.py — 日志系统

输出到 ddesign_tool/logs/ 目录
自动按日期轮转
"""

import os
import sys
import logging
from datetime import datetime

from _logging import get_logger

_log = get_logger(__name__)


def setup_logger(name: str = "ddesign", log_dir: str = None) -> logging.Logger:
    """设置日志系统

    Args:
        name: 日志名称
        log_dir: 日志目录,默认为 ddesign_tool/logs/

    Returns:
        configured Logger
    """
    if log_dir is None:
        from _paths import get_logs_dir

        log_dir = get_logs_dir()

    os.makedirs(log_dir, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # 避免重复添加 handler
    if logger.handlers:
        return logger

    # 文件 handler (所有级别)
    log_file = os.path.join(log_dir, f"ddesign_{datetime.now().strftime('%Y%m%d')}.log")
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(
        logging.Formatter(
            "[%(asctime)s] %(levelname)-7s %(name)s: %(message)s", datefmt="%H:%M:%S"
        )
    )
    logger.addHandler(fh)

    # 控制台 handler (INFO 及以上)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("%(levelname)-7s %(message)s"))
    logger.addHandler(ch)

    return logger


# 全局 logger 实例
log = setup_logger()
