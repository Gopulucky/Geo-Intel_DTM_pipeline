// frontend/src/pages/HomePage.jsx
import { useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";

export default function HomePage() {
  const [file, setFile]         = useState(null);
  const [village, setVillage]   = useState("");
  const [epsgCode, setEpsgCode] = useState("");
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
      const res = await api.upload(file, village, epsgCode);
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
    <div className="min-h-screen bg-surface-darker relative overflow-hidden flex flex-col items-center justify-center px-4 py-12">
      
      {/* Animated Background Elements */}
      <div className="absolute top-0 left-0 w-full h-full overflow-hidden z-0 pointer-events-none">
        <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] rounded-full bg-brand-500/20 blur-[120px] animate-blob"></div>
        <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] rounded-full bg-blue-500/20 blur-[120px] animate-blob" style={{ animationDelay: '2s' }}></div>
        <div className="absolute top-[40%] left-[40%] w-[20%] h-[20%] rounded-full bg-purple-500/20 blur-[100px] animate-blob" style={{ animationDelay: '4s' }}></div>
      </div>

      <div className="relative z-10 w-full max-w-xl flex flex-col items-center">
        {/* Hero */}
        <div className="text-center mb-10 animate-float">
          <div className="inline-block p-4 rounded-3xl bg-white/5 backdrop-blur-sm border border-white/10 mb-6 shadow-2xl">
            <div className="text-6xl filter drop-shadow-lg">🌍</div>
          </div>
          <h1 className="text-5xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-brand-400 via-emerald-300 to-blue-400 font-display mb-4 tracking-tight">
            Geo-Intel AI Pipeline
          </h1>
          <p className="text-slate-300 text-lg max-w-xl mx-auto font-light">
            LULC Classification <span className="text-brand-500 mx-2">•</span> Hydrology <span className="text-brand-500 mx-2">•</span> Drainage Design
          </p>
          <div className="inline-flex mt-6 items-center gap-2 bg-brand-500/10 border border-brand-500/30 text-brand-300 text-xs px-4 py-1.5 rounded-full uppercase tracking-wider font-semibold">
            <span className="w-2 h-2 rounded-full bg-brand-400 animate-pulse-slow"></span>
            MoPR × IIT Tirupati NiF
          </div>
        </div>

        {/* Upload Card */}
        <div className="glass-panel-dark rounded-3xl p-8 w-full transition-all duration-300 relative overflow-hidden group">
          <div className="absolute inset-0 bg-gradient-to-br from-brand-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none z-0"></div>
          
          <div className="relative z-10">
          <h2 className="text-2xl font-bold text-white font-display mb-6 flex items-center gap-2">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-brand-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
            </svg>
            Upload LiDAR Data
          </h2>

          {/* Drop Zone */}
          <div
            onDrop={handleDrop}
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onClick={() => fileInputRef.current.click()}
            className={`relative border-2 border-dashed rounded-2xl p-10 text-center cursor-pointer transition-all duration-300 mb-6 group/drop ${
              dragging 
                ? "border-brand-400 bg-brand-500/10 scale-[1.02]" 
                : "border-slate-600/50 bg-slate-800/30 hover:border-brand-500/50 hover:bg-slate-800/50"
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
                <p className="font-bold text-brand-300 text-lg truncate px-4">{file.name}</p>
                <p className="text-sm text-slate-400 mt-2 font-mono bg-slate-900/50 inline-block px-3 py-1 rounded-full border border-slate-700/50">
                  {(file.size / 1024 / 1024).toFixed(1)} MB
                </p>
              </div>
            ) : (
              <div>
                <div className="w-20 h-20 mx-auto bg-slate-800 rounded-full flex items-center justify-center mb-4 border border-slate-700 shadow-inner group-hover/drop:bg-slate-700 transition-colors duration-300">
                  <span className="text-4xl filter drop-shadow">📂</span>
                </div>
                <p className="text-slate-300 font-medium text-lg">Drag & Drop your file</p>
                <p className="text-slate-500 text-sm mt-2">or click to browse computer</p>
              </div>
            )}
          </div>

          {/* Village Name */}
          <div className="mb-6">
            <label className="block text-sm font-medium text-slate-300 mb-2 ml-1">Project / Village Name</label>
            <input
              type="text"
              value={village}
              onChange={(e) => setVillage(e.target.value)}
              placeholder="e.g. Singapur, Karimnagar"
              className="w-full bg-slate-800/50 border border-slate-600 rounded-xl px-5 py-4 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-brand-500/50 focus:border-brand-500 transition-all font-medium"
            />
          </div>

          {/* EPSG Code */}
          <div className="mb-6">
            <label className="block text-sm font-medium text-slate-300 mb-2 ml-1">EPSG Code (Optional)</label>
            <input
              type="text"
              value={epsgCode}
              onChange={(e) => setEpsgCode(e.target.value)}
              placeholder="e.g. 32643"
              className="w-full bg-slate-800/50 border border-slate-600 rounded-xl px-5 py-4 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-brand-500/50 focus:border-brand-500 transition-all font-medium"
            />
          </div>

          {/* Error */}
          {error && (
            <div className="bg-red-500/10 border border-red-500/20 text-red-400 rounded-xl px-4 py-3 text-sm mb-6 flex items-center gap-2 animate-slide-down">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 shrink-0" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
              </svg>
              {error}
            </div>
          )}

          {/* Submit Button */}
          <button
            onClick={handleSubmit}
            disabled={uploading}
            className="relative w-full bg-gradient-to-r from-brand-600 to-emerald-500 hover:from-brand-500 hover:to-emerald-400 disabled:from-slate-700 disabled:to-slate-600 disabled:text-slate-400 disabled:cursor-not-allowed text-white font-bold py-4 rounded-xl text-lg transition-all duration-300 shadow-lg hover:shadow-brand-500/25 overflow-hidden group/btn"
          >
            {uploading ? (
              <span className="flex items-center justify-center gap-2">
                <svg className="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Uploading...
              </span>
            ) : (
              <span className="flex items-center justify-center gap-2">
                🚀 Initialize Pipeline
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 transform group-hover/btn:translate-x-1 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
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
                  className="text-sm text-slate-400 hover:text-brand-400 font-medium transition-colors flex items-center justify-center gap-2 mx-auto"
              >
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                  Or try it with sample data (Demo Mode)
              </button>
          </div>
          </div>
        </div>

        {/* What It Outputs */}
        <div className="mt-12 grid grid-cols-2 md:grid-cols-4 gap-4 w-full">
          {[
            { icon: "🏔️", label: "DTM / DSM Maps", desc: "High-res terrain" },
            { icon: "🌱", label: "LULC Classification", desc: "AI Land Use" },
            { icon: "💧", label: "Drainage Design", desc: "Flow modeling" },
            { icon: "🌐", label: "Interactive Maps", desc: "Web visualizer" },
          ].map((item, i) => (
            <div key={i} className="glass-panel-dark rounded-2xl p-5 text-center hover-lift border-t border-white/5">
              <div className="text-3xl mb-3 drop-shadow-md">{item.icon}</div>
              <p className="text-sm text-white font-bold font-display leading-tight mb-1">{item.label}</p>
              <p className="text-xs text-slate-400">{item.desc}</p>
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
