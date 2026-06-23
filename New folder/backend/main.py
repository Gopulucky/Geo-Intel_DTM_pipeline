# backend/main.py
"""
Geo-Intel DTM Pipeline — FastAPI Backend
Production-grade API with security, health checks, and job management.
"""
import os
import re
import uuid
import asyncio
import tempfile
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from logger import get_logger
from file_manager import job_store, persist_job, load_all_jobs, cleanup_old_jobs
from pipeline_runner import run_full_pipeline

log = get_logger("api")

# ── Constants ─────────────────────────────────────────────────────────────────

SAFE_FILENAME_RE = re.compile(r"^[\w\-. ()]+$")
START_TIME = datetime.now()


def _sanitize_filename(filename: str) -> str:
    """Strip directory components and replace dangerous characters with underscores."""
    name = os.path.basename(filename)
    if not name:
        name = "uploaded_file"
    # Replace anything that isn't a word char, dash, dot, space, or parens with underscore
    name = re.sub(r'[^\w\-. ()]', '_', name)
    return name


# ── Lifecycle Events ──────────────────────────────────────────────────────────

async def _periodic_cleanup():
    """Background task: clean up expired jobs every hour."""
    while True:
        await asyncio.sleep(3600)
        try:
            deleted = cleanup_old_jobs()
            if deleted:
                log.info(f"Periodic cleanup: removed {deleted} expired jobs.")
        except Exception as e:
            log.error(f"Cleanup error: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup — load previous jobs from disk
    load_all_jobs()
    log.info(f"Server started. {len(job_store)} jobs loaded from disk.")

    # Start periodic cleanup task
    cleanup_task = asyncio.create_task(_periodic_cleanup())

    yield

    # Shutdown
    cleanup_task.cancel()
    log.info("Server shutting down.")


# ── App Setup ─────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Geo-Intel DTM Pipeline API",
    description="LiDAR point cloud processing for rural India infrastructure",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # In production: replace * with your Vercel URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health Check ──────────────────────────────────────────────────────────────

@app.get("/health")
def health_check():
    """Health check endpoint — pinged by monitoring tools and HuggingFace."""
    active = len([j for j in job_store.values() if j.get("status") == "running"])
    return {
        "status": "ok",
        "uptime_seconds": int((datetime.now() - START_TIME).total_seconds()),
        "active_jobs": active,
        "total_jobs": len(job_store),
        "version": "2.0.0"
    }


@app.get("/")
def root():
    return {
        "message": "Geo-Intel DTM Pipeline API is running",
        "docs": "/docs",
        "health": "/health",
        "version": "2.0.0"
    }


# ── Upload ────────────────────────────────────────────────────────────────────

@app.post("/upload")
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    village_name: str = Form(...),
    epsg_code: str = Form(None),
    stream_threshold: int = Form(None)
):
    """
    Receives .las/.laz file and village name.
    Starts pipeline in background.
    Returns job_id for status polling.
    """
    safe_name = _sanitize_filename(file.filename)

    job_id = str(uuid.uuid4())[:8]
    village_name = village_name.strip().replace(" ", "_")

    if not re.match(r"^[\w\-]+$", village_name):
        raise HTTPException(
            status_code=400,
            detail="Village name may only contain letters, digits, dashes, underscores."
        )

    output_dir = settings.get_output_dir(job_id)
    os.makedirs(output_dir, exist_ok=True)

    # Streaming write — never loads entire file into RAM
    las_path = os.path.join(output_dir, safe_name)
    total_bytes = 0
    with open(las_path, "wb") as f_out:
        while True:
            chunk = await file.read(settings.UPLOAD_CHUNK_SIZE)
            if not chunk:
                break
            total_bytes += len(chunk)
            f_out.write(chunk)

    log.info(f"Job {job_id}: uploaded {safe_name} ({total_bytes / 1024 / 1024:.1f} MB) for village '{village_name}'")

    # Initialize job
    job_store[job_id] = {
        "status": "queued",
        "stage": 0,
        "stage_name": "Waiting to start...",
        "village": village_name,
        "created_at": datetime.now().isoformat(),
        "file_size_mb": round(total_bytes / (1024 * 1024), 1),
        "percent": 0,
        "outputs": {},
        "errors": [],
        "logs": []
    }
    persist_job(job_id)

    # Enqueue pipeline task
    background_tasks.add_task(
        run_full_pipeline,
        job_id=job_id,
        las_path=las_path,
        village_name=village_name,
        output_dir=output_dir,
        epsg_code=epsg_code,
        stream_threshold=stream_threshold
    )

    return {
        "job_id": job_id,
        "village": village_name,
        "message": "Pipeline started. Poll /status/{job_id} for updates."
    }


# ── Demo Mode ─────────────────────────────────────────────────────────────────

@app.post("/demo")
async def run_demo(background_tasks: BackgroundTasks, village_name: str = "DEMO_Village"):
    """Run the pipeline on a bundled sample .las file (no upload needed)."""
    import glob
    sample_files = glob.glob(os.path.join(settings.SAMPLE_DATA_DIR, "*.la[sz]"))
    if not sample_files:
        raise HTTPException(
            status_code=404,
            detail="No sample data found. Place a .las file in backend/sample_data/ to enable demo mode."
        )

    sample_las = sample_files[0]
    job_id = str(uuid.uuid4())[:8]
    output_dir = settings.get_output_dir(job_id)
    os.makedirs(output_dir, exist_ok=True)

    log.info(f"Demo job {job_id}: using sample file {os.path.basename(sample_las)}")

    job_store[job_id] = {
        "status": "queued",
        "stage": 0,
        "stage_name": "Demo starting...",
        "village": village_name,
        "is_demo": True,
        "created_at": datetime.now().isoformat(),
        "file_size_mb": round(os.path.getsize(sample_las) / (1024 * 1024), 1),
        "percent": 0,
        "outputs": {},
        "errors": [],
        "logs": []
    }
    persist_job(job_id)

    background_tasks.add_task(
        run_full_pipeline,
        job_id=job_id,
        las_path=sample_las,
        village_name=village_name,
        output_dir=output_dir
    )

    return {"job_id": job_id, "demo": True, "village": village_name}


@app.post("/rerun-hydrology/{job_id}")
async def rerun_hydrology(
    job_id: str,
    background_tasks: BackgroundTasks,
    stream_threshold: int = Form(...)
):
    """
    Re-runs the Hydrology and Map stages with a new physics threshold.
    """
    if job_id not in job_store:
        raise HTTPException(status_code=404, detail="Job not found")
        
    from pipeline_runner import re_run_hydrology_stages
    
    background_tasks.add_task(
        re_run_hydrology_stages,
        job_id=job_id,
        stream_threshold=stream_threshold
    )
    
    return {"status": "re_running_hydrology", "job_id": job_id}


# ── Status Polling ────────────────────────────────────────────────────────────

@app.get("/status/{job_id}")
def get_status(job_id: str):
    """Returns current pipeline status. Frontend polls this every 3 seconds."""
    if job_id not in job_store:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job_store[job_id]


@app.get("/files/{job_id}")
def list_files(job_id: str):
    """Returns list of all output files for a completed job."""
    if job_id not in job_store:
        raise HTTPException(status_code=404, detail="Job not found.")

    output_dir = settings.get_output_dir(job_id)
    if not os.path.exists(output_dir):
        return {"files": []}

    files = []
    for fname in os.listdir(output_dir):
        fpath = os.path.join(output_dir, fname)
        skip = (
            fname.lower().endswith(('.las', '.laz')) or 
            fname == "job_meta.json" or
            "WaterloggingHotspots.tif" in fname or
            "Intensity.tif" in fname
        )
        if os.path.isfile(fpath) and not skip:
            files.append({
                "name": fname,
                "size_mb": round(os.path.getsize(fpath) / 1024 / 1024, 2),
                "url": f"/download/{job_id}/{fname}"
            })
    return {"files": files, "job_id": job_id}


# ── GeoJSON endpoint for frontend attribute panel ─────────────────────────────

@app.get("/geojson/{job_id}")
def get_drainage_geojson(job_id: str):
    """Returns the DrainageDesign GeoJSON (WGS-84) for the Leaflet map panel."""
    if job_id not in job_store:
        raise HTTPException(status_code=404, detail="Job not found.")

    output_dir = settings.get_output_dir(job_id)
    if not os.path.exists(output_dir):
        raise HTTPException(status_code=404, detail="No outputs found.")

    # Find the DrainageDesign GeoJSON regardless of village name prefix
    import glob as _glob
    matches = _glob.glob(os.path.join(output_dir, "*_DrainageDesign.geojson"))
    if not matches:
        raise HTTPException(status_code=404, detail="DrainageDesign GeoJSON not yet generated.")

    geojson_path = matches[0]
    return FileResponse(
        path=geojson_path,
        media_type="application/geo+json",
        headers={"Access-Control-Allow-Origin": "*", "Cache-Control": "no-cache"}
    )


# ── Downloads ─────────────────────────────────────────────────────────────────

@app.get("/download/{job_id}/{filename}")
def download_file(job_id: str, filename: str):
    """Serves a specific output file. Path-traversal protected."""
    safe_name = _sanitize_filename(filename)
    output_dir = settings.get_output_dir(job_id)
    file_path = os.path.join(output_dir, safe_name)

    # Double-check resolved path is inside output dir
    if not os.path.abspath(file_path).startswith(os.path.abspath(output_dir)):
        raise HTTPException(status_code=400, detail="Invalid file path.")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found.")

    media_types = {
        '.tif': 'image/tiff', '.tiff': 'image/tiff',
        '.png': 'image/png', '.jpg': 'image/jpeg',
        '.html': 'text/html',
        '.gpkg': 'application/octet-stream',
        '.shp': 'application/octet-stream',
        '.zip': 'application/zip',
        '.json': 'application/json',
    }
    ext = os.path.splitext(safe_name)[1].lower()
    media_type = media_types.get(ext, "application/octet-stream")

    return FileResponse(
        path=file_path,
        filename=safe_name,
        media_type=media_type,
        content_disposition_type="inline",
        headers={"Access-Control-Allow-Origin": "*"}
    )


@app.get("/download-all/{job_id}")
def download_all(job_id: str):
    """Creates and serves a ZIP of all output files."""
    import zipfile

    output_dir = settings.get_output_dir(job_id)
    if not os.path.exists(output_dir):
        raise HTTPException(status_code=404, detail="No output files found.")

    village = job_store.get(job_id, {}).get("village", "outputs")
    zip_path = os.path.join(tempfile.gettempdir(), f"{job_id}_{village}_all_outputs.zip")

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for fname in os.listdir(output_dir):
            fpath = os.path.join(output_dir, fname)
            skip = (
                fname.lower().endswith(('.las', '.laz', '.zip')) or 
                fname == "job_meta.json" or
                "WaterloggingHotspots.tif" in fname or
                "Intensity.tif" in fname
            )
            if os.path.isfile(fpath) and not skip:
                zf.write(fpath, fname)

    return FileResponse(
        path=zip_path,
        filename=f"{village}_geo_intel_outputs.zip",
        media_type="application/zip"
    )


# ── Cleanup ───────────────────────────────────────────────────────────────────

@app.delete("/cleanup/{job_id}")
def cleanup_job(job_id: str):
    """Manually delete output files for a job."""
    import shutil
    output_dir = settings.get_output_dir(job_id)
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir, ignore_errors=True)
    if job_id in job_store:
        del job_store[job_id]
    log.info(f"Manually cleaned up job: {job_id}")
    return {"deleted": job_id}
