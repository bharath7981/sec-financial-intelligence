"""SEC Financial Intelligence Engine — FastAPI Application."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.companies import router as companies_router
from app.api.evaluations import router as evaluations_router
from app.api.filings import router as filings_router
from app.api.health import router as health_router
from app.api.metrics import router as metrics_router
from app.api.query import router as query_router
from app.api.sources import router as sources_router
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.db.session import async_engine

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown lifecycle management."""
    settings = get_settings()
    logger.info("Starting SEC Financial Intelligence Engine [env=%s]", settings.app_env)

    # Auto-initialize database tables in dev/self-hosted environments
    try:
        async with async_engine.begin() as conn:
            from app.db.models import Base
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database schema initialized successfully.")
    except Exception as e:
        logger.warning("Database schema auto-init note: %s", e)

    yield

    logger.info("Shutting down SEC Financial Intelligence Engine...")
    await async_engine.dispose()


def create_app() -> FastAPI:
    """Application factory."""
    settings = get_settings()

    app = FastAPI(
        title="SEC Financial Intelligence Engine",
        description="Production-minded multi-year SEC 10-K/10-Q financial RAG platform with verified calculations and source citations.",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Custom exception handling
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message, "code": exc.__class__.__name__},
        )

    # API Routers
    app.include_router(health_router)
    app.include_router(companies_router)
    app.include_router(filings_router)
    app.include_router(metrics_router)
    app.include_router(query_router)
    app.include_router(sources_router)
    app.include_router(evaluations_router)

    # Direct job lookup alias for convenience
    @app.get("/api/jobs/{job_id}", tags=["Filings"])
    async def get_job_alias(job_id: str, request: Request):
        from app.api.filings import get_job_status
        from app.db.session import AsyncSessionLocal
        import uuid
        async with AsyncSessionLocal() as db:
            parsed_id = uuid.UUID(str(job_id))
            return await get_job_status(parsed_id, db)

    # Mount frontend static files if dist directory exists (e.g. unified Render deployment)
    from pathlib import Path
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse
    from fastapi import HTTPException

    project_root = Path(__file__).resolve().parents[2]
    dist_paths = [
        project_root / "frontend" / "dist",
        Path("frontend/dist").resolve(),
        Path("../frontend/dist").resolve(),
    ]
    frontend_dist = next((p for p in dist_paths if p.exists() and (p / "index.html").exists()), None)

    if frontend_dist:
        logger.info("Mounting frontend SPA from %s", frontend_dist)
        assets_dir = frontend_dist / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def serve_spa(full_path: str):
            if full_path.startswith("api/") or full_path == "api" or full_path == "health":
                raise HTTPException(status_code=404, detail="Not Found")
            target = frontend_dist / full_path
            if target.exists() and target.is_file():
                return FileResponse(str(target))
            return FileResponse(str(frontend_dist / "index.html"))

    return app


app = create_app()
