"""
validator/checks/constraint.py — 约束一致性检查

检查硬编码 ok_* 边界与 discretization.json 中的 constraint_limits 是否一致.
这是发现双路径不同步 bug 的核心检查.
"""

from __future__ import annotations

import numpy as np
from _logging import get_logger

from ..engine import CheckResult, Severity

_log = get_logger(__name__)


def _parse_limit(limit_str: str):
    """解析约束限值字符串 → (lower, upper)"""
    limit_str = limit_str.strip()
    if not limit_str:
        return None, None
    if "~" in limit_str:
        parts = limit_str.replace(" ", "").split("~")
        try:
            return float(parts[0]), float(parts[1])
        except ValueError:
            return None, None
    for prefix, is_lower in [(">=", True), ("<=", False), (">", True), ("<", False)]:
        if limit_str.startswith(prefix):
            try:
                val = float(limit_str[len(prefix) :].replace("%", "").strip())
                return (val, None) if is_lower else (None, val)
            except ValueError:
                return None, None
    return None, None


class ConstraintConsistencyCheck:
    """约束一致性 — 硬编码 ok_* vs constraint_limits"""

    fast = True
    name = "约束一致性"

    def run(self, cls, cfg, flow, quality, mode):
        if flow is None:
            return CheckResult(
                "con_skip", self.name, Severity.WARN, "无测试流量数据,跳过", ""
            )

        if not hasattr(cls, "_vectorized_compute"):
            return CheckResult(
                "con_skip", self.name, Severity.WARN, "模组无 _vectorized_compute", ""
            )

        ckeys = cfg.get("constraint_keys", [])
        cnames = cfg.get("constraint_names", [])
        climits = cfg.get("constraint_limits", {})

        if not ckeys:
            return CheckResult("con_none", self.name, Severity.PASS, "无约束定义", "")

        # 构建最小网格
        grid = {}
        for k, v in cfg.get("free", {}).items():
            if k not in cfg.get("fixed", {}):
                grid[k] = np.array(v[:1], dtype=float)
        if not grid:
            return CheckResult(
                "con_skip", self.name, Severity.WARN, "无自由参数,无法构建测试网格", ""
            )

        try:
            results = cls._vectorized_compute(grid, flow, quality, cfg.get("fixed", {}))
        except Exception as e:
            return CheckResult(
                "con_crash",
                self.name,
                Severity.ERROR,
                f"_vectorized_compute 崩溃: {e}",
                "",
            )

        issues = []
        ok_count = 0
        for i, ckey in enumerate(ckeys):
            val_field = f"val_{ckey}"
            ok_field = f"ok_{ckey}"

            if val_field not in results.dtype.names:
                issues.append(
                    f"约束 '{ckey}': 缺少 val_{ckey} 字段 "
                    f"(dtype 中有: {list(results.dtype.names)[:8]}...)"
                )
                continue

            ok_count += 1
            cname = cnames[i] if i < len(cnames) else ckey
            limit_str = climits.get(cname, "")
            if not limit_str:
                continue

            lo, hi = _parse_limit(limit_str)
            if lo is None and hi is None:
                continue

            actual = float(results[val_field][0])

            # 动态计算 ok
            dynamic_ok = True
            if lo is not None and actual < lo:
                dynamic_ok = False
            if hi is not None and actual > hi:
                dynamic_ok = False

            # 硬编码 ok
            if ok_field in results.dtype.names:
                hardcoded_ok = bool(results[ok_field][0])
            else:
                hardcoded_ok = None

            if hardcoded_ok is not None and hardcoded_ok != dynamic_ok:
                issues.append(
                    f"约束 '{cname}': 硬编码 ok={hardcoded_ok}, "
                    f"动态检查 ok={dynamic_ok} "
                    f"(val={actual:.4g}, limit={limit_str})"
                )

        if issues:
            return CheckResult(
                "con_mismatch",
                self.name,
                Severity.FAIL,
                f"{len(issues)}/{ok_count} 个约束不一致",
                "\n".join(issues),
            )
        return CheckResult(
            "con_ok", self.name, Severity.PASS, f"{ok_count} 个约束均一致", ""
        )
