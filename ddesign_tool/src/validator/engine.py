"""
validator/engine.py — 模组验证引擎

嵌入式测试系统核心.不依赖外部测试框架,仅使用已打包在 EXE 中的模块.

使用:
    validator = ModValidator(mod_manager)
    report = validator.validate("tiaojiechi", mode="deep")
    print(report.passed, report.failures)
"""

from __future__ import annotations

import json
import os
import time
import traceback
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, List, Optional

from _logging import get_logger

_log = get_logger(__name__)


class Severity(IntEnum):
    """检查结果严重级别"""

    ERROR = 0  # 致命:模组无法加载或计算崩溃
    FAIL = 1  # 失败:约束不满足、结果不一致
    WARN = 2  # 警告:不规范但可用
    PASS = 3  # 通过
    INFO = 4  # 已知设计决策,仅作记录


SEVERITY_ICON = {0: "[ERROR]", 1: "[FAIL] ", 2: "[WARN] ", 3: "[PASS] ", 4: "[INFO] "}
SEVERITY_COLOR = {0: "red", 1: "red", 2: "yellow", 3: "green", 4: "cyan"}


@dataclass
class CheckResult:
    """单条检查结果"""

    check_id: str
    name: str
    severity: Severity
    message: str
    detail: str = ""
    duration_ms: float = 0.0

    @property
    def passed(self) -> bool:
        return self.severity >= Severity.WARN

    @property
    def is_fatal(self) -> bool:
        return self.severity <= Severity.FAIL


@dataclass
class ModReport:
    """单个模组的完整验证报告"""

    node_type: str
    mod_name: str = ""
    mod_category: str = ""
    total: int = 0
    passed: int = 0
    warnings: int = 0
    failures: int = 0
    errors: int = 0
    results: List[CheckResult] = field(default_factory=list)
    duration_ms: float = 0.0

    @property
    def healthy(self) -> bool:
        return self.errors == 0 and self.failures == 0


@dataclass
class ValidationReport:
    """全局验证报告"""

    reports: List[ModReport] = field(default_factory=list)
    total_mods: int = 0
    healthy_mods: int = 0
    total_checks: int = 0
    total_passed: int = 0
    total_warnings: int = 0
    total_failures: int = 0
    total_errors: int = 0
    duration_ms: float = 0.0


# ═══════════════════════════════════════════════════════════════
# 流量提供器
# ═══════════════════════════════════════════════════════════════


class DefaultFlowProvider:
    """为各模组提供标准测试流量"""

    def get(self, node_type: str):
        """返回 (WaterFlow, WaterQuality) 元组"""
        from models.base import WaterFlow, WaterQuality

        # 矿井水模组使用矿井水流量
        if node_type.startswith("kw_"):
            return (
                WaterFlow(Q_design=0.609, Q_avg_daily=43836.0, Kz=1.2),
                WaterQuality(BOD5=30, COD=70, SS=100, NH3N=1.5, TN=2.0, TP=0.3),
            )

        # 污泥模组 — 需要使用 SludgeFlow 或特殊处理
        if node_type.startswith("wuni_"):
            return (
                WaterFlow(Q_design=0.1, Q_avg_daily=5000.0, Kz=1.1),
                WaterQuality(),
            )

        # 市政污水
        return (
            WaterFlow(Q_design=0.523, Q_avg_daily=34760.0, Kz=1.3),
            WaterQuality(BOD5=200, COD=400, SS=250, NH3N=35, TN=45, TP=5),
        )


# ═══════════════════════════════════════════════════════════════
# 基线管理
# ═══════════════════════════════════════════════════════════════


class BaselineManager:
    """验证基线管理 — 支持已知问题抑制和设计决策标记

    文件结构 (每个模组目录下):
      .validator-notes.json   — 手动编写的设计决策标记 (allow list)
      .validator-baseline.json — 自动生成的基线 (suppressed list)

    .validator-notes.json 格式:
      {
        "allow": {
          "check_id": "设计决策说明",
        }
      }
    """

    def __init__(self):
        self._baselines: Dict[str, dict] = {}
        self._notes_cache: Dict[str, dict] = {}

    # ═══════════════ 初始化/加载 ═══════════════
    def _load_notes(self, node_type: str) -> dict:
        """从模组目录的 .validator-notes.json 加载设计决策标记"""
        if node_type in self._notes_cache:
            return self._notes_cache[node_type]
        try:
            from mods.mod_manager import get_mod_manager

            mgr = get_mod_manager()
            mod_info = mgr.get_mod_by_node_type(node_type)
            if mod_info and mod_info.mod_dir:
                path = os.path.join(mod_info.mod_dir, ".validator-notes.json")
                if os.path.exists(path):
                    with open(path, encoding="utf-8") as f:
                        notes = json.load(f)
                        self._notes_cache[node_type] = notes
                        return notes
        except Exception as e:
            _log.warning("operation failed: %s", e, exc_info=True)
        self._notes_cache[node_type] = {}
        return {}

    def is_allowed(self, node_type: str, check_id: str) -> Optional[str]:
        """检查是否被标记为设计决策.返回原因字符串或 None"""
        notes = self._load_notes(node_type)
        allows = notes.get("allow", {})
        return allows.get(check_id)

    def load(self, node_type: str) -> dict:
        """加载模组的基线文件"""
        if node_type in self._baselines:
            return self._baselines[node_type]
        try:
            from mods.mod_manager import get_mod_manager

            mgr = get_mod_manager()
            mod_info = mgr.get_mod_by_node_type(node_type)
            if mod_info and mod_info.mod_dir:
                path = os.path.join(mod_info.mod_dir, ".validator-baseline.json")
                if os.path.exists(path):
                    with open(path, encoding="utf-8") as f:
                        self._baselines[node_type] = json.load(f)
                        return self._baselines[node_type]
        except Exception as e:
            _log.warning("operation failed: %s", e, exc_info=True)
        self._baselines[node_type] = {}
        return {}

    # ═══════════════ 保存 ═══════════════
    def save(self, node_type: str, baseline: dict):
        """保存基线文件"""
        try:
            from mods.mod_manager import get_mod_manager

            mgr = get_mod_manager()
            mod_info = mgr.get_mod_by_node_type(node_type)
            if mod_info and mod_info.mod_dir:
                path = os.path.join(mod_info.mod_dir, ".validator-baseline.json")
                baseline["created"] = time.strftime("%Y-%m-%d %H:%M:%S")
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(baseline, f, ensure_ascii=False, indent=2)
        except Exception as e:
            _log.warning("operation failed: %s", e, exc_info=True)

    def is_suppressed(self, node_type: str, check_id: str) -> bool:
        """检查某条结果是否被基线抑制"""
        baseline = self.load(node_type)
        suppressed = baseline.get("suppressed", {})
        return check_id in suppressed

    def generate_baseline(self, report: ModReport) -> dict:
        """从验证报告生成基线 (抑制所有 FAIL/WARN)"""
        suppressed = {}
        design_decisions = []
        for r in report.results:
            if r.severity <= Severity.WARN:
                suppressed[r.check_id] = [r.message]
        return {
            "suppressed": suppressed,
            "design_decisions": design_decisions,
        }


# ═══════════════════════════════════════════════════════════════
# 验证引擎
# ═══════════════════════════════════════════════════════════════


class ModValidator:
    """模组验证引擎"""

    def __init__(self, mod_manager=None, flow_provider=None):
        self._mgr = mod_manager
        self._flow_provider = flow_provider or DefaultFlowProvider()
        self._baseline = BaselineManager()
        self._checks: List = []
        self._register_default_checks()

    @property
    def mgr(self):
        if self._mgr is None:
            from mods.mod_manager import get_mod_manager

            self._mgr = get_mod_manager()
            self._mgr.load_all()
        return self._mgr

    # ═══════════════ 状态检查 ═══════════════
    def _register_default_checks(self):
        """注册所有内置检查器"""
        from .checks.calculation import CalculationSmokeCheck
        from .checks.config import ConfigIntegrityCheck
        from .checks.constraint import ConstraintConsistencyCheck
        from .checks.ui_contract import UIContractCheck
        from .checks.vectorized import VectorizedParityCheck

        self._checks = [
            ConfigIntegrityCheck(),
            CalculationSmokeCheck(),
            ConstraintConsistencyCheck(),
            VectorizedParityCheck(),
            UIContractCheck(),
        ]

    # ── 公开 API ──

    # ═══════════════ 验证 ═══════════════
    def validate(
        self, node_type: str, mode: str = "quick", use_baseline: bool = False
    ) -> ModReport:
        """验证单个模组

        Args:
            node_type: 模组类型名
            mode: "quick" (基础, <3s) | "deep" (完整, <30s)
            use_baseline: 是否使用基线抑制已知问题
        """
        mod_info = self.mgr.get_mod_by_node_type(node_type)
        mod_name = mod_info.name if mod_info else node_type
        mod_category = getattr(mod_info, "category", "") if mod_info else ""
        report = ModReport(
            node_type=node_type,
            mod_name=mod_name,
            mod_category=mod_category,
        )

        # 1. 加载模组类
        cls = self.mgr.load_mod(node_type)
        if cls is None:
            report.errors += 1
            report.total += 1
            report.results.append(
                CheckResult(
                    "load", "模组加载", Severity.ERROR, f"无法加载模组 {node_type}", ""
                )
            )
            return report

        # 2. 加载配置
        try:
            from models.discretization import _refresh_merged_configs, get_config

            _refresh_merged_configs()
            cfg = get_config(node_type)
        except KeyError:
            report.errors += 1
            report.total += 1
            report.results.append(
                CheckResult(
                    "cfg_load",
                    "配置加载",
                    Severity.ERROR,
                    f"{node_type}: discretization.json 不存在或无效",
                    "",
                )
            )
            return report
        except Exception as e:
            report.errors += 1
            report.total += 1
            report.results.append(
                CheckResult(
                    "cfg_load", "配置加载", Severity.ERROR, f"加载配置异常: {e}", ""
                )
            )
            return report

        # 3. 获取测试流量
        try:
            flow, quality = self._flow_provider.get(node_type)
        except Exception as e:
            flow = None
            quality = None

        # 4. 执行所有检查
        t0 = time.perf_counter()
        for check in self._checks:
            # 快速模式跳过慢检查
            if mode == "quick" and not getattr(check, "fast", True):
                continue

            t_check = time.perf_counter()
            try:
                result = check.run(cls, cfg, flow, quality, mode)
            except Exception as e:
                result = CheckResult(
                    check.__class__.__name__,
                    getattr(check, "name", "未知检查"),
                    Severity.ERROR,
                    f"检查器崩溃: {e}",
                    traceback.format_exc()[-500:],
                )
            result.duration_ms = (time.perf_counter() - t_check) * 1000

            # ── 设计决策标记: 降级为 INFO ──
            if result.severity <= Severity.WARN:
                reason = self._baseline.is_allowed(node_type, result.check_id)
                if reason:
                    result.severity = Severity.INFO
                    result.message += f" [allowed: {reason}]"

            # ── 基线抑制: 将已知问题降级 ──
            if use_baseline and result.severity <= Severity.WARN:
                if self._baseline.is_suppressed(node_type, result.check_id):
                    result.severity = Severity.PASS
                    result.message += " [baseline-suppressed]"

            report.results.append(result)
            report.total += 1

            if result.severity == Severity.PASS:
                report.passed += 1
            elif result.severity == Severity.WARN:
                report.warnings += 1
            elif result.severity == Severity.FAIL:
                report.failures += 1
            elif result.severity == Severity.ERROR:
                report.errors += 1

        report.duration_ms = (time.perf_counter() - t0) * 1000
        return report

    def validate_all(
        self, mode: str = "quick", use_baseline: bool = False
    ) -> ValidationReport:
        """验证所有已安装模组"""
        # 从 discretization 配置获取所有模组列表
        from models.discretization import (
            _refresh_merged_configs,
            load_mod_discretizations,
        )

        _refresh_merged_configs()
        configs = load_mod_discretizations()

        reports = []
        t0 = time.perf_counter()

        for node_type in sorted(configs.keys()):
            try:
                report = self.validate(node_type, mode, use_baseline=use_baseline)
                reports.append(report)
            except Exception as e:
                mod_info = self.mgr.get_mod_by_node_type(node_type)
                mod_name = mod_info.name if mod_info else node_type
                reports.append(
                    ModReport(
                        node_type=node_type,
                        mod_name=mod_name,
                        errors=1,
                        results=[
                            CheckResult(
                                "crash",
                                "验证器",
                                Severity.ERROR,
                                str(e),
                                traceback.format_exc()[-300:],
                            )
                        ],
                    )
                )

        # 汇总
        total = ValidationReport(reports=reports, total_mods=len(reports))
        total.duration_ms = (time.perf_counter() - t0) * 1000
        for r in reports:
            total.healthy_mods += 1 if r.healthy else 0
            total.total_checks += r.total
            total.total_passed += r.passed
            total.total_warnings += r.warnings
            total.total_failures += r.failures
            total.total_errors += r.errors
        return total

    def generate_baselines(self) -> int:
        """为所有模组生成基线文件 (抑制当前所有 FAIL/WARN)"""
        count = 0
        total = self.validate_all(mode="deep")
        for report in total.reports:
            baseline = self._baseline.generate_baseline(report)
            if baseline.get("suppressed"):
                self._baseline.save(report.node_type, baseline)
                count += 1
        return count
