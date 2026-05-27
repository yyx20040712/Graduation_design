"""
validator/__main__.py — 支持 python -m validator 调用
"""

import sys

from _logging import get_logger

from . import main

_log = get_logger(__name__)
sys.exit(main())
