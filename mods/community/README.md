# 🧪 社区模组开发指南

欢迎来到排水工程设计工具的模组系统！

> 📖 **完整规范**: 请参阅 [`../MOD_SPEC.md`](../MOD_SPEC.md) — 包含处理阶段分类、约束规范、向量化计算、测试要求等完整内容。

## 什么是模组？

模组（Mod）是一个独立的水处理工艺模块，包含：
- **计算逻辑**：基于工程标准的尺寸/参数计算
- **去除率定义**：各污染物的默认去除率
- **参数元数据**：变量物理意义、单位、取值范围
- **处理阶段**：一级处理/二级处理/深度处理/矿井水处理

就像 Minecraft 的模组社区一样，你可以创建自己的工艺模组，分享给其他工程师使用！

## 快速开始

### 1. 创建模组文件夹

在 `community/` 下创建你的模组文件夹，例如 `community/my_reactor/`：

```
community/my_reactor/
├── mod.json        # 模组元数据 (无 module_path)
├── __init__.py     # from .reactor import MyReactorNode
└── reactor.py      # 计算逻辑 (NodeBase 子类)
```

### 2. 编写 mod.json

> ⚠️ **关键**：`module_path` 字段**不要填写**（或留空）。社区模组通过文件系统加载，无需 `module_path`。<｜end▁of▁thinking｜>

```json
{
  "id": "my_reactor",
  "name": "我的反应器",
  "version": "1.0.0",
  "author": "你的名字",
  "description": "自定义反应器水力计算",
  "category": "市政污水处理",
  "process_stage": "secondary",
  "icon": "⚗️",
  "node_type": "my_reactor",
  "node_class": "MyReactorNode",
  "inputs": [{"type": "MIXED", "name": "进水"}],
  "outputs": [{"type": "MIXED", "name": "出水"}],
  "parameters": [
    {
      "key": "n",
      "symbol": "n",
      "name": "池数量",
      "unit": "座",
      "default": 2,
      "min": 1,
      "max": 8,
      "step": 1,
      "description": "并联池体数量"
    }
  ],
  "removal_rates": {
    "BOD5": 0.85,
    "COD": 0.80,
    "SS": 0.70,
    "NH3N": 0.50,
    "TN": 0.40,
    "TP": 0.30
  },
  "formula": "V = Q / (n × q)",
  "formula_detail": "V: 有效容积(m³), Q: 设计流量(m³/h), n: 池数, q: 容积负荷",
  "dependencies": [],
  "tags": ["生物处理", "自定义"],
  "references": ["GB50014-2021"]
}
```

### 3. 编写 __init__.py

```python
"""我的反应器 — 自定义水处理工艺模块"""

from models.base import NodeBase, WaterFlow, WaterQuality, NodeResult, ParamDef, PortType

class MyReactorNode(NodeBase):
    NODE_TYPE = "my_reactor"
    NODE_NAME = "我的反应器"
    NODE_CATEGORY = "社区模组"

    @classmethod
    def _default_params(cls):
        return {"n": 2, "q": 1.0}

    def _build_param_defs(self):
        return [
            ParamDef("池数量", "n", 2, 2, 1, 8, 1, "座"),
            ParamDef("容积负荷", "q", 1.0, 1.0, 0.1, 5.0, 0.1, "m³/(m³·h)"),
        ]

    @classmethod
    def _default_removal_rates(cls):
        return {"BOD5": 0.85, "COD": 0.80, "SS": 0.70}

    def calculate(self, flow, quality):
        n = self.get_param("n")
        q = self.get_param("q")
        Q = flow.Q_design * 3600  # m³/s → m³/h

        V = Q / (n * q)

        result = NodeResult(success=True, params=dict(self._params))
        result.add_dimension("有效容积", round(V, 2), "m³")
        return result
```

### 4. 重启应用

模组管理器会自动扫描 `core/` 和 `community/` 目录，发现并注册你的模组。

> 📦 **EXE 运行时动态加载**：将模组文件夹放入 `mods/community/`，重启 EXE 即可，**无需重新打包**。
> 
> 原理：ModManager 发现 `mod.json` 无 `module_path` → 走文件系统加载路径 → `importlib` 加载 `__init__.py` → `from models.base` 通过 PYZ 内置模块解析 → `from .reactor import` 相对导入同目录 `.py` → 注册到 UI 菜单。

## 高级功能

### 向量化计算

如果你的模组需要支持方案空间枚举（Solution Browser），实现 `_vectorized_compute()` 方法：

```python
@classmethod
def _vectorized_compute(cls, grid, flow, quality, fixed):
    import numpy as np
    N = len(grid["n"])
    n_arr = grid["n"]
    q_arr = grid.get("q", np.full(N, fixed.get("q", 1.0)))
    
    Q = flow.Q_design * 3600
    V = Q / (n_arr * q_arr)
    
    dt = np.dtype([("V", np.float64), ("ok_有效容积", np.bool_)])
    arr = np.zeros(N, dtype=dt)
    arr["V"] = V
    arr["ok_有效容积"] = (V > 0)
    return arr
```

### 自定义端口

```python
def _init_ports(self):
    self.input_ports.append(Port(
        port_id=f"{self.node_id}-in1",
        name="进水1", port_type=PortType.WATER,
        direction="input", node_id=self.node_id,
    ))
    # ... 更多端口
```

## 分享模组

将你的模组文件夹打包为 zip，其他人解压到 `community/` 目录即可使用！

## 参考

- 查看 `core/` 目录下的内置模组获取更多示例
- 基类 API 参考: `models/base.py`
- 工程标准: GB50014-2021《室外排水设计标准》
