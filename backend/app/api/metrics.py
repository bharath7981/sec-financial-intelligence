"""Metrics endpoint — structured financial data retrieval."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db import repositories as repo
from app.db.session import get_db
from app.financial.calculator import build_facts_dict, calculate_all_metrics
from app.schemas.metrics import MetricValue, MetricsResponse

router = APIRouter(prefix="/api/companies", tags=["Metrics"])


@router.get("/{ticker}/metrics", response_model=MetricsResponse)
async def get_metrics(
    ticker: str,
    fiscal_years: Optional[str] = Query(
        default=None,
        description="Comma-separated fiscal years, e.g. 2022,2023,2024",
    ),
    concepts: Optional[str] = Query(
        default=None,
        description="Comma-separated metric names",
    ),
    db: AsyncSession = Depends(get_db),
):
    """Get financial metrics for a company by fiscal year."""
    company = await repo.get_company_by_ticker(db, ticker)
    if not company:
        raise NotFoundError("Company", ticker)

    # Parse query params
    fy_list = None
    if fiscal_years:
        fy_list = [int(y.strip()) for y in fiscal_years.split(",") if y.strip().isdigit()]

    concept_list = None
    if concepts:
        concept_list = [c.strip() for c in concepts.split(",") if c.strip()]

    # Fetch facts
    facts = await repo.get_facts_for_company(
        db, company.id,
        concepts=concept_list,
        fiscal_years=fy_list,
    )

    # Group by concept
    metrics_map = {}
    all_fy = set()
    for f in facts:
        metrics_map.setdefault(f.concept, []).append(MetricValue(
            concept=f.concept,
            label=f.label,
            value=f.value,
            unit=f.unit,
            fiscal_year=f.fiscal_year,
            fiscal_period=f.fiscal_period,
            form_type=f.form_type,
            period_type=f.period_type,
            provenance=f.provenance or "xbrl",
            source_ref=f.source_ref,
        ))
        if f.fiscal_year:
            all_fy.add(f.fiscal_year)

    # Calculate derived metrics
    calculated = []
    if fy_list and len(fy_list) >= 1:
        facts_dict = build_facts_dict(facts)
        calc_results = calculate_all_metrics(facts_dict, fy_list or sorted(all_fy))
        calculated = [r.to_dict() for r in calc_results if r.status == "success"]

    return MetricsResponse(
        ticker=ticker.upper(),
        fiscal_years=sorted(all_fy),
        metrics=metrics_map,
        calculated=calculated,
    )
