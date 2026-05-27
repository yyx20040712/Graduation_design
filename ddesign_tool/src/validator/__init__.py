"""
validator — 嵌入式模组验证系统

使用:
    # CLI 模式
    > python -m validator --all --deep

    # 编程模式
    from validator import run_validation
    report = run_validation("tiaojiechi", mode="deep")
"""

from __future__ import annotations

import sys
from typing import List, Optional

from _logging import get_logger

from .engine import ModValidator, ValidationReport
from .reporters.console import ConsoleReporter
from .reporters.html import HTMLReporter
from .reporters.json_report import JSONReporter

_log = get_logger(__name__)


def run_validation(
    node_type: Optional[str] = None,
    mode: str = "quick",
    mod_manager=None,
    output: Optional[str] = None,
    verbose: bool = False,
    use_baseline: bool = False,
) -> ValidationReport:
    """运行验证

    Args:
        node_type: 模组类型名,None = 全部
        mode: "quick" | "deep"
        mod_manager: 模组管理器实例
        output: 输出文件路径 (.html / .json)
        verbose: 详细输出

    Returns:
        ValidationReport
    """
    validator = ModValidator(mod_manager)

    if node_type:
        report = validator.validate(node_type, mode, use_baseline=use_baseline)
        reports = [report]
    else:
        total = validator.validate_all(mode, use_baseline=use_baseline)
        reports = total.reports

    total = ValidationReport(reports=reports, total_mods=len(reports))
    for r in reports:
        total.healthy_mods += 1 if r.healthy else 0
        total.total_checks += r.total
        total.total_passed += r.passed
        total.total_warnings += r.warnings
        total.total_failures += r.failures
        total.total_errors += r.errors
    total.duration_ms = sum(r.duration_ms for r in reports)

    # 终端输出
    console = ConsoleReporter(verbose=verbose)
    for r in reports:
        console.print_report(r)
    console.print_summary(total)

    # 文件输出
    if output:
        if output.endswith(".html"):
            HTMLReporter().save(reports, output)
            print(f"  报告已保存: {output}")
        elif output.endswith(".json"):
            JSONReporter().save(reports, output)
            print(f"  报告已保存: {output}")

    return total


def main(argv: Optional[List[str]] = None):
    """CLI 入口"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Mod Validator — 嵌入式模组验证系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  ddesign_tool.exe --validate --all              # 验证所有模组
  ddesign_tool.exe --validate --mod=tiaojiechi   # 验证指定模组
  ddesign_tool.exe --validate --all --deep       # 深度验证
  ddesign_tool.exe --validate --all --output=report.html
  ddesign_tool.exe --validate --all --ci         # CI 模式 (非零退出码)
""",
    )
    parser.add_argument("--mod", help="验证指定模组 (node_type)")
    parser.add_argument("--all", action="store_true", help="验证所有模组")
    parser.add_argument("--deep", action="store_true", help="深度验证模式")
    parser.add_argument("--output", help="输出报告文件 (.html / .json)")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    parser.add_argument("--ci", action="store_true", help="CI 模式 (非零退出码)")
    parser.add_argument("--baseline", action="store_true", help="使用基线抑制已知问题")
    parser.add_argument(
        "--generate-baseline",
        action="store_true",
        help="为所有模组生成基线 (抑制当前所有 FAIL/WARN)",
    )
    parser.add_argument("--list", action="store_true", help="列出可用模组")

    args = parser.parse_args(argv)

    # 列出模组
    if args.list:
        from mods.mod_manager import get_mod_manager

        mgr = get_mod_manager()
        mgr.load_all()
        from models.discretization import (
            _refresh_merged_configs,
            load_mod_discretizations,
        )

        _refresh_merged_configs()
        configs = load_mod_discretizations()
        mgr = get_mod_manager()
        mgr.load_all()
        for nt in sorted(configs.keys()):
            mod_info = mgr.get_mod_by_node_type(nt)
            name = mod_info.name if mod_info else nt
            print(f"  {nt:<25} {name}")
        return 0

    if not args.all and not args.mod and not args.generate_baseline:
        parser.print_help()
        return 1

    # 生成基线模式
    if args.generate_baseline:
        from .engine import ModValidator

        validator = ModValidator()
        count = validator.generate_baselines()
        print(f"  基线已生成: {count} 个模组")
        return 0

    total = run_validation(
        node_type=args.mod if args.mod else None,
        mode="deep" if args.deep else "quick",
        output=args.output,
        verbose=args.verbose,
        use_baseline=args.baseline,
    )

    # CI 模式: 有 FAIL/ERROR 则返回非零
    if args.ci:
        if total.total_failures > 0 or total.total_errors > 0:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
