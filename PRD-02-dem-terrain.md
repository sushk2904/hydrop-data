# PRD-02 — DEM / Elevation Dataset

## Objective
Acquire and preprocess Digital Elevation Model (DEM) data for Mumbai, Delhi, and Chennai to support surface runoff, flow accumulation, terrain analysis, and later inundation modelling.

The research document identifies CartoDEM, Copernicus DEM, and SRTM as candidate open-source DEM sources.

## Sources

### Primary
ISRO / NRSC Bhuvan:
https://bhuvan-app3.nrsc.gov.in/data/

### Alternative
Copernicus DEM:
https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM

## Processing Pipeline
```text
Raw DEM
  ↓
Mosaic tiles if required
  ↓
Reproject to metric CRS
  ↓
Clip to AOI
  ↓
Hydrological sink/pit filling
  ↓
Slope
  ↓
Aspect
  ↓
Flow direction
  ↓
Flow accumulation
```

## Requirements
1. Acquire DEM tiles covering each city AOI.
2. Preserve the original DEM.
3. Mosaic tiles where necessary.
4. Reproject into an appropriate metric CRS.
5. Clip to the city AOI.
6. Perform hydrological sink/pit filling.
7. Generate slope, aspect, flow direction, and flow accumulation.
8. Preserve and record original spatial resolution.
9. Do NOT claim that resampling a coarse DEM creates genuine higher-resolution terrain information.
10. Store complete metadata.

## Suggested Libraries
- GDAL
- Rasterio
- NumPy
- PySheds

## Outputs
```text
data/terrain/<city>/
├── dem.tif
├── dem_filled.tif
├── slope.tif
├── aspect.tif
├── flow_direction.tif
├── flow_accumulation.tif
└── metadata.json
```

## Agent Prompt
Build a reproducible DEM acquisition and preprocessing pipeline for SIH26085.

Cities: Mumbai, Delhi, Chennai.

Primary source: ISRO/NRSC CartoDEM.
Fallback: Copernicus DEM or SRTM.

Acquire DEM coverage for each AOI, mosaic tiles when required, reproject into a suitable metric CRS, clip to the AOI, perform hydrological sink filling, and generate elevation, slope, aspect, flow direction, and flow accumulation rasters.

Use Rasterio/GDAL/NumPy and PySheds or an equivalent hydrological library.

Preserve original resolution and clearly distinguish source resolution from any resampled output.

Generate metadata containing source, product, resolution, CRS, acquisition date, processing steps, and file paths.

Directory: `data/terrain/<city>/`

Make the pipeline reproducible through configuration rather than hardcoded paths or coordinates.
