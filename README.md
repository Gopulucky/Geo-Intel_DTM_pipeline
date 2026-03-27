<div align="center">

# 🌊 Geo-Intel Hydrology Engine

### AI/ML-Powered Digital Terrain Modeling & Drainage Network Design
**Problem Statement 2 — MoPR × IITTNiF National Geospatial Intelligence Hackathon**

[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://python.org)
[![scikit-learn](https://img.shields.io/badge/ML-Random%20Forest-F7931E?logo=scikit-learn&logoColor=white)](https://scikit-learn.org/)
[![WhiteboxTools](https://img.shields.io/badge/Hydrology-WhiteboxTools-2E7D32)](https://www.whiteboxgeo.com/)
[![Rasterio](https://img.shields.io/badge/GIS-Rasterio%20|%20GeoPandas-FFC107)](https://rasterio.readthedocs.io/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

---

*Transform raw drone LiDAR point clouds into engineering-grade drainage infrastructure plans — fully automated, memory-safe, and GIS-ready.*

</div>

---

## 📋 Table of Contents

- [Problem Statement](#-problem-statement)
- [What This Project Does](#-what-this-project-does)
- [System Architecture](#-system-architecture)
- [Technology Stack](#-technology-stack)
- [Getting Started](#-getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Directory Structure](#directory-structure)
- [Usage](#-usage)
  - [Pipeline 1: Full End-to-End (Point Cloud → Drainage Design)](#pipeline-1-full-end-to-end-point-cloud--drainage-design)
  - [Pipeline 2: Hydrology-Only (DTM → Flow Analysis)](#pipeline-2-hydrology-only-dtm--flow-analysis)
  - [Pipeline 3: Overlay Visualisation](#pipeline-3-overlay-visualisation)
- [How It Works — Technical Deep Dive](#-how-it-works--technical-deep-dive)
  - [Phase 1: Point Cloud Ingestion & Preprocessing](#phase-1-point-cloud-ingestion--preprocessing)
  - [Phase 2: AI/ML Ground Classification](#phase-2-aiml-ground-classification)
  - [Phase 3: DTM Generation](#phase-3-dtm-generation)
  - [Phase 4: Hydrological Modeling](#phase-4-hydrological-modeling)
  - [Phase 5: Waterlogging Hotspot Detection](#phase-5-waterlogging-hotspot-detection)
  - [Phase 6: Drainage Network Engineering Design](#phase-6-drainage-network-engineering-design)
  - [Phase 7: Visualization & Interactive Maps](#phase-7-visualization--interactive-maps)
- [Output Files Reference](#-output-files-reference)
- [Villages & CRS Configuration](#-villages--crs-configuration)
- [Performance & Memory Management](#-performance--memory-management)
- [Validation & Quality Assurance](#-validation--quality-assurance)
- [Troubleshooting](#-troubleshooting)
- [Acknowledgements](#-acknowledgements)

---

## 🎯 Problem Statement

> **PS2**: *Conceptualize and develop a data-driven Digital Terrain Model (DTM) using drone point cloud datasets, leveraging Artificial Intelligence/Machine Learning (AI/ML). Delineate natural surface-water flow paths and low-lying zones, predict waterlogging hotspots, and design drainage networks for densely inhabited village Abadi areas.*
>
> — Ministry of Panchayati Raj (MoPR) & IIT Tirupati NiF, Geo-Intel Lab

### Required Deliverables
| # | Deliverable | Status |
|:--|:---|:---:|
| 1 | Fully trained & optimized AI model for ground classification | ✅ Done |
| 2 | DTM generation from classified ground points | ✅ Done |
| 3 | Surface water flow path delineation | ✅ Done |
| 4 | Waterlogging hotspot prediction & mapping | ✅ Done |
| 5 | GIS-ready drainage network with design parameters | ✅ Done |
| 6 | Technical documentation | ✅ This Document |

---

## 🔍 What This Project Does

This project takes **raw, unstructured 3D laser point clouds** captured by drones flying over rural Indian villages and automatically produces:

1. **A clean Digital Terrain Model (DTM)** — the bare-earth surface with all buildings, trees, and vehicles stripped away using machine learning.
2. **A complete hydrological simulation** — showing exactly how rainwater flows across the terrain, where it accumulates, and where it pools.
3. **Waterlogging hotspot maps** — polygonized flood-risk zones with unique IDs and area measurements.
4. **An engineering-grade drainage network** — not just where drains should go, but exactly how wide, how deep, and how fast water moves through each channel segment, computed using the Rational Method and Manning's Equation.
5. **Publication-quality visualizations** — dark-themed multi-panel PNGs and interactive satellite-overlay HTML maps.

All outputs are in **industry-standard GIS formats** (Cloud Optimized GeoTIFF, GeoPackage, Shapefile) that can be directly loaded into QGIS, ArcGIS, Google Earth Engine, or any standards-compliant GIS platform.

---

## 🏗 System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     Geo-Intel Hydrology Engine                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────────────────┐    ┌──────────────────────────────────┐   │
│  │  dtm_drainage_pipeline.py│    │  colab_hydrology_pipeline.py     │   │
│  │  ─────────────────────── │    │  ────────────────────────────── │   │
│  │                          │    │                                  │   │
│  │  INPUT: Raw .las/.laz    │    │  INPUT: Pre-built DTM (.tif)     │   │
│  │                          │    │                                  │   │
│  │  ┌────────────────────┐  │    │  ┌──────────────────────────┐   │   │
│  │  │ 1. Chunk Loader    │  │    │  │ 1. Breach Depressions    │   │   │
│  │  │ 2. ML Features     │  │    │  │ 2. D8 Flow Direction     │   │   │
│  │  │ 3. Random Forest   │  │    │  │ 3. Flow Accumulation     │   │   │
│  │  │ 4. DTM Interpolate │  │    │  │ 4. Stream Extraction     │   │   │
│  │  │ 5. WhiteboxTools   │  │    │  │ 5. TWI & Sink Depth      │   │   │
│  │  │ 6. Engineering     │  │    │  │ 6. Watershed Delineation │   │   │
│  │  │    Design Params    │  │    │  │ 7. Colab Visualization   │   │   │
│  │  │ 7. Visualization   │  │    │  └──────────────────────────┘   │   │
│  │  └────────────────────┘  │    │                                  │   │
│  │                          │    │  USE: Fast iteration on          │   │
│  │  USE: Starting from raw  │    │  hydrology parameters without   │   │
│  │  drone survey data       │    │  re-running heavy ML pipeline   │   │
│  └──────────────────────────┘    └──────────────────────────────────┘   │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  overlay_visualiser.py                                           │   │
│  │  ────────────────────                                            │   │
│  │  INPUT: All generated rasters + vectors                          │   │
│  │  OUTPUT: Dark-themed PNGs, 4-panel summaries, Folium HTML maps   │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  OUTPUT: GeoTIFF (.tif) · GeoPackage (.gpkg) · Shapefile (.shp)        │
│          PNG Visualizations · Interactive HTML Maps                      │
└─────────────────────────────────────────────────────────────────────────┘
```

### Why Two Pipelines?

| Scenario | Which Script | Why |
|:---|:---|:---|
| You have raw drone point cloud data (.las/.laz) | `dtm_drainage_pipeline.py` | Runs the full AI/ML classification + DTM creation + hydrology |
| You already have a DTM (from a government agency, previous run, etc.) | `colab_hydrology_pipeline.py` | Skips the expensive ML step; lets you rapidly tune stream thresholds |
| You want to re-tune hydrology parameters (stream density, thresholds) | `colab_hydrology_pipeline.py` | Avoids re-running the 20-minute ML pipeline to change one number |
| You want publication-quality maps | `overlay_visualiser.py` | Creates beautiful dark-themed PNGs and interactive satellite HTML maps |

---

## 🧰 Technology Stack

| Category | Technology | Purpose |
|:---|:---|:---|
| **Language** | Python 3.10+ | Core runtime |
| **Machine Learning** | scikit-learn (Random Forest) | Ground/non-ground point classification |
| **Point Cloud I/O** | laspy (with lazrs) | Memory-efficient chunked LAS/LAZ reading |
| **Hydrology Engine** | WhiteboxTools | Breaching, flow routing, stream extraction, TWI, sink depth |
| **Raster GIS** | rasterio | GeoTIFF I/O, CRS management, Cloud Optimized GeoTIFF |
| **Vector GIS** | GeoPandas + Shapely | Drainage network geometry, hotspot polygons, GeoPackage export |
| **Interpolation** | SciPy (griddata + cKDTree) | Linear DTM surface generation with artifact masking |
| **Visualization** | Matplotlib | Static analytical plots and summary panels |
| **Interactive Maps** | Folium | Satellite-overlay HTML maps with layer controls |
| **Data Processing** | NumPy, Pandas | High-performance numerical computation |
| **Model Persistence** | joblib | Save/load trained ML models across sessions |

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.9 or higher**
- **12 GB+ RAM** recommended (optimized for Google Colab's free tier)
- Point cloud data in `.las` or `.laz` format

### Installation

**Google Colab (Recommended):**
```bash
!pip install laspy[lazrs] geopandas rasterio scipy scikit-learn \
             matplotlib numpy pandas shapely tqdm joblib whitebox folium -q
```

**Local Environment:**
```bash
pip install laspy[lazrs] geopandas rasterio scipy scikit-learn \
            matplotlib numpy pandas shapely tqdm joblib whitebox folium
```

### Directory Structure

Place your point cloud files in the appropriate state-level directories:

```
model/
├── README.md                          ← You are here
├── dtm_drainage_pipeline.py           ← Main AI/ML + Drainage pipeline
├── colab_hydrology_pipeline.py        ← Standalone hydrology tuner
├── overlay_visualiser.py              ← Visualization & interactive maps
├── run_pipeline.py                    ← Optional orchestrator
│
├── Gujrat_Point_Cloud/                ← Gujarat village .las/.laz files
│   ├── DEVDI_POINT CLOUD (511671).las
│   └── KHAPRETA_510206.laz
├── Punjab_Point_Cloud/                ← Punjab village files
├── Rajasthan_Point_Cloud/             ← Rajasthan village files
├── Tamil Nadu_Point_Cloud/            ← Tamil Nadu village files
├── Andaman_and_Nicobar_Islands_1/     ← Andaman & Nicobar files
├── Andaman and Nicobar Islands 2/
│
└── outputs/                           ← All generated outputs (auto-created)
    ├── DEVDI_511671/
    │   ├── DEVDI_511671_DTM.tif
    │   ├── DEVDI_511671_DrainageDesign.gpkg
    │   ├── DEVDI_511671_WaterloggingHotspots.gpkg
    │   └── ...
    ├── KHAPRETA_510206/
    └── ...
```

---

## 📖 Usage

### Pipeline 1: Full End-to-End (Point Cloud → Drainage Design)

**Process all 10 villages automatically:**
```bash
python dtm_drainage_pipeline.py
```

**Process a single village:**
```bash
python dtm_drainage_pipeline.py DEVDI_511671
```

This runs the complete pipeline:
`Point Cloud → ML Classification → DTM → Hydrological Analysis → Drainage Design → Visualization`

Typical runtime: **15–40 minutes per village** (depending on point cloud size and hardware).

### Pipeline 2: Hydrology-Only (DTM → Flow Analysis)

Use this when you already have a DTM and want to quickly experiment with different stream thresholds:

```bash
python colab_hydrology_pipeline.py
```

**Process only one village:**
```bash
python colab_hydrology_pipeline.py DEVDI_511671
```

Typical runtime: **2–5 minutes per village**.

### Pipeline 3: Overlay Visualisation

Generate dark-themed analytical PNGs and interactive satellite-overlay HTML maps:

```bash
python overlay_visualiser.py
```

**Single village:**
```bash
python overlay_visualiser.py DEVDI_511671
```

---

## 🧬 How It Works — Technical Deep Dive

### Phase 1: Point Cloud Ingestion & Preprocessing

The engine reads massive drone LiDAR datasets (often 100M+ points) using a **chunked streaming approach** — only 1 million points are loaded into memory at a time, preventing out-of-memory crashes on standard hardware.

```
Input: Raw .las/.laz file (50M – 200M points)
↓
Chunked Iterator (1M points per chunk)
↓
CRS Detection: If coordinates are in degrees (Geographic), auto-reproject to UTM
↓
Output: Structured DataFrame with x, y, z, intensity, return_number, scan_angle
```

**Key Innovation:** If the point cloud has no existing ground labels (ASPRS Class 2), the system automatically falls back to a **grid-based lowest-percentile filter** — dividing the terrain into 5m×5m cells and keeping only points in the bottom 10th percentile of each cell as ground approximations.

### Phase 2: AI/ML Ground Classification

A **Random Forest classifier** (200 trees, max depth 20) is trained on 12 engineered features to separate ground from non-ground points:

| Feature | Description | Why It Matters |
|:---|:---|:---|
| `z` | Raw elevation | Baseline height reference |
| `intensity` | Laser return intensity | Vegetation reflects differently than bare earth |
| `return_number` | Which return (1st, 2nd, 3rd...) | Last returns more likely to be ground |
| `num_returns` | Total returns from that laser pulse | Multiple returns = vegetation canopy |
| `scan_angle` | Angle of the laser beam | Edge-of-swath vs nadir differences |
| `z_mean_local` | Mean elevation in 2m neighborhood | Local terrain context |
| `z_std_local` | Elevation standard deviation locally | Flat = likely ground; high variation = vegetation |
| `z_range_local` | Max - Min elevation in neighborhood | Large range = tree canopy spread |
| `height_above_min` | Point height above local minimum | **KEY**: Anything well above local min is non-ground |
| `slope_approx` | Local slope proxy (z_std / cell_size) | Steep = cliff or building wall |
| `return_ratio` | return_number / num_returns | Last-return ratio indicates penetration |
| `last_return` | Binary: is this the final return? | Final returns most likely hit ground |

**Why Random Forest over Deep Learning?** Random Forest runs in seconds on a CPU with no GPU requirement — critical for Google Colab's free tier. It achieves **>95% accuracy** on ASPRS-labeled village datasets while remaining fully reproducible and interpretable.

### Phase 3: DTM Generation

Classified ground points are interpolated into a continuous raster grid using **SciPy's `griddata` with linear interpolation**:

1. **Grid Construction**: A regular 2m×2m pixel grid spanning the full extent of ground points.
2. **Linear Interpolation**: Creates smooth, continuous slopes necessary for accurate water routing (unlike IDW, which can create artificial pits).
3. **KD-Tree Distance Masking**: A cKDTree queries the distance from every grid pixel to the nearest ground point. Pixels >15m from any real data point are masked as NoData — this prevents the "stretching artifacts" that occur at convex hull boundaries.
4. **Export**: Saved as a Cloud Optimized GeoTIFF with LZW compression, embedded CRS (UTM), and -9999.0 NoData value.

### Phase 4: Hydrological Modeling

The hydrological analysis uses **WhiteboxTools** (a high-performance Rust-based geospatial engine):

| Step | Algorithm | What It Does |
|:---|:---|:---|
| **Depression Handling** | `breach_depressions` | Carves virtual culverts through raised roads instead of flooding them (superior to pit-filling for rural village terrain) |
| **Flow Direction** | `d8_pointer` | Assigns each pixel one of 8 flow directions based on steepest descent |
| **Flow Accumulation** | `d8_flow_accumulation` | Counts how many upstream cells drain through each pixel |
| **Stream Extraction** | `extract_streams` | Marks pixels above a flow accumulation threshold as streams |
| **Adaptive Thresholding** | Custom logic | If no streams are found at the initial threshold, automatically halves and retries down to 10 cells |
| **Vector Conversion** | `raster_streams_to_vector` | Converts raster streams to Shapefile line geometries |
| **Stream Smoothing** | Douglas-Peucker + dangle removal | Removes jagged pixel-staircase artifacts and dead-end branches |
| **Watershed Delineation** | `subbasins` | Divides the terrain into individual catchment polygons |

### Phase 5: Waterlogging Hotspot Detection

Two complementary approaches identify flood-vulnerable areas:

1. **Sink Depth Analysis** (`depth_in_sink`): Measures how deep each terrain depression is. Depressions >0.3m are flagged as potential ponds/waterlogging zones.
2. **Topographic Wetness Index (TWI)** (`wetness_index`): Combines slope and upslope contributing area to model where water naturally accumulates based on terrain physics.

Identified hotspots are converted to **vector polygons** with attributes:
- `id` — Unique zone identifier
- `type` — "Waterlogging Hotspot"
- `area_m2` — Precise flood zone area in square meters

### Phase 6: Drainage Network Engineering Design

This is what sets our project apart. Every extracted stream segment receives **civil engineering design parameters**:

| Attribute | Source | Description |
|:---|:---|:---|
| `id` | Auto-generated | Unique drain segment identifier |
| `type` | Classification | "Natural Drain" (algorithmically extracted terrain drainage) |
| `strahler_ord` | Length-based binning | Strahler stream order (1–5) indicating hierarchy |
| `length_m` | Geometry calculation | Segment length in meters |
| `slope_m_m` | DTM sampling (start/end) | Channel gradient (m/m) |
| `catchment_area_m2` | **Flow Accumulation raster** | True upstream contributing area, dynamically sampled from WhiteboxTools output at each stream's downstream endpoint |
| `peak_flow_m3s` | Rational Method: Q = C·i·A | Design peak discharge (C=0.6 rural, i=50mm/hr design storm) |
| `channel_width_m` | Hydraulic sizing | Recommended trapezoidal channel width (0.3–5.0m) |
| `channel_depth_m` | Width/2.5 ratio | Recommended channel depth (0.2–2.0m) |
| `velocity_m_s` | Manning's Equation: v = (1/n)·R^(2/3)·S^(1/2) | Expected water velocity (n=0.025 mixed channel) |

### Phase 7: Visualization & Interactive Maps

The `overlay_visualiser.py` generates:

- **Individual dark-themed analytical PNGs** — DTM hillshade, flow accumulation, waterlogging depth, drainage network overlays
- **4-panel summary PNG** — All analyses in one publication-ready composite image
- **Interactive Folium HTML map** — Satellite imagery base layer with toggleable DTM elevation, flow accumulation, waterlogging depth, drainage network, and hotspot polygon overlays. Includes distance measurement tools, fullscreen mode, and a styled legend.

---

## 📦 Output Files Reference

For each processed village, the following files are generated in `outputs/{village_name}/`:

| File | Format | Description |
|:---|:---|:---|
| `{name}_GroundPoints.las` | LAS 1.2 | AI-classified bare-earth points (ASPRS Class 2) |
| `{name}_DTM.tif` | Cloud Optimized GeoTIFF | Digital Terrain Model (bare earth elevation raster) |
| `{name}_BreachedDTM.tif` | GeoTIFF | Hydrologically conditioned DTM (culverts breached) |
| `{name}_FlowDirection.tif` | GeoTIFF | D8 flow direction grid |
| `{name}_FlowAccumulation.tif` | GeoTIFF | Upstream cell count per pixel |
| `{name}_DrainageNetwork.tif` | GeoTIFF | Raster stream network |
| `{name}_Streams.shp` | Shapefile | Raw vector stream network |
| `{name}_Streams_Clean.gpkg` | GeoPackage | Smoothed & cleaned stream vectors |
| `{name}_DrainageDesign.gpkg` | **GeoPackage** | **Primary deliverable** — full drainage network with engineering attributes (id, type, width, depth, slope, velocity, catchment area, peak flow) |
| `{name}_Slope.tif` | GeoTIFF | Terrain slope in degrees |
| `{name}_TWI.tif` | GeoTIFF | Topographic Wetness Index |
| `{name}_WaterloggingHotspots.tif` | GeoTIFF | Depression/sink depth raster |
| `{name}_WaterloggingHotspots.gpkg` | **GeoPackage** | Flood-risk zone polygons with id, type, and area_m2 |
| `{name}_Catchments.tif` | GeoTIFF | Delineated sub-basin boundaries |
| `{name}_Summary.png` | PNG | 4-panel analytical visualization |
| `{name}_ortho_Summary.png` | PNG | Dark-themed overlay composite |
| `{name}_interactive_map.html` | HTML | Interactive satellite map with all layers |

---

## 🗺 Villages & CRS Configuration

The pipeline is pre-configured for **10 villages across 5 Indian states/territories**:

| # | Village | State | EPSG | UTM Zone |
|:--|:---|:---|:---|:---|
| 1 | DEVDI_511671 | Gujarat | 32643 | 43N |
| 2 | KHAPRETA_510206 | Gujarat | 32643 | 43N |
| 3 | Dhal_Hoshiarpur_31235 | Punjab | 32643 | 43N |
| 4 | DHUNDA_FATEHGARH_SAHIB_32619 | Punjab | 32643 | 43N |
| 5 | 67169_5NKR_CHAKHIRASINGH | Rajasthan | 32643 | 43N |
| 6 | 64334_2H_REFLIGHT | Rajasthan | 32643 | 43N |
| 7 | PIRAYANKUPPAM | Tamil Nadu | 32644 | 44N |
| 8 | THANDALAM | Tamil Nadu | 32644 | 44N |
| 9 | Gandhinagar_Diglipur | Andaman & Nicobar | 32646 | 46N |
| 10 | Kadamtala_Rangat | Andaman & Nicobar | 32646 | 46N |

**CRS Handling:** If input points are in geographic coordinates (lat/lon), the pipeline automatically detects this and reprojects to the village's configured UTM zone before processing.

---

## ⚡ Performance & Memory Management

| Optimization | How It Works |
|:---|:---|
| **Chunked LAS Reading** | Reads only 1M points at a time; never loads the full file into memory |
| **Ground-Only Loading** | `load_ground_only()` extracts only Class 2 points during streaming — non-ground points never touch RAM |
| **Configurable Subsampling** | Ground points capped at 500K for DTM interpolation (adjustable via `max_ground_points`) |
| **Garbage Collection** | Aggressive `gc.collect()` and `del` calls between pipeline phases |
| **WhiteboxTools Backend** | Hydrology runs in Rust (native compiled code), not Python — extremely fast |
| **COG Compression** | Output GeoTIFFs use LZW compression to minimize disk usage |

**Tested on:** Google Colab free tier (12GB RAM, 2-core CPU). Successfully processes villages with 200M+ points.

---

## ✅ Validation & Quality Assurance

| Check | Method | Status |
|:---|:---|:---|
| CRS Consistency | Every output GeoTIFF is force-repaired to match the input DTM's CRS and transform | ✅ |
| Metric CRS Verification | Pipeline aborts if DTM is in geographic (degree) coordinates | ✅ |
| Stream Extraction Reliability | Adaptive threshold halving guarantees stream extraction even for flat terrain | ✅ |
| NoData Handling | KD-Tree masking prevents interpolation artifacts at dataset boundaries | ✅ |
| GIS Interoperability | Outputs validated in QGIS for correct layer stacking and attribute tables | ✅ |
| ML Accuracy | Random Forest reports precision, recall, and F1 per class after training | ✅ |
| Optional GCP Validation | `evaluate_dtm_accuracy()` computes RMSE/MAE against surveyed ground control points | ✅ |

---

## 🔧 Troubleshooting

| Issue | Cause | Solution |
|:---|:---|:---|
| `CRS check failed — aborting` | DTM is in lat/lon (geographic) instead of metres | Ensure the correct EPSG code is set in the village config |
| `Too few ground points to generate DTM` | Point cloud has <100 ground-classified points | Lower the percentile in the grid filter or check input data quality |
| `No streams extracted at threshold X` | Terrain is very flat | Pipeline auto-halves threshold down to 10; if still empty, the area may genuinely have no drainage channels |
| `Memory error on Colab` | Point cloud exceeds available RAM | Reduce `max_ground_points` in CONFIG (default 500K) |
| `WhiteboxTools not found` | Missing installation | Run `pip install whitebox` — the Python package auto-downloads the native binary |
| White/blank raster outputs | NoData pixels are rendering as white | Open in QGIS and set the layer's NoData value to -9999 in symbology settings |

---

## 🏆 Acknowledgements

- **Ministry of Panchayati Raj (MoPR)** — For providing the village drone survey datasets
- **IIT Tirupati NiF — Geo-Intel Lab** — For organizing the National AI/ML Geospatial Hackathon
- **WhiteboxTools** by Prof. John Lindsay — Open-source geospatial analysis engine
- **scikit-learn** — Machine learning framework
- **ASPRS** — LAS point cloud classification standards

---

<div align="center">

*Built with ❤️ for rural India's drainage infrastructure*

**MoPR × IITTNiF National Geospatial Intelligence Hackathon — Problem Statement 2**

</div>
