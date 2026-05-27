"""
validator/reporters/console.py — 终端彩色报告输出

设计决策: 所有输出字符均为 ASCII 安全，避免 Windows GBK 控制台崩溃.
"""

from __future__ import annotations

import sys

from _logging import get_logger

from ..engine import SEVERITY_ICON, ModReport, Severity, ValidationReport

_log = get_logger(__name__)

# ── ASCII 安全符号 (Windows GBK 控制台兼容) ──
_BLOCK = "#"  # 进度条块
_BAR = "="  # 分隔线
_CHECK = "OK"  # 通过标记
_CROSS = "!!"  # 失败标记

# ANSI color codes (仅在 isatty 时启用)
_RESET = "\033[0m"
_BOLD = "\033[1m"
_RED = "\033[31m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_CYAN = "\033[36m"
_WHITE = "\033[37m"
_GRAY = "\033[90m"


def _colorize(text: str, color: str) -> str:
    """仅在终端中着色,管道输出时不加颜色"""
    if not sys.stdout.isatty():
        return text
    return f"{color}{text}{_RESET}"


class ConsoleReporter:
    """终端彩色报告"""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    def print_report(self, report: ModReport):
        """打印单个模组报告"""
        status_icon = (
            _colorize("PASS", _GREEN) if report.healthy else _colorize("FAIL", _RED)
        )
        print(
            f"\n{_BOLD}-- {report.mod_name} ({report.node_type}){_RESET} "
            f"[{status_icon}] "
            f"{_GRAY}{report.duration_ms:.0f}ms{_RESET}"
        )

        for result in report.results:
            icon = SEVERITY_ICON.get(result.severity, "[???]  ")
            if result.severity == Severity.PASS:
                color = _GREEN
            elif result.severity == Severity.WARN:
                color = _YELLOW
            else:
                color = _RED

            print(f"  {_colorize(icon, color)} {result.name:<18} {result.message}")

            if (self.verbose or result.severity <= Severity.WARN) and result.detail:
                for line in result.detail.split("\n"):
                    print(f"        {_GRAY}{line}{_RESET}")

    def print_summary(self, total: ValidationReport):
        """打印汇总"""
        print(f"\n{_BOLD}{_BAR * 60}{_RESET}")

        # 进度条
        bar_width = 40
        if total.total_checks > 0:
            p_ratio = total.total_passed / total.total_checks
            f_ratio = total.total_failures / total.total_checks
            w_ratio = total.total_warnings / total.total_checks
            e_ratio = total.total_errors / total.total_checks
        else:
            p_ratio = f_ratio = w_ratio = e_ratio = 0

        p_bar = int(p_ratio * bar_width)
        f_bar = int(f_ratio * bar_width)
        w_bar = int(w_ratio * bar_width)
        e_bar = int(e_ratio * bar_width)

        bar = (
            _colorize(_BLOCK * p_bar, _GREEN)
            + _colorize(_BLOCK * w_bar, _YELLOW)
            + _colorize(_BLOCK * f_bar, _RED)
            + _colorize(_BLOCK * e_bar, _RED)
        )
        print(f"  [{bar}{' ' * (bar_width - p_bar - f_bar - w_bar - e_bar)}]")

        print(
            f"  模组: {total.total_mods} | 健康: "
            f"{_colorize(str(total.healthy_mods), _GREEN)} | "
            f"异常: {_colorize(str(total.total_mods - total.healthy_mods), _RED)}"
        )
        print(
            f"  检查: {total.total_checks} | "
            f"{_colorize(f'PASS {total.total_passed}', _GREEN)} | "
            f"{_colorize(f'WARN {total.total_warnings}', _YELLOW)} | "
            f"{_colorize(f'FAIL {total.total_failures}', _RED)} | "
            f"{_colorize(f'ERROR {total.total_errors}', _RED)}"
        )
        print(f"  耗时: {total.duration_ms:.0f}ms")

        if total.total_failures + total.total_errors == 0:
            print(f"\n  {_colorize(_CHECK + ' 所有模组通过验证', _BOLD + _GREEN)}")
        else:
            print(
                f"\n  {_colorize(f'{_CROSS} {total.total_failures + total.total_errors} 个问题需修复',
                _BOLD + _RED)}"  # noqa: E128
            )

        print(f"{_BAR * 60}\n")
