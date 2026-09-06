"""
07_lhs_batch_factory.py
=======================
HydroPulse Enterprise Batch Simulation Factory v2.2
PRD-01 / PRD-07 Standardized 5 km Buffered AOI (967.2 km²) + Rational-Method Hydrology
+ Triangular Hyetograph + Geographic Storm Clustering + Smart Param-Hash Idempotency
+ Connected Inflow Scoping + Surface Flood Filtering (< 5 MB JSONs)

Fixes applied in this version:
  F-011  Compact JSON format: {node_id: [overflow, depth]}
  F-012  Rational Method inflow scaling (Q = C·i·A) — replaces raw CMS injection
  F-013  Triangular hyetograph — replaces flat constant baseline
  F-014  Precision reduction to 3 decimals (millimeter precision)
  F-015  Smart Parameter-hash idempotency with standard mumbai_baked_sim_LHS_{id:05d}.json
  F-016  Scoped junction regex — isolates [JUNCTIONS] section
  F-017  Assertion-guarded config substitutions (re.subn + assert)
  F-018  Geographic storm clustering — replaces uniform random spread
  F-019  PRD-01 / PRD-07 5 km buffered AOI (967.2 km²) + 500 m² inlet catchment sizing
  F-020  Active surface flood filter (f > 0.001 CMS) + connected-only inflow scoping (60 MB → 2-5 MB)
  F-021  Telemetry desynchronization fix: clean single-run logging vs multi-worker tqdm bar
  F-022  PRD-07 DEM-derived per-node catchment area scaling (mumbai_flow_acc.tif)
  F-023  3-minute reporting resolution (180s, 40 timesteps) for fast ST-GNN training (~2.2 MB/file)
"""

import os
import re
import sys
import json
import math
import random
import hashlib
import argparse
import traceback
import logging
import statistics
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

# -- Third-party ---------------------------------------------------------------
from scipy.stats.qmc import LatinHypercube
from shapely.geometry import shape, Point
from shapely.prepared import prep
from tqdm import tqdm

# PySWMM and C-API Toolkit imports
from pyswmm import Simulation
from swmm.toolkit import solver
from swmm.toolkit.shared_enum import NodeResult, ObjectType

# -- Project utilities ---------------------------------------------------------
from utils import ProvenanceLogger

# =============================================================================
# DEFAULT CONFIGURATION & PHYSICAL CONSTANTS (PRD-01, PRD-07, PRD-08)
# =============================================================================

_SCRIPT_DIR      = Path(__file__).resolve().parent
_DATA_DIR        = _SCRIPT_DIR / ".." / "data"
BASE_INP         = _DATA_DIR / "drainage" / "mumbai_synthetic.inp"
NODES_GEOJSON    = _DATA_DIR / "drainage" / "mumbai_synthetic_nodes.geojson"
EVENTS_DIR       = _DATA_DIR / "events"
TEMP_INP_DIR     = _DATA_DIR / "drainage" / "_tmp_lhs"

# [PRD-01 & PRD-07] Standardized 5km Buffered Area of Interest (AOI)
BOUNDARY_GEOJSON = _DATA_DIR / "boundaries" / "mumbai_aoi_5km.geojson"
GRID_AREA_M2     = 967_200_000  # PRD-01 5km buffered AOI area (967.2 km²; 956.5 km² bounding box)

# [PRD-07 & PRD-08] Rational Method Physical Constants
# In Stage 05 (05_generate_synthetic_drainage.py, lines 75-83), conduits were
# hydraulically sized assuming an inlet contributing catchment area of 500 m²
# at 100 mm/hr design rainfall: Q = C * i * A
INLET_CATCHMENT_M2 = 500.0  # m² per inlet
RUNOFF_COEFF       = 0.85   # Weighted urban average from config/runoff_coefficients.yaml

DEFAULT_SAMPLES              = 1500
DEFAULT_WORKERS              = max(1, min(6, (os.cpu_count() or 2) - 1))
DEFAULT_SIM_END_TIME         = "02:00:00"
DEFAULT_ROUTING_STEP         = "0:00:15"
DEFAULT_REPORTING_STEP_S     = 180    # 3-minute intervals (40 timesteps for 2-hour event)
DEFAULT_FLOOD_THRESHOLD_CMS  = 0.001  # 1 L/s threshold for active surface overflow
LHS_SEED                     = 0

logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("lhs_factory")

# =============================================================================
# BOUNDARY & CANDIDATE JUNCTIONS EXTRACTION (PRD-01 / PRD-07)
# =============================================================================

def load_candidate_junctions(base_inp_path: Path, boundary_path: Path, nodes_path: Path) -> tuple[list[str], dict[str, tuple[float, float]], dict[str, float]]:
    """
    Extract junctions that are:
      1. Strictly within the PRD-01 / PRD-07 City AOI (mumbai_aoi_5km.geojson: 967.2 km²)
      2. Connected to at least one conduit in the synthetic drainage network (eliminates isolated nodes)
      3. Associated with PRD-07 DEM-derived catchment area from mumbai_synthetic_nodes.geojson
    Returns: (list of candidate junction IDs, dict of junction ID -> (x, y) coordinates, dict of junction ID -> catchment_area_m2)
    """
    if not boundary_path.exists():
        raise FileNotFoundError(f"Boundary AOI GeoJSON not found: {boundary_path}")
    if not base_inp_path.exists():
        raise FileNotFoundError(f"Base INP not found: {base_inp_path}")
    if not nodes_path.exists():
        raise FileNotFoundError(f"Nodes GeoJSON not found: {nodes_path}")

    # Load 5km AOI polygon
    b_data = json.loads(boundary_path.read_text(encoding="utf-8"))
    b_poly = prep(shape(b_data["features"][0]["geometry"]))

    content = base_inp_path.read_text(encoding="utf-8")

    # Find nodes connected to at least one conduit
    c_match = re.search(r"\[CONDUITS\](.*?)\n\[", content, re.DOTALL)
    if not c_match:
        raise ValueError("No [CONDUITS] section found in base INP")
    connected_nodes = set()
    for line in c_match.group(1).strip().split("\n"):
        line = line.strip()
        if line and not line.startswith(";;"):
            parts = line.split()
            if len(parts) >= 3:
                connected_nodes.add(parts[1])
                connected_nodes.add(parts[2])

    # Load node coordinates and PRD-07 catchment areas from GeoJSON
    nodes_data = json.loads(nodes_path.read_text(encoding="utf-8"))
    candidate_ids = []
    candidate_coords = {}
    candidate_catchments = {}

    for feat in nodes_data.get("features", []):
        props = feat.get("properties", {})
        nid = str(props.get("id"))
        if nid in connected_nodes:
            coords = feat["geometry"]["coordinates"]
            x, y = float(coords[0]), float(coords[1])
            if b_poly.contains(Point(x, y)):
                candidate_ids.append(nid)
                candidate_coords[nid] = (x, y)
                candidate_catchments[nid] = float(props.get("catchment_area", 500.0))

    return candidate_ids, candidate_coords, candidate_catchments

# =============================================================================
# LATIN HYPERCUBE SAMPLING
# =============================================================================

def generate_lhs_profiles(n: int, seed: int, int_min: float, int_max: float, spread_min: float, spread_max: float) -> list:
    """Generate n LHS profiles sampling rainfall intensity (mm/hr), spatial spread, and random seed."""
    sampler = LatinHypercube(d=3, seed=seed)
    unit_cube = sampler.random(n=n)
    profiles = []
    for i, row in enumerate(unit_cube):
        rainfall    = int_min    + row[0] * (int_max    - int_min)
        spread      = spread_min + row[1] * (spread_max - spread_min)
        worker_seed = int(row[2] * (2**31 - 1))
        profiles.append({
            "id": i,
            "rainfall_mm_hr": round(float(rainfall), 6),
            "spatial_spread": round(float(spread), 6),
            "random_seed": worker_seed,
        })
    return profiles

# =============================================================================
# WORKER PROCESS
# =============================================================================

def _run_single_simulation(job: dict) -> dict:
    run_id             = job["id"]
    rainfall           = job["rainfall_mm_hr"]
    spread             = job["spatial_spread"]
    rng_seed           = job["random_seed"]
    base_inp           = Path(job["base_inp"])
    events_dir         = Path(job["events_dir"])
    temp_inp_dir       = Path(job["temp_inp_dir"])
    sim_end_time       = job["sim_end_time"]
    routing_step       = job["routing_step"]
    inlet_catchment_m2   = job["inlet_catchment_m2"]
    candidates           = job["candidate_junctions"]
    candidate_coords     = job["candidate_coords"]
    candidate_catchments = job.get("candidate_catchments", {})
    reporting_step_s     = job.get("reporting_step_s", DEFAULT_REPORTING_STEP_S)
    flood_threshold      = job.get("flood_threshold", DEFAULT_FLOOD_THRESHOLD_CMS)
    verbose_telemetry    = job.get("verbose_telemetry", False)

    # [Fix F-015 + F-022 + F-023] Smart Parameter-Hash Idempotency:
    # Preserves standard filename format: mumbai_baked_sim_LHS_{run_id:05d}.json
    # while hashing all physical parameters + catchment model + temporal resolution into meta.
    param_str = f"{rainfall}-{spread}-{rng_seed}-{sim_end_time}-{routing_step}-{reporting_step_s}-{flood_threshold}-{inlet_catchment_m2}-v3"
    param_hash = hashlib.md5(param_str.encode()).hexdigest()[:8]

    temp_inp = temp_inp_dir / f"mumbai_storm_LHS_{run_id:05d}.inp"
    temp_rpt = temp_inp_dir / f"mumbai_storm_LHS_{run_id:05d}.rpt"
    temp_out = temp_inp_dir / f"mumbai_storm_LHS_{run_id:05d}.out"
    out_json = events_dir   / f"mumbai_baked_sim_LHS_{run_id:05d}.json"

    status = {
        "id": run_id, "ok": False, "steps": 0, "flooded_steps": 0,
        "skipped": False, "error": None
    }

    # Idempotent skip if this exact parameter configuration already produced this file
    overwrite = job.get("overwrite", False)
    if out_json.exists() and not overwrite:
        try:
            with open(out_json, "r", encoding="utf-8") as f:
                existing_meta = json.load(f).get("meta", {})
                if existing_meta.get("param_hash") == param_hash:
                    status["ok"] = True
                    status["skipped"] = True
                    return status
        except Exception:
            pass  # Corrupted or old format — proceed to regenerate

    try:
        content = base_inp.read_text(encoding="utf-8")

        # [Fix F-018 + F-020] Geographic storm clustering among connected AOI junctions
        rng = random.Random(rng_seed)
        n_inject = max(1, int(len(candidates) * spread))

        if candidate_coords:
            # Pick a random storm centroid from candidate junctions within the AOI
            centroid_nid = rng.choice(candidates)
            cx, cy = candidate_coords[centroid_nid]

            # Sort junctions by Euclidean distance to centroid, take the closest n_inject
            def dist_to_centroid(nid):
                if nid in candidate_coords:
                    x, y = candidate_coords[nid]
                    return math.hypot(x - cx, y - cy)
                return float("inf")

            sorted_candidates = sorted(candidates, key=dist_to_centroid)
            inflow_nodes = set(sorted_candidates[:n_inject])
        else:
            centroid_nid = "N/A"
            inflow_nodes = set(rng.sample(candidates, min(n_inject, len(candidates))))

        # [Fix F-012 + F-019 + F-022] Rational Method with PRD-07 DEM-derived catchment areas:
        # Q_j = C * i * A_j
        # i = rainfall intensity in m/s
        # A_j = contributing catchment area per node j in m² (from mumbai_synthetic_nodes.geojson)
        i_m_per_s = rainfall / 1000.0 / 3600.0

        # [Fix F-013] Triangular hyetograph: peak at 33% (front-loaded monsoon pattern)
        # Rising limb: 0.1 → 1.0; recession limb: 1.0 → 0.05
        time_parts = sim_end_time.split(":")
        storm_duration_min = int(time_parts[0]) * 60 + int(time_parts[1])
        if storm_duration_min < 1:
            storm_duration_min = 120

        peak_fraction = 0.33
        peak_time_min = max(1, int(storm_duration_min * peak_fraction))
        recession_denom = max(1, storm_duration_min - peak_time_min)

        ts_name = f"STORM_LHS_{run_id:05d}"
        ts_block = f"\n[TIMESERIES]\n;;Name Date Time Value\n"
        for t in range(0, storm_duration_min + 1, 1):
            if t <= peak_time_min:
                mult = 0.1 + 0.9 * (t / peak_time_min)
            else:
                mult = max(0.05, 1.0 - 0.95 * ((t - peak_time_min) / recession_denom))
            hours = t // 60
            mins = t % 60
            ts_block += f"{ts_name} {hours}:{mins:02d} {mult:.4f}\n"

        # Build INFLOWS block using per-node DEM catchment areas and timeseries reference
        inflows_block = "\n[INFLOWS]\n;;Node Constituent Time Series Type Mfactor Sfactor Baseline Pattern\n"
        node_catchments = []
        node_Qs = []
        for nid in inflow_nodes:
            area_j = candidate_catchments.get(nid, inlet_catchment_m2)
            Q_node = RUNOFF_COEFF * i_m_per_s * area_j
            node_catchments.append(area_j)
            node_Qs.append(Q_node)
            inflows_block += f"{nid} FLOW {ts_name} FLOW 1.0 {Q_node:.6f} 0.0\n"

        mean_catchment = statistics.mean(node_catchments) if node_catchments else inlet_catchment_m2
        mean_Q = statistics.mean(node_Qs) if node_Qs else 0.0

        # [Fix F-017] Assertion-guarded config substitutions
        content, n = re.subn(r"ROUTING_STEP\s+\S+", f"ROUTING_STEP         {routing_step}", content)
        assert n >= 1, f"ROUTING_STEP not found in base INP — template format changed?"

        content, n = re.subn(r"END_TIME\s+\S+", f"END_TIME             {sim_end_time}", content)
        assert n >= 1, f"END_TIME not found in base INP — template format changed?"

        # [Fix F-007] Inject / update LENGTHENING_STEP 15 in [OPTIONS] for Courant stability
        if re.search(r"LENGTHENING_STEP\s+\S+", content):
            content = re.sub(r"LENGTHENING_STEP\s+\S+", "LENGTHENING_STEP     15", content)
        elif re.search(r"^\[OPTIONS\]", content, re.MULTILINE):
            content = re.sub(
                r"(\[OPTIONS\][^\r\n]*\r?\n)",
                r"\1LENGTHENING_STEP     15\n",
                content,
            )

        # Write prepared INP + timeseries + inflows
        temp_inp.write_text(content + ts_block + inflows_block, encoding="utf-8")

        simulation_results = {}
        with Simulation(str(temp_inp)) as sim:
            sim.step_advance(reporting_step_s)

            # C-API Fast Hook: Get pointers to the C-engine once
            num_nodes = sim._model.getProjectSize(ObjectType.NODE.value)
            node_ids = [sim._model.getObjectId(ObjectType.NODE.value, i) for i in range(num_nodes)]
            flood_enum = NodeResult.FLOOD.value
            depth_enum = NodeResult.DEPTH.value

            step_count = 0
            total_steps = int(
                (sim.end_time - sim.start_time).total_seconds() / reporting_step_s
            )

            for _step in sim:
                current_time = sim.current_time.isoformat()

                # [Fix F-011 + F-020 + F-023] Compact JSON: {node_id: [overflow, depth]}
                # Scoped strictly to active surface flooding (f > flood_threshold).
                # Normal in-pipe water depth (d > 0) without surface overflow is
                # underground drainage flow, NOT street flooding.
                snap = {}
                for idx in range(num_nodes):
                    f = solver.node_get_result(idx, flood_enum)
                    if f > flood_threshold:
                        d = solver.node_get_result(idx, depth_enum)
                        nid = node_ids[idx]
                        snap[nid] = [round(f, 3), round(d, 3)]

                # Always preserve all timesteps for time-series continuity
                simulation_results[current_time] = snap
                if snap:
                    status["flooded_steps"] += 1

                flooded_count = len(snap)
                step_count += 1

                # [Fix F-021] Telemetry reporting (only when verbose_telemetry is active)
                if verbose_telemetry:
                    sim_minutes = step_count * reporting_step_s // 60
                    sim_hms = f"{sim_minutes // 60:02d}:{sim_minutes % 60:02d}:00"
                    if step_count % 5 == 0 or step_count == 1 or step_count == total_steps:
                        print(
                            f"  [Step {step_count:2d}/{total_steps}] (sim: {sim_hms}) | Flooded nodes: {flooded_count:,}",
                            flush=True,
                        )

            status["steps"] = step_count

    except Exception as exc:
        status["error"] = f"SWMM runtime error: {exc}\n{traceback.format_exc()}"
        return status

    finally:
        # [Fix F-010] Aggressive cleanup of intermediate engine artifacts
        for temp_file in (temp_inp, temp_rpt, temp_out):
            try:
                temp_file.unlink(missing_ok=True)
            except Exception:
                pass

    output_payload = {
        "meta": {
            "run_id": run_id,
            "boundary": "mumbai_aoi_5km.geojson (PRD-01 City AOI)",
            "aoi_area_km2": round(GRID_AREA_M2 / 1e6, 2),
            "rainfall_mm_hr": rainfall,
            "Q_per_node_cms": round(mean_Q, 6),
            "mean_Q_per_node_cms": round(mean_Q, 6),
            "inlet_catchment_m2": round(mean_catchment, 1),
            "mean_catchment_m2": round(mean_catchment, 1),
            "min_catchment_m2": round(min(node_catchments), 1) if node_catchments else inlet_catchment_m2,
            "max_catchment_m2": round(max(node_catchments), 1) if node_catchments else inlet_catchment_m2,
            "catchment_source": "DEM flow accumulation (mumbai_flow_acc.tif, PRD-07)",
            "spatial_spread": spread,
            "n_injected": len(inflow_nodes),
            "storm_centroid_nid": centroid_nid,
            "runoff_coefficient": RUNOFF_COEFF,
            "candidate_junctions_count": len(candidates),
            "random_seed": rng_seed,
            "sim_end_time": sim_end_time,
            "routing_step": routing_step,
            "reporting_step_s": reporting_step_s,
            "flood_threshold_cms": flood_threshold,
            "timesteps_count": len(simulation_results),
            "param_hash": param_hash,
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
    parser = argparse.ArgumentParser(description="HydroPulse Dynamic LHS Batch Simulation Factory v2.2")
    parser.add_argument("--samples", "-n", type=int, default=DEFAULT_SAMPLES,
                        help=f"Total LHS simulation runs (default: {DEFAULT_SAMPLES})")
    parser.add_argument("--workers", "-w", type=int, default=DEFAULT_WORKERS,
                        help=f"Concurrent worker processes (default: {DEFAULT_WORKERS})")
    parser.add_argument("--sim-end-time", "-t", type=str, default=DEFAULT_SIM_END_TIME,
                        help=f"Simulation duration (default: {DEFAULT_SIM_END_TIME})")
    parser.add_argument("--routing-step", type=str, default=DEFAULT_ROUTING_STEP,
                        help=f"DYNWAVE routing step (default: {DEFAULT_ROUTING_STEP})")
    parser.add_argument("--intensity-min", type=float, default=5.0,
                        help="Min rainfall intensity in mm/hr (default: 5.0 - light drizzle)")
    parser.add_argument("--intensity-max", type=float, default=150.0,
                        help="Max rainfall intensity in mm/hr (default: 150.0 - extreme cloudburst)")
    parser.add_argument("--spread-min", type=float, default=0.05,
                        help="Min fraction of junctions receiving inflow (default: 0.05 - tight cell)")
    parser.add_argument("--spread-max", type=float, default=0.60,
                        help="Max fraction of junctions receiving inflow (default: 0.60 - broad system)")
    parser.add_argument("--reporting-step", type=int, default=DEFAULT_REPORTING_STEP_S,
                        help=f"Reporting interval in seconds (default: {DEFAULT_REPORTING_STEP_S}s - 3 minutes, 40 timesteps for 2-hour event)")
    parser.add_argument("--flood-threshold", type=float, default=DEFAULT_FLOOD_THRESHOLD_CMS,
                        help=f"Min surface overflow rate in CMS to record as flooded (default: {DEFAULT_FLOOD_THRESHOLD_CMS} CMS / 1 L/s)")
    # [PRD-07] Inlet catchment area CLI argument (matching Stage 05 pipe design)
    parser.add_argument("--inlet-catchment", type=float, default=INLET_CATCHMENT_M2,
                        help=f"Contributing catchment area per inlet in m^2 (default: {INLET_CATCHMENT_M2} - matching Stage 05 pipe design)")
    parser.add_argument("--overwrite", action="store_true", default=False,
                        help="Force rerun and overwrite existing simulation files")

    args = parser.parse_args()

    if not BASE_INP.exists():
        raise FileNotFoundError(f"Base INP not found: {BASE_INP}")
    if not BOUNDARY_GEOJSON.exists():
        raise FileNotFoundError(f"Boundary AOI GeoJSON not found: {BOUNDARY_GEOJSON}")

    EVENTS_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_INP_DIR.mkdir(parents=True, exist_ok=True)

    # [PRD-01 + PRD-07] Extract candidate junctions strictly inside PRD-01 City AOI and connected to conduits
    print("Pre-filtering network junctions strictly within PRD-01 City AOI (967.2 km²)...")
    candidate_junctions, candidate_coords, candidate_catchments = load_candidate_junctions(
        BASE_INP, BOUNDARY_GEOJSON, NODES_GEOJSON
    )

    mean_all_catchment = statistics.mean(candidate_catchments.values()) if candidate_catchments else args.inlet_catchment

    print("=" * 70)
    print("  HydroPulse  |  LHS Batch Simulation Factory v2.2")
    print("  PRD-01 / PRD-07 City AOI (5 km Buffer) + Rational Method Hydrology")
    print("=" * 70)
    print(f"  Runs Planned     : {args.samples}")
    print(f"  Workers Active   : {args.workers}")
    print(f"  Storm Duration   : {args.sim_end_time}")
    print(f"  Routing Step     : {args.routing_step}")
    print(f"  Reporting Step   : {args.reporting_step}s ({args.reporting_step // 60} min, ~{int(int(args.sim_end_time.split(':')[0])*60 + int(args.sim_end_time.split(':')[1])) // (args.reporting_step // 60)} timesteps)")
    print(f"  Flood Threshold  : {args.flood_threshold} CMS ({args.flood_threshold * 1000:.1f} L/s)")
    print(f"  Rainfall Range   : {args.intensity_min}–{args.intensity_max} mm/hr")
    print(f"  Spread Range     : {args.spread_min}–{args.spread_max}")
    print(f"  Runoff Coeff (C) : {RUNOFF_COEFF} (from config/runoff_coefficients.yaml)")
    print(f"  Boundary Layer   : {BOUNDARY_GEOJSON.name} (PRD-01 5km Buffered AOI)")
    print(f"  City AOI Area    : {GRID_AREA_M2 / 1e6:.1f} km²")
    print(f"  Catchment Range  : {min(candidate_catchments.values()):.1f}–{max(candidate_catchments.values()):.1f} m² (mean: {mean_all_catchment:.1f} m², DEM flow acc)")
    print(f"  Valid Inlets     : {len(candidate_junctions):,} (connected junctions in AOI)")
    print("=" * 70)

    profiles = generate_lhs_profiles(
        n=args.samples,
        seed=LHS_SEED,
        int_min=args.intensity_min,
        int_max=args.intensity_max,
        spread_min=args.spread_min,
        spread_max=args.spread_max
    )

    is_single_run = (args.samples == 1 and args.workers == 1)

    jobs = [
        {
            **p,
            "base_inp": str(BASE_INP),
            "events_dir": str(EVENTS_DIR),
            "temp_inp_dir": str(TEMP_INP_DIR),
            "sim_end_time": args.sim_end_time,
            "routing_step": args.routing_step,
            "reporting_step_s": args.reporting_step,
            "flood_threshold": args.flood_threshold,
            "inlet_catchment_m2": args.inlet_catchment,
            "candidate_junctions": candidate_junctions,
            "candidate_coords": candidate_coords,
            "candidate_catchments": candidate_catchments,
            "overwrite": args.overwrite,
            "verbose_telemetry": is_single_run,
        }
        for p in profiles
    ]

    completed = failed = skipped = 0

    if is_single_run:
        # Clean single-run execution: direct execution without progress bar clobbering
        print("\nStarting simulation physics loop (2-hour storm window)...")
        res = _run_single_simulation(jobs[0])
        if res.get("skipped"):
            skipped += 1
            print(f"  [SKIPPED] File already exists with identical physics parameters.")
        elif res["ok"]:
            completed += 1
            print(f"\n  [OK] Run completed: {res['steps']} steps, {res['flooded_steps']} steps with active surface flooding.")
        else:
            failed += 1
            print(f"\n  [FAILED] {res.get('error')}")
    else:
        # Multi-worker batch mode: live tqdm progress bar across runs
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