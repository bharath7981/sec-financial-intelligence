"""Health check endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db

router = APIRouter()


@router.get("/health")
@router.get("/api/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """Health check with dependency status."""
    settings = get_settings()
    checks = {"status": "healthy", "services": {}}

    # Database
    try:
        await db.execute(text("SELECT 1"))
        checks["services"]["database"] = "ok"
    except Exception as e:
        checks["services"]["database"] = f"error: {e}"
        checks["status"] = "degraded"

    # Qdrant
    try:
        from app.retrieval.dense_search import DenseSearchEngine
        engine = DenseSearchEngine()
        if engine.is_available():
            checks["services"]["qdrant"] = "ok"
        else:
            checks["services"]["qdrant"] = "unavailable"
            checks["status"] = "degraded"
    except Exception:
        checks["services"]["qdrant"] = "unavailable"
        checks["status"] = "degraded"

    # AI providers
    checks["services"]["chat_provider"] = (
        f"{settings.ai_chat_provider} (configured)" if settings.has_chat_provider
        else "not configured (limited mode)"
    )
    checks["services"]["embedding_provider"] = (
        f"{settings.ai_embedding_provider} (configured)" if settings.has_embedding_provider
        else "not configured (mock embeddings)"
    )

    checks["limited_mode"] = settings.limited_mode
    checks["environment"] = settings.app_env

    return checks
