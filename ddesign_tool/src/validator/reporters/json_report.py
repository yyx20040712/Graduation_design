"""
validator/reporters/json_report.py — JSON 机器可读报告
"""

from __future__ import annotations

import json
import os
from typing import List

from _logging import get_logger

from ..engine import CheckResult, ModReport, ValidationReport

_log = get_logger(__name__)
_SEVERITY_NAME = {0: "ERROR", 1: "FAIL", 2: "WARN", 3: "PASS"}


def _result_to_dict(r: CheckResult) -> dict:
    return {
        "check_id": r.check_id,
        "name": r.name,
        "severity": _SEVERITY_NAME.get(r.severity, "UNKNOWN"),
        "message": r.message,
        "detail": r.detail,
        "duration_ms": round(r.duration_ms, 1),
    }


def _report_to_dict(r: ModReport) -> dict:
    return {
        "node_type": r.node_type,
        "mod_name": r.mod_name,
        "mod_category": r.mod_category,
        "healthy": r.healthy,
        "total": r.total,
        "passed": r.passed,
        "warnings": r.warnings,
        "failures": r.failures,
        "errors": r.errors,
        "duration_ms": round(r.duration_ms, 1),
        "results": [_result_to_dict(rr) for rr in r.results],
    }


class JSONReporter:
    """JSON 报告生成器"""

    def print_report(self, report: ModReport):
        """打印单个模组为 JSON"""
        print(json.dumps(_report_to_dict(report), ensure_ascii=False, indent=2))

    def save(self, reports: List[ModReport], filepath: str):
        """保存所有报告到 JSON 文件"""
        total = ValidationReport(reports=reports, total_mods=len(reports))
        for r in reports:
            total.healthy_mods += 1 if r.healthy else 0
            total.total_checks += r.total
            total.total_passed += r.passed
            total.total_warnings += r.warnings
            total.total_failures += r.failures
            total.total_errors += r.errors

        data = {
            "summary": {
                "total_mods": total.total_mods,
                "healthy_mods": total.healthy_mods,
                "total_checks": total.total_checks,
                "passed": total.total_passed,
                "warnings": total.total_warnings,
                "failures": total.total_failures,
                "errors": total.total_errors,
                "duration_ms": round(total.duration_ms, 1),
            },
            "reports": [_report_to_dict(r) for r in reports],
        }
        os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
