# PRD-09 — Dataset Validation & Quality Control

## Objective
Create automated validation for all datasets before they are passed to the backend/modeling stage.

## Validation Categories

### Geometry
- invalid geometries
- empty geometries
- self-intersections
- duplicate features

### CRS
- expected CRS
- accidental geographic/metric mixing

### Raster
- missing values
- invalid values
- dimensions
- resolution
- bounds
- CRS
- alignment

### Network
- disconnected components
- isolated nodes
- cycles where inappropriate
- impossible slopes
- zero/negative lengths
- invalid pipe parameters

### Rainfall
- timestamp continuity
- missing intervals
- units
- expected spatial coverage
- anomalous values

## Outputs
```text
reports/
├── data_quality_report.md
└── validation.json
```

## Agent Prompt
Build an automated dataset validation framework for SIH26085.

Validate every dataset before it is considered usable by the backend.

Check raster CRS, resolution, bounds, dimensions, NoData and invalid values. Check vector geometry validity and duplicates. Check road/drainage graph connectivity, invalid edges, impossible slopes and invalid pipe parameters. Check rainfall timestamps, missing intervals, units and spatial coverage.

Generate both machine-readable JSON and human-readable Markdown reports.

The validation process must fail loudly for critical errors and warn for non-critical issues.

Directory: `reports/`.
