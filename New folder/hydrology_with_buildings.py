import os
import sys
import numpy as np
import pandas as pd
import laspy
from scipy.interpolate import griddata
import rasterio
from rasterio.transform import from_bounds
from rasterio.crs import CRS
import whitebox
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.colors import LinearSegmentedColormap
import matplotlib.colors

import glob

if len(sys.argv) < 2:
    print("Usage: python hydrology_with_buildings.py <village_name>")
    sys.exit(1)

village_name = sys.argv[1]
base_dir = os.environ.get("BASE_DIR", os.path.abspath(os.path.dirname(__file__)))
input_dir = os.environ.get("INPUTS_DIR", os.path.join(base_dir, "input_data"))
output_base = os.environ.get("OUTPUTS_DIR", os.path.join(base_dir, "outputs"))

output_dir = os.path.join(output_base, village_name)
os.makedirs(output_dir, exist_ok=True)

# Find LAS file
las_paths = glob.glob(os.path.join(input_dir, "**", f"*{village_name}*.[lL][aA][sSzZ]"), recursive=True)
if not las_paths:
    print(f"Error: Could not find point cloud for {village_name} in {input_dir}")
    sys.exit(1)
input_las = las_paths[0]

# Add pipeline to path to reuse functions
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from GEO_INTEL_pipeline import ensure_metric_crs
except ImportError:
    def ensure_metric_crs(x, y, header=None):
        return x, y

def create_dsm_geotiff(las_path, out_tif, resolution=2.0):
    print(f"Loading LAS: {las_path}")
    las = laspy.read(las_path)
    x, y = ensure_metric_crs(np.array(las.x), np.array(las.y), las.header)
    z = np.array(las.z)
    
    # Subsample if large
    if len(x) > 3000000:
        idx = np.random.choice(len(x), 3000000, replace=False)
        x, y, z = x[idx], y[idx], z[idx]
        
    df = pd.DataFrame({"x": x, "y": y, "z": z})
    
    x_min, x_max = df["x"].min(), df["x"].max()
    y_min, y_max = df["y"].min(), df["y"].max()
    
    grid_x = np.arange(x_min, x_max + resolution, resolution)
    grid_y = np.arange(y_min, y_max + resolution, resolution)
    gx, gy = np.meshgrid(grid_x, grid_y)
    
    xi = ((df["x"] - x_min) / resolution).astype(int)
    yi = ((df["y"] - y_min) / resolution).astype(int)
    df["cell"] = yi * (len(grid_x) + 1) + xi
    
    # 95th percentile captures buildings
    cell_stats = df.groupby("cell")["z"].quantile(0.95)
    
    dsm_sparse_x = []
    dsm_sparse_y = []
    dsm_sparse_z = []
    for cell_id, z_val in cell_stats.items():
        cx = cell_id % (len(grid_x) + 1)
        cy = cell_id // (len(grid_x) + 1)
        if 0 <= cy < len(grid_y) and 0 <= cx < len(grid_x):
            dsm_sparse_x.append(grid_x[cx])
            dsm_sparse_y.append(grid_y[cy])
            dsm_sparse_z.append(z_val)
            
    print("Interpolating DSM...")
    dsm = griddata((dsm_sparse_x, dsm_sparse_y), dsm_sparse_z, (gx, gy), method="linear")
    
    mask_nan = np.isnan(dsm)
    if mask_nan.any():
        dsm_near = griddata((dsm_sparse_x, dsm_sparse_y), dsm_sparse_z, (gx, gy), method="nearest")
        dsm[mask_nan] = dsm_near[mask_nan]
        
    dsm = np.flipud(dsm)
    transform = from_bounds(x_min, y_min, x_max, y_max, dsm.shape[1], dsm.shape[0])
    
    epsg = 32643
    if hasattr(las.header, 'parse_crs'):
        try:
            crs = las.header.parse_crs()
            if crs and crs.to_epsg():
                epsg = crs.to_epsg()
        except: pass

    with rasterio.open(
        out_tif, "w", driver="GTiff", height=dsm.shape[0], width=dsm.shape[1],
        count=1, dtype="float32", crs=CRS.from_epsg(epsg), transform=transform, nodata=-9999.0
    ) as dst:
        dst.write(dsm.astype(np.float32), 1)
        
    return dsm, transform

def run_hydrology(dsm_tif, out_dir):
    wbt = whitebox.WhiteboxTools()
    wbt.set_working_dir(out_dir)
    wbt.set_verbose_mode(False)
    
    dsm_base = os.path.basename(dsm_tif)
    breached = "DSM_Breached.tif"
    fdir = "DSM_FlowDir.tif"
    facc = "DSM_FlowAcc.tif"
    sink = "DSM_SinkDepth.tif"
    streams = "DSM_Streams.tif"
    
    print("Running WhiteboxTools on DSM (with buildings)...")
    wbt.breach_depressions(dem=dsm_base, output=breached)
    wbt.d8_pointer(dem=breached, output=fdir)
    wbt.d8_flow_accumulation(i=breached, output=facc, out_type="cells")
    wbt.depth_in_sink(dem=dsm_base, output=sink, zero_background=True)
    wbt.extract_streams(flow_accum=facc, output=streams, threshold=500)
    
    return {
        "dsm": dsm_tif,
        "facc": os.path.join(out_dir, facc),
        "sink": os.path.join(out_dir, sink)
    }

def animate_hydrology(hydro_paths, out_gif_hotspots, out_gif_streams):
    print("Generating Animations...")
    with rasterio.open(hydro_paths["dsm"]) as src:
        dsm = src.read(1)
        dsm[dsm == src.nodata] = np.nan
        
    with rasterio.open(hydro_paths["facc"]) as src:
        facc = src.read(1)
        facc[facc == src.nodata] = 0
        
    with rasterio.open(hydro_paths["sink"]) as src:
        sink = src.read(1)
        sink[sink == src.nodata] = 0
        
    # Create Hillshade
    ls = matplotlib.colors.LightSource(azdeg=315, altdeg=45)
    hillshade = ls.hillshade(dsm, vert_exag=2)
    
    # Colormaps
    colors_water = [(0, 0, 1, 0), (0, 0, 1, 0.5), (0, 0, 0.8, 0.9)]
    cmap_water = LinearSegmentedColormap.from_list('water', colors_water)
    
    colors_stream = [(0, 1, 1, 0), (0, 1, 1, 0.8), (0, 0.5, 1, 1)]
    cmap_stream = LinearSegmentedColormap.from_list('stream', colors_stream)
    
    # Precompute frames
    num_frames = 60
    max_sink = np.percentile(sink[sink>0], 95) if (sink>0).any() else 1.0
    max_facc = np.percentile(facc[facc>0], 95) if (facc>0).any() else 1000
    
    facc_log = np.log1p(facc)
    max_facc_log = np.log1p(max_facc)
    
    # ─── ANIMATION 1: HOTSPOTS ───
    print("Creating Hotspots Animation...")
    fig1, ax1 = plt.subplots(figsize=(10, 10))
    ax1.axis("off")
    ax1.imshow(hillshade, cmap="gray")
    im_sink = ax1.imshow(np.zeros_like(sink), cmap=cmap_water, vmin=0, vmax=2.0, animated=True)
    
    def update_hotspots(frame):
        progress = frame / num_frames
        current_sink_threshold = max_sink * progress
        sink_frame = np.where(sink > 0, np.minimum(sink, current_sink_threshold), 0)
        im_sink.set_array(sink_frame)
        return [im_sink]
        
    ani1 = animation.FuncAnimation(fig1, update_hotspots, frames=num_frames, interval=100, blit=True)
    ani1.save(out_gif_hotspots, writer="pillow", fps=15)
    print(f"Saved Hotspots animation to {out_gif_hotspots}")
    plt.close(fig1)

    # ─── ANIMATION 2: STREAMS ───
    print("Creating Streams Animation...")
    fig2, ax2 = plt.subplots(figsize=(10, 10))
    ax2.axis("off")
    ax2.imshow(hillshade, cmap="gray")
    im_stream = ax2.imshow(np.zeros_like(facc), cmap=cmap_stream, vmin=0, vmax=1, animated=True)
    
    def update_streams(frame):
        progress = frame / num_frames
        stream_frame = np.where(facc_log > (max_facc_log * (1.0 - progress)), facc_log / max_facc_log, 0)
        im_stream.set_array(stream_frame)
        return [im_stream]
        
    ani2 = animation.FuncAnimation(fig2, update_streams, frames=num_frames, interval=100, blit=True)
    ani2.save(out_gif_streams, writer="pillow", fps=15)
    print(f"Saved Streams animation to {out_gif_streams}")
    plt.close(fig2)

if __name__ == "__main__":
    dsm_tif = os.path.join(output_dir, f"{village_name}_DSM.tif")
    out_gif_hotspots = os.path.join(output_dir, f"{village_name}_Hydrology_Animation_Hotspots.gif")
    out_gif_streams = os.path.join(output_dir, f"{village_name}_Hydrology_Animation_Streams.gif")
    
    # We can skip recreating the DSM if it exists to save time, but for completeness:
    if not os.path.exists(dsm_tif):
        create_dsm_geotiff(input_las, dsm_tif)
        run_hydrology(dsm_tif, output_dir)
        
    # Always get paths assuming hydrology files exist
    hydro_paths = {
        "dsm": dsm_tif,
        "facc": os.path.join(output_dir, "DSM_FlowAcc.tif"),
        "sink": os.path.join(output_dir, "DSM_SinkDepth.tif")
    }
    animate_hydrology(hydro_paths, out_gif_hotspots, out_gif_streams)
