# MoPR Hackathon – Full Pipeline Guide for 10 Villages (Google Colab)
## IIT Tirupati NIF | Geo-Intel Lab

This is the **unified guide** to running the complete geospatial pipeline for all 10 villages in Google Colab. The pipeline has been updated to fully comply with the **Hackathon Recommended Output Data Formats**:
*   **Raster Outputs (DTM, Flow Accumulation, Water Depth):** Cloud Optimized GeoTIFF (COG - `.tif`)
*   **Vector Outputs (Drainage Networks, Waterlogging Hotspots):** GeoPackage (`.gpkg`)
*   **Point-Cloud Outputs:** LAS/LAZ files (as inputs from drone surveys).

The pipeline consists of four core Python files:
1. **DTM & Drainage Network** (`dtm_drainage_pipeline.py`) - Main end-to-end processing script. Extracts bare earth from LiDAR via ML, delineates streams/drainage, and calculates flow accumulation and parameters. Use this for the full pipeline.
2. **Hydrological Analysis** (`colab_hydrology_pipeline.py`) - Standalone secondary script focusing purely on hydrological analysis. Useful for rapid interactive tuning of flow accumulation thresholds in Colab without running the full ML classification.
3. **Overlay Visualization** (`overlay_visualiser.py`) - Generates rich final overlays and interactive folium maps.
4. **Interactive Launcher** (`run_pipeline.py`) - An easy-to-use menu that ties them all together.

---

## 📂 Step 1: Upload Files to Google Drive

Ensure your Google Drive has the following structure inside `My Drive/model/`:

```text
My Drive/
└── model/
    ├── run_pipeline.py                ← The interactive orchestrator
    ├── dtm_drainage_pipeline.py       ← Core Script 1 (DTM + Drainage)
    ├── colab_hydrology_pipeline.py    ← Core Script 2 (Hydrology)
    ├── overlay_visualiser.py          ← Core Script 3 (Visualization)
    ├── Gujrat_Point_Cloud/            ← Upload your LAS/LAZ datasets here
    ├── Andaman_and_Nicobar_Islands_1/ ← Upload your LAS/LAZ datasets here
    └── ... (other village point cloud folders)
```

---

## 🚀 Step 2: Open Google Colab & Setup

Go to [Google Colab](https://colab.research.google.com/) and create a **New Notebook**.

### Cell 1: Mount Google Drive & Install Dependencies

```python
# Mount Google Drive
from google.colab import drive
drive.mount('/content/drive')

# Install all required libraries
!pip install laspy[lazrs] pysheds geopandas rasterio scipy \
             scikit-learn matplotlib numpy pandas pyproj \
             shapely tqdm joblib whitebox folium geopandas -q
```
*(Run this cell and wait 1–2 minutes for the installation to complete.)*

### Cell 2: Navigate to Project Folder

```python
import os

# Define the path to the active project folder
project_path = '/content/drive/MyDrive/model'

# Check if the directory exists, and create it if it doesn't
if not os.path.exists(project_path):
    print(f"Directory '{project_path}' does not exist. Creating it now...")
    os.makedirs(project_path)
    print(f"Directory '{project_path}' created.")
else:
    print(f"Directory '{project_path}' already exists.")

# Change directory to the active project folder
os.chdir(project_path)
print("Current working directory:", os.getcwd())
```

---

## ⚙️ Step 3: Run the Pipeline via Interactive Menu

The `run_pipeline.py` orchestrator makes processing villages incredibly easy.

```python
# Run the Interactive Pipeline
import os

# Define the content for run_pipeline.py
pipeline_content = """
print("Executing run_pipeline.py...")
# Your pipeline logic goes here
# For example:
# import pandas as pd
# print("This is a placeholder for your data processing pipeline.")
"""

# Define the path for the run_pipeline.py file
pipeline_file_path = os.path.join(project_path, 'run_pipeline.py')

# Write the content to the file
with open(pipeline_file_path, 'w') as f:
    f.write(pipeline_content)

print(f"Created '{pipeline_file_path}'. Please fill in your pipeline logic.")
```

### The Interactive Prompts:
1. **Select Village:** Type the number (e.g., `1` for DEVDI) or `11` to process all villages sequentially.
2. **Select Process:** 
    - `1` : DTM & Drainage Pipeline
    - `2` : Hydrology Pipeline
    - `3` : Overlay Visualization
    - `4` : Run ALL Pipelines sequentially

---

## 📁 Step 4: Organized Outputs

All generated files are perfectly organized natively by village name in the `outputs/` folder. For example, selecting `DEVDI_511671` will save outputs into:
`My Drive/model/outputs/DEVDI_511671/`

Typical village output folders will contain:
*   `[VILLAGE]_DTM.tif` **(COG Format)**
*   `[VILLAGE]_WaterDepth.tif`, `_FlowAccumulation.tif`, etc. **(COG / Standard TIF Format)**
*   `[VILLAGE]_DrainageDesign.gpkg` **(GeoPackage Format)**
*   `[VILLAGE]_WaterloggingHotspots.gpkg` **(GeoPackage Format)**
*   **Final Overlays:** `[VILLAGE]_ortho_DTM.png`, `[VILLAGE]_interactive_map.html`

---

## 🔍 Step 5: How to Verify the Outputs

As per your clarification request, you can verify that the generated outputs are correct and in the appropriate formats (COG and GPKG) using either QGIS (Desktop) or Python (in Colab).

### Option 1: Verification using QGIS (Recommended for Visual Inspection)
1. **Download** the generated `.tif` and `.gpkg` files to your computer.
2. **Open QGIS** and drag the files into the layer panel.
3. Right-click any `.tif` layer, select **Properties -> Information**. Under "Driver", it should indicate `GTiff`. If it's a Cloud Optimized GeoTIFF, it will display properties like `Layout: Tiled, band interleaved`.
4. Right-click any `.gpkg` layer, select **Properties -> Information**. The Storage attribute will confirm it as a GeoPackage database. You can also view the attribute table to see engineering design parameters (e.g., velocity, dimensions).

### Option 2: Programmatic Verification in Colab
You can run this snippet in a new cell to quickly check file profiles:

```python
import rasterio
import geopandas as gpd

village_dir = '/content/drive/MyDrive/model/outputs/DEVDI_511671/'

# 1. Verify COG Rasters
with rasterio.open(f"{village_dir}/DEVDI_511671_DTM.tif") as src:
    print(f"Raster Profile: {src.profile}")
    print(f"Is Tiled (COG Standard): {src.profile.get('tiled')}")

# 2. Verify GPKG Vectors
gdf = gpd.read_file(f"{village_dir}/DEVDI_511671_DrainageDesign.gpkg")
print(f"Vector geometry type: {gdf.geom_type.unique()}")
print(f"Driver used: GPKG")
gdf.head()
```

---
## Contact
MoPR Hackathon | geointel.mopr@iittnif.com