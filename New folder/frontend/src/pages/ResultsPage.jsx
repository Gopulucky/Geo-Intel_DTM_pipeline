// frontend/src/pages/ResultsPage.jsx
// Full-page split layout:
//   LEFT  — attribute panel (job info, collapsible sections, hydraulic inspector)
//   RIGHT — interactive Leaflet map with DTM raster + GeoJSON drainage network
//
// Responsive: Sidebar becomes a sliding drawer on mobile, side-by-side on lg+ screens.

import { useEffect, useState, useCallback } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "../api/client";
import TifViewer from "../components/TifViewer";
import DrainageMapPanel from "../components/DrainageMapPanel";

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmt(val, digits = 3) {
  if (val === null || val === undefined || isNaN(val)) return "—";
  return Number(val).toFixed(digits);
}

function fmtArea(m2) {
  if (!m2) return "—";
  return m2 >= 1_000_000
    ? `${(m2 / 1_000_000).toFixed(3)} km²`
    : `${Math.round(m2).toLocaleString()} m²`;
}

const STRAHLER_LABELS = { 1: "1st — Headwater", 2: "2nd — Minor", 3: "3rd — Sub-trib.", 4: "4th — Tributary", 5: "5th — Main Channel" };
const STRAHLER_COLORS = { 1: "#60a5fa", 2: "#3b82f6", 3: "#2563eb", 4: "#1d4ed8", 5: "#1e3a8a" };

const TIF_CONFIGS = [
  { suffix: "_LULC.tif",             type: "lulc",      title: "🌱 LULC Classification" },
  { suffix: "_DTM.tif",              type: "dtm",       title: "🏔️ Digital Terrain Model" },
  { suffix: "_FlowAccumulation.tif", type: "hydrology", title: "💧 Flow Accumulation" },
  { suffix: "_TWI.tif",              type: "hydrology", title: "💦 Topographic Wetness Index" },
  { suffix: "_Catchments.tif",       type: "hydrology", title: "🗺️ Catchment Basins" },
];

// ── Sub-components ────────────────────────────────────────────────────────────

function CollapsibleSection({ title, icon, badge, defaultOpen = false, children }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border border-slate-700/50 rounded-xl overflow-hidden mb-3 bg-slate-800/20 flex-shrink-0">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-4 py-3.5 bg-slate-800/80 hover:bg-slate-700/80 transition-colors text-left"
      >
        <span className="flex items-center gap-2.5 text-[13px] font-semibold text-slate-200 tracking-wide">
          <span className="text-base drop-shadow-sm">{icon}</span>{title}
          {badge != null && (
            <span className="ml-1 text-[10px] bg-slate-700 text-teal-300 px-2 py-0.5 rounded-full font-mono border border-slate-600">{badge}</span>
          )}
        </span>
        <svg
          className={`w-4 h-4 text-slate-400 transition-transform duration-300 ${open ? "rotate-180 text-brand-400" : ""}`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {open && <div className="p-3.5 bg-slate-900/60 animate-slide-down border-t border-slate-700/50">{children}</div>}
    </div>
  );
}

function StatRow({ label, value, unit, highlight }) {
  return (
    <div className={`flex items-center justify-between py-2 px-2.5 rounded-lg transition-colors ${highlight ? "bg-teal-500/10 border border-teal-500/20" : "hover:bg-slate-800/60"}`}>
      <span className="text-[11px] lg:text-xs text-slate-400 font-medium tracking-wide">{label}</span>
      <span className={`text-[11px] lg:text-xs font-mono font-bold ${highlight ? "text-teal-300 drop-shadow-sm" : "text-slate-200"}`}>
        {value}{unit ? <span className="text-slate-500 ml-1 font-normal">{unit}</span> : null}
      </span>
    </div>
  );
}

// ── Hydraulic Inspector Panel ─────────────────────────────────────────────────

function HydraulicInspector({ feature }) {
  if (!feature) {
    return (
      <div className="flex flex-col items-center justify-center py-10 text-center">
        <div className="w-16 h-16 rounded-full bg-slate-800/80 flex items-center justify-center mb-4 text-3xl shadow-inner border border-slate-700">
          <span className="animate-pulse">👆</span>
        </div>
        <p className="text-slate-300 text-sm font-medium">Select Stream Segment</p>
        <p className="text-slate-500 text-xs mt-1.5 max-w-[200px] mx-auto">Tap any drainage segment on the map to inspect hydraulics.</p>
      </div>
    );
  }

  const order    = feature.strahler_ord || 1;
  const ordColor = STRAHLER_COLORS[order] || "#60a5fa";
  const ordLabel = STRAHLER_LABELS[order] || "Unknown";

  return (
    <div className="space-y-3 animate-fade-in">
      {/* Header badge */}
      <div className="flex items-center gap-2 mb-4 bg-slate-800/80 p-2 rounded-lg border border-slate-700/50">
        <div className="w-3 h-3 rounded-full flex-shrink-0 shadow-[0_0_8px_rgba(255,255,255,0.3)]" style={{ backgroundColor: ordColor }} />
        <span className="text-xs font-bold text-slate-200">{ordLabel}</span>
        <span className="ml-auto text-[10px] text-slate-400 font-mono bg-slate-900 px-2 py-0.5 rounded border border-slate-700">ID: {feature.id}</span>
      </div>

      {/* Design Storm */}
      <div className="bg-blue-950/40 border border-blue-800/40 rounded-xl p-3 mb-3 relative overflow-hidden group">
        <div className="absolute top-0 left-0 w-1 h-full bg-blue-500"></div>
        <p className="text-[10px] text-blue-400 uppercase tracking-widest font-bold mb-1">Design Storm (P₉₉)</p>
        <p className="text-xl font-black text-blue-300 font-display tracking-tight">
          {fmt(feature.rainfall_mm_day, 1)} <span className="text-xs text-blue-500 font-medium">mm/day</span>
        </p>
        <p className="text-[10px] text-blue-600/80 mt-1 font-medium">Open-Meteo 10-year return period</p>
      </div>

      {/* Geometry */}
      <div className="space-y-0.5">
        <StatRow label="Reach Length"       value={fmt(feature.length_m, 1)}           unit="m" />
        <StatRow label="Catchment Area"     value={fmtArea(feature.catchment_area_m2)} />
      </div>

      {/* Hydraulics */}
      <div className="border-t border-slate-700/50 pt-3 mt-3">
        <p className="text-[10px] text-slate-500 uppercase tracking-widest font-bold mb-2">Rational Method (Q = C·i·A)</p>
        <div className="space-y-0.5">
          <StatRow label="Channel Slope"    value={fmt(feature.slope_m_m, 4)}          unit="m/m" />
          <StatRow label="Peak Flow (Q)"    value={fmt(feature.peak_flow_m3s, 4)}       unit="m³/s" highlight />
          <StatRow label="Channel Width"    value={fmt(feature.channel_width_m, 2)}     unit="m" />
          <StatRow label="Channel Depth"    value={fmt(feature.channel_depth_m, 2)}     unit="m" />
          <StatRow label="Flow Velocity"    value={fmt(feature.velocity_m_s, 2)}        unit="m/s" />
        </div>
      </div>

      {/* Cross-section visual */}
      <div className="border-t border-slate-700/50 pt-3 mt-3">
        <p className="text-[10px] text-slate-500 uppercase tracking-widest font-bold mb-3">Profile Visualization</p>
        <div className="relative h-16 bg-surface-darker rounded-xl overflow-hidden flex items-end px-4 pb-1 border border-slate-800 shadow-inner">
          {/* Ground */}
          <div className="absolute bottom-0 left-0 right-0 h-4 bg-amber-900/40 border-t border-amber-800/50 rounded-b-xl" />
          {/* Water channel */}
          {feature.channel_width_m && feature.channel_depth_m && (
            <div
              className="bg-blue-500/30 border-x border-b border-blue-400/50 rounded-b-sm mx-auto relative z-10 backdrop-blur-[2px]"
              style={{
                width: `${Math.min(90, Math.max(15, (feature.channel_width_m / 5) * 70))}%`,
                height: `${Math.min(80, Math.max(20, (feature.channel_depth_m / 2) * 70))}%`,
              }}
            >
              {/* Water surface line */}
              <div className="absolute top-0 left-0 right-0 h-[1px] bg-blue-300/60 shadow-[0_0_5px_rgba(96,165,250,0.8)]"></div>
              
              <div className="absolute inset-0 flex items-center justify-center text-blue-200 text-[10px] font-mono font-bold drop-shadow-md">
                {fmt(feature.channel_width_m, 1)}m
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Main ResultsPage ──────────────────────────────────────────────────────────

export default function ResultsPage() {
  const { jobId } = useParams();

  const [files,          setFiles]          = useState([]);
  const [job,            setJob]            = useState(null);
  const [loadError,      setLoadError]      = useState(null);
  const [geojsonData,    setGeojsonData]    = useState(null);
  const [geojsonError,   setGeojsonError]   = useState(null);
  const [selectedFeature, setSelectedFeature] = useState(null);

  // Responsive state for sidebar (drawer on mobile)
  const [sidebarOpen,    setSidebarOpen]    = useState(false); // Used for mobile drawer
  const [isMobile,       setIsMobile]       = useState(false);

  // Active top-level tab (nav bar)
  const [activeTab,      setActiveTab]      = useState("maps");
  
  // Selected raster for popup modal
  const [selectedRasterIndex, setSelectedRasterIndex] = useState(null);

  // Physics Calculator State
  const [rainfall, setRainfall] = useState(100);
  const [runoff, setRunoff] = useState(0.6);
  const [channelWidth, setChannelWidth] = useState(0.5);
  const [channelDepth, setChannelDepth] = useState(0.3);
  const [slope, setSlope] = useState(0.001); 
  const [roughness, setRoughness] = useState(0.035);

  // Physics Math
  const manningDischarge = () => {
    const w = parseFloat(channelWidth) || 0;
    const d = parseFloat(channelDepth) || 0;
    const s = parseFloat(slope) || 0;
    const n = parseFloat(roughness) || 1;
    if (w <= 0 || d <= 0 || s <= 0 || n <= 0) return 0;
    
    const A = w * d;
    const P = w + 2 * d;
    const R = A / P;
    const velocity = (1 / n) * Math.pow(R, 2/3) * Math.pow(s, 0.5);
    return A * velocity;
  };

  const rationalThreshold = (minDischarge) => {
    const r = parseFloat(rainfall) || 1;
    const c = parseFloat(runoff) || 1;
    if (r <= 0 || c <= 0) return 0;
    
    const area_ha = minDischarge / (0.00278 * c * r);
    const area_m2 = area_ha * 10000;
    return Math.max(10, Math.round(area_m2));
  };

  const currentQ = manningDischarge();
  const currentThreshold = rationalThreshold(currentQ);

  const handleRerun = async () => {
    try {
      await api.rerunHydrology(jobId, currentThreshold);
      // Let the polling system pick up the state change naturally
      // But we could force a refresh or show a local loading state if needed.
    } catch (err) {
      alert("Failed to re-run: " + err.message);
    }
  };

  // Check viewport size
  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 1024); // lg breakpoint in tailwind
      if (window.innerWidth >= 1024) setSidebarOpen(true);
    };
    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  // ── Data loading and Polling ──────────────────────────────────────────────
  useEffect(() => {
    let intervalId;
    
    const load = async () => {
      try {
        const [statusData, filesData] = await Promise.all([
          api.getStatus(jobId),
          api.getFiles(jobId),
        ]);
        setJob(statusData);
        setFiles(filesData.files || []);
        
        // If it's re_running, keep polling. Otherwise, clear interval.
        if (statusData.status !== "re_running_hydrology" && statusData.status !== "re_running" && statusData.status !== "running") {
           if (intervalId) clearInterval(intervalId);
        }
      } catch (err) {
        setLoadError(err.message || "Failed to load results.");
        if (intervalId) clearInterval(intervalId);
      }
    };

    // Initial load
    load();
    
    // Set up polling every 2.5 seconds
    intervalId = setInterval(load, 2500);

    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [jobId]);

  // Load GeoJSON for stream inspection
  useEffect(() => {
    // Only fetch if job is complete or partial
    if (job?.status === "complete" || job?.status === "partial") {
      api.getGeoJSON(jobId)
        .then(data => {
          setGeojsonData(data);
          // If we had a geojson error before, clear it on successful fetch
          setGeojsonError(null);
        })
        .catch(err => setGeojsonError(err.message));
    }
  }, [jobId, job?.status]);

  const handleFeatureClick = useCallback((props) => {
    setSelectedFeature(props);
    if (isMobile) setSidebarOpen(true);
  }, [isMobile]);

  // ── Derived data ────────────────────────────────────────────────────────
  const tifFiles  = files.filter(f => f.name.endsWith(".tif"));
  const pngFiles  = files.filter(f => f.name.endsWith(".png"));
  const htmlFiles = files.filter(f => f.name.endsWith(".html"));

  const dtmFile   = files.find(f => f.name.endsWith("_DTM.tif"));
  const dtmUrl    = dtmFile ? api.getFileUrl(jobId, dtmFile.name) : null;

  const matchedSet = new Set();
  const tifViewers = [];
  TIF_CONFIGS.forEach(cfg => {
    const match = tifFiles.find(f => f.name.endsWith(cfg.suffix));
    if (match && !matchedSet.has(match.name)) {
      matchedSet.add(match.name);
      tifViewers.push({ ...cfg, url: api.getFileUrl(jobId, match.name), filename: match.name });
    }
  });
  tifFiles.forEach(f => {
    if (!matchedSet.has(f.name)) {
      tifViewers.push({ suffix: f.name, type: "dtm", title: `📄 ${f.name}`,
        url: api.getFileUrl(jobId, f.name), filename: f.name });
    }
  });

  const streamCount = geojsonData?.features?.length ?? null;

  // ── Error state ─────────────────────────────────────────────────────────
  if (loadError) {
    return (
      <div className="min-h-screen bg-surface-darker flex items-center justify-center p-4">
        <div className="glass-panel-dark rounded-3xl p-8 lg:p-10 max-w-md text-center shadow-2xl border-red-500/20 border">
          <div className="text-5xl mb-6">⚠️</div>
          <h2 className="text-2xl font-bold text-white mb-3 font-display">Unable to Load Data</h2>
          <p className="text-slate-400 mb-8">{loadError}</p>
          <Link to="/" className="inline-flex items-center justify-center bg-white text-slate-900 px-6 py-3 rounded-xl font-bold hover:bg-slate-200 transition-colors shadow-lg">
            Return to Mission Control
          </Link>
        </div>
      </div>
    );
  }

  // ── Main Render ─────────────────────────────────────────────────────────
  return (
    <div className="flex flex-col h-[100dvh] bg-surface-darker overflow-hidden font-body text-slate-100">

      {/* ── Top Header Bar ──────────────────────────────────────────────── */}
      <header className="flex-shrink-0 flex flex-wrap items-center justify-between px-4 lg:px-6 py-3 bg-slate-900/95 backdrop-blur border-b border-slate-800/80 z-[2000] shadow-md gap-4">
        <div className="flex items-center gap-3">
          <Link to="/" className="hidden sm:flex w-10 h-10 rounded-xl bg-gradient-to-br from-brand-600 to-teal-400 items-center justify-center text-xl shadow-lg shadow-brand-500/20 hover:scale-105 transition-transform">
            🌍
          </Link>
          <button className="lg:hidden w-10 h-10 flex items-center justify-center text-slate-400 hover:text-white" onClick={() => setSidebarOpen(!sidebarOpen)}>
             <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
               <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
             </svg>
          </button>
          
          <div className="hidden sm:block">
            <h1 className="text-[13px] lg:text-sm font-bold text-white tracking-wide font-display">Geo-Intel Mission Data</h1>
            <div className="flex items-center gap-2 mt-0.5">
              <span className="text-[10px] font-mono bg-slate-800 text-brand-300 px-2 py-0.5 rounded border border-slate-700">
                {jobId}
              </span>
              <span className="text-xs text-slate-400 font-medium truncate max-w-[150px] lg:max-w-xs">{job?.village || "Loading…"}</span>
              {job?.status === "complete" && (
                <span className="hidden lg:inline-block text-[10px] bg-brand-500/10 text-brand-400 border border-brand-500/20 px-2 py-0.5 rounded-full font-bold uppercase tracking-wider">
                  ✓ Verified
                </span>
              )}
            </div>
          </div>
          
          {/* Mobile title */}
          <div className="sm:hidden font-display font-bold text-sm truncate max-w-[140px] text-white">
              {job?.village || "Mission Data"}
          </div>
        </div>

        {/* ── Global View Tabs (Moved to Header) ── */}
        <div className="flex bg-slate-900 rounded-xl p-1 border border-slate-700/50 shadow-inner order-last sm:order-none w-full sm:w-auto overflow-x-auto">
          {["maps", "web", "images", "files"].map(tab => (
            <button key={tab}
              onClick={() => setActiveTab(tab)}
              className={`flex-1 sm:flex-none whitespace-nowrap text-[11px] sm:text-xs font-bold py-2 px-4 rounded-lg transition-all capitalize
                ${activeTab === tab
                  ? "bg-slate-700 text-white shadow-sm"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
                }`}
            >
              {tab === "maps" ? "Rasters (TIF)" : tab === "web" ? "Web Visualizers" : tab === "images" ? "Previews" : "Archive"}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2 lg:gap-3">
          <Link to="/"
            className="hidden md:block text-xs text-slate-400 hover:text-white border border-slate-700 hover:border-slate-500 px-3 py-2 rounded-xl transition-colors font-semibold"
          >
            + New Mission
          </Link>
          <a href={api.getZipUrl(jobId)}
            className="text-[11px] lg:text-xs bg-white text-slate-900 hover:bg-slate-200 px-3 lg:px-4 py-2 rounded-xl font-bold transition-all shadow-md hover:shadow-lg flex items-center gap-2 group whitespace-nowrap"
          >
            <svg className="w-3.5 h-3.5 lg:w-4 lg:h-4 group-hover:-translate-y-0.5 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            <span className="hidden lg:inline">Export Assets</span>
            <span className="lg:hidden">Export</span>
          </a>
        </div>
      </header>

      {/* ── Main Body ───────────────────────────── */}
      <div className="flex flex-1 overflow-hidden relative">

        {/* ── MAP VIEW (Sidebar + Map) ─────────────────────────────────────────────────── */}
        {activeTab === "maps" && (
          <>
            <div 
              className={`fixed inset-0 bg-black/60 backdrop-blur-sm z-[1500] lg:hidden transition-opacity duration-300 ${sidebarOpen ? "opacity-100" : "opacity-0 pointer-events-none"}`}
              onClick={() => setSidebarOpen(false)}
            />
            
            <aside
              className={`absolute lg:relative top-0 bottom-0 left-0 z-[1600] flex flex-col bg-slate-900 border-r border-slate-800 shadow-2xl lg:shadow-none transition-transform duration-300 w-[85%] sm:w-[380px] lg:w-[400px] lg:translate-x-0
                ${sidebarOpen ? "translate-x-0" : "-translate-x-full"}`}
            >
              {/* Mobile drawer header */}
              <div className="lg:hidden flex items-center justify-between p-4 border-b border-slate-800 bg-slate-900">
                <h2 className="font-display font-bold text-white text-lg">Mission Intelligence</h2>
                <button onClick={() => setSidebarOpen(false)} className="w-8 h-8 flex items-center justify-center rounded-full bg-slate-800 text-slate-400 hover:text-white">
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                </button>
              </div>

              <div className="flex-1 overflow-y-auto custom-scrollbar px-4 pt-4 pb-8 space-y-3">
                {/* ── Job Stats ─────────────────────────────────────────── */}
                <CollapsibleSection title="Mission Summary" icon="📊" defaultOpen>
                  <div className="space-y-1">
                    <StatRow label="Target Village" value={job?.village || "—"} />
                    <StatRow label="Processing Status" value={job?.status  || "—"} />
                    <StatRow label="Dataset Volume" value={job?.file_size_mb ? `${job.file_size_mb} MB` : "—"} />
                    <StatRow label="Drainage Segments" value={streamCount ?? "Loading…"} />
                  </div>
                </CollapsibleSection>

                {/* ── Hydraulic Attribute Inspector ─────────────────────── */}
                <CollapsibleSection
                  title="Hydraulic Inspector"
                  icon="🔬"
                  badge={selectedFeature ? `Seg #${selectedFeature.id}` : "Standby"}
                  defaultOpen
                >
                  <HydraulicInspector feature={selectedFeature} />
                  {geojsonError && (
                    <p className="text-[11px] text-red-400 mt-2 bg-red-500/10 p-2 rounded-lg border border-red-500/20 text-center font-medium">
                      ⚠️ Network data unavailable — {geojsonError}
                    </p>
                  )}
                </CollapsibleSection>

                {/* ── Map Layers (QGIS style) ───────────────────────────────────────── */}
                <CollapsibleSection title="Map Layers" icon="🗂️" badge={tifViewers.length + 1} defaultOpen>
                  <div className="space-y-2">
                    {/* Hydrological Network layer (Default) */}
                    <label className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${selectedRasterIndex === null ? "bg-slate-800 border-teal-500/50" : "bg-slate-900 border-slate-700/80 hover:bg-slate-800"}`}>
                       <input 
                         type="checkbox" 
                         checked={selectedRasterIndex === null}
                         onChange={() => {
                           setSelectedRasterIndex(null);
                           if (isMobile) setSidebarOpen(false);
                         }} 
                         className="w-4 h-4 accent-teal-500 cursor-pointer" 
                       />
                       <span className="text-sm font-semibold text-slate-200">Hydrological Network</span>
                    </label>

                    {/* Raster Layers */}
                    {tifViewers.length === 0 ? (
                      <p className="text-xs text-slate-500 text-center py-4 font-medium">No raster models generated.</p>
                    ) : tifViewers.map((v, i) => (
                      <label key={i} className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${selectedRasterIndex === i ? "bg-slate-800 border-teal-500/50" : "bg-slate-900 border-slate-700/80 hover:bg-slate-800"}`}>
                         <input 
                           type="checkbox" 
                           checked={selectedRasterIndex === i}
                           onChange={(e) => {
                             if (e.target.checked) {
                               setSelectedRasterIndex(i);
                             } else {
                               setSelectedRasterIndex(null);
                             }
                             if (isMobile) setSidebarOpen(false);
                           }} 
                           className="w-4 h-4 accent-teal-500 cursor-pointer" 
                         />
                         <span className="text-sm font-semibold text-slate-200">{v.title}</span>
                      </label>
                    ))}
                  </div>
                </CollapsibleSection>

                {/* ── Hydrology Design Parameters ──────────────────────────────── */}
                <CollapsibleSection title="Hydrology Parameters" icon="⚙️" defaultOpen={false}>
                  <div className="space-y-4">
                    {/* Sliders */}
                    <div>
                      <label className="flex justify-between text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1 ml-1">
                        <span>Rainfall (I)</span><span className="text-brand-400 font-mono">{rainfall} mm/hr</span>
                      </label>
                      <input type="range" min="10" max="200" step="5" value={rainfall} onChange={(e) => setRainfall(e.target.value)} className="w-full accent-brand-500" />
                    </div>
                    <div>
                      <label className="flex justify-between text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1 ml-1">
                        <span>Runoff Coeff (C)</span><span className="text-brand-400 font-mono">{runoff}</span>
                      </label>
                      <input type="range" min="0.1" max="0.95" step="0.05" value={runoff} onChange={(e) => setRunoff(e.target.value)} className="w-full accent-brand-500" />
                    </div>
                    <div>
                      <label className="flex justify-between text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1 ml-1">
                        <span>Channel Width</span><span className="text-brand-400 font-mono">{channelWidth} m</span>
                      </label>
                      <input type="range" min="0.1" max="3.0" step="0.1" value={channelWidth} onChange={(e) => setChannelWidth(e.target.value)} className="w-full accent-brand-500" />
                    </div>
                    <div>
                      <label className="flex justify-between text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1 ml-1">
                        <span>Channel Depth</span><span className="text-brand-400 font-mono">{channelDepth} m</span>
                      </label>
                      <input type="range" min="0.05" max="2.0" step="0.05" value={channelDepth} onChange={(e) => setChannelDepth(e.target.value)} className="w-full accent-brand-500" />
                    </div>

                    {/* Math Results */}
                    <div className="bg-slate-900 border border-slate-700/80 rounded-lg p-3">
                      <div className="flex justify-between items-center mb-2">
                        <span className="text-[10px] text-slate-500 font-bold uppercase tracking-widest">Discharge</span>
                        <span className="text-xs font-mono font-bold text-slate-200">{currentQ.toFixed(3)} m³/s</span>
                      </div>
                      <div className="flex justify-between items-center">
                        <span className="text-[10px] text-slate-500 font-bold uppercase tracking-widest">Threshold</span>
                        <span className="text-xs font-mono font-bold text-brand-400">{currentThreshold.toLocaleString()} cells</span>
                      </div>
                    </div>

                    {/* Action Button */}
                    <button
                      onClick={handleRerun}
                      disabled={job?.status === "re_running" || job?.status === "re_running_hydrology"}
                      className={`w-full py-2.5 rounded-lg text-xs font-bold transition-all shadow-md active:scale-95 flex items-center justify-center gap-2 ${
                        (job?.status === "re_running" || job?.status === "re_running_hydrology")
                          ? "bg-slate-800 text-slate-500 cursor-not-allowed" 
                          : "bg-gradient-to-r from-brand-600 to-teal-500 hover:from-brand-500 hover:to-teal-400 text-white"
                      }`}
                    >
                      {(job?.status === "re_running" || job?.status === "re_running_hydrology") ? (
                        <>
                           <svg className="animate-spin h-4 w-4 text-slate-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                           </svg>
                           Calculating...
                        </>
                      ) : (
                        "Re-run Drainage Analysis"
                      )}
                    </button>
                  </div>
                </CollapsibleSection>


              </div>
            </aside>

            {/* ── RIGHT: Interactive Map ─────────────────────────────────────── */}
            <main className="flex-1 relative overflow-hidden bg-slate-950">
              
              {/* Mobile Sidebar Toggle Button (floating on map) */}
              <button 
                onClick={() => setSidebarOpen(true)}
                className="absolute bottom-6 left-1/2 -translate-x-1/2 z-[1000] lg:hidden bg-slate-900/95 backdrop-blur-md text-white border border-slate-700 shadow-[0_10px_30px_rgba(0,0,0,0.5)] px-6 py-3 rounded-full flex items-center gap-2 font-semibold text-xs active:scale-95 transition-transform"
              >
                <svg className="w-4 h-4 text-brand-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" /></svg>
                Inspect Data
              </button>

              {selectedRasterIndex === null ? (
                <>
                  {/* Map type label */}
                  <div className="absolute top-4 left-4 z-[1000] bg-slate-900/80 backdrop-blur-md border border-slate-700/80 shadow-lg rounded-xl px-4 py-2.5 text-[11px] lg:text-xs font-bold text-slate-200 flex items-center gap-2.5 max-w-[calc(100vw-32px)]">
                    <span className="w-2.5 h-2.5 rounded-full bg-teal-500 shadow-[0_0_8px_rgba(20,184,166,0.8)] animate-pulse shrink-0" />
                    <span className="truncate">Hydrological Network — {job?.village || "…"}</span>
                    {streamCount != null && (
                      <span className="ml-1 text-slate-500 font-mono shrink-0">({streamCount} segs)</span>
                    )}
                  </div>

                  <DrainageMapPanel
                    dtmUrl={dtmUrl}
                    geojsonData={geojsonData}
                    onFeatureClick={handleFeatureClick}
                    selectedFeatureId={selectedFeature?.id}
                  />

                  {/* Hint if no GeoJSON */}
                  {(!geojsonData && !geojsonError) && (
                    <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-[800] bg-slate-950/50 backdrop-blur-sm">
                      <div className="bg-slate-900 border border-slate-700/80 shadow-2xl rounded-2xl px-8 py-6 text-center max-w-sm">
                        <div className="w-12 h-12 border-4 border-slate-700 border-t-brand-500 rounded-full animate-spin mx-auto mb-4"></div>
                        <h3 className="text-white font-bold font-display mb-1">Synthesizing Network</h3>
                        <p className="text-xs text-slate-400">Loading drainage vectors onto visualizer...</p>
                      </div>
                    </div>
                  )}

                  {/* Re-running overlay */}
                  {(job?.status === "re_running" || job?.status === "re_running_hydrology") && (
                    <div className="absolute inset-0 flex items-center justify-center z-[2000] bg-slate-950/70 backdrop-blur-md">
                      <div className="bg-slate-900 border border-brand-500/30 shadow-[0_0_50px_rgba(20,184,166,0.15)] rounded-2xl px-10 py-8 text-center max-w-sm animate-zoom-in">
                        <div className="relative w-16 h-16 mx-auto mb-6">
                           <div className="absolute inset-0 border-4 border-slate-700 border-t-brand-500 rounded-full animate-spin"></div>
                           <div className="absolute inset-2 border-4 border-slate-700 border-b-teal-400 rounded-full animate-spin-reverse"></div>
                        </div>
                        <h3 className="text-white font-bold font-display text-lg mb-2">Re-calculating Physics</h3>
                        <p className="text-xs text-slate-400">Fast-path hydrology extraction in progress. Streams will update momentarily...</p>
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <>
                  <div className="absolute top-4 left-4 z-[1000] bg-slate-900/80 backdrop-blur-md border border-slate-700/80 shadow-lg rounded-xl px-4 py-2.5 text-[11px] lg:text-xs font-bold text-slate-200 flex items-center gap-2.5">
                    <button onClick={() => setSelectedRasterIndex(null)} className="mr-2 text-brand-400 hover:text-brand-300 flex items-center gap-1 transition-colors">
                       <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" /></svg>
                       <span className="hidden sm:inline">Back to Network</span>
                    </button>
                    <div className="w-[1px] h-4 bg-slate-700 mx-1"></div>
                    <span className="truncate">{tifViewers[selectedRasterIndex].title}</span>
                  </div>
                  <div className="w-full h-full bg-slate-950">
                    <TifViewer 
                      tifUrl={tifViewers[selectedRasterIndex].url} 
                      type={tifViewers[selectedRasterIndex].type} 
                      title={tifViewers[selectedRasterIndex].title} 
                    />
                  </div>
                </>
              )}
            </main>
          </>
        )}

        {/* ── WEB VISUALIZERS VIEW (Full Page Grid) ─────────────────────────────────────────────────── */}
        {activeTab === "web" && (
          <main className="flex-1 overflow-y-auto bg-slate-950 p-6 lg:p-10 custom-scrollbar">
             <div className="max-w-7xl mx-auto">
                <h2 className="text-2xl font-display font-bold text-white mb-6">Interactive Web Visualizers</h2>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
                  {htmlFiles.length === 0 ? (
                    <p className="text-slate-500 text-center py-10 font-medium col-span-full bg-slate-900/50 rounded-2xl border border-slate-800">No web visualizers generated.</p>
                  ) : htmlFiles.map((f, i) => (
                    <a key={i} href={api.getFileUrl(jobId, f.name)} target="_blank" rel="noreferrer" 
                       className="group flex flex-col rounded-2xl overflow-hidden border border-teal-900/50 bg-slate-900 hover:bg-slate-800 hover:border-teal-500/50 transition-all shadow-lg hover:shadow-teal-900/20">
                      <div className="aspect-video bg-slate-950 flex items-center justify-center relative overflow-hidden">
                        <div className="absolute inset-0 bg-teal-500/5 group-hover:bg-teal-500/10 transition-colors"></div>
                        <span className="text-6xl drop-shadow-2xl group-hover:scale-110 transition-transform duration-500">🌍</span>
                      </div>
                      <div className="p-4 flex items-center justify-between border-t border-slate-800/50">
                        <div>
                          <p className="text-sm text-teal-100 font-bold truncate">{f.name}</p>
                          <p className="text-[10px] text-slate-500 font-mono mt-1">Interactive HTML Map</p>
                        </div>
                        <div className="w-8 h-8 rounded-full bg-teal-950/50 flex items-center justify-center text-teal-500 group-hover:text-teal-300 group-hover:bg-teal-900 transition-colors">
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                          </svg>
                        </div>
                      </div>
                    </a>
                  ))}
                </div>
             </div>
          </main>
        )}

        {/* ── IMAGES VIEW (Full Page Grid) ─────────────────────────────────────────────────── */}
        {activeTab === "images" && (
          <main className="flex-1 overflow-y-auto bg-slate-950 p-6 lg:p-10 custom-scrollbar">
             <div className="max-w-7xl mx-auto">
                <h2 className="text-2xl font-display font-bold text-white mb-6">Visual Previews</h2>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
                  {pngFiles.length === 0 ? (
                    <p className="text-slate-500 text-center py-10 font-medium col-span-full bg-slate-900/50 rounded-2xl border border-slate-800">No visual previews generated yet.</p>
                  ) : pngFiles.map((f, i) => (
                    <div key={i} className="rounded-2xl overflow-hidden border border-slate-700 bg-slate-900 group relative shadow-lg">
                      <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity z-10 flex flex-col justify-end p-4 pointer-events-none">
                         <p className="text-sm text-white font-mono font-bold truncate drop-shadow-md">{f.name}</p>
                      </div>
                      <a href={api.getFileUrl(jobId, f.name)} target="_blank" rel="noreferrer" className="block aspect-[4/3] overflow-hidden">
                        <img src={api.getFileUrl(jobId, f.name)} alt={f.name}
                          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" />
                      </a>
                    </div>
                  ))}
                </div>
             </div>
          </main>
        )}

        {/* ── FILES VIEW (Full Page List) ─────────────────────────────────────────────────── */}
        {activeTab === "files" && (
          <main className="flex-1 overflow-y-auto bg-slate-950 p-6 lg:p-10 custom-scrollbar">
             <div className="max-w-5xl mx-auto">
                <h2 className="text-2xl font-display font-bold text-white mb-6">File Archive</h2>
                <div className="space-y-3 bg-slate-900/30 p-2 rounded-3xl border border-slate-800">
                  {files.length === 0 ? (
                    <p className="text-slate-500 text-center py-10 font-medium">Archive empty.</p>
                  ) : files.map((f, i) => {
                    const ext = f.name.split(".").pop().toUpperCase();
                    const icon = ext === "TIF" ? "🗺️" : ext === "PNG" ? "🖼️" : ext === "HTML" ? "🌐" : ext === "GEOJSON" || ext === "JSON" ? "📐" : "📄";
                    return (
                      <div key={i} className="flex items-center gap-4 p-4 rounded-2xl bg-slate-900 hover:bg-slate-800 border border-slate-700/50 hover:border-slate-600 group transition-all shadow-sm">
                        <span className="text-3xl drop-shadow-sm bg-slate-800 p-3 rounded-xl border border-slate-700 group-hover:scale-105 transition-transform">{icon}</span>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-bold text-slate-200 truncate">{f.name}</p>
                          <div className="flex items-center gap-3 mt-1">
                             <span className="text-xs text-slate-500 font-mono tracking-wide bg-slate-950 px-2 py-0.5 rounded border border-slate-800">{f.size_mb.toFixed(2)} MB</span>
                             <span className="text-[10px] text-slate-600 uppercase font-bold">{ext} FILE</span>
                          </div>
                        </div>
                        <a href={api.getFileUrl(jobId, f.name)} download title="Download file"
                          className="w-12 h-12 flex items-center justify-center rounded-xl bg-slate-800 text-slate-400 hover:text-white hover:bg-teal-600 transition-colors shadow-sm"
                        >
                          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                          </svg>
                        </a>
                      </div>
                    );
                  })}
                </div>
             </div>
          </main>
        )}

      </div>
    </div>
  );
}
