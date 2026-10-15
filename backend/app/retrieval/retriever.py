"""Unified retriever — orchestrates dense + sparse + fusion + reranking + parent expansion."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db import repositories as repo
from app.retrieval.bm25_search import BM25SearchEngine
from app.retrieval.dense_search import DenseSearchEngine
from app.retrieval.embeddings import get_embedding_provider
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.reranker import get_reranker

logger = get_logger(__name__)


class HybridRetriever:
    """Orchestrates the full hybrid retrieval pipeline:
    1. Dense search (Qdrant)
    2. Sparse search (PG full-text / BM25)
    3. Reciprocal Rank Fusion
    4. Reranking
    5. Parent expansion
    """

    def __init__(self):
        self._settings = get_settings()
        self._dense = DenseSearchEngine()
        self._sparse = BM25SearchEngine()
        self._embedder = get_embedding_provider()
        self._reranker = get_reranker()

    async def retrieve(
        self,
        db: AsyncSession,
        query: str,
        company_id: Optional[uuid.UUID] = None,
        ticker: Optional[str] = None,
        fiscal_years: Optional[List[int]] = None,
        form_type: Optional[str] = None,
        dense_top_k: Optional[int] = None,
        sparse_top_k: Optional[int] = None,
        rerank_top_k: Optional[int] = None,
        mode: str = "hybrid",  # dense | sparse | hybrid
        enable_reranking: bool = True,
    ) -> Dict[str, Any]:
        """Execute hybrid retrieval pipeline.

        Returns:
            {
                "children": [...],    # Reranked child chunks
                "parents": [...],     # Expanded parent chunks
                "metadata": {...},    # Retrieval statistics
            }
        """
        s = self._settings
        dk = dense_top_k or s.dense_top_k
        sk = sparse_top_k or s.sparse_top_k
        rk = rerank_top_k or s.rerank_top_k

        dense_results: List[Dict] = []
        sparse_results: List[Dict] = []
        metadata = {"mode": mode, "dense_count": 0, "sparse_count": 0}

        # Build filters
        filters = {}
        if ticker:
            filters["ticker"] = ticker.upper()
        if fiscal_years:
            filters["fiscal_year"] = fiscal_years[0] if len(fiscal_years) == 1 else fiscal_years

        # 1. Dense retrieval
        if mode in ("dense", "hybrid"):
            try:
                if self._dense.is_available():
                    query_embedding = (await self._embedder.embed_texts([query]))[0]
                    dense_results = self._dense.search(
                        query_vector=query_embedding,
                        top_k=dk,
                        filters=filters if filters else None,
                    )
                    for r in dense_results:
                        r["retrieval_method"] = "dense"
                    metadata["dense_count"] = len(dense_results)
                    logger.info("Dense search returned %d results", len(dense_results))
            except Exception as e:
                logger.warning("Dense search failed: %s", e)

        # 2. Sparse retrieval
        if mode in ("sparse", "hybrid"):
            try:
                sparse_results = await self._sparse.search(
                    db, query,
                    company_id=company_id,
                    ticker=ticker,
                    fiscal_years=fiscal_years,
                    form_type=form_type,
                    top_k=sk,
                )
                metadata["sparse_count"] = len(sparse_results)
                logger.info("Sparse search returned %d results", len(sparse_results))
            except Exception as e:
                logger.warning("Sparse search failed: %s", e)

        # 3. Fusion
        if mode == "hybrid" and dense_results and sparse_results:
            fused = reciprocal_rank_fusion(
                [dense_results, sparse_results], top_n=dk + sk
            )
        elif dense_results:
            fused = dense_results
        elif sparse_results:
            fused = sparse_results
        else:
            return {"children": [], "parents": [], "metadata": metadata}

        metadata["fused_count"] = len(fused)

        # 4. Reranking
        if enable_reranking:
            reranked = await self._reranker.rerank(query, fused, top_k=rk)
        else:
            reranked = fused[:rk]
        metadata["reranked_count"] = len(reranked)

        # 5. Parent expansion
        parent_ids = set()
        for doc in reranked:
            pid = doc.get("parent_id")
            if pid:
                try:
                    parent_ids.add(uuid.UUID(pid))
                except (ValueError, TypeError):
                    pass

        parents = []
        if parent_ids:
            parent_chunks = await repo.get_parent_chunks(db, list(parent_ids))
            parents = [
                {
                    "id": str(p.id),
                    "content": p.content,
                    "content_type": p.content_type,
                    "section": p.section,
                    "heading": p.heading,
                    "ticker": p.ticker,
                    "fiscal_year": p.fiscal_year,
                    "fiscal_period": p.fiscal_period,
                    "form_type": p.form_type,
                    "accession_number": p.accession_number,
                    "source_url": p.source_url,
                }
                for p in parent_chunks
            ]
        metadata["parent_count"] = len(parents)

        return {
            "children": reranked,
            "parents": parents,
            "metadata": metadata,
        }
