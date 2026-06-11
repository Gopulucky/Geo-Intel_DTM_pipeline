# backend/config.py
"""
Centralized configuration for the Geo-Intel Pipeline.
All magic numbers, paths, and settings live here — change once, affects everywhere.
"""
import os
from dataclasses import dataclass, field


@dataclass
class Config:
    # ── Server ────────────────────────────────────────────────────────────
    HOST: str = "0.0.0.0"
    PORT: int = 7860
    MAX_UPLOAD_BYTES: int = 2 * 1024 * 1024 * 1024   # 2 GB
    UPLOAD_CHUNK_SIZE: int = 8 * 1024 * 1024           # 8 MB streaming chunks

    # ── Jobs ──────────────────────────────────────────────────────────────
    JOB_TIMEOUT_SECONDS: int = 60 * 60                 # 1 hour max per pipeline run
    JOB_RETENTION_HOURS: int = 24                      # auto-delete after 24 hours

    # ── Pipeline Defaults ─────────────────────────────────────────────────
    DTM_RESOLUTION: float = 2.0
    FLOW_ACC_THRESHOLD: int = 500
    MAX_GROUND_POINTS: int = 500_000
    DEFAULT_EPSG: int = 32643
    MIN_POINT_COUNT: int = 1_000
    MAX_POINT_COUNT: int = 2_000_000_000

    # ── Paths ─────────────────────────────────────────────────────────────
    OUTPUTS_DIR: str = field(default_factory=lambda: os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "outputs", "jobs")
    ))
    SAMPLE_DATA_DIR: str = field(default_factory=lambda: os.path.abspath(
        os.path.join(os.path.dirname(__file__), "sample_data")
    ))

    def get_output_dir(self, job_id: str) -> str:
        """Canonical path for a job's output directory."""
        return os.path.join(self.OUTPUTS_DIR, job_id)


settings = Config()
