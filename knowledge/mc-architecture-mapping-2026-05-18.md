# MC式模组架构三层映射 — v3.2 完整剖析

> 最后更新: 2026-05-18
> 状态: v3.2 MC式模组架构上线
> 测试: 177 passed, 3 skipped, 0 failed
> 模组数: 24 (核心22 + 社区2)

本文档从 Minecraft 模组兼容性架构的三层模型出发，逐层映射到「排水工程设计工具 v3.2」的实际代码实现，展示"仅管理自身JAR即可共存"的架构理念如何在一个 Python 工程工具中得到复现。

---

## 一、MC三层架构概览

Minecraft 模组加载器（Forge/Fabric）构建了三层正交的扩展架构，使得无数第三方模组可以无冲突共存：

```
MC 模组架构                         本工程实现
────────────────────────────        ────────────────────────────
Layer 1: 类加载与字节码增强           importlib 动态类加载 + 三层回退策略
  ├── ASM 字节码织入                 ├── NodeBase 继承 + calculate() 覆写
  ├── Mixin 注入 (@Inject)           ├── _vectorized_compute() 向量化批量
  └── 自定义 ClassLoader 命名空间隔离  └── sys.path 注入 + per-mod __init__.py

Layer 2: 资源标识与命名空间融合       per-mod mod.json + discretization.json
  ├── modid:path 资源定位符          ├── node_type + per-mod JSON 契约
  ├── 虚拟联合文件系统               ├── DISCRETE_CONFIGS 合并策略
  └── asset/data 目录规范            └── constraint_limits / estimator_type 内联

Layer 3: 注册表与事件驱动调度          NodeRegistry + on_register 生命周期钩子
  ├── Registry<Block/Item> 全局注册   ├── NodeRegistry.register() 统一入口
  ├── @SubscribeEvent / IEventBus     ├── on_register 装饰器 + _fire_register
  └── 生命周期事件链 (init→post)      └── scan → load → register → validate → UI
```

| MC 概念 | 本工程等价物 | 核心文件 |
|---------|-------------|---------|
| Forge Mod Loader | `ModManager` 单例 | `mods/mod_manager.py:132-141` |
| `@Mod` 注解 | `mod.json` JSON 元数据 | `mods/core/*/mod.json` |
| `IEventBus` / `@SubscribeEvent` | `on_register` / `_lifecycle_hooks` | `models/node_registry.py:183-198` |
| `RegistryEvent.Register<T>` | `NodeRegistry.register()` | `models/node_registry.py:73-81` |
| `modid:resource_path` | node_type + per-mod JSON | `mods/core/*/discretization.json` |
| ASM `ClassTransformer` | `importlib.import_module()` | `mods/mod_manager.py:264-305` |
| Mixin `@Inject(method, at)` | NodeBase `calculate()` 覆写 | `models/base.py:408-580` |
| `resource_pack/manifest.json` | `mod.json` + `discretization.json` 双清单 | per-mod 目录 |
| 类命名空间隔离 | sys.path 插入 + per-mod `__init__.py` | `mods/mod_manager.py:276-298` |

---

## 二、Layer 1 — 类加载与字节码增强

### 2.1 概念映射

Minecraft 中，模组通过 ASM/Mixin 在类加载阶段将自定义代码织入游戏核心逻辑。本工程以 Python 的 `importlib` 动态导入 + `NodeBase` 继承体系实现了等效的非侵入式扩展：

| MC 机制 | 本工程实现 | 关键差异 |
|---------|-----------|---------|
| ASM `ClassTransformer` 字节码织入 | `importlib.import_module(module_path)` 动态加载 .py → 内存类对象 | Python 无字节码织入；通过类继承覆写父类方法实现等价效果 |
| Mixin `@Inject(method, at=HEAD/TAIL)` | `NodeBase.calculate()` 在子类中被覆写 → DAG 执行器统一调用 | 覆写粒度是方法级（不是字节码级），但效果等价 |
| `FMLClassLoader` 命名空间隔离 | `sys.path.insert()` + per-mod `__init__.py` 自包含类定义 | Python 依赖 `sys.modules` 的 import hook 而非 ClassLoader |
| `@Mod` 注解元数据 | `mod.json` 声明 `node_type` / `node_class` / `module_path` | JSON 契约替代注解，更具声明性 |

### 2.2 三层回退加载链路

```
mod.json 文件
    │
    ├── 策略 1: module_path 存在？
    │   ┌──────────────────────────────────────────────┐
    │   │ importlib.import_module("models.tiaojiechi")  │
    │   │ → getattr(module, "TiaojiechiNode")           │
    │   │ → ✅ 返回类 (核心模组，在 PYZ 归档中)          │
    │   └──────────────────────────────────────────────┘
    │                                         ↓ 失败
    ├── 策略 2: mod_dir/__init__.py 存在？
    │   ┌──────────────────────────────────────────────┐
    │   │ sys.path.insert(0, parent_dir)               │
    │   │ importlib.import_module("erchunchi")          │
    │   │ → getattr(module, "ErchunchiNode")            │
    │   │ → ✅ 返回类 (社区模组，文件系统加载)          │
    │   └──────────────────────────────────────────────┘
    │                                         ↓ 失败
    └── 策略 3: 兼容映射降级
        ┌──────────────────────────────────────────────┐
        │ node_registry.resolve_class(node_type)       │
        │ → _COMPAT_MODULE_MAP[node_type]              │
        │ → importlib.import_module("models.cass")     │
        │ → ✅ 返回类 (ModManager 不可用时的安全网)     │
        └──────────────────────────────────────────────┘
```

**代码实现** — `mods/mod_manager.py:246-305`：
```python
def load_mod(self, mod_id: str) -> Optional[Type]:
    # 策略 1: module_path (核心模组，如 "models.tiaojiechi")
    if mod_info.module_path:
        module = importlib.import_module(mod_info.module_path)
        node_cls = getattr(module, mod_info.node_class, None)
        if node_cls:
            self._register_node(mod_info)
            return node_cls

    # 策略 2: mod_dir/__init__.py (社区模组，文件系统)
    if (mod_dir / "__init__.py").exists():
        sys.path.insert(0, parent_dir)     # 类路径注入 = ClassLoader 隔离
        module = importlib.import_module(mod_name)
        node_cls = getattr(module, mod_info.node_class, None)
        if node_cls:
            self._register_node(mod_info)
            return node_cls

    # 策略 3: node_registry 兼容映射降级 (安全网)
```

**NodeRegistry 兼容降级** — `models/node_registry.py:34-57 + 133-167`：
```python
# 向后兼容映射 — 22 个内置模块的 module_path + class_name
_COMPAT_MODULE_MAP = {
    "tiaojiechi": ("models.tiaojiechi", "TiaojiechiNode"),
    "cass":       ("models.cass",       "CASSNode"),
    "aao":        ("models.aao",        "AAONode"),
    # ... 22 entries total
}

def resolve_class(self, node_type: str) -> Optional[Type]:
    # 1. ModManager 优先 (动态发现)
    mgr.load_all()
    cls = mgr.get_node_class(node_type)
    if cls: return cls
    # 2. 兼容映射降级 (ModManager 不可用时的安全网)
    mod = importlib.import_module(mod_path)
    return getattr(mod, cls_name, None)
```

### 2.3 隔离机制 — 为何24个模组无冲突

Minecraft 中通过 `FMLClassLoader` 为不同模组创建隔离的类命名空间。本工程中：

| 隔离维度 | MC (Java) | 本工程 (Python) |
|---------|-----------|-----------------|
| **类定义隔离** | 独立 ClassLoader 实例 | 核心模组: 通过 `models.xxx` 的 Python 包命名空间; 社区模组: per-mod `__init__.py` 自包含 `class XxxNode(NodeBase)` |
| **参数数据隔离** | Transient NBT / Capability | `self._params: dict` 实例存储，`set_param()` / `get_param()` 读写 |
| **类型标识隔离** | `ResourceLocation(modid, path)` | `NODE_TYPE: str` 类属性，全局唯一；`_INFRA_TYPES` frozen set 标记基础设施节点 |
| **依赖污染防护** | `@Mod(dependencies="mod:xxx")` | `mod.json.dependencies: []` 声明依赖关系（当前未强制校验，为扩展留接口） |

```python
# 每个模组的 __init__.py = 自包含的类定义单元
# 例: mods/community/erchunchi/__init__.py
from models.base import NodeBase, NodeResult, ...  # ← base 在 PYZ 中始终可用

class ErchunchiNode(NodeBase):     # ← 类定义完全封装在此文件中
    NODE_TYPE = "erchunchi"        # ← 全局唯一命名空间标识
    NODE_NAME = "辐流式二沉池"
    def calculate(self, flow, quality) -> NodeResult: ...
    def _vectorized_compute(cls, ...) -> np.ndarray: ...
```

### 2.4 MC Mixin → NodeBase 继承对比

| Mixin 注解 | NodeBase 继承等价 |
|-----------|-----------------|
| `@Inject(method="onBlockPlaced", at=@At("HEAD"))` | 覆写 `calculate()` → 在 DAG 执行流中替代父类方法 |
| `@Inject(method="tick", at=@At("TAIL"))` | 覆写 `_vectorized_compute()` → 方案空间批量计算的注入点 |
| `@ModifyArg(method="getDrops")` | `set_removal_rate()` → 调整污染物去除率参数 |
| `@Redirect(method="getHardness")` | `NodeBase._default_removal_rates()` → 覆写默认去除率字典 |
| `@Overwrite` | `class XxxNode(NodeBase):` → 完整覆写父类所有行为 |

**基类 API** — `models/base.py:408-580`：
```python
class NodeBase:
    # 子类必须覆写 (等价于 MC @Overwrite)
    NODE_TYPE: str
    NODE_NAME: str
    NODE_CATEGORY: str

    # 核心计算注入点 (等价于 MC @Inject)
    def calculate(self, flow, quality) -> NodeResult:       # [必须覆写]
    def _vectorized_compute(cls, grid, flow, quality, fixed) -> np.ndarray:  # [可选]

    # 参数管理 (等价于 MC capability system)
    def get_param(key) -> float
    def set_param(key, value) -> None
    def get_removal_rates() -> dict
```

---

## 三、Layer 2 — 资源标识与命名空间融合

### 3.1 概念映射

Minecraft 通过 `modid:path` 形式的资源定位符，将所有模组的资产/数据整合为虚拟联合文件系统。本工程以 `node_type` + per-mod `discretization.json` 实现等效的声明式资源配置：

| MC 概念 | 本工程实现 | 文件位置 |
|---------|-----------|---------|
| `assets/modid/textures/...` | `mods/core/{node_type}/discretization.json` | per-mod 目录 |
| `data/modid/recipes/...` | `constraint_limits` + `constraint_keys` 内联配置 | `discretization.json` |
| resource pack 叠加加载 | `_get_merged_configs()` 合并 base + mod configs | `discretization.py:442-457` |
| `modid:block/path` 寻址 | `get_config("erchunchi")` → `{"free": ..., "fixed": ..., "constraint_keys": ..., "estimator_type": "circular"}` | `discretization.py` |
| `pack.mcmeta` 包清单 | `mod.json` (元数据) + `discretization.json` (计算配置) | 双清单模式 |

### 3.2 资源命名空间 — per-mod 数据流

```
mods/core/tiaojiechi/
├── mod.json              ← 元数据清单 (name, category, ports, parameters)
├── __init__.py           ← 导入桥 (from models.tiaojiechi import ...)
└── discretization.json   ← 计算配置 (free/fixed vars + constraints + limits + estimator)
                                │
                                ▼
                    ┌──────────────────────────┐
                    │ discretization.py         │
                    │ load_mod_discretizations()│  ← 扫描所有 mod 文件夹
                    │   → {node_type: config}   │
                    │   → 合并到 DISCRETE_CONFIGS│
                    │   → _get_merged_configs() │  缓存 + 自动刷新
                    └──────────┬───────────────┘
                               │
            ┌──────────────────┼──────────────────┐
            ▼                  ▼                  ▼
    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
    │solution_space│  │fast_estimator│  │dimension_    │
    │   .py        │  │   .py        │  │labels.py     │
    │              │  │              │  │              │
    │ 约束筛选     │  │ estimator    │  │ 参数标签     │
    │ 方案枚举     │  │ _type 选择   │  │ 自动生成     │
    │ robustness   │  │ cost 计算    │  │              │
    └──────────────┘  └──────────────┘  └──────────────┘
```

**合并加载机制** — `discretization.py:442-457`：
```python
def load_mod_discretizations() -> Dict[str, dict]:
    """从 per-mod discretization.json 加载离散化配置。
    确保先触发 ModManager 加载（懒加载），再查询其离散化配置。
    返回 {node_type: config} 字典，可直接与 DISCRETE_CONFIGS 合并。"""
    mgr = get_mod_manager()
    mgr.load_all()                              # 触发 scan → load → register
    return mgr.get_all_discretizations()        # 返回所有 mod 的离散化配置
```

### 3.3 per-mod discretization.json — 独立契约

每个模组的 `discretization.json` 是自包含的计算配置契约，无需修改任何 Python 源文件：

```json
{
  "free": {
    "n": [2, 4, 6, 8],
    "q_prime": [1.5, 1.8, 2.0, 2.3, 2.5, 2.8, 3.0]
  },
  "fixed": {
    "T_settle": 2.0, "h2_min": 2.0, "alpha": 50
  },
  "constraint_keys": ["D_min", "q_prime", "h2_min"],
  "constraint_names": [
    "池径 D >= 16",
    "实际表面负荷 q'",
    "有效水深 h2 >= 2.0"
  ],
  "constraint_limits": {
    "池径 D >= 16": ">= 16",
    "实际表面负荷 q'": "0.6~1.5",
    "有效水深 h2 >= 2.0": ">= 2.0"
  },
  "display_name": "辐流式初沉池",
  "estimator_type": "circular"
}
```

### 3.4 constraint_limits 内联 — v3.1 → v3.2 架构演进

这是 Layer 2 最关键的架构改进：

| 版本 | constraint_limits 位置 | 添加新模组需要改什么 |
|------|----------------------|---------------------|
| v3.1 | `solution_space.py` 中的 `CONSTRAINT_LIMITS` 全局 dict | 编辑 `solution_space.py` + `discretization.py` 两个源文件 |
| v3.2 | per-mod `discretization.json` 中的 `constraint_limits` 字段 | **零源文件修改** — 仅需 mod 文件夹内的 3 个文件 |

```python
# v3.1 (旧): 硬编码在 solution_space.py 中
CONSTRAINT_LIMITS = {
    "池径 D >= 16": ">= 16",
    "实际表面负荷 q'": "0.6~1.5",
    # 新增模组 → 必须编辑此文件
}

# v3.2 (新): 自动从 per-mod discretization.json 读取
def _extract_checks(result: np.ndarray, cfg: dict, ...):
    limits = cfg.get("constraint_limits", {})  # ← 从 JSON 读取
    for ckey, cname in zip(cfg["constraint_keys"], cfg["constraint_names"]):
        limit_desc = limits.get(cname, "")      # ← 自动匹配
```

### 3.5 estimator_type 内联 — 成本估算自动路由

同样在 v3.2 中，`estimator_type` 从 `fast_estimator.py` 的硬编码字典迁移到 per-mod JSON：

```json
// discretization.json — 声明本模组的几何类型
{ "estimator_type": "circular" }  // → fast_estimator._get_estimator() 自动选择圆形池估算器
```

| estimator_type | 匹配的估算器 | 适用模组 |
|---------------|-------------|---------|
| `"circular"` | 圆形池: π×R² 底板 + 2πR 池壁 | 初沉池, 二沉池, 浓缩池, 消化池 |
| `"rectangular"` | 矩形池: L×B 底板 + 2(L+B) 池壁 | 调节池, CASS, V型滤池, 高密度沉淀池 |
| `"cass"` | CASS 专用: 多格 + 曝气 + 滗水器 | 仅 CASS |
| `"ziwai"` | UV 渠道: 长条形混凝土渠道 | 仅紫外消毒 |
| (未指定) | 自动检测: 有 D 字段 → circular; 有 L+B → rectangular | 未知模组的智能降级 |

**代码参考** — `cost/fast_estimator.py`（通过 JSON 字段驱动路由）：
```python
def _get_estimator(node_type: str, cfg: dict) -> str:
    # 优先从 discretization.json 读取
    return cfg.get("estimator_type", _auto_detect(node_type, cfg))
```

---

## 四、Layer 3 — 注册表与事件驱动调度

### 4.1 概念映射

Minecraft 通过全局注册表和事件总线实现模组内容的非侵入式集成。本工程通过 `NodeRegistry` + `on_register` 生命周期钩子实现等效的声明式集成：

| MC 概念 | 本工程实现 | 代码位置 |
|---------|-----------|---------|
| `Registry<Block>` / `Registry<Item>` | `NodeRegistry._types: dict` 存储 node_type → 元数据 | `node_registry.py:67` |
| `RegistryEvent.Register<Block>` | `NodeRegistry.register()` | `node_registry.py:73-81` |
| `@SubscribeEvent` 注解 | `@on_register` 装饰器 | `node_registry.py:186-189` |
| `IEventBus.post(event)` | `_fire_register(mod_id, node_type, node_cls)` | `node_registry.py:192-198` |
| `FMLCommonSetupEvent` | `load_all()` → `register_from_mod_manager()` 批量同步 | `mod_manager.py:307-319` |
| `RegistryObject<T>` 延迟注册 | `_class_cache` 延迟解析 | `node_registry.py:68` |

### 4.2 注册-事件全链路

```
                          启动
                           │
                           ▼
                  ┌─────────────────┐
                  │ ModManager       │
                  │ .discover_all()  │ 扫描 mods/core/ + mods/community/
                  │  → _scan_directory()
                  │  → mod.json → ModInfo
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │ .load_all()      │
                  │   for mod_id:    │
                  │     load_mod()   │  三层回退策略
                  │       importlib  │  module_path → __init__.py → compat
                  │       ↓          │
                  │     node_cls ✅   │
                  └────────┬────────┘
                           │
                           ▼
                  ┌────────────────────────────┐
                  │ _register_node(mod_info)    │  ← 核心注册方法
                  │   ├── _node_registry[nt] =  │
                  │   │   (cls, display_name)   │
                  │   ├── _formulas[nt] = fml   │
                  │   ├── _categories[cat].add  │
                  │   └── 🔥 _fire_register()   │  ← 生命周期事件
                  └────────┬───────────────────┘
                           │
                           ▼
                  ┌────────────────────────────┐
                  │ _fire_register()            │
                  │   for hook in _hooks:       │
                  │     hook(id, type, cls)     │  ← 通知所有监听器
                  └────────┬───────────────────┘
                           │
            ┌──────────────┼──────────────┐
            ▼              ▼              ▼
    ┌──────────────┐ ┌──────────┐ ┌──────────────┐
    │ NodeRegistry │ │ UI 菜单  │ │ solution_    │
    │ .sync()      │ │ 自动生成 │ │ space 自动   │
    │              │ │          │ │ 发现         │
    └──────────────┘ └──────────┘ └──────────────┘
```

**代码 — `mods/mod_manager.py:327-356`**：
```python
def _register_node(self, mod_info: ModInfo) -> None:
    # 注册表写入
    self._node_registry[node_type] = (mod_info.node_cls, mod_info.name)

    # 🔥 生命周触发: 通知所有 on_register 监听器
    from models.node_registry import _fire_register
    _fire_register(mod_info.id, node_type, mod_info.node_cls)

    # 公式注册
    self._formulas[node_type] = formula_text
    # 分类菜单
    self._categories[category].append(node_type)
```

**代码 — `models/node_registry.py:183-198`**：
```python
# 全局生命周期钩子列表 (相当于 MC Event Bus 订阅列表)
_lifecycle_hooks: list = []

def on_register(callback):
    """装饰器: 注册模组生命周期回调。
    签名: callback(mod_id, node_type, node_cls)"""
    _lifecycle_hooks.append(callback)
    return callback

def _fire_register(mod_id: str, node_type: str, node_cls):
    """通知所有监听器: 新模组已注册 (相当于 IEventBus.post)"""
    for hook in _lifecycle_hooks:
        try:
            hook(mod_id, node_type, node_cls)
        except Exception:
            pass  # 单个钩子失败不影响其他监听器
```

### 4.3 NodeRegistry 统一注册表

**代码 — `models/node_registry.py:63-167`**：
```python
class NodeRegistry:
    """统一节点类型注册表 — 单一数据源，取代分散在各模块中的硬编码列表"""

    def __init__(self):
        self._types: Dict[str, dict] = {}        # node_type → 元数据
        self._class_cache: Dict[str, Type] = {}   # 延迟解析缓存
        self._populated = False                   # ModManager 是否已同步

    def register(self, node_type, module_path, class_name,
                 display_name, process_stage):
        """ModManager 调用此方法注册新模组 (等价于 MC Registry.register)"""

    def register_from_mod_manager(self, mgr):
        """启动时批量同步 ModManager 的所有已加载模组 (等价于 MC RegistryEvent 批量注册)"""

    # 查询 API — 所有消费者通过此模块查询，无需各自维护硬编码列表
    def is_io_node(self, node_type: str) -> bool: ...
    def has_solution_space(self, node_type: str) -> bool: ...
    def resolve_class(self, node_type: str) -> Optional[Type]: ...
```

### 4.4 自动发现链 — 添加新模组的零编辑流程

```
                ┌──────────────────────────────┐
                │ 用户仅在 community/ 中创建:    │
                │  mod.json                    │
                │  __init__.py                 │
                │  discretization.json         │
                └─────────────┬────────────────┘
                              │
                  零源文件修改, 以下全部自动:
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ UI 菜单       │    │ 方案浏览器    │    │ 工程概算      │
│              │    │              │    │              │
│ discover_all │    │ has_solution │    │ estimator    │
│ → categories │    │ _space()     │    │ _type 自动   │
│ → "添加节点" │    │ → 枚举方案   │    │ 路由成本计算  │
│ 菜单项       │    │              │    │              │
└──────────────┘    └──────────────┘    └──────────────┘
        │                     │                     │
        ▼                     ▼                     ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ 画布右键菜单  │    │ 维度标签      │    │ 流程排序      │
│              │    │              │    │              │
│ _show_canvas │    │ mod.json     │    │ process      │
│ _menu()      │    │ parameters   │    │ _stage →     │
│ → 分类分组   │    │ → 自动生成   │    │ FLOW_ORDER   │
│              │    │ label 映射   │    │              │
└──────────────┘    └──────────────┘    └──────────────┘
```

---

## 五、全栈架构图

```
                      ┌─────────────────────────────────────────────────┐
                      │              排水工程设计工具 v3.2               │
                      │           MC式三层模组架构 — 完整数据流          │
                      └─────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────────────┐
  │  LAYER 1 — 类加载与字节码增强 (mod_manager.py:246-305)                   │
  │                                                                         │
  │  mod.json ──→ discover_all() ──→ load_all() ──→ _register_node()       │
  │    │                                     │                              │
  │    │  module_path?                       │     三层回退:                 │
  │    ├── "models.cass" ──→ importlib ──→ ✅│     ① module_path (核心)     │
  │    ├── "" ──→ sys.path ──→ __init__.py │     ② __init__.py (社区)     │
  │    └── (none) ──→ _COMPAT_MAP ──→ ✅   │     ③ compat map (安全网)    │
  │                                         ▼                              │
  │                              node_cls: NodeBase 子类                    │
  │                              ├── calculate(flow, quality)              │
  │                              ├── _vectorized_compute(grid, ...)         │
  │                              └── execute_sludge(sludge)  [污泥线]      │
  └─────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
  ┌─────────────────────────────────────────────────────────────────────────┐
  │  LAYER 2 — 资源标识与命名空间融合 (discretization.py:442-457)            │
  │                                                                         │
  │  per-mod/                      DISCRETE_CONFIGS                         │
  │  ├── mod.json ──→ 元数据 ──→  合并策略:                                │
  │  └── discretization.json ──→  ① 基础配置 (discretization.py)           │
  │       ├── free: {n, q', ...}   ② load_mod_discretizations()             │
  │       ├── fixed: {...}         ③ _get_merged_configs() 缓存             │
  │       ├── constraint_keys      ④ 自动缓存失效刷新 (ModManager 重载时)   │
  │       ├── constraint_names                                              │
  │       ├── constraint_limits ──→ robustness 计算                         │
  │       └── estimator_type   ──→ cost estimation 路由                     │
  └─────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
  ┌─────────────────────────────────────────────────────────────────────────┐
  │  LAYER 3 — 注册表与事件驱动调度 (node_registry.py:63-219)               │
  │                                                                         │
  │  _register_node()                                                       │
  │       │                                                                 │
  │       ├── _node_registry[nt] = (cls, name)    ← Registry 写入          │
  │       ├── _formulas[nt] = formula              ← 公式注册               │
  │       ├── _categories[cat].append(nt)         ← 分类菜单               │
  │       │                                                                 │
  │       └── 🔥 _fire_register(id, nt, cls)       ← Event Bus 发布         │
  │               │                                                         │
  │               │  _lifecycle_hooks (监听器列表)                           │
  │               │                                                         │
  │               ├──→ NodeRegistry.sync()         注册表同步               │
  │               ├──→ UI 菜单自动生成              main_window.py          │
  │               ├──→ solution_space 自动发现      solution_space.py       │
  │               ├──→ dimension_labels 标签生成    dimension_labels.py     │
  │               ├──→ cost_estimator 自动路由      cost_estimator.py       │
  │               └──→ output_writer 节点分类       output_writer.py        │
  └─────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
                          ┌─────────────────────────┐
                          │      用户可见结果         │
                          │  ├── UI 菜单 (分类展示)   │
                          │  ├── 方案浏览器 (枚举)    │
                          │  ├── DAG 画布 (拖拽连线)  │
                          │  ├── Excel 报告 (5表格式) │
                          │  └── 工程概算 (BOQ清单)   │
                          └─────────────────────────┘
```

---

## 六、术语对照表

| # | MC 术语 | 本工程术语 | 核心文件 | 说明 |
|---|---------|-----------|---------|------|
| 1 | Forge Mod Loader (FML) | `ModManager` 单例 | `mods/mod_manager.py:132` | 模组生命周期管理 |
| 2 | `@Mod` 注解 | `mod.json` JSON 元数据 | `mods/*/mod.json` | 声明式元数据契约 |
| 3 | ASM `ClassTransformer` | `importlib.import_module()` | `mod_manager.py:264` | 动态类加载 |
| 4 | Mixin `@Inject` | `NodeBase.calculate()` 覆写 | `models/base.py:408` | 计算逻辑注入点 |
| 5 | FML ClassLoader 命名空间隔离 | `sys.path.insert()` + `__init__.py` | `mod_manager.py:276-298` | 类定义隔离 |
| 6 | `modid:resource_path` | `node_type` + per-mod JSON | `mods/core/*/discretization.json` | 资源命名空间 |
| 7 | `assets/modid/textures/` | `discretization.json` 中的 `constraint_limits` | per-mod JSON | 内联约束限值 |
| 8 | `data/modid/recipes/` | `discretization.json` 中的 `estimator_type` | per-mod JSON | 内联估算器类型 |
| 9 | resource pack 叠加 | `_get_merged_configs()` 合并 | `discretization.py:442-457` | 配置合并策略 |
| 10 | `pack.mcmeta` | `mod.json` + `discretization.json` | 双文件 | 双清单模式 |
| 11 | `Registry<Block>` | `NodeRegistry._types: dict` | `node_registry.py:67` | 全局注册表 |
| 12 | `RegistryEvent.Register<T>` | `NodeRegistry.register()` | `node_registry.py:73-81` | 注册方法 |
| 13 | `@SubscribeEvent` | `@on_register` 装饰器 | `node_registry.py:186-189` | 事件订阅 |
| 14 | `IEventBus.post(event)` | `_fire_register(mod_id, nt, cls)` | `node_registry.py:192-198` | 事件发布 |
| 15 | `FMLCommonSetupEvent` | `load_all()` → `register_from_mod_manager()` | `mod_manager.py:307-319` | 启动批量注册 |
| 16 | `RegistryObject<T>` 延迟注册 | `_class_cache: Dict` 延迟解析 | `node_registry.py:68` | 懒加载类解析 |
| 17 | `@Mod.EventBusSubscriber` | `_lifecycle_hooks: list` 监听列表 | `node_registry.py:183` | 监听器注册表 |
| 18 | `IRecipeSerializer` | `_vectorized_compute()` 向量化计算 | `models/*.py` | 方案批量计算 |
| 19 | Forge 配置系统 (TOML) | `config.ini` + per-mod `mod.json.parameters` | `config.ini` + JSON | 设计参数配置 |
| 20 | Capability 系统 (IItemHandler) | `WaterFlow` / `SludgeFlow` / `WaterQuality` dataclass | `models/base.py:115-290` | 类型化数据传递 |

---

## 七、架构演进 — v3.1 → v3.2

| 层次 | v3.1 (硬编码) | v3.2 (MC式) | 影响 |
|------|-------------|-----------|------|
| **Layer 1** 加载 | `graph_executor.py` 中 `compat_modules` 硬编码 15 个 `import` 语句 | `ModManager.load_mod()` 三层回退 + `importlib` 动态导入 | 添加新模组无需修改 `graph_executor.py` |
| **Layer 1** 隔离 | 所有模组类通过 `models.xxx` 包导入，无社区模组隔离 | `sys.path.insert()` + per-mod `__init__.py` 自包含 | 社区模组可在运行时从文件系统动态加载 |
| **Layer 2** 约束 | `CONSTRAINT_LIMITS` 硬编码在 `solution_space.py` | `constraint_limits` 内联在 per-mod `discretization.json` | 新增模组无需编辑 `solution_space.py` |
| **Layer 2** 估算 | `_ESTIMATORS` dict 硬编码在 `fast_estimator.py` | `estimator_type` 内联在 per-mod `discretization.json` | 新增模组无需编辑 `fast_estimator.py` |
| **Layer 3** 注册 | `graph_executor.py` + `main_window.py` + `solution_space.py` 各维护一份硬编码 node_type 列表 | `NodeRegistry` 单一注册表 → 所有消费者通过 `node_registry.py` 查询 | 5 处硬编码列表 → 1 个动态注册表 |
| **Layer 3** 事件 | 无生命周期钩子，`load_all()` 后手动调用各模块初始化 | `on_register` + `_fire_register` 事件总线 | 新增监听器通过装饰器注册，无需修改 `mod_manager.py` |
| **整体** | 添加新模组需编辑 8 个分散文件 | 添加新模组仅需 3~4 文件（全在一文件夹内） | 从"全仓修改"到"文件夹即插即用" |

### 验证案例: 二沉池社区模组 (erchunchi)

```
mods/community/erchunchi/           # ← 仅3文件, 零源文件修改
├── mod.json                        # 元数据: name, ports, params, process_stage
├── __init__.py                     # NodeBase 子类: ErchunchiNode
└── discretization.json            # 离散化: free/fixed/constraints/limits/estimator

结果: 72 可行方案, robust=0.335, cost=87-175w
所有自动发现功能正常: UI菜单 ✅ 方案浏览器 ✅ 工程概算 ✅ 维度标签 ✅
```

---

## 八、关键文件清单

| 文件 | 行数 | 职责 | MC 对应层 |
|------|------|------|----------|
| `mods/mod_manager.py` | 828 | ModManager 单例: 扫描/加载/注册/验证 | Layer 1 + 3 |
| `models/node_registry.py` | 219 | 统一注册表 + on_register 生命周期 | Layer 3 |
| `models/base.py` | 719 | NodeBase 基类: 计算注入点 + 端口体系 | Layer 1 |
| `models/discretization.py` | 457 | 离散化配置 + per-mod JSON 合并 | Layer 2 |
| `models/solution_space.py` | 500 | 方案枚举引擎 (自动发现) | Layer 2 + 3 |
| `cost/fast_estimator.py` | 155 | 快速估算器 (estimator_type 自动路由) | Layer 2 |
| `cost/cost_estimator.py` | 446 | 工程概算引擎 (is_io_node 自动跳过) | Layer 2 + 3 |
| `ui/main_window.py` | 1333 | 主窗口 (UI 菜单自动生成) | Layer 3 |
| `ui/canvas_view.py` | 427 | 节点画布 (分类菜单自动生成) | Layer 3 |
| `output_writer.py` | 308 | Excel 输出 (自动分类 + 维度映射) | Layer 3 |
| `mods/core/*/mod.json` | 22 files | 模组元数据契约 | Layer 1 + 2 |
| `mods/core/*/discretization.json` | 22 files | per-mod 计算配置 | Layer 2 |

---

> **维护提示**: 本文档与 `codebase-comprehensive-2026-05-17.md` 互补——后者按功能模块和修复历史组织，本文档按 MC 架构三层映射组织。
> **模组开发**: 参照 `mods/MOD_SPEC.md` (AI vibe-coding 指南) 和 `mods/community/README.md` (社区快速开始)。
> **每次修改后运行**: `pytest tests/ -q` 确认测试通过。
