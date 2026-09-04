import os
import geopandas as gpd
import osmnx as ox
from utils import ProvenanceLogger, DataValidator

def main():
    aoi_path = "../data/boundaries/mumbai_aoi_5km.geojson"
    output_dir = "../data/osm"
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, "mumbai_roads.graphml")
    
    if not os.path.exists(aoi_path):
        print(f"Error: AOI not found at {aoi_path}. Run 01_fetch_boundaries.py first.")
        return
        
    print("Loading AOI...")
    aoi_gdf = gpd.read_file(aoi_path)
    aoi_polygon = aoi_gdf.geometry.iloc[0]
    
    print("Fetching drivable road network from OSM...")
    # Fetch drivable road network
    graph = ox.graph_from_polygon(aoi_polygon, network_type="drive")
    
    print("Saving graph to graphml...")
    ox.save_graphml(graph, filepath=out_path)
    
    logger = ProvenanceLogger()
    validator = DataValidator()
    
    print("Validating saved graph...")
    if validator.validate_graphml(out_path):
        logger.log_dataset("mumbai_roads", "Mumbai", "OSM", out_path)
        print("OSM road network fetched successfully.")

if __name__ == "__main__":
    main()
