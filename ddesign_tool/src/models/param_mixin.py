"""
param_mixin.py — 参数管理 Mixin (extracted from base.py)

从 NodeBase 中分离参数管理逻辑.避免循环依赖: 运行时导入 NodeState.
"""

from __future__ import annotations

from typing import Dict


class ParamMixin:
    """参数管理 Mixin — 管理节点的所有可调参数和去除率.

    由 NodeBase 继承.运行时通过 self.state 访问 NodeState.
    """

    _params: Dict[str, float]
    _param_defs: list
    _removal_rates: Dict[str, float]

    @classmethod
    def _default_params(cls) -> Dict[str, float]:
        return {}

    def _build_param_defs(self) -> list:
        return []

    @classmethod
    def _default_removal_rates(cls) -> Dict[str, float]:
        return {}

    def _init_params(self) -> None:
        self._params = dict(self._default_params())
        self._param_defs = self._build_param_defs()
        self._removal_rates = dict(self._default_removal_rates())

    def get_param(self, key: str) -> float:
        return self._params.get(key, 0.0)

    def set_param(self, key: str, value: float) -> None:
        if key in self._params:
            self._params[key] = value
            from .base import NodeState

            self.state = NodeState.DIRTY  # type: ignore[attr-defined]
            for pd in self._param_defs:
                if pd.key == key:
                    pd.set_value(value)
                    break

    def get_param_defs(self) -> list:
        for pd in self._param_defs:
            if pd.key in self._params:
                pd.value = self._params[pd.key]
        return self._param_defs

    def get_removal_rates(self) -> Dict[str, float]:
        return dict(self._removal_rates)

    def set_removal_rate(self, pollutant: str, rate: float) -> None:
        self._removal_rates[pollutant] = max(0.0, min(1.0, rate))
        from .base import NodeState

        self.state = NodeState.DIRTY  # type: ignore[attr-defined]

    def reset_params(self) -> None:
        self._params = dict(self._default_params())
        for pd in self._param_defs:
            pd.reset()
            if pd.key in self._params:
                self._params[pd.key] = pd.default
        self._removal_rates = dict(self._default_removal_rates())
        from .base import NodeState

        self.state = NodeState.DIRTY  # type: ignore[attr-defined]
