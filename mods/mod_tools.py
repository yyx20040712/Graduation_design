"""
mod_tools.py — 模组开发工具 CLI

用法:
    python -m ddesign_tool.mods.mod_tools scaffold <mod_id> <display_name>
    python -m ddesign_tool.mods.mod_tools validate
    python -m ddesign_tool.mods.mod_tools list
"""

import sys
from pathlib import Path

# Windows 终端编码修复
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 确保 ddesign_tool/ 在 sys.path 中
_APP_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_APP_ROOT))
sys.path.insert(0, str(_APP_ROOT / "src"))


MOD_TEMPLATE_JSON = """{
  "id": "{mod_id}",
  "name": "{display_name}",
  "version": "1.0.0",
  "author": "Your Name",
  "description": "{display_name} 处理单元模组",
  "category": "未分类",
  "process_stage": "primary",
  "node_type": "{mod_type}",
  "node_class": "{class_name}",
  "module_path": "",
  "inputs": [
    {{ "type": "MIXED", "name": "进水" }}
  ],
  "outputs": [
    {{ "type": "MIXED", "name": "出水" }}
  ],
  "parameters": [
    {{
      "key": "n",
      "symbol": "n",
      "name": "池数",
      "unit": "座",
      "default": 2,
      "min": 2,
      "max": 8,
      "step": 2
    }}
  ],
  "removal_rates": {{
    "BOD5": 0.0,
    "COD": 0.0,
    "SS": 0.0
  }},
  "formula": "填写核心计算公式",
  "tags": [],
  "references": []
}}"""

MOD_TEMPLATE_INIT = '''"""
{mod_id}.py — {display_name} 处理单元模组
"""

from models.base import NodeBase, WaterFlow, WaterQuality, NodeResult, ParamDef, PortType


class {class_name}(NodeBase):
    """{display_name}"""

    NODE_TYPE = "{mod_type}"
    NODE_NAME = "{display_name}"
    NODE_CATEGORY = "未分类"

    def _default_params(self) -> dict:
        return {{"n": 2}}

    def _build_param_defs(self) -> list:
        return [
            ParamDef(
                key="n", symbol="n", name="池数", unit="座",
                default=2, min_val=2, max_val=8, step=2,
            ),
        ]

    def _default_removal_rates(self) -> dict:
        return {{"BOD5": 0.0, "COD": 0.0, "SS": 0.0}}

    def _init_ports(self):
        self.input_ports = [
            self._create_port("in", PortType.MIXED, "进水"),
        ]
        self.output_ports = [
            self._create_port("out", PortType.MIXED, "出水"),
        ]

    def calculate(self, flow: WaterFlow, quality: WaterQuality) -> NodeResult:
        """核心计算逻辑"""
        n = self.get_param("n")

        result = NodeResult(success=True)
        result.add_dimension("池数", n, "座")

        # TODO: 添加实际计算逻辑
        # result.add_dimension("池长 L", L, "m")
        # result.add_check("约束名", passed, actual, limit, "单位")

        return result
'''


def cmd_scaffold(mod_id: str, display_name: str):
    """生成新模组骨架"""
    # 查找 community 目录
    app_root = Path(__file__).parent.parent
    mods_dir = app_root / "mods" / "community"
    mod_dir = mods_dir / mod_id

    if mod_dir.exists():
        print(f"错误: 模组目录已存在: {mod_dir}")
        return 1

    mod_dir.mkdir(parents=True, exist_ok=True)

    class_name = "".join(word.capitalize() for word in mod_id.split("_")) + "Node"

    # 写入 mod.json
    mod_json = MOD_TEMPLATE_JSON.format(
        mod_id=mod_id,
        display_name=display_name,
        mod_type=mod_id,
        class_name=class_name,
    )
    (mod_dir / "mod.json").write_text(mod_json, encoding="utf-8")
    print(f"  ✓ mod.json")

    # 写入 __init__.py
    init_py = MOD_TEMPLATE_INIT.format(
        mod_id=mod_id,
        display_name=display_name,
        mod_type=mod_id,
        class_name=class_name,
    )
    (mod_dir / "__init__.py").write_text(init_py, encoding="utf-8")
    print(f"  ✓ __init__.py")

    print(f"\n模组骨架已创建: {mod_dir}")
    print(f"下一步: 编辑 {mod_dir}/mod.json 和 {mod_dir}/__init__.py")
    print(f"        完成后重启应用即可在菜单中看到「{display_name}」")
    return 0


def cmd_validate():
    """验证所有已安装模组"""
    from mods.mod_manager import validate_all_mods
    results = validate_all_mods()
    if not results:
        print("✓ 所有模组验证通过")
        return 0
    else:
        print(f"✗ {len(results)} 个模组存在错误:\n")
        for mod_id, errors in results.items():
            print(f"  [{mod_id}]")
            for e in errors:
                print(f"    - {e}")
        return 1


def cmd_list():
    """列出所有模组"""
    from mods.mod_manager import get_mod_manager
    mgr = get_mod_manager()
    mgr.load_all()
    mods = mgr.list_mods()
    print(f"{'ID':<25} {'名称':<15} {'阶段':<12} {'版本':<10} {'状态'}")
    print("-" * 72)
    for m in sorted(mods, key=lambda x: x["id"]):
        loaded = "✓" if m["loaded"] else "✗"
        print(f"{m['id']:<25} {m['name']:<15} {m['process_stage']:<12} {m['version']:<10} {loaded}")
    print(f"\n{mgr.get_load_summary()}")
    return 0


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 0

    cmd = sys.argv[1]

    if cmd == "scaffold":
        if len(sys.argv) < 4:
            print("用法: python -m ddesign_tool.mods.mod_tools scaffold <mod_id> <display_name>")
            print("示例: python -m ddesign_tool.mods.mod_tools scaffold my_filter 我的过滤器")
            return 1
        return cmd_scaffold(sys.argv[2], sys.argv[3])

    elif cmd == "validate":
        return cmd_validate()

    elif cmd == "list":
        return cmd_list()

    else:
        print(f"未知命令: {cmd}")
        print(__doc__)
        return 1


if __name__ == "__main__":
    sys.exit(main())
