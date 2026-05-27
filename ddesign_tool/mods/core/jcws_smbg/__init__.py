"""jcws_smbg.py — 进厂污水水面标高 (Inlet Water Surface Elevation)"""

from __future__ import annotations

import numpy as np
from typing import Dict, List, Tuple
from models.base import (
    NodeBase,
    NodeResult,
    WaterFlow,
    WaterQuality,
    ParamDef,
    Port,
    PortType,
    ElevationData,
)


class JcwsSmbgNode(NodeBase):
    """进厂污水水面标高 — 高程计算起点节点"""

    NODE_TYPE = "jcws_smbg"
    NODE_NAME = "进厂污水水面标高"
    NODE_CATEGORY = "高程模组"

    @classmethod
    def _default_params(cls) -> Dict[str, float]:
        return {"Z_water_inlet": 100.0, "Z_ground": 102.0, "DN_inlet": 800.0}

    def _build_param_defs(self) -> List[ParamDef]:
        return [
            ParamDef(
                "进厂水面标高",
                "Z_water_inlet",
                value=100.0,
                default=100.0,
                min_val=-10000.0,
                max_val=10000.0,
                step=0.001,
                unit="m",
            ),
            ParamDef(
                "进厂地面标高",
                "Z_ground",
                value=102.0,
                default=102.0,
                min_val=-10000.0,
                max_val=10000.0,
                step=0.001,
                unit="m",
            ),
            ParamDef(
                "进水管径",
                "DN_inlet",
                value=800.0,
                default=800.0,
                min_val=300.0,
                max_val=2000.0,
                step=50.0,
                unit="mm",
            ),
        ]

    def _init_ports(self) -> None:
        self.input_ports = [
            Port(
                port_id=f"{self.node_id}-in",
                name="进水",
                port_type=PortType.MIXED,
                direction="input",
                node_id=self.node_id,
            ),
        ]
        self.output_ports = [
            Port(
                port_id=f"{self.node_id}-out",
                name="出水",
                port_type=PortType.MIXED,
                direction="output",
                node_id=self.node_id,
            ),
        ]

    @classmethod
    def _default_removal_rates(cls) -> Dict[str, float]:
        return {"SS": 0.0, "BOD5": 0.0, "COD": 0.0, "NH3N": 0.0, "TN": 0.0, "TP": 0.0}

    def calculate(self, flow: WaterFlow, quality: WaterQuality) -> NodeResult:
        Z_water = self.get_param("Z_water_inlet")
        Z_ground = self.get_param("Z_ground")
        DN = self.get_param("DN_inlet") / 1000.0
        Z_bottom = Z_water - DN
        result = NodeResult(success=True)
        result.params = {
            "Z_water_inlet": Z_water,
            "Z_ground": Z_ground,
            "DN_inlet": DN * 1000,
        }
        result.add_dimension("进厂水面标高", round(Z_water, 3), "m")
        result.add_dimension("地面标高", round(Z_ground, 3), "m")
        result.add_dimension("进水管径", DN * 1000, "mm")
        result.add_dimension("管底标高", round(Z_bottom, 3), "m")
        return result

    @classmethod
    def _vectorized_compute(
        cls, grid: dict, flow: WaterFlow, quality: WaterQuality, fixed: dict
    ) -> "np.ndarray":
        import numpy as np

        Z_water = fixed.get("Z_water_inlet", 100.0)
        Z_ground = fixed.get("Z_ground", 102.0)
        DN = fixed.get("DN_inlet", 800.0) / 1000.0
        N = 1
        Z_bottom = Z_water - DN
        dtype = np.dtype(
            [
                ("Z_water", np.float64),
                ("Z_ground", np.float64),
                ("DN", np.float64),
                ("Z_bottom", np.float64),
                ("H", np.float64),
                ("concrete_m3", np.float64),
            ]
        )
        result = np.empty(N, dtype=dtype)
        result["Z_water"] = Z_water
        result["Z_ground"] = Z_ground
        result["DN"] = DN
        result["Z_bottom"] = Z_bottom
        result["H"] = 0.0
        result["concrete_m3"] = 0.0
        return result
