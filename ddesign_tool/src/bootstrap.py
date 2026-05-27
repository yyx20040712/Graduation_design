"""
Bootstrap resource extraction for PyInstaller frozen distributions.

When the application is run from a PyInstaller-frozen executable, bundled
resources live under `sys._MEIPASS`.  This module copies those resources into
the current working directory so the rest of the application can find them at
their expected relative paths.

In source (non-frozen) mode the module is a deliberate no-op — resources are
already present in the working tree.
"""

import os
import shutil
import sys

from _logging import get_logger

_log = get_logger(__name__)
# ---------------------------------------------------------------------------
# Resource manifest
# ---------------------------------------------------------------------------
# Each entry: (relative_path_inside_MEIPASS, relative_destination_in_CWD, is_directory)
# ---------------------------------------------------------------------------

RESOURCE_MANIFEST: list[tuple[str, str, bool]] = [
    ("config.ini", "config.ini", False),
    ("mods", "mods", True),
    ("data", "data", True),
    ("MODS_GUIDE.md", "MODS_GUIDE.md", False),
    ("README.md", "README.md", False),
    ("使用方法.md", "使用方法.md", False),
    ("yyx.ddesign.json", "yyx.ddesign.json", False),
    ("kuangjing.ddesign.json", "kuangjing.ddesign.json", False),
    ("knowledge", "knowledge", True),
    ("output_template", "output", True),
    ("file_inventory.xlsx", "output/file_inventory.xlsx", False),
]

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _merge_directory(src: str, dst: str, verbose: bool) -> None:
    """合并源目录到目标目录 — 仅拷贝缺失的文件和子目录.

    用于解决增量更新问题:旧版 EXE 已提取 mods/ 目录后,
    新版 EXE 新增的模组子文件夹需要被拷贝进去.
    """
    if not os.path.isdir(src):
        return
    for name in os.listdir(src):
        s = os.path.join(src, name)
        d = os.path.join(dst, name)
        if os.path.isdir(s):
            if not os.path.exists(d):
                shutil.copytree(s, d)
                if verbose:
                    print(f"[bootstrap] MERGE +dir → {os.path.relpath(d)}")
            else:
                _merge_directory(s, d, verbose)  # 递归合并
        else:
            if not os.path.exists(d):
                shutil.copy2(s, d)
                if verbose:
                    print(f"[bootstrap] MERGE +file → {os.path.relpath(d)}")


def extract_resources(force: bool = False, verbose: bool = True) -> int:
    """Extract bundled resources from ``sys._MEIPASS`` to the current working
    directory.

    In frozen mode (``getattr(sys, 'frozen', False)`` is truthy) this function
    iterates *RESOURCE_MANIFEST* and, for every entry whose target does **not**
    already exist (or when *force* is ``True``), copies the resource from the
    PyInstaller staging area into ``os.getcwd()``.

    When running from source (non-frozen) the function returns ``0``
    immediately — no copying is needed.

    Parameters
    ----------
    force : bool
        If ``True``, overwrite existing targets.  By default existing files and
        directories are skipped.
    verbose : bool
        If ``True`` (the default), print progress to stdout.

    Returns
    -------
    int
        Number of resources that were actually copied (skipped items are not
        counted).
    """

    # -- Source-mode: nothing to do ------------------------------------------
    if not getattr(sys, "frozen", False):
        return 0

    meipass: str = sys._MEIPASS  # type: ignore[attr-defined]
    cwd: str = os.getcwd()
    copied: int = 0

    for src_subpath, dst_subpath, is_dir in RESOURCE_MANIFEST:
        src = os.path.join(meipass, src_subpath)
        dst = os.path.join(cwd, dst_subpath)

        # -- Skip if target already exists (unless forced) -------------------
        if os.path.exists(dst) and not force:
            if is_dir:
                # 目录已存在 → 合并模式: 仅拷贝缺失的子文件/子目录
                _merge_directory(src, dst, verbose)
            else:
                if verbose:
                    print(f"[bootstrap] SKIP (already exists): {dst_subpath}")
            continue

        # -- Guard: source must exist inside MEIPASS -------------------------
        if not os.path.exists(src):
            print(f"[bootstrap] WARNING — source not found in MEIPASS: {src}")
            continue

        # -- Copy ------------------------------------------------------------
        try:
            if is_dir:
                if os.path.exists(dst) and force:
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)

            copied += 1
            if verbose:
                print(f"[bootstrap] OK  → {dst_subpath}")
        except Exception:
            import traceback

            print(f"[bootstrap] ERROR copying {src_subpath}:")
            traceback.print_exc()

    return copied
