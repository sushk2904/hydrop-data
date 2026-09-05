import os
import json
import random
import traceback
import geopandas as gpd
from pyswmm import Simulation, Nodes
from utils import ProvenanceLogger

def main():
    inp_path = "../data/drainage/mumbai_synthetic.inp"
    storm_inp_path = "../data/drainage/mumbai_storm.inp"
    nodes_geojson_path = "../data/drainage/mumbai_synthetic_nodes.geojson"
    out_json_path = "../data/events/mumbai_baked_simulation.json"
    os.makedirs(os.path.dirname(out_json_path), exist_ok=True)
    
    print("Loading node coordinates from GeoJSON...")
    node_coords = {}
    try:
        nodes_gdf = gpd.read_file(nodes_geojson_path)
        for _, row in nodes_gdf.iterrows():
            node_coords[str(row['id'])] = {"lat": row.geometry.y, "lon": row.geometry.x}
    except Exception as e:
        print(f"Error loading nodes geojson: {e}")
        return

    # Create the storm INP by copying the original and appending INFLOWS
    print("Generating storm INP with hardcoded baseline inflows...")
    with open(inp_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    # Get all junction IDs
    import re
    junctions = re.findall(r"^(\d+)\s+[\d\.]+\s+0\s+0", content, re.MULTILINE)
    
    random.seed(42)
    num_nodes_to_inject = int(len(junctions) * 0.3)
    inflow_nodes = set(random.sample(junctions, num_nodes_to_inject))
    
    inflows_block = "\n[INFLOWS]\n;;Node           Constituent      Time Series      Type     Mfactor  Sfactor  Baseline Pattern\n"
    for nid in inflow_nodes:
        # 0.5 CMS constant baseline inflow
        inflows_block += f"{nid} FLOW \"\" FLOW 1.0 1.0 0.5\n"

    # Replace ROUTING_STEP to 15 seconds for Dynamic Wave stability if present
    content = content.replace("ROUTING_STEP         0:01:00", "ROUTING_STEP         0:00:15")
    # [Fix F-007] Stabilize short conduits against Courant time-step collapse
    content = content.replace("LENGTHENING_STEP     0", "LENGTHENING_STEP     15")
    # Reduce simulation length to 2 hours to avoid 50 min runtime
    content = content.replace("END_TIME             06:00:00", "END_TIME             02:00:00")

    with open(storm_inp_path, "w", encoding="utf-8") as f:
        f.write(content)
        f.write(inflows_block)

    print("Initializing PySWMM Simulation...")
    try:
        from swmm.toolkit import solver
        from swmm.toolkit.shared_enum import NodeResult, ObjectType

        with Simulation(storm_inp_path) as sim:
            sim.step_advance(60)  # 60 seconds reporting step size
            
            num_nodes = sim._model.getProjectSize(ObjectType.NODE.value)
            print(f"Pre-caching {num_nodes:,} node IDs for accelerated C-API access...")
            node_ids = [sim._model.getObjectId(ObjectType.NODE.value, i) for i in range(num_nodes)]
            
            print(f"Tracking 0.5 m^3/s injected into {num_nodes_to_inject} random nodes...")
            
            simulation_results = {}
            step_count = 0
            flood_enum = NodeResult.FLOOD.value
            depth_enum = NodeResult.DEPTH.value
            
            print("Starting the physics event loop...", flush=True)
            for step in sim:
                current_time = sim.current_time.isoformat()
                
                flooded_nodes_this_step = []
                for idx in range(num_nodes):
                    f = solver.node_get_result(idx, flood_enum)
                    if f > 0:
                        nid = node_ids[idx]
                        coords = node_coords.get(nid, {"lat": 0.0, "lon": 0.0})
                        flooded_nodes_this_step.append({
                            "node_id": nid,
                            "lat": coords["lat"],
                            "lon": coords["lon"],
                            "overflow_cms": round(f, 4)
                        })
                        
                if flooded_nodes_this_step:
                    simulation_results[current_time] = flooded_nodes_this_step
                
                step_count += 1
                if step_count % 10 == 0 or step_count <= 5:
                    print(f"Step {step_count:3d} (sim time: {current_time}) — flooded nodes: {len(flooded_nodes_this_step):,}", flush=True)
                    
    except Exception as e:
        print(f"Simulation failed: {e}", flush=True)
        traceback.print_exc()
        return

    print(f"Simulation complete. {len(simulation_results)} timesteps had flooding.")
    print("Saving baked simulation results...")
    try:
        with open(out_json_path, "w", encoding="utf-8") as f:
            json.dump(simulation_results, f)
    except Exception as e:
        print(f"Error saving JSON: {e}")
        return
        
    print("Logging to provenance...")
    logger = ProvenanceLogger()
    logger.log_dataset("mumbai_baked_simulation", "Mumbai", "PySWMM", out_json_path)
    
    print("Baked JSON dropped successfully.")

if __name__ == "__main__":
    main()
