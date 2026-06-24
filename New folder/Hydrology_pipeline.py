import os
import geopandas as gpd
from shapely.geometry import LineString, MultiLineString
import rasterio
import whitebox
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np


import pandas as pd
import laspy
from scipy.interpolate import griddata
from rasterio.transform import from_bounds
from rasterio.crs import CRS
import matplotlib.animation as animation
from matplotlib.colors import LinearSegmentedColormap

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

def step4_waterlogging_hotspots(wbt, dtm_file, breached_file, streams_file, twi_file, slope_file, sink_depth_file, hand_file):
    """
    Phase 3: Identify waterlogging zones using Slope, TWI, Sink Depths, and HAND.
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
    # Use the ORIGINAL (unbreached) DTM — breaching removes all depressions,
    # so depth_in_sink on a breached DTM returns empty data.
    wbt.depth_in_sink(dem=dtm_file, output=sink_depth_file, zero_background=False)

    print("⏳ Computing Height Above Nearest Drainage (HAND)...")
    wbt.elevation_above_stream(dem=breached_file, streams=streams_file, output=hand_file)

    # Cleanup temp file
    if os.path.exists(os.path.join(wbt.work_dir, sca_file)):
        os.remove(os.path.join(wbt.work_dir, sca_file))
        
    print(f"✅ TWI Hotspot Map saved to: {twi_file}")
    print(f"✅ Sink Depths (Ponds) saved to: {sink_depth_file}")
    print(f"✅ HAND saved to: {hand_file}")

def step6_flood_vulnerability_and_drainage(wbt, dtm_file, twi_file, slope_file, hand_file, streams_file, flood_vuln_file, cost_file, targets_file, cost_dist_file, backlink_file, drain_raster_file, drain_vector_file, fdir_file):
    """
    Phase 5: Compute Hybrid Flood Vulnerability Index and Route Alternate Drainage Pathways
    """
    print("⏳ Computing Flood Vulnerability Index and Alternate Drainage Paths...")
    import rasterio
    import numpy as np
    import warnings
    
    def get_path(f):
        return os.path.join(wbt.work_dir, f)
        
    def load_raster(path):
        with rasterio.open(path) as src:
            arr = src.read(1).astype("float32")
            nodata = src.nodata
        if nodata is not None:
            arr[arr == nodata] = np.nan
        return arr, src.meta.copy()
        
    def normalize(x):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=RuntimeWarning)
            min_val = np.nanmin(x)
            max_val = np.nanmax(x)
            if max_val == min_val:
                return np.zeros_like(x)
            return (x - min_val) / (max_val - min_val)

    dem, meta = load_raster(get_path(dtm_file))
    slope_arr, _ = load_raster(get_path(slope_file))
    twi_arr, _ = load_raster(get_path(twi_file))
    hand_arr, _ = load_raster(get_path(hand_file))
    streams_arr, _ = load_raster(get_path(streams_file))

    twi_n = normalize(twi_arr)
    slope_n = 1.0 - normalize(slope_arr)
    elev_n = 1.0 - normalize(dem)
    hand_n = 1.0 - normalize(hand_arr)

    index = (twi_n + slope_n + elev_n + hand_n) / 4.0
    index[np.isnan(dem)] = np.nan

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        threshold = np.nanpercentile(index, 70)
        hotspots = index >= threshold

    meta.update(dtype="float32", nodata=np.nan)
    with rasterio.open(get_path(flood_vuln_file), "w", **meta) as dst:
        dst.write(index.astype("float32"), 1)
        
    # Cost surface
    streams_bin = (streams_arr > 0) & (~np.isnan(streams_arr))
    unconnected = hotspots & (~streams_bin)

    cost = 0.5 * slope_n + 0.3 * hand_n + 0.2 * elev_n
    cost[np.isnan(cost)] = 9999.0

    meta.update(dtype="float32", nodata=9999.0)
    with rasterio.open(get_path(cost_file), "w", **meta) as dst:
        dst.write(cost.astype("float32"), 1)
        
    meta.update(dtype="int32", nodata=0)
    with rasterio.open(get_path(targets_file), "w", **meta) as dst:
        dst.write(unconnected.astype("int32"), 1)

    print("⏳ Computing Cost Distance and Pathways...")
    wbt.cost_distance(source=streams_file, cost=cost_file, out_accum=cost_dist_file, out_backlink=backlink_file)
    wbt.cost_pathway(destination=targets_file, backlink=backlink_file, output=drain_raster_file)
    
    # Vectorize drainage
    print("⏳ Vectorizing Alternate Drainage Network...")
    wbt.raster_streams_to_vector(
        streams=drain_raster_file,
        d8_pntr=fdir_file,
        output=drain_vector_file
    )
    print(f"✅ Flood Vulnerability saved to: {flood_vuln_file}")
    print(f"✅ Alternate drainage saved to: {drain_vector_file}")

def step5_pour_points_and_catchments(wbt, fdir_file, streams_file, watersheds_file):
    """
    Phase 3/4: Define Pour points (outlets) and delineate watersheds.
    Automatically identifies catchment boundaries for the stream network.
    """
    print("⏳ Delineating Subbasins for Stream Network...")
    wbt.subbasins(d8_pntr=fdir_file, streams=streams_file, output=watersheds_file)
    print(f"✅ Watershed catchments saved to: {watersheds_file}")

def render_colab_outputs(dtm_file, facc_file, streams_file, twi_file, sink_depth_file, watersheds_file, flood_vuln_file, drain_raster_file, output_path=None):
    """
    Renders the outputs directly in the Google Colab interface using Matplotlib.
    Applies custom colormaps and styling to prevent 'all white' rasters.
    Saves the figure to output_path if provided.
    """
    print("\n⏳ Generating Visualizations for Colab Output...")
    fig, axs = plt.subplots(3, 2, figsize=(16, 21))
    
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
    # Use very low mask to keep shallow depressions visible; log norm for dynamic range
    if os.path.exists(sink_depth_file):
        with rasterio.open(sink_depth_file) as src:
            sd_arr = src.read(1).astype(float)
            if src.nodata is not None:
                sd_arr[sd_arr == src.nodata] = np.nan
            sd_arr[sd_arr <= 0.001] = np.nan  # only mask truly zero values
            masked = np.ma.masked_invalid(sd_arr)
            if masked.count() > 0:
                vmin = max(0.001, float(masked.min()))
                vmax = float(masked.max())
                if vmax > vmin * 10:
                    norm = mcolors.LogNorm(vmin=vmin, vmax=vmax)
                else:
                    norm = None
                im = axs[1, 0].imshow(masked, cmap='PuBu', norm=norm, origin='upper')
                axs[1, 0].set_title("Sink Depths (Pond/Waterlogging)")
                axs[1, 0].axis('off')
                fig.colorbar(im, ax=axs[1, 0], fraction=0.046, pad=0.04)
            else:
                axs[1, 0].set_title("Sink Depths (No significant depressions)")
                axs[1, 0].axis('off')
    else:
        axs[1, 0].set_title("Sink Depths (File Not Found)")
        axs[1, 0].axis('off')
    
    # 4. Watersheds / Catchments
    plot_raster(axs[1, 1], watersheds_file, cmap='tab20', title="Delineated Catchments (Subbasins)")

    # 5. Flood Vulnerability
    plot_raster(axs[2, 0], flood_vuln_file, cmap='RdYlBu_r', title="Flood Vulnerability Index")

    # 6. Alternate Drainage Network
    plot_raster(axs[2, 1], drain_raster_file, cmap='Greens', title="Alternate Drainage Pathways", mask_val=0.5)

    plt.tight_layout()
    if output_path:
        fig.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f"  Hydrology summary figure saved -> {output_path}")
    plt.close(fig)  # free RAM — no GUI on server

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



def consolidate_vectors_to_gpkg(work_dir, pfx, dtm_crs=None):
    """Consolidates all shapefiles and single-layer gpkgs into a single final GPKG.
    
    If dtm_crs is provided, any vector layer missing a CRS will be assigned
    the DTM's CRS before consolidation.  For shapefiles this also writes the
    missing .prj sidecar so individual files work in QGIS too.
    """
    import geopandas as gpd
    import glob
    print("⏳ Consolidating vector outputs into a single GeoPackage...")
    
    final_gpkg = os.path.join(work_dir, f"{pfx}_FinalOutputs.gpkg")
    
    if os.path.exists(final_gpkg):
        os.remove(final_gpkg)
        
    vector_files = glob.glob(os.path.join(work_dir, f"{pfx}_*.shp")) + \
                   [f for f in glob.glob(os.path.join(work_dir, f"{pfx}_*.gpkg")) if "FinalOutputs" not in f]
                   
    for vfile in vector_files:
        try:
            layer_name = os.path.basename(vfile).split('.')[0].replace(f"{pfx}_", "")
            gdf = gpd.read_file(vfile)
            if len(gdf) > 0:
                # Assign the DTM CRS to any vector that lacks one
                if gdf.crs is None and dtm_crs is not None:
                    gdf.set_crs(dtm_crs, allow_override=True, inplace=True)
                    print(f"  [CRS FIX] Set CRS on {layer_name} to {dtm_crs}")
                    # Re-save the individual file so .prj is written for shapefiles
                    if vfile.lower().endswith(".shp"):
                        gdf.to_file(vfile)
                gdf.to_file(final_gpkg, layer=layer_name, driver="GPKG")
                print(f"  Added {layer_name} to FinalOutputs.gpkg")
        except Exception as e:
            print(f"  Warning: Failed to add {vfile} to GPKG: {e}")
            
    print(f"✅ Consolidated GeoPackage saved to: {final_gpkg}")

def convert_all_to_cog(work_dir, pfx):
    """Converts all generated .tif files to Cloud Optimized GeoTIFF (COG)."""
    import glob
    import shutil
    import rasterio
    print("⏳ Converting output rasters to Cloud Optimized GeoTIFF (COG)...")
    
    tif_files = glob.glob(os.path.join(work_dir, f"{pfx}_*.tif"))
    cog_dir = os.path.join(work_dir, "cog")
    os.makedirs(cog_dir, exist_ok=True)
    
    for tfile in tif_files:
        filename = os.path.basename(tfile)
        cog_path = os.path.join(cog_dir, filename)
        
        try:
            with rasterio.open(tfile) as src:
                kwargs = src.meta.copy()
                kwargs.update({
                    'driver': 'COG',
                    'compress': 'LZW'
                })
                data = src.read()
                
            with rasterio.open(cog_path, 'w', **kwargs) as dst:
                dst.write(data)
            
            shutil.move(cog_path, tfile)
            print(f"  Converted {filename} to COG")
        except Exception as e:
            print(f"  Warning: Failed to convert {filename} to COG: {e}")
            
    if os.path.exists(cog_dir) and not os.listdir(cog_dir):
        os.rmdir(cog_dir)
    print("✅ All rasters converted to COG.")

def manning_discharge(width, depth, slope, roughness):
    """Computes minimum discharge automatically from channel geometry."""
    A = width * depth
    wetted_perimeter = width + 2*depth
    R = A / wetted_perimeter
    velocity = (1/roughness) * (R**(2/3)) * (slope**0.5)
    Q = A * velocity
    return Q

def rainfall_based_threshold(
        dtm_path,
        rainfall_intensity_mmhr,
        runoff_coefficient=0.5,
        minimum_discharge=0.1):
    """Compute flow accumulation threshold using Rational Method."""
    with rasterio.open(dtm_path) as src:
        cell_size_x = abs(src.transform[0])
        cell_size_y = abs(src.transform[4])
        cell_area = cell_size_x * cell_size_y

    # Rational Method: Q = CIA -> A = Q / (CI * conversion)
    area_ha = minimum_discharge / (0.00278 * runoff_coefficient * rainfall_intensity_mmhr)

    # hectares to m²
    area_m2 = area_ha * 10000

    # Convert to number of cells
    threshold_cells = int(area_m2 / cell_area)

    return max(10, threshold_cells)

def adjust_waterlogging_depth(water_depth_file: str, current_intensity: float, max_intensity: float):
    """
    Dynamically scales the waterlogging depth based on the rainfall intensity.
    Reduces the extent by subtracting a deficit, and scales the remaining depth.
    """
    if not os.path.exists(water_depth_file):
        return
        
    ratio = min(1.0, current_intensity / max_intensity)
    if ratio >= 0.95:
        return # Flood scenario, keep full depths
        
    print(f"  [Rainfall] Adjusting waterlogging depths (Intensity Ratio: {ratio:.2f})")
    
    deficit_m = 0.5 * (1.0 - ratio) # Max 0.5m deficit at edges
    
    try:
        with rasterio.open(water_depth_file) as src:
            arr = src.read(1).astype(np.float32)
            meta = src.meta.copy()
            nodata = src.nodata
            
        if nodata is None:
            nodata = -9999.0
            
        mask = (arr != nodata) & (arr > 0)
        
        # Subtract deficit
        arr[mask] = arr[mask] - deficit_m
        
        # Floor to 0
        arr[mask & (arr <= 0)] = 0
        
        # Scale remaining
        arr[mask & (arr > 0)] = arr[mask & (arr > 0)] * ratio
        
        # Optional: set 0 to nodata so extent looks smaller in frontend
        arr[arr == 0] = nodata
        
        meta.update(nodata=nodata)
        with rasterio.open(water_depth_file, 'w', **meta) as dst:
            dst.write(arr, 1)
            
    except Exception as e:
        print(f"  [Rainfall] Error adjusting waterlogging depths: {e}")

def run_village_pipeline(work_dir: str, dtm_filename: str,
                         stream_threshold: int = None,
                         fast_path: bool = False,
                         rainfall_scenario: str = "flood"):
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
        
    if stream_threshold is None:
        # 1. Compute minimum discharge using Manning Equation for a small headwater channel
        Qmin = manning_discharge(
            width=0.5,       # 0.5m wide
            depth=0.3,       # 0.3m deep
            slope=0.001,     # typical flat terrain slope
            roughness=0.035  # natural channel with weeds/stones
        )
        print(f"  Physics-based minimum discharge (Manning): {Qmin:.3f} m³/s")
        
        from GEO_INTEL_pipeline import fetch_peak_rainfall, get_dtm_center_latlon
        try:
            lat, lon = get_dtm_center_latlon(dtm_path)
            # Fetch the absolute max and scenario-specific rainfall from 10 years of history
            rainfall_daily = fetch_peak_rainfall(lat, lon, scenario=rainfall_scenario)
            flood_daily    = fetch_peak_rainfall(lat, lon, scenario="flood")
            
            # The Rational Method expects mm/hr, but API returns mm/day.
            # We normalize so the historical MAXIMUM maps to the engineering
            # design baseline of 80 mm/hr (which produces well-known good results).
            # The RATIO between scenarios is preserved from real weather data.
            ENGINEERING_BASELINE = 80.0  # mm/hr — standard Indian drainage design
            if flood_daily > 0:
                rainfall_intensity = (rainfall_daily / flood_daily) * ENGINEERING_BASELINE
            else:
                rainfall_intensity = ENGINEERING_BASELINE
            flood_intensity = ENGINEERING_BASELINE  # max always maps to baseline
            
            print(f"  [Rainfall] Historical daily: {rainfall_daily:.1f} mm/day  "
                  f"(Max: {flood_daily:.1f} mm/day)")
            print(f"  [Rainfall] Normalized engineering intensity: {rainfall_intensity:.1f} mm/hr  "
                  f"(Ratio: {rainfall_daily/flood_daily:.2f})")
        except Exception:
            print("  [Rainfall] Warning: could not fetch dynamic rainfall, defaulting to 80 mm/hr")
            rainfall_intensity = 80.0
            flood_intensity = 80.0

        # 2. Compute the flow accumulation threshold using Rational Method
        stream_threshold = rainfall_based_threshold(
            dtm_path,
            rainfall_intensity_mmhr=rainfall_intensity,
            runoff_coefficient=0.6,       # typical for rural/village areas
            minimum_discharge=Qmin
        )

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
    HAND           = f"{pfx}_HAND.tif"
    FLOOD_VULN     = f"{pfx}_FloodVulnerability.tif"
    COST_SURFACE   = f"{pfx}_CostSurface.tif"
    COST_DIST      = f"{pfx}_CostDistance.tif"
    BACKLINK       = f"{pfx}_Backlink.tif"
    TARGETS        = f"{pfx}_Targets.tif"
    DRAIN_RASTER   = f"{pfx}_AlternateDrainage.tif"
    DRAIN_VECTOR   = f"{pfx}_AlternateDrainage.shp"
    DYNAMIC_RASTER_STREAMS = f"{pfx}_DynamicDrainageNetwork.tif"
    DYNAMIC_VECTOR_STREAMS = f"{pfx}_DynamicStreams.shp"

    # ── Compute comparison metrics: Baseline (i=80) vs Dynamic Weather ────────
    baseline_threshold = rainfall_based_threshold(
        dtm_path,
        rainfall_intensity_mmhr=80.0,
        runoff_coefficient=0.6,
        minimum_discharge=manning_discharge(0.5, 0.3, 0.001, 0.035)
    )
    
    # Collect all metrics for the comparison table
    try:
        ratio = rainfall_daily / flood_daily if flood_daily > 0 else 1.0
        hist_max = flood_daily
        hist_scenario = rainfall_daily
    except NameError:
        ratio = 1.0
        hist_max = None
        hist_scenario = None
    
    try:
        eng_intensity = rainfall_intensity
    except NameError:
        eng_intensity = 80.0

    print(f"\n{'='*72}")
    print(f"  HYDROLOGY PIPELINE  ->  {pfx}")
    print(f"{'='*72}")
    print(f"  Scenario Selected   :  {rainfall_scenario.upper()}")
    print(f"{'─'*72}")
    print(f"  {'Metric':<40} {'Baseline':>12}  {'Dynamic':>12}")
    print(f"  {'─'*64}")
    if hist_max is not None:
        print(f"  {'Historical Max Rainfall (mm/day)':<40} {'—':>12}  {hist_max:>10.1f}  ")
        print(f"  {'Scenario Rainfall (mm/day)':<40} {'—':>12}  {hist_scenario:>10.1f}  ")
        print(f"  {'Weather Ratio (scenario/max)':<40} {'1.00':>12}  {ratio:>10.2f}  ")
    print(f"  {'Engineering Intensity (mm/hr)':<40} {'80.0':>12}  {eng_intensity:>10.1f}  ")
    print(f"  {'Stream Threshold (cells)':<40} {baseline_threshold:>12}  {stream_threshold:>12}")
    thresh_diff = stream_threshold - baseline_threshold
    thresh_pct = ((stream_threshold - baseline_threshold) / baseline_threshold) * 100 if baseline_threshold > 0 else 0
    if thresh_diff > 0:
        stream_change = "FEWER streams (higher threshold)"
    elif thresh_diff < 0:
        stream_change = "MORE streams (lower threshold)"
    else:
        stream_change = "SAME streams"
    print(f"  {'Threshold Difference':<40} {'':>12}  {thresh_diff:>+10} ({thresh_pct:+.0f}%)")
    print(f"  {'Stream Density Impact':<40} {'':>12}  {stream_change}")
    print(f"{'='*72}")

    # Save the rainfall comparison metrics as a JSON report
    import json
    rainfall_report = {
        "village": pfx,
        "scenario": rainfall_scenario,
        "baseline": {
            "intensity_mm_hr": 80.0,
            "stream_threshold_cells": baseline_threshold,
            "description": "Fixed engineering baseline (i=80 mm/hr)"
        },
        "dynamic": {
            "historical_max_daily_mm": hist_max,
            "historical_scenario_daily_mm": hist_scenario,
            "weather_ratio": round(ratio, 4) if hist_max else None,
            "normalized_intensity_mm_hr": round(eng_intensity, 1),
            "stream_threshold_cells": stream_threshold,
            "description": f"Dynamic weather-based ({rainfall_scenario})"
        },
        "comparison": {
            "threshold_difference_cells": thresh_diff,
            "threshold_difference_pct": round(thresh_pct, 1),
            "stream_density_impact": stream_change
        }
    }
    report_path = os.path.join(work_dir, f"{pfx}_RainfallMetrics.json")
    with open(report_path, "w") as f:
        json.dump(rainfall_report, f, indent=2)
    print(f"  📊 Rainfall comparison report saved -> {report_path}")

    wbt = setup_whitebox(work_dir)

    dtm_crs = verify_metric_crs(dtm_path)
    if dtm_crs is None:
        print(f"🚨 CRS check failed for {dtm_filename} – aborting this village.")
        return

    if not fast_path:
        step1_hydrological_breaching(wbt, dtm_filename, BREACHED_DTM)
        step2_flow_modeling(wbt, BREACHED_DTM, FDIR, FACC)
    else:
        print("⚡ FAST PATH ENABLED: Skipping DTM Breaching and Flow Accumulation (using existing files).")

    # 1. Main Pipeline Streams (Standard Engineering Baseline i=80)
    print("\n⏳ [Baseline] Extracting standard stream network (i=80)...")
    step3_stream_extraction_and_smoothing(
        wbt, FACC, FDIR, RASTER_STREAMS, VECTOR_STREAMS,
        threshold=baseline_threshold, dtm_crs=dtm_crs
    )

    # 2. Dynamic Weather Streams
    print(f"\n⏳ [Dynamic] Extracting weather-adjusted streams (scenario: {rainfall_scenario})...")
    step3_stream_extraction_and_smoothing(
        wbt, FACC, FDIR, DYNAMIC_RASTER_STREAMS, DYNAMIC_VECTOR_STREAMS,
        threshold=stream_threshold, dtm_crs=dtm_crs
    )

    # 3. Generate Hydraulic Parameters & GeoJSONs
    from GEO_INTEL_pipeline import compute_drainage_parameters
    
    print("\n⏳ Computing drainage parameters (Baseline)...")
    compute_drainage_parameters(
        streams_path=os.path.join(work_dir, VECTOR_STREAMS),
        dtm_path=dtm_path,
        facc_path=os.path.join(work_dir, FACC),
        village_name=pfx,
        rainfall_mm_day=100.0, # Standard design storm approx
        custom_output_dir=work_dir,
        file_suffix="DrainageDesign"
    )

    print("\n⏳ Computing drainage parameters (Dynamic Weather)...")
    compute_drainage_parameters(
        streams_path=os.path.join(work_dir, DYNAMIC_VECTOR_STREAMS),
        dtm_path=dtm_path,
        facc_path=os.path.join(work_dir, FACC),
        village_name=pfx,
        rainfall_mm_day=hist_scenario if hist_scenario else 100.0,
        custom_output_dir=work_dir,
        file_suffix="DynamicDrainageDesign"
    )

    step4_waterlogging_hotspots(wbt, dtm_filename, BREACHED_DTM, RASTER_STREAMS, TWI, SLOPE, WATER_DEPTH, HAND)
    
    # Adjust waterlogging hotspots dynamically based on rainfall scenario
    try:
        adjust_waterlogging_depth(os.path.join(work_dir, WATER_DEPTH), rainfall_intensity, flood_intensity)
    except NameError:
        pass # If stream_threshold was provided manually, intensities might not be defined

    step5_pour_points_and_catchments(wbt, FDIR, RASTER_STREAMS, WATERSHEDS)
    step6_flood_vulnerability_and_drainage(wbt, dtm_filename, TWI, SLOPE, HAND, RASTER_STREAMS, FLOOD_VULN, COST_SURFACE, TARGETS, COST_DIST, BACKLINK, DRAIN_RASTER, DRAIN_VECTOR, FDIR)



    print("⏳ Fixing projection metadata for GeoTIFFs...")
    for out_tif in [BREACHED_DTM, FDIR, FACC, RASTER_STREAMS, SLOPE, TWI, WATER_DEPTH, WATERSHEDS, HAND, FLOOD_VULN, COST_SURFACE, COST_DIST, BACKLINK, TARGETS, DRAIN_RASTER]:
        fix_raster_crs(os.path.join(work_dir, out_tif), dtm_path)
        
    consolidate_vectors_to_gpkg(work_dir, pfx, dtm_crs=dtm_crs)
    convert_all_to_cog(work_dir, pfx)

    print(f"\n🎉 {pfx} – ALL STEPS COMPLETED SUCCESSFULLY!")

    render_colab_outputs(
        dtm_path,
        os.path.join(work_dir, FACC),
        os.path.join(work_dir, RASTER_STREAMS),
        os.path.join(work_dir, TWI),
        os.path.join(work_dir, WATER_DEPTH),
        os.path.join(work_dir, WATERSHEDS),
        os.path.join(work_dir, FLOOD_VULN),
        os.path.join(work_dir, DRAIN_RASTER),
        output_path=os.path.join(work_dir, f"{pfx}_HydrologySummary.png"),
    )


if __name__ == "__main__":
    import sys
    import glob
    WORK_DIR = os.path.join(os.getcwd(), 'outputs')

    processed_dirs = [d for d in glob.glob(os.path.join(WORK_DIR, "*")) if os.path.isdir(d)]
    
    if len(sys.argv) > 1:
        target = sys.argv[1]
        processed_dirs = [d for d in processed_dirs if os.path.basename(d) == target]

    for village_work_dir in processed_dirs:
        village_name = os.path.basename(village_work_dir)
        dtm_filename = f"{village_name}_DTM.tif"
        if os.path.exists(os.path.join(village_work_dir, dtm_filename)):
            run_village_pipeline(
                work_dir         = village_work_dir,
                dtm_filename     = dtm_filename,
                stream_threshold = None,
            )
        else:
            print(f"Skipping {village_name} - DTM file not found at {os.path.join(village_work_dir, dtm_filename)}")


# ─────────────────────────────────────────────────────────────────────────────
# WRAPPER FOR BACKEND
# ─────────────────────────────────────────────────────────────────────────────

def run_hydrology_pipeline(las_path: str, village_name: str, output_dir: str, stream_threshold: int = None, fast_path: bool = False, rainfall_scenario: str = "flood"):
    """Full Hydrology pipeline wrapper for the web backend."""
    print(f"🚀 Starting Hydrology Pipeline for {village_name} (Scenario: {rainfall_scenario})...")
    
    # The existing script expects DTM in a subdirectory of outputs
    # but the backend saves everything in output_dir
    dtm_filename = f"{village_name}_DTM.tif"
    
    run_village_pipeline(
        work_dir = output_dir,
        dtm_filename = dtm_filename,
        stream_threshold = stream_threshold,
        fast_path = fast_path,
        rainfall_scenario = rainfall_scenario
    )
    
    print("⏳ Running Building Fluid Simulations...")
    generate_building_fluid_simulations(las_path, village_name, output_dir)
    
    print(f"✅ Hydrology Pipeline finished for {village_name}")

# --- MERGED FROM hydrology_with_buildings.py ---

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

def run_dsm_hydrology(dsm_tif, out_dir):
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

def generate_building_fluid_simulations(input_las, village_name, output_dir):
    dsm_tif = os.path.join(output_dir, f"{village_name}_DSM.tif")
    out_gif_hotspots = os.path.join(output_dir, f"{village_name}_Hydrology_Animation_Hotspots.gif")
    out_gif_streams = os.path.join(output_dir, f"{village_name}_Hydrology_Animation_Streams.gif")
    
    if not os.path.exists(dsm_tif):
        create_dsm_geotiff(input_las, dsm_tif)
        run_dsm_hydrology(dsm_tif, output_dir)
        
    hydro_paths = {
        "dsm": dsm_tif,
        "facc": os.path.join(output_dir, "DSM_FlowAcc.tif"),
        "sink": os.path.join(output_dir, "DSM_SinkDepth.tif")
    }
    animate_hydrology(hydro_paths, out_gif_hotspots, out_gif_streams)
    
    return {
        "hotspots_gif": f"{village_name}_Hydrology_Animation_Hotspots.gif",
        "streams_gif": f"{village_name}_Hydrology_Animation_Streams.gif"
    }
