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
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import matplotlib.patches as mpatches

# --- 1. SETUP ENVIRONMENT FOR GOOGLE COLAB ---
try:
    import whitebox
except ImportError:
    print("Whitebox not found. Please run: !pip install whitebox rasterio scikit-learn matplotlib joblib")
    sys.exit(1)

# Set base paths for Google Drive! Change to match your exact Google Drive folder path!
BASE_DIR = "/content/drive/MyDrive/GEO-INTEL_pipeline" 
OUTPUTS_DIR = os.path.join(BASE_DIR, "Outputs") # Note: adjust exact capitalization

wbt = whitebox.WhiteboxTools()
wbt.set_working_dir(BASE_DIR)


# --- 2. LULC CORE PIPELINE ---
def read_and_align_raster(target_meta, src_path, resampling=Resampling.bilinear):
    with rasterio.open(src_path) as src:
        with WarpedVRT(src, src_crs=target_meta['crs'], crs=target_meta['crs'], transform=target_meta['transform'], 
                       height=target_meta['height'], width=target_meta['width'],
                       resampling=resampling) as vrt:
            return vrt.read(1)

def create_lulc_features(dtm_path, dsm_path, intensity_path):
    if not os.path.exists(dtm_path) or not os.path.exists(dsm_path) or not os.path.exists(intensity_path):
        return None, None, None, None

    with rasterio.open(dtm_path) as src:
        dtm = src.read(1)
        meta = src.meta.copy()
        nodata = src.nodata if src.nodata is not None else -9999.0
        
    dsm = read_and_align_raster(meta, dsm_path)
    intensity = read_and_align_raster(meta, intensity_path)
    
    ndsm = np.where((dtm != nodata) & (dsm != nodata), dsm - dtm, np.nan)
    valid_mask = (~np.isnan(ndsm)) & (~np.isnan(intensity)) & (dtm != nodata)
    ndsm[valid_mask] = np.clip(ndsm[valid_mask], 0, None)
    
    features = np.column_stack((ndsm[valid_mask], intensity[valid_mask]))
    return features, valid_mask, dtm.shape, meta

def train_lulc_model(X, y, model_out_path):
    print("⏳ Training Random Forest...")
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    clf = RandomForestClassifier(n_estimators=100, max_depth=15, n_jobs=-1, random_state=42, class_weight='balanced')
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
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with rasterio.open(output_path, 'w', **meta) as dst:
        dst.write(lulc.astype(np.float32), 1)
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

def run_village_lulc(dtm, dsm, intensity, out, model_path, waterlog):
    features, valid_mask, shape, meta = create_lulc_features(dtm, dsm, intensity)
    if features is None: return
    
    print("⏳ Auto-Generating Training Baseline...")
    if len(features) > 100_000:
        syn_features = features[np.random.choice(len(features), 100_000, replace=False)]
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
print("🔍 Scanning Google Drive for Point Clouds...")
all_las_files = []
pc_dirs = ["Gujrat_Point_Cloud", "Punjab_Point_Cloud", "Rajasthan_Point_Cloud", 
           "Tamil Nadu_Point_Cloud", "Andaman_and_Nicobar_Islands_1", "Andaman and Nicobar Islands 2"]

for d in pc_dirs:
    dir_path = os.path.join(BASE_DIR, d)
    if os.path.exists(dir_path):
        all_las_files.extend(glob.glob(os.path.join(dir_path, "**", "*.las"), recursive=True))
        all_las_files.extend(glob.glob(os.path.join(dir_path, "**", "*.laz"), recursive=True))

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
        try: wbt.lidar_idw_interpolation(i=las, output=intensity, parameter="intensity", returns="all", resolution=2.0, weight=2.0, radius=2.0)
        except: wbt.lidar_point_stats(i=las, output=intensity, resolution=2.0, num_returns=False, z_range=False, intensity_range=False, predominant_class=False)

    if os.path.exists(dsm) and os.path.exists(intensity):
        run_village_lulc(dtm, dsm, intensity, lulc, model_out, waterlog)

print("\n🎉 ALL VILLAGES PROCESSED SUCCESSFULLY ON COLAB!")
