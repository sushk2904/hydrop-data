# PRD-03 — OpenStreetMap Road & Urban Infrastructure Dataset

## Objective
Acquire the public urban street and infrastructure network needed to construct the surface graph and later generate a synthetic drainage network.

## Source
OpenStreetMap:
https://www.openstreetmap.org/

Use OSMnx / Overpass-compatible methods for programmatic acquisition.

## Required Layers
### Roads
- motorway
- trunk
- primary
- secondary
- tertiary
- residential
- service
- living street
- other relevant drivable roads

### Network features
- intersections
- junctions
- road geometry

### Additional useful features
- buildings
- waterways
- canals
- mapped drains
- bridges
- culverts
- relevant land-use
- railway
- major infrastructure

## Requirements
1. Acquire data for Mumbai, Delhi, and Chennai AOIs.
2. Preserve OSM feature IDs where available.
3. Convert road network into a NetworkX graph.
4. Save GraphML.
5. Save GIS-friendly GeoJSON layers.
6. Keep an EPSG:4326 interchange version.
7. Create projected metric copies for spatial calculations.
8. Record acquisition timestamp.
9. Do not assume OSM drainage information is complete.
10. Clearly distinguish observed OSM infrastructure from synthetic infrastructure generated later.

## Outputs
```text
data/osm/<city>/
├── roads.graphml
├── roads.geojson
├── intersections.geojson
├── buildings.geojson
├── waterways.geojson
├── canals_drains.geojson
└── metadata.json
```

## Agent Prompt
Build an OpenStreetMap acquisition pipeline for SIH26085 using OSMnx and Overpass-compatible methods.

Cities: Mumbai, Delhi, Chennai.

Acquire the drivable road network, road geometry, intersections, buildings, waterways, canals/drains where mapped, bridges, culverts and relevant land-use/infrastructure features.

Preserve OSM IDs where possible. Convert the road network into a NetworkX graph and save GraphML. Also export GIS layers as GeoJSON.

Maintain EPSG:4326 interchange files and projected metric copies for calculations. Record the OSM acquisition timestamp.

Do not represent OSM-mapped drains as the complete municipal drainage network. The actual drainage model will be explicitly labelled synthetic.

Directory: `data/osm/<city>/`
