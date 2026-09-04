# PRD-04 — GPM IMERG Rainfall Dataset

## Objective
Create a reproducible rainfall ingestion pipeline for Mumbai, Delhi, and Chennai using NASA GPM IMERG.

IMERG is intended as the initial accessible rainfall source and as a fallback/supplement to the eventual IMD Doppler Weather Radar ingestion layer.

## Sources

NASA GPM IMERG:
https://gpm.nasa.gov/data/imerg

NASA GES DISC IMERG Early Run:
https://disc.gsfc.nasa.gov/datasets/GPM_3IMERGHHE_07/summary

NASA GPM Data Directory:
https://gpm.nasa.gov/data/directory

## Dataset Characteristics
- 30-minute precipitation products
- Near-real-time Early Run
- Historical Final Run
- Approximately 0.1° spatial resolution for IMERG
- Multiple machine-readable formats depending on product/access route

## Intended Use
### Early Run
Near-real-time prototype / rainfall forcing.

### Final Run
Historical event replay and validation.

## Requirements
1. Acquire rainfall data covering each city AOI.
2. Support configurable historical date ranges.
3. Download only required spatial/temporal coverage where practical.
4. Extract precipitation values correctly according to the selected product.
5. Clip rainfall fields to the city AOI.
6. Preserve UTC timestamps.
7. Store product/version metadata.
8. Export GeoTIFF and optionally NetCDF/HDF5 as appropriate.
9. Maintain a manifest for every acquired rainfall field.
10. Do not treat IMERG's spatial resolution as street-level rainfall resolution.

## Outputs
```text
data/rainfall/IMERG/<city>/
├── YYYYMMDD_HHMM.tif
└── ...

data/rainfall/IMERG/
└── manifest.csv
```

## Manifest Fields
```text
city
timestamp_utc
source
product
version
file_path
units
spatial_resolution
processing_status
```

## Agent Prompt
Build a reproducible GPM IMERG rainfall ingestion pipeline for SIH26085.

Cities: Mumbai, Delhi, Chennai.

Use NASA GPM IMERG products. Support the near-real-time Early Run and historical Final Run through configuration.

Acquire 30-minute precipitation data covering each city's AOI, spatially clip it, preserve UTC timestamps, validate units, and store product/version metadata.

Export machine-readable rainfall fields and create a manifest.csv containing city, timestamp, source, product, version, file path, units, spatial resolution, and processing status.

Do not artificially upscale IMERG and claim that the resulting raster contains true street-level rainfall information.

Directory: `data/rainfall/IMERG/<city>/`
