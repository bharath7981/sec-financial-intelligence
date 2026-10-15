"""Database session management with resilient connection handling."""

from __future__ import annotations

import os
from pathlib import Path
from typing import AsyncGenerator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
_settings = get_settings()

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = _PROJECT_ROOT / "data" if (_PROJECT_ROOT / "data").exists() else Path("data").resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)
SQLITE_ASYNC_URL = f"sqlite+aiosqlite:///{DATA_DIR / 'secfi.db'}"
SQLITE_SYNC_URL = f"sqlite:///{DATA_DIR / 'secfi.db'}"


def _create_engines():
    """Create async and sync engines with automatic SQLite fallback if PostgreSQL is offline."""
    db_url = _settings.database_url
    db_url_sync = _settings.database_url_sync

    # If already configured with sqlite, use sqlite directly
    if "sqlite" in db_url:
        a_eng = create_async_engine(db_url, echo=(_settings.app_env == "development"))
        s_eng = create_engine(db_url_sync, echo=False)
        return a_eng, s_eng

    # Test PostgreSQL connection synchronously
    try:
        s_eng_test = create_engine(db_url_sync, pool_pre_ping=True, connect_args={"connect_timeout": 3})
        with s_eng_test.connect() as conn:
            pass
        logger.info("Connected to primary PostgreSQL database at %s", db_url_sync.split("@")[-1])
        a_eng = create_async_engine(
            db_url,
            echo=(_settings.app_env == "development"),
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
        )
        s_eng = create_engine(db_url_sync, echo=False, pool_pre_ping=True)
        return a_eng, s_eng
    except Exception as e:
        logger.warning(
            "Primary database (%s) unavailable: %s. Using local SQLite at %s",
            db_url, e, SQLITE_ASYNC_URL,
        )
        a_eng = create_async_engine(SQLITE_ASYNC_URL, echo=(_settings.app_env == "development"))
        s_eng = create_engine(SQLITE_SYNC_URL, echo=False)
        return a_eng, s_eng


async_engine, sync_engine = _create_engines()

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

SyncSessionLocal = sessionmaker(bind=sync_engine)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that provides an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Initialize all database tables."""
    from app.db.models import Base
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialized successfully.")
