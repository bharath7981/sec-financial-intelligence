"""Reciprocal Rank Fusion — combines dense and sparse retrieval rankings."""

from __future__ import annotations

from typing import Any, Dict, List

from app.core.logging import get_logger

logger = get_logger(__name__)

DEFAULT_RRF_K = 60  # Standard RRF constant


def reciprocal_rank_fusion(
    rankings: List[List[Dict[str, Any]]],
    k: int = DEFAULT_RRF_K,
    top_n: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Combine multiple ranked result lists using Reciprocal Rank Fusion.

    RRF score = sum(1 / (k + rank_i)) across all rankings.

    Args:
        rankings: List of ranked result lists. Each result must have 'id'.
        k: RRF constant (default 60).
        top_n: Maximum results to return.

    Returns:
        Fused ranking sorted by RRF score descending.
    """
    scores: Dict[str, float] = {}
    docs: Dict[str, Dict[str, Any]] = {}

    for ranking_idx, ranking in enumerate(rankings):
        for rank, doc in enumerate(ranking):
            doc_id = doc.get("id", "")
            if not doc_id:
                continue

            rrf_score = 1.0 / (k + rank + 1)  # rank is 0-indexed
            scores[doc_id] = scores.get(doc_id, 0.0) + rrf_score

            if doc_id not in docs:
                docs[doc_id] = {**doc}
                docs[doc_id]["original_scores"] = {}
            docs[doc_id]["original_scores"][f"ranking_{ranking_idx}"] = doc.get("score", 0.0)

    # Sort by fused score
    fused = []
    for doc_id in sorted(scores, key=lambda x: scores[x], reverse=True):
        doc = docs[doc_id]
        doc["rrf_score"] = scores[doc_id]
        doc["fused"] = True
        fused.append(doc)

    if top_n:
        fused = fused[:top_n]

    # Deduplicate by content if needed
    seen_content = set()
    deduped = []
    for doc in fused:
        preview = doc.get("content_preview", "")[:100]
        if preview and preview in seen_content:
            continue
        seen_content.add(preview)
        deduped.append(doc)

    logger.info(
        "RRF fused %d rankings -> %d results (deduped from %d)",
        len(rankings), len(deduped), len(fused),
    )
    return deduped


# Required import for Optional type hint
from typing import Optional
