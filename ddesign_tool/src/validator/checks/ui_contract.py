"""
validator/checks/ui_contract.py — UI 契约检查

检查 ParamDef 与 discretization.json 的一致性:
  - ParamDef 的默认值范围与 discretization 的 free/fixed 值一致
  - 自由参数在 ParamDef 中定义的 min/max 涵盖 discretization 中的值
"""

from __future__ import annotations

from _logging import get_logger

from ..engine import CheckResult, Severity

_log = get_logger(__name__)


class UIContractCheck:
    """UI 契约 — ParamDef 与 discretization 一致性"""

    fast = True
    name = "UI 契约"

    def run(self, cls, cfg, flow, quality, mode):
        issues = []

        # 1. 获取 ParamDef
        try:
            node = cls()
            param_defs = node._build_param_defs()
        except Exception as e:
            return CheckResult(
                "ui_params", self.name, Severity.WARN, f"无法获取 ParamDef: {e}", ""
            )

        param_map = {p.key: p for p in param_defs}
        free = cfg.get("free", {})
        fixed = cfg.get("fixed", {})

        # 2. 检查 fixed 参数: 值应在 ParamDef 允许范围内
        for key, val in fixed.items():
            pdef = param_map.get(key)
            if pdef is None:
                continue
            min_v = getattr(pdef, "min_val", None)
            max_v = getattr(pdef, "max_val", None)
            if min_v is not None and val < min_v:
                issues.append(f"fixed['{key}']={val} < ParamDef.min_val={min_v}")
            if max_v is not None and val > max_v:
                issues.append(f"fixed['{key}']={val} > ParamDef.max_val={max_v}")

        # 3. 检查 free 参数: 所有离散值应在 ParamDef 范围内
        for key, vals in free.items():
            if key in fixed:
                continue  # 已在 fixed 中,忽略 free
            pdef = param_map.get(key)
            if pdef is None:
                issues.append(
                    f"free['{key}'] 无对应的 ParamDef (可用: {list(param_map.keys())})"
                )
                continue
            if not isinstance(vals, list):
                continue
            min_v = getattr(pdef, "min_val", None)
            max_v = getattr(pdef, "max_val", None)
            if min_v is not None and any(v < min_v for v in vals):
                bad = [v for v in vals if v < min_v]
                issues.append(f"free['{key}'] 有值 {bad} < ParamDef.min_val={min_v}")
            if max_v is not None and any(v > max_v for v in vals):
                bad = [v for v in vals if v > max_v]
                issues.append(f"free['{key}'] 有值 {bad} > ParamDef.max_val={max_v}")

        # 4. 检查离散值数量 (≤4 建议)
        if mode == "deep":
            for key, vals in free.items():
                if isinstance(vals, list) and len(vals) > 4:
                    issues.append(f"free['{key}'] 有 {len(vals)} 个离散值 (建议 ≤4)")

        if issues:
            return CheckResult(
                "ui_contract",
                self.name,
                Severity.WARN if all("建议" in i for i in issues) else Severity.FAIL,
                f"{len(issues)} 个不一致",
                "\n".join(issues),
            )

        return CheckResult(
            "ui_ok",
            self.name,
            Severity.PASS,
            f"ParamDef ({len(param_defs)} params) 与 discretization 一致",
            "",
        )
