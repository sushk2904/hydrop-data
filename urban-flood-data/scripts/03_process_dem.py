import os
import numpy as np
if not hasattr(np, 'in1d'):
    np.in1d = lambda ar1, ar2, assume_unique=False, invert=False, *, kind=None: np.isin(ar1, ar2, assume_unique=assume_unique, invert=invert)

import geopandas as gpd
import rasterio
from rasterio.mask import mask
from pysheds.grid import Grid
from utils import ProvenanceLogger, DataValidator

def main():
    raw_dem_path = "../data/terrain/mumbai_raw_cartodem.tif"
    clipped_dem_path = "../data/terrain/mumbai_dem_clipped.tif"
    filled_dem_path = "../data/terrain/mumbai_dem_filled.tif"
    flow_acc_path = "../data/terrain/mumbai_flow_acc.tif"
    aoi_path = "../data/boundaries/mumbai_aoi_5km.geojson"
    
    logger = ProvenanceLogger()
    validator = DataValidator()
    
    if not os.path.exists(raw_dem_path):
        print(f"Raw DEM not found at {raw_dem_path}. Please place it manually before running this script.")
        return
        
    print("Loading AOI...")
    aoi_gdf = gpd.read_file(aoi_path)
    
    print("Clipping DEM to AOI...")
    with rasterio.open(raw_dem_path) as src:
        # Convert AOI to same CRS as the DEM
        aoi_gdf = aoi_gdf.to_crs(src.crs)
        out_image, out_transform = mask(src, aoi_gdf.geometry, crop=True)
        out_meta = src.meta.copy()
        
    out_meta.update({
        "driver": "GTiff",
        "height": out_image.shape[1],
        "width": out_image.shape[2],
        "transform": out_transform
    })
    
    with rasterio.open(clipped_dem_path, "w", **out_meta) as dest:
        dest.write(out_image)
        
    if validator.validate_raster_crs(clipped_dem_path):
        logger.log_dataset("mumbai_dem_clipped", "Mumbai", "ISRO CartoDEM", clipped_dem_path)
        
    print("Running pit-filling and flow accumulation using pysheds...")
    grid = Grid.from_raster(clipped_dem_path)
    dem = grid.read_raster(clipped_dem_path)
    
    # Pit filling
    pit_filled_dem = grid.fill_pits(dem)
    
    # Save filled DEM
    grid.to_raster(pit_filled_dem, filled_dem_path)
    if validator.validate_raster_crs(filled_dem_path):
        logger.log_dataset("mumbai_dem_filled", "Mumbai", "Derived from DEM", filled_dem_path)

    # Flow direction
    fdir = grid.flowdir(pit_filled_dem)
    # Flow accumulation
    acc = grid.accumulation(fdir)
    
    # Save flow accumulation
    grid.to_raster(acc, flow_acc_path)
    
    if validator.validate_raster_crs(flow_acc_path):
        logger.log_dataset("mumbai_flow_accumulation", "Mumbai", "Derived from DEM", flow_acc_path)
        
    print("DEM processing complete.")

if __name__ == "__main__":
    main()
