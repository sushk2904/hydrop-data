# PRD-10 — Dataset Manifest, Provenance & Reproducibility

## Objective
Make the entire SIH26085 data collection process reproducible and auditable.

Every downloaded/generated dataset must have provenance metadata.

## Required Metadata
- dataset name
- city
- source
- source URL
- product/version
- acquisition timestamp
- original filename
- local filename
- original CRS
- processed CRS
- original resolution
- processed resolution
- processing steps
- script version/commit where possible
- license/usage information
- checksum where practical

## Master Manifest
Create:

```text
data/manifest.csv
```

Recommended fields:

```text
dataset_id
city
dataset_type
source
source_url
product
version
acquired_at
original_resolution
processed_resolution
original_crs
processed_crs
file_path
checksum
license
status
notes
```

## Source Registry
Create:

```text
SOURCES.md
```

with links to:
- ISRO/NRSC Bhuvan
- Copernicus DEM
- NASA GPM IMERG
- OpenStreetMap
- IMD
- any additional source actually used

## Agent Prompt
Build a provenance and dataset-manifest system for SIH26085.

Every acquisition and processing script must register its output in `data/manifest.csv` and include source, URL, product/version, acquisition timestamp, CRS, resolution, processing steps, license and file path.

Create `SOURCES.md` and `DATA_DICTIONARY.md`.

Do not fabricate source URLs or licenses. Preserve the exact source used for each dataset.

The goal is that another developer can clone the repository, inspect the manifest, understand where every dataset came from, and reproduce the preprocessing pipeline.
