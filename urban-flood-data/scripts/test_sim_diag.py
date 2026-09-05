import sys
from pathlib import Path
import json, time, re, random
from pyswmm import Simulation
from swmm.toolkit import solver
from swmm.toolkit.shared_enum import NodeResult, ObjectType
from scipy.stats.qmc import LatinHypercube

sampler = LatinHypercube(d=3, seed=0)
unit_cube = sampler.random(n=1)
row = unit_cube[0]
intensity = 0.05 + row[0] * (2.50 - 0.05)
spread = 0.10 + row[1] * (0.50 - 0.10)
worker_seed = int(row[2] * (2**31 - 1))
print(f'intensity: {intensity:.4f}, spread: {spread:.4f}, worker_seed: {worker_seed}')

base_inp = Path('urban-flood-data/data/drainage/mumbai_synthetic.inp')
content = base_inp.read_text(encoding='utf-8')
junctions = re.findall(r'^(\d+)\s+[\d\.]+\s+0\s+0', content, re.MULTILINE)
print(f'Parsed {len(junctions)} junctions')

rng = random.Random(worker_seed)
n_inject = max(1, int(len(junctions) * spread))
inflow_nodes = set(rng.sample(junctions, min(n_inject, len(junctions))))
print(f'Injecting {len(inflow_nodes)} nodes with {intensity:.4f} CMS each')

lines = ['\n[INFLOWS]', ';;Node Constituent Time Series Type Mfactor Sfactor Baseline Pattern']
for nid in inflow_nodes:
    lines.append(f'{nid} FLOW "" FLOW 1.0 1.0 {intensity:.6f}')
inflows_block = '\n'.join(lines) + '\n'

content = re.sub(r'ROUTING_STEP\s+\S+', 'ROUTING_STEP         0:00:15', content)
content = re.sub(r'END_TIME\s+\S+', 'END_TIME             02:00:00', content)

test_inp = Path('urban-flood-data/data/drainage/_tmp_lhs/test_run0.inp')
test_inp.parent.mkdir(parents=True, exist_ok=True)
test_inp.write_text(content + inflows_block, encoding='utf-8')
print('Wrote test_run0.inp')

t0 = time.time()
print('Initializing Simulation...')
with Simulation(str(test_inp)) as sim:
    print(f'Simulation loaded in {time.time()-t0:.2f}s')
    sim.step_advance(60)
    t1 = time.time()
    for count, step in enumerate(sim):
        t_now = time.time()
        print(f'Step {count+1} took {t_now - t1:.3f}s (sim time: {sim.current_time})', flush=True)
        t1 = t_now
        if count >= 5:
            break
print('Test finished successfully!')
