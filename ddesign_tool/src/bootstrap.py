"""
Bootstrap — PyInstaller 资源提取 (v5.4-s7)

启动时从 sys._MEIPASS 将打包资源拷贝到 EXE 所在目录。
源码模式下为 no-op。

资源清单与 ddesign_tool.spec 的 datas 列表对应:
  spec datas                          → MEIPASS 路径    → EXE 目标
  ─────────────────────────────────────────────────────────────
  ("ddesign_tool/config.ini", ".")    → config.ini      → config.ini
  ("ddesign_tool/mods", "mods")       → mods/           → mods/
  ("ddesign_tool/data", "data")       → data/           → data/
  (".sisyphus/notepads", "knowledge") → knowledge/      → knowledge/
  ("ddesign_tool/resources","resources") → resources/   → ./ (平铺)

⚠ 修改 spec datas 时, 务必同步更新下方的 RESOURCE_MANIFEST.
"""

import os
import shutil
import sys
import time

from _logging import get_logger

_log = get_logger(__name__)

# ── 资源清单 ──
# 格式: {MEIPASS路径: (EXE目标路径, 是目录?)}
# 目标 "." = 目录内容平铺到 EXE 根目录
# 不存在的条目会静默跳过 (verbose 模式下打印 SKIP)
RESOURCE_MANIFEST: dict[str, tuple[str, bool]] = {
    "config.ini": ("config.ini", False),
    "mods": ("mods", True),
    "data": ("data", True),
    "knowledge": ("knowledge", True),
    "resources": (".", True),  # 平铺: README, 演示项目, 使用说明等
    "output_template": (".", True),  # 兼容旧版打包
}

# ── 运行时目录 (始终在 EXE 目录创建) ──
RUNTIME_DIRS = ["output", "logs", "cache", "projects"]


def _copy_file(src: str, dst: str, verbose: bool) -> bool:
    """拷贝单个文件, 带 3 次重试"""
    for attempt in range(3):
        try:
            shutil.copy2(src, dst)
            if verbose:
                print(f"[bootstrap] + {os.path.basename(dst)}")
            return True
        except PermissionError:
            if attempt < 2:
                time.sleep(0.2)
        except OSError:
            return False
    return False


def _copy_tree(src: str, dst: str, verbose: bool) -> int:
    """递归合并目录树.

    仅拷贝缺失文件, 永不覆盖已有文件 (保护用户数据).
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


def _create_dirs(target: str, verbose: bool) -> None:
    """预创建运行时输出目录"""
    for name in RUNTIME_DIRS:
        path = os.path.join(target, name)
        try:
            os.makedirs(path, exist_ok=True)
            if verbose:
                print(f"[bootstrap] mkdir {name}/")
        except OSError:
            pass


def _debug_meipass(meipass: str) -> None:
    """调试: 列出 MEIPASS 顶层内容 (通过 DDESIGN_BOOTSTRAP_DEBUG=1 启用)"""
    if not os.environ.get("DDESIGN_BOOTSTRAP_DEBUG"):
        return
    print("[bootstrap] === MEIPASS contents ===")
    for name in sorted(os.listdir(meipass)):
        path = os.path.join(meipass, name)
        tag = "/" if os.path.isdir(path) else ""
        size = ""
        if not os.path.isdir(path):
            try:
                size = f" ({os.path.getsize(path):,} B)"
            except OSError:
                pass
        marker = " ← IN MANIFEST" if name in RESOURCE_MANIFEST else ""
        print(f"  {name}{tag}{size}{marker}")
    print("[bootstrap] ========================")


def extract_resources(force: bool = False, verbose: bool = True) -> int:
    """从 MEIPASS 提取资源到 EXE 所在目录.

    Args:
        force: 强制覆盖已有文件 (默认 False, 永不覆盖用户数据)
        verbose: 打印提取日志

    Returns:
        成功处理的条目数 (目录算 1, 即使无文件拷贝)
    """
    if not getattr(sys, "frozen", False):
        return 0

    meipass = sys._MEIPASS
    target = os.path.dirname(sys.executable)
    total = 0

    _debug_meipass(meipass)

    # 1) 创建运行时目录
    _create_dirs(target, verbose)

    # 2) 提取资源
    if verbose:
        print(f"[bootstrap] Extracting resources to {target} ...")

    for src_sub, (dst_sub, is_dir) in RESOURCE_MANIFEST.items():
        src = os.path.join(meipass, src_sub)

        if not os.path.exists(src):
            if verbose:
                print(f"[bootstrap] SKIP: {src_sub}/ not in build")
            continue

        if is_dir:
            dst = os.path.join(target, dst_sub) if dst_sub != "." else target
            n = _copy_tree(src, dst, verbose)
            if verbose and n > 0:
                rel = os.path.relpath(dst) if dst_sub != "." else "(root)"
                print(f"[bootstrap] {src_sub}/ → {rel} ({n} files)")
            total += 1
        else:
            dst = os.path.join(target, dst_sub)
            if os.path.exists(dst) and not force:
                if verbose:
                    print(f"[bootstrap] SKIP: {dst_sub} already exists")
                total += 1
                continue
            os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
            if _copy_file(src, dst, verbose):
                total += 1

    if verbose:
        print(f"[bootstrap] Done: {total} items processed")
    return total
