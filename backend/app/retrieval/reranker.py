"""Reranker abstraction — reranks fused candidates using the original query."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class Reranker(ABC):
    """Abstract reranker interface."""

    @abstractmethod
    async def rerank(
        self, query: str, documents: List[Dict[str, Any]], top_k: int = 4
    ) -> List[Dict[str, Any]]:
        ...


class GeminiReranker(Reranker):
    """Use Gemini to score relevance of each document."""

    async def rerank(
        self, query: str, documents: List[Dict[str, Any]], top_k: int = 4
    ) -> List[Dict[str, Any]]:
        settings = get_settings()
        if not settings.has_gemini:
            logger.warning("Gemini not available for reranking, using score-based fallback")
            return _score_fallback(documents, top_k)

        from google import genai
        client = genai.Client(api_key=settings.gemini_api_key)

        # Score each document
        scored = []
        for doc in documents:
            content = doc.get("content_preview", "")[:500]
            prompt = (
                f"Rate the relevance of this passage to the question on a scale of 0-10.\n"
                f"Question: {query}\n"
                f"Passage: {content}\n"
                f"Reply with ONLY a number between 0 and 10."
            )
            try:
                response = client.models.generate_content(
                    model=settings.gemini_chat_model,
                    contents=prompt,
                )
                score_text = response.text.strip()
                score = float(score_text.split()[0])
                score = max(0, min(10, score))
            except Exception as e:
                logger.debug("Reranking score failed for doc: %s", e)
                score = doc.get("rrf_score", 0) * 10

            scored.append({**doc, "rerank_score": score})

        scored.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)
        return scored[:top_k]


class NoopReranker(Reranker):
    """Passthrough reranker — just takes top_k by existing score."""

    async def rerank(
        self, query: str, documents: List[Dict[str, Any]], top_k: int = 4
    ) -> List[Dict[str, Any]]:
        return _score_fallback(documents, top_k)


def _score_fallback(documents: List[Dict[str, Any]], top_k: int) -> List[Dict[str, Any]]:
    """Fallback: sort by rrf_score and take top_k."""
    docs = sorted(
        documents,
        key=lambda x: x.get("rrf_score", x.get("score", 0)),
        reverse=True,
    )
    return docs[:top_k]


def get_reranker() -> Reranker:
    """Factory: return configured reranker."""
    settings = get_settings()
    provider = settings.ai_rerank_provider.lower()
    if provider == "gemini" and settings.has_gemini:
        return GeminiReranker()
    logger.info("Using no-op reranker (reranking disabled or provider unavailable)")
    return NoopReranker()
