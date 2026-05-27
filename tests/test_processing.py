"""
test_processing.py — 关键处理单元计算测试

覆盖调节池、CASS反应器、紫外消毒的核心计算逻辑.
"""

from __future__ import annotations

import pytest
import numpy as np
from models.base import WaterFlow, WaterQuality, NodeResult, NodeState
from mods.mod_manager import get_mod_manager
_mgr = get_mod_manager()
TiaojiechiNode = _mgr.load_mod("tiaojiechi")
CASSNode = _mgr.load_mod("cass")
ZiwaiNode = _mgr.load_mod("ziwai")


# ═══════════════════════════════════════════════════════════════════
# 调节池 (TiaojiechiNode)
# ═══════════════════════════════════════════════════════════════════

class TestTiaojiechi:
    """调节池计算测试"""

    @pytest.fixture
    def node(self):
        return TiaojiechiNode()

    def test_creation(self, node):
        assert node.NODE_TYPE == "tiaojiechi"
        assert node.NODE_NAME == "调节池"

    def test_calculate_success(self, node, sample_flow, sample_quality):
        result, _, _ = node.execute(sample_flow, sample_quality)
        assert result.success
        assert node.state == NodeState.CLEAN

    def test_calculate_produces_dimensions(self, node, sample_flow, sample_quality):
        result, _, _ = node.execute(sample_flow, sample_quality)
        # 应有基本维度
        dim_keys = " ".join(result.dimensions.keys())
        assert "长度" in dim_keys or "有效容积" in dim_keys or "L" in dim_keys

    def test_calculate_positive_dimensions(self, node, sample_flow, sample_quality):
        result, _, _ = node.execute(sample_flow, sample_quality)
        for name, (val, unit) in result.dimensions.items():
            if isinstance(val, (int, float)) and "去除率" not in name:
                assert val >= 0, f"{name} = {val} should be >= 0"

    def test_param_defaults(self, node):
        """默认参数应在合理范围"""
        assert node.get_param("n") >= 2
        assert node.get_param("HRT") >= 4.0
        assert node.get_param("h_eff") >= 3.0

    def test_set_n(self, node, sample_flow, sample_quality):
        node.set_param("n", 2)
        result, _, _ = node.execute(sample_flow, sample_quality)
        assert result.success

    def test_small_flow(self, node, small_flow, sample_quality):
        """小流量场景"""
        result, _, _ = node.execute(small_flow, sample_quality)
        assert result.success

    def test_vectorized_compute(self, node, sample_flow, sample_quality):
        """向量化计算可用"""
        try:
            grid = {"n": np.array([2, 4, 6]), "HRT": np.array([4.0, 6.0, 8.0]),
                    "h_eff": np.array([4.0, 4.5, 5.0]),
                    "ratio_LB": np.array([1.5, 2.0, 2.5])}
            fixed = {"h_super": 0.5, "P_density": 15.0}
            result = TiaojiechiNode._vectorized_compute(grid, sample_flow, sample_quality, fixed)
            assert len(result) > 0
            assert len(result.shape) == 1
        except NotImplementedError:
            pytest.skip("_vectorized_compute not implemented")


# ═══════════════════════════════════════════════════════════════════
# CASS 反应器 (CASSNode)
# ═══════════════════════════════════════════════════════════════════

class TestCASS:
    """CASS 反应器计算测试"""

    @pytest.fixture
    def node(self):
        return CASSNode()

    def test_creation(self, node):
        assert node.NODE_TYPE == "cass"
        assert "CASS" in node.NODE_NAME

    def test_calculate_success(self, node, sample_flow, sample_quality):
        result, _, _ = node.execute(sample_flow, sample_quality)
        assert result.success

    def test_calculate_produces_checks(self, node, sample_flow, sample_quality):
        result, _, _ = node.execute(sample_flow, sample_quality)
        # CASS 应有多个校核项
        assert len(result.checks) > 0

    def test_removal_rates_high(self, node):
        """CASS 去除率应较高(生物处理)"""
        rates = node.get_removal_rates()
        assert rates.get("BOD5", 0) >= 0.85
        assert rates.get("COD", 0) >= 0.80

    def test_param_n_range(self, node):
        n_defs = node.get_param_defs()
        n_param = next((d for d in n_defs if d.key == "n"), None)
        if n_param:
            assert n_param.min_val >= 2
            assert n_param.max_val <= 8

    def test_large_flow(self, node, large_flow, sample_quality):
        """大流量场景"""
        result, _, _ = node.execute(large_flow, sample_quality)
        assert result.success

    def test_vectorized_compute(self, node, sample_flow, sample_quality):
        """向量化计算 - 自动从 discretization.json 读取 free/fixed"""
        try:
            import json
            with open("ddesign_tool/mods/core/cass/discretization.json", encoding="utf-8") as f:
                cfg = json.load(f)
            grid = {k: np.array([v[0]]) for k, v in cfg["free"].items()}
            fixed = dict(cfg["fixed"])
            result = CASSNode._vectorized_compute(grid, sample_flow, sample_quality, fixed)
            assert len(result) == 1
        except NotImplementedError:
            pytest.skip("_vectorized_compute not implemented")


# ═══════════════════════════════════════════════════════════════════
# 紫外消毒池 (ZiwaiNode)
# ═══════════════════════════════════════════════════════════════════

class TestZiwai:
    """紫外消毒池计算测试"""

    @pytest.fixture
    def node(self):
        return ZiwaiNode()

    def test_creation(self, node):
        assert node.NODE_TYPE == "ziwai"
        assert "紫外" in node.NODE_NAME or "UV" in node.NODE_NAME.upper()

    def test_calculate_success(self, node, sample_flow, sample_quality):
        result, _, _ = node.execute(sample_flow, sample_quality)
        assert result.success

    def test_min_channels(self, node):
        """渠道数 n 应 >= 1(标准要求 >= 2,代码中 min_val 用于离散化)"""
        n_defs = node.get_param_defs()
        n_param = next((d for d in n_defs if d.key == "n"), None)
        if n_param:
            assert n_param.min_val >= 1, "UV渠道数最小值应 >= 1"

    def test_no_removal(self, node):
        """紫外消毒不应有污染物去除率"""
        rates = node.get_removal_rates()
        for pollutant, rate in rates.items():
            assert rate == 0.0, f"{pollutant} should not be removed by UV"

    def test_calculate_produces_uv_checks(self, node, sample_flow, sample_quality):
        result, _, _ = node.execute(sample_flow, sample_quality)
        # 应有紫外剂量或流速相关校核
        checks_text = " ".join(result.checks.keys())
        assert "剂量" in checks_text or "流速" in checks_text or "dose" in checks_text.lower() or "v" in checks_text.lower()

    def test_small_flow(self, node, small_flow, sample_quality):
        """小流量 - n=2 时流速可能不足,但不应崩溃"""
        result, _, _ = node.execute(small_flow, sample_quality)
        # 即使校核失败也不应崩溃
        assert result is not None

    def test_vectorized_compute(self, node, sample_flow, sample_quality):
        """向量化计算 - 自动从 discretization.json 读取 free/fixed"""
        try:
            import json
            with open("ddesign_tool/mods/core/ziwai/discretization.json", encoding="utf-8") as f:
                cfg = json.load(f)
            grid = {k: np.array([v[0]]) for k, v in cfg["free"].items()}
            fixed = dict(cfg["fixed"])
            result = ZiwaiNode._vectorized_compute(grid, sample_flow, sample_quality, fixed)
            assert len(result) == 1
        except NotImplementedError:
            pytest.skip("_vectorized_compute not implemented")
