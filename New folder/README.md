<div align="center">

# 🌍 Geo-Intel AI Pipeline: LULC & Hydrology Engine

### AI/ML-Powered Land Use Classification, Digital Terrain Modeling & Drainage Network Design
**Problem Statement 2 — MoPR × IITTNiF National Geospatial Intelligence Hackathon**

[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://python.org)
[![scikit-learn](https://img.shields.io/badge/ML-Random%20Forest-F7931E?logo=scikit-learn&logoColor=white)](https://scikit-learn.org/)
[![WhiteboxTools](https://img.shields.io/badge/Hydrology-WhiteboxTools-2E7D32)](https://www.whiteboxgeo.com/)
[![Rasterio](https://img.shields.io/badge/GIS-Rasterio%20|%20GeoPandas-FFC107)](https://rasterio.readthedocs.io/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

---

*Transform raw drone LiDAR point clouds into presentation-ready Land Use/Land Cover (LULC) maps and engineering-grade drainage infrastructure plans — fully automated, data-fused, and GIS-ready.*

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
- [Usage Pipelines](#-usage-pipelines)
  - [Pipeline 1: Full End-to-End (LiDAR → Drainage Design)](#pipeline-1-full-end-to-end-lidar--drainage-design)
  - [Pipeline 2: Hydrology-Only (DTM → Flow Analysis)](#pipeline-2-hydrology-only-dtm--flow-analysis)
  - [Pipeline 3: LULC Classification (nDSM + Intensity → LULC Map)](#pipeline-3-lulc-classification-ndsm--intensity--lulc-map)
  - [Pipeline 4: Overlay & Visualisation](#pipeline-4-overlay--visualisation)
- [How It Works — Technical Deep Dive](#-how-it-works--technical-deep-dive)
  - [Phase 1: LiDAR Ingestion & Base Topography](#phase-1-lidar-ingestion--base-topography)
  - [Phase 2: Hydrological Modeling & Hotspots](#phase-2-hydrological-modeling--hotspots)
  - [Phase 3: Automated LULC Classification via ML](#phase-3-automated-lulc-classification-via-ml)
  - [Phase 4: Drainage Network Design](#phase-4-drainage-network-design)
- [Output Files Reference](#-output-files-reference)
- [Villages & CRS Configuration](#-villages--crs-configuration)
- [Performance & Scalability](#-performance--scalability)
- [Acknowledgements](#-acknowledgements)

---

## 🎯 Problem Statement

> **PS2**: *Conceptualize and develop a data-driven Digital Terrain Model (DTM) using drone point cloud datasets, leveraging Artificial Intelligence/Machine Learning (AI/ML). Delineate natural surface-water flow paths and low-lying zones, predict waterlogging hotspots, and design drainage networks for densely inhabited village Abadi areas.*
>
> — Ministry of Panchayati Raj (MoPR) & IIT Tirupati NiF, Geo-Intel Lab

### Key Deliverables Met
| # | Deliverable | Status |
|:--|:---|:---:|
| 1 | AI model for precise ground & off-ground element classification | ✅ Done |
| 2 | High-fidelity DTM & DSM generation from LiDAR data | ✅ Done |
| 3 | LULC Mapping (Residential, Agricultural, Water, Roads) | ✅ Done |
| 4 | Delineation of natural surface water flow paths | ✅ Done |
| 5 | Waterlogging & inundation hotspot prediction | ✅ Done |
| 6 | Detailed engineering drainage network design | ✅ Done |

---

## 🔍 What This Project Does

This comprehensive pipeline takes **raw, unstructured 3D laser point clouds** captured by drones over Indian villages and fully automates the creation of structural, geospatial, and hydrological insights:

1. **Topographic Modeling**: Renders a clean Digital Terrain Model (DTM) and Digital Surface Model (DSM), filtering out physical objects like trees and vehicles using machine learning.
2. **LULC Classification**: Extracts distinct land classes (Residential, Agricultural, Water bodies, Roads) using an intelligent Random Forest classifier on derived spatial features (nDSM and Intensity).
3. **Hydrological Simulation**: Simulates rainwater routing using WhiteboxTools, mapping exactly where water flows, pathways it takes, and sinks where it accumulates.
4. **Flood Hotspot Data Fusion**: Directly fuses hydrology-detected sink depth arrays into the LULC Classification to override and perfectly map exact water bodies.
5. **Drainage Infrastructure Engineering**: Generates an actionable and geometrically-accurate canal network specifying width, depth, and flow velocity using the Rational Method and Manning's Equation.
6. **Publication-Ready Visualization**: Creates detailed, styled plots and interactive maps.

---

## 🏗 System Architecture

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                       Geo-Intel Multi-Modal Engine                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│ ┌──────────────────────────┐    ┌──────────────────────────┐                │
│ │ 1. DTM/Drainage Pipeline │    │ 2. Hydrology Tuner       │                │
│ │ (dtm_drainage_pipeline.py│    │ (colab_hydrology_.py)    │                │
│ │ ───────────────────────  │    │ ───────────────────────  │                │
│ │ Extracts base DTM from   │    │ Rapid re-iteration of    │                │
│ │ point clouds using RF    │    │ stream properties using  │                │
│ │ classifiers.             │    │ WhiteboxTools.           │                │
│ └───────┬──────────────────┘    └───────┬──────────────────┘                │
│         │                               │                                   │
│         ▼                               ▼                                   │
│ ┌──────────────────────────────────────────────────────────┐                │
│ │               3. LULC Auto-Classifier                    │                │
│ │               (lulc_pipeline.py)                         │                │
│ │ ──────────────────────────────────────────────────────── │                │
│ │  INPUT: DTM + DSM + Intensity + Waterlogging Rasters     │                │
│ │  1. Computes nDSM (Normalized Digital Surface Model)     │                │
│ │  2. Combines Intensity profiles for material detection   │                │
│ │  3. Generates Synthetic labels based on logic rules      │                │
│ │  4. Trains Random Forest for classification              │                │
│ │  5. OVERRRIDES Water bodies using Phase 2 outputs        │                │
│ └───────┬──────────────────────────────────────────────────┘                │
│         │                                                                   │
│         ▼                                                                   │
│ ┌──────────────────────────────────────────────────────────┐                │
│ │               4. Overlay Visualiser                      │                │
│ │               (overlay_visualiser.py)                    │                │
│ │ ──────────────────────────────────────────────────────── │                │
│ │  Generates HTML maps, folium layers, and presentation    │                │
│ │  ready multi-panel plots of the village topography.      │                │
│ └──────────────────────────────────────────────────────────┘                │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🧰 Technology Stack

| Category | Technology | Purpose |
|:---|:---|:---|
| **Python Core** | `Python 3.10+` | Core execution and logic chaining |
| **Machine Learning** | `scikit-learn` | Terrain generation & LULC prediction (`RandomForestClassifier`) |
| **Spatial Engines** | `WhiteboxTools`, `laspy` | Raw point cloud iteration and hydrological simulations |
| **Raster Operations** | `rasterio`, `SciPy` | nDSM matrix arrays, alignments, and continuous surface interpolators |
| **Vector Geometry** | `GeoPandas`, `Shapely` | Exporting vector layouts, hotspot polygons, geometries |
| **Dashboards / Vis** | `matplotlib`, `Folium` | High-definition charts and portable HTML interactive maps |

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.9+** (tested up to 3.11)
- At least **12 GB memory** (optimized to handle memory through chunk allocation)
- Raw input format: `.las` or `.laz` files.

### Installation

For either local or Colab environment setup:
```bash
pip install laspy[lazrs] geopandas rasterio scipy scikit-learn \
            matplotlib numpy pandas shapely tqdm joblib whitebox folium
```

### Directory Structure

```plaintext
workspace/
├── README.md                          ← You are here
├── dtm_drainage_pipeline.py           ← Topography base setup & point cloud ingestion
├── colab_hydrology_pipeline.py        ← Hydrological sandbox
├── lulc_pipeline.py                   ← ML-based Land Use / Land Cover mapping (NEW!)
├── overlay_visualiser.py              ← Plot renderer and report generators
│
├── <State Name>_Point_Cloud/          ← Data Dirs containing LAS/LAZ
└── outputs/                           ← Processed outputs per village
    └── VILLAGE_NAME_ID/
        ├── ...DTM.tif
        ├── ...LULC.tif
        └── ...DrainageDesign.gpkg
```

---

## 📖 Usage Pipelines

### Pipeline 1: Full End-to-End (LiDAR → Drainage Design)

Converts point clouds to raw raster layers (DTM, streams, etc.).
```bash
python dtm_drainage_pipeline.py [VILLAGE_NAME]
```

### Pipeline 2: Hydrology-Only (DTM → Flow Analysis)

Allows threshold/parameter testing on existing Topographic Data.
```bash
python colab_hydrology_pipeline.py [VILLAGE_NAME]
```

### Pipeline 3: LULC Classification (nDSM + Intensity → LULC Map)

The **new** classification pipeline runs Random Forest to classify the village into semantic segments. It extracts bounding boxes, generates a Normalized Digital Surface Model (nDSM), trains models based on physical properties iteratively, and generates the mapping overlay.

```bash
python lulc_pipeline.py
```
*Note: This relies on the core topographical output (.dtm, .dsm, .intensity, .waterlogging) already existing in the outputs folder.*

### Pipeline 4: Overlay & Visualisation

Renders beautiful dark-themed analytical plots and HTML map applications.
```bash
python overlay_visualiser.py [VILLAGE_NAME]
```

---

## 🧬 How It Works — Technical Deep Dive

### Phase 1: LiDAR Ingestion & Base Topography
Instead of crashing standard systems on massive point cloud reads, the core parser iterates `laspy` files chunk-by-chunk. It creates:
- **DTM (Bare Earth)** using ground-classification ML.
- **DSM (Surface Level)** using native WhiteboxTools LIDAR rendering.
- **Intensity Profiles** parsing spectral signatures based on object return reflections.

### Phase 2: Hydrological Modeling & Hotspots
Rasters undergo `d8_pointer` flow directives and `breach_depressions` to accurately model rural village topography without artifacts. Key feature outputs include Stream delineations, Catchments, and critical *Waterlogging Hotspot Depths*.

### Phase 3: Automated LULC Classification via ML
The **LULC Pipeline (`lulc_pipeline.py`)** extracts 4 critical classes via an optimized `RandomForestClassifier` (100-Trees, balanced class weights):
1. **nDSM Extraction:** Calculates the difference between the surface model (DSM) and terrain (DTM). Large values correlate to buildings/structures.
2. **Feature Generation:** Matches intensity and layout against height. High reflection on flat ground = Roads. Medium reflection = Agriculture.
3. **Auto-Training:** Synthetically creates a dynamic 100k-point sample using empirical heuristic bounds to act as a pre-training label set, vastly boosting class distinctiveness automatically.
4. **Data Fusion for Water Bodies:** Directly super-imposes the *Waterlogging Hotspot* geometries gathered from hydrologic equations to classify the "Water" category exactly matching ground truth physics, eliminating ML hallucinations in flat terrains.

### Phase 4: Drainage Network Design
Every stream extracted by the water models is given **civil engineering traits**: Rational Method peaking flow rate, Trapezoidal structure estimates, and velocity parameters.

---

## 📦 Output Files Reference

For each village, all artifacts are dumped to `outputs/{village_name}/`:

**Topographical Core:**
* `{name}_DTM.tif`, `{name}_DSM.tif`, `{name}_Intensity.tif`

**Hydrology Insights:**
* `{name}_FlowAccumulation.tif`, `{name}_WaterloggingHotspots.gpkg`, `{name}_Catchments.tif`
* `{name}_DrainageDesign.gpkg` *(Primary Engineering Deliverable)*

**Classification Outputs:**
* `{name}_LULC.tif` *(Raster map of classes {1:Res, 2:Agri, 3:Water, 4:Roads})*
* `{name}_LULC_Map.png` *(Colorized plot for presentation)*

**Presentation Layouts:**
* `{name}_interactive_map.html`, `{name}_Summary.png`

---

## 🗺 Villages & CRS Configuration

The pipeline automatically auto-projects standard geographic degrees into appropriate metric UTM grids. Handled EPSGs include Gujarat/Punjab/Rajasthan (32643 - 43N), Tamil Nadu (32644 - 44N), and Andaman/Nicobar (32646 - 46N).

---

## ⚡ Performance & Scalability

* **Chunk/Batch Iterations:** LAS clouds processed at 1M points per RAM buffer sweep preventing Colab OOM locks.
* **Algorithm Caching:** The Whitebox framework binds fast compiled-rust methods instead of slow Pythonic math vectors.
* **Compression Vectors:** Every final Raster is output with `LZW` encodings (Cloud Optimized GeoTIFF).
* **Multi-Node Joblib Allocation:** Random Forests split trees concurrently (`n_jobs=-1`).

---

## 🏆 Acknowledgements

- **Ministry of Panchayati Raj (MoPR)** — For providing the village drone survey datasets.
- **IIT Tirupati NiF — Geo-Intel Lab** — For organizing the National AI/ML Geospatial Hackathon.
- **WhiteboxTools** by Prof. John Lindsay — Open-source geospatial analysis engine.
- **scikit-learn** — Machine learning framework.

---

<div align="center">

*Built with ❤️ for rural India's infrastructure.*

**MoPR × IITTNiF National Geospatial Intelligence Hackathon — Problem Statement 2**

</div>
