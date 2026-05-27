"""
_logging.py — 统一日志配置 (v5.1)

自 v5.1 起统一所有模块的日志输出.替代分散的 logging.getLogger() 调用.

使用:
    from _logging import get_logger
    _log = get_logger(__name__)

默认只输出 WARNING+ 到 stderr,避免 GUI 模式下控制台污染.
"""

import logging
import sys


def get_logger(name: str) -> logging.Logger:
    """获取统一配置的 Logger 实例.

    首次调用时配置 StreamHandler(stderr),后续调用复用已有 handler.
    默认级别 WARNING,可通过环境变量 DDESIGN_LOG_LEVEL 覆盖.

    Args:
        name: Logger 名称(通常为 __name__)

    Returns:
        logging.Logger
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))
        logger.addHandler(handler)

        # 默认 WARNING,环境变量可覆盖
        level_name = "WARNING"
        from os import environ

        env_level = environ.get("DDESIGN_LOG_LEVEL", "")
        if env_level.upper() in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            level_name = env_level.upper()
        logger.setLevel(getattr(logging, level_name))
        logger.propagate = False

    return logger
