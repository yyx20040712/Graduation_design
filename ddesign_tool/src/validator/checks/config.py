"""
validator/checks/config.py — 配置完整性检查

检查 discretization.json 的字段完整性、命名规范、一致性.
"""

from __future__ import annotations

from _logging import get_logger

from ..engine import CheckResult, Severity

_log = get_logger(__name__)


class ConfigIntegrityCheck:
    """配置完整性 — 适用于所有模组,零模组特定逻辑"""

    fast = True
    name = "配置完整性"

    def run(self, cls, cfg, flow, quality, mode):
        errors = []

        # 1. 必需字段检查
        required = [
            "free",
            "fixed",
            "constraint_keys",
            "constraint_names",
            "constraint_limits",
            "constraint_types",
        ]
        for field in required:
            if field not in cfg:
                errors.append(f"缺少字段: {field}")

        if errors:
            return CheckResult(
                "cfg_fields", self.name, Severity.ERROR, "\n".join(errors), ""
            )

        # 2. free/fixed 不重叠
        free_keys = set(cfg.get("free", {}).keys())
        fixed_keys = set(cfg.get("fixed", {}).keys())
        overlap = free_keys & fixed_keys
        if overlap:
            return CheckResult(
                "cfg_overlap",
                self.name,
                Severity.WARN,
                f"参数同时在 free 和 fixed 中: {overlap}",
                "这些参数将只以 fixed 值参与计算,free 中的值被忽略",
            )

        # 3. constraint_keys 数量 = constraint_names 数量
        ck = cfg.get("constraint_keys", [])
        cn = cfg.get("constraint_names", [])
        if len(ck) != len(cn):
            return CheckResult(
                "cfg_ck_cn",
                self.name,
                Severity.ERROR,
                f"constraint_keys({len(ck)}) != constraint_names({len(cn)})",
                f"keys: {ck}\nnames: {cn}",
            )

        # 4. 每个 constraint_name 有对应的 constraint_limits
        limits = cfg.get("constraint_limits", {})
        missing_limits = [n for n in cn if n not in limits]
        if missing_limits:
            return CheckResult(
                "cfg_missing_limits",
                self.name,
                Severity.WARN,
                f"{len(missing_limits)} 个约束缺少 constraint_limits 条目",
                "\n".join(missing_limits),
            )

        # 5. constraint_types 与 constraint_names 匹配
        types = cfg.get("constraint_types", {})
        missing_types = [n for n in cn if n not in types]
        if missing_types and types:  # types 可以为空
            return CheckResult(
                "cfg_missing_types",
                self.name,
                Severity.WARN,
                f"{len(missing_types)} 个约束缺少 constraint_types 条目",
                "\n".join(missing_types),
            )

        # 6. free 列表非空且值合法
        for k, v in cfg.get("free", {}).items():
            if not isinstance(v, list):
                errors.append(f"free['{k}'] 不是列表: {type(v).__name__}")
            elif len(v) == 0:
                errors.append(f"free['{k}'] 为空列表")
            elif any(not isinstance(x, (int, float)) for x in v):
                errors.append(f"free['{k}'] 包含非数值: {v}")

        # 7. fixed 值类型检查
        for k, v in cfg.get("fixed", {}).items():
            if not isinstance(v, (int, float)):
                errors.append(f"fixed['{k}'] 不是数值: {type(v).__name__} = {v}")

        if errors:
            return CheckResult(
                "cfg_value", self.name, Severity.ERROR, "\n".join(errors), ""
            )

        return CheckResult(
            "cfg_ok",
            self.name,
            Severity.PASS,
            f"配置完整: {len(free_keys)} free, {len(fixed_keys)} fixed, {len(ck)} constraints",
            "",
        )
