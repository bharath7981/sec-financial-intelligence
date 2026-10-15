"""Query endpoint — the primary research interface."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.generation.answer_service import answer_question
from app.schemas.query import QueryRequest, QueryResponse

router = APIRouter(prefix="/api", tags=["Query"])


@router.post("/query", response_model=QueryResponse)
async def query_financials(
    request: QueryRequest,
    db: AsyncSession = Depends(get_db),
):
    """Ask a financial research question.

    The system will:
    1. Classify the question type
    2. Retrieve structured financial facts
    3. Calculate metrics deterministically
    4. Retrieve narrative evidence using hybrid search
    5. Generate a grounded answer with citations
    """
    return await answer_question(
        db=db,
        question=request.question,
        ticker=request.ticker,
        fiscal_years=request.fiscal_years,
        form_types=request.form_types,
        top_k=request.top_k,
        retrieval_mode=request.retrieval_mode,
        use_reranker=request.use_reranker,
        include_calculations=request.include_calculations,
        include_narrative=request.include_narrative,
    )
