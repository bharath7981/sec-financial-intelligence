"""Citation builder — validates and constructs source citations."""

from __future__ import annotations

import re
import uuid
from typing import Any, Dict, List, Optional, Set

from app.core.logging import get_logger
from app.schemas.query import SourceCitation

logger = get_logger(__name__)


def build_citations(
    retrieved_docs: List[Dict[str, Any]],
    parent_docs: List[Dict[str, Any]],
) -> List[SourceCitation]:
    """Build validated source citations from retrieved evidence."""
    citations: List[SourceCitation] = []
    seen = set()

    for doc in retrieved_docs:
        doc_id = doc.get("id", "")
        if doc_id in seen:
            continue
        seen.add(doc_id)

        # Build SEC filing URL
        accession = doc.get("accession_number", "")
        source_url = doc.get("source_url", "")
        if not source_url and accession:
            source_url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=&type=&dateb=&owner=include&count=40&search_text=&action=getcompany"

        citations.append(SourceCitation(
            source_id=f"SRC-{doc_id[:8]}" if len(doc_id) > 8 else f"SRC-{doc_id}",
            chunk_id=doc_id,
            content_preview=doc.get("content_preview", "")[:300],
            section=doc.get("section"),
            form_type=doc.get("form_type"),
            fiscal_year=doc.get("fiscal_year"),
            fiscal_period=doc.get("fiscal_period"),
            filing_date=doc.get("filing_date"),
            accession_number=accession,
            source_url=source_url,
            relevance_score=doc.get("rerank_score") or doc.get("rrf_score") or doc.get("score"),
        ))

    return citations


def validate_citations_in_answer(
    answer: str,
    valid_source_ids: Set[str],
) -> str:
    """Validate [SOURCE: id] citations in the answer against known sources.

    Removes citations that reference non-existent sources.
    """
    pattern = re.compile(r'\[SOURCE:\s*([^\]]+)\]')
    matches = pattern.findall(answer)

    for match in matches:
        src_id = match.strip()
        if src_id not in valid_source_ids:
            logger.warning("Removing invalid citation: [SOURCE: %s]", src_id)
            answer = answer.replace(f"[SOURCE: {match}]", "")

    return answer.strip()
