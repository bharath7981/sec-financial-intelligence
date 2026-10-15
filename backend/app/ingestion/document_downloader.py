"""Download SEC filing documents."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from app.core.logging import get_logger
from app.ingestion.sec_client import sec_get_text

logger = get_logger(__name__)

DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))
DOWNLOADS_DIR = DATA_DIR / "downloads"


async def download_filing_document(
    cik: str,
    accession_number: str,
    primary_document: str,
    filing_url: Optional[str] = None,
) -> str:
    """Download a filing's primary HTML document.

    Returns the HTML content string.
    Saves a local copy for caching.
    """
    cik_clean = cik.zfill(10)
    accession_clean = accession_number.replace("-", "")

    # Check local cache
    cache_dir = DOWNLOADS_DIR / cik_clean / accession_clean
    cache_path = cache_dir / primary_document
    if cache_path.exists():
        logger.debug("Using cached document: %s", cache_path)
        return cache_path.read_text(encoding="utf-8", errors="replace")

    # Build URL
    if not filing_url:
        filing_url = (
            f"https://www.sec.gov/Archives/edgar/data/"
            f"{cik_clean}/{accession_clean}/{primary_document}"
        )

    logger.info("Downloading filing document: %s", filing_url)
    html = await sec_get_text(filing_url, timeout=60.0)

    # Cache locally
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(html, encoding="utf-8")
    logger.debug("Cached document: %s (%d bytes)", cache_path, len(html))

    return html


async def get_filing_index(cik: str, accession_number: str) -> str:
    """Get the filing index page to discover documents."""
    cik_clean = cik.zfill(10)
    accession_clean = accession_number.replace("-", "")
    url = (
        f"https://www.sec.gov/Archives/edgar/data/"
        f"{cik_clean}/{accession_clean}/index.json"
    )
    from app.ingestion.sec_client import sec_get_json
    return await sec_get_json(url)
