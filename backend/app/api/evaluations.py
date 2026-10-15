"""Evaluation endpoints."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db import repositories as repo
from app.db.session import get_db
from app.schemas.evaluation import (
    EvaluationRunRequest,
    EvaluationRunResponse,
)

router = APIRouter(prefix="/api/evaluations", tags=["Evaluations"])


@router.post("/run", response_model=EvaluationRunResponse)
async def run_evaluation(
    request: EvaluationRunRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Start an evaluation run."""
    run = await repo.create_evaluation_run(db, {
        "name": request.name or f"eval-{uuid.uuid4().hex[:8]}",
        "description": request.description,
        "config": request.config.model_dump(),
        "status": "pending",
    })
    await db.commit()

    # Background evaluation execution
    async def _run_in_background(r_id: uuid.UUID, cfg: dict):
        from app.db.session import AsyncSessionLocal
        from app.evaluation.evaluator import run_benchmark_evaluation
        async with AsyncSessionLocal() as bg_db:
            await run_benchmark_evaluation(bg_db, r_id, cfg)

    background_tasks.add_task(_run_in_background, run.id, request.config.model_dump())
    return EvaluationRunResponse.model_validate(run)


@router.get("/{run_id}", response_model=EvaluationRunResponse)
async def get_evaluation(run_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get evaluation run results."""
    run = await repo.get_evaluation_run(db, run_id)
    if not run:
        raise NotFoundError("Evaluation run", str(run_id))
    return EvaluationRunResponse.model_validate(run)


@router.get("/", response_model=list[EvaluationRunResponse])
async def list_evaluations(db: AsyncSession = Depends(get_db)):
    """List all evaluation runs."""
    runs = await repo.list_evaluation_runs(db)
    return [EvaluationRunResponse.model_validate(r) for r in runs]
