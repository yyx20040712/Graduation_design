"""
sync_mods.py — 模组目录同步工具 (v5.1)

将 ddesign_tool/mods/ (生产目录) 单向同步到 mods/ (测试目录).
也可作为 validator --sync 子命令使用.

使用:
    # 直接运行
    python -m tools.sync_mods

    # validator 子命令
    python -m validator --sync

    # 预览模式 (不实际写入)
    python -m tools.sync_mods --dry-run
"""

from __future__ import annotations

import filecmp
import shutil
import sys
from pathlib import Path


def sync_mods(
    src_dir: str | Path | None = None,
    dst_dir: str | Path | None = None,
    dry_run: bool = False,
) -> list[str]:
    """同步 ddesign_tool/mods/ → mods/ (单向: 生产 → 测试)

    Args:
        src_dir: 源目录 (生产), 默认 ddesign_tool/mods/
        dst_dir: 目标目录 (测试), 默认 mods/
        dry_run: True 时只报告差异,不实际写入

    Returns:
        已同步的文件相对路径列表
    """
    from _paths import get_app_root

    root = Path(get_app_root()).parent if src_dir is None else Path(src_dir).parent.parent

    if src_dir is None:
        src_dir = root / "ddesign_tool" / "mods"
    if dst_dir is None:
        dst_dir = root / "mods"

    src = Path(src_dir)
    dst = Path(dst_dir)

    synced: list[str] = []
    skipped: list[str] = []

    if not src.exists():
        print(f"[ERROR] 源目录不存在: {src}")
        return synced

    for sf in sorted(src.rglob("*")):
        if sf.is_dir():
            continue
        if "__pycache__" in str(sf):
            continue

        rel = sf.relative_to(src)
        df = dst / rel

        if not df.exists():
            if not dry_run:
                df.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(sf), str(df))
            synced.append(str(rel))
            print(f"  + {rel}")
        elif not filecmp.cmp(str(sf), str(df), shallow=False):
            if not dry_run:
                shutil.copy2(str(sf), str(df))
            synced.append(str(rel))
            print(f"  * {rel}")

    for df in sorted(dst.rglob("*")):
        if df.is_dir() or "__pycache__" in str(df):
            continue
        rel = df.relative_to(dst)
        sf2 = src / rel
        if not sf2.exists():
            skipped.append(str(rel))
            print(f"  ? {rel} (仅存在于测试目录)")

    print(f"\n同步完成: {len(synced)} 个文件已同步, {len(skipped)} 个仅测试目录")
    return synced


def main(argv: list[str] | None = None) -> int:
    """CLI 入口

    Flags:
        --dry-run, -n: 预览模式,不实际写入
        --check, -c:   CI 模式,有差异时 exit 1
        --reverse, -r: 反向同步 (测试 → 生产)
    """
    if argv is None:
        argv = sys.argv[1:]

    dry_run = "--dry-run" in argv or "-n" in argv
    check_mode = "--check" in argv or "-c" in argv
    reverse = "--reverse" in argv or "-r" in argv

    if check_mode and not dry_run:
        dry_run = True  # check mode implies dry-run

    if reverse:
        # 反向: mods/ → ddesign_tool/mods/
        from _paths import get_app_root
        root = Path(get_app_root()).parent
        src = root / "mods"
        dst = root / "ddesign_tool" / "mods"
    else:
        src = dst = None  # use defaults (production → test)

    synced = sync_mods(src_dir=src, dst_dir=dst, dry_run=dry_run)

    if check_mode and synced:
        print("\n[FAIL] 模组目录不同步! 请运行 sync_mods 修复.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
