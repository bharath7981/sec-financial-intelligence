"""Filing listing and ingestion endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db import repositories as repo
from app.db.session import get_db, AsyncSessionLocal
from app.ingestion.ingestion_service import run_ingestion
from app.schemas.filings import (
    FilingListResponse,
    FilingResponse,
    IngestJobResponse,
    IngestRequest,
)

router = APIRouter(prefix="/api/companies", tags=["Filings"])


@router.get("/{ticker}/filings", response_model=FilingListResponse)
async def list_filings(
    ticker: str,
    form_type: Optional[str] = Query(default=None),
    fiscal_year: Optional[int] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List filings for a company."""
    company = await repo.get_company_by_ticker(db, ticker)
    if not company:
        raise NotFoundError("Company", ticker)

    filings = await repo.get_filings_for_company(
        db, company.id,
        form_type=form_type,
        fiscal_year=fiscal_year,
        limit=limit,
        offset=offset,
    )
    return FilingListResponse(
        filings=[FilingResponse.model_validate(f) for f in filings],
        total=len(filings),
    )


@router.post("/{ticker}/ingest", response_model=IngestJobResponse)
async def ingest_company(
    ticker: str,
    request: IngestRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Start an ingestion job for a company.

    Creates a background job and returns immediately with the job ID.
    """
    # Create job record
    job_id = uuid.uuid4()
    job = await repo.create_ingestion_job(db, {
        "id": job_id,
        "ticker": ticker.upper(),
        "form_types": request.form_types,
        "fiscal_years": request.fiscal_years,
        "status": "pending",
    })
    await db.commit()

    # Run ingestion in background
    background_tasks.add_task(
        _run_ingestion_background,
        ticker=ticker,
        form_types=request.form_types,
        fiscal_years=request.fiscal_years,
        max_filings=request.max_filings,
        job_id=job_id,
    )

    return IngestJobResponse(
        job_id=job_id,
        ticker=ticker.upper(),
        status="pending",
        message=f"Ingestion job created. Check status at /api/jobs/{job_id}",
    )


async def _run_ingestion_background(
    ticker: str,
    form_types: list,
    fiscal_years: Optional[list],
    max_filings: int,
    job_id: uuid.UUID,
):
    """Background task for ingestion."""
    async with AsyncSessionLocal() as db:
        try:
            await run_ingestion(
                db, ticker,
                form_types=form_types,
                fiscal_years=fiscal_years,
                max_filings=max_filings,
                job_id=job_id,
            )
        except Exception as e:
            await repo.update_ingestion_job(
                db, job_id,
                status="failed",
                error=str(e),
                completed_at=datetime.utcnow(),
            )
            await db.commit()


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get the status of an ingestion job."""
    job = await repo.get_ingestion_job(db, job_id)
    if not job:
        raise NotFoundError("Job", str(job_id))
    return {
        "id": job.id,
        "ticker": job.ticker,
        "status": job.status,
        "progress": job.progress,
        "total_filings": job.total_filings,
        "completed_filings": job.completed_filings,
        "failed_filings": job.failed_filings,
        "error": job.error,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "created_at": job.created_at,
    }
