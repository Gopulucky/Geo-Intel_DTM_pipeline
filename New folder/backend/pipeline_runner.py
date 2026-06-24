# backend/pipeline_runner.py
"""
Pipeline orchestrator — runs all 4 stages with:
- Input validation (Feature 3)
- Real-time log streaming to frontend (Feature 1)
- Progress percentage tracking (Feature 4)
- Job timeout protection (Upgrade 3)
- DTM guard gate (stages 2-4 skip if DTM missing)
"""
import sys
import os
import traceback
import concurrent.futures
from datetime import datetime

# Add parent directory to path (pipeline files live in repo root)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from file_manager import job_store, persist_job
from config import settings
from logger import get_logger

log = get_logger("pipeline")


# ── Helpers ───────────────────────────────────────────────────────────────────

def pipeline_log(job_id: str, message: str):
    """Log to both stdout and the job's live log stream (visible in browser)."""
    log.info(f"[{job_id}] {message}")
    if job_id in job_store:
        job_store[job_id]["logs"].append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "msg": message
        })
        # Keep max 200 log entries to prevent memory bloat
        if len(job_store[job_id]["logs"]) > 200:
            job_store[job_id]["logs"] = job_store[job_id]["logs"][-200:]


def update_status(job_id, stage, stage_name, status="running", percent=None):
    """Updates job progress — frontend reads this via /status endpoint."""
    if job_id in job_store:
        job_store[job_id]["stage"] = stage
        job_store[job_id]["stage_name"] = stage_name
        job_store[job_id]["status"] = status
        job_store[job_id]["percent"] = percent or int((stage / 4) * 100)
        persist_job(job_id)
    pipeline_log(job_id, f"Stage {stage}/4: {stage_name}")


def _record_outputs(job_id, output_dir, file_map):
    """Only record output files that actually exist on disk."""
    for key, filename in file_map.items():
        full_path = os.path.join(output_dir, filename)
        if os.path.exists(full_path):
            job_store[job_id]["outputs"][key] = full_path
            pipeline_log(job_id, f"  ✓ Output: {filename}")
        else:
            pipeline_log(job_id, f"  ✗ Not generated: {filename}")


# ── Input Validation ──────────────────────────────────────────────────────────

def validate_las_file(las_path: str) -> tuple:
    """Quick sanity check before running the full pipeline."""
    try:
        import laspy
        with laspy.open(las_path) as f:
            header = f.header
            point_count = header.point_count

        if point_count == 0:
            return False, "The uploaded file has 0 points. Please check your file."
        if point_count < settings.MIN_POINT_COUNT:
            return False, f"Only {point_count:,} points found. Need at least {settings.MIN_POINT_COUNT:,} for processing."
        if point_count > settings.MAX_POINT_COUNT:
            return False, f"File has {point_count:,} points — too large (max {settings.MAX_POINT_COUNT:,})."

        return True, f"Valid LAS file: {point_count:,} points"
    except Exception as e:
        return False, f"Cannot read file as LAS/LAZ: {str(e)}"


# ── Core Pipeline ─────────────────────────────────────────────────────────────

def _run_pipeline_stages(job_id: str, las_path: str, village_name: str, output_dir: str, epsg_code: str = None, stream_threshold: int = None, rainfall_scenario: str = "flood"):
    """Internal: runs all 4 pipeline stages sequentially."""

    dtm_path = os.path.join(output_dir, f"{village_name}_DTM.tif")
    dtm_generated = False

    # ── Validation ─────────────────────────────────────────────────────────
    pipeline_log(job_id, "Validating uploaded file...")
    valid, msg = validate_las_file(las_path)
    pipeline_log(job_id, msg)
    if not valid:
        job_store[job_id]["errors"].append(f"Validation failed: {msg}")
        update_status(job_id, 0, "Validation failed", status="failed", percent=0)
        return

    # ── Stage 1: DTM Processing ────────────────────────────────────────────
    try:
        update_status(job_id, 1, "Processing LiDAR point cloud → DTM & DSM...", percent=5)
        if epsg_code:
            os.environ["EPSG"] = str(epsg_code)
        else:
            os.environ["EPSG"] = str(settings.DEFAULT_EPSG)

        from GEO_INTEL_pipeline import run_dtm_pipeline
        run_dtm_pipeline(las_path, village_name, output_dir)

        _record_outputs(job_id, output_dir, {
            "dtm":         f"{village_name}_DTM.tif",
            "dsm":         f"{village_name}_DSM.tif",
            "chm":         f"{village_name}_CHM.tif",
            "ground_las":  f"{village_name}_GroundPoints.las",
            "summary_png": f"{village_name}_Summary.png",
        })

        dtm_generated = os.path.exists(dtm_path)
        if dtm_generated:
            pipeline_log(job_id, "✅ Stage 1 complete — DTM generated.")
        else:
            job_store[job_id]["errors"].append("Stage 1 completed but DTM file was not generated.")
            pipeline_log(job_id, "⚠️ Stage 1 ran but DTM file not found on disk.")

    except Exception as e:
        job_store[job_id]["errors"].append(f"Stage 1 (DTM) failed: {str(e)}")
        pipeline_log(job_id, f"❌ Stage 1 error: {str(e)}")
        log.error(traceback.format_exc())

    # ── Guard: Stages 2-4 require the DTM ──────────────────────────────────
    if not dtm_generated:
        msg = "Stages 2-4 skipped — DTM was not generated in Stage 1."
        job_store[job_id]["errors"].append(msg)
        pipeline_log(job_id, f"⚠️ {msg}")
        update_status(job_id, 4, "Pipeline incomplete — DTM missing.", status="partial", percent=100)
        persist_job(job_id)
        return

    # ── Stage 2: Hydrology ─────────────────────────────────────────────────
    try:
        update_status(job_id, 2, "Running hydrological simulation → drainage design...", percent=30)

        from Hydrology_pipeline import run_hydrology_pipeline
        run_hydrology_pipeline(las_path, village_name, output_dir, stream_threshold, rainfall_scenario=rainfall_scenario)

        _record_outputs(job_id, output_dir, {
            "flow_acc":      f"{village_name}_FlowAccumulation.tif",
            "streams_shp":   f"{village_name}_Streams.shp",
            "twi":           f"{village_name}_TWI.tif",
            "catchments":    f"{village_name}_Catchments.tif",
            "hotspots_gpkg": f"{village_name}_WaterloggingHotspots.gpkg",
            "drainage_gpkg": f"{village_name}_DrainageDesign.gpkg",
            "hotspots_gif":  f"{village_name}_Hydrology_Animation_Hotspots.gif",
            "streams_gif":   f"{village_name}_Hydrology_Animation_Streams.gif",
        })
        pipeline_log(job_id, "✅ Stage 2 complete.")

    except Exception as e:
        job_store[job_id]["errors"].append(f"Stage 2 (Hydrology) failed: {str(e)}")
        pipeline_log(job_id, f"❌ Stage 2 error: {str(e)}")
        log.error(traceback.format_exc())


    # ── Stage 4: Interactive Map ───────────────────────────────────────────
    try:
        update_status(job_id, 3, "Generating interactive maps and summary report...", percent=85)

        from InteractiveMap import run_interactive_map
        run_interactive_map(village_name, output_dir)

        _record_outputs(job_id, output_dir, {
            "html_map":    f"{village_name}_interactive_map.html",
            "summary_png": f"{village_name}_Summary.png",
        })
        pipeline_log(job_id, "✅ Stage 4 complete.")

    except Exception as e:
        job_store[job_id]["errors"].append(f"Stage 4 (Map) failed: {str(e)}")
        pipeline_log(job_id, f"❌ Stage 4 error: {str(e)}")
        log.error(traceback.format_exc())

    # ── Done ───────────────────────────────────────────────────────────────
    final_status = "complete" if not job_store[job_id]["errors"] else "partial"
    update_status(job_id, 4, "Pipeline complete!", status=final_status, percent=100)
    pipeline_log(job_id, f"🏁 Pipeline finished with status: {final_status}")
    persist_job(job_id)


def run_full_pipeline(job_id: str, las_path: str, village_name: str, output_dir: str, epsg_code: str = None, stream_threshold: int = None, rainfall_scenario: str = "flood"):
    """
    Runs the full pipeline with a timeout guard.
    If the pipeline takes longer than JOB_TIMEOUT_SECONDS, it's terminated.
    """
    pipeline_log(job_id, f"Pipeline started for village: {village_name}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_run_pipeline_stages, job_id, las_path, village_name, output_dir, epsg_code, stream_threshold, rainfall_scenario)
        try:
            future.result(timeout=settings.JOB_TIMEOUT_SECONDS)
        except concurrent.futures.TimeoutError:
            job_store[job_id]["status"] = "timeout"
            job_store[job_id]["errors"].append(
                f"Pipeline timed out after {settings.JOB_TIMEOUT_SECONDS // 60} minutes."
            )
            pipeline_log(job_id, f"⏰ TIMEOUT — pipeline exceeded {settings.JOB_TIMEOUT_SECONDS // 60} min limit.")
            persist_job(job_id)
        except Exception as e:
            job_store[job_id]["status"] = "failed"
            job_store[job_id]["errors"].append(f"Unexpected error: {str(e)}")
            pipeline_log(job_id, f"💥 Unexpected error: {str(e)}")
            persist_job(job_id)


def re_run_hydrology_stages(job_id: str, stream_threshold: int = None, rainfall_scenario: str = "flood"):
    """
    Fast Path: Re-runs only Stage 2 (Hydrology) and Stage 4 (Map).
    Skips DTM breaching and Flow Accumulation.
    """
    if job_id not in job_store:
        return

    village_name = job_store[job_id]["village"]
    output_dir = settings.get_output_dir(job_id)

    pipeline_log(job_id, f"⚡ Fast-Path Hydrology Re-run started for: {village_name} with threshold {stream_threshold}")
    job_store[job_id]["errors"] = []

    # ── Stage 2: Hydrology (Fast Path) ─────────────────────────────────────
    try:
        update_status(job_id, 2, "Re-running hydrological extraction...", status="re_running", percent=40)

        from Hydrology_pipeline import run_hydrology_pipeline
        run_hydrology_pipeline(village_name, output_dir, stream_threshold, fast_path=True, rainfall_scenario=rainfall_scenario)

        pipeline_log(job_id, "✅ Stage 2 (Fast Path) complete.")
    except Exception as e:
        job_store[job_id]["errors"].append(f"Stage 2 Re-run failed: {str(e)}")
        pipeline_log(job_id, f"❌ Stage 2 Re-run error: {str(e)}")
        log.error(traceback.format_exc())

    # ── Stage 4: Interactive Map ───────────────────────────────────────────
    try:
        update_status(job_id, 4, "Updating interactive maps...", status="re_running", percent=85)

        from InteractiveMap import run_interactive_map
        run_interactive_map(village_name, output_dir)

        pipeline_log(job_id, "✅ Stage 4 update complete.")
    except Exception as e:
        job_store[job_id]["errors"].append(f"Stage 4 Re-run failed: {str(e)}")
        pipeline_log(job_id, f"❌ Stage 4 Re-run error: {str(e)}")
        log.error(traceback.format_exc())

    # ── Done ───────────────────────────────────────────────────────────────
    final_status = "complete" if not job_store[job_id]["errors"] else "partial"
    update_status(job_id, 4, "Hydrology Update complete!", status=final_status, percent=100)
    pipeline_log(job_id, f"🏁 Hydrology Re-run finished with status: {final_status}")
    persist_job(job_id)
