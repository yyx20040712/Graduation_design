"""
test_kw_input.py — 矿井水输入节点 KwInputNode 单元测试

覆盖:
  - 默认参数键/值
  - ParamDef 数量
  - water_quality 与 params 同步
  - TDS 不进入 water_quality
  - calculate() 结果维度包含 TDS 和水质键
  - to_dict() 保存 TDS
  - from_dict() 向后兼容旧数据
"""

from __future__ import annotations

import pytest
from mods.mod_manager import get_mod_manager
KwInputNode = get_mod_manager().load_mod("kw_input")
from models.base import WaterFlow, WaterQuality


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture
def node() -> KwInputNode:
    """创建默认的 KwInputNode 实例"""
    return KwInputNode()


@pytest.fixture
def dummy_flow() -> WaterFlow:
    """占位水流(KwInputNode 不使用上游流量)"""
    return WaterFlow()


@pytest.fixture
def dummy_quality() -> WaterQuality:
    """占位水质(KwInputNode 不使用上游水质)"""
    return WaterQuality()


# ═══════════════════════════════════════════════════════════════════
# 测试 1-3: 参数定义
# ═══════════════════════════════════════════════════════════════════

class TestDefaultParams:
    """测试 _default_params() 和 _build_param_defs()"""

    def test_default_params_keys(self):
        """_default_params() 返回 13 个键 (v5.3: 新增 Z_water_inlet/Z_ground/DN_inlet 高程参数)"""
        params = KwInputNode._default_params()
        expected_keys = {"Q_avg_daily", "Kz", "SS_in", "TDS", "pH", "COD",
                         "BOD5", "NH3N", "TN", "TP",
                         "Z_water_inlet", "Z_ground", "DN_inlet"}
        assert set(params.keys()) == expected_keys
        assert len(params) == 13

    def test_default_params_values(self):
        """默认值与规格一致"""
        params = KwInputNode._default_params()
        assert params["Q_avg_daily"] == 43835.6
        assert params["Kz"] == 1.5
        assert params["SS_in"] == 800
        assert params["TDS"] == 1500
        assert params["pH"] == 7.5
        assert params["COD"] == 200
        assert params["BOD5"] == 30.0
        assert params["NH3N"] == 8.0
        assert params["TN"] == 12.0
        assert params["TP"] == 2.0

    def test_param_defs_count(self, node):
        """_build_param_defs() 返回 13 个 ParamDef 对象 (v5.3: 新增高程参数)"""
        defs = node.get_param_defs()
        assert len(defs) == 13


# ═══════════════════════════════════════════════════════════════════
# 测试 4-5: water_quality 同步
# ═══════════════════════════════════════════════════════════════════

class TestWaterQualitySync:
    """测试 water_quality 与 params 的同步逻辑"""

    def test_water_quality_sync(self, node):
        """__init__ 后 water_quality 从 params 取值"""
        assert node.water_quality.SS == node.get_param("SS_in")
        assert node.water_quality.COD == node.get_param("COD")
        assert node.water_quality.pH == node.get_param("pH")
        # 验证具体值
        assert node.water_quality.SS == 800.0
        assert node.water_quality.COD == 200.0
        assert node.water_quality.pH == 7.5

    def test_tds_not_in_water_quality(self, node):
        """TDS 在 _params 中但不在 water_quality 上"""
        assert "TDS" in node._params
        assert node.get_param("TDS") == 1500
        # TDS 不应是 WaterQuality 的属性
        assert not hasattr(node.water_quality, "TDS")


# ═══════════════════════════════════════════════════════════════════
# 测试 6-7: calculate() 结果维度
# ═══════════════════════════════════════════════════════════════════

class TestCalculateDimensions:
    """测试 calculate() 生成的结果维度"""

    def test_calculate_adds_tds_dimension(self, node, dummy_flow, dummy_quality):
        """calculate() 结果包含 '进水TDS' 维度"""
        result = node.calculate(dummy_flow, dummy_quality)
        assert "进水TDS" in result.dimensions
        assert result.dimensions["进水TDS"] == (1500.0, "mg/L")

    def test_calculate_has_water_quality_dims(self, node, dummy_flow, dummy_quality):
        """结果维度包含 BOD5, COD, SS, NH3N, TN, TP, pH"""
        result = node.calculate(dummy_flow, dummy_quality)
        dim_keys = set(result.dimensions.keys())
        for key in ["进水BOD5", "进水COD", "进水SS", "进水NH3N", "进水TN", "进水TP"]:
            assert key in dim_keys, f"Missing dimension: {key}"


# ═══════════════════════════════════════════════════════════════════
# 测试 8-9: 序列化与向后兼容
# ═══════════════════════════════════════════════════════════════════

class TestSerialization:
    """测试 to_dict() / from_dict() 序列化"""

    def test_to_dict_preserves_tds(self, node):
        """to_dict() 在 params 中保存 TDS"""
        d = node.to_dict()
        assert "TDS" in d["params"]
        assert d["params"]["TDS"] == 1500
        assert d["params"]["SS_in"] == 800
        assert d["params"]["pH"] == 7.5
        assert d["params"]["COD"] == 200

    def test_backward_compat(self):
        """from_dict() 处理旧格式数据(params 中缺少新键)时仍能正常创建节点"""
        old_data = {
            "id": "kw_input-test01",
            "type": "kw_input",
            "name": "矿井水输入",
            "category": "矿井水处理",
            "position": {"x": 100.0, "y": 200.0},
            "params": {
                "Q_avg_daily": 43835.6,
                "Kz": 1.5,
                "SS_in": 800,
                "COD": 200,
                "BOD5": 30,
                "NH3N": 8,
                "TN": 12,
                "TP": 2,
                "TDS": 1500,
                "pH": 7.5,
            },
            "removal_rates": {},
            "ports": {"input": [], "output": []},
            "cached_result": None,
            "state": "DIRTY",
        }
        node = KwInputNode.from_dict(old_data)
        assert node.node_id == "kw_input-test01"
        assert node.water_quality.SS == 800.0
        assert node.water_quality.COD == 200.0
        assert node.water_quality.pH == 7.5

    def test_set_water_quality_bidirectional(self, node):
        """set_water_quality() 双向同步 water_quality 和 _params"""
        node.set_water_quality(SS=1200.0, COD=300.0, pH=6.0)
        assert node.water_quality.SS == 1200.0
        assert node.get_param("SS_in") == 1200.0
        assert node.water_quality.COD == 300.0
        assert node.get_param("COD") == 300.0
        assert node.water_quality.pH == 6.0
        assert node.get_param("pH") == 6.0
        assert node.state.value == 2  # DIRTY
