"""
test_bootstrap.py — 资源提取模块单元测试
"""
import os
import sys
import tempfile
import shutil
from unittest.mock import patch, MagicMock, call

import pytest

# Ensure we can import bootstrap even from tests/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ddesign_tool", "src"))
from bootstrap import extract_resources, RESOURCE_MANIFEST


class TestExtractResourcesSourceMode:
    """Source mode: extract_resources is a no-op."""

    def test_returns_zero_in_source_mode(self):
        """In source mode (not frozen), returns 0 immediately."""
        assert not getattr(sys, "frozen", False), "Test must run in source mode"
        result = extract_resources(verbose=False)
        assert result == 0

    def test_no_file_operations_in_source_mode(self):
        """extract_resources does not touch filesystem in source mode."""
        with patch("os.path.exists") as mock_exists:
            extract_resources(verbose=False)
            mock_exists.assert_not_called()


class TestExtractResourcesFrozenMode:
    """Frozen mode: verify extraction logic with mocked MEIPASS."""

    @pytest.fixture
    def tmp_cwd(self):
        """Create a temporary working directory."""
        old_cwd = os.getcwd()
        tmp = tempfile.mkdtemp(prefix="bootstrap_test_cwd_")
        os.chdir(tmp)
        yield tmp
        os.chdir(old_cwd)
        shutil.rmtree(tmp, ignore_errors=True)

    @pytest.fixture
    def tmp_meipass(self):
        """Create a temporary MEIPASS directory with dummy resources."""
        tmp = tempfile.mkdtemp(prefix="bootstrap_test_meipass_")
        # Create dummy resources
        os.makedirs(os.path.join(tmp, "mods", "core"), exist_ok=True)
        os.makedirs(os.path.join(tmp, "data"), exist_ok=True)
        os.makedirs(os.path.join(tmp, "knowledge"), exist_ok=True)
        os.makedirs(os.path.join(tmp, "output_template"), exist_ok=True)
        # Create dummy files
        with open(os.path.join(tmp, "config.ini"), "w") as f:
            f.write("[test]\nkey=value\n")
        with open(os.path.join(tmp, "MODS_GUIDE.md"), "w") as f:
            f.write("# Test MODS_GUIDE\n")
        with open(os.path.join(tmp, "README.md"), "w") as f:
            f.write("# Test README\n")
        with open(os.path.join(tmp, "yyx.ddesign.json"), "w") as f:
            f.write('{"test": true}\n')
        yield tmp
        shutil.rmtree(tmp, ignore_errors=True)

    def test_copies_missing_resources(self, tmp_cwd, tmp_meipass):
        """In frozen mode, copies resources that don't exist in cwd."""
        with patch.object(sys, "frozen", True, create=True), \
             patch.object(sys, "_MEIPASS", tmp_meipass, create=True):
            count = extract_resources(verbose=False)
            assert count > 0
            # Verify key resources were copied
            assert os.path.exists(os.path.join(tmp_cwd, "config.ini"))
            assert os.path.exists(os.path.join(tmp_cwd, "mods"))
            assert os.path.exists(os.path.join(tmp_cwd, "data"))
            assert os.path.exists(os.path.join(tmp_cwd, "knowledge"))
            assert os.path.exists(os.path.join(tmp_cwd, "output"))
            assert os.path.exists(os.path.join(tmp_cwd, "MODS_GUIDE.md"))
            assert os.path.exists(os.path.join(tmp_cwd, "README.md"))
            assert os.path.exists(os.path.join(tmp_cwd, "yyx.ddesign.json"))

    def test_skips_existing_resources(self, tmp_cwd, tmp_meipass):
        """Second run should skip already-extracted resources."""
        # First extraction
        with patch.object(sys, "frozen", True, create=True), \
             patch.object(sys, "_MEIPASS", tmp_meipass, create=True):
            extract_resources(verbose=False)

        # Second extraction — should copy 0 (all exist)
        with patch.object(sys, "frozen", True, create=True), \
             patch.object(sys, "_MEIPASS", tmp_meipass, create=True):
            count = extract_resources(verbose=False)
            assert count == 0

    def test_force_overwrites_existing(self, tmp_cwd, tmp_meipass):
        """force=True should overwrite existing resources."""
        # First extraction
        with patch.object(sys, "frozen", True, create=True), \
             patch.object(sys, "_MEIPASS", tmp_meipass, create=True):
            extract_resources(verbose=False)

        # Force extraction — should copy again
        with patch.object(sys, "frozen", True, create=True), \
             patch.object(sys, "_MEIPASS", tmp_meipass, create=True):
            count = extract_resources(force=True, verbose=False)
            assert count > 0

    def test_handles_missing_source_gracefully(self, tmp_cwd):
        """If source doesn't exist in MEIPASS, skip without crashing."""
        empty_meipass = tempfile.mkdtemp(prefix="bootstrap_test_empty_")
        try:
            with patch.object(sys, "frozen", True, create=True), \
                 patch.object(sys, "_MEIPASS", empty_meipass, create=True):
                count = extract_resources(verbose=False)
                assert count == 0  # Nothing to copy
        finally:
            shutil.rmtree(empty_meipass, ignore_errors=True)

    def test_output_template_maps_to_output_dir(self, tmp_cwd, tmp_meipass):
        """output_template/ in MEIPASS → output/ in cwd."""
        with patch.object(sys, "frozen", True, create=True), \
             patch.object(sys, "_MEIPASS", tmp_meipass, create=True):
            extract_resources(verbose=False)
            assert os.path.isdir(os.path.join(tmp_cwd, "output"))
            # output_template should NOT exist as a dir name in cwd
            assert not os.path.exists(os.path.join(tmp_cwd, "output_template"))
