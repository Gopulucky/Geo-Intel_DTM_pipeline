// frontend/src/components/DrainageMapPanel.jsx
// Full-screen Leaflet map: renders DTM raster + GeoJSON drainage network.
// Clicking a stream segment fires onFeatureClick(properties) to populate
// the left-side attribute panel in ResultsPage.

import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import GeoRasterLayer from "georaster-layer-for-leaflet";
import parseGeoraster from "georaster";

// Fix Leaflet default icon (broken by Vite)
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png",
  iconUrl:       "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png",
  shadowUrl:     "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png",
});

// ── Strahler order → visual style ────────────────────────────────────────────
function streamStyle(feature) {
  const order = feature?.properties?.strahler_ord || 1;
  const styles = {
    1: { color: "#60a5fa", weight: 1.5, opacity: 0.75 },   // blue-400
    2: { color: "#3b82f6", weight: 2.5, opacity: 0.85 },   // blue-500
    3: { color: "#2563eb", weight: 3.5, opacity: 0.90 },   // blue-600
    4: { color: "#1d4ed8", weight: 5,   opacity: 0.95 },   // blue-700
    5: { color: "#1e3a8a", weight: 6.5, opacity: 1.00 },   // blue-900
  };
  return styles[order] || styles[1];
}

// ── DTM elevation color ramp (matches TifViewer) ──────────────────────────────
function dtmColor(values, min, max) {
  const val = values[0];
  if (val === null || val === undefined || isNaN(val)) return null;
  const norm = Math.max(0, Math.min(1, (val - min) / (max - min)));
  if (norm < 0.2) {
    const t = norm / 0.2;
    return `rgb(${Math.round(t*34)},${Math.round(t*139)},${Math.round(139 + t*(87-139))})`;
  } else if (norm < 0.5) {
    const t = (norm - 0.2) / 0.3;
    return `rgb(${Math.round(34+t*(154-34))},${Math.round(139+t*(205-139))},${Math.round(87+t*(50-87))})`;
  } else if (norm < 0.8) {
    const t = (norm - 0.5) / 0.3;
    return `rgb(${Math.round(154+t*(240-154))},${Math.round(205+t*(230-205))},${Math.round(50+t*(140-50))})`;
  } else {
    const t = (norm - 0.8) / 0.2;
    return `rgb(${Math.round(240+t*(255-240))},${Math.round(230+t*(255-230))},${Math.round(140+t*(255-140))})`;
  }
}

// ── Main Component ────────────────────────────────────────────────────────────

export default function DrainageMapPanel({ dtmUrl, geojsonData, dynamicGeojsonData, onFeatureClick, selectedFeatureId }) {
  const mapRef      = useRef(null);
  const mapInst     = useRef(null);
  const dtmLayer    = useRef(null);
  const streamLayer = useRef(null);

  const [dtmLoading,    setDtmLoading]    = useState(false);
  const [dtmError,      setDtmError]      = useState(null);
  const [streamLoading, setStreamLoading] = useState(false);
  const [coords,        setCoords]        = useState(null);
  const [hoveredId,     setHoveredId]     = useState(null);
  const [viewMode,      setViewMode]      = useState("baseline"); // "baseline" | "dynamic"

  // ── Init Leaflet map ──────────────────────────────────────────────────────
  useEffect(() => {
    if (mapInst.current) return;

    const map = L.map(mapRef.current, {
      center: [20.5, 78.9],
      zoom: 5,
      zoomControl: false,
      attributionControl: false,
    });

    // Dark base tile — OSM dark variant for geo context
    L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
      attribution: "© OSM © CartoDB",
      subdomains: "abcd",
      maxZoom: 19,
      opacity: 0.5,
    }).addTo(map);

    // Custom zoom control (top-right)
    L.control.zoom({ position: "topright" }).addTo(map);

    map.on("mousemove", (e) => {
      setCoords({ lat: e.latlng.lat.toFixed(6), lng: e.latlng.lng.toFixed(6) });
    });

    mapInst.current = map;
  }, []);

  // ── Load DTM raster ───────────────────────────────────────────────────────
  useEffect(() => {
    if (!dtmUrl || !mapInst.current) return;

    setDtmLoading(true);
    setDtmError(null);

    if (dtmLayer.current) {
      mapInst.current.removeLayer(dtmLayer.current);
      dtmLayer.current = null;
    }

    fetch(dtmUrl)
      .then(r => { if (!r.ok) throw new Error(`DTM fetch failed: ${r.status}`); return r.arrayBuffer(); })
      .then(buf => parseGeoraster(buf))
      .then(gr => {
        const min = gr.mins[0];
        const max = gr.maxs[0];
        const layer = new GeoRasterLayer({
          georaster: gr,
          opacity: 0.80,
          resolution: 256,
          pixelValuesToColorFn: (v) => dtmColor(v, min, max),
        });
        layer.addTo(mapInst.current);
        dtmLayer.current = layer;
        mapInst.current.fitBounds(layer.getBounds());
        setDtmLoading(false);
      })
      .catch(err => {
        console.error("DTM load error:", err);
        setDtmError(err.message);
        setDtmLoading(false);
      });
  }, [dtmUrl]);

  // ── Render Stream GeoJSON ─────────────────────────────────────────────────
  useEffect(() => {
    if (!mapInst.current) return;

    const activeGeojson = viewMode === "baseline" ? geojsonData : dynamicGeojsonData;

    // Clear existing
    if (streamLayer.current) {
      mapInst.current.removeLayer(streamLayer.current);
      streamLayer.current = null;
    }

    if (!activeGeojson || !activeGeojson.features) return;

    setStreamLoading(true);
    try {
      const layer = L.geoJSON(activeGeojson, {
        style: (feature) => {
          const isSelected = feature?.properties?.id === selectedFeatureId;
          const base = streamStyle(feature);
          return isSelected
            ? { ...base, color: "#f59e0b", weight: base.weight + 2, opacity: 1 }
            : base;
        },
        onEachFeature: (feature, lyr) => {
          const props = feature.properties || {};

          // Hover effect
          lyr.on("mouseover", function () {
            setHoveredId(props.id);
            this.setStyle({
              color: "#34d399",       // emerald highlight
              weight: (streamStyle(feature).weight || 2) + 3,
              opacity: 1,
            });
            this.bringToFront();
          });
          lyr.on("mouseout", function () {
            setHoveredId(null);
            layer.resetStyle(this);
          });

          // Click: fire selection callback
          lyr.on("click", function (e) {
            L.DomEvent.stopPropagation(e);
            if (onFeatureClick) onFeatureClick(props);
          });
        },
      });

      layer.addTo(mapInst.current);
      streamLayer.current = layer;

      // If DTM hasn't loaded yet, fit to streams
      if (!dtmLayer.current && activeGeojson.features?.length) {
        mapInst.current.fitBounds(layer.getBounds(), { padding: [30, 30] });
      }
      setStreamLoading(false);
    } catch (err) {
      console.error("GeoJSON render error:", err);
      setStreamLoading(false);
    }
  }, [geojsonData, dynamicGeojsonData, viewMode, onFeatureClick]);

  // Re-style when selection changes
  useEffect(() => {
    if (!streamLayer.current) return;
    streamLayer.current.eachLayer((lyr) => {
      const props = lyr.feature?.properties || {};
      const isSelected = props.id === selectedFeatureId;
      const base = streamStyle(lyr.feature);
      lyr.setStyle(
        isSelected
          ? { ...base, color: "#f59e0b", weight: base.weight + 2, opacity: 1 }
          : base
      );
    });
  }, [selectedFeatureId]);

  return (
    <div className="relative w-full h-full">
      {/* Leaflet container */}
      <div ref={mapRef} style={{ width: "100%", height: "100%" }} />

      {/* DTM loading spinner */}
      {dtmLoading && (
        <div className="absolute inset-0 z-[900] flex items-center justify-center bg-slate-900/60 backdrop-blur-sm pointer-events-none">
          <div className="flex flex-col items-center gap-3">
            <div className="w-10 h-10 rounded-full border-4 border-blue-400/30 border-t-blue-400 animate-spin" />
            <span className="text-blue-300 text-sm font-medium">Loading DTM raster…</span>
          </div>
        </div>
      )}

      {/* DTM error */}
      {dtmError && !dtmLoading && (
        <div className="absolute top-14 left-1/2 -translate-x-1/2 z-[900] bg-red-900/80 text-red-200 text-xs px-4 py-2 rounded-xl backdrop-blur border border-red-700/50 max-w-xs text-center">
          ⚠️ DTM layer unavailable — {dtmError}
        </div>
      )}

      {/* Map legend */}
      <div className="absolute bottom-10 right-3 z-[900] bg-slate-900/80 backdrop-blur-md border border-slate-700/50 rounded-xl p-3 text-xs">
        <p className="font-semibold text-slate-300 mb-2 text-center tracking-wide uppercase text-[10px]">Stream Order</p>
        {[
          { order: 1, color: "#60a5fa", label: "1st — Headwaters" },
          { order: 2, color: "#3b82f6", label: "2nd — Minor streams" },
          { order: 3, color: "#2563eb", label: "3rd — Sub-tributaries" },
          { order: 4, color: "#1d4ed8", label: "4th — Tributaries" },
          { order: 5, color: "#1e3a8a", label: "5th — Main channel" },
        ].map(({ color, label }) => (
          <div key={label} className="flex items-center gap-2 mb-1">
            <div className="w-6 h-1.5 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
            <span className="text-slate-400">{label}</span>
          </div>
        ))}
        <div className="border-t border-slate-700/50 mt-2 pt-2 flex items-center gap-2">
          <div className="w-6 h-1.5 rounded-full flex-shrink-0 bg-amber-400" />
          <span className="text-amber-300">Selected segment</span>
        </div>
      </div>

      {/* View Toggle */}
      {dynamicGeojsonData && (
        <div className="absolute top-4 left-1/2 -translate-x-1/2 z-[900] bg-slate-900/80 backdrop-blur-md border border-slate-700/50 rounded-xl p-1 flex gap-1 shadow-lg">
          <button 
            onClick={() => setViewMode("baseline")}
            className={`px-4 py-1.5 text-xs font-semibold rounded-lg transition-colors ${viewMode === "baseline" ? "bg-blue-600 text-white" : "text-slate-400 hover:text-slate-200 hover:bg-slate-800"}`}
          >
            Engineering Baseline
          </button>
          <button 
            onClick={() => setViewMode("dynamic")}
            className={`px-4 py-1.5 text-xs font-semibold rounded-lg transition-colors ${viewMode === "dynamic" ? "bg-teal-600 text-white" : "text-slate-400 hover:text-slate-200 hover:bg-slate-800"}`}
          >
            Dynamic Weather
          </button>
        </div>
      )}

      {/* Stream loading indicator */}
      {streamLoading && (
        <div className="absolute top-3 left-1/2 -translate-x-1/2 z-[900] bg-blue-900/80 text-blue-200 text-xs px-4 py-1.5 rounded-full backdrop-blur flex items-center gap-2">
          <div className="w-3 h-3 rounded-full border-2 border-blue-400/40 border-t-blue-400 animate-spin" />
          Rendering stream network…
        </div>
      )}

      {/* Coordinates bar */}
      {coords && (
        <div className="absolute bottom-0 left-0 right-0 z-[900] bg-slate-900/70 backdrop-blur-sm text-[11px] text-slate-400 px-4 py-1 flex gap-6 font-mono border-t border-slate-700/30">
          <span>📍 {coords.lat}°N</span>
          <span>{coords.lng}°E</span>
          {hoveredId != null && (
            <span className="text-emerald-400">Segment #{hoveredId} — click to inspect</span>
          )}
        </div>
      )}
    </div>
  );
}
