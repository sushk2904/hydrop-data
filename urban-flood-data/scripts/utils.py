import csv
import os
from datetime import datetime
import geopandas as gpd
import rasterio

class ProvenanceLogger:
    def __init__(self, manifest_path: str = "../data/manifest.csv"):
        self.manifest_path = manifest_path
        self._ensure_manifest()

    def _ensure_manifest(self):
        os.makedirs(os.path.dirname(self.manifest_path), exist_ok=True)
        if not os.path.exists(self.manifest_path):
            with open(self.manifest_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["dataset_id", "city", "source", "file_path", "acquired_at"])

    def log_dataset(self, dataset_id: str, city: str, source: str, file_path: str):
        acquired_at = datetime.utcnow().isoformat() + "Z"
        with open(self.manifest_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([dataset_id, city, source, file_path, acquired_at])
        print(f"Logged {dataset_id} to provenance manifest.")

class DataValidator:
    @staticmethod
    def validate_geojson(file_path: str) -> bool:
        try:
            gdf = gpd.read_file(file_path)
            if gdf.empty:
                print(f"Validation failed: {file_path} is empty.")
                return False
            invalid_geoms = gdf[~gdf.is_valid]
            if not invalid_geoms.empty:
                print(f"Validation failed: {file_path} contains invalid geometries.")
                return False
            print(f"Validation passed: {file_path} contains valid geometries.")
            return True
        except Exception as e:
            print(f"Validation error for {file_path}: {e}")
            return False

    @staticmethod
    def validate_raster_crs(file_path: str) -> bool:
        try:
            with rasterio.open(file_path) as src:
                crs = src.crs
                if crs is None:
                    print(f"Validation failed: {file_path} has no CRS.")
                    return False
                if crs.to_epsg() == 4326 or crs.is_projected:
                    print(f"Validation passed: {file_path} has valid CRS ({crs}).")
                    return True
                else:
                    print(f"Validation failed: {file_path} has unsupported CRS ({crs}).")
                    return False
        except Exception as e:
            print(f"Validation error for raster {file_path}: {e}")
            return False

    @staticmethod
    def validate_graphml(file_path: str) -> bool:
        try:
            import osmnx as ox
            graph = ox.load_graphml(file_path)
            if len(graph.nodes) == 0:
                print(f"Validation failed: {file_path} is an empty graph.")
                return False
            print(f"Validation passed: {file_path} is a valid graph with {len(graph.nodes)} nodes.")
            return True
        except Exception as e:
            print(f"Validation error for graphml {file_path}: {e}")
            return False
