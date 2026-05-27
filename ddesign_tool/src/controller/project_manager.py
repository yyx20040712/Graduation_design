"""
project_manager.py — 项目文件管理

功能:
  - .ddesign.json 项目的读写
  - 自动保存
  - 最近文件列表管理
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from _logging import get_logger

# 默认项目目录
from _paths import get_projects_dir

from .graph_executor import GraphExecutor, default_node_factory

_log = get_logger(__name__)
DEFAULT_PROJECT_DIR = Path(get_projects_dir())

# 最近文件记录路径
RECENT_FILES_PATH = DEFAULT_PROJECT_DIR.parent / ".recent_projects.json"


class ProjectManager:
    """项目文件管理器"""

    def __init__(self, projects_dir: Optional[Path] = None):
        self._projects_dir = projects_dir or DEFAULT_PROJECT_DIR
        self._projects_dir.mkdir(parents=True, exist_ok=True)
        self._current_path: Optional[Path] = None
        self._executor: Optional[GraphExecutor] = None
        self._autosave_interval: int = 120  # 秒

    @property
    def current_path(self) -> Optional[Path]:
        return self._current_path

    @property
    def executor(self) -> Optional[GraphExecutor]:
        return self._executor

    # ── 保存 ──

    def save(
        self,
        executor: GraphExecutor,
        metadata: Optional[Dict[str, str]] = None,
        filepath: Optional[Path] = None,
    ) -> Path:
        """保存项目到文件"""
        self._executor = executor

        if filepath is None:
            filepath = self._current_path or self._generate_filename(metadata)

        # 构建项目数据
        graph_data = executor.to_dict()

        # 收集约束覆盖
        constraint_overrides = self._collect_constraint_overrides(executor)

        project_data = {
            "format_version": "5.1",
            "metadata": {
                "name": (metadata or {}).get("name", "未命名项目"),
                "author": (metadata or {}).get("author", ""),
                "created": (metadata or {}).get("created", datetime.now().isoformat()),
                "modified": datetime.now().isoformat(),
                "description": (metadata or {}).get("description", ""),
            },
            "graph": graph_data,
            "constraint_overrides": constraint_overrides,
        }

        save_path = Path(filepath)
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(project_data, f, ensure_ascii=False, indent=2)

        self._current_path = save_path
        self._add_to_recent(save_path)

        return self._current_path

    def autosave(self) -> Optional[Path]:
        """自动保存到 .autosave/ 目录"""
        if not self._executor:
            return None

        autosave_dir = self._projects_dir / ".autosave"
        autosave_dir.mkdir(parents=True, exist_ok=True)

        base_name = self._current_path.stem if self._current_path else "autosave"
        filename = autosave_dir / f"{base_name}_{int(time.time())}.ddesign.json"

        return self.save(self._executor, filepath=filename)

    # ── 加载 ──

    def load(self, filepath: Path) -> GraphExecutor:
        """从文件加载项目

        Returns:
            重建的 GraphExecutor

        Raises:
            FileNotFoundError: 文件不存在
            json.JSONDecodeError: JSON 格式错误
        """
        if not filepath.exists():
            raise FileNotFoundError(f"项目文件不存在: {filepath}")

        with open(filepath, "r", encoding="utf-8") as f:
            project_data = json.load(f)

        version = project_data.get("format_version", project_data.get("version", "1.0"))
        graph_data = project_data.get("graph", {})

        # ── 版本迁移 ──
        if version != "5.1":
            _log.warning("项目文件版本 %s (当前 5.1),加载时可能丢失部分数据.", version)

        executor = GraphExecutor.from_dict(
            graph_data, node_factory=default_node_factory
        )

        # 恢复约束覆盖
        constraint_overrides = project_data.get("constraint_overrides", {})
        self._apply_constraint_overrides(constraint_overrides)

        self._executor = executor
        self._current_path = Path(filepath)
        self._add_to_recent(filepath)

        return executor

    def new_project(self) -> GraphExecutor:
        """创建新项目"""
        self._executor = GraphExecutor()
        self._current_path = None
        return self._executor

    # ── 最近文件 ──

    def _add_to_recent(self, filepath: Path) -> None:
        """记录到最近文件列表"""
        recent = self.get_recent_files()
        path_str = str(filepath.resolve())

        # 去重并移到最前
        if path_str in recent:
            recent.remove(path_str)
        recent.insert(0, path_str)

        # 只保留最近 20 个
        recent = recent[:20]

        with open(RECENT_FILES_PATH, "w", encoding="utf-8") as f:
            json.dump(recent, f, ensure_ascii=False)

    @staticmethod
    def get_recent_files() -> List[str]:
        """获取最近文件列表"""
        if not RECENT_FILES_PATH.exists():
            return []
        try:
            with open(RECENT_FILES_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []

    # ── 辅助 ──

    def _generate_filename(self, metadata: Optional[Dict[str, str]] = None) -> Path:
        """生成默认文件名"""
        name = (metadata or {}).get("name", "未命名项目")
        safe_name = "".join(c for c in name if c.isalnum() or c in "._- ").strip()
        if not safe_name:
            safe_name = "untitled"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return self._projects_dir / f"{safe_name}_{timestamp}.ddesign.json"

    @staticmethod
    def _collect_constraint_overrides(executor: GraphExecutor) -> Dict[str, dict]:
        """收集所有已修改的约束限制值

        遍历图中所有非IO节点, 读取其 discretization.json 中的当前
        constraint_limits, 与默认值比较后仅保存被修改的条目.

        Returns:
            {node_type: {"constraint_limits": {...}}}
        """
        overrides = {}
        try:
            from models.discretization import get_config

            seen_types = set()
            for node in executor._nodes.values():
                nt = node.NODE_TYPE
                if nt in seen_types:
                    continue
                seen_types.add(nt)
                try:
                    cfg = get_config(nt)
                except KeyError:
                    continue
                limits = cfg.get("constraint_limits", {})
                if limits:
                    overrides[nt] = {"constraint_limits": dict(limits)}
        except ImportError:
            pass
        return overrides

    @staticmethod
    def _apply_constraint_overrides(overrides: Dict[str, dict]) -> None:
        """应用保存的约束覆盖值到运行时配置

        Args:
            overrides: {node_type: {"constraint_limits": {...}}}
        """
        if not overrides:
            return
        try:
            from models.discretization import get_config
            from models.solution_space import set_constraint_limits

            for node_type, data in overrides.items():
                limits = data.get("constraint_limits", {})
                if limits:
                    # 更新 discretization 配置
                    try:
                        cfg = get_config(node_type)
                        if "constraint_limits" not in cfg:
                            cfg["constraint_limits"] = {}
                        cfg["constraint_limits"].update(limits)
                    except KeyError:
                        pass
                    # 更新 solution_space 运行时覆盖
                    set_constraint_limits(node_type, limits)
        except ImportError:
            pass


# ── 单例(可选)──
_project_manager: Optional[ProjectManager] = None


def get_project_manager() -> ProjectManager:
    """获取全局 ProjectManager 单例"""
    global _project_manager
    if _project_manager is None:
        _project_manager = ProjectManager()
    return _project_manager
