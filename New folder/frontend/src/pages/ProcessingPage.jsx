// frontend/src/pages/ProcessingPage.jsx
import { useEffect, useState, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { api } from "../api/client";

const STAGES = [
  { id: 1, label: "Point Cloud Analytics", desc: "Generating DTM, DSM, CHM from .las file" },
  { id: 2, label: "Hydrological Modeling", desc: "Computing flow direction, drainage design" },
  { id: 3, label: "LULC AI Classification",desc: "Random Forest ML land use mapping" },
  { id: 4, label: "Map Synthesis",         desc: "Creating interactive maps and summary" },
];

export default function ProcessingPage() {
  const { jobId }     = useParams();
  const navigate      = useNavigate();
  const [job, setJob] = useState(null);
  const logsEndRef    = useRef(null);

  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const data = await api.getStatus(jobId);
        setJob(data);

        if (data.status === "complete" || data.status === "partial" || data.status === "failed" || data.status === "timeout") {
          clearInterval(interval);
          if (data.status === "complete" || data.status === "partial") {
             setTimeout(() => navigate(`/results/${jobId}`), 2500);
          }
        }
      } catch (err) {
        console.error("Status poll error:", err);
      }
    }, 2500);

    return () => clearInterval(interval);
  }, [jobId, navigate]);

  // Auto-scroll logs to bottom
  useEffect(() => {
    if (logsEndRef.current) {
        logsEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [job?.logs]);

  const currentStage = job?.stage || 0;
  const progress     = job?.percent || 0;

  return (
    <div className="min-h-screen bg-surface-darker relative overflow-hidden flex flex-col items-center justify-center px-4 py-8 lg:py-12">
      
      {/* Animated Background Gradients */}
      <div className="absolute top-0 left-0 w-full h-full overflow-hidden z-0 pointer-events-none">
        <div className="absolute top-[20%] right-[-10%] w-[80%] h-[80%] lg:w-[50%] lg:h-[50%] rounded-full bg-brand-500/10 blur-[150px] animate-pulse-slow"></div>
        <div className="absolute bottom-[-20%] left-[-10%] w-[80%] h-[80%] lg:w-[50%] lg:h-[50%] rounded-full bg-teal-500/10 blur-[150px] animate-pulse-slow" style={{ animationDelay: '2s' }}></div>
      </div>

      <div className="relative z-10 w-full max-w-5xl flex flex-col lg:flex-row gap-6 lg:gap-8">
        
        {/* Left Side: Progress & Stages */}
        <div className="flex-1 glass-panel-dark rounded-3xl p-6 lg:p-8 flex flex-col relative overflow-hidden shadow-2xl border-t border-white/10">
            {/* Glossy top edge */}
            <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-brand-400/50 to-transparent"></div>

            <div className="flex items-center gap-4 mb-8">
               <div className="w-12 h-12 lg:w-14 lg:h-14 rounded-2xl bg-brand-500/20 border border-brand-500/30 flex items-center justify-center shadow-[0_0_15px_rgba(20,184,166,0.2)]">
                  <span className={`text-2xl ${job?.status === 'running' ? 'animate-[spin_4s_linear_infinite]' : ''}`}>⚙️</span>
               </div>
               <div>
                  <h1 className="text-2xl lg:text-3xl font-bold text-white font-display tracking-tight">
                    System Processing
                  </h1>
                  <p className="text-slate-400 text-xs lg:text-sm mt-1 flex items-center gap-2">
                    <span className="font-mono bg-slate-800/80 px-2 py-0.5 rounded text-brand-300 border border-slate-700">ID: {jobId}</span>
                    <span className="w-1.5 h-1.5 rounded-full bg-slate-600"></span>
                    <span className="text-slate-300 font-medium">{job?.village || "Initializing..."}</span>
                  </p>
               </div>
            </div>

            {/* Glowing Progress Bar */}
            <div className="mb-8 relative">
              <div className="flex justify-between text-xs lg:text-sm mb-2 font-medium">
                <span className="text-brand-300 animate-pulse">{job?.stage_name || "Waking up compute nodes..."}</span>
                <span className="text-white font-mono bg-brand-500/20 px-2 rounded">{progress}%</span>
              </div>
              <div className="bg-slate-800/80 rounded-full h-3 mb-2 overflow-hidden border border-slate-700/50 p-0.5 shadow-inner">
                <div
                  className="bg-gradient-to-r from-brand-600 via-teal-400 to-brand-300 h-full rounded-full transition-all duration-1000 ease-out relative"
                  style={{ width: `${progress}%` }}
                >
                  <div className="absolute inset-0 bg-white/20 animate-[pulse_2s_ease-in-out_infinite]"></div>
                  <div className="absolute top-0 right-0 bottom-0 w-10 bg-gradient-to-r from-transparent to-white opacity-50"></div>
                </div>
              </div>
            </div>

            {/* Stage List */}
            <div className="space-y-3 lg:space-y-4 flex-1">
              {STAGES.map((stage) => {
                const isDone    = currentStage > stage.id;
                const isCurrent = currentStage === stage.id;

                return (
                  <div key={stage.id} className={`flex items-start gap-4 p-3 lg:p-4 rounded-2xl transition-all duration-500 ${
                    isCurrent ? "bg-brand-500/10 border border-brand-500/30 shadow-[0_0_20px_rgba(20,184,166,0.1)] lg:translate-x-2" :
                    isDone    ? "bg-slate-800/40 border border-slate-700/50 opacity-90" : 
                    "opacity-40 border border-transparent"
                  }`}>
                    <div className={`w-10 h-10 rounded-full flex items-center justify-center shrink-0 ${
                        isCurrent ? "bg-brand-500/20 text-brand-400 shadow-[0_0_10px_rgba(20,184,166,0.3)]" :
                        isDone ? "bg-slate-700 text-white" : "bg-slate-800 text-slate-500"
                    }`}>
                      {isDone ? <svg className="w-5 h-5 text-teal-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" /></svg> : 
                       isCurrent ? <span className="animate-spin text-xl">⏳</span> : 
                       <span className="font-mono text-sm">{stage.id}</span>}
                    </div>
                    <div>
                      <p className={`font-semibold font-display tracking-wide text-sm lg:text-base ${isCurrent ? "text-brand-300" : "text-slate-200"}`}>
                        {stage.label}
                      </p>
                      <p className="text-[11px] lg:text-sm text-slate-400 mt-0.5 leading-snug">{stage.desc}</p>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Errors */}
            {job?.errors?.length > 0 && (
              <div className="mt-6 bg-red-950/40 border border-red-500/20 rounded-2xl p-4 lg:p-5 text-left animate-slide-up">
                <p className="font-bold text-red-400 text-sm mb-2 flex items-center gap-2">
                   <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
                   Issues detected
                </p>
                <div className="space-y-1">
                    {job.errors.map((e, i) => (
                    <p key={i} className="text-xs text-red-300 font-mono bg-red-900/20 p-2 rounded">{e}</p>
                    ))}
                </div>
              </div>
            )}

            {/* Complete / Failed messages */}
            {(job?.status === "complete" || job?.status === "partial") && (
              <div className="mt-6 bg-brand-500/10 border border-brand-500/30 rounded-2xl p-4 lg:p-5 text-center shadow-[0_0_30px_rgba(20,184,166,0.15)] animate-zoom-in">
                <p className="font-bold text-brand-300 flex justify-center items-center gap-2 text-base lg:text-lg">
                    <svg className="w-6 h-6 animate-bounce text-teal-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                    Pipeline Complete!
                </p>
                <p className="text-xs lg:text-sm text-brand-400/70 mt-1">Routing to intelligence dashboard...</p>
              </div>
            )}

            {(job?.status === "failed" || job?.status === "timeout") && (
              <div className="mt-6 bg-red-950/40 border border-red-500/30 rounded-2xl p-5 text-center">
                <p className="font-bold text-red-400 text-lg">Pipeline {job.status}</p>
                <button onClick={() => navigate("/")} className="mt-4 px-6 py-2.5 bg-red-500/20 hover:bg-red-500/30 text-red-300 rounded-xl text-sm font-semibold transition-colors border border-red-500/30">
                    Return to Mission Control
                </button>
              </div>
            )}
        </div>

        {/* Right Side: Live Terminal */}
        <div className="flex-1 lg:max-w-md bg-surface-darker rounded-3xl p-1 flex flex-col h-[400px] lg:h-auto lg:min-h-[600px] border border-slate-800 shadow-2xl relative">
           {/* macOS style terminal header */}
           <div className="bg-slate-900/90 rounded-t-[22px] px-4 py-3 flex items-center justify-between border-b border-slate-800">
               <div className="flex gap-2">
                   <div className="w-3 h-3 rounded-full bg-red-500/80"></div>
                   <div className="w-3 h-3 rounded-full bg-yellow-500/80"></div>
                   <div className="w-3 h-3 rounded-full bg-green-500/80"></div>
               </div>
               <div className="text-slate-500 font-mono text-[10px] lg:text-xs font-semibold tracking-widest uppercase flex items-center gap-2">
                   {job?.status === "running" && <span className="w-2 h-2 rounded-full bg-brand-500 animate-pulse"></span>}
                   sys.stdout
               </div>
               <div className="w-12"></div> {/* Spacer for centering */}
           </div>

           <div className="flex-1 overflow-y-auto font-mono text-[11px] lg:text-[13px] p-4 lg:p-5 space-y-2 custom-scrollbar bg-transparent leading-relaxed tracking-wide">
              {job?.logs && job.logs.length > 0 ? (
                  job.logs.map((log, i) => {
                      const isErr = log.msg.includes("❌") || log.msg.includes("error") || log.msg.includes("failed");
                      const isOk = log.msg.includes("✅") || log.msg.includes("✓");
                      const isWarn = log.msg.includes("⚠️") || log.msg.includes("skipped");
                      
                      return (
                      <div key={i} className="flex gap-3 group">
                          <span className="text-slate-600 shrink-0 select-none group-hover:text-slate-400 transition-colors">[{log.time}]</span>
                          <span className={`break-words ${
                              isErr ? "text-red-400 font-semibold" :
                              isOk ? "text-teal-400" :
                              isWarn ? "text-yellow-400" :
                              "text-slate-300"
                          }`}>{log.msg}</span>
                      </div>
                      )
                  })
              ) : (
                  <div className="flex items-center gap-3 text-brand-500/50 animate-pulse">
                      <span className="text-xl">_</span>
                      <span>Establishing secure connection to compute node...</span>
                  </div>
              )}
              {job?.status === "running" && (
                 <div className="flex items-center gap-2 text-brand-500 mt-2">
                     <span className="animate-pulse font-bold text-lg">_</span>
                 </div>
              )}
              <div ref={logsEndRef} className="h-4" />
           </div>
        </div>

      </div>
    </div>
  );
}
