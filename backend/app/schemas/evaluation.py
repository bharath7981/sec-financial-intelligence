"""Pydantic schemas for evaluation runs."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class EvaluationConfig(BaseModel):
    retrieval_mode: str = "hybrid"  # dense | sparse | hybrid
    use_reranker: bool = True
    dense_top_k: int = 25
    sparse_top_k: int = 25
    rerank_top_k: int = 4


class EvaluationRunRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    config: EvaluationConfig = Field(default_factory=EvaluationConfig)


class EvaluationRunResponse(BaseModel):
    id: uuid.UUID
    name: str
    status: str
    config: Optional[Dict[str, Any]] = None
    total_questions: int = 0
    completed_questions: int = 0
    results_summary: Optional[Dict[str, Any]] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}
