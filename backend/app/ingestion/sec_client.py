"""SEC EDGAR HTTP client with throttling, retries, and proper User-Agent."""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import get_settings
from app.core.exceptions import SECClientError
from app.core.logging import get_logger

logger = get_logger(__name__)

# SEC EDGAR base URLs
EDGAR_BASE = "https://www.sec.gov"
EDGAR_DATA = "https://data.sec.gov"
EDGAR_EFTS = "https://efts.sec.gov"

# SEC requires ≥100ms between requests
_last_request_time: float = 0.0
_lock = asyncio.Lock()


async def _throttle() -> None:
    """Enforce SEC request rate limiting."""
    global _last_request_time
    settings = get_settings()
    delay = settings.sec_request_delay_ms / 1000.0
    async with _lock:
        elapsed = time.monotonic() - _last_request_time
        if elapsed < delay:
            await asyncio.sleep(delay - elapsed)
        _last_request_time = time.monotonic()


def _get_headers() -> Dict[str, str]:
    settings = get_settings()
    return {
        "User-Agent": settings.sec_user_agent,
        "Accept-Encoding": "gzip, deflate",
        "Accept": "application/json, text/html, */*",
    }


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.HTTPStatusError)),
    reraise=True,
)
async def sec_get(
    url: str,
    params: Optional[Dict[str, Any]] = None,
    timeout: float = 30.0,
    accept: Optional[str] = None,
) -> httpx.Response:
    """Make a throttled GET request to SEC EDGAR."""
    await _throttle()
    headers = _get_headers()
    if accept:
        headers["Accept"] = accept

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        logger.debug(f"SEC GET {url}")
        response = await client.get(url, headers=headers, params=params)
        if response.status_code == 429:
            logger.warning("SEC rate limited (429), backing off")
            await asyncio.sleep(5)
            raise httpx.HTTPStatusError(
                "Rate limited", request=response.request, response=response
            )
        response.raise_for_status()
        return response


async def sec_get_json(url: str, **kwargs: Any) -> Dict[str, Any]:
    """GET JSON from SEC EDGAR."""
    try:
        resp = await sec_get(url, accept="application/json", **kwargs)
        return resp.json()
    except httpx.HTTPStatusError as e:
        raise SECClientError(
            f"SEC request failed: {e.response.status_code} for {url}",
            detail={"url": url, "status": e.response.status_code},
        )
    except httpx.TimeoutException:
        raise SECClientError(f"SEC request timed out: {url}", detail={"url": url})
    except Exception as e:
        raise SECClientError(f"SEC request error: {e}", detail={"url": url})


async def sec_get_text(url: str, **kwargs: Any) -> str:
    """GET text/HTML from SEC EDGAR."""
    try:
        resp = await sec_get(url, accept="text/html, */*", **kwargs)
        return resp.text
    except httpx.HTTPStatusError as e:
        raise SECClientError(
            f"SEC request failed: {e.response.status_code} for {url}",
            detail={"url": url, "status": e.response.status_code},
        )
    except httpx.TimeoutException:
        raise SECClientError(f"SEC request timed out: {url}", detail={"url": url})
    except Exception as e:
        raise SECClientError(f"SEC request error: {e}", detail={"url": url})
