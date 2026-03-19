# Drone Orthophoto Overlay Pipeline for Google Colab

This repository contains the `overlay_visualiser.py` module to produce high-resolution, alpha-blended overlay visuals of your DTM, Waterlogging, and Drainage networks on top of RGB Drone Orthophotos.

## 🚀 Setting up in Google Colab

Since drone orthophotos are massive in size, this script is designed to safely run within Colab's standard 12GB RAM limit by utilizing `rasterio`'s windowed reading feature.

### 1. Install Required Libraries
Open a new cell at the top of your Colab Notebook and run the following commands to install the necessary spatial libraries:

```bash
!pip install rasterio geopandas folium matplotlib numpy
```

### 2. Mount Google Drive
To access your outputs (DTMs, Hotspots, Geotiffs) and the large orthophotos from your Google Drive without uploading them directly to the Colab session every time, mount your drive:

```python
from google.colab import drive
drive.mount('/content/drive')
```

### 3. Move the Scripts
Ensure both your master pipeline file (`Ps2_Gujarat_dtm_drainage_pipeline.py`) and the newly created `overlay_visualiser.py` are present in your Google Drive folder and imported properly into your Colab environment.

You may need to add your Drive folder to Python's path so it knows where to import `overlay_visualiser.py` from:

```python
import sys
sys.path.append('/content/drive/MyDrive/path_to_your_project_folder')
```

### 4. Code Integration

In your main pipeline code, after the DTM, Streams, and Hotspots have finished exporting successfully, import and call the visualization function:

import os
import sys
import importlib.util
from pathlib import Path

# --- 1. SET PATHS FOR GOOGLE COLAB ---
# Using the Google Drive mount point instead of D:\
model_dir = Path('/content/drive/MyDrive/model')
file_path = model_dir / 'overlay_visualiser.py'

# --- 2. LOAD THE MODULE ---
if file_path.exists():
    print(f"Success: {file_path} found. Attempting manual load...")
    spec = importlib.util.spec_from_file_location("overlay_visualiser", str(file_path))
    overlay_visualiser = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(overlay_visualiser)
    run_overlay_visualisation = overlay_visualiser.run_overlay_visualisation
    print("Module loaded successfully.")
else:
    print(f"Error: {file_path} not found. Please ensure your folder is named 'model' in MyDrive.")

# --- 3. SET VILLAGE AND DATA PATHS ---
village = "DEVDI_511671"

# Paths inside Google Drive
outputs_dir = model_dir / 'outputs'
inputs_dir = model_dir / 'inputs'

dtm_file = outputs_dir / f"{village}_DTM.tif"
ortho_file = inputs_dir / f"{village}_Orthophoto.tif"
streams_file = outputs_dir / f"{village}_Streams.geojson"
hotspot_file = outputs_dir / f"{village}_WaterloggingHotspots.geojson"
output_directory = outputs_dir / 'visualisations'

# --- 4. DIAGNOSTIC: LIST FILES ---
if outputs_dir.exists():
    print(f"\nChecking files in {outputs_dir}:")
    files = os.listdir(outputs_dir)
    for f in files:
        print(f" - {f}")
else:
    print(f"\nError: Folder not found at {outputs_dir}")

# --- 5. RUN VISUALIZATION ---
if not dtm_file.exists():
    print(f"\nSTOP: Cannot find DTM file at: {dtm_file}")
    print("Check if the filename in Drive matches 'DEVDI_511671_DTM.tif' exactly.")
elif 'run_overlay_visualisation' in globals():
    print(f"\nStarting visualization for {village}...")
    run_overlay_visualisation(
        village_name=village,
        dtm_path=str(dtm_file),
        ortho_path=str(ortho_file),
        streams_path=str(streams_file),
        hotspot_path=str(hotspot_file),
        output_dir=str(output_directory),
        epsg=32643,
        export_html=True
    )
    print("Done!")

## ⚠️ Important Colab Notes
1. **RAM Limits**: `overlay_visualiser.py` uses *Windowed Reading*. It only loads the portion of the Orthophoto that matches your DTM's exact bounding box. However, if your DTM itself is unusually large (e.g., >4GB), you could still run into RAM spikes during the matplotlib blending phase. High-RAM runtime is recommended if available.
2. **Missing Files**: The module uses safe fallback measures. If an orthophoto isn't found, it gracefully downgrades to a colored terrain basemap. If `folium` fails to load, the script will print a warning but continue generating the static PNG files without crashing.
3. **Interactive Map**: Your interactive `.html` map will be saved in your `/outputs/visualisations` folder. You can double-click this file from your Google Drive on your computer to open it in a browser, or download it locally. It cannot be viewed directly inside a Colab cell output.
