"""
test_button_functions.py — 按钮回调 / 面板逻辑轻量测试 (v5.2)

不创建完整 GUI, 使用静态分析 + 轻量运行时检查.
"""
import ast
import os
import sys
import pytest

_SRC = os.path.join(os.path.dirname(__file__), "..", "..", "ddesign_tool", "src")
_TOOL = os.path.join(os.path.dirname(__file__), "..", "..", "ddesign_tool")
for p in [_SRC, _TOOL]:
    if p not in sys.path:
        sys.path.insert(0, p)

_FP = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ddesign_tool", "src", "ui", "main_window.py"))


def _ast():
    with open(_FP, encoding="utf-8") as f:
        return ast.parse(f.read())


def _mw_methods():
    methods = set()
    for node in ast.walk(_ast()):
        if isinstance(node, ast.ClassDef) and node.name == "MainWindow":
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    methods.add(item.name)
    return methods


# ── 静态分析: 所有按钮回调方法存在 ──

REQUIRED_METHODS = [
    "_on_calc_all", "_on_clear_cache", "_on_pipe_hydraulic",
    "_on_export_cost", "_on_export_all", "_on_calc_pipe_cost",
    "_on_validate_quick", "_on_validate_deep", "_on_toggle_mode",
    "_on_new", "_on_open", "_on_save", "_on_save_as", "_on_close",
    "_view_results", "_reset_params", "_add_node", "_delete_selected",
    "_populate_result_tree", "_show_water_quality_card",
    "_build_full_quality_flow", "_build_quality_table",
]


class TestAllCallbacksExist:
    """所有关键回调方法在 MainWindow 中定义"""
    _methods = _mw_methods()

    @pytest.mark.parametrize("method", REQUIRED_METHODS)
    def test_method_exists(self, method):
        assert method in self._methods, f"MainWindow 缺少方法: {method}"


# ── 运行时: 模块可导入, 类可创建 ──

class TestImportChain:
    """完整导入链可以加载"""

    def test_import_main_window(self):
        from ui.main_window import MainWindow
        assert MainWindow is not None

    def test_import_quality_panel(self):
        from ui.quality_panel import QualityPanel
        assert QualityPanel is not None

    def test_import_solution_browser(self):
        from ui.solution_browser import SolutionBrowser
        assert SolutionBrowser is not None

    def test_import_constraint_panel(self):
        from ui.constraint_panel import ConstraintPanel
        assert ConstraintPanel is not None

    def test_import_export_handlers(self):
        from ui.export_handlers import (
            export_all_results, export_cost_report, calc_pipe_cost_report,
        )
        assert callable(export_all_results)
        assert callable(export_cost_report)
        assert callable(calc_pipe_cost_report)

    def test_import_validator(self):
        from ui.validator_dialog import run_validator_dialog
        assert callable(run_validator_dialog)

    def test_import_graph_executor(self):
        from controller.graph_executor import GraphExecutor
        assert GraphExecutor is not None

    def test_import_mod_manager(self):
        from mods.mod_manager import ModManager
        assert ModManager is not None


# ── 运行时: 核心逻辑正确 ──

class TestCoreLogic:
    """核心计算逻辑冒烟测试"""

    def test_dag_executor_creates(self):
        from controller.graph_executor import GraphExecutor
        g = GraphExecutor()
        assert g.node_count == 0

    def test_dag_add_node(self):
        from controller.graph_executor import GraphExecutor
        from mods.mod_manager import get_mod_manager
        mgr = get_mod_manager()
        mgr.load_all()
        cls = mgr.get_node_class("tiaojiechi")
        assert cls is not None, "tiaojiechi mod not loaded"
        node = cls()
        g = GraphExecutor()
        g.add_node(node)
        assert g.node_count == 1

    def test_dag_topological_order(self):
        from controller.graph_executor import GraphExecutor
        from mods.mod_manager import get_mod_manager
        mgr = get_mod_manager()
        mgr.load_all()
        tjc_cls = mgr.get_node_class("tiaojiechi")
        assert tjc_cls is not None, "tiaojiechi mod not loaded"
        g = GraphExecutor()
        g.add_node(tjc_cls())
        order = g.topological_order()
        assert len(order) == 1

    def test_mod_manager_loads_all(self):
        from mods.mod_manager import get_mod_manager
        mgr = get_mod_manager()
        mgr.load_all()
        assert len(mgr.mods) >= 31

    def test_node_base_dimension_flow(self):
        from models.base import NodeResult
        r = NodeResult(success=True)
        r.add_dimension("测试", 1.5, "m")
        assert "测试" in r.dimensions
        assert r.dimensions["测试"] == (1.5, "m")

    def test_node_base_check_flow(self):
        from models.base import NodeResult
        r = NodeResult(success=True)
        r.add_check("测试约束", True, 1.5, "1~2", "m")
        assert "测试约束" in r.checks
        passed, actual, limit, unit = r.checks["测试约束"]
        assert passed is True
        assert actual == 1.5

    def test_water_flow_defaults(self):
        from models.base import WaterFlow
        f = WaterFlow()
        assert f.Q_design == 0.57
        assert f.Q_avg_daily == 34760.7

    def test_water_quality_removal(self):
        from models.base import WaterQuality
        q = WaterQuality(BOD5=200, COD=400, SS=220)
        q2 = q.apply_removal({"BOD5": 0.5, "COD": 0.3})
        assert q2.BOD5 == 100.0
        assert q2.COD == 280.0

    def test_solution_space_engine(self):
        from models.solution_space import get_engine
        engine = get_engine()
        assert engine is not None

    def test_sync_mods_tool(self):
        """sync_mods 工具可导入"""
        from tools.sync_mods import sync_mods
        assert callable(sync_mods)


# ── 面板契约 ──

class TestPanelContract:
    """面板数据契约 (不渲染 GUI, 测试数据结构)"""

    def test_split_dimensions_returns_4_groups(self):
        from ui.dimension_labels import split_dimensions
        dims = {}
        cats = {}
        c, p, wq_in, wq_out = split_dimensions(dims, cats)
        assert isinstance(c, list)
        assert isinstance(p, list)
        assert isinstance(wq_in, list)
        assert isinstance(wq_out, list)

    def test_resolve_dimension_finds_known_key(self):
        from ui.dimension_labels import resolve_dimension
        sym, meaning, unit = resolve_dimension("Q_design")
        assert len(sym) > 0
        assert len(meaning) > 0

    def test_format_param_value_float(self):
        from ui.dimension_labels import format_param_value
        result = format_param_value("HRT", 8.0)
        assert "8.00" in result

    def test_section_header_tag_registered(self):
        """section_banner 标签在代码中注册"""
        with open(_FP, encoding="utf-8") as f:
            content = f.read()
        assert "section_banner" in content, "缺少 section_banner 标签"
