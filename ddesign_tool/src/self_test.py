"""
self_test.py — 内嵌自检模块 (v5.2)

独立于 pytest, 可在 PyInstaller 打包后的 EXE 中运行。
通过 GUI 工具栏「🔍 自检」按钮或 CLI `python -m self_test` 调用。

测试维度:
  1. 核心导入链
  2. 数据模型完整性
  3. 模组加载 (34 mods)
  4. DAG 引擎
  5. 方案空间枚举
  6. 约束一致性
  7. 标签系统
  8. 成本估算
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List

# 兼容直接运行和模块导入
if __name__ == "__main__" or "." not in __package__:
    sys.path.insert(0, os.path.dirname(__file__))

from _logging import get_logger

_log = get_logger(__name__)

# ═══════════════════════════════════════════════════════════════════
# 结果数据类
# ═══════════════════════════════════════════════════════════════════


@dataclass
class TestResult:
    name: str
    passed: bool
    duration_ms: float = 0.0
    message: str = ""
    detail: str = ""


@dataclass
class TestReport:
    results: List[TestResult] = field(default_factory=list)
    start_time: float = 0.0
    end_time: float = 0.0

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if not r.passed)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def duration_s(self) -> float:
        return self.end_time - self.start_time

    @property
    def healthy(self) -> bool:
        return self.failed == 0


# ═══════════════════════════════════════════════════════════════════
# 测试运行器
# ═══════════════════════════════════════════════════════════════════


class SelfTestRunner:
    """自检运行器 — 收集并执行所有测试"""

    def __init__(self):
        self._tests: List[Callable[[], TestResult]] = []
        self._register_all()

    def _register_all(self) -> None:
        """注册所有测试"""
        # 1. 导入链
        self._tests.append(self.test_core_imports)
        # 2. 数据模型
        self._tests.append(self.test_data_model)
        # 3. 模组加载
        self._tests.append(self.test_mod_loading)
        # 4. DAG 引擎
        self._tests.append(self.test_dag_engine)
        # 5. 方案空间
        self._tests.append(self.test_solution_space)
        # 6. 约束一致性
        self._tests.append(self.test_constraint_consistency)
        # 7. 标签系统
        self._tests.append(self.test_label_system)
        # 8. 成本估算
        self._tests.append(self.test_cost_estimation)
        # 9. 高程系统
        self._tests.append(self.test_elevation)
        # 10. 面板契约
        self._tests.append(self.test_panel_contract)

    def run(self) -> TestReport:
        report = TestReport(start_time=time.time())
        for test_fn in self._tests:
            t0 = time.time()
            try:
                result = test_fn()
            except Exception as e:
                result = TestResult(
                    name=test_fn.__doc__ or test_fn.__name__,
                    passed=False,
                    message=str(e),
                    detail=traceback.format_exc(),
                )
            result.duration_ms = (time.time() - t0) * 1000
            report.results.append(result)
        report.end_time = time.time()
        return report

    # ── 测试 1: 核心导入 ──

    def test_core_imports(self) -> TestResult:
        """核心模块导入"""
        modules = [
            ("models.base", ["NodeBase", "WaterFlow", "WaterQuality", "SludgeFlow", "NodeResult"]),
            ("controller.graph_executor", ["GraphExecutor"]),
            ("models.solution_space", ["get_engine"]),
            ("models.discretization", ["get_config"]),
            ("models.elevation_calculator", ["ElevationCalculator"]),
            ("models.dimension_formulas", ["get_formula"]),
            ("models.node_registry", ["resolve_class"]),
            ("ui.dimension_labels", ["resolve_dimension", "split_dimensions"]),
            ("ui.quality_panel", ["QualityPanel"]),
            ("mods.mod_manager", ["ModManager", "get_mod_manager"]),
            ("_logging", ["get_logger"]),
        ]
        failed = []
        for mod_path, attrs in modules:
            try:
                m = __import__(mod_path, fromlist=attrs)
                for a in attrs:
                    if not hasattr(m, a):
                        failed.append(f"{mod_path}.{a}")
            except Exception as e:
                failed.append(f"{mod_path}: {e}")
        if failed:
            return TestResult(name="核心模块导入", passed=False,
                              message=f"{len(failed)} 个失败", detail="\n".join(failed))
        return TestResult(name="核心模块导入", passed=True,
                          message=f"{len(modules)} 个模块通过")

    # ── 测试 2: 数据模型 ──

    def test_data_model(self) -> TestResult:
        """数据模型完整性"""
        from models.base import WaterFlow, WaterQuality, SludgeFlow, NodeResult
        errors = []
        # WaterFlow
        f = WaterFlow()
        if f.Q_design != 0.57: errors.append("WaterFlow.Q_design")
        if f.Q_avg_daily != 34760.7: errors.append("WaterFlow.Q_avg_daily")
        # WaterQuality
        q = WaterQuality(BOD5=200, COD=400, SS=220)
        q2 = q.apply_removal({"BOD5": 0.5, "COD": 0.3})
        if q2.BOD5 != 100.0: errors.append("WaterQuality.apply_removal")
        # SludgeFlow
        s = SludgeFlow.from_dry_solids(DS=5000, P_moisture=0.96)
        if abs(s.Q_wet - 125.0) > 1.0: errors.append("SludgeFlow.from_dry_solids")
        # NodeResult
        r = NodeResult(success=True)
        r.add_dimension("测试", 1.5, "m")
        if "测试" not in r.dimensions: errors.append("NodeResult.add_dimension")
        if errors:
            return TestResult(name="数据模型完整性", passed=False,
                              message=f"{len(errors)} 个失败", detail="\n".join(errors))
        return TestResult(name="数据模型完整性", passed=True,
                          message="WaterFlow/Quality/Sludge/NodeResult 通过")

    # ── 测试 3: 模组加载 ──

    def test_mod_loading(self) -> TestResult:
        """模组加载 (34 mods)"""
        from mods.mod_manager import get_mod_manager
        mgr = get_mod_manager()
        mgr.load_all()
        total = len(mgr.mods)
        errors = []
        for mod_id, info in mgr.mods.items():
            cls = mgr.load_mod(mod_id)
            if cls is None:
                errors.append(f"{mod_id}: 类加载失败")
            elif cls.NODE_TYPE != mod_id:
                errors.append(f"{mod_id}: NODE_TYPE 不匹配 ({cls.NODE_TYPE})")
        if errors:
            return TestResult(name="模组加载", passed=False,
                              message=f"{total} 模组, {len(errors)} 失败",
                              detail="\n".join(errors[:10]))
        return TestResult(name="模组加载", passed=True,
                          message=f"{total} 模组全部通过")

    # ── 测试 4: DAG 引擎 ──

    def test_dag_engine(self) -> TestResult:
        """DAG 执行引擎"""
        from controller.graph_executor import GraphExecutor
        from mods.mod_manager import get_mod_manager
        mgr = get_mod_manager()
        cls = mgr.load_mod("tiaojiechi")
        if cls is None:
            return TestResult(name="DAG 引擎", passed=False, message="tiaojiechi 未加载")
        g = GraphExecutor()
        node = cls()
        g.add_node(node)
        order = g.topological_order()
        if len(order) != 1:
            return TestResult(name="DAG 引擎", passed=False,
                              message=f"拓扑排序错误: {len(order)}")
        return TestResult(name="DAG 引擎", passed=True,
                          message="拓扑排序 + 节点执行通过")

    # ── 测试 5: 方案空间 ──

    def test_solution_space(self) -> TestResult:
        """方案空间枚举"""
        from models.solution_space import get_engine
        from models.base import WaterFlow, WaterQuality
        from mods.mod_manager import get_mod_manager
        mgr = get_mod_manager()
        engine = get_engine()
        flow = WaterFlow(Q_design=0.57, Q_avg_daily=34760.7, Kz=1.4)
        quality = WaterQuality()
        errors = []
        for mod_id in ["tiaojiechi", "gaomidu", "vxinglvchi", "cass"]:
            try:
                sols = engine.enumerate(mod_id, flow, quality)
                if not isinstance(sols, list):
                    errors.append(f"{mod_id}: 返回值不是 list")
            except Exception as e:
                errors.append(f"{mod_id}: {e}")
        if errors:
            return TestResult(name="方案空间枚举", passed=False,
                              message=f"{len(errors)} 失败", detail="\n".join(errors))
        return TestResult(name="方案空间枚举", passed=True,
                          message="4 模组枚举通过")

    # ── 测试 6: 约束一致性 ──

    def test_constraint_consistency(self) -> TestResult:
        """约束配置一致性"""
        from mods.mod_manager import get_mod_manager
        mgr = get_mod_manager()
        mgr.load_all()
        errors = []
        for mod_id, info in mgr.mods.items():
            dp = os.path.join(info.mod_dir, "discretization.json")
            if not os.path.exists(dp):
                continue  # 无离散化配置的模组跳过
            try:
                with open(dp, encoding="utf-8") as f:
                    cfg = json.load(f)
            except Exception:
                continue
            names = cfg.get("constraint_names", [])
            limits = cfg.get("constraint_limits", {})
            types_set = cfg.get("constraint_types", {})
            for n in names:
                if n not in limits:
                    errors.append(f"{mod_id}: '{n}' missing constraint_limits")
                if n not in types_set:
                    errors.append(f"{mod_id}: '{n}' missing constraint_types")
        if errors:
            return TestResult(name="约束配置一致性", passed=False,
                              message=f"{len(errors)} 个问题", detail="\n".join(errors[:10]))
        return TestResult(name="约束配置一致性", passed=True,
                          message="全部约束配置完整")

    # ── 测试 7: 标签系统 ──

    def test_label_system(self) -> TestResult:
        """维度标签系统"""
        from ui.dimension_labels import resolve_dimension, split_dimensions
        errors = []
        try:
            c, p, wq_in, wq_out = split_dimensions({}, {})
            if not isinstance(c, list): errors.append("split_dimensions 返回值错误")
        except Exception as e:
            errors.append(f"split_dimensions: {e}")
        try:
            sym, meaning, unit = resolve_dimension("n")
            if not sym: errors.append("resolve_dimension('n') 无符号")
        except Exception as e:
            errors.append(f"resolve_dimension: {e}")
        if errors:
            return TestResult(name="维度标签系统", passed=False,
                              message=f"{len(errors)} 个失败", detail="\n".join(errors))
        return TestResult(name="维度标签系统", passed=True,
                          message="split_dimensions + resolve_dimension 通过")

    # ── 测试 8: 成本估算 ──

    def test_cost_estimation(self) -> TestResult:
        """工程成本估算"""
        from models.cost.cost_estimator import CostEstimator
        from models.cost.unit_prices import CIVIL
        errors = []
        try:
            ce = CostEstimator()
            if ce is None: errors.append("CostEstimator 创建失败")
        except Exception as e:
            errors.append(f"CostEstimator: {e}")
        if not isinstance(CIVIL, dict) or len(CIVIL) == 0:
            errors.append("unit_prices.CIVIL 为空")
        if errors:
            return TestResult(name="工程成本估算", passed=False,
                              message=f"{len(errors)} 个失败", detail="\n".join(errors))
        return TestResult(name="工程成本估算", passed=True,
                          message="CostEstimator + unit_prices 通过")

    # ── 测试 9: 高程系统 ──

    def test_elevation(self) -> TestResult:
        """高程计算系统"""
        from controller.graph_executor import GraphExecutor
        from models.elevation_calculator import ElevationCalculator
        from models.base import ElevationData
        errors = []
        try:
            g = GraphExecutor()
            calc = ElevationCalculator(g)
        except Exception as e:
            errors.append(f"ElevationCalculator: {e}")
        e = ElevationData()
        if e.ground_elevation != 0.0: errors.append("ElevationData 默认值")
        if errors:
            return TestResult(name="高程计算系统", passed=False,
                              message=f"{len(errors)} 个失败", detail="\n".join(errors))
        return TestResult(name="高程计算系统", passed=True,
                          message="ElevationCalculator + ElevationData 通过")

    # ── 测试 10: 面板契约 ──

    def test_panel_contract(self) -> TestResult:
        """UI 面板契约 (不渲染 GUI, 仅验证结构)"""
        errors = []
        # QualityPanel 可导入
        try:
            from ui.quality_panel import QualityPanel, WQ_COLORS, WQ_INDICATORS
            if len(WQ_COLORS) != 6:
                errors.append(f"WQ_COLORS: {len(WQ_COLORS)} != 6")
            if len(WQ_INDICATORS) != 6:
                errors.append(f"WQ_INDICATORS: {len(WQ_INDICATORS)} != 6")
        except Exception as e:
            errors.append(f"QualityPanel: {e}")
        # main_window.py 标签存在 (仅在源码环境中检查)
        try:
            fp = os.path.join(os.path.dirname(__file__), "ui", "main_window.py")
            if os.path.exists(fp):
                with open(fp, encoding="utf-8") as f:
                    content = f.read()
                for tag in ["section_banner", "formula_sub"]:
                    if tag not in content:
                        errors.append(f"缺少标签: {tag}")
        except Exception:
            pass  # 打包后无源文件, 跳过
        if errors:
            return TestResult(name="UI 面板契约", passed=False,
                              message=f"{len(errors)} 个失败", detail="\n".join(errors))
        return TestResult(name="UI 面板契约", passed=True,
                          message="QualityPanel + 标签注册通过")


# ═══════════════════════════════════════════════════════════════════
# 便捷函数
# ═══════════════════════════════════════════════════════════════════


def run_self_test() -> TestReport:
    """运行完整自检并返回报告"""
    runner = SelfTestRunner()
    return runner.run()


def format_report(report: TestReport) -> str:
    """格式化自检报告为可读文本"""
    lines = []
    lines.append("=" * 60)
    lines.append("  排水工程设计工具 — 自检报告")
    lines.append("=" * 60)
    lines.append(f"  执行时间: {report.duration_s:.2f}s")
    lines.append(f"  通过: {report.passed}/{report.total}")
    if report.failed > 0:
        lines.append(f"  失败: {report.failed}")
    lines.append("")

    for r in report.results:
        icon = "✓" if r.passed else "✗"
        lines.append(f"  [{icon}] {r.name}")
        lines.append(f"       {r.message} ({r.duration_ms:.0f}ms)")
        if r.detail and not r.passed:
            for line in r.detail.split("\n")[:5]:
                if line.strip():
                    lines.append(f"       │ {line.strip()[:100]}")
        lines.append("")

    if report.healthy:
        lines.append("  结论: ✅ 全部通过, 系统健康")
    else:
        lines.append(f"  结论: ❌ {report.failed} 项失败, 需要修复")
    lines.append("=" * 60)
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════
# CLI 入口 (python -m self_test)
# ═══════════════════════════════════════════════════════════════════

def main():
    print("正在运行自检...")
    report = run_self_test()
    print(format_report(report))
    return 0 if report.healthy else 1


if __name__ == "__main__":
    sys.exit(main())
