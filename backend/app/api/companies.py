"""Company search and detail endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models import Company, Filing
from app.db.session import get_db
from app.db import repositories as repo
from app.ingestion.ticker_registry import search_tickers
from app.schemas.companies import CompanyDetail, CompanySearchResponse, CompanySearchResult

router = APIRouter(prefix="/api/companies", tags=["Companies"])


@router.get("/search", response_model=CompanySearchResponse)
async def search_companies(
    q: str = Query(..., min_length=1, max_length=20, description="Ticker or company name"),
    limit: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Search for companies by ticker or name."""
    # First check local DB
    local = await repo.get_company_by_ticker(db, q.strip())
    local_results = []
    if local:
        local_results.append(CompanySearchResult(
            ticker=local.ticker,
            name=local.name,
            cik=local.cik,
            exchange=local.exchange,
        ))

    # Also search SEC registry
    try:
        sec_results = await search_tickers(q, limit=limit)
        for r in sec_results:
            if not any(lr.ticker == r["ticker"] for lr in local_results):
                local_results.append(CompanySearchResult(
                    ticker=r["ticker"],
                    name=r["name"],
                    cik=r["cik"],
                ))
    except Exception:
        pass  # SEC search is best-effort

    return CompanySearchResponse(
        results=local_results[:limit],
        total=len(local_results),
    )


@router.get("/{ticker}", response_model=CompanyDetail)
async def get_company(ticker: str, db: AsyncSession = Depends(get_db)):
    """Get company details by ticker."""
    company = await repo.get_company_by_ticker(db, ticker)
    if not company:
        raise NotFoundError("Company", ticker)

    # Get filing count and fiscal years
    filings = await repo.get_filings_for_company(db, company.id, limit=500)
    fiscal_years = sorted(set(f.fiscal_year for f in filings if f.fiscal_year))

    return CompanyDetail(
        id=company.id,
        ticker=company.ticker,
        cik=company.cik,
        name=company.name,
        sic=company.sic,
        sic_description=company.sic_description,
        state=company.state,
        fiscal_year_end=company.fiscal_year_end,
        exchange=company.exchange,
        entity_type=company.entity_type,
        filing_count=len(filings),
        available_fiscal_years=fiscal_years,
        created_at=company.created_at,
    )
