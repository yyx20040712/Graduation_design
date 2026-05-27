"""
test_base.py — 核心数据模型单元测试

覆盖:
  - WaterFlow: 默认值、属性、单位转换、序列化、边界
  - WaterQuality: 默认值、去除率、出水标准检查、单位转换
  - NodeResult: 成功/失败、维度、校核、序列化
  - ParamDef: 创建、钳制、重置
  - Port: 创建、连接规则、序列化
  - NodeBase: 参数、状态转换、执行、序列化
  - 工具函数: ceil_to, round_to
"""

from __future__ import annotations

import pytest
import math
from models.base import (
    WaterFlow, WaterQuality, NodeResult, ParamDef,
    Port, PortType, NodeBase, NodeState,
    ceil_to, round_to, GRAVITY, WATER_QUALITY_ATTRS,
)


# ═══════════════════════════════════════════════════════════════════
# WaterFlow 测试
# ═══════════════════════════════════════════════════════════════════

class TestWaterFlow:
    """WaterFlow 数据类测试"""

    def test_default_values(self):
        """默认值匹配中期报告"""
        f = WaterFlow()
        assert f.Q_design == 0.57
        assert f.Q_avg_daily == 34760.7
        assert f.Kz == 1.4

    def test_custom_values(self):
        """自定义构造"""
        f = WaterFlow(Q_design=1.0, Q_avg_daily=50000.0, Kz=1.5)
        assert f.Q_design == 1.0
        assert f.Q_avg_daily == 50000.0
        assert f.Kz == 1.5

    def test_avg_hourly(self):
        """平均时流量 = 平均日流量 / 24"""
        f = WaterFlow(Q_avg_daily=34760.7)
        assert abs(f.Q_avg_hourly - 1448.3625) < 1e-4

    def test_avg_second(self):
        """平均秒流量 = 平均日流量 / 86400"""
        f = WaterFlow(Q_avg_daily=86400.0)
        assert f.Q_avg_second == 1.0

    def test_design_Ls(self):
        """设计流量 L/s = m³/s × 1000"""
        f = WaterFlow(Q_design=0.57)
        assert f.Q_design_Ls == 570.0

    def test_conversions_m3s(self):
        f = WaterFlow(Q_design=1.0)
        assert f.Q_design_as("m3/s") == 1.0

    def test_conversions_Ls(self):
        f = WaterFlow(Q_design=0.5)
        assert f.Q_design_as("L/s") == 500.0

    def test_conversions_m3h(self):
        f = WaterFlow(Q_design=1.0)
        assert f.Q_design_as("m3/h") == 3600.0

    def test_conversions_m3d(self):
        f = WaterFlow(Q_design=1.0)
        assert f.Q_design_as("m3/d") == 86400.0

    def test_conversions_invalid_unit(self):
        f = WaterFlow()
        with pytest.raises(ValueError, match="不支持的单位"):
            f.Q_design_as("gpm")

    def test_serialization_roundtrip(self):
        f = WaterFlow(Q_design=0.8, Q_avg_daily=50000.0, Kz=1.5)
        d = f.to_dict()
        f2 = WaterFlow.from_dict(d)
        assert f2.Q_design == 0.8
        assert f2.Q_avg_daily == 50000.0
        assert f2.Kz == 1.5

    def test_from_dict_partial(self):
        """部分字段缺失时使用默认值"""
        f = WaterFlow.from_dict({"Q_design": 2.0})
        assert f.Q_design == 2.0
        assert f.Q_avg_daily == 34760.7  # 默认值
        assert f.Kz == 1.4  # 默认值

    def test_zero_flow_edge_case(self, zero_flow):
        """零流量边界 - 属性计算不应崩溃"""
        assert zero_flow.Q_design == 0.0
        assert zero_flow.Q_avg_hourly == 0.0
        assert zero_flow.Q_avg_second == 0.0
        assert zero_flow.Q_design_Ls == 0.0


# ═══════════════════════════════════════════════════════════════════
# WaterQuality 测试
# ═══════════════════════════════════════════════════════════════════

class TestWaterQuality:
    """WaterQuality 数据类测试"""

    def test_default_values(self):
        """默认浓度匹配中期报告表3-1"""
        q = WaterQuality()
        assert q.BOD5 == 200.0
        assert q.COD == 400.0
        assert q.SS == 220.0
        assert q.NH3N == 35.0
        assert q.TN == 45.0
        assert q.TP == 5.0
        assert q.pH == 7.0

    def test_apply_removal_full(self, sample_quality):
        """全去除率应用"""
        rates = {"BOD5": 0.92, "COD": 0.88, "SS": 0.70}
        out = sample_quality.apply_removal(rates)
        assert out.BOD5 == pytest.approx(200.0 * 0.08)  # 8% 剩余
        assert out.COD == pytest.approx(400.0 * 0.12)
        assert out.SS == pytest.approx(220.0 * 0.30)

    def test_apply_removal_partial(self, sample_quality):
        """部分去除率(只指定部分指标)"""
        rates = {"BOD5": 0.5}
        out = sample_quality.apply_removal(rates)
        assert out.BOD5 == 100.0
        assert out.COD == 400.0  # 未指定,保持不变
        assert out.SS == 220.0

    def test_apply_removal_zero(self, sample_quality):
        """零去除率"""
        out = sample_quality.apply_removal({})
        assert out.BOD5 == sample_quality.BOD5
        assert out.COD == sample_quality.COD

    def test_apply_removal_full_removal(self, sample_quality):
        """100% 去除率"""
        rates = {"BOD5": 1.0, "COD": 1.0}
        out = sample_quality.apply_removal(rates)
        assert out.BOD5 == 0.0
        assert out.COD == 0.0

    def test_check_effluent_pass(self, clean_quality):
        """达标的出水"""
        results = clean_quality.check_effluent()
        for key, (passed, _diff) in results.items():
            assert passed, f"{key} should pass but didn't"

    def test_check_effluent_fail(self, sample_quality):
        """不达标的进水"""
        results = sample_quality.check_effluent()
        assert not results["BOD5"][0]  # 200 >> 10
        assert not results["COD"][0]   # 400 >> 50

    def test_check_effluent_boundary(self):
        """边界值 - 刚好达标"""
        q = WaterQuality(BOD5=10.0, COD=50.0, SS=10.0,
                         NH3N=5.0, TN=15.0, TP=0.5)
        results = q.check_effluent()
        for key, (passed, _) in results.items():
            assert passed, f"{key} at boundary should pass"

    def test_mgL_to_kgm3(self):
        assert WaterQuality.mgL_to_kgm3(1000.0) == 1.0
        assert WaterQuality.mgL_to_kgm3(200.0) == 0.2

    def test_kgm3_to_mgL(self):
        assert WaterQuality.kgm3_to_mgL(1.0) == 1000.0
        assert WaterQuality.kgm3_to_mgL(0.5) == 500.0

    def test_unit_conversion_roundtrip(self):
        val = 350.0
        assert WaterQuality.kgm3_to_mgL(
            WaterQuality.mgL_to_kgm3(val)) == val

    def test_serialization_roundtrip(self):
        q = WaterQuality(BOD5=250.0, COD=500.0, SS=300.0)
        d = q.to_dict()
        q2 = WaterQuality.from_dict(d)
        assert q2.BOD5 == 250.0
        assert q2.COD == 500.0
        assert q2.SS == 300.0

    def test_serialization_preserves_effluent_standard(self, sample_quality):
        """序列化后出水标准仍然有效"""
        q = WaterQuality.from_dict(sample_quality.to_dict())
        assert len(q.EFFLUENT_STANDARD) == 6
        assert q.EFFLUENT_STANDARD["BOD5"] == 10.0

    def test_ph_unchanged_by_removal(self, sample_quality):
        """pH 不通过简单去除率改变"""
        out = sample_quality.apply_removal({"BOD5": 0.5})
        assert out.pH == sample_quality.pH

    def test_zero_quality_removal(self, zero_quality):
        """全零浓度 + 去除率 - 不崩溃"""
        out = zero_quality.apply_removal({"BOD5": 0.5})
        assert out.BOD5 == 0.0
        # check_effluent with zero values should not crash
        results = zero_quality.check_effluent()
        assert results["BOD5"][0]  # 0 <= 10, passes


# ═══════════════════════════════════════════════════════════════════
# ParamDef 测试
# ═══════════════════════════════════════════════════════════════════

class TestParamDef:
    """ParamDef 可调参数定义测试"""

    def test_creation(self):
        p = ParamDef("测试", "test", 5.0, 5.0, 0.0, 10.0, 0.5, "m", "desc")
        assert p.name == "测试"
        assert p.key == "test"
        assert p.value == 5.0
        assert p.min_val == 0.0
        assert p.max_val == 10.0

    def test_set_value_within_range(self, param_def):
        param_def.set_value(7.0)
        assert param_def.value == 7.0

    def test_set_value_below_min(self, param_def):
        """低于最小值时钳制"""
        param_def.set_value(-5.0)
        assert param_def.value == 0.0  # min_val

    def test_set_value_above_max(self, param_def):
        """高于最大值时钳制"""
        param_def.set_value(15.0)
        assert param_def.value == 10.0  # max_val

    def test_reset(self, param_def):
        param_def.set_value(9.0)
        param_def.reset()
        assert param_def.value == param_def.default

    def test_serialization_roundtrip(self, param_def):
        d = param_def.to_dict()
        p2 = ParamDef.from_dict(d)
        assert p2.key == param_def.key
        assert p2.value == param_def.value
        assert p2.min_val == param_def.min_val

    def test_from_dict_partial(self):
        """部分字段缺失"""
        d = {"name": "x", "key": "x", "value": 1.0, "default": 1.0,
             "min": 0.0, "max": 5.0}
        p = ParamDef.from_dict(d)
        assert p.step == 0.01  # 默认值
        assert p.unit == ""
        assert p.description == ""


# ═══════════════════════════════════════════════════════════════════
# NodeResult 测试
# ═══════════════════════════════════════════════════════════════════

class TestNodeResult:
    """NodeResult 计算结果测试"""

    def test_success_default(self):
        r = NodeResult()
        assert r.success is True
        assert r.error_msg == ""
        assert r.dimensions == {}
        assert r.checks == {}

    def test_failed(self):
        r = NodeResult.failed("出错了")
        assert r.success is False
        assert r.error_msg == "出错了"

    def test_add_dimension(self):
        r = NodeResult()
        r.add_dimension("长度", 10.0, "m")
        assert r.dimensions["长度"] == (10.0, "m")

    def test_add_check_passed(self):
        r = NodeResult()
        r.add_check("长宽比", True, 2.0, "1.5~3", "-")
        passed, actual, limit, unit = r.checks["长宽比"]
        assert passed is True
        assert actual == 2.0
        assert limit == "1.5~3"
        assert unit == "-"

    def test_add_check_failed(self):
        r = NodeResult()
        r.add_check("流速", False, 0.8, "0.3~0.5", "m/s")
        passed, _, _, _ = r.checks["流速"]
        assert passed is False

    def test_add_warning(self):
        r = NodeResult()
        r.add_warning("流速偏低")
        r.add_warning("砂斗容积不足")
        assert len(r.warnings) == 2
        assert "流速偏低" in r.warnings

    def test_robustness_default(self):
        r = NodeResult()
        assert r.robustness == 0.0

    def test_inlet_outlet_quality(self, sample_quality):
        r = NodeResult()
        r.inlet_quality = sample_quality
        cleaned = sample_quality.apply_removal({"BOD5": 0.9})
        r.outlet_quality = cleaned
        assert r.inlet_quality.BOD5 == 200.0
        assert r.outlet_quality.BOD5 == pytest.approx(20.0)

    def test_serialization_roundtrip(self, success_result):
        d = success_result.to_dict()
        assert d["success"] is True
        assert "长度" in d["dimensions"]


# ═══════════════════════════════════════════════════════════════════
# Port 测试
# ═══════════════════════════════════════════════════════════════════

class TestPort:
    """Port 端口定义测试"""

    def test_creation(self, input_port):
        assert input_port.port_id == "node-1-in"
        assert input_port.is_input is True
        assert input_port.is_output is False

    def test_direction_properties(self, output_port):
        assert output_port.is_input is False
        assert output_port.is_output is True

    def test_can_connect_input_output_same_type(self, input_port, output_port):
        """同类型输入→输出可以连接"""
        in_p = Port("in", "in", PortType.MIXED, "input", "n1")
        out_p = Port("out", "out", PortType.MIXED, "output", "n2")
        assert in_p.can_connect(out_p) is True

    def test_can_connect_same_direction(self):
        """同方向不能连接"""
        in1 = Port("in1", "in1", PortType.MIXED, "input", "n1")
        in2 = Port("in2", "in2", PortType.MIXED, "input", "n2")
        assert in1.can_connect(in2) is False

    def test_can_connect_type_mismatch(self):
        """不同类型不能连接(非MIXED)"""
        water_out = Port("w", "w", PortType.WATER, "output", "n1")
        quality_in = Port("q", "q", PortType.QUALITY, "input", "n2")
        assert water_out.can_connect(quality_in) is False

    def test_can_connect_mixed_compatible(self):
        """MIXED 端口兼容 WATER 和 QUALITY"""
        mixed_in = Port("m", "m", PortType.MIXED, "input", "n1")
        water_out = Port("w", "w", PortType.WATER, "output", "n2")
        assert mixed_in.can_connect(water_out) is True

    def test_serialization_roundtrip(self, input_port):
        d = input_port.to_dict()
        p2 = Port.from_dict(d)
        assert p2.port_id == input_port.port_id
        assert p2.port_type == input_port.port_type

    def test_port_type_enum_name(self, input_port):
        d = input_port.to_dict()
        assert d["port_type"] == "MIXED"


# ═══════════════════════════════════════════════════════════════════
# NodeBase 测试
# ═══════════════════════════════════════════════════════════════════

class TestNodeBase:
    """NodeBase 节点基类测试"""

    def test_initial_state(self, test_node):
        assert test_node.state == NodeState.DIRTY

    def test_set_param(self, test_node):
        test_node.set_param("param_a", 5.0)
        assert test_node.get_param("param_a") == 5.0
        assert test_node.state == NodeState.DIRTY

    def test_set_param_unknown_key(self, test_node):
        """设置不存在的参数不影响状态"""
        import copy
        state_before = copy.copy(test_node._params)
        test_node.set_param("nonexistent", 999)
        assert test_node._params == state_before

    def test_get_param_defs(self, test_node):
        defs = test_node.get_param_defs()
        assert len(defs) == 2
        keys = [d.key for d in defs]
        assert "param_a" in keys
        assert "param_b" in keys

    def test_reset_params(self, test_node):
        test_node.set_param("param_a", 9.0)
        test_node.reset_params()
        assert test_node.get_param("param_a") == 1.0  # 默认值

    def test_removal_rates_default(self, test_node):
        rates = test_node.get_removal_rates()
        assert rates["BOD5"] == 0.3
        assert rates["COD"] == 0.3
        assert rates["SS"] == 0.4

    def test_set_removal_rate(self, test_node):
        test_node.set_removal_rate("BOD5", 0.5)
        assert test_node.get_removal_rates()["BOD5"] == 0.5
        assert test_node.state == NodeState.DIRTY

    def test_set_removal_rate_clamped(self, test_node):
        """去除率钳制到 [0, 1]"""
        test_node.set_removal_rate("BOD5", 1.5)
        assert test_node.get_removal_rates()["BOD5"] == 1.0
        test_node.set_removal_rate("BOD5", -0.5)
        assert test_node.get_removal_rates()["BOD5"] == 0.0

    def test_execute_success(self, test_node, sample_flow, sample_quality):
        result, downstream_flow, downstream_quality = test_node.execute(
            sample_flow, sample_quality
        )
        assert result is not None
        assert result.success is True
        assert test_node.state == NodeState.CLEAN
        assert "长度" in result.dimensions

    def test_execute_passes_flow_through(self, test_node, sample_flow, sample_quality):
        """流量透传不变"""
        _, downstream_flow, _ = test_node.execute(sample_flow, sample_quality)
        assert downstream_flow.Q_design == sample_flow.Q_design

    def test_execute_applies_removal(self, test_node, sample_flow, sample_quality):
        """下游水质应用了去除率"""
        _, _, downstream_quality = test_node.execute(sample_flow, sample_quality)
        # BOD5 应从 200 降到 200*(1-0.3)=140
        assert downstream_quality.BOD5 == pytest.approx(140.0)

    def test_execute_records_tracking(self, test_node, sample_flow, sample_quality):
        """execute 记录了 inlet/outlet quality"""
        result, _, _ = test_node.execute(sample_flow, sample_quality)
        assert result.inlet_quality is not None
        assert result.inlet_quality.BOD5 == 200.0
        assert result.outlet_quality is not None

    def test_node_id_generation(self, test_node):
        assert test_node.node_id.startswith("test_node-")
        assert len(test_node.node_id) > len("test_node-")

    def test_node_id_custom(self, test_node_class):
        node = test_node_class(node_id="my-custom-id")
        assert node.node_id == "my-custom-id"

    def test_serialization_roundtrip(self, test_node, sample_flow, sample_quality):
        """执行后序列化往返"""
        test_node.execute(sample_flow, sample_quality)
        d = test_node.to_dict()
        assert d["type"] == "test_node"
        assert "cached_result" in d
        assert d["cached_result"] is not None

    def test_state_transition_dirty_clears_result(self, test_node, sample_flow, sample_quality):
        """设置为 DIRTY 应清除缓存结果"""
        test_node.execute(sample_flow, sample_quality)
        assert test_node.state == NodeState.CLEAN
        test_node.state = NodeState.DIRTY
        assert test_node.result is None

    def test_calculate_not_implemented(self):
        """未实现 calculate() 的节点应抛出错误"""

        class BadNode(NodeBase):
            NODE_TYPE = "bad"
            NODE_NAME = "坏节点"
            NODE_CATEGORY = "测试"

        node = BadNode()
        with pytest.raises(NotImplementedError):
            node.calculate(WaterFlow(), WaterQuality())

    def test_vectorized_compute_not_implemented(self, test_node_class):
        """NodeBase._vectorized_compute 默认抛出 NotImplementedError"""
        import numpy as np
        grid = {"x": np.array([1.0, 2.0])}
        with pytest.raises(NotImplementedError):
            NodeBase._vectorized_compute(grid, WaterFlow(), WaterQuality(), {})

    def test_vectorized_compute_implemented(self, test_node_class):
        """_TestNode 实现了 _vectorized_compute"""
        import numpy as np
        grid = {"x": np.array([1.0, 2.0])}
        fixed = {}
        result = test_node_class._vectorized_compute(
            grid, WaterFlow(), WaterQuality(), fixed
        )
        assert len(result) == 2
        assert result["L"][0] == 10.0
        assert bool(result["ok_长宽比"][0]) is True

    def test_reset_params_also_resets_removal(self, test_node):
        test_node.set_removal_rate("BOD5", 0.99)
        test_node.reset_params()
        assert test_node.get_removal_rates()["BOD5"] == 0.3  # 回到默认


# ═══════════════════════════════════════════════════════════════════
# 工具函数测试
# ═══════════════════════════════════════════════════════════════════

class TestUtilityFunctions:
    """工具函数测试"""

    def test_ceil_to_basic(self):
        assert ceil_to(3.14159, 0.1) == 3.2
        assert ceil_to(3.14159, 0.5) == 3.5
        assert ceil_to(3.0, 0.5) == 3.0  # 刚好整除

    def test_ceil_to_integer_precision(self):
        assert ceil_to(3.14, 1.0) == 4.0
        assert ceil_to(5.0, 1.0) == 5.0

    def test_ceil_to_negative(self):
        assert ceil_to(-1.2, 0.5) == -1.0

    def test_round_to_basic(self):
        assert round_to(3.14159, 0.1) == 3.1
        assert round_to(3.15, 0.1) == 3.1  # 浮点精度: 3.15/0.1≈31.499, round=31
        assert round_to(3.25, 0.5) == 3.0  # banker's rounding: 3.25/0.5=6.5, round=6

    def test_round_to_integer(self):
        assert round_to(3.6, 1.0) == 4.0

    def test_gravity_constant(self):
        assert GRAVITY == 9.81


# ═══════════════════════════════════════════════════════════════════
# WATER_QUALITY_ATTRS 测试 (v5.3)
# ═══════════════════════════════════════════════════════════════════


class TestWaterQualityAttrs:
    """WATER_QUALITY_ATTRS 常量完整性测试"""

    def test_attrs_has_six(self):
        """精确 6 个水质指标"""
        assert len(WATER_QUALITY_ATTRS) == 6, (
            f"expected 6, got {len(WATER_QUALITY_ATTRS)}"
        )

    def test_attrs_are_waterquality_fields(self):
        """所有属性都是 WaterQuality 的字段"""
        wq = WaterQuality()
        for attr in WATER_QUALITY_ATTRS:
            assert hasattr(wq, attr), f"WaterQuality 缺少字段: {attr}"

    def test_attrs_apply_removal_uses_all(self):
        """apply_removal() 接受全部 6 个指标"""
        wq = WaterQuality()
        rates = {attr: 0.5 for attr in WATER_QUALITY_ATTRS}
        result = wq.apply_removal(rates)
        for attr in WATER_QUALITY_ATTRS:
            expected = getattr(wq, attr) * 0.5
            assert getattr(result, attr) == expected, (
                f"{attr}: expected {expected}, got {getattr(result, attr)}"
            )

    def test_attrs_check_effluent_uses_all(self):
        """check_effluent() 涵盖全部 6 个指标（不含 pH）"""
        wq = WaterQuality()
        checks = wq.check_effluent()
        for attr in WATER_QUALITY_ATTRS:
            assert attr in checks, f"check_effluent 缺少指标: {attr}"

    def test_attrs_no_duplicates(self):
        """无重复指标"""
        assert len(set(WATER_QUALITY_ATTRS)) == len(WATER_QUALITY_ATTRS)
