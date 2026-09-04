# PRD-08 — Land Surface & Runoff Parameters

## Objective
Create a configurable land-surface classification and runoff-parameter layer to estimate how rainfall becomes surface runoff.

## Candidate Surface Classes
- buildings
- roads
- paved/commercial areas
- residential areas
- vegetation
- open land
- water
- other/unknown

## Approach
Use available OSM/land-use information and, where appropriate, openly available land-cover data.

Do not claim that assumed runoff coefficients are measured municipal parameters.

## Configuration
Store coefficients separately:

```text
config/runoff_coefficients.yaml
```

Example structure:
```yaml
building: 0.90
road: 0.95
commercial: 0.90
residential: 0.75
vegetation: 0.30
open_land: 0.40
```

These values are initial model assumptions and must remain configurable.

## Outputs
```text
data/surface/<city>/
├── landcover.geojson
├── runoff_coefficient.tif
└── metadata.json
```

## Agent Prompt
Build a land-surface/runoff parameter pipeline for SIH26085.

Use available OSM and openly available land-cover information to classify surfaces into buildings, roads, paved/commercial, residential, vegetation, open land, water and unknown.

Generate a spatial runoff coefficient layer.

Keep runoff coefficients in `config/runoff_coefficients.yaml` rather than hardcoding them into processing code.

Clearly distinguish observed land-cover data from model assumptions.

Record source, resolution, CRS, acquisition date and processing steps.

Directory: `data/surface/<city>/`.
