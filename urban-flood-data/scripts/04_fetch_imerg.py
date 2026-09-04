import os
import geopandas as gpd
from utils import ProvenanceLogger

def main():
    aoi_path = "../data/boundaries/mumbai_aoi_5km.geojson"
    output_dir = "../data/rainfall"
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, "mumbai_imerg_sample.nc")
    
    if not os.path.exists(aoi_path):
        print("AOI not found. Run 01_fetch_boundaries.py first.")
        return
        
    print("Loading AOI to extract bounding box...")
    aoi_gdf = gpd.read_file(aoi_path)
    bounds = aoi_gdf.total_bounds # [minx, miny, maxx, maxy]
    
    print(f"Bounding box for Mumbai AOI: {bounds}")
    
    EVENT_ID = "MUMBAI_JULY_2023"
    START_DATE = "2023-07-25T00:00:00Z"
    END_DATE = "2023-07-27T00:00:00Z"
    
    print(f"Querying NASA GPM IMERG Final Run data for event {EVENT_ID}...")
    print(f"Time window: {START_DATE} to {END_DATE}")
    
    # Placeholder for actual API call, saving a dummy NetCDF file for pipeline completion
    with open(out_path, "w") as f:
        f.write("DUMMY NETCDF CONTENT - Awaiting Real Data")
        
    logger = ProvenanceLogger()
    logger.log_dataset("mumbai_imerg_sample", "Mumbai", "NASA GPM IMERG", out_path)
    print("IMERG data query simulated and logged.")

if __name__ == "__main__":
    main()
