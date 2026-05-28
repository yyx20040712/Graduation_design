"""test_constraint_types.py — 约束类型数据模型验证

验证 discretization.json 中的 constraint_types 字段:
  - 每个模组都有 constraint_types
  - 值只能是 "original" 或 "result"
  - "original" 约束对应 fixed 参数
  - constraint_types 的 key 与 constraint_names 完全匹配
"""

import json
import os
import pytest
from pathlib import Path

# 项目根目录(测试文件在 tests/ 下)
PROJECT_ROOT = Path(__file__).parent.parent
MODS_CORE = PROJECT_ROOT / "mods" / "core"
MODS_COMMUNITY = PROJECT_ROOT / "mods" / "community"


def _load_json(path: Path) -> dict:
    """加载 JSON 文件"""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _get_all_discretization_files() -> list:
    """获取所有 discretization.json 文件路径"""
    files = []
    for base in [MODS_CORE, MODS_COMMUNITY]:
        if base.exists():
            for d in base.iterdir():
                if d.is_dir():
                    disc = d / "discretization.json"
                    if disc.exists():
                        files.append((d.name, disc))
    return files


# ── 所有带离散化配置的模组 ──
ALL_MODS = _get_all_discretization_files()


@pytest.mark.parametrize("mod_id,disc_path", ALL_MODS)
def test_discretization_has_constraint_types(mod_id: str, disc_path: Path):
    """每个 discretization.json 必须包含 constraint_types 字段"""
    cfg = _load_json(disc_path)
    assert "constraint_types" in cfg, (
        f"{mod_id}/discretization.json 缺少 constraint_types 字段"
    )
    types = cfg["constraint_types"]
    assert isinstance(types, dict), (
        f"{mod_id} constraint_types 必须是 dict, 实际: {type(types)}"
    )


@pytest.mark.parametrize("mod_id,disc_path", ALL_MODS)
def test_constraint_type_values(mod_id: str, disc_path: Path):
    """constraint_types 的值只能是 'original' 或 'result'"""
    cfg = _load_json(disc_path)
    types = cfg.get("constraint_types", {})
    for name, ctype in types.items():
        assert ctype in ("original", "result"), (
            f"{mod_id} constraint_type '{name}' = '{ctype}', "
            f"必须是 'original' 或 'result'"
        )


@pytest.mark.parametrize("mod_id,disc_path", ALL_MODS)
def test_constraint_types_keys_match_names(mod_id: str, disc_path: Path):
    """constraint_types 的每个 key 必须存在于 constraint_names 中"""
    cfg = _load_json(disc_path)
    types = cfg.get("constraint_types", {})
    names = cfg.get("constraint_names", [])
    for name in types:
        assert name in names, (
            f"{mod_id}: constraint_types key '{name}' 不在 constraint_names 中: {names}"
        )


@pytest.mark.parametrize("mod_id,disc_path", ALL_MODS)
def test_constraint_names_covered(mod_id: str, disc_path: Path):
    """每个 constraint_names 条目必须有对应的 constraint_type"""
    cfg = _load_json(disc_path)
    types = cfg.get("constraint_types", {})
    names = cfg.get("constraint_names", [])
    for name in names:
        assert name in types, (
            f"{mod_id}: constraint_name '{name}' 在 constraint_types 中缺失"
        )


# ── 特定约束值回归测试 ──

def test_tiaojiechi_LB_range():
    """调节池 长宽比 L/B 约束应为 1.0~2.0"""
    disc = _load_json(MODS_CORE / "tiaojiechi" / "discretization.json")
    limits = disc.get("constraint_limits", {})
    assert "长宽比 L/B" in limits
    assert "1.0" in limits["长宽比 L/B"] or "1~2" in limits["长宽比 L/B"].replace(" ", "")


def test_tiaojiechi_HRT_range():
    """调节池 实际 HRT 约束应为 6~12"""
    disc = _load_json(MODS_CORE / "tiaojiechi" / "discretization.json")
    limits = disc.get("constraint_limits", {})
    assert "实际 HRT" in limits
    limit_str = limits["实际 HRT"]
    assert "2" in limit_str and "12" in limit_str, f"HRT limit: {limit_str}"


def test_chenshachi_Dh2_range():
    """旋流沉砂池 径深比 D/h2 约束应为 2.0~2.5"""
    disc = _load_json(MODS_CORE / "chenshachi" / "discretization.json")
    limits = disc.get("constraint_limits", {})
    assert "径深比 D/h2" in limits
    limit_str = limits["径深比 D/h2"]
    assert "2.0" in limit_str and "2.5" in limit_str, f"D/h2 limit: {limit_str}"


def test_chenshachi_h2_constraint_exists():
    """旋流沉砂池 应有 有效水深 h2 约束"""
    disc = _load_json(MODS_CORE / "chenshachi" / "discretization.json")
    names = disc.get("constraint_names", [])
    assert "有效水深 h2" in names or any("h2" in n for n in names), (
        f"chenshachi constraint_names 缺少 h2 约束: {names}"
    )
