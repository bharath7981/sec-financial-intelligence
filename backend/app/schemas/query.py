"""Pydantic schemas for query and answer."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=5, max_length=2000)
    ticker: str = Field(..., min_length=1, max_length=10)
    fiscal_years: Optional[List[int]] = None
    form_types: Optional[List[str]] = None
    include_calculations: bool = True
    include_narrative: bool = True
    retrieval_mode: str = Field(default="hybrid", description="dense | sparse | hybrid")
    use_reranker: bool = Field(default=True, description="Enable reranking step")
    top_k: int = Field(default=4, ge=1, le=20)


class SourceCitation(BaseModel):
    source_id: str
    chunk_id: Optional[str] = None
    content_preview: str
    section: Optional[str] = None
    form_type: Optional[str] = None
    fiscal_year: Optional[int] = None
    fiscal_period: Optional[str] = None
    filing_date: Optional[str] = None
    accession_number: Optional[str] = None
    source_url: Optional[str] = None
    relevance_score: Optional[float] = None


class CalculationDetail(BaseModel):
    metric: str
    value: Optional[float] = None
    unit: str = "USD"
    formula: Optional[str] = None
    period: Optional[str] = None
    fiscal_year: Optional[int] = None
    input_facts: List[Dict[str, Any]] = Field(default_factory=list)
    status: str = "success"  # success | missing_data | error
    warnings: List[str] = Field(default_factory=list)
    source_refs: List[str] = Field(default_factory=list)


class ComparisonRow(BaseModel):
    metric: str
    unit: str = ""
    values: Dict[str, Optional[float]] = Field(default_factory=dict)  # period -> value
    change: Optional[float] = None
    change_pct: Optional[float] = None


class QueryResponse(BaseModel):
    question: str
    query_type: str
    answer: str
    calculations: List[CalculationDetail] = Field(default_factory=list)
    comparison_table: List[ComparisonRow] = Field(default_factory=list)
    sources: List[SourceCitation] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    model_used: Optional[str] = None
    processing_time_ms: Optional[float] = None
