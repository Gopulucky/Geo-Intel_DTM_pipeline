// frontend/src/pages/HomePage.jsx
import { useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";

export default function HomePage() {
  const [file, setFile]         = useState(null);
  const [village, setVillage]   = useState("");
  const [epsgCode, setEpsgCode] = useState("");
  const [rainfallScenario, setRainfallScenario] = useState("flood");
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError]       = useState("");
  const fileInputRef            = useRef(null);
  const navigate                = useNavigate();

  const handleDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) {
      setFile(dropped);
      setError("");
    }
  };

  const handleSubmit = async () => {
    if (!file)    { setError("Please upload a file."); return; }
    if (!village) { setError("Please enter a village name."); return; }

    setUploading(true);
    setError("");

    try {
      const res = await api.upload(file, village, epsgCode, null, rainfallScenario);
      navigate(`/processing/${res.job_id}`);
    } catch (err) {
      setError(err.message);
      setUploading(false);
    }
  };

  const handleDemo = async () => {
    setUploading(true);
    setError("");
    try {
      const res = await api.runDemo("DEMO_Village");
      navigate(`/processing/${res.job_id}`);
    } catch (err) {
      setError(err.message);
      setUploading(false);
    }
  };

  return (
    <div className="min-h-screen bg-surface-darker relative overflow-hidden flex flex-col items-center justify-center px-4 py-12 lg:py-20">
      
      {/* Animated Background Elements */}
      <div className="absolute top-0 left-0 w-full h-full overflow-hidden z-0 pointer-events-none">
        <div className="absolute top-[-10%] left-[-10%] w-[60%] h-[60%] lg:w-[40%] lg:h-[40%] rounded-full bg-brand-500/10 blur-[120px] animate-blob"></div>
        <div className="absolute bottom-[-10%] right-[-10%] w-[60%] h-[60%] lg:w-[40%] lg:h-[40%] rounded-full bg-blue-500/10 blur-[120px] animate-blob" style={{ animationDelay: '2s' }}></div>
        <div className="absolute top-[30%] left-[30%] w-[40%] h-[40%] lg:w-[20%] lg:h-[20%] rounded-full bg-purple-500/10 blur-[100px] animate-blob" style={{ animationDelay: '4s' }}></div>
      </div>

      <div className="relative z-10 w-full max-w-2xl flex flex-col items-center">
        {/* Hero */}
        <div className="text-center mb-8 lg:mb-12 animate-float">
          <div className="inline-flex items-center justify-center p-3 lg:p-4 rounded-3xl bg-white/5 backdrop-blur-sm border border-white/10 mb-6 shadow-2xl">
            <div className="text-4xl lg:text-6xl filter drop-shadow-lg">🌍</div>
          </div>
          <h1 className="text-4xl lg:text-6xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-brand-300 via-emerald-200 to-teal-400 font-display mb-4 tracking-tight leading-tight">
            Geo-Intel Platform
          </h1>
          <p className="text-slate-300 text-base lg:text-lg max-w-xl mx-auto font-light leading-relaxed px-4">
            Point Cloud Analytics <span className="text-brand-500 mx-2">•</span> Hydrology <span className="text-brand-500 mx-2">•</span> Drainage Design
          </p>
          <div className="inline-flex mt-6 items-center gap-2 bg-brand-500/10 border border-brand-500/30 text-brand-300 text-[10px] lg:text-xs px-4 py-1.5 rounded-full uppercase tracking-widest font-bold">
            <span className="w-2 h-2 rounded-full bg-brand-400 animate-pulse-slow"></span>
            MoPR × IIT Tirupati NiF
          </div>
        </div>

        {/* Upload Card */}
        <div className="glass-panel-dark rounded-3xl p-6 lg:p-10 w-full transition-all duration-300 relative overflow-hidden group shadow-[0_0_50px_rgba(0,0,0,0.5)]">
          <div className="absolute inset-0 bg-gradient-to-br from-brand-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-700 pointer-events-none z-0"></div>
          
          <div className="relative z-10">
            <h2 className="text-xl lg:text-2xl font-bold text-white font-display mb-6 flex items-center gap-3">
              <div className="bg-brand-500/20 p-2 rounded-xl border border-brand-500/30">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 lg:h-6 lg:w-6 text-brand-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                </svg>
              </div>
              Initialize Mission
            </h2>

            {/* Drop Zone */}
            <div
              onDrop={handleDrop}
              onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onClick={() => fileInputRef.current.click()}
              className={`relative border-2 border-dashed rounded-2xl p-8 lg:p-10 text-center cursor-pointer transition-all duration-300 mb-6 group/drop ${
                dragging 
                  ? "border-brand-400 bg-brand-500/10 scale-[1.02] shadow-[0_0_30px_rgba(20,184,166,0.2)]" 
                  : "border-slate-700 bg-slate-900/50 hover:border-brand-500/50 hover:bg-slate-800/80"
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                className="hidden"
                onChange={(e) => { setFile(e.target.files[0]); setError(""); }}
              />
              {file ? (
                <div className="animate-zoom-in">
                  <div className="text-5xl mb-4 drop-shadow-md">✅</div>
                  <p className="font-bold text-brand-300 text-base lg:text-lg truncate px-4">{file.name}</p>
                  <p className="text-xs text-slate-400 mt-2 font-mono bg-slate-950 inline-block px-3 py-1 rounded-full border border-slate-800">
                    {(file.size / 1024 / 1024).toFixed(1)} MB
                  </p>
                </div>
              ) : (
                <div>
                  <div className="w-16 h-16 lg:w-20 lg:h-20 mx-auto bg-slate-800 rounded-full flex items-center justify-center mb-4 border border-slate-700 shadow-inner group-hover/drop:bg-slate-700 group-hover/drop:scale-110 transition-all duration-300">
                    <span className="text-3xl lg:text-4xl filter drop-shadow opacity-80 group-hover/drop:opacity-100">📂</span>
                  </div>
                  <p className="text-slate-300 font-semibold text-base lg:text-lg">Drag & Drop LiDAR Data</p>
                  <p className="text-slate-500 text-xs lg:text-sm mt-2 font-medium tracking-wide">.las or .laz format supported</p>
                </div>
              )}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 lg:gap-6 mb-6">
              {/* Village Name */}
              <div>
                <label className="block text-[11px] lg:text-xs font-bold text-slate-400 uppercase tracking-wider mb-2 ml-1">Location ID / Village</label>
                <input
                  type="text"
                  value={village}
                  onChange={(e) => setVillage(e.target.value)}
                  placeholder="e.g. Singapur"
                  className="w-full bg-slate-900/80 border border-slate-700 rounded-xl px-4 py-3.5 lg:py-4 text-white placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-brand-500/50 focus:border-brand-500 transition-all font-medium text-sm lg:text-base"
                />
              </div>

              {/* EPSG Code */}
              <div>
                <label className="block text-[11px] lg:text-xs font-bold text-slate-400 uppercase tracking-wider mb-2 ml-1">EPSG Code <span className="text-slate-600 normal-case font-medium tracking-normal">(Optional)</span></label>
                <input
                  type="text"
                  value={epsgCode}
                  onChange={(e) => setEpsgCode(e.target.value)}
                  placeholder="e.g. 32643"
                  className="w-full bg-slate-900/80 border border-slate-700 rounded-xl px-4 py-3.5 lg:py-4 text-white placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-brand-500/50 focus:border-brand-500 transition-all font-medium text-sm lg:text-base"
                />
              </div>

              {/* Analysis Scenario */}
              <div className="md:col-span-2">
                <label className="block text-[11px] lg:text-xs font-bold text-slate-400 uppercase tracking-wider mb-2 ml-1">Analysis Scenario</label>
                <div className="relative">
                  <select
                    value={rainfallScenario}
                    onChange={(e) => setRainfallScenario(e.target.value)}
                    className="w-full appearance-none bg-slate-900/80 border border-slate-700 rounded-xl px-4 py-3.5 lg:py-4 text-white focus:outline-none focus:ring-2 focus:ring-brand-500/50 focus:border-brand-500 transition-all font-medium text-sm lg:text-base cursor-pointer"
                  >
                    <option value="flood">Flood Simulation (Extreme Rainfall / P99)</option>
                    <option value="waterlogging">Waterlogging Simulation (Normal Rainy Day / P50)</option>
                  </select>
                  <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-4 text-slate-400">
                    <svg className="h-4 w-4 fill-current" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20">
                      <path d="M9.293 12.95l.707.707L15.657 8l-1.414-1.414L10 10.828 5.757 6.586 4.343 8z"/>
                    </svg>
                  </div>
                </div>
              </div>
            </div>

            {/* Error */}
            {error && (
              <div className="bg-red-500/10 border border-red-500/20 text-red-400 rounded-xl px-4 py-3 text-sm mb-6 flex items-center gap-3 animate-slide-down">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 shrink-0 text-red-500" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
                <span className="font-medium">{error}</span>
              </div>
            )}

            {/* Submit Button */}
            <button
              onClick={handleSubmit}
              disabled={uploading}
              className="relative w-full bg-gradient-to-r from-brand-600 to-teal-500 hover:from-brand-500 hover:to-teal-400 disabled:from-slate-800 disabled:to-slate-800 disabled:text-slate-500 disabled:border-slate-700 disabled:cursor-not-allowed border border-transparent text-white font-bold py-4 rounded-xl text-base lg:text-lg transition-all duration-300 shadow-lg hover:shadow-brand-500/25 overflow-hidden group/btn"
            >
              {uploading ? (
                <span className="flex items-center justify-center gap-3">
                  <svg className="animate-spin h-5 w-5 text-white/70" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Establishing Uplink...
                </span>
              ) : (
                <span className="flex items-center justify-center gap-2">
                  Launch Analytics Pipeline
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 transform group-hover/btn:translate-x-1.5 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M14 5l7 7m0 0l-7 7m7-7H3" />
                  </svg>
                </span>
              )}
              
              {/* Button Shine Effect */}
              <div className="absolute top-0 -inset-full h-full w-1/2 z-5 block transform -skew-x-12 bg-gradient-to-r from-transparent to-white opacity-20 group-hover/btn:animate-[shine_1s_ease-in-out]"></div>
            </button>
            
            {/* Demo Mode Button */}
            <div className="mt-6 text-center">
                <button 
                    onClick={handleDemo}
                    disabled={uploading}
                    className="text-[13px] lg:text-sm text-slate-500 hover:text-brand-400 font-medium transition-colors flex items-center justify-center gap-2 mx-auto disabled:opacity-50"
                >
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                    Run diagnostics with sample data
                </button>
            </div>
          </div>
        </div>

        {/* What It Outputs */}
        <div className="mt-10 lg:mt-14 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 w-full">
          {[
            { icon: "🏔️", label: "Terrain Models", desc: "High-res DTM/DSM" },
            { icon: "🌍", label: "Analytics", desc: "Point Cloud Processing" },
            { icon: "💧", label: "Drainage", desc: "Hydrological flows" },
            { icon: "🌐", label: "Intelligence", desc: "Interactive mapping" },
          ].map((item, i) => (
            <div key={i} className="glass-panel-dark rounded-2xl p-5 text-center hover-lift border-t border-white/5 transition-all duration-300">
              <div className="text-3xl mb-3 drop-shadow-md opacity-90">{item.icon}</div>
              <p className="text-[13px] lg:text-sm text-white font-bold font-display leading-tight mb-1">{item.label}</p>
              <p className="text-[11px] lg:text-xs text-slate-400 font-medium">{item.desc}</p>
            </div>
          ))}
        </div>
      </div>
      
      {/* Required custom animation for button shine */}
      <style dangerouslySetInnerHTML={{__html: `
        @keyframes shine {
          100% { left: 200%; }
        }
      `}} />
    </div>
  );
}
