"""
mod_config.py — 模组配置文件加载 (v5.4 — extracted from ModManager)

职责: 从模组目录加载 discretization.json / labels.json / unit_prices.json,
      合并所有模组的配置, 持久化离散化配置.

ModManager 通过委托模式调用此模块, 保持公共 API 不变.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Callable, Dict, List, Optional

log = logging.getLogger("ModConfig")


def _load_json(mod_dir: str, filename: str) -> Optional[dict]:
    """从模组目录加载单个 JSON 配置文件. 返回 None 如果不存在."""
    path = os.path.join(mod_dir, filename)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log.warning("Failed to load %s from %s: %s", filename, mod_dir, e)
        return None


def load_discretization(mod_dir: str) -> Optional[dict]:
    """加载模组的 discretization.json"""
    return _load_json(mod_dir, "discretization.json")


def load_labels(mod_dir: str) -> Optional[dict]:
    """加载模组的 labels.json"""
    return _load_json(mod_dir, "labels.json")


def load_equipment(mod_dir: str) -> Optional[dict]:
    """加载模组的 unit_prices.json"""
    return _load_json(mod_dir, "unit_prices.json")


def get_all_discretizations(
    mods: Dict[str, Any],
    discover_fn: Optional[Callable[[], None]] = None,
) -> Dict[str, dict]:
    """合并所有模组的 discretization 配置. 返回 {node_type: config}."""
    if not mods and discover_fn:
        discover_fn()
    result = {}
    for mod_info in mods.values():
        if not mod_info.mod_dir:
            continue
        cfg = load_discretization(mod_info.mod_dir)
        if cfg:
            result[mod_info.node_type] = cfg
    return result


def get_all_labels(
    mods: Dict[str, Any],
    discover_fn: Optional[Callable[[], None]] = None,
) -> Dict[str, dict]:
    """合并所有模组的 labels 配置. 返回 {node_type: labels}."""
    if not mods and discover_fn:
        discover_fn()
    result = {}
    for mod_info in mods.values():
        if not mod_info.mod_dir:
            continue
        labels = load_labels(mod_info.mod_dir)
        if labels:
            result[mod_info.node_type] = labels
    return result


def get_all_equipment(
    mods: Dict[str, Any],
    discover_fn: Optional[Callable[[], None]] = None,
) -> Dict[str, dict]:
    """合并所有模组的 equipment 配置. 返回 {node_type: config}."""
    if not mods and discover_fn:
        discover_fn()
    result = {}
    for mod_info in mods.values():
        if not mod_info.mod_dir:
            continue
        equip = load_equipment(mod_info.mod_dir)
        if equip:
            result[mod_info.node_type] = equip
    return result


def save_discretization(
    mod_dir: str, mod_id: str, config: dict, test_dirs: List[str] | None = None
) -> bool:
    """保存 discretization.json 到模组目录 (及测试目录).

    Args:
        mod_dir: 生产模组目录
        mod_id: 模组 ID (用于日志)
        config: 离散化配置字典
        test_dirs: 额外的测试目录路径列表 (如 mods/core/{mod_id}/)

    Returns:
        True 如果至少一个目标写入成功
    """
    import os as _os

    mod_name = _os.path.basename(mod_dir)
    json_text = json.dumps(config, ensure_ascii=False, indent=2) + "\n"
    success = False

    targets = [mod_dir]
    if test_dirs:
        targets.extend(test_dirs)

    for target_dir in targets:
        target_path = _os.path.join(target_dir, "discretization.json")
        try:
            _os.makedirs(_os.path.dirname(target_path), exist_ok=True)
            tmp_path = target_path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(json_text)
            _os.replace(tmp_path, target_path)
            success = True
        except Exception:
            log.warning(
                "Failed to save discretization for %s to %s",
                mod_id,
                target_path,
                exc_info=True,
            )
    return success
