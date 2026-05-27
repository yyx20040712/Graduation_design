"""
fast_estimator.py — 向量化工程成本快速估算 (v2 — 标准化输出契约)

基于 _vectorized_compute 输出的标准字段 L/B/D/H/concrete_m3 进行计算.
每个模组必须在输出 dtype 中包含这些标准字段(不需要的可设为 0).

标准契约:
  矩形池: L > 0, B > 0, H > 0, D = 0
  圆形池: D > 0, H > 0, L = 0, B = 0
  明渠/无结构: L > 0, B > 0, H = 0, D = 0
  仅设备: L = B = D = H = 0 (仅用 concrete_m3)
"""

from __future__ import annotations

from typing import Dict

import numpy as np

from _logging import get_logger

_log = get_logger(__name__)

from .unit_prices import (
    CIVIL,
    REBAR_FLOOR,
    REBAR_WALL,
    floor_t,
    wall_t,
)

# ═══════════════════════════════════════════════════════════════════
# 标准字段提取
# ═══════════════════════════════════════════════════════════════════


def _std_L(results):
    return (
        results.get("L")
        if hasattr(results, "get")
        else (
            results["L"] if "L" in results.dtype.names else np.zeros(results.shape[0])
        )
    )


def _std_B(results):
    return (
        results.get("B")
        if hasattr(results, "get")
        else (
            results["B"] if "B" in results.dtype.names else np.zeros(results.shape[0])
        )
    )


def _std_D(results):
    return (
        results.get("D")
        if hasattr(results, "get")
        else (
            results["D"] if "D" in results.dtype.names else np.zeros(results.shape[0])
        )
    )


def _std_H(results):
    return (
        results.get("H")
        if hasattr(results, "get")
        else (
            results["H"] if "H" in results.dtype.names else np.zeros(results.shape[0])
        )
    )


# ═══════════════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════════════


def estimate_vectorized(
    node_type: str,
    results: np.ndarray,
    grid: Dict[str, np.ndarray],
    flow,
) -> np.ndarray:
    """向量化成本估算 (土建+设备, 用于方案排序)

    Priority:
      1. discretization.json estimator_type → 详细土建计算(L/B/D/H 标准字段)
      2. concrete_m3 回退估算(所有模组通用)
    """
    N = results.shape[0] if hasattr(results, "shape") else 1
    civil = np.zeros(N)

    # 1. 详细土建计算(声明了 estimator_type 的模组)
    estimator = _get_estimator(node_type)
    if estimator is not None:
        civil = estimator(results, grid, flow)

    # 2. 回退: concrete_m3 简化估算
    if civil.sum() == 0 and "concrete_m3" in results.dtype.names:
        civil = results["concrete_m3"] * CIVIL["c30_wall"] / 10000.0

    # 3. 设备费
    equip = _estimate_equipment(node_type, grid)

    return civil + equip


# ═══════════════════════════════════════════════════════════════════
# 统一成本估算器(只使用标准字段 L/B/D/H)
# ═══════════════════════════════════════════════════════════════════


def _cost_rectangular(results, grid, flow):
    """矩形池 — 标准字段: L, B, H"""
    L = _std_L(results)
    B = _std_B(results)
    H = _std_H(results)
    n = grid.get("n", 1)
    if np.isscalar(n):
        n = np.full(len(L), n)

    # 明渠等 H=0 的结构只计算开挖
    mask_has_H = H > 0

    V_eff = L * B * H
    tw = np.where(mask_has_H, wall_t(V_eff), 0.0)
    tf = np.where(mask_has_H, floor_t(V_eff), 0.0)

    V_excav = (L + 2) * (B + 2) * (np.where(mask_has_H, H + tf + 0.5, 1.0)) * n * 1.2
    V_pad = np.where(mask_has_H, (L + 0.6) * (B + 0.6) * 0.1 * n, 0.0)
    V_floor = np.where(mask_has_H, L * B * tf * n, 0.0)
    V_wall = np.where(mask_has_H, 2 * (L + B) * (H - tf) * tw * n, 0.0)
    W_rebar = (V_floor * REBAR_FLOOR + V_wall * REBAR_WALL) / 1000
    A_wp = np.where(mask_has_H, (2 * (L + B) * (H - tf) + L * B) * n, 0.0)
    A_form = np.where(mask_has_H, (2 * (L + B) * (H - tf) + L * B) * n, 0.0)

    cost = (
        V_excav * CIVIL["excavation"]
        + V_pad * CIVIL["c15_pad"]
        + V_floor * CIVIL["c30_floor"]
        + V_wall * CIVIL["c30_wall"]
        + W_rebar * CIVIL["rebar"]
        + A_wp * CIVIL["waterproof_inner"]
        + A_form * CIVIL["formwork_wall"]
    )
    return cost / 10000.0


def _cost_circular(results, grid, flow):
    """圆形池 — 标准字段: D, H"""
    D = _std_D(results)
    H = _std_H(results)
    n = grid.get("n", 1)
    if np.isscalar(n):
        n = np.full(len(D), n)
    R = D / 2

    V_eff = np.pi * R**2 * H
    tw = wall_t(V_eff)
    tf = floor_t(V_eff)

    V_excav = np.pi * (R + 1) ** 2 * (H + tf + 0.5) * n * 1.3
    V_pad = np.pi * (R + 0.3) ** 2 * 0.1 * n
    V_floor = np.pi * R**2 * tf * n
    V_wall = 2 * np.pi * R * (H - tf) * tw * n
    W_rebar = (V_floor * REBAR_FLOOR + V_wall * REBAR_WALL) / 1000
    A_wp = (2 * np.pi * R * (H - tf) + np.pi * R**2) * n
    A_form = 2 * np.pi * R * (H - tf) * n

    cost = (
        V_excav * CIVIL["excavation"]
        + V_pad * CIVIL["c15_pad"]
        + V_floor * CIVIL["c30_floor"]
        + V_wall * CIVIL["c30_wall"]
        + W_rebar * CIVIL["rebar"]
        + A_wp * CIVIL["waterproof_inner"]
        + A_form * CIVIL["formwork_wall"]
    )
    return cost / 10000.0


# ═══════════════════════════════════════════════════════════════════
# 估算器路由(仅通过 discretization.json estimator_type)
# ═══════════════════════════════════════════════════════════════════

_ESTIMATOR_TYPES = {
    "rectangular": _cost_rectangular,
    "circular": _cost_circular,
}


def _get_estimator(node_type: str):
    """从 discretization.json 的 estimator_type 获取估算器"""
    try:
        from models.discretization import get_config

        cfg = get_config(node_type)
        est_type = cfg.get("estimator_type", "")
        if est_type:
            return _ESTIMATOR_TYPES.get(est_type)
    except Exception as e:
        _log.warning("operation failed: %s", e, exc_info=True)
    return None


# ═══════════════════════════════════════════════════════════════════
# 设备费估算
# ═══════════════════════════════════════════════════════════════════


def _estimate_equipment(node_type: str, grid: Dict[str, np.ndarray]) -> np.ndarray:
    """估算设备费 (万元/方案)"""
    from .unit_prices import EQUIPMENT

    N = len(list(grid.values())[0])
    equip_total = 0.0
    if node_type in EQUIPMENT:
        for en, (qty, up) in EQUIPMENT[node_type].items():
            equip_total += qty * up
    return np.full(N, equip_total)
