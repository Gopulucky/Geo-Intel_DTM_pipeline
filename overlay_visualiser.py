"""
overlay_visualiser.py
=====================
Overlay analytical layers (DTM, Flow Accumulation, Waterlogging Depth, Drainage
Networks) on top of a drone orthophoto, then export:
  • Individual dark-themed PNGs per layer
  • A 4-panel dark-themed summary PNG
  • A rich interactive Folium HTML map

Supports any number of villages — call run_overlay_visualisation() once per village.

USAGE (Google Colab / local):
    from overlay_visualiser import run_overlay_visualisation

    # DEVDI
    run_overlay_visualisation(
        village_name = "DEVDI_511671",
        dtm_path     = "/content/outputs/DEVDI_511671_DTM.tif",
        ortho_path   = None,                           # optional drone orthophoto
        output_dir   = "/content/outputs",
        epsg         = 32643,
    )

    # KHAPRETA
    run_overlay_visualisation(
        village_name = "KHAPRETA_510206",
        dtm_path     = "/content/outputs/KHAPRETA_510206_DTM.tif",
        ortho_path   = None,
        output_dir   = "/content/outputs",
        epsg         = 32643,
    )
"""

import os
import warnings
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import matplotlib.colors as mcolors
import matplotlib.ticker as mticker
import rasterio
from rasterio.windows import from_bounds
from rasterio.warp import (reproject, Resampling,
                            transform_bounds, calculate_default_transform)
from rasterio.crs import CRS
import geopandas as gpd

warnings.filterwarnings("ignore")

# ── Optional deps ─────────────────────────────────────────────────────────────
try:
    import folium
    from folium.plugins import MeasureControl, Fullscreen, MiniMap
    FOLIUM_AVAILABLE = True
except ImportError:
    FOLIUM_AVAILABLE = False

# ─────────────────────────────────────────────────────────────────────────────
# THEME
# ─────────────────────────────────────────────────────────────────────────────
DARK_BG       = "#1a1a2e"
PANEL_BG      = "#0f0f1a"
SPINE_COLOR   = "#333355"
TITLE_COLOR   = "#e0e0ff"
TICK_COLOR    = "#888899"
ACCENT_CYAN   = "#00e5ff"
ACCENT_ORANGE = "#ff9800"

# Per-layer styling table: (suffix, label, cmap, log_scale, unit, alpha)
LAYER_DEFS = [
    ("_DTM.tif",                   "Elevation (DTM)",          "terrain",    False, "m",    0.85),
    ("_FlowAccumulation.tif",      "Flow Accumulation (log)",  "Blues",      True,  "cells",0.70),
    ("_WaterDepth.tif",            "Sink Depth / Waterlogging","PuBu",       False, "m",    0.75),
    ("_TWI_Waterlogging.tif",      "Topographic Wetness Index","RdYlGn_r",  False, "TWI",  0.75),
]


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _load_raster(path, nodata_to_nan=True):
    """Read band-1 of a GeoTIFF and return (array, src_meta)."""
    with rasterio.open(path) as src:
        arr = src.read(1).astype(np.float32)
        nd  = src.nodata
        meta = {
            "nodata": nd,
            "bounds": src.bounds,
            "transform": src.transform,
            "crs": src.crs,
            "shape": (src.height, src.width),
        }
    if nodata_to_nan and nd is not None:
        arr[arr == nd] = np.nan
    arr[~np.isfinite(arr)] = np.nan
    return arr, meta


def load_orthophoto(ortho_path, clip_bounds):
    """Windowed-read of RGB orthophoto clipped to DTM bounds. Returns (rgb, extent)."""
    if not ortho_path or not os.path.exists(ortho_path):
        return None, None
    try:
        with rasterio.open(ortho_path) as src:
            left, bottom, right, top = clip_bounds
            win = from_bounds(left, bottom, right, top, src.transform)
            full = rasterio.windows.Window(0, 0, src.width, src.height)
            win  = win.intersection(full)
            if win.width <= 0 or win.height <= 0:
                return None, None
            bands  = min(src.count, 3)
            img    = src.read(list(range(1, bands + 1)), window=win)
            img    = np.transpose(img, (1, 2, 0))
            if img.shape[2] == 1:
                img = np.repeat(img, 3, axis=2)
            elif img.shape[2] > 3:
                img = img[..., :3]
            img = img.astype(np.float32)
            if img.max() > 1.0:
                img /= 255.0
            t   = src.window_transform(win)
            h, w = img.shape[:2]
            ext = [t[2], t[2] + w * t[0], t[5] + h * t[4], t[5]]
            return img, ext
    except Exception as exc:
        print(f"  ⚠ Ortho load failed: {exc}")
        return None, None


def reproject_to_match(source_path, reference_path):
    """Reproject + resample source raster to exactly match the reference grid."""
    arr_ref, meta_ref = _load_raster(reference_path)
    dst = np.full(meta_ref["shape"], np.nan, dtype=np.float32)
    with rasterio.open(source_path) as src:
        reproject(
            source      = rasterio.band(src, 1),
            destination = dst,
            src_transform = src.transform,
            src_crs       = src.crs,
            dst_transform = meta_ref["transform"],
            dst_crs       = meta_ref["crs"],
            resampling    = Resampling.bilinear,
            src_nodata    = src.nodata,
            dst_nodata    = np.nan,
        )
    return dst


def compute_hillshade(arr, cell_size, azimuth=315.0, altitude=45.0):
    """Returns a [0,1] hillshade array from a DTM."""
    dy, dx   = np.gradient(arr, cell_size, cell_size)
    az_rad   = np.radians(azimuth)
    alt_rad  = np.radians(altitude)
    slope    = np.pi / 2.0 - np.arctan(np.sqrt(dx**2 + dy**2))
    aspect   = np.arctan2(-dx, dy)
    shaded   = (np.sin(alt_rad) * np.sin(slope) +
                np.cos(alt_rad) * np.cos(slope) *
                np.cos((az_rad - np.pi / 2.0) - aspect))
    return np.clip(shaded, 0, 1)


def _masked(arr, lower_pct=2, upper_pct=98, min_mask=None, log=False):
    """Apply nan-masking, optional lower threshold, optional log, percentile clip."""
    a = arr.copy()
    if min_mask is not None:
        a[a <= min_mask] = np.nan
    if log:
        a = np.where(a > 0, np.log1p(a), np.nan)
    valid = a[np.isfinite(a)]
    if valid.size == 0:
        return np.ma.masked_all_like(a), None, None
    vmin, vmax = np.nanpercentile(valid, [lower_pct, upper_pct])
    return np.ma.masked_invalid(a), vmin, vmax


def _style_ax(ax, title, crs_label=""):
    """Apply consistent dark-theme styling to a matplotlib Axes."""
    ax.set_facecolor(PANEL_BG)
    ax.set_title(title, color=TITLE_COLOR, fontsize=11, fontweight="bold", pad=8)
    ax.tick_params(axis="both", colors=TICK_COLOR, labelsize=7)
    ax.xaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f"))
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f"))
    ax.set_xlabel("Easting (m)",  color=TICK_COLOR, fontsize=7)
    ax.set_ylabel("Northing (m)", color=TICK_COLOR, fontsize=7)
    for sp in ax.spines.values():
        sp.set_edgecolor(SPINE_COLOR)
    if crs_label:
        ax.text(0.99, 0.01, crs_label, transform=ax.transAxes,
                fontsize=5, color="#444466", ha="right", va="bottom")


def _add_colorbar(fig, im, ax, unit, label_color=TICK_COLOR):
    cbar = fig.colorbar(im, ax=ax, fraction=0.036, pad=0.02)
    cbar.ax.tick_params(labelsize=7, colors=label_color)
    cbar.set_label(unit, color=label_color, fontsize=8)
    cbar.outline.set_edgecolor(SPINE_COLOR)


def _save(fig, path, dpi=200):
    fig.savefig(path, dpi=dpi, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"  ✅ Saved → {path}")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN RUNNER
# ─────────────────────────────────────────────────────────────────────────────

def run_overlay_visualisation(
    village_name,
    dtm_path,
    ortho_path   = None,
    streams_path = None,
    hotspot_path = None,
    output_dir   = "./outputs",
    epsg         = None,
    export_html  = True,
):
    """
    Generate overlay visualisations for ONE village.

    Parameters
    ----------
    village_name : str   e.g. "KHAPRETA_510206"
    dtm_path     : str   Path to the village DTM GeoTIFF
    ortho_path   : str   Optional drone RGB orthophoto GeoTIFF
    streams_path : str   Optional streams vector (auto-detected if None)
    hotspot_path : str   Optional waterlogging hotspots vector (auto-detected if None)
    output_dir   : str   Directory for all outputs
    epsg         : int   Fallback EPSG if DTM has no embedded CRS
    export_html  : bool  Whether to produce an interactive Folium HTML map
    """
    os.makedirs(output_dir, exist_ok=True)

    # ── 1. Load DTM ────────────────────────────────────────────────────────────
    if not os.path.exists(dtm_path):
        print(f"  ❌ DTM not found: {dtm_path}")
        return

    dtm_arr, dtm_meta = _load_raster(dtm_path)
    dtm_crs    = dtm_meta["crs"] or (CRS.from_epsg(epsg) if epsg else None)
    dtm_bounds = dtm_meta["bounds"]
    cell_size  = dtm_meta["transform"][0]
    crs_label  = dtm_crs.to_string() if dtm_crs else "No CRS"
    ext_dtm    = [dtm_bounds.left, dtm_bounds.right,
                  dtm_bounds.bottom, dtm_bounds.top]

    print(f"\n{'='*60}")
    print(f"  Overlay visualisation  →  {village_name}")
    print(f"  CRS   : {crs_label}")
    print(f"  Bounds: {dtm_bounds}")
    print(f"{'='*60}")

    # ── 2. Hillshade ───────────────────────────────────────────────────────────
    dtm_hs = compute_hillshade(dtm_arr, cell_size)

    # ── 3. Orthophoto (optional) ───────────────────────────────────────────────
    ortho_rgb, ext_ortho = load_orthophoto(
        ortho_path,
        (dtm_bounds.left, dtm_bounds.bottom, dtm_bounds.right, dtm_bounds.top)
    )
    ext_base = ext_ortho if ortho_rgb is not None else ext_dtm

    def _base(ax):
        """Draw base layer (ortho or terrain DTM)."""
        if ortho_rgb is not None:
            ax.imshow(ortho_rgb, extent=ext_base, origin="upper")
            dtm_m, v0, v1 = _masked(dtm_arr)
            ax.imshow(dtm_m, extent=ext_dtm, origin="upper",
                      cmap="terrain", alpha=0.12, vmin=v0, vmax=v1)
            ax.imshow(np.ma.masked_invalid(dtm_hs),
                      extent=ext_dtm, origin="upper", cmap="Greys_r", alpha=0.30)
        else:
            dtm_m, v0, v1 = _masked(dtm_arr)
            ax.imshow(dtm_m, extent=ext_dtm, origin="upper",
                      cmap="terrain", alpha=0.85, vmin=v0, vmax=v1)
            ax.imshow(np.ma.masked_invalid(dtm_hs),
                      extent=ext_dtm, origin="upper", cmap="Greys_r", alpha=0.40)

    # ── 4. Auto-detect optional file paths ────────────────────────────────────
    base_dir = os.path.dirname(dtm_path)
    if streams_path is None:
        for sfx in ("_DrainageDesign.gpkg", "_Clean.gpkg", "_VectorStreams_Clean.geojson",
                    "_Streams.shp", "_Streams.geojson"):
            p = os.path.join(base_dir, village_name + sfx)
            if os.path.exists(p):
                streams_path = p
                break
    if hotspot_path is None:
        for ext in (".gpkg", ".geojson"):
            p = os.path.join(base_dir, f"{village_name}_WaterloggingHotspots{ext}")
            if os.path.exists(p):
                hotspot_path = p
                break

    flow_path = os.path.join(base_dir, f"{village_name}_FAcc.tif")
    if not os.path.exists(flow_path):
        flow_path = os.path.join(base_dir, f"{village_name}_FlowAccumulation.tif")
    wl_path = os.path.join(base_dir, f"{village_name}_WaterDepth.tif")
    twi_path = os.path.join(base_dir, f"{village_name}_TWI_Waterlogging.tif")

    # ── 5. Load optional rasters ──────────────────────────────────────────────
    def _try_load(path):
        if path and os.path.exists(path):
            return reproject_to_match(path, dtm_path)
        return None

    flow_arr = _try_load(flow_path)
    wl_arr   = _try_load(wl_path)
    twi_arr  = _try_load(twi_path)

    # ── 6. Load optional vectors ──────────────────────────────────────────────
    def _load_vec(path):
        if not path or not os.path.exists(path):
            return None
        gdf = gpd.read_file(path)
        if dtm_crs and gdf.crs and gdf.crs != dtm_crs:
            gdf = gdf.to_crs(dtm_crs)
        return gdf if not gdf.empty else None

    streams_gdf  = _load_vec(streams_path)
    hotspots_gdf = _load_vec(hotspot_path)

    # ── 7. Individual overlay PNGs ────────────────────────────────────────────

    # --- A. DTM + Hillshade ---
    fig, ax = plt.subplots(figsize=(10, 10)); fig.patch.set_facecolor(DARK_BG)
    _base(ax)
    _style_ax(ax, f"{village_name}  ·  DTM & Hillshade", crs_label)
    _save(fig, os.path.join(output_dir, f"{village_name}_ortho_DTM.png"))

    # --- B. Flow Accumulation ---
    fig, ax = plt.subplots(figsize=(10, 10)); fig.patch.set_facecolor(DARK_BG)
    _base(ax)
    if flow_arr is not None:
        fm, v0, v1 = _masked(flow_arr, min_mask=10, log=True)
        if fm.count() > 0:
            im = ax.imshow(fm, extent=ext_dtm, origin="upper",
                           cmap="Blues", alpha=0.70, vmin=v0, vmax=v1)
            _add_colorbar(fig, im, ax, "log(cells)")
    _style_ax(ax, f"{village_name}  ·  Flow Accumulation", crs_label)
    _save(fig, os.path.join(output_dir, f"{village_name}_ortho_FlowAcc.png"))

    # --- C. Waterlogging Depth ---
    fig, ax = plt.subplots(figsize=(10, 10)); fig.patch.set_facecolor(DARK_BG)
    _base(ax)
    if wl_arr is not None:
        wm, v0, v1 = _masked(wl_arr, min_mask=0.05)
        if wm.count() > 0:
            im = ax.imshow(wm, extent=ext_dtm, origin="upper",
                           cmap="cool", alpha=0.70, vmin=v0, vmax=v1)
            _add_colorbar(fig, im, ax, "m")
    if hotspots_gdf is not None:
        hotspots_gdf.plot(ax=ax, facecolor="#0080ff55",
                         edgecolor="#00ccff", linewidth=0.8)
    _style_ax(ax, f"{village_name}  ·  Waterlogging Depth", crs_label)
    _save(fig, os.path.join(output_dir, f"{village_name}_ortho_Waterlogging.png"))

    # --- D. Drainage Network ---
    fig, ax = plt.subplots(figsize=(10, 10)); fig.patch.set_facecolor(DARK_BG)
    _base(ax)
    if streams_gdf is not None:
        streams_gdf.plot(ax=ax, color=ACCENT_CYAN, linewidth=1.8, alpha=0.90)
    if hotspots_gdf is not None:
        hotspots_gdf.plot(ax=ax, facecolor="#ff450066",
                         edgecolor=ACCENT_ORANGE, linewidth=0.6)
    _style_ax(ax, f"{village_name}  ·  Drainage Network", crs_label)
    _save(fig, os.path.join(output_dir, f"{village_name}_ortho_Drainage.png"))

    # ── 8. 4-Panel Summary PNG ────────────────────────────────────────────────
    fig, axs = plt.subplots(2, 2, figsize=(20, 20), dpi=150)
    fig.patch.set_facecolor(DARK_BG)
    fig.suptitle(f"🌊  Overlay Analysis  ·  {village_name.replace('_', ' ')}",
                 fontsize=20, fontweight="bold", color=TITLE_COLOR, y=0.998)

    # Panel 0,0 – DTM Hillshade
    _base(axs[0, 0])
    _style_ax(axs[0, 0], "DTM & Hillshade", crs_label)

    # Panel 0,1 – Flow Accumulation
    _base(axs[0, 1])
    if flow_arr is not None:
        fm, v0, v1 = _masked(flow_arr, min_mask=10, log=True)
        if fm.count() > 0:
            im = axs[0, 1].imshow(fm, extent=ext_dtm, origin="upper",
                                   cmap="Blues", alpha=0.70, vmin=v0, vmax=v1)
            _add_colorbar(fig, im, axs[0, 1], "log(cells)")
    _style_ax(axs[0, 1], "Flow Accumulation", crs_label)

    # Panel 1,0 – Waterlogging
    _base(axs[1, 0])
    if wl_arr is not None:
        wm, v0, v1 = _masked(wl_arr, min_mask=0.05)
        if wm.count() > 0:
            im = axs[1, 0].imshow(wm, extent=ext_dtm, origin="upper",
                                   cmap="cool", alpha=0.70, vmin=v0, vmax=v1)
            _add_colorbar(fig, im, axs[1, 0], "m")
    if hotspots_gdf is not None:
        hotspots_gdf.plot(ax=axs[1, 0], facecolor="#0080ff55",
                         edgecolor="#00ccff", linewidth=0.8)
    _style_ax(axs[1, 0], "Waterlogging Depth & Hotspots", crs_label)

    # Panel 1,1 – Drainage
    _base(axs[1, 1])
    if streams_gdf is not None:
        streams_gdf.plot(ax=axs[1, 1], color=ACCENT_CYAN, linewidth=1.8, alpha=0.90)
    if hotspots_gdf is not None:
        hotspots_gdf.plot(ax=axs[1, 1], facecolor="#ff450066",
                         edgecolor=ACCENT_ORANGE, linewidth=0.6)
    _style_ax(axs[1, 1], "Drainage Network & Hotspots", crs_label)

    plt.tight_layout(rect=[0, 0, 1, 0.995])
    _save(fig, os.path.join(output_dir, f"{village_name}_ortho_Summary.png"), dpi=150)

    # ── 9. Rich Folium HTML Map ───────────────────────────────────────────────
    if not export_html or not FOLIUM_AVAILABLE or dtm_crs is None:
        if not FOLIUM_AVAILABLE:
            print("  ⚠ folium not installed — skipping HTML export (pip install folium)")
        print(f"\n  Done for {village_name}.\n")
        return

    try:
        print(f"  Creating interactive HTML map…")
        b4326 = transform_bounds(dtm_crs, "EPSG:4326", *dtm_bounds)
        c_lat = (b4326[1] + b4326[3]) / 2.0
        c_lon = (b4326[0] + b4326[2]) / 2.0
        f_bounds = [[b4326[1], b4326[0]], [b4326[3], b4326[2]]]

        # ── Base map (dark Esri satellite) ────────────────────────────────────
        m = folium.Map(
            location=[c_lat, c_lon],
            zoom_start=14,
            tiles=None,
            prefer_canvas=True,
        )

        # Tile layers
        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            attr="Esri World Imagery",
            name="🛰 Esri Satellite",
            overlay=False,
            control=True,
        ).add_to(m)
        folium.TileLayer(
            tiles="CartoDB dark_matter",
            name="🌑 Dark Matter",
            overlay=False,
            control=True,
        ).add_to(m)
        folium.TileLayer(
            tiles="OpenStreetMap",
            name="🗺 OpenStreetMap",
            overlay=False,
            control=True,
        ).add_to(m)

        # ── DTM elevation overlay (coloured raster) ───────────────────────────
        tw, th = 512, 512
        dtm_t, dtm_w, dtm_h = calculate_default_transform(
            dtm_crs, "EPSG:4326", tw, th, *dtm_bounds
        )
        dtm_4326 = np.full((dtm_h, dtm_w), np.nan, dtype=np.float32)
        with rasterio.open(dtm_path) as src2:
            reproject(
                source       = rasterio.band(src2, 1),
                destination  = dtm_4326,
                src_transform= dtm_meta["transform"],
                src_crs      = dtm_crs,
                dst_transform= dtm_t,
                dst_crs      = "EPSG:4326",
                resampling   = Resampling.bilinear,
                src_nodata   = dtm_meta["nodata"],
                dst_nodata   = np.nan,
            )
        dtm_4326_m = np.ma.masked_invalid(dtm_4326)
        norm_dtm   = mcolors.Normalize(
            vmin=np.nanpercentile(dtm_4326, 2),
            vmax=np.nanpercentile(dtm_4326, 98)
        )
        dtm_rgba = cm.terrain(norm_dtm(dtm_4326_m))
        dtm_rgba[dtm_4326_m.mask, 3] = 0.0     # transparent nodata
        folium.raster_layers.ImageOverlay(
            image=dtm_rgba, bounds=f_bounds,
            opacity=0.45, name="🏔 DTM Elevation",
            interactive=False, cross_origin=False,
        ).add_to(m)

        # ── Flow Accumulation overlay ─────────────────────────────────────────
        if flow_arr is not None:
            fa_crop = flow_arr.copy()
            fa_crop[fa_crop <= 10] = np.nan
            fa_4326 = np.full((dtm_h, dtm_w), np.nan, dtype=np.float32)
            with rasterio.open(flow_path) as src_fa:
                reproject(
                    source       = rasterio.band(src_fa, 1),
                    destination  = fa_4326,
                    src_transform= src_fa.transform,
                    src_crs      = src_fa.crs,
                    dst_transform= dtm_t,
                    dst_crs      = "EPSG:4326",
                    resampling   = Resampling.bilinear,
                    src_nodata   = src_fa.nodata,
                    dst_nodata   = np.nan,
                )
            fa_4326[fa_4326 <= 0] = np.nan
            fa_log = np.log1p(fa_4326)
            fa_m   = np.ma.masked_invalid(fa_log)
            if fa_m.count() > 0:
                norm_fa = mcolors.Normalize(
                    vmin=np.nanpercentile(fa_log[np.isfinite(fa_log)], 2),
                    vmax=np.nanpercentile(fa_log[np.isfinite(fa_log)], 98),
                )
                fa_rgba = cm.Blues(norm_fa(fa_m))
                fa_rgba[fa_m.mask, 3] = 0.0
                folium.raster_layers.ImageOverlay(
                    image=fa_rgba, bounds=f_bounds,
                    opacity=0.55, name="💧 Flow Accumulation",
                    interactive=False, cross_origin=False,
                ).add_to(m)

        # ── Waterlogging depth overlay ────────────────────────────────────────
        if wl_arr is not None:
            wl_4326 = np.full((dtm_h, dtm_w), np.nan, dtype=np.float32)
            with rasterio.open(wl_path) as src_wl:
                reproject(
                    source       = rasterio.band(src_wl, 1),
                    destination  = wl_4326,
                    src_transform= src_wl.transform,
                    src_crs      = src_wl.crs,
                    dst_transform= dtm_t,
                    dst_crs      = "EPSG:4326",
                    resampling   = Resampling.bilinear,
                    src_nodata   = src_wl.nodata,
                    dst_nodata   = np.nan,
                )
            wl_4326[wl_4326 <= 0.05] = np.nan
            wl_m = np.ma.masked_invalid(wl_4326)
            if wl_m.count() > 0:
                norm_wl = mcolors.Normalize(
                    vmin=np.nanpercentile(wl_4326[np.isfinite(wl_4326)], 2),
                    vmax=np.nanpercentile(wl_4326[np.isfinite(wl_4326)], 98),
                )
                wl_rgba = cm.cool(norm_wl(wl_m))
                wl_rgba[wl_m.mask, 3] = 0.0
                folium.raster_layers.ImageOverlay(
                    image=wl_rgba, bounds=f_bounds,
                    opacity=0.60, name="🌊 Waterlogging Depth",
                    interactive=False, cross_origin=False,
                ).add_to(m)

        # ── Stream network (GeoJSON with tooltips) ────────────────────────────
        if streams_gdf is not None:
            streams_4326 = streams_gdf.to_crs("EPSG:4326")
            # add length if not present
            if "length_m" not in streams_4326.columns:
                streams_4326["length_m"] = streams_4326.to_crs(
                    streams_gdf.crs).geometry.length.round(1)

            folium.GeoJson(
                streams_4326,
                name="🔵 Drainage Network",
                style_function=lambda feat: {
                    "color":   "#00e5ff",
                    "weight":  2.0,
                    "opacity": 0.85,
                },
                tooltip=folium.GeoJsonTooltip(
                    fields=["length_m"] if "length_m" in streams_4326.columns else [],
                    aliases=["Length (m):"],
                    localize=True,
                    sticky=False,
                ),
            ).add_to(m)

        # ── Waterlogging hotspots (polygons with popup) ───────────────────────
        if hotspots_gdf is not None:
            h_4326 = hotspots_gdf.to_crs("EPSG:4326")
            folium.GeoJson(
                h_4326,
                name="⚠ Waterlogging Hotspots",
                style_function=lambda feat: {
                    "fillColor":   "#0080ff",
                    "color":       "#ff9800",
                    "weight":      1.2,
                    "fillOpacity": 0.40,
                },
                tooltip=folium.GeoJsonTooltip(
                    fields=[], aliases=[],
                    labels=False,
                    localize=True,
                    sticky=False,
                    style="font-size:12px; background:#111; color:#0ff; border:none;",
                ),
                popup=folium.GeoJsonPopup(
                    fields=[], labels=False,
                    localize=True,
                    max_width=150,
                ),
            ).add_to(m)

        # ── Bounding-box rectangle to show study area ─────────────────────────
        folium.Rectangle(
            bounds=f_bounds,
            color="#ffffff",
            weight=1.5,
            fill=False,
            opacity=0.5,
            tooltip=f"Study area: {village_name}",
        ).add_to(m)

        # ── Plugins ───────────────────────────────────────────────────────────
        MeasureControl(
            position="topright",
            primary_length_unit="meters",
            secondary_length_unit="kilometers",
            primary_area_unit="sqmeters",
        ).add_to(m)
        Fullscreen(position="topright").add_to(m)
        MiniMap(toggle_display=True).add_to(m)

        folium.LayerControl(collapsed=False).add_to(m)

        # ── Custom legend ─────────────────────────────────────────────────────
        legend_html = f"""
        <div style="
            position: fixed; bottom: 40px; left: 20px; z-index: 1000;
            background: rgba(10, 10, 30, 0.88);
            border: 1px solid #333;
            border-radius: 10px;
            padding: 12px 16px;
            font-family: 'Segoe UI', sans-serif;
            color: #dde;
            font-size: 12px;
            min-width: 190px;
            box-shadow: 0 4px 18px rgba(0,0,0,0.6);
        ">
          <b style="font-size:14px; color:#00e5ff;">🌊 {village_name.replace("_"," ")}</b>
          <hr style="border-color:#223; margin:6px 0;">
          <div><span style="display:inline-block;width:14px;height:6px;background:#00e5ff;border-radius:3px;margin-right:6px;"></span>Drainage streams</div>
          <div><span style="display:inline-block;width:14px;height:14px;background:#0080ff55;border:1px solid #00ccff;border-radius:3px;margin-right:6px;"></span>Waterlogging hotspot</div>
          <div><span style="display:inline-block;width:14px;height:14px;background:#184e77cc;border-radius:3px;margin-right:6px;"></span>Flow accumulation</div>
          <div><span style="display:inline-block;width:14px;height:14px;background:#22cc8855;border-radius:3px;margin-right:6px;"></span>DTM elevation</div>
          <hr style="border-color:#223; margin:6px 0;">
          <div style="font-size:10px; color:#778;">CRS: {crs_label}</div>
        </div>
        """
        m.get_root().html.add_child(folium.Element(legend_html))

        html_out = os.path.join(output_dir, f"{village_name}_interactive_map.html")
        m.save(html_out)
        print(f"  ✅ Interactive map → {html_out}")

    except Exception as exc:
        print(f"  ⚠ Folium export failed: {exc}")

    print(f"\n  ✅ All outputs for {village_name} saved to → {output_dir}\n")


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT  (run from Colab or terminal)
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    OUTPUT_DIR = "/content/outputs"     # ← change to your path
    if os.path.exists("./outputs"): OUTPUT_DIR = "./outputs" # Fallback for local

    VILLAGES = [
        {"name": "DEVDI_511671", "epsg": 32643},
        {"name": "KHAPRETA_510206", "epsg": 32643},
        {"name": "Dhal_Hoshiarpur_31235", "epsg": 32643},
        {"name": "DHUNDA_FATEHGARH_SAHIB_32619", "epsg": 32643},
        {"name": "67169_5NKR_CHAKHIRASINGH", "epsg": 32643},
        {"name": "64334_2H_REFLIGHT", "epsg": 32643},
        {"name": "PIRAYANKUPPAM", "epsg": 32644},
        {"name": "THANDALAM", "epsg": 32644},
        {"name": "Gandhinagar_Diglipur", "epsg": 32646},
        {"name": "Kadamtala_Rangat", "epsg": 32646},
    ]

    if len(sys.argv) > 1:
        target = sys.argv[1]
        VILLAGES = [v for v in VILLAGES if v["name"] == target]

    for v in VILLAGES:
        village_output_dir = f"{OUTPUT_DIR}/{v['name']}"
        os.makedirs(village_output_dir, exist_ok=True)
        dtm_path = f"{village_output_dir}/{v['name']}_DTM.tif"
        
        if os.path.exists(dtm_path):
            run_overlay_visualisation(
                village_name = v["name"],
                dtm_path     = dtm_path,
                ortho_path   = None,            # e.g. "/content/drive/MyDrive/model/{v['name']}_ortho.tif"
                output_dir   = village_output_dir,
                epsg         = v["epsg"],
                export_html  = True,
            )
        else:
            print(f"Skipping {v['name']} - DTM file not found at {dtm_path}")
