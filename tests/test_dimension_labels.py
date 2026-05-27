"""test_dimension_labels.py — 自动化维度标签完整性校验

确保所有模组的标量 add_dimension 名称和向量化 dtype 字段名
均在 DIMENSION_TABLE / VEC_FIELD_TABLE / labels.json 中有对应标签.
"""
import pytest
from ui.dimension_labels import (
    validate_dimension_labels,
    reset_fallback_warnings,
    get_fallback_warnings,
)
from mods.mod_manager import get_mod_manager


@pytest.fixture(autouse=True)
def _reset_warnings():
    """每个测试前重置告警记录"""
    reset_fallback_warnings()


def test_all_vectorized_fields_have_labels():
    """验证所有模组的向量化字段名在标签表中有对应条目"""
    mgr = get_mod_manager()
    mgr.load_all()

    result = validate_dimension_labels()

    if not result["ok"]:
        missing_list = "\n  ".join(
            f"[{m['mod']}] {m['key']} ({m['path']})"
            for m in result["missing"]
        )
        pytest.fail(
            f"{len(result['missing'])} 个向量化字段缺少标签(共检查 {result['total']} 个):\n"
            f"  {missing_list}\n"
            f"修复方法: 在 dimension_labels.py 的 VEC_FIELD_TABLE "
            f"或模组 labels.json 中添加对应条目."
        )


def test_no_fallback_warnings_during_startup():
    """验证启动时无兜底告警(即所有常用维度名都有标签)"""
    from models.base import WaterFlow, WaterQuality
    from models.solution_space import get_engine
    from ui.dimension_labels import resolve_dimension

    mgr = get_mod_manager()
    mgr.load_all()

    # 用标准流量水质触发所有模组的向量化计算
    flow = WaterFlow(Q_design=0.57, Q_avg_daily=34760.7, Kz=1.4)
    quality = WaterQuality()

    engine = get_engine()
    for mod_id in mgr.mods:
        try:
            sols = engine.enumerate(mod_id, flow, quality)
            if sols:
                # 遍历方案中的维度名 → 触发 resolve_dimension
                for k in sols[0].dimensions:
                    resolve_dimension(k)
        except Exception:
            pass  # 部分模组可能无方案空间

    warnings = get_fallback_warnings()
    if warnings:
        pytest.fail(
            f"启动时 {len(warnings)} 个维度名触发了兜底告警:\n  "
            + "\n  ".join(warnings)
        )
