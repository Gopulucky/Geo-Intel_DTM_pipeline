# backend/logger.py
"""
Structured logging for the Geo-Intel Pipeline.
Replaces print() with proper log levels visible in HuggingFace Logs tab.
"""
import logging
import sys

if sys.stdout and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr and sys.stderr.encoding.lower() != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8')

_loggers = {}


def get_logger(name: str) -> logging.Logger:
    """Get or create a logger with consistent formatting."""
    if name in _loggers:
        return _loggers[name]

    logger = logging.getLogger(f"geointel.{name}")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-5s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        ))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    _loggers[name] = logger
    return logger
