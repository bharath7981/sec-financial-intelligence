"""Source citation retrieval endpoint."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db import repositories as repo
from app.db.session import get_db

router = APIRouter(prefix="/api", tags=["Sources"])


@router.get("/sources/{source_id}")
async def get_source(source_id: str, db: AsyncSession = Depends(get_db)):
    """Get the full content of a source citation."""
    # source_id is "SRC-<uuid_prefix>" — try to find matching chunk
    chunk_id_part = source_id.replace("SRC-", "")

    # Try direct UUID lookup
    try:
        chunk = await repo.get_chunk_by_id(db, uuid.UUID(chunk_id_part))
        if chunk:
            return _chunk_to_source(chunk)
    except (ValueError, TypeError):
        pass

    # Search by prefix match
    from sqlalchemy import select, cast, String
    from app.db.models import DocumentChunk
    result = await db.execute(
        select(DocumentChunk).where(
            cast(DocumentChunk.id, String).like(f"{chunk_id_part}%")
        ).limit(1)
    )
    chunk = result.scalars().first()
    if chunk:
        return _chunk_to_source(chunk)

    raise NotFoundError("Source", source_id)


def _chunk_to_source(chunk) -> dict:
    return {
        "source_id": f"SRC-{str(chunk.id)[:8]}",
        "chunk_id": str(chunk.id),
        "content": chunk.content,
        "content_html": chunk.content_html,
        "content_type": chunk.content_type,
        "section": chunk.section,
        "heading": chunk.heading,
        "ticker": chunk.ticker,
        "fiscal_year": chunk.fiscal_year,
        "fiscal_period": chunk.fiscal_period,
        "form_type": chunk.form_type,
        "filing_date": str(chunk.filing_date) if chunk.filing_date else None,
        "accession_number": chunk.accession_number,
        "source_url": chunk.source_url,
        "token_count": chunk.token_count,
        "parent_id": str(chunk.parent_id) if chunk.parent_id else None,
    }
