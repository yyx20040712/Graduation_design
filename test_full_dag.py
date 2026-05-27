"""Full DAG test: combiner → jcws_smbg → tiaojiechi"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'ddesign_tool', 'src'))
from _paths import setup_import_paths
setup_import_paths()

from models.base import WaterFlow, WaterQuality
from models.pipe_network import PipeNetworkNode
from models.water_quality_node import WaterQualityNode
from models.combiner import CombinerNode
from mods.mod_manager import get_mod_manager

_mgr = get_mod_manager()
_mgr.load_all()
JcwsSmbgNode = _mgr.load_mod("jcws_smbg")
TiaojiechiNode = _mgr.load_mod("tiaojiechi")
from controller.graph_executor import GraphExecutor

executor = GraphExecutor()

# Create nodes
pipe = PipeNetworkNode()
wq = WaterQualityNode()
comb = CombinerNode()
jcws = JcwsSmbgNode()
tjc = TiaojiechiNode()

# Set user input
jcws.set_param("Z_ground", 150.0)
jcws.set_param("Z_water_inlet", 148.0)

# Add to executor
for n in [pipe, wq, comb, jcws, tjc]:
    executor.add_node(n)

# Connect: pipe→comb, wq→comb, comb→jcws, jcws→tjc
executor.connect(pipe.output_ports[0], comb.input_ports[0])
executor.connect(wq.output_ports[0], comb.input_ports[1])
executor.connect(comb.output_ports[0], jcws.input_ports[0])
executor.connect(jcws.output_ports[0], tjc.input_ports[0])

# Execute
results = executor.execute(force_all=True)

# Check results
for name, node in [("jcws", jcws), ("tjc", tjc)]:
    r = node.result
    e = r.elevation if r else None
    if e:
        print(f"{name}: ground={e.ground_elevation:.3f} water={e.water_elevation:.3f} "
              f"bottom={e.bottom_elevation:.3f} h_loss={e.head_loss:.3f}")
    else:
        print(f"{name}: NO ELEVATION DATA")

# Verify propagation
assert tjc.result.elevation is not None, "tjc has no elevation"
assert tjc.result.elevation.ground_elevation == 150.0, \
    f"Ground not propagated! Got {tjc.result.elevation.ground_elevation}"
assert abs(tjc.result.elevation.water_elevation - 147.7) < 0.5, \
    f"Water elevation wrong! Got {tjc.result.elevation.water_elevation}"
print("\nALL CHECKS PASSED")
