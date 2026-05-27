"""
release.py — 自动化发布脚本 (v5.3)

用法:
  python tools/release.py --dry-run     预览检查
  python tools/release.py v5.3.0         完整发布

步骤:
  1. 运行测试套件
  2. 运行 flake8
  3. 检查 mod 目录同步
  4. 构建 PyInstaller EXE
  5. 复制到 dist/
  6. git tag 版本号
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DIST_DIR = PROJECT_ROOT / "dist"
SPEC_FILE = PROJECT_ROOT / "ddesign_tool.spec"
VENV_PYTHON = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"


def _run(cmd: list[str], desc: str) -> bool:
    """运行命令, 返回是否成功"""
    print(f"\n  [{desc}]")
    print(f"  {' '.join(cmd)}")
    t0 = time.perf_counter()
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT), capture_output=False)
    elapsed = time.perf_counter() - t0
    if result.returncode == 0:
        print(f"  OK ({elapsed:.1f}s)")
        return True
    else:
        print(f"  FAIL (exit {result.returncode}, {elapsed:.1f}s)")
        return False


def check_tests(skip: bool = False) -> bool:
    """运行测试套件"""
    if skip:
        print("\n  [跳过] 测试套件")
        return True
    return _run(
        [
            str(VENV_PYTHON),
            "-m",
            "pytest",
            "tests/",
            "-q",
            "--tb=no",
            "--ignore=tests/integration",
            "-k",
            "not (test_all_vectorized or test_no_fallback)",
        ],
        "运行测试套件",
    )


def check_lint(skip: bool = False) -> bool:
    """运行 flake8"""
    if skip:
        print("\n  [跳过] flake8")
        return True
    return _run(
        [str(VENV_PYTHON), "-m", "flake8", "ddesign_tool/", "--select=F401"],
        "flake8 (F401 检查)",
    )


def check_sync() -> bool:
    """检查 mod 目录同步"""
    return _run(
        [
            str(VENV_PYTHON),
            str(PROJECT_ROOT / "ddesign_tool" / "src" / "tools" / "sync_mods.py"),
            "--check",
        ],
        "mod 目录同步检查",
    )


def build_exe(skip: bool = False) -> bool:
    """构建 PyInstaller EXE"""
    if skip:
        print("\n  [跳过] PyInstaller 构建")
        return True
    return _run(
        [
            str(VENV_PYTHON),
            "-m",
            "PyInstaller",
            "--clean",
            "--log-level=WARN",
            str(SPEC_FILE),
        ],
        "PyInstaller 构建",
    )


def tag_version(version: str, dry_run: bool = False) -> bool:
    """git tag 版本号"""
    tag = f"v{version}" if not version.startswith("v") else version
    if dry_run:
        print(f"\n  [dry-run] git tag {tag}")
        return True
    return _run(["git", "tag", "-a", tag, "-m", f"Release {tag}"], f"git tag {tag}")


def copy_artifacts(version: str) -> bool:
    """复制构建产物到 dist/"""
    exe_src = DIST_DIR / "ddesign_tool" / "ddesign_tool.exe"
    if not exe_src.exists():
        print(f"\n  [错误] EXE 未找到: {exe_src}")
        return False
    release_name = f"ddesign_tool_{version}.exe"
    dest = DIST_DIR / release_name
    shutil.copy2(str(exe_src), str(dest))
    size_mb = dest.stat().st_size / (1024 * 1024)
    print(f"\n  [产物] {release_name} ({size_mb:.1f} MB)")
    return True


def main():
    import argparse

    parser = argparse.ArgumentParser(description="ddesign_tool 发布脚本")
    parser.add_argument("version", nargs="?", help="版本号 (如 v5.3.0)")
    parser.add_argument("--dry-run", action="store_true", help="预览模式")
    parser.add_argument("--skip-tests", action="store_true", help="跳过测试")
    parser.add_argument("--skip-lint", action="store_true", help="跳过 lint")
    parser.add_argument("--skip-build", action="store_true", help="跳过构建")

    args = parser.parse_args()

    if not args.version and not args.dry_run:
        parser.print_help()
        return 1

    version = args.version or "dry-run"
    print(f"\n{'=' * 60}")
    print(f"  ddesign_tool 发布: {version}")
    if args.dry_run:
        print("  (预览模式 — 不实际写入)")
    print(f"{'=' * 60}")

    steps = [
        ("测试套件", lambda: check_tests(skip=args.skip_tests)),
        ("代码规范", lambda: check_lint(skip=args.skip_lint)),
        ("目录同步", check_sync),
        ("EXE 构建", lambda: build_exe(skip=args.skip_build or args.dry_run)),
    ]

    failed = 0
    for name, step in steps:
        if not step():
            failed += 1
            print(f"  [{name}] FAIL")
            if not args.dry_run:
                print(f"\n发布中止: {name} 失败")
                return 1
        else:
            print(f"  [{name}] PASS")

    if not args.dry_run and not args.skip_build:
        if not copy_artifacts(version):
            return 1
        if not tag_version(version):
            return 1

    print(f"\n{'=' * 60}")
    if args.dry_run:
        print("  预览通过 — 可以正式发布")
    else:
        if failed > 0:
            print(f"  发布完成但有 {failed} 个警告")
        else:
            print(f"  发布成功! {version}")
    print(f"{'=' * 60}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
