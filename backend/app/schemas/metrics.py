"""Pydantic schemas for financial metrics."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MetricValue(BaseModel):
    concept: str
    label: Optional[str] = None
    value: float
    unit: str = "USD"
    fiscal_year: Optional[int] = None
    fiscal_period: Optional[str] = None
    form_type: Optional[str] = None
    period_type: Optional[str] = None
    provenance: str = "xbrl"
    source_ref: Optional[str] = None


class MetricsResponse(BaseModel):
    ticker: str
    fiscal_years: List[int]
    metrics: Dict[str, List[MetricValue]] = Field(default_factory=dict)
    calculated: List[Dict[str, Any]] = Field(default_factory=list)
