"""
Bootstrap resource extraction for PyInstaller frozen distributions.

When the application is run from a PyInstaller-frozen executable, bundled
resources live under ``sys._MEIPASS``.  This module copies those resources into
the current working directory so the rest of the application can find them at
their expected relative paths.

In source (non-frozen) mode the module is a deliberate no-op — resources are
already present in the working tree.
"""

import os
import shutil
import sys
import time

from _logging import get_logger

_log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Resource manifest
# ---------------------------------------------------------------------------
# Each entry: (relative_path_in_MEIPASS, relative_destination_in_CWD, is_directory)
#
# Strategy per entry type:
#   - Directories (mods/data/knowledge): merge — only copy new files, never overwrite
#   - resources/: copy files that don't exist in cwd; existing files are skipped
#     (user must manually delete old files to receive updates)
#   - config.ini: never overwrite (user's local configuration)
# ---------------------------------------------------------------------------

RESOURCE_MANIFEST: list[tuple[str, str, bool]] = [
    ("config.ini",            "config.ini",  False),
    ("mods",                  "mods",        True),
    ("data",                  "data",        True),
    ("knowledge",             "knowledge",   True),
    ("resources",             ".",           True),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _merge_directory(src: str, dst: str, verbose: bool) -> None:
    """合并源目录到目标目录 — 仅拷贝缺失的文件和子目录."""
    if not os.path.isdir(src):
        return
    for name in os.listdir(src):
        s = os.path.join(src, name)
        d = os.path.join(dst, name)
        if os.path.isdir(s):
            if not os.path.exists(d):
                try:
                    shutil.copytree(s, d)
                except (PermissionError, FileNotFoundError, OSError) as exc:
                    if verbose:
                        print(f"[bootstrap] WARN {name}: {exc}")
                    continue
                if verbose:
                    print(f"[bootstrap] MERGE +dir -> {os.path.relpath(d)}")
            else:
                _merge_directory(s, d, verbose)
        else:
            if not os.path.exists(d):
                try:
                    shutil.copy2(s, d)
                except (PermissionError, FileNotFoundError, OSError) as exc:
                    if verbose:
                        print(f"[bootstrap] WARN {name}: {exc}")
                    continue
                if verbose:
                    print(f"[bootstrap] MERGE +file -> {os.path.relpath(d)}")


def _safe_copy_file(src: str, dst: str) -> None:
    """Copy a single file with retry for Windows file locks."""
    for attempt in range(3):
        try:
            shutil.copy2(src, dst)
            return
        except PermissionError:
            if attempt == 2:
                raise
            time.sleep(0.2)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_resources(force: bool = False, verbose: bool = True) -> int:
    """Extract bundled resources to the current working directory.

    In frozen mode iterates *RESOURCE_MANIFEST* and copies resources from the
    PyInstaller staging area into ``os.getcwd()``.

    Returns the number of resources actually copied.
    """
    if not getattr(sys, "frozen", False):
        return 0

    meipass: str = sys._MEIPASS  # type: ignore[attr-defined]
    cwd: str = os.getcwd()
    copied: int = 0

    for src_subpath, dst_subpath, is_dir in RESOURCE_MANIFEST:
        src = os.path.join(meipass, src_subpath)
        dst = os.path.join(cwd, dst_subpath)

        if not os.path.exists(src):
            if verbose:
                print(f"[bootstrap] SKIP (not bundled): {src_subpath}")
            continue

        if is_dir:
            _merge_directory(src, dst, verbose)
            copied += 1
        else:
            if os.path.exists(dst) and not force:
                if verbose:
                    print(f"[bootstrap] SKIP (already exists): {dst_subpath}")
                continue
            try:
                _safe_copy_file(src, dst)
                copied += 1
                if verbose:
                    print(f"[bootstrap] OK  -> {dst_subpath}")
            except Exception as exc:
                print(f"[bootstrap] ERROR {src_subpath}: {exc}")

    return copied
