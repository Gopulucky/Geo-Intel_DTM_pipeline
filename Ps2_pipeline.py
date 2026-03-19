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
  3. DTM Generation                          (IDW interpolation → GeoTIFF)
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

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────
# CELL 3 – Global Config
# ─────────────────────────────────────────────
CONFIG = {
    # Paths
    "las_dir":       "./Andaman_and_Nicobar_Islands_1",   # folder with the .laz file
    "output_dir":    "./outputs",
    "model_path":    "./outputs/rf_classifier.joblib",

    # DTM raster
    "dtm_resolution": 2.0,                  # metres per pixel (2.0m for Colab; use 0.5-1.0 on high-RAM machines)
    "dtm_interp":     "nearest",            # nearest = low RAM; use 'linear' on high-RAM machines

    # ML Classifier
    "rf_n_estimators": 200,
    "rf_max_depth":    20,
    "test_size":       0.2,
    "random_state":    42,

    # Hydrology
    "flow_acc_threshold": 500,              # min flow accumulation cells to form a stream
    "depression_depth_m": 0.3,             # depth threshold for waterlogging hotspot (m)

    # Memory management
    "max_ground_points": 500_000,           # max ground points for DTM interpolation (subsample if larger)

    # CRS – UTM Zone 46N for Andaman and Nicobar Islands (Gandhinagar, Diglipur)
    "epsg": 32646,
}

os.makedirs(CONFIG["output_dir"], exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 1 – POINT CLOUD LOADING
# ─────────────────────────────────────────────────────────────────────────────

def load_point_cloud(las_path: str) -> pd.DataFrame:
    """
    Load a LAS/LAZ file and return a DataFrame of point attributes.
    Columns: x, y, z, intensity, return_number, number_of_returns,
             scan_angle, classification (original, if available)
    """
    las = laspy.read(las_path)
    df = pd.DataFrame({
        "x":               np.array(las.x),
        "y":               np.array(las.y),
        "z":               np.array(las.z),
        "intensity":       np.array(las.intensity).astype(np.float32),
        "return_number":   np.array(las.return_number).astype(np.uint8),
        "num_returns":     np.array(las.number_of_returns).astype(np.uint8),
        "scan_angle":      np.array(las.scan_angle_rank).astype(np.float32),
        "classification":  np.array(las.classification).astype(np.uint8),
    })
    print(f"  Loaded {len(df):,} points from {os.path.basename(las_path)}")
    return df


def load_ground_only(las_path: str, max_points: int = None) -> pd.DataFrame:
    """
    Memory-efficient loader: reads LAZ file in CHUNKS and keeps only
    GROUND points (ASPRS Class 2). The full file is NEVER loaded into
    memory at once — safe for 200M+ point datasets on Colab (12GB RAM).
    """
    import gc
    max_pts = max_points or CONFIG.get("max_ground_points", 500_000)
    chunk_size = 1_000_000   # read 1M points at a time

    print(f"  Reading LAZ file in chunks of {chunk_size:,} (ground only)…")

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
                print(f"    … read {n_total:,} points so far ({n_ground:,} ground)")

    print(f"  Total points: {n_total:,}  |  Ground (class 2): {n_ground:,}")

    # Concatenate all ground chunks
    x = np.concatenate(ground_x); del ground_x
    y = np.concatenate(ground_y); del ground_y
    z = np.concatenate(ground_z); del ground_z
    gc.collect()

    # Subsample if too many ground points
    if len(x) > max_pts:
        print(f"  Subsampling ground points: {len(x):,} → {max_pts:,}")
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
      - height_above_min  (z - local minimum → key ground indicator)
      - slope_approx      (z_std / radius as slope proxy)
      - return_ratio      (return_number / num_returns)
      - last_return       (1 if last return, else 0)
    Uses a fast grid-based approach (no KD-tree needed for large datasets).
    """
    if len(df) > sample_n:
        print(f"  Subsampling to {sample_n:,} points for feature computation…")
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
    print("  Training Random Forest classifier…")
    clf.fit(X_train, y_train)

    y_pred = clf.predict(X_test)
    print(f"\n  Accuracy: {accuracy_score(y_test, y_pred)*100:.2f}%")
    print(classification_report(y_test, y_pred, target_names=["Non-Ground", "Ground"]))

    # Save model
    joblib.dump(clf, CONFIG["model_path"])
    print(f"  Model saved → {CONFIG['model_path']}")
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

def generate_dtm(df: pd.DataFrame, village_name: str,
                 resolution: float = None,
                 method: str = None) -> tuple:
    """
    Generate a DTM raster from classified ground points.
    Uses scipy griddata (linear by default) on ground-only points.

    Returns:
        dtm_array  : 2D numpy array of elevations (NaN for no-data)
        transform  : rasterio Affine transform
        out_path   : path to saved GeoTIFF
    """
    res = resolution or CONFIG["dtm_resolution"]
    interp = method or CONFIG["dtm_interp"]

    gnd = df[df["pred_ground"] == 1][["x", "y", "z"]].copy()
    if len(gnd) < 100:
        raise ValueError("Too few ground points to generate DTM!")

    # Build regular grid
    x_min, x_max = gnd["x"].min(), gnd["x"].max()
    y_min, y_max = gnd["y"].min(), gnd["y"].max()

    grid_x = np.arange(x_min, x_max + res, res)
    grid_y = np.arange(y_min, y_max + res, res)
    gx, gy = np.meshgrid(grid_x, grid_y)

    print(f"  Interpolating DTM ({len(grid_x)}×{len(grid_y)} px) using '{interp}'…")
    dtm = griddata(
        points=gnd[["x", "y"]].values,
        values=gnd["z"].values,
        xi=(gx, gy),
        method=interp,
        rescale=True,
    )
    dtm = np.flipud(dtm)   # rasterio convention: row 0 = top

    # Save GeoTIFF
    transform = from_bounds(x_min, y_min, x_max, y_max, dtm.shape[1], dtm.shape[0])
    out_path = os.path.join(CONFIG["output_dir"], f"{village_name}_DTM.tif")
    with rasterio.open(
        out_path, "w",
        driver="GTiff",
        height=dtm.shape[0], width=dtm.shape[1],
        count=1, dtype="float32",
        crs=CRS.from_epsg(CONFIG["epsg"]),
        transform=transform,
        nodata=np.nan,
    ) as dst:
        dst.write(dtm.astype(np.float32), 1)

    print(f"  DTM saved → {out_path}")
    return dtm, transform, out_path


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 5 – HYDROLOGICAL ANALYSIS (pysheds)
# ─────────────────────────────────────────────────────────────────────────────

def run_hydrology(dtm_path: str, village_name: str) -> dict:
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
    
    dtm_abs = os.path.abspath(dtm_path)
    paths = {}
    
    def out_file(name):
        return os.path.join(os.path.abspath(CONFIG["output_dir"]), f"{village_name}_{name}")

    breached = out_file("BreachedDTM.tif")
    fdir = out_file("FlowDirection.tif")
    facc = out_file("FlowAccumulation.tif")
    streams_tif = out_file("RasterStreams.tif")
    streams_vec = out_file("Streams.shp")
    sink_depth = out_file("WaterDepth.tif")
    twi = out_file("TWI.tif")
    slope = out_file("Slope.tif")
    sca = out_file("SCA.tif")
    catchments = out_file("Catchments.tif")

    # ── 1. Breach depressions ──────────────────────────────────────────────────
    print("  Breaching depressions to model culverts/drainpaths…")
    wbt.breach_depressions(dem=dtm_abs, output=breached)

    # ── 2. Flow direction & accumulation ─────────────────────────────────────
    print("  Computing flow direction & accumulation (D8)…")
    wbt.d8_pointer(dem=breached, output=fdir)
    wbt.d8_flow_accumulation(i=breached, output=facc, out_type="cells")
    paths["FlowAccumulation"] = facc

    # ── 3. Stream extraction & Watersheds ────────────────────────────────────
    print("  Extracting streams and catchments…")
    wbt.extract_streams(flow_accum=facc, output=streams_tif, threshold=CONFIG["flow_acc_threshold"])
    wbt.raster_streams_to_vector(streams=streams_tif, d8_pntr=fdir, output=streams_vec)
    paths["streams"] = streams_vec
    
    wbt.subbasins(d8_pntr=fdir, streams=streams_tif, output=catchments)
    paths["catchments"] = catchments

    # ── 4. Waterlogging hotspots (Depression + TWI) ──────────────────────────
    print("  Predicting waterlogging zones (Sink Depth & TWI)…")
    wbt.depth_in_sink(dem=dtm_abs, output=sink_depth, zero_background=False)
    paths["WaterloggingDepth"] = sink_depth
    
    wbt.slope(dem=breached, output=slope, units="degrees")
    wbt.d_inf_flow_accumulation(i=breached, output=sca, out_type="sca")
    wbt.wetness_index(sca=sca, slope=slope, output=twi)
    paths["TWI"] = twi

    # Clean up temp files if desired
    for tmp in [sca, slope, streams_tif]:
        if os.path.exists(tmp): os.remove(tmp)

    # Build Hotspots Polygons simply by thresholding depth_in_sink
    with rasterio.open(sink_depth) as src:
        depth_arr = src.read(1)
        depth_arr[depth_arr == src.nodata] = 0
        hotspot_mask = depth_arr > CONFIG["depression_depth_m"]
        
    hotspot_polys = _raster_to_polygons(hotspot_mask, sink_depth, min_area_m2=4.0)
    if hotspot_polys is not None and len(hotspot_polys) > 0:
        hp_path = out_file("WaterloggingHotspots.geojson")
        hotspot_polys.to_file(hp_path, driver="GeoJSON")
        paths["hotspots"] = hp_path
        print(f"  Waterlogging hotspots → {hp_path} ({len(hotspot_polys)} zones)")

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
    return gpd.GeoDataFrame(geometry=geoms, crs=crs)


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 6 – DRAINAGE NETWORK DESIGN PARAMETERS
# ─────────────────────────────────────────────────────────────────────────────

def compute_drainage_parameters(streams_path: str,
                                 dtm_path: str,
                                 village_name: str) -> gpd.GeoDataFrame:
    """
    Augment the stream network with engineering design parameters:
      - Strahler stream order
      - Channel slope (m/m)
      - Catchment area proxy (from flow accumulation)
      - Recommended channel width & depth (rational method proxy)
      - Flow velocity estimate (Manning's equation)
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
    # Q = C * i * A  (simplified; C=0.6 for rural, i=50mm/hr design rain)
    C_runoff   = 0.6
    i_mm_hr    = 50.0
    i_m_s      = i_mm_hr / (1000.0 * 3600.0)
    # Catchment area proxy: assume 500 m² per contributing stream metre
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

    out_path = os.path.join(CONFIG["output_dir"], f"{village_name}_DrainageDesign.geojson")
    gdf.to_file(out_path, driver="GeoJSON")
    print(f"  Drainage design parameters saved → {out_path}")
    print(gdf[["strahler_ord","slope_m_m","peak_flow_m3s",
               "channel_width_m","channel_depth_m","velocity_m_s"]].describe().round(3))
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
    dtm[dtm == src.nodata] = np.nan

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
    hs_path = dtm_path.replace("_DTM.tif", "_WaterloggingDepth.tif")
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
    plt.show()
    print(f"  Figure saved → {fig_path}")


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

    # 1. Load
    df = load_point_cloud(las_path)

    # 2. Features
    print("\n[Step 2] Feature engineering…")
    df = compute_neighbourhood_features(df)

    # 3. Train / Apply classifier
    print("\n[Step 3] ML Ground Classification…")
    if train_mode:
        X, y = prepare_training_data(df)
        clf  = train_classifier(X, y)
    elif clf is None:
        if os.path.exists(CONFIG["model_path"]):
            clf = joblib.load(CONFIG["model_path"])
            print(f"  Loaded pre-trained model from {CONFIG['model_path']}")
        else:
            raise FileNotFoundError("No trained model found. Run with train_mode=True first.")
    df = classify_points(df, clf)

    # 4. DTM
    print("\n[Step 4] DTM Generation…")
    dtm_arr, transform, dtm_path = generate_dtm(df, village_name)

    # 5. Hydrology
    print("\n[Step 5] Hydrological Analysis…")
    hydro_paths = run_hydrology(dtm_path, village_name)

    # 6. Drainage design parameters
    print("\n[Step 6] Drainage Design Parameters…")
    streams_path = hydro_paths.get("streams", "")
    drain_gdf = compute_drainage_parameters(streams_path, dtm_path, village_name)

    # 7. Visualise
    print("\n[Step 7] Generating summary figure…")
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
    print("\n[Step 1] Loading ground points only (skipping ML – using existing labels)…")
    df = load_ground_only(las_path)

    # 2. DTM Generation
    print("\n[Step 2] DTM Generation…")
    dtm_arr, transform, dtm_path = generate_dtm(df, village_name)

    # Free the DataFrame – no longer needed
    del df
    gc.collect()
    print("  Freed point cloud from memory.")

    # 3. Hydrology
    print("\n[Step 3] Hydrological Analysis…")
    hydro_paths = run_hydrology(dtm_path, village_name)

    # 4. Drainage design parameters
    print("\n[Step 4] Drainage Design Parameters…")
    streams_path = hydro_paths.get("streams", "")
    drain_gdf = compute_drainage_parameters(streams_path, dtm_path, village_name)

    # 5. Visualise
    print("\n[Step 5] Generating summary figure…")
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
            print(f"  {k:10s} → {v}")
    return all_results


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # ── RECOMMENDED: Memory-efficient mode (for Colab / large datasets) ──────
    # Uses existing ground labels (Class 2), skips ML, subsamples to save RAM
    result = run_pipeline_memory_efficient(
        "./Andaman_and_Nicobar_Islands_1/Gandhinagar_Diglipur_group1_densified_point_cloud.laz",
        "Gandhinagar_Diglipur"
    )

    # ── OPTION B: Full ML pipeline (needs more RAM) ──────────────────────────
    # result = run_pipeline_for_village(
    #     "./Andaman_and_Nicobar_Islands_1/Gandhinagar_Diglipur_group1_densified_point_cloud.laz",
    #     "Gandhinagar_Diglipur", train_mode=True
    # )

    # ── OPTION C: DTM accuracy check (if GCP CSV available) ──────────────────
    # evaluate_dtm_accuracy("./outputs/Gandhinagar_Diglipur_DTM.tif", "./data/GCPs.csv")