# PRD-07 — Synthetic Urban Drainage Network

## Objective
Generate a mathematically plausible urban drainage network because the actual municipal underground drainage topology is not assumed to be publicly available.

This network must be explicitly labelled **synthetic** and must never be represented as the real municipal network.

The research document proposes generating the network from OSM street topology and DEM elevation, then producing an EPA-SWMM-compatible `.inp` file.

## Inputs
- OSM road/intersection graph
- Hydrologically corrected DEM
- Flow accumulation
- City AOI

## Pipeline
```text
OSM roads
    ↓
Intersections
    ↓
Drainage nodes
    ↓
DEM elevation
    ↓
Downstream direction
    ↓
Catchment area
    ↓
Synthetic pipes
    ↓
Pipe parameters
    ↓
SWMM .inp
```

## Node Attributes
- node_id
- latitude
- longitude
- elevation
- catchment_area
- downstream_node
- surface_type where available

## Edge/Pipe Attributes
- pipe_id
- upstream_node
- downstream_node
- length
- slope
- diameter
- Manning roughness
- estimated capacity

## Requirements
1. Generate candidate drainage nodes from appropriate road intersections.
2. Sample ground elevation from the processed DEM.
3. Determine plausible downstream flow direction.
4. Avoid creating obvious elevation cycles.
5. Estimate upstream catchment area.
6. Assign configurable pipe parameters.
7. Calculate hydraulic capacity.
8. Generate SWMM-compatible input.
9. Preserve provenance of every synthetic parameter.
10. Clearly label assumptions.

## Outputs
```text
data/drainage/<city>/
├── nodes.geojson
├── pipes.geojson
├── drainage.graphml
├── network.inp
├── parameters.json
└── README.md
```

## Agent Prompt
Build a synthetic urban drainage network generator for SIH26085.

Inputs:
- OSM road/intersection graph
- hydrologically corrected DEM
- flow accumulation
- city AOI

Create synthetic drainage nodes at suitable intersections, sample elevation from the DEM, determine plausible downstream directions, estimate catchment areas, create directed pipe edges, assign configurable Manning roughness and pipe dimensions, calculate hydraulic capacity, and generate an EPA-SWMM-compatible `.inp` file.

The network must be explicitly labelled synthetic. Never describe it as the actual municipal drainage network.

Store all node and pipe attributes plus provenance and assumptions.

Directory: `data/drainage/<city>/`.
