// frontend/src/components/TifViewer.jsx
// Opens .tif files in browser using georaster + Leaflet — like QGIS

import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import GeoRasterLayer from "georaster-layer-for-leaflet";
import parseGeoraster from "georaster";

// Fix Leaflet's default icon paths (Vite breaks them)
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png",
  iconUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png",
  shadowUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png",
});

// ── Color Maps (same as QGIS symbology) ─────────────────────────────────────

const COLOR_MAPS = {
  // LULC — categorized renderer (your pipeline's class codes)
  lulc: (values, min, max) => {
    const val = values[0];
    if (val === null || val === undefined || isNaN(val)) return null;
    const colorTable = {
      1: "#E8A87C",   // Built-up / Residential — orange
      2: "#90EE90",   // Agricultural land — light green
      3: "#228B22",   // Dense vegetation / Forest — dark green
      4: "#4169E1",   // Water bodies — blue
      5: "#D2B48C",   // Bare soil / Fallow — tan
      6: "#808080",   // Roads / Impervious — grey
      7: "#FFD700",   // Scrubland — yellow
      8: "#FF6B6B",   // Degraded land — red
    };
    return colorTable[Math.round(val)] || "#CCCCCC";
  },

  // DTM — elevation gradient (QGIS terrain color ramp)
  dtm: (values, min, max) => {
    const val = values[0];
    if (val === null || val === undefined || isNaN(val)) return null;
    const norm = Math.max(0, Math.min(1, (val - min) / (max - min)));

    // Terrain color ramp: deep blue → green → yellow → white
    if (norm < 0.2) {
      const t = norm / 0.2;
      return `rgb(${Math.round(t*34)}, ${Math.round(t*139)}, ${Math.round(139 + t*( 87-139))})`;
    } else if (norm < 0.5) {
      const t = (norm - 0.2) / 0.3;
      return `rgb(${Math.round(34 + t*(154-34))}, ${Math.round(139 + t*(205-139))}, ${Math.round(87 + t*(50-87))})`;
    } else if (norm < 0.8) {
      const t = (norm - 0.5) / 0.3;
      return `rgb(${Math.round(154 + t*(240-154))}, ${Math.round(205 + t*(230-205))}, ${Math.round(50 + t*(140-50))})`;
    } else {
      const t = (norm - 0.8) / 0.2;
      return `rgb(${Math.round(240 + t*(255-240))}, ${Math.round(230 + t*(255-230))}, ${Math.round(140 + t*(255-140))})`;
    }
  },

  // Hydrology — single band pseudocolor (blue gradient like QGIS)
  hydrology: (values, min, max) => {
    const val = values[0];
    if (val === null || val === undefined || isNaN(val) || val <= 0) return null;
    const norm = Math.max(0, Math.min(1, (Math.log1p(val) - Math.log1p(min)) / (Math.log1p(max) - Math.log1p(min))));
    const r = Math.round(230 - norm * 200);
    const g = Math.round(240 - norm * 160);
    const b = 255;
    return `rgba(${r},${g},${b},${0.3 + norm * 0.6})`;
  },

  // DSM — same as DTM but different range
  dsm: (values, min, max) => COLOR_MAPS.dtm(values, min, max),

  // CHM — Canopy Height Model — green gradient
  chm: (values, min, max) => {
    const val = values[0];
    if (val === null || val === undefined || isNaN(val) || val <= 0) return null;
    const norm = Math.max(0, Math.min(1, (val - min) / (max - min)));
    const g = Math.round(80 + norm * 175);
    const r = Math.round(norm * 60);
    return `rgb(${r}, ${g}, 40)`;
  },
};

// ── Legend Component ─────────────────────────────────────────────────────────

function Legend({ type }) {
  const legends = {
    lulc: [
      { color: "#E8A87C", label: "Built-up / Residential" },
      { color: "#90EE90", label: "Agricultural" },
      { color: "#228B22", label: "Forest / Vegetation" },
      { color: "#4169E1", label: "Water Bodies" },
      { color: "#D2B48C", label: "Bare Soil" },
      { color: "#808080", label: "Roads" },
      { color: "#FFD700", label: "Scrubland" },
      { color: "#FF6B6B", label: "Degraded Land" },
    ],
    dtm: [
      { color: "#228BB7", label: "Low elevation" },
      { color: "#22A559", label: "Mid elevation" },
      { color: "#F0E696", label: "High elevation" },
      { color: "#FFFFFF", label: "Peak / Highest" },
    ],
    hydrology: [
      { color: "rgba(230,240,255,0.5)", label: "Low flow accumulation" },
      { color: "rgba(100,150,255,0.8)", label: "High flow accumulation" },
      { color: "rgba(30,80,255,1)", label: "Main drainage channel" },
    ],
    chm: [
      { color: "rgb(10,80,40)", label: "Tall canopy (>15m)" },
      { color: "rgb(30,160,40)", label: "Medium canopy (5-15m)" },
      { color: "rgb(60,220,40)", label: "Low canopy (<5m)" },
    ],
  };

  const items = legends[type] || legends.lulc;

  return (
    <div className="absolute bottom-4 right-4 z-[1000] bg-white rounded-xl shadow-lg p-3 text-xs">
      <p className="font-semibold text-gray-700 mb-2 font-display">Legend</p>
      {items.map((item, i) => (
        <div key={i} className="flex items-center gap-2 mb-1">
          <div className="w-4 h-4 rounded-sm border border-gray-200 flex-shrink-0"
               style={{ background: item.color }} />
          <span className="text-gray-600">{item.label}</span>
        </div>
      ))}
    </div>
  );
}

// ── Main TifViewer Component ─────────────────────────────────────────────────

export default function TifViewer({ tifUrl, type = "lulc", title = "Map" }) {
  const mapRef        = useRef(null);
  const mapInstance   = useRef(null);
  const geoLayer      = useRef(null);

  const [loading,  setLoading]  = useState(true);
  const [error,    setError]    = useState(null);
  const [stats,    setStats]    = useState(null);   // min/max values
  const [coords,   setCoords]   = useState(null);   // mouse position
  const [pixelVal, setPixelVal] = useState(null);   // value under cursor

  // ── Initialize Leaflet map ────────────────────────────────────────────────
  useEffect(() => {
    if (mapInstance.current) return;

    const map = L.map(mapRef.current, {
      center: [20.5, 78.9],
      zoom: 5,
      zoomControl: true,
    });

    // Base layer removed per request. Leaflet map background will be transparent/grey.

    // Show coordinates on mouse move (like QGIS status bar)
    map.on("mousemove", (e) => {
      setCoords({
        lat: e.latlng.lat.toFixed(6),
        lng: e.latlng.lng.toFixed(6)
      });
    });

    mapInstance.current = map;
  }, []);

  // ── Load and render .tif file ─────────────────────────────────────────────
  useEffect(() => {
    if (!tifUrl || !mapInstance.current) return;

    setLoading(true);
    setError(null);

    // Remove previous layer
    if (geoLayer.current) {
      mapInstance.current.removeLayer(geoLayer.current);
      geoLayer.current = null;
    }

    // Step 1: Fetch .tif file as binary
    fetch(tifUrl)
      .then(res => {
        if (!res.ok) throw new Error(`Failed to fetch: ${res.status} ${res.statusText}`);
        return res.arrayBuffer();
      })

      // Step 2: Parse GeoTIFF (reads GPS coords, pixel values, metadata)
      .then(buffer => parseGeoraster(buffer))

      // Step 3: Create colored layer (applies color map like QGIS symbology)
      .then(georaster => {
        const min = georaster.mins[0];
        const max = georaster.maxs[0];
        setStats({ min: min.toFixed(2), max: max.toFixed(2) });

        const colorFn = COLOR_MAPS[type] || COLOR_MAPS.lulc;

        const layer = new GeoRasterLayer({
          georaster,
          opacity: 0.85,
          resolution: 512,  // higher = sharper but slower

          // This is the QGIS "symbology" equivalent
          pixelValuesToColorFn: (values) => colorFn(values, min, max),
        });

        layer.addTo(mapInstance.current);
        geoLayer.current = layer;

        // Zoom to .tif extent (like QGIS "Zoom to Layer")
        mapInstance.current.fitBounds(layer.getBounds());

        // Show pixel value on click (like QGIS "Identify Features")
        mapInstance.current.on("click", (e) => {
          const { lat, lng } = e.latlng;
          // Convert lat/lng to pixel and get value
          // (simplified — full implementation needs coordinate transform)
          console.log(`Clicked: ${lat.toFixed(4)}, ${lng.toFixed(4)}`);
        });

        setLoading(false);
      })

      .catch(err => {
        console.error("TIF load error:", err);
        setError(err.message);
        setLoading(false);
      });

  }, [tifUrl, type]);

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="relative w-full h-full rounded-xl overflow-hidden border border-green-100 shadow-md">

      {/* Map Title Bar */}
      <div className="absolute top-0 left-0 right-0 z-[1000] bg-white/90 backdrop-blur px-4 py-2 flex items-center justify-between border-b border-green-100">
        <span className="font-semibold text-green-800 text-sm font-display">{title}</span>
        {stats && (
          <span className="text-xs text-gray-500">
            Range: {stats.min} — {stats.max}
          </span>
        )}
      </div>

      {/* Loading Overlay */}
      {loading && (
        <div className="absolute inset-0 z-[999] bg-white/80 flex flex-col items-center justify-center gap-3">
          <div className="w-10 h-10 border-4 border-green-200 border-t-green-600 rounded-full animate-spin" />
          <p className="text-green-700 font-medium text-sm">Loading {type.toUpperCase()} map...</p>
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="absolute inset-0 z-[999] bg-red-50 flex flex-col items-center justify-center gap-2 p-4">
          <span className="text-2xl">⚠️</span>
          <p className="text-red-700 font-medium text-center text-sm">{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="mt-2 px-4 py-2 bg-red-600 text-white rounded-lg text-sm"
          >
            Retry
          </button>
        </div>
      )}

      {/* Leaflet Map Container */}
      <div ref={mapRef} style={{ height: "100%", width: "100%", paddingTop: "40px" }} />

      {/* Legend */}
      {!loading && !error && <Legend type={type} />}

      {/* Coordinates Status Bar (like QGIS bottom bar) */}
      {coords && (
        <div className="absolute bottom-0 left-0 right-0 z-[1000] bg-white/90 backdrop-blur px-3 py-1 text-xs text-gray-500 border-t border-green-100 flex gap-4">
          <span>📍 Lat: {coords.lat}</span>
          <span>Lng: {coords.lng}</span>
        </div>
      )}
    </div>
  );
}
