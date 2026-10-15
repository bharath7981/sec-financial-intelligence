"""BM25 sparse retrieval via PostgreSQL full-text search (with SQLite keyword fallback)."""

from __future__ import annotations

import re
import uuid
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import DocumentChunk

logger = get_logger(__name__)


class BM25SearchEngine:
    """BM25-style sparse retrieval.

    Uses PostgreSQL tsvector/ts_rank_cd on PostgreSQL databases,
    and a token-based frequency ranker on SQLite/local databases.
    """

    async def search(
        self,
        db: AsyncSession,
        query: str,
        company_id: Optional[uuid.UUID] = None,
        ticker: Optional[str] = None,
        fiscal_years: Optional[List[int]] = None,
        form_type: Optional[str] = None,
        top_k: int = 25,
    ) -> List[Dict[str, Any]]:
        """Search chunks using sparse full-text search."""
        dialect = db.bind.dialect.name if db.bind else "postgresql"

        if dialect == "postgresql":
            return await self._search_postgres(
                db, query, company_id, ticker, fiscal_years, form_type, top_k
            )
        else:
            return await self._search_sqlite(
                db, query, company_id, ticker, fiscal_years, form_type, top_k
            )

    async def _search_postgres(
        self,
        db: AsyncSession,
        query: str,
        company_id: Optional[uuid.UUID],
        ticker: Optional[str],
        fiscal_years: Optional[List[int]],
        form_type: Optional[str],
        top_k: int,
    ) -> List[Dict[str, Any]]:
        ts_query = func.plainto_tsquery("english", query)
        q = (
            select(
                DocumentChunk.id,
                DocumentChunk.content,
                DocumentChunk.section,
                DocumentChunk.parent_id,
                DocumentChunk.ticker,
                DocumentChunk.fiscal_year,
                DocumentChunk.fiscal_period,
                DocumentChunk.form_type,
                DocumentChunk.filing_date,
                DocumentChunk.accession_number,
                DocumentChunk.source_url,
                DocumentChunk.chunk_type,
                DocumentChunk.content_type,
                func.ts_rank_cd(DocumentChunk.search_vector, ts_query).label("rank"),
            )
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

        q = q.order_by(text("rank DESC")).limit(top_k)
        result = await db.execute(q)
        rows = result.all()

        return [
            {
                "id": str(row.id),
                "score": float(row.rank) if row.rank else 0.0,
                "content_preview": (row.content or "")[:300],
                "section": row.section,
                "parent_id": str(row.parent_id) if row.parent_id else None,
                "ticker": row.ticker,
                "fiscal_year": row.fiscal_year,
                "fiscal_period": row.fiscal_period,
                "form_type": row.form_type,
                "filing_date": str(row.filing_date) if row.filing_date else None,
                "accession_number": row.accession_number,
                "source_url": row.source_url,
                "retrieval_method": "bm25",
            }
            for row in rows
        ]

    async def _search_sqlite(
        self,
        db: AsyncSession,
        query: str,
        company_id: Optional[uuid.UUID],
        ticker: Optional[str],
        fiscal_years: Optional[List[int]],
        form_type: Optional[str],
        top_k: int,
    ) -> List[Dict[str, Any]]:
        # Tokenize query words
        tokens = [w.lower() for w in re.findall(r"\w+", query) if len(w) > 2]
        if not tokens:
            return []

        # Find matching chunks
        filters = [DocumentChunk.content.ilike(f"%{tok}%") for tok in tokens]
        q = (
            select(
                DocumentChunk.id,
                DocumentChunk.content,
                DocumentChunk.section,
                DocumentChunk.parent_id,
                DocumentChunk.ticker,
                DocumentChunk.fiscal_year,
                DocumentChunk.fiscal_period,
                DocumentChunk.form_type,
                DocumentChunk.filing_date,
                DocumentChunk.accession_number,
                DocumentChunk.source_url,
                DocumentChunk.chunk_type,
                DocumentChunk.content_type,
            )
            .where(or_(*filters))
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

        result = await db.execute(q)
        rows = result.all()

        # Score by term frequency
        scored = []
        for row in rows:
            text_lower = (row.content or "").lower()
            score = sum(text_lower.count(tok) for tok in tokens)
            scored.append((score, row))

        scored.sort(key=lambda x: x[0], reverse=True)
        top_rows = scored[:top_k]

        return [
            {
                "id": str(row.id),
                "score": float(sc),
                "content_preview": (row.content or "")[:300],
                "section": row.section,
                "parent_id": str(row.parent_id) if row.parent_id else None,
                "ticker": row.ticker,
                "fiscal_year": row.fiscal_year,
                "fiscal_period": row.fiscal_period,
                "form_type": row.form_type,
                "filing_date": str(row.filing_date) if row.filing_date else None,
                "accession_number": row.accession_number,
                "source_url": row.source_url,
                "retrieval_method": "bm25",
            }
            for sc, row in top_rows
        ]


async def update_search_vectors(db: AsyncSession, filing_id: uuid.UUID) -> int:
    """Update tsvector column for all chunks of a filing."""
    dialect = db.bind.dialect.name if db.bind else "postgresql"
    if dialect != "postgresql":
        return 0

    sql = text("""
        UPDATE document_chunks
        SET search_vector = to_tsvector('english', coalesce(content, ''))
        WHERE filing_id = :filing_id
    """)
    result = await db.execute(sql, {"filing_id": str(filing_id)})
    await db.commit()
    count = result.rowcount
    logger.info("Updated search vectors for %d chunks (filing %s)", count, filing_id)
    return count
