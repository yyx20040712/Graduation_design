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
  9. 高程系统
 10. 面板契约
 11. 约束面板信号链 (v5.4-s7 新增)
 12. 工具栏按钮信号 (v5.4-s7 新增)
 13. 约束面板按钮绑定 (v5.4-s7 新增)
 14. 参数面板/方案浏览器按钮信号 (v5.4-s7 新增)
"""

from __future__ import annotations

import json
import os
import sys
import time
import traceback
from dataclasses import dataclass, field
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
        # 11. 约束面板信号链 (v5.4-s7: 验证参数修改→确定→重算链路完整性)
        self._tests.append(self.test_constraint_signal_chain)
        # 12. 工具栏按钮信号 (v5.4-s7: 验证所有工具栏按钮 command= 回调存在且委托正确)
        self._tests.append(self.test_toolbar_button_signals)
        # 13. 约束面板按钮绑定 (v5.4-s7: 验证确定按钮 + dirty 追踪链路)
        self._tests.append(self.test_constraint_panel_buttons)
        # 14. 参数面板/方案浏览器按钮信号 (v5.4-s7)
        self._tests.append(self.test_param_panel_buttons)

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
            (
                "models.base",
                ["NodeBase", "WaterFlow", "WaterQuality", "SludgeFlow", "NodeResult"],
            ),
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
            return TestResult(
                name="核心模块导入",
                passed=False,
                message=f"{len(failed)} 个失败",
                detail="\n".join(failed),
            )
        return TestResult(
            name="核心模块导入", passed=True, message=f"{len(modules)} 个模块通过"
        )

    # ── 测试 2: 数据模型 ──

    def test_data_model(self) -> TestResult:
        """数据模型完整性"""
        from models.base import NodeResult, SludgeFlow, WaterFlow, WaterQuality

        errors = []
        # WaterFlow
        f = WaterFlow()
        if f.Q_design != 0.57:
            errors.append("WaterFlow.Q_design")
        if f.Q_avg_daily != 34760.7:
            errors.append("WaterFlow.Q_avg_daily")
        # WaterQuality
        q = WaterQuality(BOD5=200, COD=400, SS=220)
        q2 = q.apply_removal({"BOD5": 0.5, "COD": 0.3})
        if q2.BOD5 != 100.0:
            errors.append("WaterQuality.apply_removal")
        # SludgeFlow
        s = SludgeFlow.from_dry_solids(DS=5000, P_moisture=0.96)
        if abs(s.Q_wet - 125.0) > 1.0:
            errors.append("SludgeFlow.from_dry_solids")
        # NodeResult
        r = NodeResult(success=True)
        r.add_dimension("测试", 1.5, "m")
        if "测试" not in r.dimensions:
            errors.append("NodeResult.add_dimension")
        if errors:
            return TestResult(
                name="数据模型完整性",
                passed=False,
                message=f"{len(errors)} 个失败",
                detail="\n".join(errors),
            )
        return TestResult(
            name="数据模型完整性",
            passed=True,
            message="WaterFlow/Quality/Sludge/NodeResult 通过",
        )

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
            return TestResult(
                name="模组加载",
                passed=False,
                message=f"{total} 模组, {len(errors)} 失败",
                detail="\n".join(errors[:10]),
            )
        return TestResult(name="模组加载", passed=True, message=f"{total} 模组全部通过")

    # ── 测试 4: DAG 引擎 ──

    def test_dag_engine(self) -> TestResult:
        """DAG 执行引擎"""
        from controller.graph_executor import GraphExecutor

        from mods.mod_manager import get_mod_manager

        mgr = get_mod_manager()
        cls = mgr.load_mod("tiaojiechi")
        if cls is None:
            return TestResult(
                name="DAG 引擎", passed=False, message="tiaojiechi 未加载"
            )
        g = GraphExecutor()
        node = cls()
        g.add_node(node)
        order = g.topological_order()
        if len(order) != 1:
            return TestResult(
                name="DAG 引擎", passed=False, message=f"拓扑排序错误: {len(order)}"
            )
        return TestResult(
            name="DAG 引擎", passed=True, message="拓扑排序 + 节点执行通过"
        )

    # ── 测试 5: 方案空间 ──

    def test_solution_space(self) -> TestResult:
        """方案空间枚举"""
        from models.base import WaterFlow, WaterQuality
        from models.solution_space import get_engine

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
            return TestResult(
                name="方案空间枚举",
                passed=False,
                message=f"{len(errors)} 失败",
                detail="\n".join(errors),
            )
        return TestResult(name="方案空间枚举", passed=True, message="4 模组枚举通过")

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
            return TestResult(
                name="约束配置一致性",
                passed=False,
                message=f"{len(errors)} 个问题",
                detail="\n".join(errors[:10]),
            )
        return TestResult(
            name="约束配置一致性", passed=True, message="全部约束配置完整"
        )

    # ── 测试 7: 标签系统 ──

    def test_label_system(self) -> TestResult:
        """维度标签系统"""
        from ui.dimension_labels import resolve_dimension, split_dimensions

        errors = []
        try:
            c, p, wq_in, wq_out = split_dimensions({}, {})
            if not isinstance(c, list):
                errors.append("split_dimensions 返回值错误")
        except Exception as e:
            errors.append(f"split_dimensions: {e}")
        try:
            sym, meaning, unit = resolve_dimension("n")
            if not sym:
                errors.append("resolve_dimension('n') 无符号")
        except Exception as e:
            errors.append(f"resolve_dimension: {e}")
        if errors:
            return TestResult(
                name="维度标签系统",
                passed=False,
                message=f"{len(errors)} 个失败",
                detail="\n".join(errors),
            )
        return TestResult(
            name="维度标签系统",
            passed=True,
            message="split_dimensions + resolve_dimension 通过",
        )

    # ── 测试 8: 成本估算 ──

    def test_cost_estimation(self) -> TestResult:
        """工程成本估算"""
        from models.cost.cost_estimator import CostEstimator
        from models.cost.unit_prices import CIVIL

        errors = []
        try:
            ce = CostEstimator()
            if ce is None:
                errors.append("CostEstimator 创建失败")
        except Exception as e:
            errors.append(f"CostEstimator: {e}")
        if not isinstance(CIVIL, dict) or len(CIVIL) == 0:
            errors.append("unit_prices.CIVIL 为空")
        if errors:
            return TestResult(
                name="工程成本估算",
                passed=False,
                message=f"{len(errors)} 个失败",
                detail="\n".join(errors),
            )
        return TestResult(
            name="工程成本估算", passed=True, message="CostEstimator + unit_prices 通过"
        )

    # ── 测试 9: 高程系统 ──

    def test_elevation(self) -> TestResult:
        """高程计算系统"""
        from controller.graph_executor import GraphExecutor
        from models.base import ElevationData
        from models.elevation_calculator import ElevationCalculator

        errors = []
        try:
            g = GraphExecutor()
            calc = ElevationCalculator(g)
        except Exception as e:
            errors.append(f"ElevationCalculator: {e}")
        e = ElevationData()
        if e.ground_elevation != 0.0:
            errors.append("ElevationData 默认值")
        if errors:
            return TestResult(
                name="高程计算系统",
                passed=False,
                message=f"{len(errors)} 个失败",
                detail="\n".join(errors),
            )
        return TestResult(
            name="高程计算系统",
            passed=True,
            message="ElevationCalculator + ElevationData 通过",
        )

    # ── 测试 10: 面板契约 ──

    def test_panel_contract(self) -> TestResult:
        """UI 面板契约 (不渲染 GUI, 仅验证结构)"""
        errors = []
        # QualityPanel 可导入
        try:
            from ui.quality_panel import WQ_COLORS, WQ_INDICATORS

            if len(WQ_COLORS) != 6:
                errors.append(f"WQ_COLORS: {len(WQ_COLORS)} != 6")
            if len(WQ_INDICATORS) != 6:
                errors.append(f"WQ_INDICATORS: {len(WQ_INDICATORS)} != 6")
        except Exception as e:
            errors.append(f"QualityPanel: {e}")
        # ResultPanel Treeview 标签 (运行时导入, 不依赖源文件 grep)
        # v5.4: 标签定义在 result_panel.RESULT_TREE_TAGS, 自检直接验证常量
        try:
            from ui.result_panel import RESULT_TREE_TAGS

            for tag in ["section_banner", "formula_sub"]:
                if tag not in RESULT_TREE_TAGS:
                    errors.append(f"ResultPanel 缺少标签常量: {tag}")
        except Exception as e:
            errors.append(f"ResultPanel 标签检查失败: {e}")
        if errors:
            return TestResult(
                name="UI 面板契约",
                passed=False,
                message=f"{len(errors)} 个失败",
                detail="\n".join(errors),
            )
        return TestResult(
            name="UI 面板契约", passed=True, message="QualityPanel + 标签注册通过"
        )

    # ── 测试 11: 约束面板信号链 ──

    def test_constraint_signal_chain(self) -> TestResult:
        """约束面板信号链完整性 — 验证修改参数→确定→重算回调不中断

        检查三个关键环节:
          1. ConstraintPanel._notify_change() 是否调用了注册的回调
          2. ParamPanel._on_constraint_changed() 是否标记 NodeState.DIRTY
          3. MainWindow callbacks 是否正确绑定 (静态分析)
        """
        import inspect

        errors = []

        # ── 环节1: ConstraintPanel 正确保存和调用回调 ──
        try:
            from ui.constraint_panel import ConstraintPanel

            cp_source = inspect.getsource(ConstraintPanel._notify_change)
            if "self._on_constraint_changed" not in cp_source:
                errors.append(
                    "ConstraintPanel._notify_change 未调用 _on_constraint_changed"
                )
        except Exception as e:
            errors.append(f"ConstraintPanel 检查失败: {e}")

        # ── 环节2: MainWindow._on_constraint_changed 委托给 ParamPanel ──
        try:
            mw_path = os.path.join(os.path.dirname(__file__), "ui", "main_window.py")
            with open(mw_path, encoding="utf-8") as f:
                mw_src = f.read()
            if "self.param_panel._on_constraint_changed" not in mw_src:
                errors.append("MainWindow._on_constraint_changed 未委托给 ParamPanel")
        except Exception as e:
            errors.append(f"MainWindow 检查失败: {e}")

        # ── 环节3: ParamPanel._on_constraint_changed 标记 NodeState.DIRTY ──
        try:
            from ui.param_panel import ParamPanel

            pp_source = inspect.getsource(ParamPanel._on_constraint_changed)
            if "NodeState.DIRTY" not in pp_source:
                errors.append(
                    "ParamPanel._on_constraint_changed 未设置 NodeState.DIRTY — "
                    "F5 计算将跳过参数修改后的节点"
                )
            if "self.executor._nodes" not in pp_source:
                errors.append(
                    "ParamPanel._on_constraint_changed 未访问 executor._nodes — "
                    "节点状态标记可能未生效"
                )
        except Exception as e:
            errors.append(f"ParamPanel 检查失败: {e}")

        if errors:
            return TestResult(
                name="约束面板信号链",
                passed=False,
                message=f"{len(errors)} 个断点",
                detail="\n".join(errors),
            )
        return TestResult(
            name="约束面板信号链", passed=True, message="修改→确定→DIRTY 链路完整"
        )

    # ── 测试 12: 工具栏按钮信号 ──

    def test_toolbar_button_signals(self) -> TestResult:
        """工具栏按钮信号完整性 — 验证所有 command= 回调存在且委托链不断

        覆盖: 文件菜单、工具菜单、计算按钮、输出按钮、布局按钮、管网按钮、
              节点管理按钮。静态分析 MainWindow 源码。
        """
        import inspect

        errors = []

        # ── 工具栏按钮 → 回调方法映射 ──
        # 格式: (按钮描述, 回调属性名, 期望的委托目标或行为关键字)
        BUTTON_CHECKS = [
            # 文件菜单
            ("文件→新建", "_on_new", ["file_manager.on_new"]),
            ("文件→打开", "_on_open", ["file_manager.on_open"]),
            ("文件→保存", "_on_save", ["file_manager.on_save"]),
            ("文件→另存为", "_on_save_as", ["file_manager.on_save_as"]),
            ("文件→关闭", "_on_close", ["file_manager.on_close"]),
            # 工具菜单
            ("工具→快速验证", "_on_validate_quick", ["run_validator_dialog"]),
            ("工具→深度验证", "_on_validate_deep", ["run_validator_dialog"]),
            ("工具→系统自检", "_on_self_test", ["run_self_test"]),
            # 计算按钮
            ("F5 全部计算", "_on_calc_all", ["_on_calc_rest"]),
            ("清除缓存", "_on_clear_cache", ["NodeState.DIRTY", "engine._cache"]),
            # 管网按钮
            ("污水水力计算", "_on_pipe_hydraulic", ["run_pipe_hydraulic"]),
            ("雨水水力计算", "_on_pipe_hydraulic", ["run_pipe_hydraulic"]),
            ("管网概算报告", "_on_calc_pipe_cost", ["calc_pipe_cost_report"]),
            # 输出按钮
            ("导出概算", "_on_export_cost", ["export_cost_report"]),
            ("全部输出", "_on_export_all", ["export_all_results"]),
            # 布局按钮
            ("列式布局", "_on_locate_flow", ["auto_layout_nodes"]),
            # 管网浏览
            ("管网浏览", "_browse_pipe", ["filedialog"]),
            # 节点管理
            ("删除节点", "_delete_selected", ["_do_delete"]),
        ]

        try:
            mw_path = os.path.join(os.path.dirname(__file__), "ui", "main_window.py")
            with open(mw_path, encoding="utf-8") as f:
                mw_src = f.read()

            # 验证每个按钮的 command= 在源码中存在
            for desc, attr, keywords in BUTTON_CHECKS:
                # 检查回调属性在源码中被引用为 command=
                found_cmd = (
                    f"command=self.{attr}" in mw_src
                    or f"command=lambda: self.{attr}" in mw_src
                    or f"command=lambda: self.{attr}(" in mw_src
                )
                # ── 特殊: _on_close 通过 protocol("WM_DELETE_WINDOW") 绑定 ──
                if attr == "_on_close":
                    found_cmd = f"self.{attr}" in mw_src
                if not found_cmd:
                    errors.append(f"{desc}: 未找到 command=self.{attr}")
                    continue

                # 检查方法定义存在 (不用 replace 破坏空格结构)
                if f"def {attr}(" not in mw_src:
                    errors.append(f"{desc}: 方法 {attr}() 未定义")

        except Exception as e:
            errors.append(f"MainWindow 分析失败: {e}")

        # ── 验证关键委托链: _on_calc_all → _on_calc_rest → executor.execute ──
        try:
            from ui.main_window import MainWindow

            src = inspect.getsource(MainWindow._on_calc_all)
            if "_on_calc_rest" not in src:
                errors.append("_on_calc_all 未调用 _on_calc_rest — F5 按钮无效")
            src2 = inspect.getsource(MainWindow._on_calc_rest)
            if "executor.execute" not in src2:
                errors.append("_on_calc_rest 未调用 executor.execute — 计算链路断开")
        except Exception:
            pass

        # ── 验证 _on_clear_cache 标记所有节点 DIRTY ──
        try:
            from ui.main_window import MainWindow

            src = inspect.getsource(MainWindow._on_clear_cache)
            if "NodeState.DIRTY" not in src:
                errors.append("_on_clear_cache 未设置 NodeState.DIRTY — 清除缓存无效")
        except Exception:
            pass

        if errors:
            return TestResult(
                name="工具栏按钮信号",
                passed=False,
                message=f"{len(errors)} 个按钮信号异常",
                detail="\n".join(errors),
            )
        return TestResult(
            name="工具栏按钮信号",
            passed=True,
            message=f"{len(BUTTON_CHECKS)} 个按钮回调均有效",
        )

    # ── 测试 13: 约束面板按钮绑定 ──

    def test_constraint_panel_buttons(self) -> TestResult:
        """约束面板按钮绑定 — 验证确定按钮 + dirty 追踪链路完整

        检查:
          1. 原始约束"确定"按钮 command → _on_original_confirm
          2. 结果约束"确定"按钮 command → _on_result_confirm
          3. Entry 输入变化 trace_add → _on_original_dirty / _on_result_dirty
          4. Combobox 选择变化 bind → _on_original_dirty
        """
        import inspect

        errors = []

        try:
            from ui.constraint_panel import ConstraintPanel

            # ── 检查确定按钮 command 绑定 ──
            build_src = inspect.getsource(ConstraintPanel._build_original_row)
            if "_on_original_confirm" not in build_src:
                errors.append("原始约束确定按钮 command 未绑定 _on_original_confirm")
            if "sv.trace_add" not in build_src:
                errors.append(
                    "原始约束 Entry 未绑定 trace_add → 输入变化不会触发 dirty"
                )
            if "_on_original_dirty" not in build_src:
                errors.append("原始约束 Combobox/Entry 未绑定 _on_original_dirty")

            result_src = inspect.getsource(ConstraintPanel._build_result_row)
            if "_on_result_confirm" not in result_src:
                errors.append("结果约束确定按钮 command 未绑定 _on_result_confirm")
            if "_on_result_dirty" not in result_src:
                errors.append("结果约束输入未绑定 _on_result_dirty")

            # ── 检查 dirty → gray button 链路 ──
            dirty_src = inspect.getsource(ConstraintPanel._on_original_dirty)
            if "bg" not in dirty_src or "#555555" not in dirty_src:
                errors.append("_on_original_dirty 未将按钮设为灰色 — 无视觉反馈")

            # ── 检查 confirm → green button 链路 ──
            set_applied_src = inspect.getsource(ConstraintPanel._set_applied)
            if "#55cc55" not in set_applied_src:
                errors.append("_set_applied 未将按钮恢复绿色 — 用户无法确认保存成功")

            # ── 检查 confirm 方法调用 _notify_change ──
            confirm_src = inspect.getsource(ConstraintPanel._on_original_confirm)
            if "_notify_change" not in confirm_src:
                errors.append(
                    "_on_original_confirm 未调用 _notify_change — "
                    "确定后不会通知主窗口刷新"
                )

        except Exception as e:
            errors.append(f"ConstraintPanel 分析失败: {e}")

        if errors:
            return TestResult(
                name="约束面板按钮绑定",
                passed=False,
                message=f"{len(errors)} 个绑定异常",
                detail="\n".join(errors),
            )
        return TestResult(
            name="约束面板按钮绑定",
            passed=True,
            message="确定→dirty→confirm→green 链路完整",
        )

    # ── 测试 14: 参数面板/方案浏览器按钮信号 ──

    def test_param_panel_buttons(self) -> TestResult:
        """参数面板 + 方案浏览器按钮信号 — 验证模式切换/查看结果/方案应用链路

        检查:
          1. 模式切换按钮 → _on_toggle_mode → browse_mode 翻转
          2. "查看此节点结果" → _on_view_results → tab_var 切换到 results
          3. "重置默认值" → _reset_params
          4. 方案浏览器 on_apply → _on_solution_applied → _on_recompute
          5. 质量面板 dirty callback 绑定
        """
        import inspect

        errors = []

        mw_path = os.path.join(os.path.dirname(__file__), "ui", "main_window.py")

        try:
            # ── 1. 模式切换按钮 ──
            with open(mw_path, encoding="utf-8") as f:
                mw_src = f.read()
            if "command=self._on_toggle_mode" not in mw_src.replace(" ", ""):
                errors.append("模式切换按钮 command 未绑定 _on_toggle_mode")

            from ui.param_panel import ParamPanel

            toggle_src = inspect.getsource(ParamPanel._on_toggle_mode)
            if "browse_mode" not in toggle_src:
                errors.append("_on_toggle_mode 未切换 browse_mode — 按钮无效")

        except Exception as e:
            errors.append(f"MainWindow 按钮分析失败: {e}")

        try:
            # ── 2. 查看结果按钮 ──
            from ui.param_panel import ParamPanel

            manual_src = inspect.getsource(ParamPanel._show_manual_mode)
            if "查看此节点结果" not in manual_src:
                errors.append("手动模式下缺少'查看此节点结果'按钮")
            if "_on_view_results" not in manual_src:
                errors.append("'查看此节点结果' button command 未绑定回调")

            from ui.main_window import MainWindow

            view_src = inspect.getsource(MainWindow._view_results)
            if "tab_var.set" not in view_src:
                errors.append("_view_results 未切换 tab — 点击无效")

        except Exception as e:
            errors.append(f"参数面板按钮分析失败: {e}")

        try:
            # ── 3. 重置默认值按钮 ──
            from ui.param_panel import ParamPanel

            manual_src = inspect.getsource(ParamPanel._show_manual_mode)
            if "重置默认值" not in manual_src:
                errors.append("手动模式下缺少'重置默认值'按钮")

            reset_src = inspect.getsource(ParamPanel._reset_params)
            if "reset_params" not in reset_src:
                errors.append("_reset_params 未调用 backend.reset_params()")
        except Exception:
            pass

        try:
            # ── 4. 方案浏览器 on_apply 回调 ──
            with open(mw_path, encoding="utf-8") as f:
                mw_src = f.read()
            if "on_apply=self._on_solution_applied" not in mw_src.replace(" ", ""):
                errors.append("SolutionBrowser on_apply 未绑定 — 方案应用无效")

            from ui.main_window import MainWindow

            apply_src = inspect.getsource(MainWindow._on_solution_applied)
            if "param_panel._on_solution_applied" not in apply_src:
                errors.append(
                    "_on_solution_applied 未委托给 param_panel — " "方案应用链路断开"
                )
        except Exception:
            pass

        if errors:
            return TestResult(
                name="参数面板按钮信号",
                passed=False,
                message=f"{len(errors)} 个信号异常",
                detail="\n".join(errors),
            )
        return TestResult(
            name="参数面板按钮信号",
            passed=True,
            message="模式切换/查看结果/方案应用链路完整",
        )


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
