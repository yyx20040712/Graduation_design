"""
test_performance.py — 性能基准测试 (v5.3)

验证关键路径的执行时间在可接受范围内.
不依赖 pytest-benchmark, 使用 time.perf_counter().
"""

from __future__ import annotations

import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ddesign_tool", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ddesign_tool"))


class TestDAGPerformance:
    """DAG 执行引擎性能"""

    def test_full_dag_execution_under_2s(self):
        """完整 DAG (pipe→combiner→jcws_smbg→tiaojiechi) 执行 < 2s"""
        from models.base import WaterFlow, WaterQuality
        from models.combiner import CombinerNode
        from models.pipe_network import PipeNetworkNode
        from models.water_quality_node import WaterQualityNode
        from mods.mod_manager import get_mod_manager
        from controller.graph_executor import GraphExecutor

        mgr = get_mod_manager()
        mgr.load_all()
        JcwsNode = mgr.load_mod("jcws_smbg")
        TjcNode = mgr.load_mod("tiaojiechi")

        executor = GraphExecutor()
        pipe = PipeNetworkNode()
        wq = WaterQualityNode()
        comb = CombinerNode()
        jcws = JcwsNode()
        tjc = TjcNode()

        for n in [pipe, wq, comb, jcws, tjc]:
            executor.add_node(n)
        executor.connect(pipe.output_ports[0], comb.input_ports[0])
        executor.connect(wq.output_ports[0], comb.input_ports[1])
        executor.connect(comb.output_ports[0], jcws.input_ports[0])
        executor.connect(jcws.output_ports[0], tjc.input_ports[0])

        t0 = time.perf_counter()
        results = executor.execute(force_all=True)
        elapsed = time.perf_counter() - t0

        assert elapsed < 2.0, f"DAG 执行 {elapsed:.2f}s > 2.0s (上限)"
        assert len(results) >= 5, f"expected >=5 results, got {len(results)}"

    def test_dag_execution_under_5s_with_10_nodes(self):
        """10 节点 DAG < 5s"""
        from models.base import WaterFlow, WaterQuality
        from models.combiner import CombinerNode
        from models.pipe_network import PipeNetworkNode
        from models.water_quality_node import WaterQualityNode
        from mods.mod_manager import get_mod_manager
        from controller.graph_executor import GraphExecutor

        mgr = get_mod_manager()
        mgr.load_all()

        mod_ids = [
            "tiaojiechi",
            "cugeshan",
            "xigeshan",
            "chenshachi",
            "chuchenchi",
            "cass",
            "gaomidu",
            "vxinglvchi",
            "ziwai",
        ]
        nodes = []
        for mid in mod_ids:
            cls = mgr.load_mod(mid)
            if cls:
                nodes.append(cls())

        executor = GraphExecutor()
        pipe = PipeNetworkNode()
        wq = WaterQualityNode()
        comb = CombinerNode()
        executor.add_node(pipe)
        executor.add_node(wq)
        executor.add_node(comb)
        executor.connect(pipe.output_ports[0], comb.input_ports[0])
        executor.connect(wq.output_ports[0], comb.input_ports[1])

        prev = comb
        for node in nodes:
            executor.add_node(node)
            executor.connect(prev.output_ports[0], node.input_ports[0])
            prev = node

        t0 = time.perf_counter()
        results = executor.execute(force_all=True)
        elapsed = time.perf_counter() - t0

        assert elapsed < 5.0, f"10-node DAG {elapsed:.2f}s > 5.0s"
        success_count = sum(
            1 for r in results.values() if hasattr(r, "success") and r.success
        )
        assert success_count >= 7, f"only {success_count}/10 nodes succeeded"


class TestModLoadingPerformance:
    """模组加载性能"""

    def test_load_all_under_1s(self):
        """load_all() 34 模组 < 1s"""
        from mods.mod_manager import get_mod_manager

        mgr = get_mod_manager()

        t0 = time.perf_counter()
        mgr.load_all()
        elapsed = time.perf_counter() - t0

        assert elapsed < 1.0, f"load_all() {elapsed:.2f}s > 1.0s"
        assert len(mgr.mods) >= 34, f"expected >=34 mods, got {len(mgr.mods)}"

    def test_second_load_all_under_200ms(self):
        """第二次 load_all() (缓存命中) < 200ms"""
        from mods.mod_manager import get_mod_manager

        mgr = get_mod_manager()
        mgr.load_all()  # 预热

        t0 = time.perf_counter()
        mgr.load_all()
        elapsed = time.perf_counter() - t0

        assert elapsed < 0.2, f"缓存 load_all() {elapsed:.3f}s > 0.2s"


class TestSolutionSpacePerformance:
    """方案空间枚举性能"""

    def test_enumerate_under_1s(self):
        """单个模组方案枚举 < 1s"""
        from models.base import WaterFlow, WaterQuality
        from models.solution_space import get_engine

        engine = get_engine()
        flow = WaterFlow(Q_design=0.57, Q_avg_daily=34760.7, Kz=1.4)
        quality = WaterQuality()

        t0 = time.perf_counter()
        sols = engine.enumerate("tiaojiechi", flow, quality)
        elapsed = time.perf_counter() - t0

        assert elapsed < 1.0, f"方案枚举 {elapsed:.2f}s > 1.0s"
        assert len(sols) > 0, "无可行方案"

    def test_enumerate_10_mods_under_5s(self):
        """10 个模组方案枚举 < 5s"""
        from models.base import WaterFlow, WaterQuality
        from models.node_registry import has_solution_space
        from models.solution_space import get_engine
        from mods.mod_manager import get_mod_manager

        mgr = get_mod_manager()
        mgr.load_all()
        engine = get_engine()
        flow = WaterFlow(Q_design=0.57, Q_avg_daily=34760.7, Kz=1.4)
        quality = WaterQuality()

        total = 0
        t0 = time.perf_counter()
        for mod_id, info in list(mgr.mods.items())[:10]:
            if has_solution_space(info.node_type):
                sols = engine.enumerate(info.node_type, flow, quality)
                total += len(sols) if sols else 0
        elapsed = time.perf_counter() - t0

        assert elapsed < 5.0, f"10-mod enumeration {elapsed:.2f}s > 5.0s"
        assert total > 0, "零可行方案"


class TestStartupPerformance:
    """冷启动性能"""

    def test_mod_discovery_under_500ms(self):
        """discover_all() < 500ms"""
        from mods.mod_manager import get_mod_manager

        mgr = get_mod_manager()
        mgr._loaded = False
        mgr._mods.clear()

        t0 = time.perf_counter()
        mgr.discover_all(force_rescan=True)
        elapsed = time.perf_counter() - t0

        assert elapsed < 0.5, f"discover_all() {elapsed:.3f}s > 0.5s"
        assert len(mgr.mods) >= 34
