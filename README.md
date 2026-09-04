# SIH26085 — Urban Flood Nowcasting System
## Data Foundation PRD Package

This package defines the data acquisition, preprocessing, synthetic drainage generation, and validation phase for SIH26085.

## Development Principle

Do not start ML training before the physical/geospatial data foundation is working.

The intended progression is:

```text
City AOI
   ↓
DEM
   ↓
OSM street network
   ↓
Rainfall
   ↓
Hydrological preprocessing
   ↓
Synthetic drainage network
   ↓
SWMM
   ↓
Surface routing
   ↓
Nowcasting
   ↓
Backend
   ↓
ML evaluation/surrogate modelling if justified
```

## Recommended Initial Sprint

Start with **Mumbai only**.

Complete:

1. PRD-01 — City boundary
2. PRD-02 — DEM
3. PRD-03 — OSM
4. PRD-04 — GPM IMERG
5. PRD-09 — Validation
6. PRD-10 — Provenance

Then proceed to:

7. PRD-07 — Synthetic drainage
8. PRD-06 — Historical events
9. PRD-08 — Surface/runoff parameters
10. PRD-05 — IMD DWR integration investigation

## Core Sources

### ISRO / NRSC Bhuvan
https://bhuvan-app3.nrsc.gov.in/data/

### Copernicus DEM
https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM

### NASA GPM IMERG
https://gpm.nasa.gov/data/imerg

### NASA GES DISC IMERG Early Run
https://disc.gsfc.nasa.gov/datasets/GPM_3IMERGHHE_07/summary

### OpenStreetMap
https://www.openstreetmap.org/

### India Meteorological Department
https://mausam.imd.gov.in/

## Important Modelling Constraint

IMERG is a rainfall forcing/fallback source. It must not be presented as genuine street-level rainfall data.

The underground drainage network generated under PRD-07 is synthetic and must not be represented as actual municipal infrastructure.

## Final Data Directory

```text
urban-flood-data/
├── config/
├── data/
│   ├── boundaries/
│   ├── terrain/
│   ├── osm/
│   ├── rainfall/
│   ├── events/
│   ├── drainage/
│   ├── surface/
│   └── metadata/
├── scripts/
├── notebooks/
├── reports/
├── SOURCES.md
└── DATA_DICTIONARY.md
```
