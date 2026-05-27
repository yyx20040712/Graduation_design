"""
pipe_network.py — 管网输入节点

像 Blender 选贴图一样,点击选择 Excel 文件读取管网计算结果.
输出: 总设计流量 (WATER 端口)
"""

import os
from typing import Dict, List, Optional, Tuple

from _logging import get_logger

_log = get_logger(__name__)

from .base import (
    NodeBase,
    NodeResult,
    NodeState,
    ParamDef,
    Port,
    PortType,
    WaterFlow,
    WaterQuality,
)


class PipeNetworkNode(NodeBase):
    """管网输入节点 — 从 Excel 读取管网计算结果

    读取 pipe_final.xlsx / pipe_final2.xlsx (污水) 或 yushui.xlsx (雨水)
    的「计算结果」sheet,提取总管段的设计流量.

    输入端口: 无 (或 1个QUALITY端口用于水质)
    输出端口: 1个 WATER 端口 (仅水量)
    """

    NODE_TYPE = "pipe_network"
    NODE_NAME = "管网输入"
    NODE_CATEGORY = "输入/输出"

    # 支持的文件列表
    BUILTIN_FILES = {
        "pipe_final": "污水管网方案一",
        "pipe_final2": "污水管网方案二",
        "yushui": "雨水管网方案",
    }

    def __init__(self, node_id: Optional[str] = None):
        super().__init__(node_id)
        self._excel_path: str = ""
        self._sheet_name: str = "计算结果"
        self._pipe_type: str = "污水"  # "污水" or "雨水"
        self._total_flow: float = 0.57  # m³/s (Excel读取值,仅作备用)
        self._pipe_stats: Dict = {}  # 管道统计 {管径: 总长度}

    @classmethod
    def _default_params(cls) -> Dict[str, float]:
        return {
            "Kz": 1.4,
            "Q_design": 0.57,
        }  # Q_design is max flow (already includes Kz)

    def _build_param_defs(self) -> List[ParamDef]:
        return [
            ParamDef(
                "总变化系数 Kz",
                "Kz",
                value=1.4,
                default=1.4,
                min_val=1.1,
                max_val=2.5,
                step=0.05,
                unit="",
                description="Kz = Q_max / Q_avg,用于反算日均流量",
            ),
            ParamDef(
                "设计流量 Q_max",
                "Q_design",
                value=0.57,
                default=0.57,
                min_val=0.01,
                max_val=10.0,
                step=0.01,
                unit="m³/s",
                description="最大设计流量(已含Kz)",
            ),
        ]

    def _init_ports(self) -> None:
        """管网节点: 可选水质输入 + 水量输出"""
        # 可选的水质输入端口
        self.input_ports = [
            Port(
                port_id=f"{self.node_id}-qin",
                name="水质(可选)",
                port_type=PortType.QUALITY,
                direction="input",
                node_id=self.node_id,
            )
        ]
        # 水量输出端口
        self.output_ports = [
            Port(
                port_id=f"{self.node_id}-wout",
                name="水量",
                port_type=PortType.WATER,
                direction="output",
                node_id=self.node_id,
            )
        ]

    @classmethod
    def _default_removal_rates(cls) -> Dict[str, float]:
        return {}

    # ── Excel 文件操作 ──

    def set_excel(self, filepath: str) -> bool:
        """设置 Excel 文件路径并加载数据

        支持两种方式:
          1. 完整路径: "D:/.../pipe_final.xlsx"
          2. 内置名称: "pipe_final" 或 "pipe_final.xlsx" → 自动查找 data/ 目录

        Returns: True 如果加载成功
        """
        # 去除 .xlsx 后缀后检查是否为内置文件
        name = filepath
        if name.endswith(".xlsx"):
            name = name[:-5]
        if name in self.BUILTIN_FILES:
            from _paths import get_data_dir

            data_dir = get_data_dir()
            filepath = os.path.join(data_dir, f"{name}.xlsx")

        if not os.path.exists(filepath):
            return False

        self._excel_path = filepath
        return self._load_excel_data()

    def _load_excel_data(self) -> bool:
        """从 Excel 的「计算结果」sheet 读取管网数据"""
        try:
            import pandas as pd

            df = pd.read_excel(self._excel_path, sheet_name=self._sheet_name)

            # 识别管道类型
            if "雨水" in str(self._excel_path):
                self._pipe_type = "雨水"
            else:
                self._pipe_type = "污水"

            # 读取最后一行的总设计流量
            # 「计算结果」sheet 的列: ... 设计流量(L/s), 管径(mm), ...
            if "设计流量(L/s)" in df.columns:
                total_flow_lps = df["设计流量(L/s)"].iloc[-1]
                self._total_flow = float(total_flow_lps) / 1000.0  # L/s → m³/s
            elif "设计流量" in df.columns:
                total_flow_lps = float(df["设计流量"].iloc[-1])
                self._total_flow = (
                    total_flow_lps / 1000.0 if total_flow_lps > 10 else total_flow_lps
                )

            # 管道统计: 按管径汇总长度 (流量由滑块直接控制,不再依赖Excel)
            if "管径(mm)" in df.columns and "长度(m)" in df.columns:
                for _, row in df.iterrows():
                    d = row["管径(mm)"]
                    l = row["长度(m)"]
                    if pd.notna(d) and pd.notna(l):
                        d = int(d)
                        self._pipe_stats[d] = self._pipe_stats.get(d, 0) + float(l)

            self.state = NodeState.DIRTY  # 管网数据变更, 标记需重算
            return True
        except Exception as e:
            _log.warning("operation failed: %s", e, exc_info=True)
            return False

    def get_available_files(self) -> List[Tuple[str, str, str]]:
        """返回可选文件列表 [(内部名, 显示名, 完整路径)]"""
        from _paths import get_data_dir

        data_dir = get_data_dir()
        files = []
        for key, desc in self.BUILTIN_FILES.items():
            path = os.path.join(data_dir, f"{key}.xlsx")
            exists = "✓" if os.path.exists(path) else "✗"
            files.append((key, f"{desc} [{exists}]", path))
        return files

    @property
    def excel_path(self) -> str:
        return self._excel_path

    @property
    def pipe_type(self) -> str:
        return self._pipe_type

    def calculate(self, flow: WaterFlow, quality: WaterQuality) -> NodeResult:
        """返回用户设定的流量数据"""
        Qd = self.get_param("Q_design") or self._total_flow
        Kz = self.get_param("Kz") or 1.4
        Q_avg_daily = Qd / Kz * 86400  # m³/d

        result = NodeResult(success=True)
        result.params = {
            "excel_path": self._excel_path,
            "pipe_type": self._pipe_type,
            "Q_design": Qd,
            "Kz": Kz,
            "Q_avg_daily": Q_avg_daily,
        }

        result.add_dimension("管网类型", 0, self._pipe_type)
        result.add_dimension(
            "Excel文件",
            0,
            os.path.basename(self._excel_path) if self._excel_path else "未选择",
        )
        result.add_dimension("总变化系数 Kz", round(Kz, 2), "")
        result.add_dimension("总管设计流量", round(Qd * 1000, 1), "L/s")
        result.add_dimension("平均日流量", round(Q_avg_daily, 1), "m³/d")

        # 管道统计
        for d, length in sorted(self._pipe_stats.items()):
            result.add_dimension(f"DN{d}管道长度", round(length, 1), "m")

        return result

    def execute(self, flow: WaterFlow, quality: WaterQuality):
        """重写 execute: 输出流量使用用户设定值而非上游输入"""
        from .base import NodeState
        from .base import WaterQuality as WQ

        self.state = NodeState.COMPUTING
        try:
            result = self.calculate(flow, quality)
            self._result = result
            if result.success:
                self.state = NodeState.CLEAN
                # 输出流量 = 用户设定的 Q_design 和 Kz
                Qd = self.get_param("Q_design") or self._total_flow
                Kz = self.get_param("Kz") or 1.4
                Q_avg_daily = Qd / Kz * 86400
                out_flow = WaterFlow(
                    Q_design=Qd,
                    Q_avg_daily=Q_avg_daily,
                    Kz=Kz,
                )
                result.inlet_quality = (
                    WQ(
                        BOD5=quality.BOD5,
                        COD=quality.COD,
                        SS=quality.SS,
                        NH3N=quality.NH3N,
                        TN=quality.TN,
                        TP=quality.TP,
                        pH=quality.pH,
                    )
                    if hasattr(quality, "BOD5")
                    else None
                )
                result.outlet_quality = WQ(
                    BOD5=quality.BOD5,
                    COD=quality.COD,
                    SS=quality.SS,
                    NH3N=quality.NH3N,
                    TN=quality.TN,
                    TP=quality.TP,
                    pH=quality.pH,
                )
                return result, out_flow, quality
            else:
                self.state = NodeState.ERROR
                return result, flow, quality
        except Exception as e:
            self.state = NodeState.ERROR
            from .base import NodeResult

            failed = NodeResult.failed(str(e))
            self._result = failed
            return failed, flow, quality

    def to_dict(self) -> Dict:
        d = super().to_dict()
        d["excel_path"] = self._excel_path
        d["pipe_type"] = self._pipe_type
        return d

    @classmethod
    def from_dict(cls, d: Dict) -> "PipeNetworkNode":
        node = cls(node_id=d["id"])
        node.x = d["position"]["x"]
        node.y = d["position"]["y"]
        for k, v in d.get("params", {}).items():
            # 向后兼容: 旧项目的 Q_design_override → Q_design
            if k == "Q_design_override" and v > 0:
                node._params["Q_design"] = v
            else:
                node._params[k] = v
        node._excel_path = d.get("excel_path", "")
        if node._excel_path:
            node._load_excel_data()
        return node
