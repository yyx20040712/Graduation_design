"""
conftest.py — pytest 共享 fixtures

提供模拟的 WaterFlow、WaterQuality、GraphExecutor 等,
供所有测试文件使用.
"""

from __future__ import annotations

import sys
from pathlib import Path

# 确保 src 目录在 sys.path 中
SRC_DIR = Path(__file__).parent.parent / "ddesign_tool" / "src"
sys.path.insert(0, str(SRC_DIR))

import numpy as np  # noqa: E402
import pytest  # noqa: E402
import warnings  # noqa: E402
from models.base import (  # noqa: E402
    NodeBase,
    NodeResult,
    ParamDef,
    Port,
    PortType,
    SludgeFlow,
    WaterFlow,
    WaterQuality,
)

# ═══════════════════════════════════════════════════════════════════
# 全局防御: numpy RuntimeWarning → 测试失败
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _fail_on_numpy_divide_warnings():
    """工业级防御: 任何测试中产生 numpy 除零/无效值警告 → 直接失败.

    这防止了向量化计算中的沉默故障 — 在 CI 中, 警告即错误.
    """
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", RuntimeWarning)
        yield
        for w in caught:
            msg = str(w.message)
            if "divide by zero" in msg or "invalid value encountered" in msg:
                pytest.fail(
                    f"numpy RuntimeWarning in test: {w.message}\n"
                    f"  位置: {w.filename}:{w.lineno}\n"
                    f"  提示: 在除法/乘法前使用 np.maximum(denom, 1e-10) 或 np.divide(..., where=cond)"
                )


@pytest.fixture
def sample_flow() -> WaterFlow:
    """标准设计流量 — 来自中期报告"""
    return WaterFlow(Q_design=0.57, Q_avg_daily=34760.7, Kz=1.4)


@pytest.fixture
def small_flow() -> WaterFlow:
    """小流量场景(用于测试低流量边界)"""
    return WaterFlow(Q_design=0.05, Q_avg_daily=3000.0, Kz=1.5)


@pytest.fixture
def zero_flow() -> WaterFlow:
    """零流量边界 — 测试除零保护"""
    return WaterFlow(Q_design=0.0, Q_avg_daily=0.0, Kz=1.0)


@pytest.fixture
def large_flow() -> WaterFlow:
    """大流量场景"""
    return WaterFlow(Q_design=2.0, Q_avg_daily=120000.0, Kz=1.3)


# ═══════════════════════════════════════════════════════════════════
# WaterQuality fixtures
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def sample_quality() -> WaterQuality:
    """标准进水水质 — 来自中期报告表3-1"""
    return WaterQuality(
        BOD5=200.0,
        COD=400.0,
        SS=220.0,
        NH3N=35.0,
        TN=45.0,
        TP=5.0,
        pH=7.0,
    )


@pytest.fixture
def clean_quality() -> WaterQuality:
    """达标出水水质"""
    return WaterQuality(
        BOD5=8.0,
        COD=40.0,
        SS=8.0,
        NH3N=3.0,
        TN=12.0,
        TP=0.3,
        pH=7.0,
    )


@pytest.fixture
def polluted_quality() -> WaterQuality:
    """高浓度进水"""
    return WaterQuality(
        BOD5=400.0,
        COD=800.0,
        SS=500.0,
        NH3N=50.0,
        TN=70.0,
        TP=10.0,
        pH=6.5,
    )


@pytest.fixture
def zero_quality() -> WaterQuality:
    """全零浓度水质 — 测试除零保护"""
    return WaterQuality(
        BOD5=0.0,
        COD=0.0,
        SS=0.0,
        NH3N=0.0,
        TN=0.0,
        TP=0.0,
        pH=7.0,
    )


# ═══════════════════════════════════════════════════════════════════
# SludgeFlow fixtures
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def sample_sludge() -> SludgeFlow:
    """标准初沉污泥 — 含水率 96%"""
    return SludgeFlow(Q_wet=125.0, DS=5000.0, P_moisture=0.96, VS_ratio=0.60)


@pytest.fixture
def thickened_sludge() -> SludgeFlow:
    """浓缩后污泥 — 含水率 94%"""
    return SludgeFlow(Q_wet=83.33, DS=5000.0, P_moisture=0.94, VS_ratio=0.60)


@pytest.fixture
def dewatered_sludge() -> SludgeFlow:
    """脱水后污泥 — 含水率 80%"""
    return SludgeFlow(Q_wet=25.0, DS=5000.0, P_moisture=0.80, VS_ratio=0.45)


@pytest.fixture
def waste_activated_sludge() -> SludgeFlow:
    """剩余活性污泥 — 含水率 99.2%"""
    return SludgeFlow(Q_wet=250.0, DS=2000.0, P_moisture=0.992, VS_ratio=0.70)


@pytest.fixture
def zero_sludge() -> SludgeFlow:
    """零污泥 — 测试除零保护"""
    return SludgeFlow(Q_wet=0.0, DS=0.0, P_moisture=0.0, VS_ratio=0.0)


# ═══════════════════════════════════════════════════════════════════
# NodeBase / NodeResult / ParamDef / Port  fixtures
# ═══════════════════════════════════════════════════════════════════


class _TestNode(NodeBase):
    """仅用于测试的简单节点(传入参数和计算结果)"""

    NODE_TYPE = "test_node"
    NODE_NAME = "测试节点"
    NODE_CATEGORY = "测试"

    def __init__(self, node_id=None, params=None):
        self._given_params = dict(params or {})
        super().__init__(node_id=node_id)

    def _default_params(self) -> dict:
        return {"param_a": 1.0, "param_b": 2.0}

    def _build_param_defs(self):
        return [
            ParamDef("参数A", "param_a", 1.0, 1.0, 0.1, 10.0, 0.1, "m"),
            ParamDef("参数B", "param_b", 2.0, 2.0, 0.1, 20.0, 0.1, "m"),
        ]

    def _default_removal_rates(self):
        return {"BOD5": 0.3, "COD": 0.3, "SS": 0.4}

    def calculate(self, flow, quality):
        result = NodeResult(success=True, params=dict(self._params))
        result.add_dimension("长度", 10.0, "m")
        result.add_dimension("宽度", 5.0, "m")
        result.add_check("长宽比", True, 2.0, "1.5~3", "—")
        return result

    @classmethod
    def _vectorized_compute(cls, grid, flow, quality, fixed):
        """返回一个 dummy 结构化数组用于测试"""
        N = len(next(iter(grid.values())))
        dt = np.dtype(
            [
                ("L", np.float64),
                ("B", np.float64),
                ("ok_长宽比", np.bool_),
            ]
        )
        arr = np.zeros(N, dtype=dt)
        arr["L"] = np.full(N, 10.0)
        arr["B"] = np.full(N, 5.0)
        arr["ok_长宽比"] = True
        return arr


@pytest.fixture
def test_node_class():
    """返回 _TestNode 类"""
    return _TestNode


@pytest.fixture
def test_node(test_node_class) -> _TestNode:
    """一个预创建的 _TestNode 实例"""
    return test_node_class()


@pytest.fixture
def param_def() -> ParamDef:
    """标准 ParamDef 实例"""
    return ParamDef(
        name="测试参数",
        key="test_param",
        value=5.0,
        default=5.0,
        min_val=0.0,
        max_val=10.0,
        step=0.5,
        unit="m",
        description="测试用",
    )


@pytest.fixture
def success_result() -> NodeResult:
    """一个成功的计算结果"""
    result = NodeResult(success=True)
    result.add_dimension("长度", 10.0, "m")
    result.add_dimension("宽度", 5.0, "m")
    result.add_check("长宽比", True, 2.0, "1.5~3", "—")
    return result


@pytest.fixture
def failed_result() -> NodeResult:
    """一个失败的计算结果"""
    return NodeResult.failed("计算失败: 输入参数超出范围")


@pytest.fixture
def input_port() -> Port:
    """一个输入端口"""
    return Port(
        port_id="node-1-in",
        name="进水",
        port_type=PortType.MIXED,
        direction="input",
        node_id="node-1",
    )


@pytest.fixture
def output_port() -> Port:
    """一个输出端口"""
    return Port(
        port_id="node-1-out",
        name="出水",
        port_type=PortType.MIXED,
        direction="output",
        node_id="node-1",
    )


@pytest.fixture
def water_input_port() -> Port:
    """水量专用输入端口"""
    return Port(
        port_id="pipe-1-out",
        name="管网出水",
        port_type=PortType.WATER,
        direction="output",
        node_id="pipe-1",
    )


@pytest.fixture
def quality_output_port() -> Port:
    """水质专用输出端口"""
    return Port(
        port_id="wq-1-out",
        name="水质输出",
        port_type=PortType.QUALITY,
        direction="output",
        node_id="wq-1",
    )


# ═══════════════════════════════════════════════════════════════════
# GraphExecutor fixture (模拟)
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def executor():
    """返回一个预初始化的 GraphExecutor"""
    from controller.graph_executor import GraphExecutor

    return GraphExecutor()


# ═══════════════════════════════════════════════════════════════════
# 工具 fixture
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def node_registry():
    """返回所有注册节点的类型列表(通过 ModManager 加载)"""
    from mods.mod_manager import get_mod_manager

    mgr = get_mod_manager()
    mgr.load_all()
    types = {}
    for mod_id in [
        "tiaojiechi",
        "cugeshan",
        "xigeshan",
        "chenshachi",
        "chuchenchi",
        "cass",
        "gaomidu",
        "vxinglvchi",
        "ziwai",
        "kw_tiaojiechi",
        "kw_chenshachi",
        "kw_ningjiao",
        "kw_cifenli",
        "erchunchi",
        "bashi_jiliangcao",
        "wushui_tisheng",
    ]:
        cls = mgr.get_node_class(mod_id)
        if cls:
            types[mod_id] = cls
    from models.combiner import CombinerNode

    types["combiner"] = CombinerNode
    return types
