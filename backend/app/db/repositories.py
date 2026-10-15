"""Database repository layer — reusable query helpers."""

from __future__ import annotations

import hashlib
import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import and_, delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Company,
    DocumentChunk,
    EvaluationRun,
    Filing,
    FinancialFact,
    IngestionJob,
)


# ── Company ────────────────────────────────────────────────────────────────

async def get_company_by_ticker(db: AsyncSession, ticker: str) -> Optional[Company]:
    result = await db.execute(
        select(Company).where(func.upper(Company.ticker) == ticker.upper())
    )
    return result.scalars().first()


async def get_company_by_cik(db: AsyncSession, cik: str) -> Optional[Company]:
    padded = cik.zfill(10)
    result = await db.execute(select(Company).where(Company.cik == padded))
    return result.scalars().first()


async def upsert_company(db: AsyncSession, data: Dict[str, Any]) -> Company:
    """Insert or update a company by ticker."""
    existing = await get_company_by_ticker(db, data["ticker"])
    if existing:
        for k, v in data.items():
            if k != "id" and hasattr(existing, k):
                setattr(existing, k, v)
        await db.flush()
        return existing
    company = Company(**data)
    db.add(company)
    await db.flush()
    return company


# ── Filing ─────────────────────────────────────────────────────────────────

async def get_filing_by_accession(
    db: AsyncSession, company_id: uuid.UUID, accession: str
) -> Optional[Filing]:
    result = await db.execute(
        select(Filing).where(
            and_(Filing.company_id == company_id, Filing.accession_number == accession)
        )
    )
    return result.scalars().first()


async def upsert_filing(db: AsyncSession, data: Dict[str, Any]) -> Filing:
    existing = await get_filing_by_accession(
        db, data["company_id"], data["accession_number"]
    )
    if existing:
        for k, v in data.items():
            if k not in ("id", "company_id", "accession_number") and hasattr(existing, k):
                setattr(existing, k, v)
        await db.flush()
        return existing
    filing = Filing(**data)
    db.add(filing)
    await db.flush()
    return filing


async def get_filings_for_company(
    db: AsyncSession,
    company_id: uuid.UUID,
    form_type: Optional[str] = None,
    fiscal_year: Optional[int] = None,
    limit: int = 100,
    offset: int = 0,
) -> Sequence[Filing]:
    q = select(Filing).where(Filing.company_id == company_id)
    if form_type:
        q = q.where(Filing.form_type == form_type)
    if fiscal_year:
        q = q.where(Filing.fiscal_year == fiscal_year)
    q = q.order_by(Filing.filing_date.desc()).limit(limit).offset(offset)
    result = await db.execute(q)
    return result.scalars().all()


# ── Financial Fact ─────────────────────────────────────────────────────────

def _dim_hash(dimensions: Optional[Dict]) -> str:
    if not dimensions:
        return "none"
    raw = str(sorted(dimensions.items()))
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


async def upsert_financial_fact(db: AsyncSession, data: Dict[str, Any]) -> FinancialFact:
    data["dimensions_hash"] = _dim_hash(data.get("dimensions"))
    existing = await db.execute(
        select(FinancialFact).where(
            and_(
                FinancialFact.company_id == data["company_id"],
                FinancialFact.accession_number == data.get("accession_number", ""),
                FinancialFact.concept == data["concept"],
                FinancialFact.start_date == data.get("start_date"),
                FinancialFact.end_date == data.get("end_date"),
                FinancialFact.instant_date == data.get("instant_date"),
                FinancialFact.dimensions_hash == data["dimensions_hash"],
            )
        )
    )
    found = existing.scalars().first()
    if found:
        for k, v in data.items():
            if k not in ("id", "company_id") and hasattr(found, k):
                setattr(found, k, v)
        await db.flush()
        return found
    fact = FinancialFact(**data)
    db.add(fact)
    await db.flush()
    return fact


async def get_facts_for_company(
    db: AsyncSession,
    company_id: uuid.UUID,
    concepts: Optional[List[str]] = None,
    fiscal_years: Optional[List[int]] = None,
    fiscal_period: Optional[str] = None,
    form_type: Optional[str] = None,
) -> Sequence[FinancialFact]:
    q = select(FinancialFact).where(FinancialFact.company_id == company_id)
    if concepts:
        q = q.where(FinancialFact.concept.in_(concepts))
    if fiscal_years:
        q = q.where(FinancialFact.fiscal_year.in_(fiscal_years))
    if fiscal_period:
        q = q.where(FinancialFact.fiscal_period == fiscal_period)
    if form_type:
        q = q.where(FinancialFact.form_type == form_type)
    q = q.where(FinancialFact.dimensions_hash == "none")  # exclude dimensional breakdowns by default
    q = q.order_by(FinancialFact.fiscal_year.desc(), FinancialFact.concept)
    result = await db.execute(q)
    return result.scalars().all()


# ── Document Chunk ─────────────────────────────────────────────────────────

async def insert_chunk(db: AsyncSession, data: Dict[str, Any]) -> DocumentChunk:
    chunk = DocumentChunk(**data)
    db.add(chunk)
    await db.flush()
    return chunk


async def get_chunk_by_id(db: AsyncSession, chunk_id: uuid.UUID) -> Optional[DocumentChunk]:
    result = await db.execute(select(DocumentChunk).where(DocumentChunk.id == chunk_id))
    return result.scalars().first()


async def get_chunks_by_ids(
    db: AsyncSession, chunk_ids: List[uuid.UUID]
) -> Sequence[DocumentChunk]:
    result = await db.execute(
        select(DocumentChunk).where(DocumentChunk.id.in_(chunk_ids))
    )
    return result.scalars().all()


async def get_parent_chunks(
    db: AsyncSession, parent_ids: List[uuid.UUID]
) -> Sequence[DocumentChunk]:
    result = await db.execute(
        select(DocumentChunk).where(
            and_(DocumentChunk.id.in_(parent_ids), DocumentChunk.chunk_type == "parent")
        )
    )
    return result.scalars().all()


async def delete_chunks_for_filing(db: AsyncSession, filing_id: uuid.UUID) -> int:
    result = await db.execute(
        delete(DocumentChunk).where(DocumentChunk.filing_id == filing_id)
    )
    return result.rowcount


async def fulltext_search_chunks(
    db: AsyncSession,
    query: str,
    company_id: Optional[uuid.UUID] = None,
    ticker: Optional[str] = None,
    fiscal_years: Optional[List[int]] = None,
    form_type: Optional[str] = None,
    limit: int = 25,
) -> Sequence[DocumentChunk]:
    """PostgreSQL full-text search over document chunks (BM25 substitute)."""
    ts_query = func.plainto_tsquery("english", query)
    q = (
        select(DocumentChunk)
        .where(DocumentChunk.search_vector.op("@@")(ts_query))
        .where(DocumentChunk.chunk_type == "child")
    )
    if company_id:
        q = q.where(DocumentChunk.company_id == company_id)
    if ticker:
        q = q.where(func.upper(DocumentChunk.ticker) == ticker.upper())
    if fiscal_years:
        q = q.where(DocumentChunk.fiscal_year.in_(fiscal_years))
    if form_type:
        q = q.where(DocumentChunk.form_type == form_type)
    q = q.order_by(
        func.ts_rank_cd(DocumentChunk.search_vector, ts_query).desc()
    ).limit(limit)
    result = await db.execute(q)
    return result.scalars().all()


# ── Ingestion Job ──────────────────────────────────────────────────────────

async def create_ingestion_job(db: AsyncSession, data: Dict[str, Any]) -> IngestionJob:
    job = IngestionJob(**data)
    db.add(job)
    await db.flush()
    return job


async def get_ingestion_job(db: AsyncSession, job_id: uuid.UUID) -> Optional[IngestionJob]:
    result = await db.execute(select(IngestionJob).where(IngestionJob.id == job_id))
    return result.scalars().first()


async def update_ingestion_job(
    db: AsyncSession, job_id: uuid.UUID, **kwargs: Any
) -> None:
    await db.execute(
        update(IngestionJob).where(IngestionJob.id == job_id).values(**kwargs)
    )
    await db.flush()


# ── Evaluation ─────────────────────────────────────────────────────────────

async def create_evaluation_run(db: AsyncSession, data: Dict[str, Any]) -> EvaluationRun:
    run = EvaluationRun(**data)
    db.add(run)
    await db.flush()
    return run


async def get_evaluation_run(
    db: AsyncSession, run_id: uuid.UUID
) -> Optional[EvaluationRun]:
    result = await db.execute(select(EvaluationRun).where(EvaluationRun.id == run_id))
    return result.scalars().first()


async def list_evaluation_runs(
    db: AsyncSession, limit: int = 50
) -> Sequence[EvaluationRun]:
    result = await db.execute(
        select(EvaluationRun).order_by(EvaluationRun.created_at.desc()).limit(limit)
    )
    return result.scalars().all()
