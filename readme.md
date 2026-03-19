# PS2 – DTM Creation + Drainage Network (MoPR Hackathon)
## IIT Tirupati NIF | Geo-Intel Lab

---

## What this pipeline does

```
LAZ point cloud (Gandhinagar Diglipur)
       │
       ▼
 Load ground points only (ASPRS Class 2)
 Subsample to 2M points to fit in RAM
       │
       ▼
 DTM Generation (Linear interpolation → GeoTIFF)
       │
       ▼
 Hydrological Analysis (pysheds)
 ├── Flow Direction (D8)
 ├── Flow Accumulation
 ├── Stream Extraction
 └── Waterlogging Hotspot Detection
       │
       ▼
 Drainage Network Design
 (Strahler order, slope, Manning's equation → channel dimensions)
       │
       ▼
 GIS Outputs (GeoTIFF + GeoJSON)  +  Summary figure
```

---

## Folder Structure

```
project/
├── Andaman_and_Nicobar_Islands_1/
│   └── Gandhinagar_Diglipur_group1_densified_point_cloud.laz
├── outputs/                 ← all outputs written here automatically
├── Ps2 dtm drainage pipeline.py
└── README.md
```

---

## Google Colab – Step-by-Step Instructions

### Step 1 – Upload files to Google Drive

Upload the following to your Google Drive (inside `My Drive/model/`):

```
My Drive/
└── model/
    ├── Andaman_and_Nicobar_Islands_1/
    │   └── Gandhinagar_Diglipur_group1_densified_point_cloud.laz
    └── Ps2 dtm drainage pipeline.py
```

### Step 2 – Open a new Colab notebook

Go to [Google Colab](https://colab.research.google.com/) → **New Notebook**

### Step 3 – Cell 1: Mount Drive & Install libraries

```python
from google.colab import drive
drive.mount('/content/drive')

!pip install laspy[lazrs] pysheds geopandas rasterio scipy \
             scikit-learn matplotlib numpy pandas \
             shapely tqdm joblib -q
```

Wait for install to finish (1–2 minutes).

### Step 4 – Cell 2: Setup & Import

```python
import os, sys, shutil

os.chdir('/content/drive/MyDrive/model')

# Delete old cached copy if it exists
if os.path.exists('ps2_pipeline.py'):
    os.remove('ps2_pipeline.py')

# Auto-detect the pipeline file (handles both old and new filename)
for name in ['Ps2_Gujarat_dtm_drainage_pipeline.py',
             'Ps2 dtm drainage pipeline.py']:
    if os.path.exists(name):
        shutil.copy(name, 'ps2_pipeline.py')
        print(f"Copied: {name}")
        break
else:
    raise FileNotFoundError("Pipeline .py file not found! Upload it to My Drive/model/")

from ps2_pipeline import *
print("Import successful!")
```

### Step 5 – Cell 3: Run the pipeline

```python
CONFIG["dtm_resolution"]    = 2.0         # 2.0m to save RAM (use 0.5 on high-RAM machines)
CONFIG["max_ground_points"] = 500_000     # subsample to fit in Colab RAM
CONFIG["dtm_interp"]        = "nearest"   # nearest = low RAM; use 'linear' if you have more RAM
os.makedirs(CONFIG["output_dir"], exist_ok=True)

result = run_pipeline_memory_efficient(
    "./Andaman_and_Nicobar_Islands_1/Gandhinagar_Diglipur_group1_densified_point_cloud.laz",
    "Gandhinagar_Diglipur"
)
```

The file is read in small chunks (1M points at a time) — never fully loaded into memory. Only ground points are kept, then subsampled to 500K for DTM interpolation.

### Step 6 – Cell 4: Check outputs

```python
for f in sorted(os.listdir("./outputs")):
    size_mb = os.path.getsize(f"./outputs/{f}") / 1e6
    print(f"  {f}  ({size_mb:.1f} MB)")
```

### Step 7 – Cell 5: DTM accuracy (optional – only if you have GCPs)

```python
metrics = evaluate_dtm_accuracy(
    "./outputs/Gandhinagar_Diglipur_DTM.tif",
    "./data/Gandhinagar_Diglipur_GCPs.csv"   # CSV with columns: x, y, z_true
)
```

---

## Output files

| File | Description |
|------|-------------|
| `Gandhinagar_Diglipur_DTM.tif` | Digital Terrain Model (GeoTIFF, float32) |
| `Gandhinagar_Diglipur_FlowAccumulation.tif` | Flow accumulation raster |
| `Gandhinagar_Diglipur_WaterloggingDepth.tif` | Predicted waterlogging depth (m) |
| `Gandhinagar_Diglipur_Streams.geojson` | Extracted stream/drainage network |
| `Gandhinagar_Diglipur_WaterloggingHotspots.geojson` | Polygon zones of waterlogging risk |
| `Gandhinagar_Diglipur_DrainageDesign.geojson` | Stream network + design parameters |
| `Gandhinagar_Diglipur_Summary.png` | 4-panel summary figure |

---

## Key design parameters in DrainageDesign.geojson

| Parameter | Description |
|-----------|-------------|
| `strahler_ord` | Strahler stream order (1–5) |
| `slope_m_m` | Channel bed slope (m/m) |
| `peak_flow_m3s` | Peak discharge (Rational Method, m³/s) |
| `channel_width_m` | Recommended channel top width (m) |
| `channel_depth_m` | Recommended channel depth (m) |
| `velocity_m_s` | Flow velocity (Manning's n=0.025) |

---

## Config tweaks

| Parameter | What to change |
|-----------|---------------|
| `dtm_resolution` | 1.0m (default) → 0.5m (higher detail, needs more RAM) |
| `max_ground_points` | 2M (default) → increase if you have more RAM |
| `flow_acc_threshold` | Lower = more streams; raise for large village |
| `depression_depth_m` | Sensitivity for waterlogging (0.2–0.5m) |
| `epsg` | Must match your LAS coordinate system (32646 for A&N) |

---

## Contact
MoPR Hackathon | geointel.mopr@iittnif.com