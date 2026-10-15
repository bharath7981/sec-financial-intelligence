"""Dense vector retrieval using Qdrant (with automatic local embedded fallback)."""

from __future__ import annotations

import os
from pathlib import Path
import uuid
from typing import Any, Dict, List, Optional

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class DenseSearchEngine:
    """Qdrant-backed dense vector search.

    Connects to external Qdrant in Docker/production, and automatically
    falls back to disk-persisted local Qdrant when offline.
    """

    _shared_client = None

    def __init__(self):
        self._settings = get_settings()
        self._collection = self._settings.qdrant_collection

    def _get_client(self):
        if DenseSearchEngine._shared_client is None:
            from qdrant_client import QdrantClient

            # Try remote Qdrant first
            try:
                client = QdrantClient(
                    host=self._settings.qdrant_host,
                    port=self._settings.qdrant_port,
                    timeout=3,
                )
                # Test connectivity
                client.get_collections()
                DenseSearchEngine._shared_client = client
                logger.info("Connected to remote Qdrant at %s:%d", self._settings.qdrant_host, self._settings.qdrant_port)
            except Exception as e:
                # Fallback to local storage
                _project_root = Path(__file__).resolve().parents[3]
                data_base = _project_root / "data" if (_project_root / "data").exists() else Path("data").resolve()
                local_dir = data_base / "qdrant_local"
                local_dir.mkdir(parents=True, exist_ok=True)
                logger.info("Remote Qdrant unavailable (%s) — using embedded Qdrant at %s", e, local_dir)
                DenseSearchEngine._shared_client = QdrantClient(path=str(local_dir))

            self._ensure_collection()
        return DenseSearchEngine._shared_client

    def _ensure_collection(self):
        """Create collection if it doesn't exist."""
        from qdrant_client.models import Distance, VectorParams
        client = DenseSearchEngine._shared_client
        try:
            collections = client.get_collections().collections
            names = [c.name for c in collections]
            if self._collection not in names:
                logger.info("Creating Qdrant collection: %s", self._collection)
                client.create_collection(
                    collection_name=self._collection,
                    vectors_config=VectorParams(
                        size=self._settings.embedding_dimensions,
                        distance=Distance.COSINE,
                    ),
                )
        except Exception as e:
            logger.warning("Failed to verify/create Qdrant collection: %s", e)

    def index_chunks(
        self,
        chunk_ids: List[str],
        embeddings: List[List[float]],
        payloads: List[Dict[str, Any]],
    ) -> int:
        """Index chunk embeddings into Qdrant."""
        if not chunk_ids:
            return 0
        from qdrant_client.models import PointStruct
        client = self._get_client()
        points = []
        for cid, emb, payload in zip(chunk_ids, embeddings, payloads):
            # Qdrant accepts valid UUID strings or unsigned integers
            try:
                point_id = str(uuid.UUID(str(cid)))
            except ValueError:
                point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, str(cid)))

            points.append(PointStruct(
                id=point_id,
                vector=emb,
                payload=payload,
            ))

        # Batch upsert
        batch_size = 100
        total = 0
        for i in range(0, len(points), batch_size):
            batch = points[i:i + batch_size]
            client.upsert(collection_name=self._collection, points=batch)
            total += len(batch)

        logger.info("Indexed %d vectors in Qdrant", total)
        return total

    def search(
        self,
        query_vector: List[float],
        top_k: int = 25,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Search for similar vectors.

        Returns list of {id, score, payload}.
        """
        from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchAny
        client = self._get_client()

        qdrant_filter = None
        if filters:
            conditions = []
            for key, value in filters.items():
                if isinstance(value, list) and value:
                    conditions.append(
                        FieldCondition(key=key, match=MatchAny(any=value))
                    )
                elif value is not None:
                    conditions.append(
                        FieldCondition(key=key, match=MatchValue(value=value))
                    )
            if conditions:
                qdrant_filter = Filter(must=conditions)

        try:
            results = client.search(
                collection_name=self._collection,
                query_vector=query_vector,
                limit=top_k,
                query_filter=qdrant_filter,
            )

            return [
                {
                    "id": str(hit.id),
                    "score": hit.score,
                    "payload": hit.payload or {},
                }
                for hit in results
            ]
        except Exception as e:
            logger.error("Qdrant search error: %s", e)
            return []

    def delete_by_filing(self, filing_id: str) -> None:
        """Delete all vectors for a given filing."""
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        client = self._get_client()
        try:
            client.delete(
                collection_name=self._collection,
                points_selector=Filter(
                    must=[FieldCondition(key="filing_id", match=MatchValue(value=filing_id))]
                ),
            )
        except Exception as e:
            logger.warning("Qdrant delete error: %s", e)

    def is_available(self) -> bool:
        """Check if Qdrant is reachable."""
        try:
            self._get_client()
            return True
        except Exception:
            return False
