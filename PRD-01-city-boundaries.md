# PRD-01 — City Boundary & Geospatial Base

## Objective
Create standardized geographic boundaries and buffered Areas of Interest (AOIs) for Mumbai, Delhi, and Chennai. These AOIs will be used to crop and align all subsequent datasets.

## Cities
- Mumbai
- Delhi
- Chennai

## Sources
- OpenStreetMap: https://www.openstreetmap.org/
- Prefer authoritative/open administrative boundary sources where available.

## Requirements
1. Obtain administrative boundaries for all three cities.
2. Convert boundaries to EPSG:4326.
3. Create configurable 5 km and 10 km buffered AOIs.
4. Validate geometries.
5. Store bounding boxes.
6. Record source and acquisition date.
7. Do not hardcode coordinates unless absolutely necessary.

## Outputs
```text
data/boundaries/
├── mumbai.geojson
├── delhi.geojson
├── chennai.geojson
└── metadata.json
```

## Metadata
Record:
- city
- source
- acquisition_date
- CRS
- bounding_box
- geometry_area
- buffer_distance

## Agent Prompt
Build a reproducible Python geospatial data acquisition module for SIH26085.

Obtain authoritative/open administrative boundaries for Mumbai, Delhi and Chennai. Convert them to EPSG:4326, create configurable 5 km and 10 km buffered AOIs, validate geometries, and save GeoJSON outputs.

Generate metadata containing source, acquisition date, CRS, bounding box, geometry area and processing steps.

Use a configuration file rather than hardcoding coordinates.

Directory: `data/boundaries/`
