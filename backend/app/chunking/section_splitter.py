"""Split parsed filing content into parent-child hierarchical chunks."""

from __future__ import annotations

import re
import uuid
from datetime import date
from typing import Any, Dict, List, Optional

from app.core.logging import get_logger
from app.ingestion.table_extractor import (
    detect_periods_from_headers,
    extract_table_text,
    is_financial_statement_table,
)

logger = get_logger(__name__)

# Approximate tokens per character ratio
CHARS_PER_TOKEN = 4
CHILD_TARGET_TOKENS = 200  # ~128-256 token range
PARENT_MIN_TOKENS = 256
CHILD_MAX_CHARS = CHILD_TARGET_TOKENS * CHARS_PER_TOKEN * 2  # upper bound


def split_into_chunks(
    parsed: Dict[str, Any],
    company_id: uuid.UUID,
    filing_id: uuid.UUID,
    ticker: str,
    cik: str,
    fiscal_year: Optional[int] = None,
    fiscal_period: Optional[str] = None,
    form_type: Optional[str] = None,
    filing_date: Optional[date] = None,
    accession_number: Optional[str] = None,
    source_url: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Split parsed filing content into parent and child chunks.

    Parent chunks: full sections or tables.
    Child chunks: focused passages for retrieval.
    """
    chunks: List[Dict[str, Any]] = []
    base_meta = {
        "company_id": company_id,
        "filing_id": filing_id,
        "ticker": ticker,
        "cik": cik,
        "fiscal_year": fiscal_year,
        "fiscal_period": fiscal_period,
        "form_type": form_type,
        "filing_date": filing_date,
        "accession_number": accession_number,
        "source_url": source_url,
    }

    # Process sections
    for section in parsed.get("sections", []):
        section_chunks = _chunk_section(section, base_meta)
        chunks.extend(section_chunks)

    # Process standalone tables not already in sections
    for table in parsed.get("tables", []):
        if is_financial_statement_table(table):
            table_chunks = _chunk_table(table, base_meta, section="financial_statements")
            chunks.extend(table_chunks)

    # If no sections/tables were found, chunk the full text
    if not chunks and parsed.get("full_text"):
        full_text = parsed["full_text"]
        parent_id = uuid.uuid4()
        chunks.append(_make_chunk(
            chunk_id=parent_id,
            parent_id=None,
            chunk_type="parent",
            content_type="narrative",
            content=full_text[:50_000],
            section="full_document",
            heading="Full Document",
            **base_meta,
        ))
        children = _split_text_into_children(
            full_text[:50_000], parent_id, "full_document", base_meta,
        )
        chunks.extend(children)

    logger.info("Created %d total chunks (%d parents, %d children)",
                len(chunks),
                sum(1 for c in chunks if c["chunk_type"] == "parent"),
                sum(1 for c in chunks if c["chunk_type"] == "child"))
    return chunks


def _chunk_section(
    section: Dict[str, Any], base_meta: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Create parent and child chunks for a filing section."""
    chunks: List[Dict[str, Any]] = []
    section_id = section.get("id", "unknown")
    heading = section.get("heading", "")
    content = section.get("content", "")

    if not content.strip():
        return chunks

    # Parent chunk
    parent_id = uuid.uuid4()
    parent_content = content[:50_000]  # Safety limit
    chunks.append(_make_chunk(
        chunk_id=parent_id,
        parent_id=None,
        chunk_type="parent",
        content_type="narrative",
        content=parent_content,
        section=section_id,
        heading=heading,
        **base_meta,
    ))

    # Child narrative chunks
    children = _split_text_into_children(content, parent_id, section_id, base_meta)
    chunks.extend(children)

    # Child table chunks within this section
    for table in section.get("tables", []):
        table_chunks = _chunk_table(table, base_meta, section=section_id, parent_id=parent_id)
        chunks.extend(table_chunks)

    return chunks


def _chunk_table(
    table: Dict[str, Any],
    base_meta: Dict[str, Any],
    section: str = "tables",
    parent_id: Optional[uuid.UUID] = None,
) -> List[Dict[str, Any]]:
    """Create chunks for a financial table, preserving headers with rows."""
    chunks: List[Dict[str, Any]] = []
    table_text = extract_table_text(table)
    if not table_text.strip():
        return chunks

    headers = table.get("headers", [])
    periods = detect_periods_from_headers(headers)

    # Create parent for the full table
    if parent_id is None:
        parent_id = uuid.uuid4()
        chunks.append(_make_chunk(
            chunk_id=parent_id,
            parent_id=None,
            chunk_type="parent",
            content_type="table",
            content=table_text,
            content_html=table.get("html", "")[:30_000],
            section=section,
            heading=table.get("caption", "Financial Table"),
            table_headers=headers,
            table_periods=periods,
            **base_meta,
        ))

    # Child chunks: preserve headers + groups of rows
    header_text = " | ".join(h for h in headers if h) if headers else ""
    caption = table.get("caption", "")
    rows = table.get("rows", [])

    if not rows:
        return chunks

    # Group rows to stay under child target size
    row_group: List[str] = []
    group_len = 0
    prefix = f"{caption}\n{header_text}\n" if (caption or header_text) else ""

    for row in rows:
        row_text = " | ".join(str(c) for c in row if c)
        if not row_text.strip():
            continue

        if group_len + len(row_text) > CHILD_MAX_CHARS and row_group:
            # Flush current group
            child_content = prefix + "\n".join(row_group)
            chunks.append(_make_chunk(
                chunk_id=uuid.uuid4(),
                parent_id=parent_id,
                chunk_type="child",
                content_type="table",
                content=child_content,
                section=section,
                heading=caption,
                table_headers=headers,
                table_periods=periods,
                **base_meta,
            ))
            row_group = []
            group_len = 0

        row_group.append(row_text)
        group_len += len(row_text) + 1

    # Final group
    if row_group:
        child_content = prefix + "\n".join(row_group)
        chunks.append(_make_chunk(
            chunk_id=uuid.uuid4(),
            parent_id=parent_id,
            chunk_type="child",
            content_type="table",
            content=child_content,
            section=section,
            heading=caption,
            table_headers=headers,
            table_periods=periods,
            **base_meta,
        ))

    return chunks


def _split_text_into_children(
    text: str,
    parent_id: uuid.UUID,
    section: str,
    base_meta: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Split narrative text into child chunks preserving sentence boundaries."""
    chunks: List[Dict[str, Any]] = []
    # Split by paragraph first
    paragraphs = re.split(r'\n\s*\n', text)

    buffer: List[str] = []
    buffer_len = 0
    target_chars = CHILD_TARGET_TOKENS * CHARS_PER_TOKEN

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if buffer_len + len(para) > target_chars and buffer:
            content = "\n\n".join(buffer)
            chunks.append(_make_chunk(
                chunk_id=uuid.uuid4(),
                parent_id=parent_id,
                chunk_type="child",
                content_type="narrative",
                content=content,
                section=section,
                **base_meta,
            ))
            buffer = []
            buffer_len = 0

        buffer.append(para)
        buffer_len += len(para) + 2

    # Final buffer
    if buffer:
        content = "\n\n".join(buffer)
        chunks.append(_make_chunk(
            chunk_id=uuid.uuid4(),
            parent_id=parent_id,
            chunk_type="child",
            content_type="narrative",
            content=content,
            section=section,
            **base_meta,
        ))

    return chunks


def _make_chunk(
    chunk_id: uuid.UUID,
    parent_id: Optional[uuid.UUID],
    chunk_type: str,
    content_type: str,
    content: str,
    company_id: uuid.UUID,
    filing_id: uuid.UUID,
    ticker: str,
    cik: str,
    section: Optional[str] = None,
    heading: Optional[str] = None,
    content_html: Optional[str] = None,
    table_headers: Optional[List] = None,
    table_periods: Optional[List] = None,
    fiscal_year: Optional[int] = None,
    fiscal_period: Optional[str] = None,
    form_type: Optional[str] = None,
    filing_date: Optional[date] = None,
    accession_number: Optional[str] = None,
    source_url: Optional[str] = None,
    **kwargs,
) -> Dict[str, Any]:
    """Create a chunk data dictionary."""
    token_estimate = len(content) // CHARS_PER_TOKEN
    return {
        "id": chunk_id,
        "company_id": company_id,
        "filing_id": filing_id,
        "parent_id": parent_id,
        "chunk_type": chunk_type,
        "content_type": content_type,
        "content": content,
        "content_html": content_html,
        "token_count": token_estimate,
        "section": section,
        "heading": heading,
        "table_headers": table_headers,
        "table_periods": table_periods,
        "ticker": ticker,
        "cik": cik,
        "fiscal_year": fiscal_year,
        "fiscal_period": fiscal_period,
        "form_type": form_type,
        "filing_date": filing_date,
        "accession_number": accession_number,
        "source_url": source_url,
        "source_ref": f"{section}#{chunk_id}" if section else str(chunk_id),
    }
