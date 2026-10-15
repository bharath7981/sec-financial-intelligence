"""Pydantic schemas for companies."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CompanySearchResult(BaseModel):
    ticker: str
    name: str
    cik: str
    exchange: Optional[str] = None


class CompanyDetail(BaseModel):
    id: uuid.UUID
    ticker: str
    cik: str
    name: str
    sic: Optional[str] = None
    sic_description: Optional[str] = None
    state: Optional[str] = None
    fiscal_year_end: Optional[str] = None
    exchange: Optional[str] = None
    entity_type: Optional[str] = None
    filing_count: int = 0
    available_fiscal_years: List[int] = Field(default_factory=list)
    created_at: datetime

    model_config = {"from_attributes": True}


class CompanySearchResponse(BaseModel):
    results: List[CompanySearchResult]
    total: int
