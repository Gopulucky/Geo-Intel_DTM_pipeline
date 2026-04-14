import os
import geopandas as gpd
from shapely.geometry import LineString, MultiLineString
import rasterio
import whitebox
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np

def setup_whitebox(working_dir):
    """Initializes WhiteboxTools and sets the working directory."""
    wbt = whitebox.WhiteboxTools()
    abs_work_dir = os.path.abspath(working_dir)
    wbt.set_working_dir(abs_work_dir)
    # Set verbose to False to avoid crashing Colab output with too much text
    wbt.set_verbose_mode(False) 
    print(f"WhiteboxTools initialized. Working directory: {abs_work_dir}")
    return wbt

def verify_metric_crs(dtm_path):
    """Checks if the CRS is metric (e.g., UTM) to ensure accurate spatial math."""
    with rasterio.open(dtm_path) as src:
        crs = src.crs
        if crs is None:
            print("⚠️ WARNING: No CRS found in DTM! Spatial calculations will fail.")
            return None
        if crs.is_geographic:
            print(f"🚨 CRITICAL ERROR: DTM is in Geographic CRS ({crs}). Must be projected (Metric)!")
            return None
        else:
            print(f"✅ Metric CRS confirmed: {crs}")
            return crs

def step1_hydrological_breaching(wbt, dtm_file, breached_file):
    """
    Phase 4: Hydrological Enforcement (Breaching)
    Instead of filling all depressions (which turns raised roads into dams),
    we 'breach' them. This carves simulated culverts through roads.
    Very memory efficient (runs in Rust backend).
    """
    print("⏳ Running Breach Depressions (simulating culverts through roads)...")
    # Breach depressions is much better than filling pits for road-heavy village DTMs
    wbt.breach_depressions(
        dem=dtm_file,
        output=breached_file,
        flat_increment=0.001
    )
    print(f"✅ Breached DTM saved to: {breached_file}")

def step2_flow_modeling(wbt, breached_file, fdir_file, facc_file):
    """
    Phase 3: Compute D8 Flow Direction and Flow Accumulation.
    """
    print("⏳ Computing D8 Flow Direction...")
    wbt.d8_pointer(
        dem=breached_file,
        output=fdir_file
    )
    print(f"✅ Flow Direction saved to: {fdir_file}")

    print("⏳ Computing D8 Flow Accumulation (cell count)...")
    wbt.d8_flow_accumulation(
        i=breached_file,
        output=facc_file,
        out_type="cells"
    )
    print(f"✅ Flow Accumulation saved to: {facc_file}")

def step3_stream_extraction_and_smoothing(wbt, facc_file, fdir_file, raster_streams_file, vector_streams_file, threshold=500, simplify_tolerance=1.5, min_dangle_length=15.0, dtm_crs=None):
    """
    Extract streams based on a threshold, convert to vector, and remove jagged edges/dangles.
    """
    current_thresh = threshold
    vector_path = os.path.join(wbt.work_dir, vector_streams_file)
    
    while current_thresh >= 10:
        print(f"⏳ Extracting streams (Threshold > {current_thresh} cells)...")
        wbt.extract_streams(
            flow_accum=facc_file,
            output=raster_streams_file,
            threshold=current_thresh
        )
        
        print("⏳ Converting raster streams to vector...")
        wbt.raster_streams_to_vector(
            streams=raster_streams_file,
            d8_pntr=fdir_file,
            output=vector_streams_file
        )
        
        if os.path.exists(vector_path):
            try:
                if len(gpd.read_file(vector_path)) > 0:
                    break
            except Exception:
                pass
                
        print(f"⚠️ No streams extracted at threshold {current_thresh}. Halving and retrying...")
        current_thresh //= 2
    
    # --- Vector Smoothing and Cleanup (Geopandas) ---
    print("⏳ Smoothing streams and removing dangles...")
    
    if not os.path.exists(vector_path):
        print(f"⚠️ Vector streams file not created: {vector_path}. No streams extracted or WBT failed.")
        return vector_streams_file
        
    gdf = gpd.read_file(vector_path)
    
    if len(gdf) > 0:
        # 1. Simplify geometry (Douglas-Peucker algorithm) to remove jagged pixel steps
        gdf["geometry"] = gdf["geometry"].simplify(simplify_tolerance)
        
        # 2. Remove Dangles (short branches that go nowhere)
        # Assuming the 'STRM_VAL' or similar comes from Whitebox, we check line length
        gdf["length_m"] = gdf.geometry.length
        
        # Keep lines that are longer than our dangle threshold or are part of major streams
        gdf = gdf[gdf["length_m"] > min_dangle_length].copy()
        
        if dtm_crs is not None:
            gdf.set_crs(dtm_crs, allow_override=True, inplace=True)
            
        # Save cleaned streams
        clean_streams_file = vector_streams_file.replace(".shp", "_Clean.gpkg")
        clean_path = os.path.join(wbt.work_dir, clean_streams_file)
        gdf.to_file(clean_path, driver="GPKG")
        print(f"✅ Cleaned and smoothed stream network saved to: {clean_streams_file}")
        return clean_streams_file
    else:
        print("⚠️ No streams were extracted! Try lowering the accumulation threshold.")
        return vector_streams_file

def step4_waterlogging_hotspots(wbt, dtm_file, breached_file, twi_file, slope_file, sink_depth_file):
    """
    Phase 3: Identify waterlogging zones using Slope, TWI, and Sink Depths.
    """
    print("⏳ Computing Slope...")
    wbt.slope(dem=breached_file, output=slope_file, units="degrees")
    
    print("⏳ Computing Specific Catchment Area (SCA) for TWI...")
    sca_file = "temp_sca.tif"
    wbt.d_inf_flow_accumulation(i=breached_file, output="temp_sca.tif", out_type="sca")
    
    print("⏳ Computing Topographic Wetness Index (TWI)...")
    # TWI represents where water naturally accumulates based on slope and upslope drainage area
    wbt.wetness_index(sca=sca_file, slope=slope_file, output=twi_file)
    
    print("⏳ Computing Sink Depths (Ponds and Depressions)...")
    # FIX: use breached_file so waterlogging depth aligns with the flow network
    wbt.depth_in_sink(dem=breached_file, output=sink_depth_file, zero_background=False)

    # Cleanup temp file
    if os.path.exists(os.path.join(wbt.work_dir, sca_file)):
        os.remove(os.path.join(wbt.work_dir, sca_file))
        
    print(f"✅ TWI Hotspot Map saved to: {twi_file}")
    print(f"✅ Sink Depths (Ponds) saved to: {sink_depth_file}")

def step5_pour_points_and_catchments(wbt, fdir_file, streams_file, watersheds_file):
    """
    Phase 3/4: Define Pour points (outlets) and delineate watersheds.
    Automatically identifies catchment boundaries for the stream network.
    """
    print("⏳ Delineating Subbasins for Stream Network...")
    wbt.subbasins(d8_pntr=fdir_file, streams=streams_file, output=watersheds_file)
    print(f"✅ Watershed catchments saved to: {watersheds_file}")

def render_colab_outputs(dtm_file, facc_file, streams_file, twi_file, sink_depth_file, watersheds_file):
    """
    Renders the outputs directly in the Google Colab interface using Matplotlib.
    Applies custom colormaps and styling to prevent 'all white' rasters.
    """
    print("\n⏳ Generating Visualizations for Colab Output...")
    fig, axs = plt.subplots(2, 2, figsize=(16, 14))
    
    # Helper to plot raster with transparent nodata
    def plot_raster(ax, file_path, cmap, title, norm=None, mask_val=None, alpha=1.0):
        if not os.path.exists(file_path):
            ax.set_title(f"{title} (File Not Found)")
            ax.axis('off')
            return
            
        with rasterio.open(file_path) as src:
            arr = src.read(1).astype(float)
            nodata = src.nodata
            
            if nodata is not None:
                arr[arr == nodata] = np.nan
            if mask_val is not None:
                arr[arr <= mask_val] = np.nan
                
            masked = np.ma.masked_invalid(arr)
            im = ax.imshow(masked, cmap=cmap, norm=norm, origin='upper', alpha=alpha)
            ax.set_title(title)
            ax.axis('off')
            fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    # 1. Flow Accumulation
    if os.path.exists(facc_file):
        with rasterio.open(facc_file) as src:
            facc_arr = src.read(1).astype(float)
            if src.nodata: facc_arr[facc_arr == src.nodata] = np.nan
            masked = np.ma.masked_invalid(facc_arr)
            masked = np.ma.masked_less_equal(masked, 10) # Hide tiny flows
            if masked.count() > 0:
                norm = mcolors.LogNorm(vmin=max(1, masked.min()), vmax=masked.max())
                im = axs[0, 0].imshow(masked, cmap='Blues', norm=norm, origin='upper')
                axs[0, 0].set_title("Flow Accumulation (Log Scale)")
                axs[0, 0].axis('off')
                fig.colorbar(im, ax=axs[0, 0], fraction=0.046, pad=0.04)
    
    # 2. Extracted Streams (Fixing the 'white mask' issue)
    # Give streams a nice blue color and full transparency everywhere else
    plot_raster(axs[0, 1], streams_file, cmap='Blues_r', title="Extracted Stream Network", mask_val=0.5)

    # 3. Waterlogging Depths (Ponds)
    # Masking out very shallow puddles < 5cm to emphasize real ponds
    plot_raster(axs[1, 0], sink_depth_file, cmap='PuBu', title="Sink Depths (Pond/Waterlogging)", mask_val=0.05)
    
    # 4. Watersheds / Catchments
    plot_raster(axs[1, 1], watersheds_file, cmap='tab20', title="Delineated Catchments (Subbasins)")

    plt.tight_layout()
    plt.show()

# --- MAIN RUNNER FOR COLAB ---

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

def run_village_pipeline(work_dir: str, dtm_filename: str,
                         stream_threshold: int = 1000):
    """
    Run the full hydrology pipeline for one village DTM.

    Args:
        work_dir        : Folder that contains the DTM and receives all outputs.
        dtm_filename    : Filename of the village DTM inside work_dir
                          (e.g. 'DEVDI_511671_DTM.tif').
        stream_threshold: Flow-accumulation cell count to form a stream.
                          Lower  → more / finer streams.
                          Higher → only major channels.
    """
    dtm_path = os.path.join(work_dir, dtm_filename)
    if not os.path.exists(dtm_path):
        print(f"⚠️  DTM not found: {dtm_path}  – skipping this village.")
        return

    # ── Auto-generate output file names from the DTM prefix ──────────────────
    pfx            = dtm_filename.replace("_DTM.tif", "")
    BREACHED_DTM   = f"{pfx}_BreachedDTM.tif"
    FDIR           = f"{pfx}_FlowDirection.tif"
    FACC           = f"{pfx}_FlowAccumulation.tif"
    RASTER_STREAMS = f"{pfx}_DrainageNetwork.tif"
    VECTOR_STREAMS = f"{pfx}_Streams.shp"
    SLOPE          = f"{pfx}_Slope.tif"
    TWI            = f"{pfx}_TWI.tif"
    WATER_DEPTH    = f"{pfx}_WaterloggingHotspots.tif"
    WATERSHEDS     = f"{pfx}_Catchments.tif"

    print(f"\n{'='*60}")
    print(f"  HYDROLOGY PIPELINE  →  {pfx}")
    print(f"  Stream threshold    →  {stream_threshold} cells")
    print(f"{'='*60}")

    wbt = setup_whitebox(work_dir)

    dtm_crs = verify_metric_crs(dtm_path)
    if dtm_crs is None:
        print(f"🚨 CRS check failed for {dtm_filename} – aborting this village.")
        return

    step1_hydrological_breaching(wbt, dtm_filename, BREACHED_DTM)
    step2_flow_modeling(wbt, BREACHED_DTM, FDIR, FACC)
    step3_stream_extraction_and_smoothing(
        wbt, FACC, FDIR, RASTER_STREAMS, VECTOR_STREAMS,
        threshold=stream_threshold, dtm_crs=dtm_crs
    )
    step4_waterlogging_hotspots(wbt, dtm_filename, BREACHED_DTM, TWI, SLOPE, WATER_DEPTH)
    step5_pour_points_and_catchments(wbt, FDIR, RASTER_STREAMS, WATERSHEDS)

    print("⏳ Fixing projection metadata for GeoTIFFs...")
    for out_tif in [BREACHED_DTM, FDIR, FACC, RASTER_STREAMS, SLOPE, TWI, WATER_DEPTH, WATERSHEDS]:
        fix_raster_crs(os.path.join(work_dir, out_tif), dtm_path)

    print(f"\n🎉 {pfx} – ALL STEPS COMPLETED SUCCESSFULLY!")

    render_colab_outputs(
        dtm_path,
        os.path.join(work_dir, FACC),
        os.path.join(work_dir, RASTER_STREAMS),
        os.path.join(work_dir, TWI),
        os.path.join(work_dir, WATER_DEPTH),
        os.path.join(work_dir, WATERSHEDS),
    )


if __name__ == "__main__":
    import sys
    WORK_DIR = os.path.join(os.getcwd(), 'outputs')

    VILLAGES = [
        {"name": "DEVDI_511671", "stream_threshold": 500},
        {"name": "KHAPRETA_510206", "stream_threshold": 300},
        {"name": "Dhal_Hoshiarpur_31235", "stream_threshold": 500},
        {"name": "DHUNDA_FATEHGARH_SAHIB_32619", "stream_threshold": 500},
        {"name": "67169_5NKR_CHAKHIRASINGH", "stream_threshold": 500},
        {"name": "64334_2H_REFLIGHT", "stream_threshold": 500},
        {"name": "PIRAYANKUPPAM", "stream_threshold": 500},
        {"name": "THANDALAM", "stream_threshold": 500},
        {"name": "Gandhinagar_Diglipur", "stream_threshold": 500},
        {"name": "Kadamtala_Rangat", "stream_threshold": 500},
    ]

    if len(sys.argv) > 1:
        target = sys.argv[1]
        VILLAGES = [v for v in VILLAGES if v["name"] == target]

    for v in VILLAGES:
        village_work_dir = os.path.join(WORK_DIR, v["name"])
        os.makedirs(village_work_dir, exist_ok=True)
        dtm_filename = f"{v['name']}_DTM.tif"
        if os.path.exists(os.path.join(village_work_dir, dtm_filename)):
            run_village_pipeline(
                work_dir         = village_work_dir,
                dtm_filename     = dtm_filename,
                stream_threshold = v["stream_threshold"],
            )
        else:
            print(f"Skipping {v['name']} - DTM file not found at {os.path.join(village_work_dir, dtm_filename)}")
