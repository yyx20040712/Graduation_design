"""
Bootstrap — PyInstaller 资源提取 (v5.4-s7 重写)

启动时从 sys._MEIPASS 将打包资源拷贝到工作目录。
源码模式下为 no-op。
"""
import os
import shutil
import sys
import time

from _logging import get_logger

_log = get_logger(__name__)

# ── 资源清单: (MEIPASS路径, CWD目标路径, 是目录?) ──
RESOURCE_MANIFEST: list[tuple[str, str, bool]] = [
    ("config.ini",  "config.ini", False),
    ("mods",        "mods",       True),
    ("data",        "data",       True),
    ("knowledge",   "knowledge",  True),
    ("resources",   ".",          True),
]

# ── 运行时目录 (始终在 CWD 创建) ──
RUNTIME_DIRS = ["output", "logs", "cache", "projects"]


def _copy_file(src: str, dst: str, verbose: bool) -> bool:
    """拷贝单个文件, 带重试"""
    for attempt in range(3):
        try:
            shutil.copy2(src, dst)
            if verbose:
                print(f"[bootstrap] + {os.path.relpath(dst)}")
            return True
        except PermissionError:
            if attempt < 2:
                time.sleep(0.2)
        except OSError:
            return False
    return False


def _copy_tree(src: str, dst: str, verbose: bool) -> int:
    """递归合并目录树, 仅拷贝缺失文件, 永不覆盖已有文件.
    返回拷贝的文件数.
    """
    if not os.path.isdir(src):
        return 0
    os.makedirs(dst, exist_ok=True)
    count = 0
    for name in os.listdir(src):
        s = os.path.join(src, name)
        d = os.path.join(dst, name)
        if os.path.isdir(s):
            count += _copy_tree(s, d, verbose)
        elif not os.path.exists(d):
            if _copy_file(s, d, verbose):
                count += 1
    return count


def _create_dirs(verbose: bool) -> None:
    """预创建所有运行时目录"""
    target = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.getcwd()
    for name in RUNTIME_DIRS:
        path = os.path.join(target, name)
        try:
            os.makedirs(path, exist_ok=True)
            if verbose:
                print(f"[bootstrap] mkdir {name}/")
        except OSError:
            pass


def extract_resources(force: bool = False, verbose: bool = True) -> int:
    """从 MEIPASS 提取资源到 EXE 所在目录. 返回拷贝总数."""
    if not getattr(sys, "frozen", False):
        return 0

    meipass = sys._MEIPASS
    # v5.4-s7: EXE 目录作为根, 而非 CWD (U盘/跨机器场景)
    target = os.path.dirname(sys.executable)
    total = 0

    # 1) 先创建运行时目录
    _create_dirs(verbose)

    # 2) 再拷贝资源
    for src_sub, dst_sub, is_dir in RESOURCE_MANIFEST:
        src = os.path.join(meipass, src_sub)
        dst = os.path.join(target, dst_sub)

        if not os.path.exists(src):
            if verbose:
                print(f"[bootstrap] SKIP: {src_sub} not bundled")
            continue

        if is_dir:
            n = _copy_tree(src, dst, verbose)
            if verbose and n:
                print(f"[bootstrap] {src_sub}/ -> {os.path.relpath(dst)}/ ({n} files)")
            total += 1 if n >= 0 else 0
        else:
            if os.path.exists(dst) and not force:
                if verbose:
                    print(f"[bootstrap] SKIP: {dst_sub} already exists")
                continue
            os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
            if _copy_file(src, dst, verbose):
                total += 1

    return total
