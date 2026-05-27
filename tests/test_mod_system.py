"""
test_mod_system.py — 模组系统烟雾测试

验证 ModManager 的基础功能:
- 单例模式
- 模组发现
- 模组加载与注册
- 查询 API
- 优雅降级 (损坏模组不崩溃)
"""

import sys
import os
from pathlib import Path

SRC_DIR = Path(__file__).parent.parent / "ddesign_tool" / "src"
APP_DIR = Path(__file__).parent.parent / "ddesign_tool"
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(APP_DIR))


def test_mod_manager_singleton():
    """ModManager 是单例"""
    from mods.mod_manager import get_mod_manager
    mgr1 = get_mod_manager()
    mgr2 = get_mod_manager()
    assert mgr1 is mgr2


def test_mod_manager_discover():
    """discover_all() 发现所有核心模组"""
    from mods.mod_manager import get_mod_manager
    mgr = get_mod_manager()
    mgr.discover_all()
    mods = mgr.mods
    assert len(mods) >= 22, f"Expected >=22 mods, got {len(mods)}"


def test_mod_manager_load_all():
    """load_all() 加载并注册所有节点类型"""
    from mods.mod_manager import get_mod_manager
    mgr = get_mod_manager()
    mgr.load_all()
    registry = mgr.node_registry
    assert len(registry) >= 22, f"Expected >=22 registered types, got {len(registry)}"


def test_get_node_class():
    """get_node_class() 返回已知节点的类"""
    from mods.mod_manager import get_mod_manager
    mgr = get_mod_manager()
    mgr.load_all()
    cls = mgr.get_node_class("tiaojiechi")
    assert cls is not None
    assert cls.__name__ == "TiaojiechiNode"


def test_get_ui_behavior_known_type():
    """get_ui_behavior() 对已知类型返回有效行为"""
    from mods.mod_manager import get_mod_manager
    mgr = get_mod_manager()
    mgr.load_all()
    behavior = mgr.get_ui_behavior("tiaojiechi")
    assert isinstance(behavior, dict)
    assert "is_io_node" in behavior
    assert behavior["is_io_node"] is False  # 调节池不是 IO 节点


def test_get_ui_behavior_io_node():
    """get_ui_behavior() 正确标记 IO 节点"""
    from mods.mod_manager import get_mod_manager
    mgr = get_mod_manager()
    mgr.load_all()
    behavior = mgr.get_ui_behavior("pipe_network")
    assert behavior["is_io_node"] is True


def test_get_ui_behavior_sludge_node():
    """get_ui_behavior() 对污泥节点返回正确行为"""
    from mods.mod_manager import get_mod_manager
    mgr = get_mod_manager()
    mgr.load_all()
    behavior = mgr.get_ui_behavior("wuni_nongsuo")
    assert "is_io_node" in behavior
    assert behavior["is_io_node"] is False


def test_get_ui_behavior_unknown_type():
    """get_ui_behavior() 对未知类型返回安全默认值"""
    from mods.mod_manager import get_mod_manager
    mgr = get_mod_manager()
    mgr.load_all()
    behavior = mgr.get_ui_behavior("nonexistent_mod_type")
    assert behavior["is_io_node"] is False
    assert behavior["skip_solution_browser"] is False


def test_get_node_class_unknown_type():
    """get_node_class() 对未知类型返回 None (不崩溃)"""
    from mods.mod_manager import get_mod_manager
    mgr = get_mod_manager()
    mgr.load_all()
    cls = mgr.get_node_class("nonexistent_mod_type")
    assert cls is None


def test_discover_handles_corrupt_mod_json():
    """discover_all() 在 mod.json 损坏时不崩溃,其他模组正常加载"""
    import tempfile
    import json

    from mods.mod_manager import get_mod_manager
    mgr = get_mod_manager()

    # 在 community 目录创建临时损坏的 mod.json
    mods_dir = APP_DIR / "mods" / "community"
    mods_dir.mkdir(parents=True, exist_ok=True)

    corrupt_dir = mods_dir / "_test_corrupt_mod"
    corrupt_dir.mkdir(exist_ok=True)

    corrupt_json = corrupt_dir / "mod.json"
    corrupt_json.write_text("{ this is not valid json }", encoding="utf-8")

    try:
        # 重置并重新加载
        mgr._loaded = False
        mgr._mods.clear()
        mgr.discover_all()

        # 核心模组应该仍然正常加载
        mods = mgr.mods
        assert len(mods) >= 22, f"Expected >=22 mods despite corrupt one, got {len(mods)}"

        # 损坏的模组不应该出现在 mods 中
        assert "_test_corrupt_mod" not in mods
    finally:
        # 清理
        import shutil
        if corrupt_dir.exists():
            shutil.rmtree(corrupt_dir)


# ═══════════════════════════════════════════════════════════════════
# Phase 3 — Mod Validation Tests
# ═══════════════════════════════════════════════════════════════════

def test_validate_all_core_mods():
    """所有核心模组的 mod.json 通过验证"""
    from mods.mod_manager import validate_all_mods
    results = validate_all_mods()
    # 过滤 core 目录的结果
    core_errors = {k: v for k, v in results.items()
                   if not k.startswith("_test")}
    assert len(core_errors) == 0, f"Core mod validation errors: {core_errors}"


def test_validate_missing_required_field():
    """缺少必填字段返回错误"""
    import tempfile, json
    from mods.mod_manager import _validate_mod_json
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        bad_json = Path(tmp) / "mod.json"
        bad_json.write_text(json.dumps({"name": "Test"}), encoding="utf-8")
        errors = _validate_mod_json(bad_json)
        assert len(errors) > 0  # 缺少 id, node_type, node_class


def test_validate_invalid_stage():
    """无效的 process_stage 返回错误"""
    import tempfile, json
    from mods.mod_manager import _validate_mod_json
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        bad_json = Path(tmp) / "mod.json"
        bad_json.write_text(json.dumps({
            "id": "test", "name": "Test",
            "node_type": "test", "node_class": "TestNode",
            "process_stage": "invalid_stage"
        }), encoding="utf-8")
        errors = _validate_mod_json(bad_json)
        assert any("invalid_stage" in e for e in errors)


def test_validate_bad_json_syntax():
    """JSON 语法错误返回错误"""
    import tempfile
    from mods.mod_manager import _validate_mod_json
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        bad_json = Path(tmp) / "mod.json"
        bad_json.write_text("{ this is broken }", encoding="utf-8")
        errors = _validate_mod_json(bad_json)
        assert len(errors) > 0
        assert any("JSON" in e or "语法" in e for e in errors)


def test_load_errors_accessible():
    """get_load_errors() 和 get_load_summary() 可调用"""
    from mods.mod_manager import get_mod_manager
    mgr = get_mod_manager()
    mgr.load_all()
    errors = mgr.get_load_errors()
    summary = mgr.get_load_summary()
    assert isinstance(errors, list)
    assert isinstance(summary, str)
    assert "mods loaded" in summary
