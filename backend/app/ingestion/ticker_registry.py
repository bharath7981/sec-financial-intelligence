"""Resolve company tickers to CIK numbers using SEC's official ticker mapping."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.ingestion.sec_client import EDGAR_BASE, sec_get_json

logger = get_logger(__name__)

# Cache the ticker→CIK map in memory
_ticker_map: Optional[Dict[str, Dict[str, Any]]] = None


async def _load_ticker_map() -> Dict[str, Dict[str, Any]]:
    """Load the SEC company_tickers.json mapping."""
    global _ticker_map
    if _ticker_map is not None:
        return _ticker_map

    url = f"{EDGAR_BASE}/files/company_tickers.json"
    logger.info("Loading SEC ticker registry from %s", url)
    data = await sec_get_json(url)

    _ticker_map = {}
    for _key, entry in data.items():
        ticker = entry.get("ticker", "").upper()
        cik = str(entry.get("cik_str", "")).zfill(10)
        name = entry.get("title", "")
        if ticker:
            _ticker_map[ticker] = {"ticker": ticker, "cik": cik, "name": name}
    logger.info("Loaded %d tickers from SEC registry", len(_ticker_map))
    return _ticker_map


async def resolve_ticker(ticker: str) -> Dict[str, Any]:
    """Resolve a ticker symbol to CIK and company name.

    Returns dict with keys: ticker, cik, name
    Raises NotFoundError if ticker is not found.
    """
    ticker_map = await _load_ticker_map()
    key = ticker.upper().strip()
    if key not in ticker_map:
        raise NotFoundError("Company", ticker)
    return ticker_map[key]


async def search_tickers(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Search for companies by partial ticker or name match."""
    ticker_map = await _load_ticker_map()
    query_upper = query.upper().strip()
    results: List[Dict[str, Any]] = []

    # Exact ticker match first
    if query_upper in ticker_map:
        results.append(ticker_map[query_upper])

    # Partial matches
    for ticker, info in ticker_map.items():
        if len(results) >= limit:
            break
        if info in results:
            continue
        if query_upper in ticker or query_upper in info["name"].upper():
            results.append(info)

    return results[:limit]


def invalidate_cache() -> None:
    """Clear the cached ticker map (useful for testing)."""
    global _ticker_map
    _ticker_map = None
