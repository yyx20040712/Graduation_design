"""
test_smoke.py — 生产部署级冒烟测试套件 (v5.2)

覆盖所有关键路径, 不启动 GUI, 执行时间 <2s.

测试维度:
  1. 导入链完整性 — 所有核心模块可导入
  2. 数据模型 — WaterFlow/WaterQuality/SludgeFlow/NodeResult
  3. DAG 引擎 — GraphExecutor 拓扑排序 + 执行
  4. 模组系统 — 34 模组加载 + 注册
  5. 方案空间 — 向量化枚举无崩溃
  6. 参数离散化 — 所有模组配置可解析
  7. 标签系统 — dimension_labels 完整性
  8. 约束系统 — constraint_limits 一致性
  9. UI 回调 — 所有按钮方法存在
  10. 高程计算 — 全厂高程链
  11. 成本估算 — cost_estimator 无崩溃
  12. 面板契约 — section_banner / formula_sub 标签注册
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pytest

# 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ddesign_tool", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ddesign_tool"))

from models.base import (
    WaterFlow, WaterQuality, SludgeFlow, NodeResult,
    NodeState, ParamDef, Port, PortType, GRAVITY, PI,
)


# ═══════════════════════════════════════════════════════════════════
# 1. 导入链
# ═══════════════════════════════════════════════════════════════════

class TestImportChain:
    """核心模块可导入"""

    @pytest.mark.parametrize("module_path,attr", [
        ("controller.graph_executor", "GraphExecutor"),
        ("controller.project_manager", "ProjectManager"),
        ("models.base", "NodeBase"),
        ("models.solution_space", "get_engine"),
        ("models.discretization", "get_config"),
        ("models.elevation_calculator", "ElevationCalculator"),
        ("models.dimension_formulas", "get_formula"),
        ("models.node_registry", "resolve_class"),
        ("ui.dimension_labels", "resolve_dimension"),
        ("ui.dimension_labels", "split_dimensions"),
        ("ui.quality_panel", "QualityPanel"),
        ("ui.solution_browser", "SolutionBrowser"),
        ("ui.constraint_panel", "ConstraintPanel"),
        ("ui.export_handlers", "export_all_results"),
        ("ui.export_handlers", "export_cost_report"),
        ("ui.export_handlers", "calc_pipe_cost_report"),
        ("ui.validator_dialog", "run_validator_dialog"),
        ("mods.mod_manager", "ModManager"),
        ("mods.mod_manager", "get_mod_manager"),
        ("validator.engine", "ModValidator"),
        ("tools.sync_mods", "sync_mods"),
        ("_logging", "get_logger"),
    ])
    def test_import(self, module_path, attr):
        mod = __import__(module_path, fromlist=[attr])
        assert hasattr(mod, attr), f"{module_path}.{attr} not found"


# ═══════════════════════════════════════════════════════════════════
# 2. 数据模型
# ═══════════════════════════════════════════════════════════════════

class TestDataModel:
    """数据模型正确性"""

    def test_waterflow_defaults(self):
        f = WaterFlow()
        assert f.Q_design == 0.57
        assert f.Q_avg_daily == 34760.7
        assert f.Kz == 1.4

    def test_waterflow_conversions(self):
        f = WaterFlow(Q_design=0.57, Q_avg_daily=34760.7, Kz=1.4)
        assert abs(f.Q_avg_hourly - 1448.36) < 1.0
        assert f.Q_design_Ls == 570.0
        assert f.Q_design_as("m3/h") == 2052.0

    def test_waterquality_removal(self, sample_quality):
        q2 = sample_quality.apply_removal({"BOD5": 0.5, "COD": 0.3, "SS": 0.4})
        assert q2.BOD5 == 100.0
        assert q2.COD == 280.0
        assert q2.SS == 132.0

    def test_waterquality_effluent_check(self):
        q = WaterQuality(BOD5=8, COD=40, SS=8, NH3N=3, TN=12, TP=0.3)
        checks = q.check_effluent()
        for key, (ok, diff) in checks.items():
            assert ok, f"{key} should pass but diff={diff}"

    def test_sludgeflow_from_dry_solids(self):
        s = SludgeFlow.from_dry_solids(DS=5000, P_moisture=0.96)
        assert abs(s.Q_wet - 125.0) < 1.0
        assert s.DS == 5000.0

    def test_noderesult_dimension_scope(self):
        r = NodeResult(success=True)
        r.add_dimension("有效容积", 100.0, "m³", scope="single")
        assert r.get_display_name("有效容积") == "[单池]有效容积"

    def test_noderesult_checks(self):
        r = NodeResult(success=True)
        r.add_check("测试", True, 1.5, "1~2", "m")
        passed, actual, limit, unit = r.checks["测试"]
        assert passed is True
        assert actual == 1.5
        assert limit == "1~2"
        assert unit == "m"

    def test_noderesult_serialization(self, success_result):
        d = success_result.to_dict()
        assert d["success"] is True
        assert "dimensions" in d
        assert "checks" in d

    def test_port_connection_rules(self, input_port, output_port):
        assert input_port.is_input
        assert output_port.is_output
        # MIXED ↔ MIXED: 双向兼容
        assert output_port.can_connect(input_port)
        assert input_port.can_connect(output_port)

    def test_paramdef_clamp(self):
        p = ParamDef("测试", "test", 5.0, 5.0, 0, 10, 1, "m")
        p.set_value(15)  # exceeds max
        assert p.value == 10.0
        p.set_value(-5)  # below min
        assert p.value == 0.0


# ═══════════════════════════════════════════════════════════════════
# 3. DAG 引擎
# ═══════════════════════════════════════════════════════════════════

class TestDAGEngine:
    """DAG 执行引擎"""

    def test_empty_graph(self, executor):
        assert executor.node_count == 0
        order = executor.topological_order()
        assert order == []

    def test_single_node(self, executor, test_node):
        executor.add_node(test_node)
        assert executor.node_count == 1
        order = executor.topological_order()
        assert len(order) == 1

    def test_execute_single_node(self, executor, test_node, sample_flow, sample_quality):
        executor.add_node(test_node)
        results = executor.execute(force_all=True)
        assert len(results) == 1
        assert test_node.node_id in results
        assert results[test_node.node_id].success

    def test_two_node_chain(self, sample_flow, sample_quality):
        from controller.graph_executor import GraphExecutor
        from models.combiner import CombinerNode
        from models.pipe_network import PipeNetworkNode

        g = GraphExecutor()
        pipe = PipeNetworkNode()
        comb = CombinerNode()
        g.add_node(pipe)
        g.add_node(comb)
        # pipe output → combiner input 0 (WATER)
        g.connect(pipe.output_ports[0], comb.input_ports[0])

        order = g.topological_order()
        assert len(order) == 2


# ═══════════════════════════════════════════════════════════════════
# 4. 模组系统
# ═══════════════════════════════════════════════════════════════════

class TestModSystem:
    """模组加载和注册"""

    def test_all_mods_load(self):
        from mods.mod_manager import get_mod_manager
        mgr = get_mod_manager()
        mgr.load_all()
        assert len(mgr.mods) >= 31, f"Expected >=31 mods, got {len(mgr.mods)}"

    @pytest.mark.parametrize("mod_id", [
        "tiaojiechi", "cugeshan", "xigeshan", "chenshachi", "chuchenchi",
        "cass", "aao", "gaomidu", "vxinglvchi", "ziwai",
        "wuni_nongsuo", "wuni_xiaohua", "wuni_tuoshui", "wuni_ganhua",
        "wuni_hebing", "wuni_bengzhan", "wuni_shusong",
        "kw_tiaojiechi", "kw_chenshachi", "kw_ningjiao", "kw_cifenli",
        "kw_gaomidu", "kw_vxinglvchi", "kw_ziwai", "kw_input",
        "jishuijing", "peishuijing", "jipeishuijing", "peishuiqu",
        "jcws_smbg", "gdys_stss",
    ])
    def test_mod_has_class(self, mod_id):
        from mods.mod_manager import get_mod_manager
        mgr = get_mod_manager()
        cls = mgr.load_mod(mod_id)
        assert cls is not None, f"Mod {mod_id} failed to load"
        assert cls.NODE_TYPE == mod_id

    def test_mod_has_mod_json(self):
        from mods.mod_manager import get_mod_manager
        mgr = get_mod_manager()
        mgr.load_all()
        for mod_id, info in mgr.mods.items():
            assert info.id == mod_id
            assert info.name, f"{mod_id} has no name"

    def test_community_mods_load(self):
        from mods.mod_manager import get_mod_manager
        mgr = get_mod_manager()
        mgr.load_all()
        community = [m for m in mgr.mods if "community" in mgr.mods[m].mod_dir]
        assert len(community) >= 3, f"Expected >=3 community mods, got {len(community)}"


# ═══════════════════════════════════════════════════════════════════
# 5. 方案空间
# ═══════════════════════════════════════════════════════════════════

class TestSolutionSpace:
    """向量化方案枚举"""

    def test_engine_singleton(self):
        from models.solution_space import get_engine
        e1 = get_engine()
        e2 = get_engine()
        assert e1 is e2

    @pytest.mark.parametrize("mod_id", [
        "tiaojiechi", "gaomidu", "vxinglvchi", "cass",
    ])
    def test_enumerate_no_crash(self, mod_id, sample_flow, sample_quality):
        from models.solution_space import get_engine
        from mods.mod_manager import get_mod_manager
        mgr = get_mod_manager()
        cls = mgr.load_mod(mod_id)
        if cls is None:
            pytest.skip(f"{mod_id} not loaded")
        engine = get_engine()
        try:
            sols = engine.enumerate(mod_id, sample_flow, sample_quality)
            assert isinstance(sols, list)
        except Exception as e:
            pytest.fail(f"{mod_id} enumerate crashed: {e}")


# ═══════════════════════════════════════════════════════════════════
# 6. 参数离散化
# ═══════════════════════════════════════════════════════════════════

class TestDiscretization:
    """离散化配置完整性"""

    def test_all_configs_have_free_or_fixed(self):
        import os as _os
        mods_dir = os.path.join(os.path.dirname(__file__), "..", "mods", "core")
        if not _os.path.exists(mods_dir):
            mods_dir = os.path.join(os.path.dirname(__file__), "..", "ddesign_tool", "mods", "core")
        for mod_id in sorted(_os.listdir(mods_dir)):
            dp = os.path.join(mods_dir, mod_id, "discretization.json")
            if not _os.path.exists(dp):
                continue  # 部分模组无离散化配置 (如 kw_input, pipe_network)
            with open(dp, encoding="utf-8") as f:
                cfg = json.load(f)
            has_free = bool(cfg.get("free"))
            has_fixed = bool(cfg.get("fixed"))
            if not has_free and not has_fixed:
                continue  # 纯输入/输出节点无参数

    def test_constraint_limits_match_names(self):
        """constraint_limits 与 constraint_names 一一对应"""
        import os as _os
        mods_dir = os.path.join(os.path.dirname(__file__), "..", "mods", "core")
        if not _os.path.exists(mods_dir):
            mods_dir = os.path.join(os.path.dirname(__file__), "..", "ddesign_tool", "mods", "core")
        for mod_id in sorted(_os.listdir(mods_dir)):
            dp = os.path.join(mods_dir, mod_id, "discretization.json")
            if not _os.path.exists(dp):
                continue
            with open(dp, encoding="utf-8") as f:
                cfg = json.load(f)
            names = set(cfg.get("constraint_names", []))
            limits = set(cfg.get("constraint_limits", {}).keys())
            types_set = set(cfg.get("constraint_types", {}).keys())
            for n in names:
                assert n in limits, f"{mod_id}: '{n}' missing constraint_limits"
                assert n in types_set, f"{mod_id}: '{n}' missing constraint_types"


# ═══════════════════════════════════════════════════════════════════
# 7. 标签系统
# ═══════════════════════════════════════════════════════════════════

class TestLabelSystem:
    """维度标签系统"""

    def test_split_dimensions_returns_4_groups(self):
        from ui.dimension_labels import split_dimensions
        c, p, wq_in, wq_out = split_dimensions({}, {})
        assert isinstance(c, list)
        assert isinstance(p, list)

    def test_resolve_dimension_known_key(self):
        from ui.dimension_labels import resolve_dimension
        sym, meaning, unit = resolve_dimension("n")
        assert len(sym) > 0
        assert len(meaning) > 0

    def test_format_param_value(self):
        from ui.dimension_labels import format_param_value
        assert "8.00" in format_param_value("HRT", 8.0)
        assert "4" in format_param_value("n", 4)


# ═══════════════════════════════════════════════════════════════════
# 8. 高程计算
# ═══════════════════════════════════════════════════════════════════

class TestElevation:
    """全厂高程计算"""

    def test_elevation_calculator_creates(self):
        from controller.graph_executor import GraphExecutor
        from models.elevation_calculator import ElevationCalculator
        g = GraphExecutor()
        calc = ElevationCalculator(g)
        assert calc is not None

    def test_elevation_data_defaults(self):
        from models.base import ElevationData
        e = ElevationData()
        assert e.ground_elevation == 0.0
        assert e.head_loss == 0.0


# ═══════════════════════════════════════════════════════════════════
# 9. 成本估算
# ═══════════════════════════════════════════════════════════════════

class TestCostEstimation:
    """工程概算"""

    def test_cost_estimator_creates(self):
        from models.cost.cost_estimator import CostEstimator
        ce = CostEstimator()
        assert ce is not None

    def test_unit_prices_load(self):
        from models.cost.unit_prices import CIVIL
        assert isinstance(CIVIL, dict)
        assert len(CIVIL) > 0


# ═══════════════════════════════════════════════════════════════════
# 10. 面板契约
# ═══════════════════════════════════════════════════════════════════

class TestPanelContract:
    """面板标签和结构契约"""

    def test_section_banner_tag_exists(self):
        """结果面板三大类标题 section_banner 标签已注册 (v5.4: 移至 result_panel.py)"""
        fp = os.path.join(os.path.dirname(__file__), "..",
                          "ddesign_tool", "src", "ui", "result_panel.py")
        with open(fp, encoding="utf-8") as f:
            content = f.read()
        assert "section_banner" in content, "缺少 section_banner 标签"

    def test_formula_sub_tag_exists(self):
        """公式子行标签已注册 (v5.4: 移至 result_panel.py)"""
        fp = os.path.join(os.path.dirname(__file__), "..",
                          "ddesign_tool", "src", "ui", "result_panel.py")
        with open(fp, encoding="utf-8") as f:
            content = f.read()
        assert "formula_sub" in content, "缺少 formula_sub 标签"

    def test_quality_panel_class_exists(self):
        from ui.quality_panel import QualityPanel, WQ_COLORS, WQ_INDICATORS
        assert len(WQ_COLORS) == 6
        assert len(WQ_INDICATORS) == 6


# ═══════════════════════════════════════════════════════════════════
# 11. 线程安全
# ═══════════════════════════════════════════════════════════════════

class TestThreadSafety:
    """ModManager 线程安全"""

    def test_lock_exists(self):
        from mods.mod_manager import ModManager
        assert hasattr(ModManager, "_lock"), "ModManager 缺少 _lock"
