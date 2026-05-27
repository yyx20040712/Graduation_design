"""
validator/checks/vectorized.py — 向量化与标量计算一致性检查

验证 _vectorized_compute() 与 calculate() 产出相同的关键尺寸.
"""

from __future__ import annotations

import numpy as np
from _logging import get_logger

from ..engine import CheckResult, Severity

_log = get_logger(__name__)
# 通用关键尺寸映射: (向量化字段, 标量维度名, 容差)
DEFAULT_KEY_DIMS = [
    ("L", "单池长度 L", 0.05),
    ("B", "单池宽度 B", 0.05),
    ("V_actual", "单池有效容积", 1.0),
    ("HRT_actual", "设计 HRT", 0.1),
    ("ratio_actual", "长宽比 L/B", 0.05),
]


class VectorizedParityCheck:
    """向量化 vs 标量计算一致性"""

    fast = False  # 慢检查,仅 deep 模式
    name = "向量化对标量"

    def run(self, cls, cfg, flow, quality, mode):
        if flow is None:
            return CheckResult(
                "vec_skip", self.name, Severity.WARN, "无测试流量数据,跳过", ""
            )

        if not hasattr(cls, "_vectorized_compute"):
            return CheckResult(
                "vec_noimpl",
                self.name,
                Severity.WARN,
                "模组无 _vectorized_compute,跳过",
                "",
            )

        # 1. 标量计算 — 使用与网格相同的参数值
        try:
            node = cls()
            # 将网格首值同步到节点参数,确保标量与向量化输入一致
            for k, v in cfg.get("free", {}).items():
                if k not in cfg.get("fixed", {}) and isinstance(v, list) and v:
                    try:
                        node.set_param(k, v[0])
                    except (AttributeError, KeyError):
                        pass
            for k, v in cfg.get("fixed", {}).items():
                try:
                    node.set_param(k, v)
                except (AttributeError, KeyError):
                    pass
            scalar = node.calculate(flow, quality)
        except Exception as e:
            return CheckResult(
                "vec_scalar_crash", self.name, Severity.ERROR, f"标量计算崩溃: {e}", ""
            )

        if not getattr(scalar, "success", True):
            return CheckResult(
                "vec_scalar_fail",
                self.name,
                Severity.WARN,
                "标量计算返回 success=False,跳过对比",
                "",
            )

        # 2. 构建网格 (单组参数)
        grid = {}
        for k, v in cfg.get("free", {}).items():
            if k not in cfg.get("fixed", {}):
                grid[k] = np.array(v[:1], dtype=float)
        if not grid:
            return CheckResult(
                "vec_no_grid", self.name, Severity.WARN, "无自由参数,跳过", ""
            )

        # 3. 向量化计算
        try:
            results = cls._vectorized_compute(grid, flow, quality, cfg.get("fixed", {}))
            assert len(results) == 1
        except Exception as e:
            return CheckResult(
                "vec_crash",
                self.name,
                Severity.ERROR,
                f"_vectorized_compute 崩溃: {e}",
                "",
            )

        # 4. 逐字段对比
        scalar_dims = getattr(scalar, "dimensions", {})
        mismatches = []

        for vec_field, scalar_name, tolerance in DEFAULT_KEY_DIMS:
            if vec_field not in results.dtype.names:
                continue

            vec_val = float(results[vec_field][0])

            # 在标量维度中查找匹配名称
            scalar_val = None
            for name, val_obj in scalar_dims.items():
                if scalar_name in name or name == vec_field:
                    if isinstance(val_obj, (tuple, list)):
                        scalar_val = val_obj[0]
                    else:
                        scalar_val = val_obj
                    break

            if scalar_val is None:
                continue

            if isinstance(scalar_val, (int, float)):
                diff = abs(vec_val - scalar_val)
                if diff > tolerance:
                    mismatches.append(
                        f"{vec_field}: vec={vec_val:.4g}, scalar={scalar_val:.4g}, "
                        f"diff={diff:.4g} (tol={tolerance})"
                    )

        if mismatches:
            return CheckResult(
                "vec_mismatch",
                self.name,
                Severity.FAIL,
                f"{len(mismatches)} 个字段不一致",
                "\n".join(mismatches[:10]),
            )

        return CheckResult(
            "vec_ok",
            self.name,
            Severity.PASS,
            f"关键尺寸一致 (对比了 {len(DEFAULT_KEY_DIMS)} 个字段)",
            "",
        )
