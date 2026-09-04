import os
import geopandas as gpd
import osmnx as ox
from utils import ProvenanceLogger, DataValidator

def main():
    query = {'city': 'Mumbai', 'state': 'Maharashtra', 'country': 'India'}
    output_dir = "../data/boundaries"
    os.makedirs(output_dir, exist_ok=True)
    
    exact_path = os.path.join(output_dir, "mumbai_boundary.geojson")
    aoi_path = os.path.join(output_dir, "mumbai_aoi_5km.geojson")
    
    logger = ProvenanceLogger()
    validator = DataValidator()
    
    print(f"Fetching boundary for {query}...")
    try:
        gdf = ox.geocode_to_gdf(query)
    except Exception as e:
        print(f"Dict query failed ({e}). Nominatim returned a node. Falling back to 'Mumbai Suburban'...")
        gdf = ox.geocode_to_gdf("Mumbai Suburban")
    
    # Self-validation
    geom_type = gdf.geometry.iloc[0].type
    if geom_type not in ["Polygon", "MultiPolygon"]:
        raise ValueError(f"Expected Polygon/MultiPolygon, but got {geom_type}")
        
    # Check geographic area (project to local UTM to measure in square meters)
    gdf_utm_test = gdf.to_crs(gdf.estimate_utm_crs())
    area_sq_km = gdf_utm_test.geometry.area.sum() / 1e6
    print(f"Detected area: {area_sq_km:.2f} sq km")
    if area_sq_km < 100:
        raise ValueError(f"Area too small ({area_sq_km:.2f} sq km), this looks like a building, not a metropolis!")
    
    # Save exact boundary
    gdf.to_file(exact_path, driver="GeoJSON")
    print("Validating exact boundary...")
    if validator.validate_geojson(exact_path):
        logger.log_dataset("mumbai_boundary", "Mumbai", "OSM", exact_path)
    
    # Create 5km buffer (AOI)
    print("Creating 5km AOI buffer...")
    # Project to an appropriate UTM zone for accurate metric buffering
    gdf_utm = gdf.to_crs(gdf.estimate_utm_crs())
    gdf_utm_buffer = gdf_utm.copy()
    gdf_utm_buffer.geometry = gdf_utm.buffer(5000)
    gdf_buffer = gdf_utm_buffer.to_crs(gdf.crs)
    
    gdf_buffer.to_file(aoi_path, driver="GeoJSON")
    print("Validating AOI boundary...")
    if validator.validate_geojson(aoi_path):
        logger.log_dataset("mumbai_aoi_5km", "Mumbai", "OSM", aoi_path)

if __name__ == "__main__":
    main()
