# backend/file_manager.py
"""
Job store with JSON persistence.
Jobs survive server restarts by saving metadata to disk.
"""
import os
import json
from datetime import datetime, timedelta

from config import settings
from logger import get_logger

log = get_logger("storage")

# In-memory job store — populated from disk on startup
job_store = {}


def _meta_path(job_id: str) -> str:
    """Path to a job's metadata JSON file."""
    return os.path.join(settings.get_output_dir(job_id), "job_meta.json")


def persist_job(job_id: str):
    """Save current job state to disk so it survives server restarts."""
    if job_id not in job_store:
        return
    meta = _meta_path(job_id)
    os.makedirs(os.path.dirname(meta), exist_ok=True)
    try:
        with open(meta, "w") as f:
            json.dump(job_store[job_id], f, indent=2, default=str)
    except Exception as e:
        log.warning(f"Failed to persist job {job_id}: {e}")


def load_all_jobs():
    """Load all previously saved jobs from disk. Called once on startup."""
    if not os.path.exists(settings.OUTPUTS_DIR):
        return
    loaded = 0
    for job_id in os.listdir(settings.OUTPUTS_DIR):
        meta = _meta_path(job_id)
        if os.path.exists(meta):
            try:
                with open(meta) as f:
                    job_store[job_id] = json.load(f)
                loaded += 1
            except Exception as e:
                log.warning(f"Failed to load job {job_id}: {e}")
    log.info(f"Loaded {loaded} previous jobs from disk.")


def cleanup_old_jobs():
    """Delete jobs older than JOB_RETENTION_HOURS. Returns count deleted."""
    import shutil
    cutoff = datetime.now() - timedelta(hours=settings.JOB_RETENTION_HOURS)
    deleted = 0
    for job_id in list(job_store.keys()):
        try:
            created = datetime.fromisoformat(job_store[job_id].get("created_at", ""))
            if created < cutoff:
                output_dir = settings.get_output_dir(job_id)
                if os.path.exists(output_dir):
                    shutil.rmtree(output_dir, ignore_errors=True)
                del job_store[job_id]
                deleted += 1
                log.info(f"Cleaned up expired job: {job_id}")
        except Exception:
            pass
    return deleted


def get_job_files(job_id: str) -> list:
    """Returns list of output file names for a job."""
    output_dir = settings.get_output_dir(job_id)
    if not os.path.exists(output_dir):
        return []
    files = []
    for fname in os.listdir(output_dir):
        fpath = os.path.join(output_dir, fname)
        if os.path.isfile(fpath) and fname != "job_meta.json":
            files.append(fname)
    return files
