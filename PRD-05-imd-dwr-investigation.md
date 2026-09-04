# PRD-05 — IMD Doppler Weather Radar Investigation

## Objective
Investigate and document a legitimate machine-readable route for obtaining Indian Doppler Weather Radar (DWR) data covering Mumbai, Delhi, and Chennai.

This is a production-oriented integration investigation. It must not block the initial prototype, which can use GPM IMERG.

## Reference
India Meteorological Department:
https://mausam.imd.gov.in/

## Target Cities
- Mumbai
- Delhi
- Chennai

## Requirements
Determine for each city:
1. Which official IMD radar products cover the area.
2. Whether data is available as:
   - API
   - downloadable files
   - raster
   - radar imagery
   - reflectivity
   - precipitation products
3. Authentication requirements.
4. Update frequency.
5. Temporal resolution.
6. Spatial resolution.
7. File/data formats.
8. Whether automated programmatic access is permitted.
9. Whether historical radar data is accessible.
10. Any rate limits or usage restrictions.

## Important Constraints
- Prefer official IMD sources.
- Do not fabricate endpoints.
- Do not bypass authentication.
- Do not aggressively scrape pages.
- Clearly distinguish public visualization from machine-readable data.
- If no reliable public machine-readable feed is available, document that limitation.

## Output
```text
data/metadata/imd_dwr_access.md
```

## Required Report Structure
```text
# IMD DWR Access Investigation

## Mumbai
## Delhi
## Chennai

For each:
- Radar/product
- Coverage
- Format
- Resolution
- Update interval
- Historical availability
- API/download method
- Authentication
- Usage restrictions
- Confidence
- Recommended integration approach

## Prototype Recommendation
State whether IMD DWR should be:
- integrated now
- integrated later
- replaced by a documented fallback
```

## Agent Prompt
Investigate official IMD Doppler Weather Radar data access for Mumbai, Delhi and Chennai.

Identify actual publicly accessible radar products, machine-readable formats, APIs/download mechanisms, spatial and temporal resolution, update frequency, historical availability, authentication and usage restrictions.

Do not fabricate API endpoints. Do not bypass authentication or access restrictions. Distinguish public radar visualizations from actual downloadable/machine-readable datasets.

Produce `data/metadata/imd_dwr_access.md`.

If reliable machine-readable access cannot be established, explicitly mark IMD DWR as a later production integration and do not let it block the initial prototype based on GPM IMERG.
