# Google Colab Hydrology Pipeline (Phase 3 & 4)

This guide explains how to run the highly memory-optimized Hydrology Pipeline (`colab_hydrology_pipeline.py`) directly inside Google Colab. 

This pipeline is specifically designed to circumvent Google Colab's strict 12GB RAM limit by utilizing **WhiteboxTools**, which processes massive DTM (Digital Terrain Model) rasters out-of-core (chunk-by-chunk directly on the disk) rather than loading everything into memory.

## 🚀 Features
* **Memory Safe**: Easily processes huge village DTMs under 12GB RAM.
* **Road Breaching**: Simulates culverts through raised roads instead of treating them like dams.
* **Vector Smoothing**: Applies Douglas-Peucker simplification to remove jagged raster edges from exported stream networks.
* **Waterlogging Hotspots**: Calculates true Topographic Wetness Index (TWI) combining slope and catchment area.
* **Catchment Delineation**: Automatically finds outlets (pour points) and maps the drainage basin.

---

## 🛠️ Step-by-Step Instructions for Google Colab

### Step 1: Open a New Colab Notebook
Go to [Google Colab](https://colab.research.google.com/) and create a new notebook.

### Step 2: Mount your Google Drive
In your first Colab cell, paste and run the following code to connect your Google Drive to the Colab session. It will ask for permission to access your files.

```python
from google.colab import drive
drive.mount('/content/drive')
```

### Step 3: Install Required Libraries
In the next cell, install the necessary spatial packages:

```bash
!pip install whitebox geopandas rasterio shapely
```

### Step 4: Verify your File Paths and Add Project Folder to Path
To allow Colab to successfully import and run your custom scripts stored in Google Drive, you need to append your project folder's path to the system path. In a new cell, run:

```python
import sys
# Replace 'path_to_your_project_folder' with your actual folder path (e.g., 'model')
sys.path.append('/content/drive/MyDrive/path_to_your_project_folder')
```

Ensure your `DEVDI_511671_DTM.tif` (or whatever your DTM is named) is located in your Google Drive. 
For example, if it's in a folder called `model/outputs/` in the root of your Google Drive, the path in Colab will be `/content/drive/MyDrive/model/outputs/`.

### Step 5: Run the Pipeline Script
You have two ways to run the script:

**Option A: Run the `.py` file directly**
If you uploaded `colab_hydrology_pipeline.py` to your Drive (e.g., inside the `model/` folder), you can run it via magic commands:
```bash
# Change directory to where the script is located in your Google Drive
%cd /content/drive/MyDrive/model

# Run the script using the full path
!python /content/drive/MyDrive/model/colab_hydrology_pipeline.py
```
*(Make sure to edit the `colab_hydrology_pipeline.py` file to set `WORK_DIR='/content/drive/MyDrive/model/outputs'` and `INPUT_DTM="your_dtm_name.tif"` before running!)*

**Option B: Copy-Paste the code into a cell (Recommended)**
Open a new code block, paste the entire contents of `colab_hydrology_pipeline.py` into the cell. 

Before hitting run, scroll to the bottom of the cell to the `EXECUTION BLOCK FOR COLAB` and update your paths:
```python
# ==========================================
# 🚀 EXECUTION BLOCK FOR COLAB
# ==========================================
# Point this to where your DTM is stored in your Google Drive
WORK_DIR = '/content/drive/MyDrive/model/outputs' 
INPUT_DTM = "DEVDI_511671_DTM.tif" # Change this to your village's DTM name
```
Then run the cell!

---

## 📂 Expected Output Files
Once the script completes, it will generate the following files inside your `WORK_DIR`:

1. `*_BreachedDTM.tif`: The hydrologically corrected terrain model where roads have been breached.
2. `*_FDir.tif`: D8 Flow Direction raster.
3. `*_FAcc.tif`: D8 Flow Accumulation raster.
4. `*_RasterStreams.tif`: The extracted stream network as pixels.
5. `*_VectorStreams_Clean.geojson`: The smoothed, vector-format stream lines (open this in QGIS/ArcGIS).
6. `*_Slope.tif`: Terrain slope in degrees.
7. `*_TWI_Waterlogging.tif`: Hotspot map showing areas prone to waterlogging.
8. `*_Catchments.tif`: Polygon map of the discrete drainage basins.

## ⚠️ Troubleshooting
* **Error: No CRS found in DTM!** -> Your point cloud was not projected. Make sure the DTM generation script exports the TIF with an EPSG code (e.g., `EPSG:32643` for Gujarat).
* **Colab runs out of disk space:** WhiteboxTools creates temporary files. If processing all 10 villages, you might need to process 1 or 2 at a time, download the outputs, and clear your Colab environment.
* **No streams extracted:** The accumulation threshold is too high for your specific village size. Find the `step3_stream_extraction_and_smoothing` call at the bottom of the script and lower `threshold=1000` to `threshold=500` or `100`.
