"""
07_lhs_batch_factory.py
=======================
HydroPulse Enterprise Batch Simulation Factory
Fully Dynamic CLI + IPC Memory Optimization + SSD I/O Artifact Cleanup
** Features Ultra-Fast C-API Toolkit Bypass for Sub-90s Simulation Times **
"""

import os
import re
import sys
import json
import random
import argparse
import traceback
import logging
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

# -- Third-party ---------------------------------------------------------------
import geopandas as gpd
from scipy.stats.qmc import LatinHypercube
from tqdm import tqdm

# PySWMM and the crucial C-API Toolkit imports
from pyswmm import Simulation, Nodes
from swmm.toolkit import solver
from swmm.toolkit.shared_enum import NodeResult, ObjectType

# -- Project utilities ---------------------------------------------------------
from utils import ProvenanceLogger

# =============================================================================
# DEFAULT CONFIGURATION
# =============================================================================

_SCRIPT_DIR      = Path(__file__).resolve().parent
_DATA_DIR        = _SCRIPT_DIR / ".." / "data"
BASE_INP         = _DATA_DIR / "drainage" / "mumbai_synthetic.inp"
NODES_GEOJSON    = _DATA_DIR / "drainage" / "mumbai_synthetic_nodes.geojson"
EVENTS_DIR       = _DATA_DIR / "events"
TEMP_INP_DIR     = _DATA_DIR / "drainage" / "_tmp_lhs"

DEFAULT_SAMPLES      = 1500
DEFAULT_WORKERS      = max(1, min(12, (os.cpu_count() or 2) - 1))
DEFAULT_SIM_END_TIME = "02:00:00"
DEFAULT_ROUTING_STEP = "0:00:15"
REPORTING_STEP_S     = 60
LHS_SEED             = 0

logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("lhs_factory")

# =============================================================================
# LATIN HYPERCUBE SAMPLING
# =============================================================================

def generate_lhs_profiles(n: int, seed: int, int_min: float, int_max: float, spread_min: float, spread_max: float) -> list:
    sampler = LatinHypercube(d=3, seed=seed)
    unit_cube = sampler.random(n=n)
    profiles = []
    for i, row in enumerate(unit_cube):
        intensity   = int_min    + row[0] * (int_max    - int_min)
        spread      = spread_min + row[1] * (spread_max - spread_min)
        worker_seed = int(row[2] * (2**31 - 1))
        profiles.append({
            "id": i,
            "intensity_cms": round(float(intensity), 6),
            "spatial_spread": round(float(spread), 6),
            "random_seed": worker_seed,
        })
    return profiles

# =============================================================================
# WORKER PROCESS
# =============================================================================

def _run_single_simulation(job: dict) -> dict:
    run_id       = job["id"]
    intensity    = job["intensity_cms"]
    spread       = job["spatial_spread"]
    rng_seed     = job["random_seed"]
    base_inp     = Path(job["base_inp"])
    events_dir   = Path(job["events_dir"])
    temp_inp_dir = Path(job["temp_inp_dir"])
    sim_end_time = job["sim_end_time"]
    routing_step = job["routing_step"]

    temp_inp = temp_inp_dir / f"mumbai_storm_LHS_{run_id:05d}.inp"
    temp_rpt = temp_inp_dir / f"mumbai_storm_LHS_{run_id:05d}.rpt"
    temp_out = temp_inp_dir / f"mumbai_storm_LHS_{run_id:05d}.out"
    out_json = events_dir   / f"mumbai_baked_sim_LHS_{run_id:05d}.json"

    status = {
        "id": run_id, "ok": False, "steps": 0, "flooded_steps": 0,
        "skipped": False, "error": None
    }

    # Idempotent skip if file already exists
    if out_json.exists():
        status["ok"] = True
        status["skipped"] = True
        return status

    # Load node coordinates from the local disk cache (eliminates IPC queue lockup)
    try:
        with open(job["coords_cache_path"], "r", encoding="utf-8") as f:
            node_coords = json.load(f)
    except Exception as exc:
        status["error"] = f"Coords cache load failed: {exc}"
        return status

    try:
        content = base_inp.read_text(encoding="utf-8")
        junctions = re.findall(r"^(\d+)\s+[\d\.]+\s+0\s+0", content, re.MULTILINE)
        if not junctions:
            # Fallback in case base INP junctions have non-zero max depths assigned
            junctions = re.findall(r"^(\d+)\s+[\d\.]+", content, re.MULTILINE)

        rng = random.Random(rng_seed)
        n_inject = max(1, int(len(junctions) * spread))
        inflow_nodes = set(rng.sample(junctions, min(n_inject, len(junctions))))

        inflows_block = "\n[INFLOWS]\n;;Node Constituent Time Series Type Mfactor Sfactor Baseline Pattern\n"
        for nid in inflow_nodes:
            inflows_block += f"{nid} FLOW \"\" FLOW 1.0 1.0 {intensity:.6f}\n"

        content = re.sub(r"ROUTING_STEP\s+\S+", f"ROUTING_STEP         {routing_step}", content)
        content = re.sub(r"END_TIME\s+\S+", f"END_TIME             {sim_end_time}", content)

        # [Fix F-007] Inject / update LENGTHENING_STEP 15 in [OPTIONS] to satisfy the
        # Courant condition for short synthetic conduits (e.g. pipe_28488).
        # Without this, DYNWAVE collapses the internal dt to 0.50 s, forcing
        # 120 solver iterations per reporting minute instead of 4.
        if re.search(r"LENGTHENING_STEP\s+\S+", content):
            content = re.sub(r"LENGTHENING_STEP\s+\S+", "LENGTHENING_STEP     15", content)
        elif re.search(r"^\[OPTIONS\]", content, re.MULTILINE):
            content = re.sub(
                r"(\[OPTIONS\][^\r\n]*\r?\n)",
                r"\1LENGTHENING_STEP     15\n",
                content,
            )

        temp_inp.write_text(content + inflows_block, encoding="utf-8")

        simulation_results = {}
        with Simulation(str(temp_inp)) as sim:
            sim.step_advance(REPORTING_STEP_S)
            
            # C-API Fast Hook: Get pointers to the C-engine once!
            num_nodes = sim._model.getProjectSize(ObjectType.NODE.value)
            node_ids = [sim._model.getObjectId(ObjectType.NODE.value, i) for i in range(num_nodes)]
            flood_enum = NodeResult.FLOOD.value
            depth_enum = NodeResult.DEPTH.value
            
            step_count = 0
            total_steps = int(
                (
                    sim.end_time - sim.start_time
                ).total_seconds() / REPORTING_STEP_S
            )

            for _step in sim:
                current_time = sim.current_time.isoformat()
                flooded = []

                # [Fix F-008] Bypass Python objects — read flood flag first from
                # the C memory array. Only fetch depth (and build the dict) for
                # nodes that are actually surface-overflowing (f > 0).  The old
                # `d > 0.5` branch matched >6 000 underground junctions every
                # step, creating ~720 000 dicts/run and 1.72 GB of heap bloat.
                for idx in range(num_nodes):
                    f = solver.node_get_result(idx, flood_enum)
                    if f > 0:
                        d = solver.node_get_result(idx, depth_enum)
                        nid = node_ids[idx]
                        coords = node_coords.get(nid, {"lat": 0.0, "lon": 0.0})
                        flooded.append({
                            "node_id": nid,
                            "lat": coords["lat"],
                            "lon": coords["lon"],
                            "overflow_cms": round(f, 4),
                            "depth_m": round(d, 4),
                        })

                if flooded:
                    simulation_results[current_time] = flooded
                    status["flooded_steps"] += 1

                step_count += 1

                # [Fix F-009] Real-time flushed step telemetry — replaces the
                # silent tqdm bar that only ticked after full 2-hour runs.
                sim_minutes = step_count * REPORTING_STEP_S // 60
                sim_hms = f"{sim_minutes // 60:02d}:{sim_minutes % 60:02d}:00"
                if step_count % 15 == 0 or step_count == 1 or step_count == total_steps:
                    print(
                        f"[Run {run_id:05d}] Step {step_count:3d}/{total_steps}"
                        f" (sim: {sim_hms}) | Flooded nodes: {len(flooded):,}",
                        flush=True,
                    )

            status["steps"] = step_count

    except Exception as exc:
        status["error"] = f"SWMM runtime error: {exc}\n{traceback.format_exc()}"
        return status

    finally:
        # Aggressive cleanup of intermediate engine artifacts
        for temp_file in (temp_inp, temp_rpt, temp_out):
            try:
                temp_file.unlink(missing_ok=True)
            except Exception:
                pass

    output_payload = {
        "meta": {
            "run_id": run_id,
            "intensity_cms": intensity,
            "spatial_spread": spread,
            "random_seed": rng_seed,
            "n_injected": len(inflow_nodes),
            "sim_end_time": sim_end_time,
            "routing_step": routing_step,
            "reporting_step_s": REPORTING_STEP_S,
        },
        "timesteps": simulation_results,
    }

    try:
        out_json.write_text(
            json.dumps(output_payload, separators=(",", ":")),
            encoding="utf-8",
        )
    except Exception as exc:
        status["error"] = f"JSON write failed: {exc}"
        return status

    status["ok"] = True
    return status

# =============================================================================
# CLI & ORCHESTRATION
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="HydroPulse Dynamic LHS Batch Simulation Factory")
    parser.add_argument("--samples", "-n", type=int, default=DEFAULT_SAMPLES,
                        help=f"Total LHS simulation runs (default: {DEFAULT_SAMPLES})")
    parser.add_argument("--workers", "-w", type=int, default=DEFAULT_WORKERS,
                        help=f"Concurrent worker processes (default: {DEFAULT_WORKERS})")
    parser.add_argument("--sim-end-time", "-t", type=str, default=DEFAULT_SIM_END_TIME,
                        help=f"Simulation duration (default: {DEFAULT_SIM_END_TIME})")
    parser.add_argument("--routing-step", type=str, default=DEFAULT_ROUTING_STEP,
                        help=f"DYNWAVE routing step (default: {DEFAULT_ROUTING_STEP})")
    parser.add_argument("--intensity-min", type=float, default=0.05,
                        help="Min inflow intensity in CMS (default: 0.05)")
    parser.add_argument("--intensity-max", type=float, default=2.50,
                        help="Max inflow intensity in CMS (default: 2.50)")
    parser.add_argument("--spread-min", type=float, default=0.10,
                        help="Min fraction of junctions (default: 0.10)")
    parser.add_argument("--spread-max", type=float, default=0.50,
                        help="Max fraction of junctions (default: 0.50)")

    args = parser.parse_args()

    print("=" * 70)
    print("  HydroPulse  |  LHS Batch Simulation Factory")
    print("=" * 70)
    print(f"  Runs Planned    : {args.samples}")
    print(f"  Workers Active  : {args.workers}")
    print(f"  Storm Duration  : {args.sim_end_time}")
    print(f"  Routing Step    : {args.routing_step}")
    print("=" * 70)

    if not BASE_INP.exists():
        raise FileNotFoundError(f"Base INP not found: {BASE_INP}")
    if not NODES_GEOJSON.exists():
        raise FileNotFoundError(f"Nodes GeoJSON not found: {NODES_GEOJSON}")

    EVENTS_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_INP_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Loading {NODES_GEOJSON.name} ...")
    nodes_gdf = gpd.read_file(NODES_GEOJSON)
    node_coords = {
        str(row["id"]): {"lat": row.geometry.y, "lon": row.geometry.x}
        for _, row in nodes_gdf.iterrows()
    }
    print(f"  OK  {len(node_coords):,} node coordinates cached.")

    # Write coordinate cache once to avoid multi-gigabyte IPC payload copies
    cache_path = TEMP_INP_DIR / "coords_cache.json"
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(node_coords, f)

    profiles = generate_lhs_profiles(
        n=args.samples,
        seed=LHS_SEED,
        int_min=args.intensity_min,
        int_max=args.intensity_max,
        spread_min=args.spread_min,
        spread_max=args.spread_max
    )

    jobs = [
        {
            **p,
            "base_inp": str(BASE_INP),
            "events_dir": str(EVENTS_DIR),
            "temp_inp_dir": str(TEMP_INP_DIR),
            "coords_cache_path": str(cache_path),
            "sim_end_time": args.sim_end_time,
            "routing_step": args.routing_step,
        }
        for p in profiles
    ]

    completed = failed = skipped = 0

    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        future_to_job = {executor.submit(_run_single_simulation, job): job for job in jobs}

        with tqdm(
            as_completed(future_to_job),
            total=args.samples,
            desc="Simulating",
            unit="run",
            dynamic_ncols=True,
            colour="cyan",
        ) as pbar:
            for future in pbar:
                try:
                    res = future.result()
                    if res.get("skipped"):
                        skipped += 1
                    elif res["ok"]:
                        completed += 1
                    else:
                        failed += 1
                        log.warning("Run %05d failed: %s", res["id"], res.get("error"))
                except Exception as exc:
                    failed += 1
                    log.error("Unhandled future exception: %s", exc)

                pbar.set_postfix_str(f"done={completed} skip={skipped} fail={failed}", refresh=False)

    # Clean up coordinate cache
    try:
        cache_path.unlink(missing_ok=True)
    except Exception:
        pass

    print()
    print("=" * 70)
    print("  BATCH EXECUTION COMPLETE")
    print(f"  Produced: {completed} | Skipped: {skipped} | Failed: {failed}")
    print("=" * 70)

    if completed > 0:
        try:
            logger = ProvenanceLogger()
            logger.log_dataset("lhs_batch_simulations", "Mumbai", "PySWMM+LHS", str(EVENTS_DIR))
        except Exception as exc:
            log.warning("Provenance logging failed: %s", exc)

if __name__ == "__main__":
    main()
    