"""

mod_manager.py — 模组管理器



负责模组的发现、加载、注册和管理.

类似 Minecraft 的 Forge/Fabric,提供统一的模组生命周期管理.

"""

from __future__ import annotations


import json

import importlib

import logging

import sys

import threading
from dataclasses import dataclass, field

from pathlib import Path

from typing import Any, Dict, List, Optional, Type, Tuple

log = logging.getLogger("ModManager")


# ═════════════════════════════════════════════════════════════════════

# 数据类

# ═════════════════════════════════════════════════════════════════════


@dataclass
class ModParameter:
    """模组参数定义"""

    key: str

    symbol: str

    name: str

    unit: str = ""

    default: float = 0.0

    min: float = 0.0

    max: float = 100.0

    step: float = 0.1

    description: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "ModParameter":

        return cls(
            key=d["key"],
            symbol=d.get("symbol", d["key"]),
            name=d.get("name", d["key"]),
            unit=d.get("unit", ""),
            default=d.get("default", 0.0),
            min=d.get("min", 0.0),
            max=d.get("max", 100.0),
            step=d.get("step", 0.1),
            description=d.get("description", ""),
        )


@dataclass
class ModPort:
    """模组端口定义"""

    type: str  # "WATER" | "QUALITY" | "MIXED"

    name: str

    @classmethod
    def from_dict(cls, d: dict) -> "ModPort":

        return cls(type=d["type"], name=d["name"])


@dataclass
class ModInfo:
    """模组元数据信息"""

    id: str

    name: str

    version: str

    author: str

    description: str

    category: str = "未分类"

    process_stage: str = ""  # io|primary|secondary|tertiary|mine_water

    icon: str = "📦"

    node_type: str = ""

    node_class: str = ""

    module_path: str = ""

    inputs: List[ModPort] = field(default_factory=list)

    outputs: List[ModPort] = field(default_factory=list)

    parameters: List[ModParameter] = field(default_factory=list)

    removal_rates: Dict[str, float] = field(default_factory=dict)

    formula: str = ""

    formula_detail: str = ""

    elevation_formula: str = ""

    elevation_loss: Dict[str, Any] = field(default_factory=dict)

    dependencies: List[str] = field(default_factory=list)

    tags: List[str] = field(default_factory=list)

    references: List[str] = field(default_factory=list)

    # 运行时状态

    loaded: bool = False

    node_cls: Optional[Type] = None

    mod_dir: str = ""

    @classmethod
    def from_json(cls, path: str, mod_dir: str = "") -> "ModInfo":
        """从 mod.json 加载"""

        with open(path, "r", encoding="utf-8") as f:

            data = json.load(f)

        return cls(
            id=data["id"],
            name=data["name"],
            version=data.get("version", "1.0.0"),
            author=data.get("author", "Unknown"),
            description=data.get("description", ""),
            category=data.get("category", "未分类"),
            process_stage=data.get("process_stage", ""),
            icon=data.get("icon", "📦"),
            node_type=data.get("node_type", data["id"]),
            node_class=data.get("node_class", ""),
            module_path=data.get("module_path", ""),
            inputs=[ModPort.from_dict(p) for p in data.get("inputs", [])],
            outputs=[ModPort.from_dict(p) for p in data.get("outputs", [])],
            parameters=[ModParameter.from_dict(p) for p in data.get("parameters", [])],
            removal_rates=data.get("removal_rates", {}),
            formula=data.get("formula", ""),
            formula_detail=data.get("formula_detail", ""),
            elevation_formula=data.get("elevation_formula", ""),
            elevation_loss=data.get("elevation_loss", {}),
            dependencies=data.get("dependencies", []),
            tags=data.get("tags", []),
            references=data.get("references", []),
            mod_dir=mod_dir,
        )


# ═════════════════════════════════════════════════════════════════════

# ModManager

# ═════════════════════════════════════════════════════════════════════


class ModManager:
    """模组管理器 — 单例



    负责:

    1. 扫描 mods/core/ 和 mods/community/ 目录

    2. 加载 mod.json 元数据

    3. 动态导入节点类

    4. 注册到全局 NODE_REGISTRY 和 FORMULAS

    5. 提供分类菜单数据

    """

    _instance: Optional["ModManager"] = None
    _lock: "threading.Lock" = threading.Lock()  # 线程安全锁

    def __new__(cls) -> "ModManager":

        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False

        return cls._instance

    def __init__(self):

        if self._initialized:

            return

        with self._lock:
            if self._initialized:
                return
            self._initialized = True

        self._mods: Dict[str, ModInfo] = {}  # mod_id → ModInfo

        self._node_registry: Dict[str, Tuple[Type, str]] = (
            {}
        )  # node_type → (class, display_name)

        self._formulas: Dict[str, str] = {}  # node_type → formula_string

        self._categories: Dict[str, List[str]] = {}  # category → [node_type, ...]

        self._load_errors: list = []  # [{mod_id, severity, errors}]

        self._loaded = False

    # ── 公共属性 ──

    @property
    def node_registry(self) -> Dict[str, Tuple[Type, str]]:
        """返回 NODE_REGISTRY 兼容格式"""

        if not self._node_registry:

            self.load_all()

        return self._node_registry

    @property
    def formulas(self) -> Dict[str, str]:
        """返回 FORMULAS 兼容格式"""

        if not self._formulas:

            self.load_all()

        return self._formulas

    @property
    def categories(self) -> Dict[str, List[str]]:
        """返回分类菜单数据 {category: [node_type, ...]}"""

        if not self._categories:

            self.load_all()

        return self._categories

    @property
    def mods(self) -> Dict[str, ModInfo]:
        """返回所有已发现的模组"""

        if not self._mods:

            self.discover_all(force_rescan=True)

        return self._mods

    # ── 模组发现 (v5.4: 委托给 mod_discovery) ──

    def discover_all(self, force_rescan: bool = False) -> None:
        """扫描并加载所有模组."""
        from _paths import get_mods_dir
        from . import mod_discovery

        with self._lock:
            self._loaded = mod_discovery.discover_mods(
                mods_root=Path(get_mods_dir()),
                mods=self._mods,
                errors=self._load_errors,
                validate_fn=_validate_mod_json,
                schema_validate_fn=_validate_with_schema,
                force_rescan=force_rescan,
                already_loaded=self._loaded,
            )
        log.info(
            "ModManager: discovered %d mods, registered %d node types",
            len(self._mods),
            len(self._node_registry),
        )

    def _scan_directory(self, directory: Path) -> None:
        """[DEPRECATED] 使用 mod_discovery.scan_directory 替代."""
        from . import mod_discovery

        mod_discovery.scan_directory(
            directory,
            self._mods,
            self._load_errors,
            _validate_mod_json,
            _validate_with_schema,
        )

    # ── 模组加载 ──

    def load_mod(self, mod_id: str) -> Optional[Type]:
        """加载指定模组的节点类 (v5.4: delegate to mod_discovery).

        Returns:
            节点类(NodeBase 子类),失败返回 None
        """
        mod_info = self._mods.get(mod_id)
        if not mod_info:
            log.warning("ModManager: mod [%s] not found", mod_id)
            return None

        if mod_info.loaded and mod_info.node_cls:
            return mod_info.node_cls

        from . import mod_discovery

        node_cls = mod_discovery.load_mod_module(mod_info)
        if node_cls:
            self._register_node(mod_info)
        return node_cls

        if mod_info.loaded and mod_info.node_cls:

            return mod_info.node_cls

        try:

            # ── MC式: 优先从 mod 目录的 __init__.py 导入(自包含模组)──

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

                        self._register_node(mod_info)

                        log.info(
                            "ModManager: loaded mod [%s] (from __init__.py)", mod_id
                        )

                        return node_cls

                except ImportError:

                    pass  # __init__.py 加载失败,回退到 module_path

            # 备选方案: 从 module_path 导入(兼容旧式 models/ 分离模组)

            if mod_info.module_path:

                module = importlib.import_module(mod_info.module_path)

                node_cls = getattr(module, mod_info.node_class, None)

                if node_cls:

                    mod_info.node_cls = node_cls

                    mod_info.loaded = True

                    self._register_node(mod_info)

                    log.info(
                        "ModManager: loaded mod [%s] (from %s)",
                        mod_id,
                        mod_info.module_path,
                    )

                    return node_cls

            log.warning(
                "ModManager: cannot find node class %s for mod [%s]",
                mod_info.node_class,
                mod_id,
            )

        except Exception as e:

            log.error("ModManager: failed to load mod [%s]: %s", mod_id, e)

        return None

    def load_all(self) -> None:
        """加载所有模组并注册"""

        if not self._mods:

            self.discover_all(force_rescan=True)

        for mod_id in list(self._mods.keys()):

            self.load_mod(mod_id)

        # ── 同步到统一注册表 ──

        try:

            from models.node_registry import get_registry

            get_registry().register_from_mod_manager(self)

            log.debug(
                "Node registry synchronized: %d types",
                len(get_registry().get_all_types()),
            )

        except Exception as e:

            log.warning("Failed to sync node registry: %s", e)

        # ── 延迟验证向量化输出 (避免递归) ──

        for mod_id in list(self._mods.keys()):

            self._validate_vectorized_output(self._mods[mod_id])

    # ── 注册 ──

    def _register_node(self, mod_info: ModInfo) -> None:
        """将模组注册到 NODE_REGISTRY 和 FORMULAS,并验证向量化计算输出"""

        if not mod_info.node_cls:

            return

        node_type = mod_info.node_type

        # NODE_REGISTRY 格式: {node_type: (NodeClass, display_name)}

        self._node_registry[node_type] = (mod_info.node_cls, mod_info.name)

        # ── 触发生命周期: 通知监听器新模组已注册 ──

        try:

            from models.node_registry import _fire_register

            _fire_register(mod_info.id, node_type, mod_info.node_cls)

        except Exception:
            log.warning(
                "ModManager: _fire_register failed for %s", mod_info.id, exc_info=True
            )

        # FORMULAS 格式: {node_type: formula_string}

        if mod_info.formula:

            formula_text = mod_info.formula

            if mod_info.formula_detail:

                formula_text += f"\n   ({mod_info.formula_detail})"

            self._formulas[node_type] = formula_text

        # 分类

        category = mod_info.category

        if category not in self._categories:

            self._categories[category] = []

        if node_type not in self._categories[category]:

            self._categories[category].append(node_type)

    def _validate_param_consistency(self, mod_info: ModInfo) -> None:
        """Validate mod.json parameters against _build_param_defs()."""
        if not mod_info.node_cls or not mod_info.parameters:
            return
        try:
            node = mod_info.node_cls()
            param_defs = {pd.key: pd for pd in node.get_param_defs()}
            for mp in mod_info.parameters:
                pd = param_defs.get(mp.key)
                if pd is None:
                    self._load_errors.append(
                        {
                            "mod_id": mod_info.id,
                            "severity": "warning",
                            "errors": [f"mod.json param '{mp.key}' not in ParamDef"],
                        }
                    )
        except Exception:
            pass

    def _validate_vectorized_output(self, mod_info: ModInfo) -> None:
        """验证 _vectorized_compute 输出字段与离散化配置一致.



        检查:

        1. 每个 constraint_key 都有对应的 ok_* 和 val_* 字段

        2. concrete_m3 字段存在(成本估算必需)

        错误记录到 self._load_errors,不阻止模组加载.

        """

        # 防止递归: 验证过程中不触发新的加载

        if getattr(self, "_validating", False):

            return

        node_type = mod_info.node_type

        node_cls = mod_info.node_cls

        if not node_cls or not hasattr(node_cls, "_vectorized_compute"):

            return

        # 直接读取 DISCRETE_CONFIGS(不触发 ModManager 加载链)

        try:

            from models.discretization import DISCRETE_CONFIGS

            cfg = DISCRETE_CONFIGS.get(node_type)

            if not cfg:

                return

        except Exception:

            return

        constraint_keys = cfg.get("constraint_keys", [])

        if not constraint_keys:

            return

        # 用默认参数试运行一次向量化计算以获取 dtype

        self._validating = True

        try:

            import numpy as np

            free_cfg = cfg.get("free", {})

            if not free_cfg:

                return

            grid = {}

            for k, vals in free_cfg.items():

                grid[k] = np.array([vals[0]])

            from models.base import WaterFlow, WaterQuality

            result = node_cls._vectorized_compute(
                grid,
                WaterFlow(),
                WaterQuality(),
                {k: v for k, v in cfg.get("fixed", {}).items()},
            )

            dtype_names = set(result.dtype.names)

        except Exception:

            return

        finally:

            self._validating = False

        # 检查 ok_* + val_* 字段

        errors = []

        for ck in constraint_keys:

            ok_field = f"ok_{ck}"

            val_field = f"val_{ck}"

            if ok_field not in dtype_names:

                errors.append(f"missing ok_{ck}")

            if val_field not in dtype_names:

                errors.append(f"missing val_{ck} — robustness will be 0")

        # 检查 concrete_m3

        if "concrete_m3" not in dtype_names:

            errors.append("missing concrete_m3 — cost will be 0")

        if errors:

            self._load_errors.append(
                {
                    "mod_id": mod_info.id,
                    "severity": "warning",
                    "errors": errors,
                }
            )

            log.warning(
                "Mod [%s] vectorized validation: %s", mod_info.id, "; ".join(errors)
            )

    # ── 配置文件加载 (v5.4: 委托给 mod_config 模块) ──

    def _load_json_config(self, mod_id: str, filename: str) -> Optional[dict]:
        """[DEPRECATED] Use mod_config._load_json(mod_info.mod_dir, filename) instead."""
        mod_info = self._mods.get(mod_id)
        if not mod_info or not mod_info.mod_dir:
            return None
        from . import mod_config

        return mod_config._load_json(mod_info.mod_dir, filename)

    def load_discretization(self, mod_id: str) -> Optional[dict]:
        mod_info = self._mods.get(mod_id)
        if not mod_info or not mod_info.mod_dir:
            return None
        from . import mod_config

        return mod_config.load_discretization(mod_info.mod_dir)

    def load_labels(self, mod_id: str) -> Optional[dict]:
        mod_info = self._mods.get(mod_id)
        if not mod_info or not mod_info.mod_dir:
            return None
        from . import mod_config

        return mod_config.load_labels(mod_info.mod_dir)

    def load_equipment(self, mod_id: str) -> Optional[dict]:
        mod_info = self._mods.get(mod_id)
        if not mod_info or not mod_info.mod_dir:
            return None
        from . import mod_config

        return mod_config.load_equipment(mod_info.mod_dir)

    def get_all_discretizations(self) -> Dict[str, dict]:
        from . import mod_config

        return mod_config.get_all_discretizations(
            self._mods, lambda: self.discover_all(force_rescan=True)
        )

    def get_all_labels(self) -> Dict[str, dict]:
        from . import mod_config

        return mod_config.get_all_labels(
            self._mods, lambda: self.discover_all(force_rescan=True)
        )

    def get_all_equipment(self) -> Dict[str, dict]:
        from . import mod_config

        return mod_config.get_all_equipment(
            self._mods, lambda: self.discover_all(force_rescan=True)
        )

    def save_discretization(self, mod_id: str, config: dict) -> bool:
        mod_info = self._mods.get(mod_id)
        if not mod_info or not mod_info.mod_dir:
            return False
        from _paths import get_mods_dir
        import os as _os
        from . import mod_config

        mod_name = _os.path.basename(mod_info.mod_dir)
        runtime_dir = _os.path.join(get_mods_dir(), "core", mod_name)
        app_root = _os.path.abspath(_os.path.join(get_mods_dir(), ".."))
        test_dir = _os.path.join(app_root, "mods", "core", mod_name)
        test_dirs = [runtime_dir]
        if _os.path.isdir(test_dir):
            test_dirs.append(test_dir)
        return mod_config.save_discretization(
            mod_info.mod_dir, mod_id, config, test_dirs
        )

    # ── 查询 ──

    def get_mod(self, mod_id: str) -> Optional[ModInfo]:
        """获取模组信息"""

        return self._mods.get(mod_id)

    def get_node_class(self, node_type: str) -> Optional[Type]:
        """根据 node_type 获取节点类"""

        for mod_info in self._mods.values():

            if mod_info.node_type == node_type:

                return self.load_mod(mod_info.id)

        return None

    def get_category_mods(self, category: str) -> List[ModInfo]:
        """获取指定分类的所有模组"""

        return [m for m in self._mods.values() if m.category == category]

    def list_mods(self) -> List[Dict[str, Any]]:
        """列出所有模组的摘要信息"""

        result = []

        for mod_info in self._mods.values():

            result.append(
                {
                    "id": mod_info.id,
                    "name": mod_info.name,
                    "version": mod_info.version,
                    "author": mod_info.author,
                    "category": mod_info.category,
                    "process_stage": mod_info.process_stage,
                    "loaded": mod_info.loaded,
                    "tags": mod_info.tags,
                }
            )

        return result

    def get_mod_by_node_type(self, node_type: str) -> Optional["ModInfo"]:
        """Find mod by its node_type string (reverse lookup)."""

        if not self._mods:

            self.discover_all(force_rescan=True)

        for mod_info in self._mods.values():

            if mod_info.node_type == node_type:

                return mod_info

        return None

    def register_infra_node(
        self,
        node_type: str,
        node_class: type,
        display_name: str,
        formula: str = "",
        category: str = "Input/Output",
        is_io: bool = True,
    ) -> None:
        """Register an infrastructure node (legacy node without mod.json)."""
        self._node_registry[node_type] = (node_class, display_name)
        if formula:
            self._formulas[node_type] = formula
        if category not in self._categories:
            self._categories[category] = []
        if node_type not in self._categories[category]:
            self._categories[category].append(node_type)
        self._mods[node_type] = ModInfo(
            id=node_type,
            name=display_name,
            version="5.1.0",
            author="Built-in",
            description="",
            category=category,
            process_stage="io" if is_io else "",
            node_type=node_type,
            node_class=node_class.__name__,
            loaded=True,
            node_cls=node_class,
        )

    def get_ui_behavior(self, node_type: str) -> Dict[str, bool]:
        """Get UI behavior flags for a node_type.



        Returns dict with defaults derived from process_stage:

        - is_io_node: True if process_stage == 'io'

        - skip_solution_browser: True if stage not in {primary,secondary,tertiary,mine_water}

        - show_water_quality_card: True if node_type in water quality types

        - skip_cost_estimation: True if is_io_node

        - skip_output_writer: True if is_io_node

        """

        defaults = {
            "is_io_node": False,
            "skip_solution_browser": False,
            "show_water_quality_card": False,
            "skip_cost_estimation": False,
            "skip_output_writer": False,
        }

        # ── 无 mod.json 的 legacy 基础设施节点 ──

        legacy_io = {
            "water_quality",
            "pipe_network",
            "combiner",
            "input_node",
            "kw_input",
        }

        legacy_wq = {"water_quality", "input_node", "kw_input"}

        if node_type in legacy_io:

            defaults["is_io_node"] = True

            defaults["skip_solution_browser"] = True

            defaults["skip_cost_estimation"] = True

            defaults["skip_output_writer"] = True

        if node_type in legacy_wq:

            defaults["show_water_quality_card"] = True

        mod_info = self.get_mod_by_node_type(node_type)

        if not mod_info:

            return defaults

        # Derive defaults from process_stage

        is_io = mod_info.process_stage == "io"

        defaults["is_io_node"] = is_io

        defaults["skip_cost_estimation"] = is_io

        defaults["skip_output_writer"] = is_io

        # ── 方案浏览器: 仅水处理阶段 + 污泥处理阶段节点支持 ──

        # 输入/输出(io)以及未来新增的非计算阶段自动跳过方案浏览器.

        solution_stages = {
            "primary",
            "secondary",
            "tertiary",
            "mine_water",
            "sludge",
            "collection",
        }

        defaults["skip_solution_browser"] = (
            mod_info.process_stage not in solution_stages
        )

        # Water quality card nodes

        wq_card_types = {"water_quality", "input_node", "kw_input"}

        defaults["show_water_quality_card"] = node_type in wq_card_types

        return defaults

    def is_io_node(self, node_type: str) -> bool:
        """Check if a node type is an IO/infrastructure node."""

        return self.get_ui_behavior(node_type).get("is_io_node", False)

    def get_flow_order(self) -> List[Tuple[str, str]]:
        """Auto-derive flow order from process_stage grouping.

        Returns sorted list of (node_type, display_name) tuples.

        """

        if not self._mods:

            self.discover_all(force_rescan=True)

        stage_order = {
            "io": 0,
            "primary": 1,
            "secondary": 2,
            "tertiary": 3,
            "sludge": 4,
            "collection": 5,
            "mine_water": 10,
        }

        mods_by_stage = {s: [] for s in stage_order}

        for mod_info in self._mods.values():

            stage = mod_info.process_stage or "io"

            if stage in stage_order:

                mods_by_stage[stage].append((mod_info.node_type, mod_info.name))

        order = []

        for stage in [
            "io",
            "primary",
            "secondary",
            "tertiary",
            "sludge",
            "collection",
            "mine_water",
            "elevation",
        ]:

            for nt, name in sorted(mods_by_stage.get(stage, []), key=lambda x: x[0]):

                order.append((nt, name))

        return order

    def get_node_class_for_type(self, node_type: str) -> Optional[type]:
        """Get the Python class for a node_type via mod.json resolution.

        Uses module_path + node_class from mod.json to import.

        """

        mod_info = self.get_mod_by_node_type(node_type)

        if not mod_info:

            return None

        if mod_info.node_cls:

            return mod_info.node_cls

        # Try loading

        return self.load_mod(mod_info.id)

    # ── UI 菜单生成 ──

    def get_category_menu(self) -> Dict[str, List[Tuple[str, str]]]:
        """Auto-generate UI category menu structure by process_stage.



        Returns:

            {stage_display_name: [(display_name, node_type), ...]}

        """

        if not self._mods:

            self.discover_all(force_rescan=True)

        # Stage display name mapping

        stage_names = {
            "io": "输入/输出",
            "primary": "一级处理",
            "secondary": "二级处理",
            "tertiary": "深度处理",
            "sludge": "污泥处理",
            "collection": "集配水模组",
            "elevation": "高程模组",
            "mine_water": "矿井水处理",
        }

        # Legacy nodes without mod.json — inferred stage

        legacy = [
            ("管网输入", "pipe_network", "io"),
            ("进水水质", "water_quality", "io"),
            ("合并", "combiner", "io"),
        ]

        # Group by process_stage

        menu: Dict[str, List[Tuple[str, str]]] = {}

        # Add legacy nodes first

        for name, node_type, stage in legacy:

            display_stage = stage_names.get(stage, stage)

            if display_stage not in menu:

                menu[display_stage] = []

            menu[display_stage].append((name, node_type))

        # Add discovered mods

        for mod_info in self._mods.values():

            stage = mod_info.process_stage or "io"

            display_stage = stage_names.get(stage, stage)

            if display_stage not in menu:

                menu[display_stage] = []

            menu[display_stage].append((mod_info.name, mod_info.node_type))

        # Sort within each stage

        for stage in menu:

            menu[stage].sort(key=lambda x: x[1])

        # Ensure consistent stage order

        ordered = {}

        for stage_name in [
            "输入/输出",
            "一级处理",
            "二级处理",
            "深度处理",
            "污泥处理",
            "集配水模组",
            "矿井水处理",
            "高程模组",
        ]:

            if stage_name in menu:

                ordered[stage_name] = menu[stage_name]

        return ordered

    # ── 处理阶段 ──

    # 阶段排序权重(用于自动连线和流程检查)

    STAGE_ORDER: Dict[str, int] = {
        "io": 0,
        "primary": 1,
        "secondary": 2,
        "tertiary": 3,
        "sludge": 4,
        "collection": 5,
        "mine_water": 10,
        "elevation": 20,
    }

    def get_mods_by_stage(self, stage: str) -> List[ModInfo]:
        """获取指定处理阶段的所有模组"""

        if not self._mods:

            self.discover_all(force_rescan=True)

        return [m for m in self._mods.values() if m.process_stage == stage]

    def get_stage_order(self, stage: str) -> int:
        """获取阶段的排序权重"""

        return self.STAGE_ORDER.get(stage, 999)

    def get_stage_name(self, stage: str) -> str:
        """获取阶段的中文名称"""

        names = {
            "io": "输入/输出",
            "primary": "一级处理",
            "secondary": "二级处理",
            "tertiary": "深度处理",
            "sludge": "污泥处理",
            "collection": "集配水模组",
            "elevation": "高程模组",
            "mine_water": "矿井水处理",
        }

        return names.get(stage, stage)

    def get_pipeline_order(self, mod_ids: List[str]) -> List[str]:
        """按处理阶段排序模组 ID 列表"""

        if not self._mods:

            self.discover_all(force_rescan=True)

        return sorted(
            mod_ids,
            key=lambda mid: self.get_stage_order(
                self._mods.get(mid, ModInfo(id=mid)).process_stage
            ),
        )

    def reload(self) -> None:
        """重新扫描并加载所有模组(用于热更新)"""

        self._mods.clear()

        self._node_registry.clear()

        self._formulas.clear()

        self._categories.clear()

        self._load_errors.clear()

        self._loaded = False

        self.discover_all(force_rescan=True)

        self.load_all()

    # ── 错误报告 ──

    def get_load_errors(self) -> list:
        """获取所有加载错误 [{mod_id, severity, errors}]"""

        return list(self._load_errors)

    def get_load_summary(self) -> str:
        """人类可读的加载摘要"""

        total = len(self._mods)

        loaded = sum(1 for m in self._mods.values() if m.loaded)

        errors = len(self._load_errors)

        return f"{loaded}/{total} mods loaded, {errors} with errors"


# ═════════════════════════════════════════════════════════════════════

# mod.json 验证 (v5.4: 委托给 mod_validation 模块)

# ═════════════════════════════════════════════════════════════════════

# 向后兼容重导出
from .mod_validation import validate_mod_json as _validate_mod_json  # noqa: F401
from .mod_validation import validate_all_mods  # noqa: F401

# ═════════════════════════════════════════════════════════════════════

# 全局实例

# ═════════════════════════════════════════════════════════════════════


_MOD_REQUIRED_FIELDS = ["id", "name", "node_type", "node_class"]

_MOD_VALID_STAGES = {
    "io",
    "primary",
    "secondary",
    "tertiary",
    "sludge",
    "mine_water",
    "collection",
    "elevation",
}

_MOD_VALID_PORT_TYPES = {"WATER", "QUALITY", "MIXED", "SLUDGE"}


def _validate_mod_json(path: Path) -> list:
    """验证 mod.json 文件.返回错误列表;空列表 = 通过."""

    errors = []

    try:

        with open(path, "r", encoding="utf-8") as f:

            data = json.load(f)

    except json.JSONDecodeError as e:

        return [f"JSON 语法错误: {e}"]

    except Exception as e:

        return [f"无法读取文件: {e}"]

    if not isinstance(data, dict):

        return ["mod.json 必须是 JSON 对象"]

    # 必填字段

    for field in _MOD_REQUIRED_FIELDS:

        if field not in data:

            errors.append(f"缺少必填字段: '{field}'")

    # ID 格式

    mod_id = data.get("id", "")

    if mod_id and not mod_id.islower():

        errors.append(f"id '{mod_id}' 应为全小写")

    # process_stage 合法性

    stage = data.get("process_stage", "")

    if stage and stage not in _MOD_VALID_STAGES:

        errors.append(f"process_stage '{stage}' 不合法,有效值: {_MOD_VALID_STAGES}")

    # 端口类型

    for port_type in ("inputs", "outputs"):

        for i, port in enumerate(data.get(port_type, [])):

            if not isinstance(port, dict):

                errors.append(f"{port_type}[{i}] 必须是对象")

                continue

            ptype = port.get("type", "")

            if ptype and ptype not in _MOD_VALID_PORT_TYPES:

                errors.append(f"{port_type}[{i}].type '{ptype}' 不合法")

            if "name" not in port:

                errors.append(f"{port_type}[{i}] 缺少 'name'")

    return errors


# 模块级缓存: JSON Schema (懒加载)
_schema_cache: dict | None = None


def _validate_with_schema(mod_json_path: Path) -> list:
    """使用 JSON Schema 验证 mod.json 文件.

    返回错误列表;空列表 = 通过.若 jsonschema 未安装则跳过并返回空列表.
    """
    global _schema_cache
    try:
        import jsonschema
    except ImportError:
        return []  # jsonschema 未安装,静默跳过

    errors = []

    # 加载 schema (仅首次)
    if _schema_cache is None:
        try:
            schema_path = mod_json_path.parent.parent / "mod_schema.json"
            with open(schema_path, "r", encoding="utf-8") as f:
                _schema_cache = json.load(f)
        except Exception:
            return []  # schema 文件不可用,静默跳过

    # 加载 data
    try:
        with open(mod_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []  # JSON 解析错误已在 _validate_mod_json 中报告

    # 验证
    try:
        validator = jsonschema.Draft202012Validator(_schema_cache)
        for err in validator.iter_errors(data):
            path_str = (
                " → ".join(str(p) for p in err.absolute_path)
                if err.absolute_path
                else "root"
            )
            errors.append(f"Schema: {err.message} (at {path_str})")
    except Exception as e:
        errors.append(f"Schema validation error: {e}")

    return errors


def validate_all_mods() -> dict:
    """验证所有已安装模组的 mod.json.返回 {mod_id: errors}."""

    from _paths import get_mods_dir

    mods_root = Path(get_mods_dir())

    results = {}

    for scan_dir_name in ("core", "community"):

        scan_dir = mods_root / scan_dir_name

        if not scan_dir.exists():

            continue

        for item in scan_dir.iterdir():

            if not item.is_dir():

                continue

            mod_json = item / "mod.json"

            if mod_json.exists():

                errors = _validate_mod_json(mod_json)

                if errors:

                    results[item.name] = errors

    return results


# ═════════════════════════════════════════════════════════════════════

# 全局实例

# ═════════════════════════════════════════════════════════════════════


def get_mod_manager() -> ModManager:
    """获取全局 ModManager 实例"""

    return ModManager()
