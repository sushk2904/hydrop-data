"""
07_lhs_batch_factory.py
=======================
HydroPulse Enterprise Batch Simulation Factory
-----------------------------------------------
Generates N parametric SWMM simulation runs using Latin Hypercube Sampling (LHS)
across three physics variables, executed in parallel via ProcessPoolExecutor with
full artifact isolation, tqdm telemetry, and zero disk bloat.

Pipeline Stage : 07
Inputs         : ../data/drainage/mumbai_synthetic.inp
                 ../data/drainage/mumbai_synthetic_nodes.geojson
Outputs        : ../data/events/mumbai_baked_sim_LHS_{id}.json  (one per run)
Provenance     : appended to manifest via ProvenanceLogger

Physics invariants preserved from Stage 06
-------------------------------------------
  - FLOW_ROUTING DYNWAVE
  - ROUTING_STEP 15 seconds (Courant condition)
  - END_TIME 02:00:00 (2-hour storm window)
  - MaxDepth / INFLOWS block intact in base INP
"""

# -- Standard library ----------------------------------------------------------
import os
import re
import json
import random
import traceback
import logging
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

# -- Third-party ---------------------------------------------------------------
import geopandas as gpd
import numpy as np
from scipy.stats.qmc import LatinHypercube
from tqdm import tqdm
from pyswmm import Simulation, Nodes

# -- Project utilities ---------------------------------------------------------
# utils.py lives in the same scripts/ directory; ProcessPoolExecutor workers
# inherit sys.path from the parent, so the import is safe.
from utils import ProvenanceLogger

# =============================================================================
# CONFIGURATION  -  edit here, nowhere else
# =============================================================================

# Paths (relative to this script's location)
_SCRIPT_DIR      = Path(__file__).resolve().parent
_DATA_DIR        = _SCRIPT_DIR / ".." / "data"
BASE_INP         = _DATA_DIR / "drainage" / "mumbai_synthetic.inp"
NODES_GEOJSON    = _DATA_DIR / "drainage" / "mumbai_synthetic_nodes.geojson"
EVENTS_DIR       = _DATA_DIR / "events"
TEMP_INP_DIR     = _DATA_DIR / "drainage" / "_tmp_lhs"   # isolated worker files

# LHS sampling parameters
N_SAMPLES        = 1500          # total simulation runs
LHS_SEED         = 0             # reproducible LHS draw (workers use their own seeds)

# LHS variable ranges
INTENSITY_MIN    = 0.05          # CMS  - lower bound
INTENSITY_MAX    = 2.50          # CMS  - upper bound
SPREAD_MIN       = 0.10          # fraction of junctions (10%)
SPREAD_MAX       = 0.50          # fraction of junctions (50%)

# Parallelism
N_WORKERS        = max(1, (os.cpu_count() or 2) - 1)

# SWMM simulation settings (must match physics invariants)
REPORTING_STEP_S = 60            # seconds between recorded snapshots
SIM_END_TIME     = "02:00:00"
ROUTING_STEP     = "0:00:15"

# =============================================================================
# LOGGING
# =============================================================================

logging.basicConfig(
    level=logging.WARNING,           # suppress per-worker chatter; tqdm owns stdout
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("lhs_factory")


# =============================================================================
# LATIN HYPERCUBE SAMPLING
# =============================================================================

def generate_lhs_profiles(n: int, seed: int) -> list:
    """
    Draw n parametric profiles via Latin Hypercube Sampling.

    Dimensions
    ----------
    0 : intensity_cms   - constant inflow per injected junction (CMS)
    1 : spatial_spread  - fraction of total junctions receiving inflow
    2 : rng_unit        - [0,1) uniform, scaled to an integer seed per worker
                          so spatial injection patterns are maximally varied.

    Returns
    -------
    List of dicts, one per run:
        {id, intensity_cms, spatial_spread, random_seed}
    """
    sampler = LatinHypercube(d=3, seed=seed)
    unit_cube = sampler.random(n=n)          # shape (n, 3), values in [0, 1)

    profiles = []
    for i, row in enumerate(unit_cube):
        intensity   = INTENSITY_MIN + row[0] * (INTENSITY_MAX - INTENSITY_MIN)
        spread      = SPREAD_MIN    + row[1] * (SPREAD_MAX    - SPREAD_MIN)
        worker_seed = int(row[2] * 2**31)    # large integer seed for spatial RNG

        profiles.append({
            "id":             i,
            "intensity_cms":  round(float(intensity), 6),
            "spatial_spread": round(float(spread),    6),
            "random_seed":    worker_seed,
        })
    return profiles


# =============================================================================
# WORKER - runs in a subprocess; must be top-level for pickle
# =============================================================================

def _run_single_simulation(job: dict) -> dict:
    """
    Isolated simulation worker.

    Protocol
    --------
    1. Read the immutable base INP from disk (read-only).
    2. Patch ROUTING_STEP, END_TIME, and inject [INFLOWS] using job params.
    3. Write to a uniquely-named temp INP under TEMP_INP_DIR.
    4. Run the SWMM physics loop; record flooding at each reporting step.
    5. Dump results to JSON in EVENTS_DIR.
    6. Delete the temp INP (prevent disk bloat).
    7. Return a lightweight status dict to the parent process.

    Parameters
    ----------
    job : dict with keys {id, intensity_cms, spatial_spread, random_seed,
                          base_inp, nodes_geojson, events_dir, temp_inp_dir}
    """
    run_id       = job["id"]
    intensity    = job["intensity_cms"]
    spread       = job["spatial_spread"]
    rng_seed     = job["random_seed"]
    base_inp     = Path(job["base_inp"])
    events_dir   = Path(job["events_dir"])
    temp_inp_dir = Path(job["temp_inp_dir"])
    node_coords  = job["node_coords"]       # pre-loaded dict passed from parent

    temp_inp = temp_inp_dir / f"mumbai_storm_LHS_{run_id:05d}.inp"
    out_json = events_dir   / f"mumbai_baked_sim_LHS_{run_id:05d}.json"

    status = {
        "id":            run_id,
        "ok":            False,
        "steps":         0,
        "flooded_steps": 0,
        "skipped":       False,
        "error":         None,
    }

    # -- Skip if already completed (idempotent restarts) ----------------------
    if out_json.exists():
        status["ok"]      = True
        status["skipped"] = True
        return status

    # -- Read immutable base INP -----------------------------------------------
    try:
        content = base_inp.read_text(encoding="utf-8")
    except Exception as exc:
        status["error"] = f"INP read failed: {exc}"
        return status

    # -- Parse junctions -------------------------------------------------------
    junctions = re.findall(r"^(\d+)\s+[\d\.]+\s+0\s+0", content, re.MULTILINE)
    if not junctions:
        status["error"] = "No junctions parsed from INP."
        return status

    # -- Spatially sample inflow nodes -----------------------------------------
    rng      = random.Random(rng_seed)
    n_inject = max(1, int(len(junctions) * spread))
    inflow_nodes = set(rng.sample(junctions, min(n_inject, len(junctions))))

    # -- Build [INFLOWS] block -------------------------------------------------
    inflows_block = (
        "\n[INFLOWS]\n"
        ";;Node           Constituent      Time Series      Type     "
        "Mfactor  Sfactor  Baseline Pattern\n"
    )
    for nid in inflow_nodes:
        inflows_block += f"{nid} FLOW \"\" FLOW 1.0 1.0 {intensity:.6f}\n"

    # -- Patch temporal settings (regex replaces are idempotent) ---------------
    content = re.sub(
        r"ROUTING_STEP\s+\S+",
        f"ROUTING_STEP         {ROUTING_STEP}",
        content,
    )
    content = re.sub(
        r"END_TIME\s+\S+",
        f"END_TIME             {SIM_END_TIME}",
        content,
    )

    # -- Write isolated temp INP -----------------------------------------------
    try:
        temp_inp.write_text(content + inflows_block, encoding="utf-8")
    except Exception as exc:
        status["error"] = f"Temp INP write failed: {exc}"
        return status

    # -- Run SWMM physics loop -------------------------------------------------
    simulation_results = {}
    try:
        with Simulation(str(temp_inp)) as sim:
            sim.step_advance(REPORTING_STEP_S)
            step_count = 0

            for _step in sim:
                current_time = sim.current_time.isoformat()
                flooded = []

                for node in Nodes(sim):
                    if node.flooding > 0:
                        nid    = str(node.nodeid)
                        coords = node_coords.get(nid, {"lat": 0.0, "lon": 0.0})
                        flooded.append({
                            "node_id":      nid,
                            "lat":          coords["lat"],
                            "lon":          coords["lon"],
                            "overflow_cms": round(node.flooding, 4),
                            "depth_m":      round(node.depth,    4),
                        })

                if flooded:
                    simulation_results[current_time] = flooded
                    status["flooded_steps"] += 1

                step_count += 1

            status["steps"] = step_count

    except Exception as exc:
        status["error"] = f"SWMM runtime error: {exc}\n{traceback.format_exc()}"
        return status

    finally:
        # -- ALWAYS delete the temp INP to prevent disk bloat ------------------
        try:
            temp_inp.unlink(missing_ok=True)
        except Exception:
            pass   # best-effort; do not mask the real error

    # -- Persist results JSON --------------------------------------------------
    output_payload = {
        "meta": {
            "run_id":           run_id,
            "intensity_cms":    intensity,
            "spatial_spread":   spread,
            "random_seed":      rng_seed,
            "n_injected":       len(inflow_nodes),
            "sim_end_time":     SIM_END_TIME,
            "routing_step":     ROUTING_STEP,
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
# MAIN  -  orchestrator
# =============================================================================

def main():
    print("=" * 70)
    print("  HydroPulse  |  LHS Batch Simulation Factory  |  Stage 07")
    print("=" * 70)

    # -- Validate paths --------------------------------------------------------
    if not BASE_INP.exists():
        raise FileNotFoundError(f"Base INP not found: {BASE_INP}")
    if not NODES_GEOJSON.exists():
        raise FileNotFoundError(f"Nodes GeoJSON not found: {NODES_GEOJSON}")

    EVENTS_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_INP_DIR.mkdir(parents=True, exist_ok=True)

    # -- Pre-load node coordinates once in the parent process ------------------
    # Sharing via job dict avoids re-reading the GeoJSON in every worker.
    print(f"Loading {NODES_GEOJSON.name} ...")
    nodes_gdf   = gpd.read_file(NODES_GEOJSON)
    node_coords = {
        str(row["id"]): {"lat": row.geometry.y, "lon": row.geometry.x}
        for _, row in nodes_gdf.iterrows()
    }
    print(f"  OK  {len(node_coords):,} nodes loaded.")

    # -- Generate LHS parameter profiles ---------------------------------------
    print(f"\nGenerating {N_SAMPLES} LHS profiles (seed={LHS_SEED}) ...")
    profiles = generate_lhs_profiles(N_SAMPLES, LHS_SEED)

    intensities = [p["intensity_cms"]  for p in profiles]
    spreads     = [p["spatial_spread"] for p in profiles]
    print(f"  intensity_cms  : [{min(intensities):.4f}, {max(intensities):.4f}] CMS")
    print(f"  spatial_spread : [{min(spreads):.4f}, {max(spreads):.4f}]")
    print(f"  OK  LHS draw complete.\n")

    # -- Build job payloads ----------------------------------------------------
    jobs = [
        {
            **profile,
            "base_inp":     str(BASE_INP),
            "events_dir":   str(EVENTS_DIR),
            "temp_inp_dir": str(TEMP_INP_DIR),
            "node_coords":  node_coords,
        }
        for profile in profiles
    ]

    # -- Launch ProcessPoolExecutor --------------------------------------------
    print(f"Launching {N_WORKERS} parallel workers across {N_SAMPLES} runs ...")
    print(f"  Workers    : {N_WORKERS} / {os.cpu_count()} logical CPUs")
    print(f"  Events dir : {EVENTS_DIR}")
    print()

    completed = 0
    failed    = 0
    skipped   = 0

    with ProcessPoolExecutor(max_workers=N_WORKERS) as executor:
        # Submit all jobs upfront
        future_to_job = {
            executor.submit(_run_single_simulation, job): job
            for job in jobs
        }

        # tqdm wraps as_completed - live [done/total elapsed<eta rate] bar
        with tqdm(
            as_completed(future_to_job),
            total=N_SAMPLES,
            desc="Simulating",
            unit="run",
            dynamic_ncols=True,
            colour="cyan",
        ) as pbar:
            for future in pbar:
                try:
                    result = future.result()
                except Exception as exc:
                    failed += 1
                    log.error("Unhandled future exception: %s", exc)
                    pbar.set_postfix_str(
                        f"done={completed} skip={skipped} fail={failed}",
                        refresh=False,
                    )
                    continue

                if result.get("skipped"):
                    skipped += 1
                elif result["ok"]:
                    completed += 1
                else:
                    failed += 1
                    log.warning(
                        "Run %05d FAILED: %s",
                        result["id"],
                        result.get("error", "unknown"),
                    )

                pbar.set_postfix_str(
                    f"done={completed} skip={skipped} fail={failed}",
                    refresh=False,
                )

    # -- Cleanup temp dir (should be empty; belt-and-suspenders) ---------------
    try:
        remaining = list(TEMP_INP_DIR.glob("*.inp"))
        if remaining:
            log.warning(
                "%d orphaned temp INP files found - cleaning up.", len(remaining)
            )
            for f in remaining:
                f.unlink(missing_ok=True)
        TEMP_INP_DIR.rmdir()          # only succeeds when empty
    except Exception:
        pass

    # -- Final report ----------------------------------------------------------
    total_produced = completed + skipped
    print()
    print("=" * 70)
    print("  FACTORY COMPLETE")
    print(f"  Total runs     : {N_SAMPLES}")
    print(f"  Produced (new) : {completed}")
    print(f"  Skipped (exist): {skipped}")
    print(f"  Failed         : {failed}")
    print(f"  Success rate   : {total_produced / N_SAMPLES * 100:.1f}%")
    print(f"  Output dir     : {EVENTS_DIR}")
    print("=" * 70)

    # -- Provenance log --------------------------------------------------------
    if completed > 0:
        try:
            logger = ProvenanceLogger()
            logger.log_dataset(
                "lhs_batch_simulations",
                "Mumbai",
                "PySWMM+LHS",
                str(EVENTS_DIR),
            )
            print("  Provenance entry written.")
        except Exception as exc:
            log.warning("Provenance logging failed: %s", exc)


# =============================================================================
# Entry point guard - REQUIRED for ProcessPoolExecutor on Windows
# =============================================================================
if __name__ == "__main__":
    main()
