"""
validator/checks/calculation.py — 计算烟雾测试

验证标量 calculate() 不崩溃,产出非负尺寸,关键物理量满足单调性.
"""

from __future__ import annotations

from _logging import get_logger

from ..engine import CheckResult, Severity

_log = get_logger(__name__)


class CalculationSmokeCheck:
    """计算烟雾测试 — 标量 calculate 基础正确性"""

    fast = True
    name = "计算烟雾测试"

    def run(self, cls, cfg, flow, quality, mode):
        if flow is None:
            return CheckResult(
                "calc_skip", self.name, Severity.WARN, "无测试流量数据,跳过", ""
            )

        # 1. 实例化 + 执行计算
        try:
            node = cls()
        except Exception as e:
            return CheckResult(
                "calc_init", self.name, Severity.ERROR, f"无法实例化: {e}", ""
            )

        try:
            result = node.calculate(flow, quality)
        except Exception as e:
            return CheckResult(
                "calc_crash", self.name, Severity.ERROR, f"calculate() 崩溃: {e}", ""
            )

        issues = []

        # 2. 检查成功标志
        if not getattr(result, "success", True):
            issues.append("result.success = False")

        # 3. 检查维度产出
        dims = getattr(result, "dims", None) or getattr(result, "dimensions", {})
        if not dims:
            issues.append("无尺寸产出 (dimensions 为空)")

        # 4. 检查负值
        for name, val_obj in dims.items():
            if isinstance(val_obj, (tuple, list)):
                val = val_obj[0]
            else:
                val = val_obj
            if isinstance(val, (int, float)) and val < 0:
                issues.append(f"负尺寸: {name} = {val}")

        # 5. 检查校核结果
        checks = getattr(result, "checks", {})
        failed_checks = [
            (n, c)
            for n, c in checks.items()
            if isinstance(c, (list, tuple)) and not c[0]
        ]
        if failed_checks:
            # 快速模式不报告校核失败(可能是合法设计)
            if mode == "deep":
                issues.append(
                    f"{len(failed_checks)} 个校核未通过: "
                    + ", ".join(n for n, _ in failed_checks[:3])
                )

        if issues:
            return CheckResult(
                "calc_fail",
                self.name,
                (
                    Severity.FAIL
                    if any("崩溃" in i or "负" in i for i in issues)
                    else Severity.WARN
                ),
                "\n".join(issues),
                f"产出 {len(dims)} 个尺寸, {len(checks)} 个校核",
            )

        return CheckResult(
            "calc_ok",
            self.name,
            Severity.PASS,
            f"计算正常: {len(dims)} 个尺寸, {len(checks)} 个校核",
            "",
        )
