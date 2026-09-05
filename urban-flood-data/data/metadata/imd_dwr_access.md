# IMD DWR Access Investigation — Mumbai Metropolitan Region

**Document Version:** 1.1.0  
**Project:** SIH26085 — Urban Flood Nowcasting  
**Target City:** Mumbai, Maharashtra  
**Date:** 2026-09-05  
**Author:** Antigravity (Senior ML & Hydro-Informatics Engineer)  
**Status:** Completed (Mumbai Consolidated)

---

## Executive Summary

This investigation evaluates official machine-readable Doppler Weather Radar (DWR) data from the India Meteorological Department (IMD) specifically for the **Mumbai Metropolitan Region**. While IMD operates high-precision S-band dual-polarization radar (Colaba) alongside BMC's X-band/C-band municipal network, official public access is currently restricted to pre-rendered raster imagery (GIF/PNG via Mausam / Meghdoot web portals). No open, machine-readable binary API (e.g., UF, MDV, NetCDF-4/HDF5, or CfRadial) is publicly accessible without institutional MoU or registered research credentials.

Consequently, for the SIH26085 Mumbai prototype, **NASA GPM IMERG Early/Late Run (0.1° / 30-min resolution)** and calibrated ground weather station feeds serve as the primary operational rainfall input, while an architecture adapter is prepared for IMD DWR ingestion upon institutional credential clearance.

---

## Radar Inventory & Coverage Analysis: Mumbai

- **Radar Stations:**
  - **Mumbai Colaba (S-band):** 2.7–3.0 GHz, Peak Power ~750 kW, max range 500 km (surveillance) / 250 km (precipitation).
  - **Mumbai Veravali / BMC Radar (X-band / C-band network):** Municipal dual-pol installation for high-resolution micro-urban precipitation.
- **Geographic Coverage:** Full coverage of Mumbai Island City, Mumbai Suburban, Thane, Navi Mumbai, Raigad, and coastal Konkan belt (18.5°N–19.5°N, 72.5°E–73.5°E).
- **Available Products (Public Web):**
  - PPI (Plan Position Indicator) - Reflectivity (Z)
  - Max (Maximum Reflectivity - dBZ)
  - PAC (Precipitation Accumulation 1hr, 3hr, 24hr)
  - SRI (Surface Rainfall Intensity - mm/hr)
  - VVP (Volume Velocity Processing - Wind profile)
- **Format:**
  - Public web: 8-bit color-mapped PNG / animated GIF images.
  - Raw archive (internal): Universal Format (UF), IRIS (SIGMET/Vaisala), and CfRadial / HDF5.
- **Resolution:**
  - Spatial: 250m to 500m range-bin resolution (raw); ~1 km equivalent on public web render.
  - Temporal: 10 to 15-minute volume scans.
- **Update Interval:** 10 minutes during monsoon/active convective regimes; 15 minutes routine.
- **Historical Availability:** Archived internally at IMD Pune and IMD New Delhi. Not directly downloadable via web without written request / NDC (National Data Centre) data purchase.
- **API / Download Method:** No public REST API or machine-readable GeoTIFF/NetCDF feed. URLs on `mausam.imd.gov.in` are static image endpoints with query timestamp parameters.
- **Authentication:** Public web images require no auth; raw Level-II volume scan access requires institutional credentials / MoES National Data Centre registration.
- **Usage Restrictions:** Attribution required; commercial re-dissemination prohibited without IMD license.
- **Confidence Level:** High for radar existence and physics parameters; Low for immediate raw programmatic API access without MoU.
- **Recommended Integration Approach:** Ingest GPM IMERG 0.1° 30-min raster as primary feed. Provide an image-processing OCR / colormap calibration adapter for public radar PNGs as a secondary cross-validation heuristic.

---

## Comparative Assessment Table

| Metric | Mumbai (Colaba S-band) | NASA GPM IMERG (Operational Fallback) |
| :--- | :--- | :--- |
| **Sensor Type** | S-band Dual-Polarization Ground Radar | Dual-frequency Precipitation Radar + Passive Microwave Constellation |
| **Quantitative Range** | 250 km radius | Global (60°N–60°S) continuous coverage |
| **Spatial Resolution** | 250 m – 1 km range-bin | ~10 km (0.1° × 0.1° gridded) |
| **Temporal Resolution**| 10–15 minutes | 30 minutes |
| **Data Format** | IRIS / CfRadial / Web PNG | HDF5 / NetCDF4 / GeoTIFF |
| **Machine API** | ❌ No Open API (MoU required) | ✅ Open (NASA Earthdata / OPeNDAP) |
| **Historical Archive** | Closed / Formal NDC purchase | ✅ 2000–Present open download |

---

## Prototype Recommendation

> [!IMPORTANT]
> **Decision: Integrate Later in Production; Use Documented Fallback for Initial Prototype.**

1. **Immediate Prototype:**
   - Use **NASA GPM IMERG (Early / Late Run)** via NASA Earthdata for operational precipitation inputs over Mumbai.
   - Use synthetic storm profiles (e.g., Latin Hypercube Sampling parameter sweeps in Stage 07) for stress-testing Mumbai's hydraulic drainage network.
2. **Production Roadmap (Phase 2):**
   - Execute formal MoU with IMD / MoES under academic/government research protocols to obtain real-time Level-II volume scan streams (CfRadial / NetCDF4 via FTP/S3) from Colaba radar.
   - Implement Py-ART (Python ARM Radar Toolkit) or `wradlib` decoder for conversion of radar reflectivity ($Z$) to rainfall rate ($R$) via Marshall-Palmer ($Z = 200 R^{1.6}$) and dual-pol $K_{DP}/Z_{DR}$ relations.
3. **No-Blocker Clause:**
   - Under no circumstances should the lack of official IMD DWR machine-readable credentials block the SIH26085 simulation, modeling, and deep learning pipeline for Mumbai.
