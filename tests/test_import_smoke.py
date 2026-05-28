"""
test_import_smoke.py — 导入 + 初始化烟雾测试 (v5.4)

检测 agent 重构引入的隐蔽 Bug:
  - 缺少 import 语句 → ImportError
  - 属性初始化顺序错误 → AttributeError
  - numpy 类型泄漏 → JSON 序列化失败
  - 模块导入链完整性 → 全量 import 无异常
"""

from __future__ import annotations

import json
import os
import sys

import pytest

# 确保路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ddesign_tool", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ddesign_tool"))


class TestImportChain:
    """验证所有核心模块可独立导入"""

    MODULES = [
        ("models.base", "NodeBase, NodeResult, WaterFlow, WaterQuality"),
        ("models.solution_space", "SolutionSpace"),
        ("models.dimension_formulas", "get_dimension_category"),
        ("models.discretization", "get_allowed_values"),
        ("models.node_registry", "resolve_class"),
        ("controller.graph_executor", "GraphExecutor"),
        ("controller.project_manager", "ProjectManager"),
        ("_paths", "get_mods_dir, setup_import_paths"),
        ("_logging", "get_logger"),
        ("ui.app_state", "AppState"),
        ("ui.layout_engine", "sugiyama_layout"),
    ]

    @pytest.mark.parametrize("module,expected", MODULES)
    def test_module_imports(self, module, expected):
        """模块可导入且包含预期符号"""
        mod = __import__(module, fromlist=["*"])
        for name in expected.split(", "):
            assert hasattr(mod, name), f"{module} 缺少 {name}"


class TestJSONSerialization:
    """验证计算结果可 JSON 序列化 (防止 numpy 类型泄漏)"""

    def test_node_result_to_dict_json_serializable(self):
        """NodeResult.to_dict() 输出可 json.dumps"""
        from models.base import NodeResult

        r = NodeResult(success=True)
        r.add_dimension("测试尺寸", 1.5, "m")
        r.add_dimension("整数尺寸", 3, "座")
        r.add_check("测试约束", True, 1.5, "1.0~2.0", "m")
        r.add_check("失败约束", False, 0.5, ">= 1.0", "m")
        r.params = {"n": 4, "HRT": 6.0}

        d = r.to_dict()
        # 必须能 json.dumps, 无 TypeError
        json_str = json.dumps(d, ensure_ascii=False)
        assert len(json_str) > 0
        # 还原后检查类型
        restored = json.loads(json_str)
        assert restored["success"] is True
        assert "测试尺寸" in restored["dimensions"]

    def test_node_to_dict_json_serializable(self):
        """NodeBase.to_dict() 输出可 json.dumps"""
        from models.base import NodeBase

        node = NodeBase(node_id="test-01")
        node.set_param("n", 4)
        node._result = None
        d = node.to_dict()
        json_str = json.dumps(d, ensure_ascii=False)
        assert len(json_str) > 0

    def test_numpy_values_in_checks(self):
        """numpy.bool_ 和 numpy.int32 在 add_check 中被转换"""
        import numpy as np
        from models.base import NodeResult

        r = NodeResult(success=True)
        r.add_check("np_bool测试", np.bool_(True), np.float64(3.14), "1~5", "")
        r.add_check("np_int测试", True, np.int32(42), ">0", "个")

        d = r.to_dict()
        json_str = json.dumps(d, ensure_ascii=False)
        restored = json.loads(json_str)

        # 检查类型正确转换
        check1 = restored["checks"]["np_bool测试"]
        assert isinstance(check1[0], bool), f"expected bool, got {type(check1[0])}"
        assert isinstance(check1[1], float), f"expected float, got {type(check1[1])}"

    def test_numpy_values_in_dimensions(self):
        """numpy 类型在 add_dimension 中被转换为 Python 原生类型"""
        import numpy as np
        from models.base import NodeResult

        r = NodeResult(success=True)
        r.add_dimension("float测试", np.float64(3.14), "m")
        r.add_dimension("int测试", np.int32(5), "座")
        r.add_dimension("int64测试", np.int64(10), "个")

        d = r.to_dict()
        json.dumps(d, ensure_ascii=False)  # 不应抛异常

    def test_mod_calculate_produces_serializable_result(self):
        """每个模组的 calculate() 输出可完整 JSON 序列化"""
        from models.base import WaterFlow, WaterQuality
        from mods.mod_manager import get_mod_manager

        mgr = get_mod_manager()
        mgr.load_all()

        flow = WaterFlow(Q_design=0.57, Q_avg_daily=34760.7, Kz=1.4)
        quality = WaterQuality()
        errors = []

        for mod_id in sorted(mgr._mods.keys()):
            node_cls = mgr.load_mod(mod_id)
            if node_cls is None:
                continue
            try:
                node = node_cls()
                result = node.calculate(flow, quality)
                if result and result.success:
                    d = result.to_dict()
                    json.dumps(d, ensure_ascii=False)
            except TypeError as e:
                if "not JSON serializable" in str(e):
                    errors.append(f"{mod_id}: {e}")
            except Exception:
                pass  # 计算失败不在此测试范围

        assert errors == [], f"JSON 序列化失败: {errors}"


class TestPanelImport:
    """验证 UI 面板可独立导入 (不依赖 Tk 环境)"""

    def test_app_state_import(self):
        from ui.app_state import AppState

        s = AppState()
        assert s.browse_mode is True
        assert s.is_dirty is False

    def test_layout_engine_import(self):
        from ui.layout_engine import column_layout

        # 空输入
        assert column_layout([], {}, {}) == {}

        # 简单链: A→B→C (列式布局: A,B同列, C在下一列)
        positions = column_layout(
            ["A", "B", "C"],
            {"A": ["B"], "B": ["C"], "C": []},
            {"A": [], "B": ["A"], "C": ["B"]},
        )
        assert len(positions) == 3
        # A和B同列(y递增), C在下一列
        assert positions["A"][0] == positions["B"][0]
        assert positions["A"][1] < positions["B"][1]
        assert positions["B"][0] < positions["C"][0]

    def test_result_panel_import(self):
        from ui.result_panel import ResultPanel

        assert ResultPanel is not None

    def test_param_panel_import(self):
        from ui.param_panel import ParamPanel

        assert ParamPanel is not None
