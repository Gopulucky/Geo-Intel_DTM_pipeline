import os
import sys
import glob
import numpy as np
import rasterio
from rasterio.vrt import WarpedVRT
from rasterio.enums import Resampling
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
import joblib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import matplotlib.patches as mpatches

# --- 1. SETUP ENVIRONMENT ---
try:
    import whitebox
except ImportError:
    print("Whitebox not found. Please run: pip install whitebox rasterio scikit-learn matplotlib joblib")
    sys.exit(1)

# Set base paths (used by standalone execution only)
BASE_DIR = os.environ.get("BASE_DIR", os.path.abspath(os.path.dirname(__file__)))
OUTPUTS_DIR = os.environ.get("OUTPUTS_DIR", os.path.join(BASE_DIR, "outputs"))
INPUTS_DIR = os.environ.get("INPUTS_DIR", os.path.join(BASE_DIR, "input_data"))

# NOTE: wbt is NOT initialized here at module level.
# Each call to run_lulc_pipeline() creates a fresh instance
# pointed at the correct job output directory.


# --- 2. LULC CORE PIPELINE ---
def read_and_align_raster(target_meta, src_path, resampling=Resampling.bilinear):
    with rasterio.open(src_path) as src:
        with WarpedVRT(src, src_crs=target_meta['crs'], crs=target_meta['crs'], transform=target_meta['transform'], 
                       height=target_meta['height'], width=target_meta['width'],
                       resampling=resampling) as vrt:
            return vrt.read(1)

def create_lulc_features(dtm_path, dsm_path, intensity_path, roughness_path, curvature_path):
    if not all(os.path.exists(p) for p in [dtm_path, dsm_path, intensity_path, roughness_path, curvature_path]):
        return None, None, None, None

    with rasterio.open(dtm_path) as src:
        dtm = src.read(1)
        meta = src.meta.copy()
        nodata = src.nodata if src.nodata is not None else -9999.0
        
    dsm = read_and_align_raster(meta, dsm_path)
    intensity = read_and_align_raster(meta, intensity_path)
    roughness = read_and_align_raster(meta, roughness_path)
    curvature = read_and_align_raster(meta, curvature_path)
    
    ndsm = np.where((dtm != nodata) & (dsm != nodata), dsm - dtm, np.nan)
    valid_mask = (~np.isnan(ndsm)) & (~np.isnan(intensity)) & (~np.isnan(roughness)) & (~np.isnan(curvature)) & (dtm != nodata)
    ndsm[valid_mask] = np.clip(ndsm[valid_mask], 0, None)
    
    features = np.column_stack((ndsm[valid_mask], intensity[valid_mask], roughness[valid_mask], curvature[valid_mask]))
    return features, valid_mask, dtm.shape, meta

def train_lulc_model(X, y, model_out_path):
    print("⏳ Training Random Forest...")
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    clf = RandomForestClassifier(n_estimators=30, max_depth=10, n_jobs=-1, random_state=42, class_weight='balanced')
    clf.fit(X_train, y_train)
    
    y_pred = clf.predict(X_test)
    labels = np.unique(y_test).astype(int)
    class_map = {1: 'Residential', 2: 'Agricultural', 3: 'Water bodies', 4: 'Roads'}
    targets = [class_map.get(lbl, f"Class {lbl}") for lbl in labels]
    print(f"Accuracy: {accuracy_score(y_test, y_pred)*100:.2f}%")
    print(classification_report(y_test, y_pred, labels=labels, target_names=targets))
    
    os.makedirs(os.path.dirname(model_out_path), exist_ok=True)
    joblib.dump(clf, model_out_path)
    return clf

def classify_lulc(clf, features, valid_mask, shape, output_path, meta, waterlogging_path=None):
    predictions = clf.predict(features)
    nodata_val = meta.get('nodata', -9999.0)
    lulc = np.full(shape, nodata_val, dtype=np.float32)
    lulc[valid_mask] = predictions
    
    # Data Fusion: Override Water bodies
    if waterlogging_path and os.path.exists(waterlogging_path):
        print("💧 DATA FUSION: Applying Waterlogging Overrides...")
        water_raster = read_and_align_raster(meta, waterlogging_path)
        actual_water = (water_raster > 0.0) & (water_raster != nodata_val) & ~np.isnan(water_raster)
        valid_actual_water = actual_water & (lulc != nodata_val)
        lulc[valid_actual_water] = 3
        
    meta.update(dtype=rasterio.float32, count=1)
    raw_output_path = output_path.replace(".tif", "_raw.tif")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with rasterio.open(raw_output_path, 'w', **meta) as dst:
        dst.write(lulc.astype(np.float32), 1)
        
    print("⏳ Applying Majority Filter to reduce noise...")
    import whitebox
    wbt = whitebox.WhiteboxTools()
    wbt.set_verbose_mode(False)
    wbt.majority_filter(i=raw_output_path, output=output_path, filterx=5, filtery=5)
    
    if os.path.exists(output_path):
        with rasterio.open(output_path) as src:
            filtered_lulc = src.read(1)
        return filtered_lulc
    else:
        return lulc

def render_colab_lulc_output(lulc, save_path=None):
    fig, ax = plt.subplots(figsize=(10, 8))
    cmap = ListedColormap(['#FF0000', '#2CA02C', '#1F77B4', '#7F7F7F'])
    masked = np.ma.masked_invalid(np.where(lulc == -9999.0, np.nan, lulc))
    ax.imshow(masked, cmap=cmap, vmin=0.5, vmax=4.5)
    
    labels = ['Residential', 'Agricultural', 'Water bodies', 'Roads']
    colors = ['#FF0000', '#2CA02C', '#1F77B4', '#7F7F7F']
    patches = [mpatches.Patch(color=colors[i], label=labels[i]) for i in range(4)]
    ax.legend(handles=patches, bbox_to_anchor=(1.05, 1), loc=2, borderaxespad=0.)
    ax.axis('off')
    plt.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close(fig)

def run_village_lulc(dtm, dsm, intensity, roughness, curvature, out, model_path, waterlog):
    features, valid_mask, shape, meta = create_lulc_features(dtm, dsm, intensity, roughness, curvature)
    if features is None: return
    
    print("⏳ Auto-Generating Training Baseline...")
    if len(features) > 20_000:
        syn_features = features[np.random.choice(len(features), 20_000, replace=False)]
    else:
        syn_features = features.copy()
        
    y = np.full(len(syn_features), 2) # Default Agriculture
    res_mask = syn_features[:, 0] > 3.0
    y[res_mask] = 1 # Residential
    
    water_t = np.percentile(syn_features[~res_mask, 1], 5)
    road_t = np.percentile(syn_features[~res_mask, 1], 90)
    median = np.median(syn_features[~res_mask, 1])
    
    y[~res_mask & (syn_features[:, 1] >= road_t) & (syn_features[:, 1] > median)] = 4 # Roads
    y[~res_mask & (syn_features[:, 1] <= water_t) & (syn_features[:, 1] < median)] = 3 # Water
    
    clf = train_lulc_model(syn_features, y, model_path)
    lulc_result = classify_lulc(clf, features, valid_mask, shape, out, meta, waterlog)
    render_colab_lulc_output(lulc_result, save_path=out.replace(".tif", "_Map.png"))


# --- 3. BULK EXECUTION ---
if __name__ == "__main__":
    wbt = whitebox.WhiteboxTools()
    wbt.set_working_dir(BASE_DIR)
    print("🔍 Scanning for Point Clouds...")
    all_las_files = []
    
    if os.path.exists(INPUTS_DIR):
        all_las_files.extend(glob.glob(os.path.join(INPUTS_DIR, "**", "*.la[sz]"), recursive=True))
        all_las_files.extend(glob.glob(os.path.join(INPUTS_DIR, "**", "*.LA[SZ]"), recursive=True))

    if not os.path.exists(OUTPUTS_DIR):
        print("❌ Outputs folder not found! Please run DTM and Hydrology pipelines first.")
    else:
        villages = sorted([d for d in os.listdir(OUTPUTS_DIR) if os.path.isdir(os.path.join(OUTPUTS_DIR, d))])
        model_out = os.path.join(OUTPUTS_DIR, "lulc_rf_model.joblib")

        for village in villages:
            print(f"\n{'='*60}\n🚀 PROCESSING: {village}\n{'='*60}")
            village_dir = os.path.join(OUTPUTS_DIR, village)
            dtm = os.path.join(village_dir, f"{village}_DTM.tif")
            dsm = os.path.join(village_dir, f"{village}_DSM.tif")
            intensity = os.path.join(village_dir, f"{village}_Intensity.tif")
            lulc = os.path.join(village_dir, f"{village}_LULC.tif")
            waterlog = os.path.join(village_dir, f"{village}_WaterloggingHotspots.tif")
            
            if not os.path.exists(dtm): continue
                
            vid = village.split("_")[-1]
            las = next((f for f in all_las_files if village in os.path.basename(f) or vid in os.path.basename(f)), None)
            if not las: continue
                
            if not os.path.exists(dsm):
                print("⏳ Generating DSM natively via WhiteboxTools in Colab...")
                wbt.lidar_digital_surface_model(i=las, output=dsm, resolution=2.0, radius=2.0)
                
            if not os.path.exists(intensity):
                print("⏳ Generating Intensity...")
                try: wbt.lidar_nearest_neighbour_gridding(i=las, output=intensity, parameter="intensity", returns="all", resolution=2.0, radius=2.0)
                except: wbt.lidar_point_stats(i=las, output=intensity, resolution=2.0, num_returns=False, z_range=False, intensity_range=False, predominant_class=False)

            roughness = os.path.join(village_dir, f"{village}_Roughness.tif")
            curvature = os.path.join(village_dir, f"{village}_Curvature.tif")

            if not os.path.exists(roughness):
                print("⏳ Generating Roughness Index...")
                wbt.ruggedness_index(dem=dtm, output=roughness)
            
            if not os.path.exists(curvature):
                print("⏳ Generating Profile Curvature...")
                wbt.profile_curvature(dem=dtm, output=curvature)

            if os.path.exists(dsm) and os.path.exists(intensity) and os.path.exists(roughness) and os.path.exists(curvature):
                run_village_lulc(dtm, dsm, intensity, roughness, curvature, lulc, model_out, waterlog)

        print("\n🎉 ALL VILLAGES PROCESSED SUCCESSFULLY ON COLAB!")


# ─────────────────────────────────────────────────────────────────────────────
# WRAPPER FOR BACKEND
# ─────────────────────────────────────────────────────────────────────────────

def run_lulc_pipeline(village_name: str, output_dir: str):
    """Full LULC pipeline wrapper for the web backend."""
    print(f"🚀 Starting LULC Pipeline for {village_name}...")
    
    dtm = os.path.join(output_dir, f"{village_name}_DTM.tif")
    dsm = os.path.join(output_dir, f"{village_name}_DSM.tif")
    intensity = os.path.join(output_dir, f"{village_name}_Intensity.tif")
    lulc = os.path.join(output_dir, f"{village_name}_LULC.tif")
    waterlog = os.path.join(output_dir, f"{village_name}_WaterloggingHotspots.tif")
    model_path = os.path.join(output_dir, "lulc_rf_model.joblib")
    roughness = os.path.join(output_dir, f"{village_name}_Roughness.tif")
    curvature = os.path.join(output_dir, f"{village_name}_Curvature.tif")
    
    # Ensure DSM and Intensity exist (as per script logic)
    import glob
    import whitebox
    las_files = glob.glob(os.path.join(output_dir, "*.la[sz]"))
    wbt = whitebox.WhiteboxTools()
    wbt.set_working_dir(output_dir)
    wbt.set_verbose_mode(False)

    if not os.path.exists(roughness):
        wbt.ruggedness_index(dem=dtm, output=os.path.basename(roughness))
    if not os.path.exists(curvature):
        wbt.profile_curvature(dem=dtm, output=os.path.basename(curvature))

    if not os.path.exists(dsm) or not os.path.exists(intensity):
        if las_files:
            las = las_files[0]
            if not os.path.exists(dsm):
                wbt.lidar_digital_surface_model(i=las, output=os.path.basename(dsm), resolution=2.0, radius=2.0)
            if not os.path.exists(intensity):
                try: wbt.lidar_nearest_neighbour_gridding(i=las, output=os.path.basename(intensity), parameter="intensity", returns="all", resolution=2.0, radius=2.0)
                except: wbt.lidar_point_stats(i=las, output=os.path.basename(intensity), resolution=2.0, num_returns=False, z_range=False, intensity_range=False, predominant_class=False)

    run_village_lulc(dtm, dsm, intensity, roughness, curvature, lulc, model_path, waterlog)
    print(f"✅ LULC Pipeline finished for {village_name}")
