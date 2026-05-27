"""
mod_validation.py — 模组验证逻辑 (v5.4 — extracted from ModManager)

职责: JSON Schema 验证, mod.json 结构验证, ParamDef 一致性检查,
      vectorized 输出字段验证.

ModManager 通过委托模式调用此模块.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger("ModValidation")

# ── 常量 ──
_MOD_REQUIRED_FIELDS = ["id", "name", "node_type", "node_class"]
_MOD_VALID_STAGES = {
    "io",
    "primary",
    "secondary",
    "tertiary",
    "sludge",
    "mine_water",
    "collection",
    "elevation",
}
_MOD_VALID_PORT_TYPES = {"WATER", "QUALITY", "MIXED", "SLUDGE"}


# ═══════════════════════════════════════════════════════════════════
# mod.json 结构验证 (无状态, 不依赖 ModManager)
# ═══════════════════════════════════════════════════════════════════


def validate_mod_json(path: Path) -> list[str]:
    """验证 mod.json 文件. 返回错误列表; 空列表 = 通过."""
    errors: list[str] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return [f"JSON 语法错误: {e}"]
    except Exception as e:
        return [f"无法读取文件: {e}"]

    if not isinstance(data, dict):
        return ["mod.json 必须是 JSON 对象"]

    for field in _MOD_REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"缺少必填字段: '{field}'")

    mod_id = data.get("id", "")
    if mod_id and not mod_id.islower():
        errors.append(f"id '{mod_id}' 应为全小写")

    stage = data.get("process_stage", "")
    if stage and stage not in _MOD_VALID_STAGES:
        errors.append(f"process_stage '{stage}' 不合法,有效值: {_MOD_VALID_STAGES}")

    for port_type in ("inputs", "outputs"):
        for i, port in enumerate(data.get(port_type, [])):
            if not isinstance(port, dict):
                errors.append(f"{port_type}[{i}] 必须是对象")
                continue
            ptype = port.get("type", "")
            if ptype and ptype not in _MOD_VALID_PORT_TYPES:
                errors.append(f"{port_type}[{i}].type '{ptype}' 不合法")
            if "name" not in port:
                errors.append(f"{port_type}[{i}] 缺少 'name'")

    return errors


def validate_all_mods(mods_root: Optional[Path] = None) -> dict[str, list[str]]:
    """验证所有已安装模组的 mod.json. 返回 {mod_id: errors}."""
    from _paths import get_mods_dir

    if mods_root is None:
        mods_root = Path(get_mods_dir())

    results: dict[str, list[str]] = {}
    for scan_dir_name in ("core", "community"):
        scan_dir = mods_root / scan_dir_name
        if not scan_dir.exists():
            continue
        for item in scan_dir.iterdir():
            if not item.is_dir():
                continue
            mod_json = item / "mod.json"
            if mod_json.exists():
                errs = validate_mod_json(mod_json)
                if errs:
                    results[item.name] = errs
    return results


# ═══════════════════════════════════════════════════════════════════
# 代码一致性验证 (需要 ModInfo + NodeClass)
# ═══════════════════════════════════════════════════════════════════


def validate_param_consistency(mod_info) -> list[str]:
    """验证 mod.json 参数与 _build_param_defs() 一致.

    Returns:
        错误消息列表, 空列表 = 通过
    """
    errors: list[str] = []
    if not mod_info.node_cls or not mod_info.parameters:
        return errors
    try:
        node = mod_info.node_cls()
        param_defs = {pd.key: pd for pd in node.get_param_defs()}
        for mp in mod_info.parameters:
            if mp.key not in param_defs:
                errors.append(f"mod.json param '{mp.key}' not in ParamDef")
    except Exception:
        log.debug(
            "validate_param_consistency failed for %s", mod_info.id, exc_info=True
        )
    return errors


def validate_vectorized_output(mod_info, load_errors: list) -> None:
    """验证 _vectorized_compute 输出字段与离散化配置一致.

    错误追加到 load_errors 列表, 不阻止模组加载.
    """
    # 防止递归: 验证过程中不触发新的加载
    if getattr(validate_vectorized_output, "_running", False):
        return

    node_type = mod_info.node_type
    node_cls = mod_info.node_cls
    if not node_cls or not hasattr(node_cls, "_vectorized_compute"):
        return

    try:
        from models.discretization import DISCRETE_CONFIGS

        cfg = DISCRETE_CONFIGS.get(node_type)
        if not cfg:
            return
    except Exception:
        return

    constraint_keys = cfg.get("constraint_keys", [])
    if not constraint_keys:
        return

    validate_vectorized_output._running = True
    try:
        import numpy as np

        free_cfg = cfg.get("free", {})
        if not free_cfg:
            return
        grid: dict = {}
        for k, vals in free_cfg.items():
            grid[k] = np.array([vals[0]])
        from models.base import WaterFlow, WaterQuality

        result = node_cls._vectorized_compute(
            grid,
            WaterFlow(),
            WaterQuality(),
            {k: v for k, v in cfg.get("fixed", {}).items()},
        )
        dtype_names = set(result.dtype.names)
    except Exception:
        log.debug(
            "validate_vectorized_output failed for %s", mod_info.id, exc_info=True
        )
        return
    finally:
        validate_vectorized_output._running = False

    errors: list[str] = []
    for ck in constraint_keys:
        ok_field = f"ok_{ck}"
        val_field = f"val_{ck}"
        if ok_field not in dtype_names:
            errors.append(f"missing ok_{ck}")
        if val_field not in dtype_names:
            errors.append(f"missing val_{ck}")

    if "concrete_m3" not in dtype_names:
        errors.append("missing concrete_m3")

    if errors:
        load_errors.append(
            {
                "mod_id": mod_info.id,
                "severity": "warning",
                "errors": errors,
            }
        )
        log.warning(
            "Mod [%s] vectorized validation: %s", mod_info.id, "; ".join(errors)
        )
