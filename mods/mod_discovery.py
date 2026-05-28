"""
mod_discovery.py — 模组发现与加载 (v5.4 — extracted from ModManager)

职责: 文件系统扫描, mod.json 验证, 动态 Python 模块导入.

ModManager 通过委托模式调用此模块.
"""

from __future__ import annotations

import importlib
import logging
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

log = logging.getLogger("ModDiscovery")


def scan_directory(
    directory: Path,
    mods: Dict[str, Any],
    errors: List[dict],
    validate_fn: Callable[[Path], list],
    schema_validate_fn: Callable[[Path], list],
) -> int:
    """扫描目录中的所有模组子文件夹, 填充 mods dict 和 errors list.

    Args:
        directory: 要扫描的目录
        mods: ModInfo 字典 (原地修改)
        errors: 错误列表 (原地修改)
        validate_fn: mod.json 验证函数, 签名 (Path) -> list[str]
        schema_validate_fn: JSON Schema 验证函数, 签名 (Path) -> list[str]

    Returns:
        新发现的模组数量
    """
    from mods.mod_manager import ModInfo  # 延迟导入避免循环

    count = 0
    for item in sorted(directory.iterdir()):
        if not item.is_dir():
            continue

        mod_json = item / "mod.json"
        if not mod_json.exists():
            continue

        validation_errors = validate_fn(mod_json)
        schema_errors = schema_validate_fn(mod_json)
        if schema_errors:
            validation_errors.extend(schema_errors)

        if validation_errors:
            log.error(
                "Mod [%s] INVALID:\n  %s",
                item.name,
                "\n  ".join(validation_errors),
            )
            errors.append(
                {
                    "mod_id": item.name,
                    "severity": "error",
                    "errors": validation_errors,
                }
            )
            continue

        try:
            mod_info = ModInfo.from_json(str(mod_json), str(item))
            mods[mod_info.id] = mod_info
            count += 1
            log.debug("ModManager: found mod [%s] %s", mod_info.id, mod_info.name)
        except Exception as e:
            log.warning("ModManager: failed to load %s: %s", mod_json, e)
            errors.append(
                {
                    "mod_id": item.name,
                    "severity": "error",
                    "errors": [str(e)],
                }
            )
    return count


def discover_mods(
    mods_root: Path,
    mods: Dict[str, Any],
    errors: List[dict],
    validate_fn: Callable[[Path], list],
    schema_validate_fn: Callable[[Path], list],
    force_rescan: bool = False,
    already_loaded: bool = False,
) -> bool:
    """扫描 core/ 和 community/ 目录, 发现所有模组.

    Returns:
        True 如果扫描完成 (loaded 标志)
    """
    core_dir = mods_root / "core"
    community_dir = mods_root / "community"

    if not already_loaded or force_rescan:
        if core_dir.exists():
            scan_directory(core_dir, mods, errors, validate_fn, schema_validate_fn)

    if community_dir.exists():
        scan_directory(community_dir, mods, errors, validate_fn, schema_validate_fn)

    return True


def load_mod_module(mod_info) -> Optional[type]:
    """动态导入模组的 Python 模块, 返回 NodeBase 子类.

    支持两种模式:
    1. MC式自包含: mod_dir/__init__.py 中包含 Node 类
    2. 传统 module_path: models/xxx.py 中的分离模块
    """
    if mod_info.loaded and mod_info.node_cls:
        return mod_info.node_cls

    try:
        mod_dir = Path(mod_info.mod_dir)
        if mod_dir.exists() and (mod_dir / "__init__.py").exists():
            parent_dir = str(mod_dir.parent)
            mod_name = mod_dir.name
            if parent_dir not in sys.path:
                sys.path.insert(0, parent_dir)
            try:
                module = importlib.import_module(mod_name)
                node_cls = getattr(module, mod_info.node_class, None)
                if node_cls:
                    mod_info.node_cls = node_cls
                    mod_info.loaded = True
                    log.info(
                        "ModManager: loaded mod [%s] (from __init__.py)",
                        mod_info.id,
                    )
                    return node_cls
            except ImportError:
                pass

        if mod_info.module_path:
            module = importlib.import_module(mod_info.module_path)
            node_cls = getattr(module, mod_info.node_class, None)
            if node_cls:
                mod_info.node_cls = node_cls
                mod_info.loaded = True
                log.info(
                    "ModManager: loaded mod [%s] (from %s)",
                    mod_info.id,
                    mod_info.module_path,
                )
                return node_cls

        log.warning(
            "ModManager: cannot find node class %s for mod [%s]",
            mod_info.node_class,
            mod_info.id,
        )
    except Exception as e:
        log.error("ModManager: failed to load mod [%s]: %s", mod_info.id, e)

    return None
