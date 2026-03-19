================================================================================
PS2 – DTM Creation + Drainage Network Design (Gujarat)
MoPR Hackathon | IIT Tirupati NIF | Geo-Intel Lab
================================================================================


WHAT THIS PIPELINE DOES
================================================================================

Gujarat Point Cloud (DEVDI & KHAPRETA villages)
       |
       v
 Load ground points only (ASPRS Class 2)
 Subsample to 500K points to fit in Colab RAM
       |
       v
 DTM Generation (Nearest-neighbour interpolation -> GeoTIFF)
       |
       v
 Hydrological Analysis (pysheds)
 +-- Flow Direction (D8)
 +-- Flow Accumulation
 +-- Stream Extraction
 +-- Waterlogging Hotspot Detection
       |
       v
 Drainage Network Design
 (Strahler order, slope, Manning's equation -> channel dimensions)
       |
       v
 GIS Outputs (GeoTIFF + GeoJSON) + Summary figure


FOLDER STRUCTURE
================================================================================

project/
+-- Gujrat_Point_Cloud/
|   +-- DEVDI_POINT CLOUD (511671).las
|   +-- KHAPRETA_510206.laz
+-- outputs/                              <-- all outputs written here
+-- Ps2_Gujarat_dtm_drainage_pipeline.py
+-- readme_Gujarat.txt


GOOGLE COLAB – STEP-BY-STEP INSTRUCTIONS
================================================================================

STEP 1 – Upload files to Google Drive
--------------------------------------
Upload the following to your Google Drive (inside My Drive/model/):

  My Drive/
  +-- model/
      +-- Gujrat_Point_Cloud/
      |   +-- DEVDI_POINT CLOUD (511671).las
      |   +-- KHAPRETA_510206.laz
      +-- Ps2_Gujarat_dtm_drainage_pipeline.py

NOTE: The two point-cloud files are large (~1.87 GB and ~1.62 GB).
      Upload may take time depending on your internet speed.


STEP 2 – Open a new Colab notebook
--------------------------------------
Go to https://colab.research.google.com/ -> New Notebook


STEP 3 – Cell 1: Mount Drive & Install libraries
--------------------------------------

    from google.colab import drive
    drive.mount('/content/drive')

    !pip install laspy[lazrs] pysheds geopandas rasterio scipy \
                 scikit-learn matplotlib numpy pandas \
                 shapely tqdm joblib -q

Wait for install to finish (1-2 minutes).


STEP 4 – Cell 2: Setup & Import
--------------------------------------

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


STEP 5 – Cell 3: Run the pipeline (Village 1 – DEVDI)
--------------------------------------

    CONFIG["dtm_resolution"]    = 2.0         # 2.0m to save RAM
    CONFIG["max_ground_points"] = 500_000     # subsample to fit in Colab RAM
    CONFIG["dtm_interp"]        = "nearest"   # nearest = low RAM
    os.makedirs(CONFIG["output_dir"], exist_ok=True)

    result_devdi = run_pipeline_memory_efficient(
        "./Gujrat_Point_Cloud/DEVDI_POINT CLOUD (511671).las",
        "DEVDI_511671"
    )


STEP 6 – Cell 4: Run the pipeline (Village 2 – KHAPRETA)
--------------------------------------

    result_khapreta = run_pipeline_memory_efficient(
        "./Gujrat_Point_Cloud/KHAPRETA_510206.laz",
        "KHAPRETA_510206"
    )

TIP: Each village is processed independently. If Colab runs out of RAM,
     try increasing dtm_resolution to 3.0 or reducing max_ground_points
     to 300,000.


STEP 7 – Cell 5: Check outputs
--------------------------------------

    for f in sorted(os.listdir("./outputs")):
        size_mb = os.path.getsize(f"./outputs/{f}") / 1e6
        print(f"  {f}  ({size_mb:.1f} MB)")


STEP 8 – Cell 6: DTM accuracy (optional – only if you have GCPs)
--------------------------------------

    # For DEVDI
    metrics_devdi = evaluate_dtm_accuracy(
        "./outputs/DEVDI_511671_DTM.tif",
        "./data/DEVDI_GCPs.csv"       # CSV with columns: x, y, z_true
    )

    # For KHAPRETA
    metrics_khapreta = evaluate_dtm_accuracy(
        "./outputs/KHAPRETA_510206_DTM.tif",
        "./data/KHAPRETA_GCPs.csv"    # CSV with columns: x, y, z_true
    )


OUTPUT FILES (per village)
================================================================================

  <village>_DTM.tif                       Digital Terrain Model (GeoTIFF)
  <village>_FlowAccumulation.tif          Flow accumulation raster
  <village>_WaterloggingDepth.tif         Predicted waterlogging depth (m)
  <village>_Streams.geojson               Extracted stream/drainage network
  <village>_WaterloggingHotspots.geojson  Polygon zones of waterlogging risk
  <village>_DrainageDesign.geojson        Stream network + design parameters
  <village>_Summary.png                   4-panel summary figure

Where <village> is DEVDI_511671 or KHAPRETA_510206.


KEY DESIGN PARAMETERS IN DrainageDesign.geojson
================================================================================

  strahler_ord      Strahler stream order (1-5)
  slope_m_m         Channel bed slope (m/m)
  peak_flow_m3s     Peak discharge (Rational Method, m3/s)
  channel_width_m   Recommended channel top width (m)
  channel_depth_m   Recommended channel depth (m)
  velocity_m_s      Flow velocity (Manning's n=0.025)


CONFIG TWEAKS
================================================================================

  dtm_resolution      2.0m (default) -> 0.5m (higher detail, needs more RAM)
  max_ground_points   500K (default) -> increase if you have more RAM
  flow_acc_threshold  Lower = more streams; raise for large village
  depression_depth_m  Sensitivity for waterlogging (0.2-0.5m)
  epsg                32643 (UTM Zone 43N for Gujarat) - change if needed


CONTACT
================================================================================
MoPR Hackathon | geointel.mopr@iittnif.com
