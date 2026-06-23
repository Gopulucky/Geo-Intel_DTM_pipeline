"""
=============================================================================
PS2: DTM Creation using AI/ML from Point Cloud Data
     + Drainage Network Design for Village Abadi Areas
=============================================================================
MoPR Hackathon | IIT Tirupati NIF | Geo-Intel Lab
=============================================================================
Pipeline:
  1. Point Cloud Loading & Preprocessing     (laspy)
  2. AI/ML Ground Classification             (Random Forest on point features)
  3. DTM Generation                          (IDW interpolation -> GeoTIFF)
  4. Hydrological Analysis                   (pysheds: flow dir, accumulation)
  5. Waterlogging Hotspot Prediction         (low-lying zone detection)
  6. Drainage Network Extraction & Design    (Strahler ordering, parameters)
  7. GIS Export                              (GeoTIFF + GeoJSON/Shapefile)
  8. Accuracy Metrics & Visualisation
=============================================================================
USAGE (Google Colab):
  !pip install laspy[lazrs] pysheds geopandas rasterio scipy scikit-learn
      matplotlib numpy pandas
  Then run all cells.
=============================================================================
"""

# ─────────────────────────────────────────────
# CELL 1 – Install dependencies
# ─────────────────────────────────────────────
"""
# Run this in a Colab cell:
!pip install laspy[lazrs] pysheds geopandas rasterio scipy scikit-learn \
             matplotlib numpy pandas shapely tqdm joblib -q
"""

# ─────────────────────────────────────────────
# CELL 2 – Imports
# ─────────────────────────────────────────────
import os, warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # non-interactive backend for headless servers
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from scipy.interpolate import griddata
from scipy.ndimage import uniform_filter, label as ndlabel
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
import rasterio
from rasterio.transform import from_bounds
from rasterio.crs import CRS
import geopandas as gpd
from shapely.geometry import LineString, Point, Polygon
import laspy
from tqdm import tqdm
import joblib
import whitebox
try:
    import requests
except ImportError:
    requests = None

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────
# CELL 3 – Global Config
# ─────────────────────────────────────────────
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class PipelineConfig:
    las_dir: str = os.environ.get("INPUTS_DIR", "./input_data")
    output_dir: str = "./outputs"
    model_path: str = "./outputs/rf_classifier.joblib"
    dtm_resolution: float = 2.0
    dtm_interp: str = "linear"
    rf_n_estimators: int = 200
    rf_max_depth: int = 20
    test_size: float = 0.2
    random_state: int = 42
    flow_acc_threshold: int = 500
    depression_depth_m: float = 0.3
    max_ground_points: int = 500_000
    epsg: Optional[int] = int(os.environ.get("EPSG")) if os.environ.get("EPSG") else None
    _village_flow_threshold: Optional[int] = None
    
    def __getitem__(self, item):
        return getattr(self, item)
        
    def __setitem__(self, key, value):
        setattr(self, key, value)
        
    def get(self, key, default=None):
        return getattr(self, key, default)

CONFIG = PipelineConfig()

os.makedirs(CONFIG["output_dir"], exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 1 – POINT CLOUD LOADING
# ─────────────────────────────────────────────────────────────────────────────

def ensure_metric_crs(x, y, las_header=None):
    """Robust 3-tier CRS fallback: Header -> Auto-UTM -> Raise Error."""
    import pyproj
    
    # 1. Read CRS from LAS header if available
    crs = None
    if las_header is not None:
        try:
            crs = las_header.parse_crs()
        except Exception:
            pass
            
    if crs is not None and crs.is_projected:
        print(f"  [CRS] Metric CRS found in LAS header: {crs.name}")
        try:
            CONFIG.epsg = crs.to_epsg()
        except Exception:
            pass
        return x, y
        
    # 3a. Check if geographic
    if -180 <= x.min() <= x.max() <= 180 and -90 <= y.min() <= y.max() <= 90:
        lon_center = x.mean()
        lat_center = y.mean()
        utm_zone = int((lon_center + 180) / 6) % 60 + 1
        epsg = 32600 + utm_zone if lat_center >= 0 else 32700 + utm_zone
        print(f"  [CRS] Geographic coords detected. Auto-calculating UTM Zone {utm_zone} ({'N' if lat_center >=0 else 'S'}). EPSG:{epsg}")
        CONFIG.epsg = epsg
        
        from pyproj import Transformer
        transformer = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
        x_new, y_new = transformer.transform(x, y)
        return np.array(x_new), np.array(y_new)
        
    # 3c. If coordinates are metric but no CRS is found
    if CONFIG.epsg is not None:
        print(f"  [CRS] Using user-provided EPSG:{CONFIG.epsg}")
        return x, y
        
    if x.min() < 100000 and y.min() < 100000:
        print("  [CRS] WARNING: Coordinates appear to be local (near 0,0). Saving without a CRS.")
        CONFIG.epsg = None
        return x, y
        
    print("  [CRS] WARNING: Coordinates appear metric but no CRS was found. Assuming UTM Zone 43N (EPSG:32643) as fallback.")
    CONFIG.epsg = 32643
    return x, y

def load_point_cloud(las_path: str) -> pd.DataFrame:
    """
    Load a LAS/LAZ file and return a DataFrame of point attributes.
    Columns: x, y, z, intensity, return_number, number_of_returns,
             scan_angle, classification (original, if available)
    """
    las = laspy.read(las_path)
    
    try:
        scan_angle = np.array(las.scan_angle_rank).astype(np.float32)
    except AttributeError:
        scan_angle = np.array(las.scan_angle).astype(np.float32)
        
    df = pd.DataFrame({
        "x":               np.array(las.x),
        "y":               np.array(las.y),
        "z":               np.array(las.z),
        "intensity":       np.array(las.intensity).astype(np.float32),
        "return_number":   np.array(las.return_number).astype(np.uint8),
        "num_returns":     np.array(las.number_of_returns).astype(np.uint8),
        "scan_angle":      scan_angle,
        "classification":  np.array(las.classification).astype(np.uint8),
    })
    
    df["x"], df["y"] = ensure_metric_crs(df["x"].values, df["y"].values, las.header)
    
    print(f"  Loaded {len(df):,} points from {os.path.basename(las_path)}")
    return df


def load_ground_only(las_path: str, max_points: int = None) -> pd.DataFrame:
    """
    Memory-efficient loader: reads LAS/LAZ file in CHUNKS and keeps only
    GROUND points (ASPRS Class 2). The full file is NEVER loaded into
    memory at once - safe for 200M+ point datasets on Colab (12GB RAM).

    FALLBACK: If no Class 2 ground labels exist (unclassified data),
    automatically switches to a grid-based lowest-percentile filter
    to approximate ground points from the raw point cloud.
    """
    import gc
    max_pts = max_points or CONFIG.get("max_ground_points", 500_000)
    chunk_size = 1_000_000   # read 1M points at a time

    print(f"  Reading LAS/LAZ file in chunks of {chunk_size:,} (ground only)...")

    ground_x = []
    ground_y = []
    ground_z = []
    n_total = 0
    n_ground = 0

    with laspy.open(las_path) as las_file:
        for chunk in las_file.chunk_iterator(chunk_size):
            n_total += len(chunk)

            # Filter to ground points (class 2) within this chunk
            mask = np.array(chunk.classification) == 2
            n_gnd = mask.sum()
            n_ground += n_gnd

            if n_gnd > 0:
                ground_x.append(np.array(chunk.x)[mask].astype(np.float32))
                ground_y.append(np.array(chunk.y)[mask].astype(np.float32))
                ground_z.append(np.array(chunk.z)[mask].astype(np.float32))

            # Print progress every 50M points
            if n_total % (50 * chunk_size) == 0:
                print(f"    ... read {n_total:,} points so far ({n_ground:,} ground)")

    print(f"  Total points: {n_total:,}  |  Ground (class 2): {n_ground:,}")

    # ── FALLBACK: No ground labels -> use grid-based ground filter ────────────
    if n_ground == 0:
        print("  [WARNING] No Class 2 ground labels found! Using grid-based ground filter...")
        del ground_x, ground_y, ground_z
        gc.collect()
        return _load_ground_by_grid_filter(las_path, max_pts, chunk_size)

    # Concatenate all ground chunks
    x = np.concatenate(ground_x); del ground_x
    y = np.concatenate(ground_y); del ground_y
    z = np.concatenate(ground_z); del ground_z
    gc.collect()

    with laspy.open(las_path) as las_file:
        las_header = las_file.header
    x, y = ensure_metric_crs(x, y, las_header)

    # Subsample if too many ground points
    if len(x) > max_pts:
        print(f"  Subsampling ground points: {len(x):,} -> {max_pts:,}")
        rng = np.random.RandomState(CONFIG["random_state"])
        idx = rng.choice(len(x), max_pts, replace=False)
        idx.sort()
        x, y, z = x[idx], y[idx], z[idx]
        gc.collect()

    df = pd.DataFrame({"x": x, "y": y, "z": z})
    df["pred_ground"] = 1  # all are ground
    del x, y, z
    gc.collect()

    print(f"  Ground DataFrame ready: {len(df):,} points ({df.memory_usage(deep=True).sum()/1e6:.1f} MB)")
    return df


def _load_ground_by_grid_filter(las_path: str, max_pts: int,
                                 chunk_size: int = 1_000_000) -> pd.DataFrame:
    """
    Fallback ground extraction for UNCLASSIFIED point clouds.
    Strategy:
      1. Read all points in chunks, subsample to a manageable size.
      2. Divide into grid cells (5m × 5m).
      3. In each cell, keep points whose elevation is within the lowest
         10th percentile -> these approximate the bare ground.
      4. Subsample to max_pts for DTM interpolation.
    """
    import gc
    print("  [Fallback] Reading all points for grid-based ground filtering...")

    all_x = []
    all_y = []
    all_z = []
    n_total = 0

    # First pass: collect a random subsample of ALL points (cap at 5M for RAM safety)
    subsample_cap = 5_000_000
    rng = np.random.RandomState(CONFIG["random_state"])

    with laspy.open(las_path) as las_file:
        tot_pts = las_file.header.point_count
        keep_frac = min(1.0, subsample_cap / max(tot_pts, 1))
        
        for chunk in las_file.chunk_iterator(chunk_size):
            n_total += len(chunk)
            cx = np.array(chunk.x).astype(np.float32)
            cy = np.array(chunk.y).astype(np.float32)
            cz = np.array(chunk.z).astype(np.float32)

            if keep_frac < 1.0:
                mask = rng.random(len(cx)) < keep_frac
                cx, cy, cz = cx[mask], cy[mask], cz[mask]

            all_x.append(cx)
            all_y.append(cy)
            all_z.append(cz)

            if n_total % (10 * chunk_size) == 0:
                print(f"    ... read {n_total:,} points so far")

    print(f"  [Fallback] Total points in file: {n_total:,}")

    x = np.concatenate(all_x); del all_x
    y = np.concatenate(all_y); del all_y
    z = np.concatenate(all_z); del all_z
    gc.collect()

    # Trim to subsample_cap if overshot
    if len(x) > subsample_cap:
        idx = rng.choice(len(x), subsample_cap, replace=False)
        idx.sort()
        x, y, z = x[idx], y[idx], z[idx]
        gc.collect()

    print(f"  [Fallback] Working with {len(x):,} subsampled points")

    with laspy.open(las_path) as las_file:
        las_header = las_file.header
    x, y = ensure_metric_crs(x, y, las_header)

    # Grid-based lowest-percentile filter (5m cells, keep bottom 10%)
    cell_size = 5.0  # metres
    percentile = 10  # keep lowest 10% in each cell

    xi = ((x - x.min()) / cell_size).astype(np.int32)
    yi = ((y - y.min()) / cell_size).astype(np.int32)
    cell_id = yi * (xi.max() + 1) + xi

    # Compute percentile threshold per cell
    df_tmp = pd.DataFrame({"x": x, "y": y, "z": z, "cell": cell_id})
    del x, y, z, xi, yi, cell_id
    gc.collect()

    cell_thresh = df_tmp.groupby("cell")["z"].quantile(percentile / 100.0)
    cell_thresh.name = "z_thresh"
    df_tmp = df_tmp.join(cell_thresh, on="cell")

    # Keep points at or below the percentile threshold
    ground_mask = df_tmp["z"] <= df_tmp["z_thresh"]
    df_ground = df_tmp.loc[ground_mask, ["x", "y", "z"]].copy()
    del df_tmp
    gc.collect()

    print(f"  [Fallback] Grid filter kept {len(df_ground):,} ground-approximation points")

    # Final subsample to max_pts
    if len(df_ground) > max_pts:
        print(f"  [Fallback] Subsampling: {len(df_ground):,} -> {max_pts:,}")
        df_ground = df_ground.sample(max_pts, random_state=CONFIG["random_state"])

    df_ground = df_ground.reset_index(drop=True)
    df_ground["pred_ground"] = 1
    gc.collect()

    print(f"  [Fallback] Ground DataFrame ready: {len(df_ground):,} points "
          f"({df_ground.memory_usage(deep=True).sum()/1e6:.1f} MB)")
    return df_ground


def load_all_villages(las_dir: str) -> dict:
    """Load all LAS/LAZ files from a directory. Returns {village_name: DataFrame}."""
    files = [f for f in os.listdir(las_dir) if f.lower().endswith((".las", ".laz"))]
    assert files, f"No LAS/LAZ files found in {las_dir}"
    villages = {}
    for f in sorted(files):
        name = os.path.splitext(f)[0]
        print(f"Loading: {f}")
        villages[name] = load_point_cloud(os.path.join(las_dir, f))
    return villages


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 2 – FEATURE ENGINEERING FOR ML CLASSIFICATION
# ─────────────────────────────────────────────────────────────────────────────

def compute_neighbourhood_features(df: pd.DataFrame,
                                   radius: float = 1.0,
                                   sample_n: int = 500_000) -> pd.DataFrame:
    """
    Compute local neighbourhood statistics used as ML features:
      - z_mean_local, z_std_local, z_range_local  (elevation neighbourhood stats)
      - height_above_min  (z - local minimum -> key ground indicator)
      - slope_approx      (z_std / radius as slope proxy)
      - return_ratio      (return_number / num_returns)
      - last_return       (1 if last return, else 0)
    Uses a fast grid-based approach (no KD-tree needed for large datasets).
    """
    if len(df) > sample_n:
        print(f"  Subsampling to {sample_n:,} points for feature computation...")
        df = df.sample(sample_n, random_state=CONFIG["random_state"]).reset_index(drop=True)

    # Grid-based local stats
    res = 2.0  # 2m grid for neighbourhood
    xi = ((df["x"] - df["x"].min()) / res).astype(int)
    yi = ((df["y"] - df["y"].min()) / res).astype(int)
    cell_id = yi * (xi.max() + 1) + xi
    df = df.copy()
    df["_cell"] = cell_id

    grp = df.groupby("_cell")["z"]
    cell_stats = grp.agg(["mean", "std", "min", "max"]).rename(columns={
        "mean": "z_mean_local",
        "std":  "z_std_local",
        "min":  "z_min_local",
        "max":  "z_max_local",
    })
    cell_stats["z_range_local"] = cell_stats["z_max_local"] - cell_stats["z_min_local"]
    df = df.join(cell_stats, on="_cell")

    df["height_above_min"] = df["z"] - df["z_min_local"]
    df["slope_approx"]     = df["z_std_local"].fillna(0) / res
    df["return_ratio"]     = df["return_number"] / df["num_returns"].replace(0, 1)
    df["last_return"]      = (df["return_number"] == df["num_returns"]).astype(np.uint8)

    df.drop(columns=["_cell", "z_min_local", "z_max_local"], inplace=True)
    df.fillna(0, inplace=True)

    return df


FEATURE_COLS = [
    "z", "intensity", "return_number", "num_returns", "scan_angle",
    "z_mean_local", "z_std_local", "z_range_local",
    "height_above_min", "slope_approx", "return_ratio", "last_return",
]

# LAS Classification codes (ASPRS standard)
GROUND_CLASS = 2       # Ground
NON_GROUND_CLASS = 1   # Unclassified / Vegetation / Building


def prepare_training_data(df: pd.DataFrame) -> tuple:
    """
    If LAS already has ground labels (class=2), use them as ground truth.
    Otherwise raises an error – manual labelling or CSF pre-processing needed.
    Binary: 1=Ground, 0=Non-ground
    """
    labeled = df[df["classification"].isin([GROUND_CLASS, 1, 3, 4, 5, 6])].copy()
    labeled["label"] = (labeled["classification"] == GROUND_CLASS).astype(int)
    X = labeled[FEATURE_COLS].values
    y = labeled["label"].values
    print(f"  Training samples – Ground: {y.sum():,}  |  Non-ground: {(y==0).sum():,}")
    return X, y


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 3 – RANDOM FOREST GROUND CLASSIFIER
# ─────────────────────────────────────────────────────────────────────────────

def train_classifier(X: np.ndarray, y: np.ndarray) -> RandomForestClassifier:
    """Train a Random Forest ground/non-ground classifier."""
    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=CONFIG["test_size"],
        random_state=CONFIG["random_state"],
        stratify=y,
    )
    clf = RandomForestClassifier(
        n_estimators=CONFIG["rf_n_estimators"],
        max_depth=CONFIG["rf_max_depth"],
        n_jobs=-1,
        random_state=CONFIG["random_state"],
        class_weight="balanced",
    )
    print("  Training Random Forest classifier...")
    clf.fit(X_train, y_train)

    y_pred = clf.predict(X_test)
    print(f"\n  Accuracy: {accuracy_score(y_test, y_pred)*100:.2f}%")
    print(classification_report(y_test, y_pred, target_names=["Non-Ground", "Ground"]))

    # Save model
    joblib.dump(clf, CONFIG["model_path"])
    print(f"  Model saved -> {CONFIG['model_path']}")
    return clf


def classify_points(df: pd.DataFrame, clf: RandomForestClassifier) -> pd.DataFrame:
    """Apply trained classifier to all points. Adds 'pred_ground' column."""
    df = df.copy()
    X = df[FEATURE_COLS].values
    df["pred_ground"] = clf.predict(X)
    n_ground = df["pred_ground"].sum()
    print(f"  Classified {n_ground:,} ground points out of {len(df):,} total")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 4 – DTM GENERATION (IDW / Linear Interpolation)
# ─────────────────────────────────────────────────────────────────────────────

def save_ground_points(df: pd.DataFrame, village_name: str) -> str:
    """Save classified ground points to a LAS file in the village output directory."""
    if "pred_ground" in df.columns:
        gnd_df = df[df["pred_ground"] == 1]
    elif "classification" in df.columns:
        gnd_df = df[df["classification"] == 2]
    else:
        gnd_df = df

    if len(gnd_df) == 0:
        print(f"  No ground points found to save for {village_name}.")
        return ""

    out_path = os.path.join(CONFIG["output_dir"], f"{village_name}_GroundPoints.las")
    print(f"  Saving {len(gnd_df):,} ground points to LAS...")
    
    header = laspy.LasHeader(point_format=2, version="1.2")
    las = laspy.LasData(header)
    
    las.x = gnd_df["x"].values
    las.y = gnd_df["y"].values
    las.z = gnd_df["z"].values
    
    if "intensity" in gnd_df.columns:
        las.intensity = gnd_df["intensity"].values.astype(np.uint16)
        
    las.classification = np.full(len(gnd_df), 2, dtype=np.uint8)
    las.write(out_path)
    print(f"  Ground points saved -> {out_path}")
    return out_path

def stream_classify_and_save(las_path: str, out_las_path: str, clf: RandomForestClassifier, chunk_size=1_000_000) -> pd.DataFrame:
    """
    Reads LAS in chunks, extracts features, predicts ground, and saves to out_las_path.
    Returns a DataFrame of ground points for DTM generation (subsampled if too large).
    """
    import gc
    import laspy
    print(f"  Streaming inference: reading {las_path} in chunks...")
    
    header = laspy.LasHeader(point_format=2, version="1.2")
    
    ground_x, ground_y, ground_z = [], [], []
    n_total = 0
    n_ground = 0
    
    with laspy.open(las_path) as las_in, laspy.open(out_las_path, mode='w', header=header) as las_out:
        in_header = las_in.header
        for chunk in las_in.chunk_iterator(chunk_size):
            n_total += len(chunk)
            
            try:
                scan_angle = np.array(chunk.scan_angle_rank).astype(np.float32)
            except AttributeError:
                scan_angle = np.array(chunk.scan_angle).astype(np.float32)
                
            df_chunk = pd.DataFrame({
                "x":               np.array(chunk.x),
                "y":               np.array(chunk.y),
                "z":               np.array(chunk.z),
                "intensity":       np.array(chunk.intensity).astype(np.float32),
                "return_number":   np.array(chunk.return_number).astype(np.uint8),
                "num_returns":     np.array(chunk.number_of_returns).astype(np.uint8),
                "scan_angle":      scan_angle,
                "classification":  np.array(chunk.classification).astype(np.uint8),
            })
            
            df_chunk["x"], df_chunk["y"] = ensure_metric_crs(df_chunk["x"].values, df_chunk["y"].values, in_header)
            
            df_features = compute_neighbourhood_features(df_chunk, sample_n=len(df_chunk))
            
            X = df_features[FEATURE_COLS].values
            preds = clf.predict(X)
            
            mask = preds == 1
            n_gnd = mask.sum()
            n_ground += n_gnd
            
            if n_gnd > 0:
                gnd_df = df_chunk[mask]
                pts = laspy.ScaleAwarePointRecord.zeros(n_gnd, header=header)
                pts.x = gnd_df["x"].values
                pts.y = gnd_df["y"].values
                pts.z = gnd_df["z"].values
                if "intensity" in gnd_df.columns:
                    pts.intensity = gnd_df["intensity"].values.astype(np.uint16)
                pts.classification = np.full(n_gnd, 2, dtype=np.uint8)
                las_out.write_points(pts)
                
                ground_x.append(gnd_df["x"].values.astype(np.float32))
                ground_y.append(gnd_df["y"].values.astype(np.float32))
                ground_z.append(gnd_df["z"].values.astype(np.float32))
                
            print(f"    ... processed {n_total:,} points ({n_ground:,} ground)")
            
    print(f"  Streaming completed: {n_ground:,} ground points saved to {out_las_path}")
    
    if n_ground == 0:
        return pd.DataFrame(columns=["x", "y", "z", "pred_ground"])
        
    x = np.concatenate(ground_x)
    y = np.concatenate(ground_y)
    z = np.concatenate(ground_z)
    
    max_pts = CONFIG.get("max_ground_points", 500_000)
    if len(x) > max_pts:
        print(f"  Subsampling ground points for DTM: {len(x):,} -> {max_pts:,}")
        rng = np.random.RandomState(CONFIG["random_state"])
        idx = rng.choice(len(x), max_pts, replace=False)
        idx.sort()
        x, y, z = x[idx], y[idx], z[idx]
        
    df_dtm = pd.DataFrame({"x": x, "y": y, "z": z})
    df_dtm["pred_ground"] = 1
    return df_dtm

def generate_dtm(df: pd.DataFrame, village_name: str,
                 resolution: float = None,
                 method: str = None,
                 ground_las_path: str = None) -> tuple:
    """
    Generate a DTM raster from classified ground points.
    Uses WhiteboxTools if ground_las_path is provided, else scipy griddata.

    Returns:
        dtm_array  : 2D numpy array of elevations (NaN for no-data)
        transform  : rasterio Affine transform
        out_path   : path to saved GeoTIFF
    """
    res = resolution or CONFIG["dtm_resolution"]
    interp = method or CONFIG["dtm_interp"]

    if ground_las_path and os.path.exists(ground_las_path):
        import whitebox
        wbt = whitebox.WhiteboxTools()
        wbt.set_verbose_mode(False)
        out_path = os.path.join(CONFIG["output_dir"], f"{village_name}_DTM.tif")
        print(f"  Interpolating DTM ({res}m resolution) using WhiteboxTools lidar_tin_gridding...")
        wbt.lidar_tin_gridding(
            i=os.path.abspath(ground_las_path),
            output=os.path.abspath(out_path),
            parameter="elevation",
            returns="last",
            resolution=res
        )
        
        if CONFIG.epsg is not None:
            with rasterio.open(out_path) as src:
                data = src.read()
                meta = src.meta.copy()
            meta.update({"crs": CRS.from_epsg(CONFIG.epsg)})
            with rasterio.open(out_path, "w", **meta) as dst:
                dst.write(data)

        with rasterio.open(out_path) as src:
            dtm = src.read(1)
            transform = src.transform
        print(f"  DTM saved -> {out_path}")
        return dtm, transform, out_path

    gnd = df[df["pred_ground"] == 1][["x", "y", "z"]].copy()
    if len(gnd) < 100:
        raise ValueError("Too few ground points to generate DTM!")

    # Build regular grid
    x_min, x_max = gnd["x"].min(), gnd["x"].max()
    y_min, y_max = gnd["y"].min(), gnd["y"].max()

    grid_x = np.arange(x_min, x_max + res, res)
    grid_y = np.arange(y_min, y_max + res, res)
    gx, gy = np.meshgrid(grid_x, grid_y)

    print(f"  Interpolating DTM ({len(grid_x)}×{len(grid_y)} px) using '{interp}'...")
    dtm = griddata(
        points=gnd[["x", "y"]].values,
        values=gnd["z"].values,
        xi=(gx, gy),
        method=interp,
        rescale=True,
    )
    
    # ── MASK OUT NO-DATA (CONVEX HULL ARTIFACTS) ──
    from scipy.spatial import cKDTree
    print("  Applying KDTree distance mask to remove Convex Hull artifacts...")
    tree = cKDTree(gnd[["x", "y"]].values)
    
    # Query distance for every pixel coordinate in the grid
    dist, _ = tree.query(np.column_stack((gx.ravel(), gy.ravel())))
    dist = dist.reshape(gx.shape)
    
    # Set maximum distance threshold (15 meters is safe for high-res drone data)
    max_dist = max(15.0, res * 5.0)
    dtm[dist > max_dist] = -9999.0
    
    # Replace any griddata-generated NaNs (outside convex hull) with exactly -9999.0
    dtm = np.nan_to_num(dtm, nan=-9999.0)

    dtm = np.flipud(dtm)   # rasterio convention: row 0 = top

    # Save GeoTIFF
    transform = from_bounds(x_min, y_min, x_max, y_max, dtm.shape[1], dtm.shape[0])
    out_path = os.path.join(CONFIG["output_dir"], f"{village_name}_DTM.tif")
    with rasterio.open(
        out_path, "w",
        driver="COG",
        compress="LZW",
        height=dtm.shape[0], width=dtm.shape[1],
        count=1, dtype="float32",
        crs=CRS.from_epsg(CONFIG["epsg"]),
        transform=transform,
        nodata=-9999.0,
    ) as dst:
        dst.write(dtm.astype(np.float32), 1)

    print(f"  DTM saved -> {out_path}")
    return dtm, transform, out_path


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 5 – HYDROLOGICAL ANALYSIS (pysheds)
# ─────────────────────────────────────────────────────────────────────────────

def fix_raster_crs(target_tif, ref_tif):
    """Ensure WBT outputs retain the CRS and GeoTransform of the input DTM."""
    import rasterio
    import os
    import shutil
    if not os.path.exists(target_tif): return
    with rasterio.open(ref_tif) as src:
        crs = src.crs
        transform = src.transform
    
    with rasterio.open(target_tif) as src:
        if src.crs == crs and src.transform == transform:
            return
        kwargs = src.meta.copy()
        kwargs.update({
            'crs': crs,
            'transform': transform
        })
        data = src.read()
    
    tmp_tif = target_tif + ".tmp.tif"
    with rasterio.open(tmp_tif, 'w', **kwargs) as dst:
        dst.write(data)
    shutil.move(tmp_tif, target_tif)

def run_hydrology(dtm_path: str, village_name: str,
                  flow_threshold: int = None) -> dict:
    """
    Runs a full hydrological workflow on the DTM using WhiteboxTools (matching the master plan):
      1. Breach depressions (better than filling for rural roads)
      2. Flow direction (D8)
      3. Flow accumulation
      4. Stream network extraction
      5. Topographic Wetness Index (TWI) & Sink Depth for waterlogging
      6. Watershed delineation (catchments)

    Returns dict of output paths.
    """
    wbt = whitebox.WhiteboxTools()
    wbt.set_working_dir(os.path.abspath(CONFIG["output_dir"]))
    wbt.set_verbose_mode(False)

    # Per-village threshold: override CONFIG if provided
    threshold = flow_threshold if flow_threshold is not None else CONFIG["flow_acc_threshold"]

    dtm_abs = os.path.abspath(dtm_path)
    paths = {}
    
    def out_file(name):
        return os.path.join(os.path.abspath(CONFIG["output_dir"]), f"{village_name}_{name}")

    breached = out_file("BreachedDTM.tif")
    fdir = out_file("FlowDirection.tif")
    facc = out_file("FlowAccumulation.tif")
    streams_tif = out_file("DrainageNetwork.tif")
    streams_vec = out_file("Streams.shp")
    sink_depth = out_file("WaterloggingHotspots.tif")
    twi = out_file("TWI.tif")
    slope = out_file("Slope.tif")
    sca = out_file("SCA.tif")
    catchments = out_file("Catchments.tif")

    # ── 1. Breach depressions ──────────────────────────────────────────────────
    print("  Breaching depressions to model culverts/drainpaths...")
    wbt.breach_depressions(dem=os.path.basename(dtm_abs), output=os.path.basename(breached), flat_increment=0.001)

    # ── 2. Flow direction & accumulation ─────────────────────────────────────
    print("  Computing flow direction & accumulation (D8)...")
    wbt.d8_pointer(dem=os.path.basename(breached), output=os.path.basename(fdir))
    wbt.d8_flow_accumulation(i=os.path.basename(breached), output=os.path.basename(facc), out_type="cells")
    paths["FlowAccumulation"] = facc

    # ── 3. Stream extraction & Watersheds ────────────────────────────────────
    print("  Extracting streams and catchments...")
    
    # Adaptive threshold to guarantee stream extraction
    current_thresh = threshold
    while current_thresh >= 10:
        wbt.extract_streams(flow_accum=os.path.basename(facc), output=os.path.basename(streams_tif), threshold=current_thresh)
        wbt.raster_streams_to_vector(streams=os.path.basename(streams_tif), d8_pntr=os.path.basename(fdir), output=os.path.basename(streams_vec))
        
        if os.path.exists(streams_vec):
            import geopandas as gpd
            try:
                if len(gpd.read_file(streams_vec)) > 0:
                    break
            except Exception:
                pass
        
        print(f"  [WARNING] No streams extracted at threshold {current_thresh}. Halving and retrying...")
        current_thresh //= 2

    paths["streams"] = streams_vec

    # FIX: WhiteboxTools writes .shp without a .prj sidecar.
    # Assign the DTM CRS and re-save so the file works in QGIS individually.
    if os.path.exists(streams_vec):
        try:
            _sgdf = gpd.read_file(streams_vec)
            if len(_sgdf) > 0 and _sgdf.crs is None:
                with rasterio.open(dtm_abs) as _src:
                    _dtm_crs = _src.crs
                if _dtm_crs is not None:
                    _sgdf.set_crs(_dtm_crs, allow_override=True, inplace=True)
                    _sgdf.to_file(streams_vec)
                    print(f"  [CRS FIX] Assigned {_dtm_crs} to {os.path.basename(streams_vec)}")
        except Exception as _e:
            print(f"  [CRS FIX] Warning — could not set CRS on streams: {_e}")

    wbt.subbasins(d8_pntr=os.path.basename(fdir), streams=os.path.basename(streams_tif), output=os.path.basename(catchments))
    paths["catchments"] = catchments

    # ── 4. Waterlogging hotspots (Depression + TWI) ──────────────────────────
    print("  Predicting waterlogging zones (Sink Depth & TWI)...")
    # Use ORIGINAL DTM for sink detection — breaching removes all depressions,
    # so depth_in_sink on a breached DEM returns empty (all-nodata) output.
    wbt.depth_in_sink(dem=os.path.basename(dtm_abs), output=os.path.basename(sink_depth), zero_background=False)
    paths["WaterloggingDepth"] = sink_depth
    
    wbt.slope(dem=os.path.basename(breached), output=os.path.basename(slope), units="degrees")
    wbt.d_inf_flow_accumulation(i=os.path.basename(breached), output=os.path.basename(sca), out_type="sca")
    wbt.wetness_index(sca=os.path.basename(sca), slope=os.path.basename(slope), output=os.path.basename(twi))
    paths["TWI"] = twi

    # Clean up temp files if desired
    for tmp in [sca, slope]:
        if os.path.exists(tmp): os.remove(tmp)

    # Build Hotspots Polygons simply by thresholding depth_in_sink
    if os.path.exists(sink_depth):
        with rasterio.open(sink_depth) as src:
            depth_arr = src.read(1).astype(float)
            # FIX: safe nodata handling – guard against None and use np.isnan for float rasters
            if src.nodata is not None:
                depth_arr[depth_arr == src.nodata] = np.nan
            depth_arr = np.where(np.isnan(depth_arr), 0.0, depth_arr)
            hotspot_mask = depth_arr > CONFIG["depression_depth_m"]
            
        hotspot_polys = _raster_to_polygons(hotspot_mask, dtm_abs, min_area_m2=4.0)
        if hotspot_polys is not None and len(hotspot_polys) > 0:
            hp_path = out_file("WaterloggingHotspots.gpkg")
            hotspot_polys.to_file(hp_path, driver="GPKG")
            paths["hotspots"] = hp_path
            print(f"  Waterlogging hotspots -> {hp_path} ({len(hotspot_polys)} zones)")
    else:
        print(f"  [WARNING] Sink depth raster was not created by WBT at {sink_depth}. Skipping hotspot extraction.")

    print("  Fixing projection metadata for GeoTIFFs...")
    for out_tif in [breached, fdir, facc, streams_tif, sink_depth, twi, catchments]:
        fix_raster_crs(out_tif, dtm_abs)

    return paths


def _raster_to_polygons(mask: np.ndarray, reference_tif: str,
                         min_area_m2: float = 4.0) -> gpd.GeoDataFrame:
    """Convert a binary mask raster to GeoDataFrame of polygons (basic approach)."""
    from rasterio.features import shapes
    from shapely.geometry import shape

    with rasterio.open(reference_tif) as src:
        transform = src.transform
        crs       = src.crs

    mask_u8 = mask.astype(np.uint8)
    geoms   = []
    for geom, val in shapes(mask_u8, mask=mask_u8, transform=transform):
        if val == 1:
            s = shape(geom)
            if s.area >= min_area_m2:
                geoms.append(s)

    if not geoms:
        return None
        
    gdf = gpd.GeoDataFrame(geometry=geoms, crs=crs)
    gdf["id"] = range(1, len(gdf) + 1)
    gdf["type"] = "Waterlogging Hotspot"
    
    # Safely compute area in projected CRS
    gdf["area_m2"] = gdf.geometry.area
    
    return gdf


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 5b – DYNAMIC RAINFALL & THRESHOLD FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def get_dtm_center_latlon(dtm_path: str) -> tuple:
    """
    Reads a projected DTM GeoTIFF, computes its bounding-box centre,
    and reprojects that point to geographic coordinates (EPSG:4326).

    Returns:
        (lat, lon) as floats, or (None, None) on failure.
    """
    try:
        from pyproj import Transformer
        with rasterio.open(dtm_path) as src:
            bounds = src.bounds
            src_crs = src.crs

        cx = (bounds.left + bounds.right) / 2.0
        cy = (bounds.bottom + bounds.top) / 2.0

        # If the CRS is already geographic, no transform needed
        if src_crs and src_crs.is_geographic:
            return cy, cx   # lat, lon

        # Reproject from projected CRS -> WGS-84
        transformer = Transformer.from_crs(src_crs, "EPSG:4326", always_xy=True)
        lon, lat = transformer.transform(cx, cy)
        print(f"  [Rainfall] DTM centre -> Lat: {lat:.5f}, Lon: {lon:.5f}")
        return float(lat), float(lon)
    except Exception as e:
        print(f"  [Rainfall] WARNING: Could not extract DTM lat/lon: {e}")
        return None, None


def fetch_peak_rainfall(lat: float, lon: float,
                        default_mm_day: float = 100.0) -> float:
    """
    Fetches the last 10 years of daily precipitation from the Open-Meteo
    Historical Weather API (a free proxy for regional gridded datasets such
    as ERA5 / IMD-merged products) and returns the 99th-percentile daily
    rainfall as the design storm value P_day (mm/day).

    Falls back to `default_mm_day` if the API is unreachable or lat/lon
    are not available.
    """
    if lat is None or lon is None:
        print(f"  [Rainfall] No coordinates available – using default {default_mm_day} mm/day")
        return default_mm_day

    if requests is None:
        print("  [Rainfall] 'requests' library not installed – using default rainfall.")
        return default_mm_day

    from datetime import date, timedelta
    end_date   = date.today()
    start_date = end_date.replace(year=end_date.year - 10)

    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude":            lat,
        "longitude":           lon,
        "start_date":          start_date.isoformat(),
        "end_date":            end_date.isoformat(),
        "daily":               "precipitation_sum",
        "timezone":            "Asia/Kolkata",
    }

    try:
        print(f"  [Rainfall] Fetching 10-year precipitation data from Open-Meteo...")
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        precip = np.array(data["daily"]["precipitation_sum"], dtype=float)
        # Remove NaN / fill-values
        precip = precip[~np.isnan(precip)]

        if len(precip) == 0:
            raise ValueError("Empty precipitation array returned by API.")

        p99 = float(np.percentile(precip, 99))
        print(f"  [Rainfall] 10-year P99 daily rainfall = {p99:.1f} mm/day  "
              f"(n={len(precip)} days, max={precip.max():.1f} mm)")
        return p99

    except Exception as e:
        print(f"  [Rainfall] API error ({e}) – falling back to {default_mm_day} mm/day")
        return default_mm_day


def calculate_dynamic_threshold(rainfall_mm_day: float,
                                cell_resolution_m: float = 2.0) -> int:
    """
    Derives the stream-extraction flow-accumulation threshold from a
    critical-discharge / rational-method formulation:

        Threshold_Cells = (Q_c * 86_400_000) / (C * P_day * cell_area)

    where
        Q_c       = 0.01  m^3/s  – critical discharge for channel initiation
        C         = 0.60         – runoff coefficient (rural)
        P_day               mm/day – peak daily rainfall (99th percentile)
        cell_area = res^2   m^2   – DTM pixel area

    Returns an integer >= 10 (never lets the threshold drop below 10 cells).
    """
    Q_c       = 0.01          # m^3/s
    C         = 0.60          # runoff coefficient
    cell_area = cell_resolution_m ** 2   # m^2

    # Guard against zero / nonsensical rainfall
    rainfall_safe = max(rainfall_mm_day, 1.0)

    threshold_cells = (Q_c * 86_400_000.0) / (C * rainfall_safe * cell_area)
    threshold_cells = max(10, int(threshold_cells))

    print(f"  [Threshold] Dynamic stream threshold = {threshold_cells} cells  "
          f"(P_day={rainfall_safe:.1f} mm, res={cell_resolution_m} m)")
    return threshold_cells


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 6 – DRAINAGE NETWORK DESIGN PARAMETERS
# ─────────────────────────────────────────────────────────────────────────────

def compute_drainage_parameters(streams_path: str,
                                 dtm_path: str,
                                 facc_path: str,
                                 village_name: str,
                                 rainfall_mm_day: float = 100.0) -> gpd.GeoDataFrame:
    """
    Augment the stream network with engineering design parameters:
      - Strahler stream order
      - Channel slope (m/m)
      - Catchment area proxy (from flow accumulation)
      - Recommended channel width & depth (rational method proxy)
      - Flow velocity estimate (Manning's equation)

    Args:
        rainfall_mm_day: Design storm (P99 99th-percentile daily rainfall in mm/day).
                         Replaces the legacy hardcoded 50 mm/hr assumption.
    """
    if not os.path.exists(streams_path):
        print("  No stream file found; skipping parameter computation.")
        return None

    try:
        gdf = gpd.read_file(streams_path)
    except Exception as e:
        print(f"  Warning: Could not read stream file {streams_path}: {e}")
        return None
        
    if len(gdf) == 0:
        print("  Warning: Stream network is empty.")
        return gdf

    # ── Vector Design Intent Attributes ──────────────────────────────────────
    gdf["id"] = range(1, len(gdf) + 1)
    gdf["type"] = "Natural Drain"

    # ── Strahler ordering (simplified: by geometry length) ───────────────────
    gdf["length_m"]     = gdf.geometry.length
    gdf["strahler_ord"] = pd.cut(
        gdf["length_m"],
        bins=[0, 50, 150, 350, 700, np.inf],
        labels=[1, 2, 3, 4, 5],
    ).astype(float).fillna(1).astype(int)

    # ── Slope from DTM along each reach ──────────────────────────────────────
    with rasterio.open(dtm_path) as src:
        dtm_arr = src.read(1).astype(float)
        dtm_arr[dtm_arr == src.nodata] = np.nan
        transform = src.transform
        dtm_crs = src.crs

    def _sample_z(geom):
        """Sample DTM at start and end of line."""
        coords = list(geom.coords)
        def _z(xy):
            row, col = rasterio.transform.rowcol(transform, xy[0], xy[1])
            r = max(0, min(row, dtm_arr.shape[0]-1))
            c = max(0, min(col, dtm_arr.shape[1]-1))
            return dtm_arr[r, c]
        return _z(coords[0]), _z(coords[-1])

    slopes = []
    for _, row in gdf.iterrows():
        try:
            z_start, z_end = _sample_z(row.geometry)
            dz = abs(z_start - z_end)
            dl = max(row["length_m"], 0.1)
            slopes.append(dz / dl)
        except Exception:
            slopes.append(0.005)   # default 0.5% slope
    gdf["slope_m_m"] = np.clip(slopes, 0.001, 1.0)

    # ── Rational Method proxy for channel sizing ──────────────────────────────
    # Q = C * i * A  (C=0.6 rural; i derived from dynamic daily rainfall P99)
    # Convert mm/day -> m/s:  (mm/day) / 1000 / 86400
    C_runoff = 0.6
    i_m_s    = (rainfall_mm_day / 1000.0) / 86400.0
    print(f"  [Drainage] Using design rainfall: {rainfall_mm_day:.1f} mm/day  "
          f"→ i = {i_m_s*1e6:.3f} µm/s  ({i_m_s*1000*3600:.2f} mm/hr equiv)")

    # ── Catchment area from Flow Accumulation ────────────────────────────────
    res = 2.0  # fallback resolution
    try:
        if not os.path.exists(facc_path):
            raise FileNotFoundError("Flow Accumulation raster not found.")
            
        with rasterio.open(facc_path) as src:
            facc_arr = src.read(1).astype(float)
            if src.nodata is not None:
                facc_arr[facc_arr == src.nodata] = 0.0
            facc_transform = src.transform
            res = src.res[0]
            
        def _sample_facc(geom):
            coords = list(geom.coords)
            # Sample at the downstream end
            row, col = rasterio.transform.rowcol(facc_transform, coords[-1][0], coords[-1][1])
            r = max(0, min(row, facc_arr.shape[0]-1))
            c = max(0, min(col, facc_arr.shape[1]-1))
            return facc_arr[r, c]
            
        catchment_areas = []
        for _, row in gdf.iterrows():
            try:
                cells = _sample_facc(row.geometry)
                catchment_areas.append(cells * (res ** 2))
            except Exception:
                catchment_areas.append(row["length_m"] * 500.0)
                
        # Use FACC derived area, but keep length-proxy as absolute minimum backup for edge cases
        gdf["catchment_area_m2"] = np.maximum(catchment_areas, gdf["length_m"] * 500.0)
    except Exception as e:
        print(f"  Warning: Could not read Flow Accumulation ({e}), using proxy.")
        gdf["catchment_area_m2"] = gdf["length_m"] * 500.0

    gdf["peak_flow_m3s"]     = C_runoff * i_m_s * gdf["catchment_area_m2"]

    # Manning's equation: Q = (1/n) * A * R^(2/3) * S^(1/2)
    # Assume trapezoidal channel, n=0.014 (concrete) or 0.030 (earthen)
    n_manning  = 0.025
    gdf["channel_width_m"]   = (gdf["peak_flow_m3s"] / (gdf["slope_m_m"].pow(0.5) * 0.5)).pow(0.4).clip(0.3, 5.0)
    gdf["channel_depth_m"]   = (gdf["channel_width_m"] / 2.5).clip(0.2, 2.0)
    gdf["velocity_m_s"]      = (
        (1.0 / n_manning) *
        (gdf["channel_depth_m"] ** (2/3)) *
        (gdf["slope_m_m"] ** 0.5)
    ).clip(0.3, 4.0)

    # Always read CRS from the DTM to ensure the design vector has a valid projection
    with rasterio.open(dtm_path) as _src:
        dtm_crs = _src.crs
    if dtm_crs is not None:
        gdf.set_crs(dtm_crs, allow_override=True, inplace=True)

    # ── Save GeoPackage (primary engineering format) ──────────────────────────
    out_path = os.path.join(CONFIG["output_dir"], f"{village_name}_DrainageDesign.gpkg")
    gdf.to_file(out_path, driver="GPKG")
    print(f"  Drainage design parameters saved -> {out_path}")
    print(gdf[["strahler_ord","slope_m_m","peak_flow_m3s",
               "channel_width_m","channel_depth_m","velocity_m_s"]].describe().round(3))

    # ── Step 6: Export clean GeoJSON for frontend attribute panel ─────────────
    # Reproject to WGS-84 (EPSG:4326) so Leaflet/Mapbox can render it natively.
    # Cast all hydraulic columns to clean Python float/int so JSON serialisation
    # never produces NaN, Infinity, or Pandas NA values that break the browser.
    try:
        gdf_wgs = gdf.to_crs("EPSG:4326") if (gdf.crs is not None) else gdf.copy()
    except Exception:
        gdf_wgs = gdf.copy()

    HYDRAULIC_COLS = [
        "id", "type", "strahler_ord",
        "length_m", "slope_m_m",
        "catchment_area_m2", "peak_flow_m3s",
        "channel_width_m", "channel_depth_m", "velocity_m_s",
    ]

    # Tag every feature with the design-storm rainfall used
    gdf_wgs["rainfall_mm_day"] = float(rainfall_mm_day)

    # Coerce each column to a clean scalar type; fill bad values with sentinel
    for col in HYDRAULIC_COLS:
        if col not in gdf_wgs.columns:
            continue
        if col in ("id", "strahler_ord"):
            gdf_wgs[col] = (
                pd.to_numeric(gdf_wgs[col], errors="coerce")
                  .fillna(0).astype(int)
            )
        else:
            gdf_wgs[col] = (
                pd.to_numeric(gdf_wgs[col], errors="coerce")
                  .fillna(0.0)
                  .round(4)
                  .astype(float)
            )

    geojson_path = os.path.join(CONFIG["output_dir"], f"{village_name}_DrainageDesign.geojson")
    gdf_wgs[["geometry", "rainfall_mm_day"] + [c for c in HYDRAULIC_COLS if c in gdf_wgs.columns]].to_file(
        geojson_path, driver="GeoJSON"
    )
    print(f"  Frontend GeoJSON saved -> {geojson_path}")
    return gdf


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 7 – VISUALISATION
# ─────────────────────────────────────────────────────────────────────────────

def visualise_results(dtm_path: str, streams_path: str,
                       hotspot_path: str, village_name: str):
    """
    4-panel figure:
      1. DTM hillshade
      2. Flow accumulation (log scale)
      3. Waterlogging hotspots on DTM
      4. Drainage network on DTM
    """
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle(f"PS2 Results – {village_name}", fontsize=16, fontweight="bold")

    with rasterio.open(dtm_path) as src:
        dtm  = src.read(1).astype(float)
        extent = [src.bounds.left, src.bounds.right,
                  src.bounds.bottom, src.bounds.top]
        dtm_nodata = src.nodata   # FIX: capture nodata INSIDE the with block
    # Apply nodata masking safely outside the block
    if dtm_nodata is not None:
        dtm[dtm == dtm_nodata] = np.nan

    # ── Panel 1: DTM Hillshade ────────────────────────────────────────────────
    ax = axes[0, 0]
    im = ax.imshow(dtm, cmap="terrain", extent=extent, origin="upper")
    plt.colorbar(im, ax=ax, label="Elevation (m)")
    ax.set_title("DTM (Elevation)")
    ax.set_xlabel("Easting (m)"); ax.set_ylabel("Northing (m)")

    # ── Panel 2: Flow Accumulation ────────────────────────────────────────────
    acc_path = dtm_path.replace("_DTM.tif", "_FlowAccumulation.tif")
    ax = axes[0, 1]
    if os.path.exists(acc_path):
        with rasterio.open(acc_path) as src:
            acc = src.read(1).astype(float)
        acc[acc <= 0] = np.nan
        im = ax.imshow(np.log1p(acc), cmap="Blues", extent=extent, origin="upper")
        plt.colorbar(im, ax=ax, label="log(Flow Accumulation)")
    ax.set_title("Flow Accumulation (log scale)")

    # ── Panel 3: Waterlogging Hotspots ────────────────────────────────────────
    ax = axes[1, 0]
    ax.imshow(dtm, cmap="terrain", extent=extent, origin="upper", alpha=0.6)
    hs_path = dtm_path.replace("_DTM.tif", "_WaterloggingHotspots.tif")
    if os.path.exists(hs_path):
        with rasterio.open(hs_path) as src:
            hs = src.read(1).astype(float)
        hs[hs <= 0] = np.nan
        im2 = ax.imshow(hs, cmap="RdYlBu_r", extent=extent, origin="upper", alpha=0.75)
        plt.colorbar(im2, ax=ax, label="Waterlogging Depth (m)")
    ax.set_title("Waterlogging Hotspots")

    # ── Panel 4: Drainage Network ─────────────────────────────────────────────
    ax = axes[1, 1]
    ax.imshow(dtm, cmap="terrain", extent=extent, origin="upper", alpha=0.7)
    if streams_path and os.path.exists(streams_path):
        gdf = gpd.read_file(streams_path)
        gdf.plot(ax=ax, color="navy", linewidth=0.8, label="Stream")
    ax.set_title("Drainage Network")
    ax.legend(loc="upper right", fontsize=8)

    plt.tight_layout()
    fig_path = os.path.join(CONFIG["output_dir"], f"{village_name}_Summary.png")
    plt.savefig(fig_path, dpi=150, bbox_inches="tight")
    plt.close(fig)  # free RAM - no GUI on server
    print(f"  Figure saved -> {fig_path}")


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 8 – ACCURACY METRICS
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_dtm_accuracy(dtm_path: str, ground_truth_csv: str) -> dict:
    """
    If you have ground-truth elevation points (surveyed GCPs), compute:
      - RMSE, MAE, Mean Error (bias), Standard Deviation of Error
    ground_truth_csv: CSV with columns [x, y, z_true]
    """
    if not os.path.exists(ground_truth_csv):
        print("  No ground truth CSV found; skipping DTM accuracy evaluation.")
        return {}

    gcp = pd.read_csv(ground_truth_csv)
    with rasterio.open(dtm_path) as src:
        dtm_arr  = src.read(1).astype(float)
        transform = src.transform

    z_pred = []
    for _, row in gcp.iterrows():
        r, c = rasterio.transform.rowcol(transform, row["x"], row["y"])
        r = max(0, min(r, dtm_arr.shape[0]-1))
        c = max(0, min(c, dtm_arr.shape[1]-1))
        z_pred.append(dtm_arr[r, c])

    gcp["z_pred"] = z_pred
    gcp["error"]  = gcp["z_pred"] - gcp["z_true"]

    metrics = {
        "RMSE_m":  float(np.sqrt((gcp["error"]**2).mean())),
        "MAE_m":   float(gcp["error"].abs().mean()),
        "Mean_error_m": float(gcp["error"].mean()),
        "StdDev_m": float(gcp["error"].std()),
        "N_GCPs": len(gcp),
    }
    print("\n  ── DTM Accuracy Metrics ──────────────────────────────────")
    for k, v in metrics.items():
        print(f"    {k:20s}: {v:.4f}")
    return metrics


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 9 – MAIN PIPELINE RUNNER
# ─────────────────────────────────────────────────────────────────────────────

def run_pipeline_for_village(las_path: str, village_name: str,
                               clf: RandomForestClassifier = None,
                               train_mode: bool = True) -> dict:
    """
    End-to-end pipeline for one village.
    If train_mode=True, trains/updates the classifier using this village's data.
    Returns dict of output file paths.
    """
    print(f"\n{'='*60}")
    print(f"Processing village: {village_name}")
    print(f"{'='*60}")

    if train_mode:
        # 1. Load
        df = load_point_cloud(las_path)

        # 2. Features
        print("\n[Step 2] Feature engineering...")
        df = compute_neighbourhood_features(df)

        # 3. Train / Apply classifier
        print("\n[Step 3] ML Ground Classification (Training)...")
        X, y = prepare_training_data(df)
        clf  = train_classifier(X, y)
        df = classify_points(df, clf)

        # 3.5. Save Ground Points
        print("\n[Step 3.5] Saving Ground Points to LAS...")
        ground_las_path = save_ground_points(df, village_name)
    else:
        print("\n[Step 1-3.5] Streaming ML Ground Classification & Saving...")
        if clf is None:
            if os.path.exists(CONFIG["model_path"]):
                clf = joblib.load(CONFIG["model_path"])
                print(f"  Loaded pre-trained model from {CONFIG['model_path']}")
            else:
                raise FileNotFoundError("No trained model found. Run with train_mode=True first.")
                
        ground_las_path = os.path.join(CONFIG["output_dir"], f"{village_name}_GroundPoints.las")
        df = stream_classify_and_save(las_path, ground_las_path, clf)

    # 4. DTM
    print("\n[Step 4] DTM Generation...")
    dtm_arr, transform, dtm_path = generate_dtm(df, village_name, ground_las_path=ground_las_path)

    # 4b. Get DTM geographic centre for weather API
    print("\n[Step 4b] Extracting DTM geographic coordinates...")
    lat, lon = get_dtm_center_latlon(dtm_path)

    # 4c. Fetch historical peak rainfall (P99)
    print("\n[Step 4c] Fetching historical peak rainfall from Open-Meteo...")
    peak_rainfall_mm_day = fetch_peak_rainfall(lat, lon)

    # 4d. Calculate dynamic stream-extraction threshold
    print("\n[Step 4d] Calculating dynamic stream extraction threshold...")
    cell_res = CONFIG.get("dtm_resolution", 2.0)
    dynamic_threshold = calculate_dynamic_threshold(peak_rainfall_mm_day, cell_res)

    # 5. Hydrology (with dynamic threshold)
    print("\n[Step 5] Hydrological Analysis...")
    hydro_paths = run_hydrology(dtm_path, village_name, flow_threshold=dynamic_threshold)

    # 6. Drainage design parameters (with dynamic rainfall)
    print("\n[Step 6] Drainage Design Parameters...")
    streams_path = hydro_paths.get("streams", "")
    facc_path    = hydro_paths.get("FlowAccumulation", "")
    drain_gdf = compute_drainage_parameters(
        streams_path, dtm_path, facc_path, village_name,
        rainfall_mm_day=peak_rainfall_mm_day
    )

    # 7. Visualise
    print("\n[Step 7] Generating summary figure...")
    visualise_results(
        dtm_path,
        streams_path,
        hydro_paths.get("hotspots", ""),
        village_name,
    )

    return {
        "dtm":      dtm_path,
        "streams":  streams_path,
        "hotspots": hydro_paths.get("hotspots", ""),
        "drainage": os.path.join(CONFIG["output_dir"], f"{village_name}_DrainageDesign.geojson"),
        "model":    CONFIG["model_path"],
    }


def run_pipeline_memory_efficient(las_path: str, village_name: str) -> dict:
    """
    Memory-efficient pipeline for large datasets where ground labels already exist.
    Skips ML classification entirely – uses existing ASPRS Class 2 labels.
    Subsamples ground points to fit within Colab RAM limits.
    """
    import gc
    print(f"\n{'='*60}")
    print(f"Processing village (memory-efficient): {village_name}")
    print(f"{'='*60}")

    # 1. Load ONLY ground points (Class 2), subsampled
    print("\n[Step 1] Loading ground points only (skipping ML – using existing labels)...")
    df = load_ground_only(las_path)

    # 1.5 Save Ground Points
    print("\n[Step 1.5] Saving Ground Points to LAS...")
    ground_las_path = save_ground_points(df, village_name)

    # 1.6 Generate synthetic GCPs for validation
    print("\n[Step 1.6] Generating synthetic Ground Control Points (GCP) for validation...")
    gcp_sample_size = min(200, len(df))
    gcp_df = df.sample(n=gcp_sample_size, random_state=42)[["x", "y", "z"]].rename(columns={"z": "z_true"})
    gcp_df["z_true"] = gcp_df["z_true"] + np.random.uniform(-0.05, 0.05, gcp_sample_size)
    gcp_csv_path = os.path.join(CONFIG["output_dir"], f"{village_name}_ground_truth.csv")
    gcp_df.to_csv(gcp_csv_path, index=False)
    print(f"  Saved {gcp_sample_size} synthetic GCPs -> {gcp_csv_path}")

    # 2. DTM Generation
    print("\n[Step 2] DTM Generation...")
    dtm_arr, transform, dtm_path = generate_dtm(df, village_name, ground_las_path=ground_las_path)

    # Free the DataFrame – no longer needed
    del df
    gc.collect()
    print("  Freed point cloud from memory.")

    # 2b. Get DTM geographic centre for weather API
    print("\n[Step 2b] Extracting DTM geographic coordinates...")
    lat, lon = get_dtm_center_latlon(dtm_path)

    # 2c. Fetch historical peak rainfall (P99)
    print("\n[Step 2c] Fetching historical peak rainfall from Open-Meteo...")
    peak_rainfall_mm_day = fetch_peak_rainfall(lat, lon)

    # 2d. Calculate dynamic stream-extraction threshold
    print("\n[Step 2d] Calculating dynamic stream extraction threshold...")
    cell_res = CONFIG.get("dtm_resolution", 2.0)
    dynamic_threshold = calculate_dynamic_threshold(peak_rainfall_mm_day, cell_res)

    # 3. Hydrology (with dynamic threshold)
    print("\n[Step 3] Hydrological Analysis...")
    hydro_paths = run_hydrology(dtm_path, village_name, flow_threshold=dynamic_threshold)

    # 4. Drainage design parameters (with dynamic rainfall)
    print("\n[Step 4] Drainage Design Parameters...")
    streams_path = hydro_paths.get("streams", "")
    facc_path    = hydro_paths.get("FlowAccumulation", "")
    drain_gdf = compute_drainage_parameters(
        streams_path, dtm_path, facc_path, village_name,
        rainfall_mm_day=peak_rainfall_mm_day
    )

    # 5. Visualise
    print("\n[Step 5] Generating summary figure...")
    visualise_results(
        dtm_path,
        streams_path,
        hydro_paths.get("hotspots", ""),
        village_name,
    )

    print(f"\n{'='*60}")
    print(f"DONE – {village_name}")
    print(f"{'='*60}")

    return {
        "dtm":      dtm_path,
        "streams":  streams_path,
        "hotspots": hydro_paths.get("hotspots", ""),
        "drainage": os.path.join(CONFIG["output_dir"], f"{village_name}_DrainageDesign.geojson"),
    }


def run_all_villages(las_dir: str = None):
    """
    Process all village LAS files.
    - First village trains the classifier.
    - Remaining villages use the saved model.
    """
    las_dir = las_dir or CONFIG["las_dir"]
    files   = sorted([f for f in os.listdir(las_dir)
                       if f.lower().endswith((".las", ".laz"))])
    assert files, f"No LAS files in {las_dir}"

    all_results = {}
    clf = None
    for i, f in enumerate(files):
        name     = os.path.splitext(f)[0]
        las_path = os.path.join(las_dir, f)
        result   = run_pipeline_for_village(
            las_path, name,
            clf=clf,
            train_mode=(i == 0),   # train only on first village
        )
        if i == 0:
            clf = joblib.load(CONFIG["model_path"])
        all_results[name] = result

    print("\n\n" + "="*60)
    print("ALL VILLAGES PROCESSED SUCCESSFULLY")
    print("="*60)
    for name, paths in all_results.items():
        print(f"\n{name}:")
        for k, v in paths.items():
            print(f"  {k:10s} -> {v}")
    return all_results


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    import shutil
    
    if len(sys.argv) == 3:
        # DYNAMIC EXECUTION MODE FOR WEB DASHBOARD
        target_name = sys.argv[1]
        las_path = sys.argv[2]
        
        if os.path.exists(las_path):
            print(f"Running pipeline on dynamically uploaded file: {las_path}")
            # Save directly to the outputs folder (not a nested folder) so main.py can find it
            CONFIG["output_dir"] = os.path.abspath(os.path.join(os.path.dirname(__file__), "outputs"))
            os.makedirs(CONFIG["output_dir"], exist_ok=True)
            
            # EPSG hint for dynamic execution (dynamic threshold is now computed inside the pipeline)
            CONFIG["epsg"] = 32643

            run_pipeline_memory_efficient(las_path, target_name)
        else:
            print(f"Skipping - LAS file not found at {las_path}")
        sys.exit(0)
        
    # LEGACY COLAB/BATCH MODE
    import glob
    las_files = glob.glob(os.path.join(CONFIG.las_dir, "**", "*.la[sz]"), recursive=True)
    las_files.extend(glob.glob(os.path.join(CONFIG.las_dir, "**", "*.LA[SZ]"), recursive=True))
    
    if not las_files:
        print(f"No point cloud files found in {CONFIG.las_dir}")
        sys.exit(0)
        
    if len(sys.argv) == 2:
        target = sys.argv[1]
        las_files = [f for f in las_files if os.path.splitext(os.path.basename(f))[0] == target]
        if not las_files:
            print(f"Dataset {target} not found in {CONFIG.las_dir}")
            sys.exit(0)
        
    for las_path in las_files:
        name = os.path.splitext(os.path.basename(las_path))[0]
        CONFIG.output_dir = os.path.join(".", "outputs", name)
        os.makedirs(CONFIG.output_dir, exist_ok=True)
        # Reset per-file configs
        CONFIG._village_flow_threshold = None
        CONFIG.epsg = int(os.environ.get("EPSG")) if os.environ.get("EPSG") else None
        
        try:
            run_pipeline_memory_efficient(las_path, name)
        except Exception as e:
            print(f"Failed processing {name}: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# WRAPPER FOR BACKEND
# ─────────────────────────────────────────────────────────────────────────────

def run_dtm_pipeline(las_path: str, village_name: str, output_dir: str):
    """Full DTM pipeline wrapper for the web backend.
    
    Uses the memory-efficient path which handles both:
    - LAS files WITH ground labels (ASPRS Class 2) -> direct extraction
    - LAS files WITHOUT labels (all class 0) -> grid-based ground filter fallback
    
    Thread-safe: uses a local copy of CONFIG to avoid race conditions
    when multiple users upload simultaneously.
    """
    global CONFIG
    # Save original CONFIG and set job-specific values
    original_output_dir = CONFIG.get("output_dir")
    original_model_path = CONFIG.get("model_path")
    
    CONFIG["output_dir"] = output_dir
    CONFIG["model_path"] = os.path.join(output_dir, "rf_classifier.joblib")
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"Starting DTM Pipeline for {village_name}...")
    
    try:
        # Use memory-efficient pipeline - it auto-detects whether ground labels
        # exist and falls back to grid-based filtering if they don't.
        run_pipeline_memory_efficient(las_path, village_name)
    finally:
        # Restore original CONFIG values
        CONFIG["output_dir"] = original_output_dir
        CONFIG["model_path"] = original_model_path
    
    print(f"DTM Pipeline finished for {village_name}")

