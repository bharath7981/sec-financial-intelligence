"""SEC Financial Intelligence Engine — Structured logging."""

from __future__ import annotations

import logging
import sys
from typing import Optional

from app.core.config import get_settings


def setup_logging(level: Optional[str] = None) -> None:
    """Configure structured logging for the application."""
    settings = get_settings()
    log_level = level or settings.app_log_level
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    date_fmt = "%Y-%m-%d %H:%M:%S"

    logging.basicConfig(
        level=numeric_level,
        format=fmt,
        datefmt=date_fmt,
        stream=sys.stdout,
        force=True,
    )

    # Reduce noisy third-party loggers
    for name in ("httpx", "httpcore", "urllib3", "asyncio", "sqlalchemy.engine"):
        logging.getLogger(name).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a logger with the given name."""
    return logging.getLogger(name)
