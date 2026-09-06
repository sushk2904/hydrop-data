import os
import math
import networkx as nx
import osmnx as ox
import rasterio
import geopandas as gpd
from shapely.geometry import Point, LineString
from shapely import wkt
from utils import ProvenanceLogger

def get_elevation(x, y, src):
    try:
        for val in src.sample([(x, y)]):
            return float(val[0])
    except Exception:
        return 0.0

def main():
    osm_path = "../data/osm/mumbai_roads.graphml"
    dem_path = "../data/terrain/mumbai_dem_filled.tif"
    
    out_nodes_path = "../data/drainage/mumbai_synthetic_nodes.geojson"
    out_pipes_path = "../data/drainage/mumbai_synthetic_pipes.geojson"
    out_inp_path = "../data/drainage/mumbai_synthetic.inp"
    os.makedirs("../data/drainage", exist_ok=True)
    
    print("Loading OSM road graph...")
    G = ox.load_graphml(osm_path)
    
    print("Sampling elevation from DEM...")
    with rasterio.open(dem_path) as src:
        for node, data in G.nodes(data=True):
            z = get_elevation(data['x'], data['y'], src)
            data['elevation'] = z
            
    print("Building gravity-fed DiGraph...")
    D = nx.DiGraph()
    
    for node, data in G.nodes(data=True):
        D.add_node(node, x=data['x'], y=data['y'], elevation=data['elevation'])
        
    edge_id_counter = 0
    # Process edges
    for u, v, key, data in G.edges(keys=True, data=True):
        z_u = D.nodes[u]['elevation']
        z_v = D.nodes[v]['elevation']
        
        # Safely extract length
        if 'length' in data:
            try:
                length = float(data['length'])
            except:
                length = 1.0
        else:
            length = 1.0
            
        if length <= 0:
            length = 0.001
            
        if z_u == z_v:
            continue # perfectly flat? Just ignore or add arbitary flow? The logic says "strictly from the node with HIGHER to LOWER". So skip flat.
            
        # Determine flow direction
        if z_u > z_v:
            from_node, to_node = u, v
            delta_z = z_u - z_v
        else:
            from_node, to_node = v, u
            delta_z = z_v - z_u
            
        slope = delta_z / length
        if slope <= 0:
            slope = 0.001
            
        # Hydraulic Sizing
        C = 0.8
        I_ms = 0.1 / 3600.0 # 100 mm/hr converted to m/s
        A = 500.0 # m^2
        Q = C * I_ms * A # Discharge in m^3/s
        
        n = 0.013 # Manning's roughness
        # D = ((Q * n) / (0.311 * S^(1/2)))^(3/8)
        diameter = ((Q * n) / (0.311 * math.sqrt(slope)))**(3.0/8.0)
        
        geom = data.get('geometry')
        if not geom:
            geom = LineString([(D.nodes[from_node]['x'], D.nodes[from_node]['y']), 
                               (D.nodes[to_node]['x'], D.nodes[to_node]['y'])])
        
        edge_id = f"pipe_{edge_id_counter}"
        edge_id_counter += 1
        
        D.add_edge(from_node, to_node, id=edge_id, length=length, slope=slope, diameter=diameter, geometry=geom)
        
    print(f"Graph built with {len(D.nodes)} nodes and {len(D.edges)} edges.")
    
    is_dag = nx.is_directed_acyclic_graph(D)
    print(f"Is Directed Acyclic Graph (DAG)? {is_dag}")
    
    print("Sampling flow accumulation from DEM for catchment area estimation (PRD-07)...")
    flow_acc_path = "../data/terrain/mumbai_flow_acc.tif"
    node_catchment = {}
    if os.path.exists(flow_acc_path):
        with rasterio.open(flow_acc_path) as acc_src:
            for node, data in D.nodes(data=True):
                try:
                    for val in acc_src.sample([(data['x'], data['y'])]):
                        acc = float(val[0])
                        # Baseline street catchment (500 m²) + flow accumulation tributary area, capped to 5000 m²
                        node_catchment[node] = round(min(5000.0, 500.0 + max(0.0, acc) * 250.0), 1)
                        break
                except Exception:
                    node_catchment[node] = 500.0
    else:
        for node in D.nodes():
            node_catchment[node] = 500.0

    print("Exporting GeoJSONs with PRD-07 node attributes...")
    nodes_data = []
    for node, data in D.nodes(data=True):
        # Determine downstream node from directed graph successors
        successors = list(D.successors(node))
        downstream = str(successors[0]) if successors else "OUTFALL"
        nodes_data.append({
            'id': str(node),
            'elevation': data['elevation'],
            'catchment_area': node_catchment.get(node, 500.0),
            'downstream_node': downstream,
            'surface_type': 'urban_impervious',
            'geometry': Point(data['x'], data['y'])
        })
    nodes_gdf = gpd.GeoDataFrame(nodes_data, crs="EPSG:4326")
    nodes_gdf.to_file(out_nodes_path, driver="GeoJSON")
    
    edges_data = []
    for u, v, data in D.edges(data=True):
        edges_data.append({
            'id': data['id'],
            'from_node': str(u),
            'to_node': str(v),
            'length': data['length'],
            'slope': data['slope'],
            'diameter': data['diameter'],
            'geometry': data['geometry']
        })
    if edges_data:
        edges_gdf = gpd.GeoDataFrame(edges_data, crs="EPSG:4326")
        for i, row in edges_gdf.iterrows():
            if isinstance(row['geometry'], str):
                edges_gdf.at[i, 'geometry'] = wkt.loads(row['geometry'])
        edges_gdf.to_file(out_pipes_path, driver="GeoJSON")
        
    print("Writing SWMM .inp file...")
    with open(out_inp_path, "w", encoding="utf-8") as f:
        f.write("[TITLE]\nSynthetic Drainage Network\n\n")
        f.write("[JUNCTIONS]\n;;Name Elevation MaxDepth InitDepth SurDepth Aponded\n")
        for node, data in D.nodes(data=True):
            f.write(f"{node} {data['elevation']:.3f} 0 0 0 0\n")
            
        f.write("\n[CONDUITS]\n;;Name Node1 Node2 Length Roughness InOffset OutOffset InitFlow MaxFlow\n")
        for u, v, data in D.edges(data=True):
            f.write(f"{data['id']} {u} {v} {data['length']:.3f} 0.013 0 0 0 0\n")
            
        f.write("\n[XSECTIONS]\n;;Link Shape Geom1 Geom2 Geom3 Geom4 Barrels Culvert\n")
        for u, v, data in D.edges(data=True):
            f.write(f"{data['id']} CIRCULAR {data['diameter']:.3f} 0 0 0 1\n")
            
        f.write("\n[COORDINATES]\n;;Node X-Coord Y-Coord\n")
        for node, data in D.nodes(data=True):
            f.write(f"{node} {data['x']} {data['y']}\n")
            
    print("Logging to Provenance...")
    logger = ProvenanceLogger()
    logger.log_dataset("SYNTHETIC_drainage_nodes", "Mumbai", "SYNTHETIC GENERATION", out_nodes_path)
    logger.log_dataset("SYNTHETIC_drainage_pipes", "Mumbai", "SYNTHETIC GENERATION", out_pipes_path)
    logger.log_dataset("SYNTHETIC_swmm_inp", "Mumbai", "SYNTHETIC GENERATION", out_inp_path)
    
    print("Synthetic drainage generation complete.")

if __name__ == "__main__":
    main()
