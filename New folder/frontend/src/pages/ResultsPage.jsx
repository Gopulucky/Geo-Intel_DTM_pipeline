// frontend/src/pages/ResultsPage.jsx
import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "../api/client";
import TifViewer from "../components/TifViewer";

// Map filenames to TifViewer config — uses exact suffix matching
const TIF_CONFIGS = [
  { suffix: "_LULC.tif",                type: "lulc",      title: "🌱 LULC Classification Map" },
  { suffix: "_DTM.tif",                 type: "dtm",       title: "🏔️ Digital Terrain Model (DTM)" },
  { suffix: "_DSM.tif",                 type: "dsm",       title: "📡 Digital Surface Model (DSM)" },
  { suffix: "_CHM.tif",                 type: "chm",       title: "🌳 Canopy Height Model (CHM)" },
  { suffix: "_FlowAccumulation.tif",    type: "hydrology", title: "💧 Flow Accumulation" },
  { suffix: "_DrainageNetwork.tif",     type: "hydrology", title: "🌊 Drainage Network" },

  { suffix: "_TWI.tif",                 type: "hydrology", title: "💦 Topographic Wetness Index" },
  { suffix: "_Catchments.tif",          type: "hydrology", title: "🗺️ Catchment Basins" },
];

export default function ResultsPage() {
  const { jobId }       = useParams();
  const [files, setFiles] = useState([]);
  const [job, setJob]   = useState(null);
  const [activeTab, setActiveTab] = useState("maps");
  const [loadError, setLoadError] = useState(null);

  useEffect(() => {
    const load = async () => {
      try {
        const [statusData, filesData] = await Promise.all([
          api.getStatus(jobId),
          api.getFiles(jobId)
        ]);
        setJob(statusData);
        setFiles(filesData.files || []);
      } catch (err) {
        console.error("Failed to load results:", err);
        setLoadError(err.message || "Failed to load results. Is the backend running?");
      }
    };
    load();
  }, [jobId]);

  // Show error state
  if (loadError) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-3xl shadow-xl p-10 max-w-md text-center border border-red-100">
          <div className="w-20 h-20 bg-red-50 rounded-full flex items-center justify-center mx-auto mb-6">
             <div className="text-4xl">⚠️</div>
          </div>
          <h2 className="text-2xl font-bold text-slate-800 font-display mb-3">Unable to Load Data</h2>
          <p className="text-slate-500 mb-8">{loadError}</p>
          <Link to="/" className="inline-block bg-slate-900 hover:bg-slate-800 text-white px-8 py-3.5 rounded-xl font-medium transition-colors shadow-lg">
            Return to Dashboard
          </Link>
        </div>
      </div>
    );
  }

  // Find .tif files
  const tifFiles  = files.filter(f => f.name.endsWith(".tif"));
  const pngFiles  = files.filter(f => f.name.endsWith(".png"));
  const htmlFiles = files.filter(f => f.name.endsWith(".html"));
  const gpkgFiles = files.filter(f => f.name.endsWith(".gpkg"));

  // Match .tif files to viewer config using exact suffix matching
  const tifViewers = [];
  const matchedFilenames = new Set();

  TIF_CONFIGS.forEach(config => {
    const match = tifFiles.find(f => f.name.endsWith(config.suffix));
    if (match && !matchedFilenames.has(match.name)) {
      matchedFilenames.add(match.name);
      tifViewers.push({
        ...config,
        url: api.getFileUrl(jobId, match.name),
        filename: match.name
      });
    }
  });

  // Add remaining .tif files not matched by config (generic DTM viewer)
  tifFiles.forEach(f => {
    if (!matchedFilenames.has(f.name)) {
      tifViewers.push({
        suffix: f.name,
        type: "dtm",
        title: `📄 ${f.name}`,
        url: api.getFileUrl(jobId, f.name),
        filename: f.name
      });
    }
  });

  return (
    <div className="min-h-screen bg-[#f8fafc] font-body text-slate-800 selection:bg-brand-500 selection:text-white pb-12">

      {/* Premium Header */}
      <div className="bg-white border-b border-slate-200 shadow-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-5 flex flex-col md:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-gradient-to-br from-brand-500 to-emerald-400 rounded-xl flex items-center justify-center shadow-lg shadow-brand-500/20 text-xl">
                🌍
            </div>
            <div>
                <h1 className="text-xl font-bold text-slate-900 font-display tracking-tight">Geo-Intel Mission Data</h1>
                <div className="flex items-center gap-2 mt-0.5">
                    <span className="text-xs font-medium bg-slate-100 text-slate-600 px-2 py-0.5 rounded-md border border-slate-200">ID: {jobId}</span>
                    <span className="text-sm font-medium text-slate-500">{job?.village || "Loading..."}</span>
                </div>
            </div>
            </div>
            
            <div className="flex items-center gap-3 w-full md:w-auto">
            <Link to="/" className="flex-1 md:flex-none text-center bg-slate-50 hover:bg-slate-100 text-slate-600 border border-slate-200 px-5 py-2.5 rounded-xl font-semibold text-sm transition-all hover:text-slate-900">
                New Analysis
            </Link>
            <a
                href={api.getZipUrl(jobId)}
                className="flex-1 md:flex-none text-center bg-slate-900 hover:bg-slate-800 text-white px-5 py-2.5 rounded-xl font-semibold text-sm transition-all shadow-md flex justify-center items-center gap-2 group"
            >
                <svg className="w-4 h-4 text-slate-400 group-hover:text-white transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" /></svg>
                Download Master ZIP
            </a>
            </div>
        </div>

        {/* Tab Navigation */}
        <div className="max-w-7xl mx-auto px-6 mt-2">
            <div className="flex gap-2 overflow-x-auto custom-scrollbar pb-px">
            {[
                { id: "maps",        label: "🗺️ Vector Maps", count: tifViewers.length },
                { id: "interactive", label: "🌐 3D Interactive", count: htmlFiles.length },
                { id: "images",      label: "🖼️ Synthetics", count: pngFiles.length },
                { id: "files",       label: "📁 Data Vault", count: files.length },
            ].map(tab => {
                const isActive = activeTab === tab.id;
                return (
                <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    className={`px-5 py-3.5 text-sm font-semibold transition-all whitespace-nowrap flex items-center gap-2 border-b-2 ${
                    isActive
                        ? "border-brand-500 text-brand-600 bg-brand-50/50"
                        : "border-transparent text-slate-500 hover:text-slate-800 hover:bg-slate-50"
                    }`}
                >
                    {tab.label}
                    <span className={`text-xs px-2 py-0.5 rounded-full font-mono ${isActive ? "bg-brand-100 text-brand-700" : "bg-slate-100 text-slate-500"}`}>
                        {tab.count}
                    </span>
                </button>
                )
            })}
            </div>
        </div>
      </div>

      {/* Tab Content */}
      <div className="max-w-7xl mx-auto p-6 mt-4">

        {/* TIF Maps Tab */}
        {activeTab === "maps" && (
          <div className="animate-slide-up">
            <div className="mb-8 bg-white p-4 rounded-2xl border border-slate-200 shadow-sm flex items-center gap-3">
               <div className="w-10 h-10 rounded-full bg-blue-50 text-blue-500 flex items-center justify-center shrink-0">
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
               </div>
               <p className="text-slate-600 text-sm font-medium">
                 High-resolution TIF arrays rendered directly in browser via WebGL. Use scroll to zoom, click and drag to pan.
               </p>
            </div>

            {tifViewers.length === 0 ? (
              <div className="bg-white rounded-3xl p-16 text-center text-slate-400 border border-slate-200 shadow-sm">
                <div className="w-24 h-24 bg-slate-50 rounded-full flex items-center justify-center mx-auto mb-4">
                    <span className="text-4xl filter grayscale opacity-50">🗺️</span>
                </div>
                <h3 className="text-lg font-semibold text-slate-700 mb-1">No spatial data</h3>
                <p>No .tif files were generated during this run.</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 xl:grid-cols-2 gap-8">
                {tifViewers.map((viewer, i) => (
                  <div key={i} className="bg-white rounded-3xl shadow-sm border border-slate-200 overflow-hidden hover-lift flex flex-col" style={{ height: "600px" }}>
                    <div className="h-full w-full relative group">
                        {/* Title overlay integrated into viewer inside TifViewer component ideally, 
                            but we'll let TifViewer handle its own header as it currently does. */}
                        <TifViewer
                        tifUrl={viewer.url}
                        type={viewer.type}
                        title={viewer.title}
                        />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Interactive Map Tab */}
        {activeTab === "interactive" && (
          <div className="animate-slide-up">
            {htmlFiles.length === 0 ? (
              <div className="bg-white rounded-3xl p-16 text-center text-slate-400 border border-slate-200 shadow-sm">
                <div className="w-24 h-24 bg-slate-50 rounded-full flex items-center justify-center mx-auto mb-4">
                    <span className="text-4xl filter grayscale opacity-50">🌐</span>
                </div>
                <h3 className="text-lg font-semibold text-slate-700 mb-1">No interactive maps</h3>
                <p>The folium map generation may have failed or was skipped.</p>
              </div>
            ) : (
              <div className="space-y-8">
                {htmlFiles.map((f, i) => (
                  <div key={i} className="bg-white rounded-3xl shadow-sm border border-slate-200 overflow-hidden hover-lift">
                    <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
                      <div className="flex items-center gap-3">
                          <span className="text-xl">📍</span>
                          <span className="font-bold text-slate-800 font-display">{f.name}</span>
                      </div>
                      <a href={api.getFileUrl(jobId, f.name)} target="_blank" rel="noreferrer"
                         className="flex items-center gap-2 text-brand-600 bg-brand-50 hover:bg-brand-100 px-4 py-2 rounded-lg text-sm font-semibold transition-colors">
                        Open Fullscreen 
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" /></svg>
                      </a>
                    </div>
                    <div className="p-2 bg-slate-100">
                        <div className="rounded-2xl overflow-hidden border border-slate-200 bg-white">
                            <iframe
                            src={api.getFileUrl(jobId, f.name)}
                            className="w-full"
                            style={{ height: "700px", border: "none" }}
                            title={f.name}
                            />
                        </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Summary Images Tab */}
        {activeTab === "images" && (
          <div className="animate-slide-up">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            {pngFiles.length === 0 ? (
              <div className="col-span-2 bg-white rounded-3xl p-16 text-center text-slate-400 border border-slate-200 shadow-sm">
                <div className="w-24 h-24 bg-slate-50 rounded-full flex items-center justify-center mx-auto mb-4">
                    <span className="text-4xl filter grayscale opacity-50">🖼️</span>
                </div>
                <h3 className="text-lg font-semibold text-slate-700 mb-1">No synthetics</h3>
                <p>No PNG summary images were found.</p>
              </div>
            ) : (
              pngFiles.map((f, i) => (
                <div key={i} className="bg-white rounded-3xl shadow-sm border border-slate-200 overflow-hidden hover-lift flex flex-col">
                  <div className="px-6 py-4 border-b border-slate-100 flex items-center gap-3">
                    <span className="text-lg">📸</span>
                    <span className="font-bold text-slate-800 font-display">{f.name}</span>
                  </div>
                  <div className="p-4 bg-slate-50 flex-1 flex items-center justify-center">
                      <img
                        src={api.getFileUrl(jobId, f.name)}
                        alt={f.name}
                        className="w-full h-auto object-contain rounded-xl shadow-sm border border-slate-200 bg-white"
                      />
                  </div>
                  <div className="p-4 border-t border-slate-100 bg-white">
                    <a href={api.getFileUrl(jobId, f.name)} download
                       className="w-full flex items-center justify-center gap-2 bg-slate-100 hover:bg-slate-200 text-slate-700 py-2.5 rounded-xl text-sm font-semibold transition-colors">
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" /></svg>
                      Download High-Res
                    </a>
                  </div>
                </div>
              ))
            )}
          </div>
          </div>
        )}

        {/* All Files Tab */}
        {activeTab === "files" && (
          <div className="animate-slide-up">
          <div className="bg-white rounded-3xl shadow-sm border border-slate-200 overflow-hidden">
            <div className="px-6 py-5 border-b border-slate-100 bg-slate-50/50 flex justify-between items-center">
                <h2 className="font-bold text-slate-800 font-display text-lg flex items-center gap-2">
                    <span className="text-2xl">📁</span> Data Vault
                </h2>
                <span className="text-sm font-mono bg-slate-200 text-slate-600 px-3 py-1 rounded-full">{files.length} objects</span>
            </div>
            <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-white border-b border-slate-200">
                    <tr>
                      <th className="text-left px-8 py-4 text-slate-500 font-semibold uppercase tracking-wider text-xs">Filename</th>
                      <th className="text-left px-8 py-4 text-slate-500 font-semibold uppercase tracking-wider text-xs">Format</th>
                      <th className="text-left px-8 py-4 text-slate-500 font-semibold uppercase tracking-wider text-xs">Size</th>
                      <th className="text-right px-8 py-4 text-slate-500 font-semibold uppercase tracking-wider text-xs">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {files.map((f, i) => {
                      const ext = f.name.split(".").pop().toUpperCase();
                      let icon = "📄";
                      if (ext === "TIF") icon = "🗺️";
                      if (ext === "PNG") icon = "🖼️";
                      if (ext === "HTML") icon = "🌐";
                      if (ext === "GPKG" || ext === "SHP") icon = "📦";
                        
                      return (
                      <tr key={i} className="hover:bg-slate-50/80 transition-colors group">
                        <td className="px-8 py-4">
                            <div className="flex items-center gap-3">
                                <span className="text-xl opacity-80 group-hover:opacity-100 transition-opacity">{icon}</span>
                                <span className="font-medium text-slate-700">{f.name}</span>
                            </div>
                        </td>
                        <td className="px-8 py-4">
                            <span className="font-mono text-xs font-semibold bg-slate-100 text-slate-500 px-2.5 py-1 rounded-md border border-slate-200">
                                {ext}
                            </span>
                        </td>
                        <td className="px-8 py-4 text-slate-500 font-mono text-xs">{f.size_mb.toFixed(2)} MB</td>
                        <td className="px-8 py-4 text-right">
                          <a href={api.getFileUrl(jobId, f.name)} download
                             className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-slate-100 text-slate-400 hover:bg-brand-50 hover:text-brand-600 transition-colors">
                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" /></svg>
                          </a>
                        </td>
                      </tr>
                    )})}
                  </tbody>
                </table>
            </div>
          </div>
          </div>
        )}
      </div>
    </div>
  );
}
