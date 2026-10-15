"""Embedding provider abstraction — supports Gemini and OpenAI."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from app.core.config import get_settings
from app.core.exceptions import ProviderUnavailableError
from app.core.logging import get_logger

logger = get_logger(__name__)


class EmbeddingProvider(ABC):
    """Abstract embedding provider interface."""

    @abstractmethod
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts."""
        ...

    @abstractmethod
    def dimensions(self) -> int:
        """Return the embedding dimensions."""
        ...


class GeminiEmbeddingProvider(EmbeddingProvider):
    """Google Gemini embedding provider."""

    def __init__(self):
        settings = get_settings()
        if not settings.has_gemini:
            raise ProviderUnavailableError("gemini")
        self._model = settings.gemini_embedding_model
        self._dims = settings.embedding_dimensions
        self._api_key = settings.gemini_api_key

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        from google import genai
        client = genai.Client(api_key=self._api_key)
        results = []
        # Process in batches of 100
        batch_size = 100
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            response = client.models.embed_content(
                model=self._model,
                contents=batch,
            )
            for emb in response.embeddings:
                results.append(emb.values)
        return results

    def dimensions(self) -> int:
        return self._dims


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI embedding provider."""

    def __init__(self):
        settings = get_settings()
        if not settings.has_openai:
            raise ProviderUnavailableError("openai")
        self._model = settings.openai_embedding_model
        self._dims = settings.embedding_dimensions
        self._api_key = settings.openai_api_key

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        import openai
        client = openai.AsyncOpenAI(api_key=self._api_key)
        results = []
        batch_size = 100
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            response = await client.embeddings.create(
                model=self._model,
                input=batch,
            )
            for item in response.data:
                results.append(item.embedding)
        return results

    def dimensions(self) -> int:
        return self._dims


class MockEmbeddingProvider(EmbeddingProvider):
    """Mock provider for testing — returns zero vectors."""

    def __init__(self, dims: int = 768):
        self._dims = dims

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        return [[0.0] * self._dims for _ in texts]

    def dimensions(self) -> int:
        return self._dims


def get_embedding_provider() -> EmbeddingProvider:
    """Factory: return the configured embedding provider."""
    settings = get_settings()
    provider = settings.ai_embedding_provider.lower()
    if provider == "gemini" and settings.has_gemini:
        return GeminiEmbeddingProvider()
    if provider == "openai" and settings.has_openai:
        return OpenAIEmbeddingProvider()
    logger.warning("No embedding provider configured — using mock (zero vectors)")
    return MockEmbeddingProvider(settings.embedding_dimensions)
