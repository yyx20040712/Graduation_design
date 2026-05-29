"""
solution_space.py — 向量化网格搜索引擎

核心流程:
  1. build_grid() → 生成所有参数组合的 numpy 结构化数组
  2. 调用 NodeClass._vectorized_compute() → 返回维度+约束数组
  3. filter_feasible() → 布尔掩码过滤满足所有约束的组合
  4. rank_by_cost() → 按工程概算成本排序
  5. truncate() → 截断到 MAX_SOLUTIONS

术语:
  - combo: 一组自由参数取值 (如 n=4, HRT=6, h_eff=4.0, ratio=2.0)
  - feasible: 所有约束检查通过的 combo
  - Solution: 一个可行解,含参数、尺寸、校核结果、成本
"""

from __future__ import annotations

import json
import os

from _logging import get_logger

_log = get_logger(__name__)
from dataclasses import dataclass, field
from itertools import combinations
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from .base import WaterFlow, WaterQuality
from .discretization import (
    get_config,
    get_free_keys,
    get_free_values,
)

# ── 常量 ──
MAX_SOLUTIONS = 200  # 默认最大方案数

# ── 约束限值表 (v4.2: empty — 所有约束限值来自模组 discretization.json) ──
CONSTRAINT_LIMITS: Dict[str, str] = {}

# ── 运行时约束覆盖表(UI约束面板写入,优先级高于全局默认值)──
_constraint_overrides: Dict[str, Dict[str, str]] = (
    {}
)  # {node_type: {display_name: limit_str}}


# ═══════════════════════════════════════════════════════════════════
# 数据类
# ═══════════════════════════════════════════════════════════════════


@dataclass
class Solution:
    """单个可行解"""

    rank: int  # 排名 (1-based, 按成本升序)
    params: Dict[str, float]  # 参数 {key: value}
    dimensions: Dict[str, Any]  # 构筑物尺寸 {name: (value, unit)}
    checks: Dict[str, Any]  # 校核结果 {name: (passed, actual, limit, unit)}
    cost_wan_yuan: float = 0.0  # 工程概算成本 (万元)
    cost_breakdown: Dict[str, float] = field(default_factory=dict)  # 成本明细
    is_recommended: bool = False  # 是否为推荐方案 (成本最低)
    robustness: float = 0.0  # 约束安全裕度 (越大越远离边界)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rank": self.rank,
            "params": self.params,
            "dimensions": {
                k: list(v) if isinstance(v, tuple) else v
                for k, v in self.dimensions.items()
            },
            "checks": {
                k: list(v) if isinstance(v, tuple) else v
                for k, v in self.checks.items()
            },
            "cost_wan_yuan": self.cost_wan_yuan,
            "cost_breakdown": self.cost_breakdown,
            "is_recommended": self.is_recommended,
            "robustness": self.robustness,
        }

    @classmethod

    # ═══════════════ 反序列化 ═══════════════
    def from_dict(cls, d: Dict[str, Any]) -> "Solution":
        return cls(
            rank=d["rank"],
            params=d["params"],
            dimensions=d["dimensions"],
            checks=d["checks"],
            cost_wan_yuan=d.get("cost_wan_yuan", 0.0),
            cost_breakdown=d.get("cost_breakdown", {}),
            is_recommended=d.get("is_recommended", False),
            robustness=d.get("robustness", 0.0),
        )


# ═══════════════════════════════════════════════════════════════════
# 核心引擎
# ═══════════════════════════════════════════════════════════════════


class SolutionSpace:
    """可行域枚举引擎

    Usage:
        engine = SolutionSpace()
        solutions = engine.enumerate("tiaojiechi", flow, quality)
        # solutions 已按成本排序,solutions[0] 为推荐方案
    """

    def __init__(self, max_solutions: int = MAX_SOLUTIONS):
        self.max_solutions = max_solutions
        self._cache: Dict[str, List[Solution]] = {}
        self._diagnosed: set = set()  # 诊断去重: {(node_type, flow_hash)}

    # ── 公开 API ──

    def enumerate(
        self,
        node_type: str,
        flow: WaterFlow,
        quality: WaterQuality,
        force_recompute: bool = False,
    ) -> List[Solution]:
        """枚举某节点类型在当前流量/水质下的所有可行解

        Args:
            node_type: 节点类型 (如 "tiaojiechi")
            flow: 上游汇入的水量
            quality: 上游汇入的水质
            force_recompute: 是否强制重新计算(忽略缓存)

        Returns:
            可行解列表(按成本升序,最多 max_solutions 个)
        """
        cache_key = self._cache_key(node_type, flow, quality)
        if not force_recompute and cache_key in self._cache:
            return self._cache[cache_key]

        cfg = get_config(node_type)
        self._last_enumerated_type = node_type  # for _extract_checks override lookup
        free_keys = get_free_keys(node_type)
        free_vals = get_free_values(node_type)

        # 1. 构建网格
        grid = self._build_grid(free_keys, free_vals)

        # 2. 调用向量化计算
        results = self._compute_vectorized(node_type, grid, flow, quality, cfg["fixed"])

        # 3. 过滤可行解(传入 constraint_limits 以支持用户动态调节)
        feasible_mask = self._filter_feasible(
            results,
            cfg.get("constraint_keys", []),
            constraint_names=cfg.get("constraint_names", []),
            constraint_limits=cfg.get("constraint_limits", {}),
            node_type=node_type,
        )
        if feasible_mask.sum() == 0:
            self._log_no_solutions(node_type, flow, quality, results, cfg)
            return []

        feasible_results = results[feasible_mask]
        feasible_grid = {k: grid[k][feasible_mask] for k in free_keys}

        # 4. 计算成本
        costs = self._estimate_cost(node_type, feasible_results, feasible_grid, flow)

        # 5. 排序并截断
        sorted_idx = np.argsort(costs)
        n_show = min(len(sorted_idx), self.max_solutions)

        # 6. 构建 Solution 对象
        solutions = []
        for rank, idx in enumerate(sorted_idx[:n_show], 1):
            params = {k: feasible_grid[k][idx] for k in free_keys}
            for fk, fv in cfg["fixed"].items():
                params[fk] = fv

            dims = self._extract_dimensions(feasible_results, idx)
            checks = self._extract_checks(
                feasible_results,
                idx,
                cfg.get("constraint_keys", []),
                cfg.get("constraint_names", []),
                cfg.get("constraint_limits"),
            )
            cost = float(costs[idx])

            sol = Solution(
                rank=rank,
                params={
                    k: float(v) if isinstance(v, (np.floating, np.integer)) else v
                    for k, v in params.items()
                },
                dimensions=dims,
                checks=checks,
                cost_wan_yuan=cost,
                is_recommended=(rank == 1),
                robustness=_compute_robustness(checks),
            )
            solutions.append(sol)

        self._cache[cache_key] = solutions
        return solutions

    def enumerate_sludge(
        self,
        node_type: str,
        sludge: "SludgeFlow",
        force_recompute: bool = False,
    ) -> List[Solution]:
        """枚举污泥处理节点的可行方案空间

        与水处理 enumerate() 的区别: 输入为 SludgeFlow 而非 WaterFlow+WaterQuality.
        将污泥参数打包进 fixed 字典传递给 _vectorized_compute().
        """

        cfg = get_config(node_type)
        self._last_enumerated_type = node_type  # for _extract_checks override lookup
        free_keys = get_free_keys(node_type)
        free_vals = get_free_values(node_type)

        # 1. 构建网格
        grid = self._build_grid(free_keys, free_vals)

        # 2. 将 SludgeFlow 打包进 fixed
        fixed_with_sludge = dict(cfg.get("fixed", {}))
        fixed_with_sludge["_sludge_Q_wet"] = sludge.Q_wet
        fixed_with_sludge["_sludge_DS"] = sludge.DS
        fixed_with_sludge["_sludge_P"] = sludge.P_moisture
        fixed_with_sludge["_sludge_VS"] = sludge.VS_ratio

        # 3. 调用向量化计算 (dummy flow/quality, 实际数据在 fixed 中)
        dummy_flow = WaterFlow()
        dummy_quality = WaterQuality()
        results = self._compute_vectorized(
            node_type, grid, dummy_flow, dummy_quality, fixed_with_sludge
        )

        # 4. 过滤可行解(传入 constraint_limits 以支持用户动态调节)
        feasible_mask = self._filter_feasible(
            results,
            cfg.get("constraint_keys", []),
            constraint_names=cfg.get("constraint_names", []),
            constraint_limits=cfg.get("constraint_limits", {}),
            node_type=node_type,
        )
        if feasible_mask.sum() == 0:
            return []

        feasible_results = results[feasible_mask]
        feasible_grid = {k: grid[k][feasible_mask] for k in free_keys}

        # 5. 成本估算 (污泥模块暂用混凝土量)
        costs = self._estimate_cost(
            node_type, feasible_results, feasible_grid, dummy_flow
        )

        # 6. 排序并截断
        sorted_idx = np.argsort(costs)
        n_show = min(len(sorted_idx), self.max_solutions)
        sorted_idx = sorted_idx[:n_show]

        # 7. 组装 Solution 列表
        solutions = []
        for rank, idx in enumerate(sorted_idx, 1):
            params = {k: float(feasible_grid[k][idx]) for k in free_keys}
            dims = self._extract_dimensions(feasible_results, idx)
            checks = self._extract_checks(
                feasible_results,
                idx,
                cfg.get("constraint_keys", []),
                cfg.get("constraint_names", []),
                cfg.get("constraint_limits"),
            )
            cost = float(costs[idx])

            sol = Solution(
                rank=rank,
                params=params,
                dimensions=dims,
                checks=checks,
                cost_wan_yuan=cost,
                is_recommended=(rank == 1),
                robustness=_compute_robustness(checks),
            )
            solutions.append(sol)

        return solutions

    # ── 内部方法 ──

    # ═══════════════ UI 构建 ═══════════════
    def _build_grid(
        self, keys: List[str], values: List[List[float]]
    ) -> Dict[str, np.ndarray]:
        """生成笛卡尔积网格

        Returns:
            {key: np.ndarray of shape (N,)} 其中 N 为总组合数
        """
        meshes = np.meshgrid(*values, indexing="ij")
        return {k: mesh.ravel() for k, mesh in zip(keys, meshes)}

    # ═══════════════ 标签解析 ═══════════════
    def _resolve_node_class(self, node_type: str):
        """Auto-discover node class via unified registry (ModManager → compat fallback)."""
        if not hasattr(self, "_class_cache"):
            self._class_cache = {}
        if node_type in self._class_cache:
            return self._class_cache[node_type]

        from .node_registry import resolve_class

        cls = resolve_class(node_type)
        if cls is None:
            raise ValueError(f"不支持的节点类型: {node_type}")

        self._class_cache[node_type] = cls
        return cls

    # ═══════════════ 计算引擎 ═══════════════
    def _compute_vectorized(
        self,
        node_type: str,
        grid: Dict[str, np.ndarray],
        flow: WaterFlow,
        quality: WaterQuality,
        fixed: Dict[str, float],
    ) -> np.ndarray:
        """调用模块的 _vectorized_compute 类方法

        Returns:
            numpy 结构化数组,字段包含所有维度和约束标志
        """
        cls = self._resolve_node_class(node_type)

        # 调用 _vectorized_compute
        N = len(list(grid.values())[0])
        results = cls._vectorized_compute(grid, flow, quality, fixed)
        return results

    def _filter_feasible(
        self,
        results: np.ndarray,
        constraint_keys: List[str],
        constraint_names: List[str] | None = None,
        constraint_limits: dict | None = None,
        node_type: str | None = None,
    ) -> np.ndarray:
        """根据约束标志列过滤可行解

        当 constraint_limits 存在时,动态根据 val_* 字段 + 限值重新计算 ok,
        覆盖模组中硬编码的 ok_* 字段.这使得用户通过约束面板调整的限值生效.

        Args:
            results: 结构化数组,含 'ok_<key>' 和 'val_<key>' 字段
            constraint_keys: 约束键名列表 (如 ["LB_ratio", "HRT_actual"])
            constraint_names: 约束显示名列表 (如 ["长宽比 L/B", "实际 HRT"])
            constraint_limits: {display_name: "lo~hi"} 限值字典
            node_type: 节点类型,用于查找 _constraint_overrides

        Returns:
            bool 掩码数组 shape (N,)
        """
        # 合并 constraint_limits: 配置 + UI 运行时覆盖
        limits_source: dict = {}
        if constraint_limits:
            limits_source.update(constraint_limits)
        if node_type and node_type in _constraint_overrides:
            limits_source.update(_constraint_overrides[node_type])

        mask = np.ones(len(results), dtype=bool)
        for i, ckey in enumerate(constraint_keys):
            col_name = "ok_" + ckey
            if col_name not in results.dtype.names:
                continue

            # ── 动态限值检查: 当 constraint_limits 中有该约束的限值时 ──
            # 优先使用动态限值,覆盖模组硬编码的 ok_* 字段
            if limits_source and constraint_names and i < len(constraint_names):
                cname = constraint_names[i]
                limit_str = limits_source.get(cname, "")
                if limit_str:
                    val_col = "val_" + ckey
                    if val_col in results.dtype.names:
                        lo, hi = _parse_limit(limit_str)
                        if lo is not None or hi is not None:
                            val = results[val_col]
                            dynamic_ok = np.ones(len(results), dtype=bool)
                            if lo is not None:
                                dynamic_ok &= val >= lo
                            if hi is not None:
                                dynamic_ok &= val <= hi
                            # 若硬编码 ok_* 字段存在: 动态检查 OR 硬编码
                            # (硬编码通过但动态失败 → 约束有条件逻辑,信任硬编码)
                            if col_name in results.dtype.names:
                                dynamic_ok = dynamic_ok | results[col_name]
                            mask &= dynamic_ok
                            continue  # 使用动态检查,跳过硬编码 ok_*

            # ── 回退: 使用模组硬编码的 ok_* 字段 ──
            mask &= results[col_name]
        return mask

    def _log_no_solutions(
        self,
        node_type: str,
        flow: "WaterFlow",
        quality: "WaterQuality",
        results: np.ndarray,
        cfg: dict,
    ) -> None:
        """当枚举结果为空时,输出诊断日志帮助定位根因(相同流量+节点类型只诊断一次)"""
        # 去重: 相同 node_type + 流量组合只诊断一次, 防止启动时日志轰炸
        flow_key = (
            node_type,
            round(flow.Q_design, 4),
            round(flow.Q_avg_daily, 1),
            round(flow.Kz, 2),
        )
        if flow_key in self._diagnosed:
            return
        self._diagnosed.add(flow_key)

        constraint_keys = cfg.get("constraint_keys", [])
        constraint_names = cfg.get("constraint_names", [])
        total = len(results)

        _log.warning("=== 无可行方案诊断 [%s] ===", node_type)
        _log.warning(
            "  流量: Q_design=%.4f m³/s  Q_avg=%.1f m³/d  Kz=%.1f",
            flow.Q_design,
            flow.Q_avg_daily,
            flow.Kz,
        )
        _log.warning(
            "  水质: BOD5=%.0f COD=%.0f SS=%.0f NH3N=%.0f",
            quality.BOD5,
            quality.COD,
            quality.SS,
            quality.NH3N,
        )
        _log.warning("  组合总数: %d", total)

        # 零流量特殊诊断
        if flow.Q_design <= 0:
            _log.warning("  ⚠ 上游流量为 0 — 所有方案被零流量守卫拒绝")
            _log.warning("  → 可能原因: 节点未连接到有效的流量上游,或 F5 未执行")
            _log.warning("  → 建议: 先连接上游管网节点并执行 F5 计算")

        # 逐约束分析失败率
        for i, ckey in enumerate(constraint_keys):
            ok_field = "ok_" + ckey
            if ok_field in results.dtype.names:
                passed = int(results[ok_field].sum())
                name = constraint_names[i] if i < len(constraint_names) else ckey
                if passed < total:
                    _log.warning(
                        "  约束 [%s]: %d/%d 通过 (%d 失败, 通过率 %.0f%%)",
                        name,
                        passed,
                        total,
                        total - passed,
                        100.0 * passed / total if total > 0 else 0,
                    )

        # 检查是否有约束字段缺失
        for i, ckey in enumerate(constraint_keys):
            ok_field = "ok_" + ckey
            if ok_field not in results.dtype.names:
                name = constraint_names[i] if i < len(constraint_names) else ckey
                _log.error("  ❌ 约束字段缺失: %s (dtype中没有 %s)", name, ok_field)
                _log.error("     dtype 实际字段: %s", list(results.dtype.names))

        # ── v5.4-s7: 增强诊断 — 最小冲突集 + 约束提示 ──
        diag = self._diagnose_infeasibility(
            results, constraint_keys, constraint_names, cfg
        )
        conflict_set = diag.get("conflict_set", [])
        if conflict_set:
            _log.warning("  ⚡ 最小冲突集 (%d个约束无法同时满足):", len(conflict_set))
            for cname in conflict_set:
                hint = diag.get("hints", {}).get(cname, "")
                hint_str = f" → {hint}" if hint else ""
                _log.warning("    • %s%s", cname, hint_str)
        _log.warning("=== 诊断结束 ===")

    # ═══════════════ 无可行解诊断 (v5.4-s7 增强) ═══════════════

    def _diagnose_infeasibility(
        self,
        results: np.ndarray,
        constraint_keys: List[str],
        constraint_names: List[str],
        cfg: dict,
    ) -> dict:
        """无可行解时返回结构化诊断数据 (替代旧版 _suggest_relaxation)

        Returns:
            {
                "constraint_rates": [(name, passed, total), ...],  # 逐约束通过率
                "conflict_set": [name, ...],      # 最小冲突集
                "hints": {name: str, ...},         # 每约束的调整建议
            }
        """
        n_total = len(results)
        name_map = {
            ckey: constraint_names[i] if i < len(constraint_names) else ckey
            for i, ckey in enumerate(constraint_keys)
        }
        # 键名→中文名映射

        # ── 1. 逐约束通过率 ──
        constraint_rates = []
        for ckey in constraint_keys:
            ok_field = "ok_" + ckey
            if ok_field in results.dtype.names:
                passed = int(results[ok_field].sum())
                constraint_rates.append((name_map[ckey], passed, n_total))

        # ── 2. 最小冲突集 ──
        conflict_set_keys = self._find_minimal_conflict_set(
            results, constraint_keys
        )
        conflict_set = [name_map.get(ck, ck) for ck in conflict_set_keys]

        # ── 3. 约束提示 ──
        hints = self._build_constraint_hints(
            constraint_keys, constraint_names, results, cfg
        )

        return {
            "constraint_rates": constraint_rates,
            "conflict_set": conflict_set,
            "hints": hints,
        }

    def _find_minimal_conflict_set(
        self,
        results: np.ndarray,
        constraint_keys: List[str],
    ) -> List[str]:
        """找到最小的约束子集，去掉其中任意一个即可使方案可行

        贪心+枚举策略:
        1. 先尝试移除单个约束 (k=1)
        2. 无解则尝试移除 2 个
        3. 直到找到第一个可行组合

        复杂度: O(2^n) n≤10 完全可控
        """
        n_total = len(results)
        n_constraints = len(constraint_keys)

        # 预计算每个约束的 ok 布尔数组
        ok_arrays = {}
        for ckey in constraint_keys:
            ok_field = "ok_" + ckey
            if ok_field in results.dtype.names:
                ok_arrays[ckey] = results[ok_field].astype(bool)

        if not ok_arrays:
            return list(constraint_keys)

        # 从 k=1 开始尝试
        for k in range(1, n_constraints + 1):
            for combo in combinations(range(n_constraints), k):
                mask = np.ones(n_total, dtype=bool)
                for i, ckey in enumerate(constraint_keys):
                    if i in combo:
                        continue  # 跳过此约束
                    if ckey in ok_arrays:
                        mask &= ok_arrays[ckey]
                if mask.any():
                    return [constraint_keys[i] for i in combo]

        return list(constraint_keys)  # 所有约束都必须去掉

    def _build_constraint_hints(
        self,
        constraint_keys: List[str],
        constraint_names: List[str],
        results: np.ndarray,
        cfg: dict,
    ) -> dict:
        """为每个约束构建调整建议

        优先级:
          1. discretization.json 中的 constraint_hints 字段 (精确建议)
          2. 基于约束名和参数名的启发式推断
          3. 通用回退建议
        """
        hints = {}
        limits = cfg.get("constraint_limits", {})

        # 加载用户自定义的 constraint_hints
        user_hints = cfg.get("constraint_hints", {})

        for i, ckey in enumerate(constraint_keys):
            cname = constraint_names[i] if i < len(constraint_names) else ckey

            # 优先使用用户自定义提示
            if cname in user_hints:
                hints[cname] = user_hints[cname].get(
                    "hint", "请调整相关设计参数"
                )
                continue

            # 启发式推断: 从约束名提取关键词, 匹配 free 参数
            ok_field = "ok_" + ckey
            val_field = "val_" + ckey

            if ok_field not in results.dtype.names:
                hints[cname] = "建议检查约束配置或放宽限值"
                continue

            passed = int(results[ok_field].sum())
            n_total = len(results)
            if passed == n_total:
                hints[cname] = "✓ 通过"
                continue

            # 分析失败方向
            if val_field in results.dtype.names:
                median_val = float(np.median(results[val_field]))
                limit_str = limits.get(cname, "")
                lo, hi = _parse_limit(limit_str) if limit_str else (None, None)

                # 根据约束名和失败方向推断
                hint = self._infer_hint_from_name(
                    cname, median_val, lo, hi, cfg
                )
                hints[cname] = hint
            else:
                hints[cname] = "建议调整对应参数或放宽约束限值"

        return hints

    @staticmethod
    def _infer_hint_from_name(
        cname: str, median_val: float, lo, hi, cfg: dict
    ) -> str:
        """从约束中文名推断调整建议 (启发式)"""
        free_keys = list(cfg.get("free", {}).keys())
        fixed_keys = list(cfg.get("fixed", {}).keys())
        all_params = free_keys + fixed_keys

        # ── 通用模式: 根据约束名中的关键词匹配参数 ──
        HINT_PATTERNS = [
            # (约束关键词, 参数匹配词, 调整方向, 建议模板)
            (["长宽比", "L/B"], ["n", "ratio_LB"], "调整池数或长宽比参数"),
            (["宽高比", "B/H"], ["n", "H_max", "h_eff"], "调整池数或水深"),
            (["径深比", "D/h"], ["n", "h_eff", "h2"], "增大池径或减小水深"),
            (["HRT", "停留时间"], ["n", "HRT", "h_eff"], "增大池数或水深"),
            (["滤速", "v_q"], ["n", "v_filter"], "增加格数或降低设计滤速"),
            (["堰负荷", "堰口"], ["n", "L_out", "L_in"], "增加堰长或池数"),
            (["表面负荷", "q_surf"], ["n", "q_surf"], "增大池面积"),
            (["固体通量", "固体负荷"], ["n", "q_solid"], "增大沉淀面积"),
            (["污泥龄", "θc", "SRT"], ["n", "theta_c", "X_MLSS"], "增大池数或污泥龄"),
            (["充水比", "λ"], ["lam", "H_max"], "调整充水比或池深"),
            (["安全距离"], ["H_max", "X_MLSS"], "增大池深或降低MLSS"),
            (["需氧量", "O2"], ["n", "Ns", "X_MLSS"], "检查负荷参数"),
            (["砂斗", "容积"], ["n", "D", "dr"], "增大池径或砂斗尺寸"),
            (["过栅流速", "v_grate"], ["n", "b"], "增加栅条间隙或格数"),
            (["紫外剂量", "D_UV"], ["n", "D_UV"], "增加灯管排数"),
            (["冲洗水", "η_w"], ["n", "v_filter", "T_filter"], "减少滤速或增加格数"),
            (["水头损失", "H_loss"], ["n"], "增加格数降低单格流速"),
            (["硝化"], ["n", "theta_c", "T_design"], "增大污泥龄"),
            (["浓度"], ["PAC_dose", "PAM_dose", "D_PAC"], "调整药剂投加量"),
        ]

        for keywords, param_hints, general in HINT_PATTERNS:
            if any(kw in cname for kw in keywords):
                # 尝试精确匹配参数名
                matched = [p for p in all_params if any(ph in p for ph in param_hints)]
                if matched:
                    params_str = "、".join(matched[:3])
                    hint = general.replace(
                        "调整", f"调整 {params_str}"
                    ) if "调整" in general else f"尝试调整 {params_str}"
                else:
                    hint = general
                # 附加数值信息
                if lo is not None and median_val < lo:
                    hint += f" (当前 {median_val:.1f} < 下限 {lo})"
                elif hi is not None and median_val > hi:
                    hint += f" (当前 {median_val:.1f} > 上限 {hi})"
                return hint

        # 无法推断
        if lo is not None and median_val < lo:
            return f"当前值 {median_val:.1f} 低于下限 {lo}, 建议调大相关参数"
        elif hi is not None and median_val > hi:
            return f"当前值 {median_val:.1f} 超过上限 {hi}, 建议调小相关参数"
        return "建议调整对应设计参数或放宽约束限值"

    # ── 保留旧接口兼容 ──
    def _suggest_relaxation(
        self,
        results: np.ndarray,
        constraint_keys: List[str],
        constraint_names: List[str],
        cfg: dict,
    ) -> str:
        """旧接口 — 委托给 _diagnose_infeasibility"""
        diag = self._diagnose_infeasibility(
            results, constraint_keys, constraint_names, cfg
        )
        conflict = diag.get("conflict_set", [])
        if conflict:
            parts = [f"最小冲突集: {', '.join(conflict)}"]
            for cname in conflict[:2]:
                hint = diag.get("hints", {}).get(cname, "")
                if hint:
                    parts.append(f"「{cname}」{hint}")
            return "; ".join(parts)
        return ""

    def _estimate_cost(
        self,
        node_type: str,
        results: np.ndarray,
        grid: Dict[str, np.ndarray],
        flow: WaterFlow,
    ) -> np.ndarray:
        """向量化成本估算

        Returns:
            1D float 数组 shape (N,) 单位: 万元
        """
        try:
            from .cost.fast_estimator import estimate_vectorized

            return estimate_vectorized(node_type, results, grid, flow)
        except ImportError:
            # 回退:基于混凝土量的简单估算
            if "concrete_m3" in results.dtype.names:
                return results["concrete_m3"] * 0.095  # ~950元/m³ → 万元
            return np.zeros(len(results))

    def _extract_dimensions(self, results: np.ndarray, idx: int) -> Dict[str, Any]:
        """从结构化数组中提取单个解的尺寸"""
        dims = {}
        # 所有 float 字段(非 ok_/val_/cost_ 前缀)都视为尺寸
        for name in results.dtype.names:
            if (
                name.startswith("ok_")
                or name.startswith("val_")
                or name.startswith("cost_")
            ):
                continue
            val = results[name][idx]
            if isinstance(val, np.floating):
                dims[name] = (float(val), "")
            elif isinstance(val, np.integer):
                dims[name] = (int(val), "")
            else:
                dims[name] = (val, "")
        return dims

    # ═══════════════ 状态检查 ═══════════════
    def _extract_checks(
        self,
        results: np.ndarray,
        idx: int,
        constraint_keys: List[str],
        constraint_names: List[str],
        constraint_limits: dict = None,
    ) -> Dict[str, Any]:
        """从结构化数组中提取单个解的校核结果

        当 constraint_limits 存在时,passed 标志根据 val_* 字段 + 限值动态计算,
        优先于模组硬编码的 ok_* 字段.这使得 UI 面板中的校核结果与用户调节的限值一致.
        """
        limits_source = {}
        if constraint_limits:
            limits_source.update(constraint_limits)
        node_type = getattr(self, "_last_enumerated_type", None)
        if node_type and node_type in _constraint_overrides:
            limits_source.update(_constraint_overrides[node_type])
        checks = {}
        for i, ckey in enumerate(constraint_keys):
            col_name = "ok_" + ckey
            display_name = constraint_names[i] if i < len(constraint_names) else ckey
            if col_name not in results.dtype.names:
                continue
            val_name = "val_" + ckey
            if val_name not in results.dtype.names:
                checks[display_name] = [bool(results[col_name][idx]), 0.0, "", ""]
                continue

            limit_str = limits_source.get(display_name, "")
            actual_val = float(results[val_name][idx])

            # ── 动态计算 passed: 优先使用 constraint_limits ──
            if limit_str:
                lo, hi = _parse_limit(limit_str)
                if lo is not None or hi is not None:
                    passed = True
                    if lo is not None and actual_val < lo:
                        passed = False
                    if hi is not None and actual_val > hi:
                        passed = False
                else:
                    passed = bool(results[col_name][idx])
            else:
                passed = bool(results[col_name][idx])

            checks[display_name] = [passed, actual_val, limit_str, ""]
        return checks

    # ── 缓存 ──

    def _cache_key(self, node_type: str, flow: WaterFlow, quality: WaterQuality) -> str:
        """生成缓存键"""
        q_str = f"Qd{flow.Q_design:.3f}_Qad{flow.Q_avg_daily:.0f}_Kz{flow.Kz:.1f}"
        wq_str = f"BOD{quality.BOD5:.0f}_COD{quality.COD:.0f}_SS{quality.SS:.0f}"
        return f"{node_type}|{q_str}|{wq_str}"

    # ═══════════════ 保存 ═══════════════
    def save_cache(self, filepath: str) -> None:
        """将当前缓存保存到 JSON 文件"""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        data = {k: [s.to_dict() for s in v] for k, v in self._cache.items()}
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ═══════════════ 初始化/加载 ═══════════════
    def load_cache(self, filepath: str) -> None:
        """从 JSON 文件加载缓存"""
        if not os.path.exists(filepath):
            return
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        self._cache = {k: [Solution.from_dict(s) for s in v] for k, v in data.items()}


# ═══════════════════════════════════════════════════════════════════
# 便捷函数
# ═══════════════════════════════════════════════════════════════════

_global_engine: Optional[SolutionSpace] = None


def get_engine() -> SolutionSpace:
    """获取全局 SolutionSpace 单例"""
    global _global_engine
    if _global_engine is None:
        _global_engine = SolutionSpace()
    return _global_engine

    # ═══════════════ 设置 ═══════════════


def set_constraint_limits(node_type: str, limits: Dict[str, str]) -> None:
    """运行时更新约束限值 — 写入全局覆盖表并清除缓存

    Args:
        node_type: 节点类型 (如 "tiaojiechi")
        limits: {display_name: limit_str} 如 {"长宽比 L/B": "1.0~2.0"}
    """
    global _constraint_overrides
    _constraint_overrides[node_type] = dict(limits)
    # 清除缓存以触发重新枚举
    engine = get_engine()
    keys_to_remove = [k for k in engine._cache if k.startswith(node_type + "|")]
    for k in keys_to_remove:
        del engine._cache[k]

    # ═══════════════ 查询/获取 ═══════════════


def get_constraint_limits(node_type: str) -> Dict[str, str]:
    """获取某节点类型的当前约束限值(含运行时覆盖)"""
    global _constraint_overrides
    if node_type in _constraint_overrides:
        return dict(_constraint_overrides[node_type])
    from .discretization import get_config

    try:
        cfg = get_config(node_type)
        return cfg.get("constraint_limits", {})
    except KeyError:
        return {}


def enumerate_solutions(
    node_type: str, flow: WaterFlow, quality: WaterQuality
) -> List[Solution]:
    """便捷函数:枚举水处理可行解"""
    return get_engine().enumerate(node_type, flow, quality)


def enumerate_sludge_solutions(node_type: str, sludge: "SludgeFlow") -> List[Solution]:
    """便捷函数:枚举污泥处理可行解"""
    return get_engine().enumerate_sludge(node_type, sludge)


# ═══════════════════════════════════════════════════════════════════
# 约束安全裕度计算
# ═══════════════════════════════════════════════════════════════════


def _parse_limit(limit_str: str) -> Tuple[Optional[float], Optional[float]]:
    """解析约束限值字符串 → (lower, upper)

    "2.5~5.0" → (2.5, 5.0)
    "<= 2.9" → (None, 2.9)
    ">= 0.5" → (0.5, None)
    "> 0" → (0.0, None)
    "< 5" → (None, 5.0)
    "1.5~3.0" → (1.5, 3.0)
    "< 10%" → (None, 10.0)
    """
    limit_str = limit_str.strip()
    # Two-sided: "low~high" or "low ~ high"
    if "~" in limit_str:
        parts = limit_str.replace(" ", "").split("~")
        try:
            lo = float(parts[0])
            hi = float(parts[1])
            return lo, hi
        except ValueError:
            return None, None
    # One-sided: "<=", ">=", "<", ">"
    for prefix, is_lower in [(">=", True), ("<=", False), (">", True), ("<", False)]:
        if limit_str.startswith(prefix):
            try:
                val = float(limit_str[len(prefix) :].replace("%", "").strip())
                return (val, None) if is_lower else (None, val)
            except ValueError:
                return None, None
    return None, None

    # ═══════════════ 计算引擎 ═══════════════


def _compute_robustness(checks: Dict[str, Any]) -> float:
    """计算约束安全裕度 — 加权综合评分

    对每个约束, 计算实际值到边界的归一化距离 (margin ∈ [0, 1]).
    综合评分 = 0.6 × min(margins) + 0.4 × mean(margins)
      - min(margins): 最紧约束决定基本安全度 (短板效应)
      - mean(margins): 整体平衡性用于区分相同短板的方案

    值越大表示方案越远离约束边界, 工程安全性越高.
    """
    margins = []
    for cn, (passed, actual, limit_str, unit) in checks.items():
        if not passed:
            continue
        lo, hi = _parse_limit(limit_str)
        if lo is None and hi is None:
            continue

        try:
            actual_f = float(actual)
        except (ValueError, TypeError):
            continue

        margin = None
        if lo is not None and hi is not None:
            span = hi - lo
            if span > 0:
                margin = min(actual_f - lo, hi - actual_f) / span
        elif hi is not None:
            if hi <= 0 and actual_f <= 0:
                margin = 0.3
            elif abs(hi) > 0.001:
                margin = max(0.0, (hi - actual_f) / abs(hi))
            else:
                margin = 1.0 if actual_f <= hi else 0.0
        elif lo is not None:
            if lo <= 0 and actual_f >= 0:
                margin = 0.3  # 布尔型: 满足即安全
            elif lo <= 0 and passed:
                # 实际值为负但检查通过 → 有补充措施(如圆柱段)
                margin = 0.1
            else:
                denom = max(abs(actual_f), abs(lo), 1.0)
                margin = max(0.0, (actual_f - lo) / denom)

        if margin is not None:
            margins.append(max(0.0, min(1.0, margin)))

    if not margins:
        return 0.0

    min_m = min(margins)
    avg_m = sum(margins) / len(margins)
    return 0.6 * min_m + 0.4 * avg_m
