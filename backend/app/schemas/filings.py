"""Pydantic schemas for filings."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class FilingResponse(BaseModel):
    id: uuid.UUID
    accession_number: str
    form_type: str
    filing_date: date
    period_of_report: Optional[date] = None
    fiscal_year: Optional[int] = None
    fiscal_period: Optional[str] = None
    filing_url: Optional[str] = None
    is_amendment: bool = False
    ingestion_status: str = "pending"
    document_count: int = 0
    chunk_count: int = 0
    fact_count: int = 0

    model_config = {"from_attributes": True}


class FilingListResponse(BaseModel):
    filings: List[FilingResponse]
    total: int


class IngestRequest(BaseModel):
    form_types: List[str] = ["10-K"]
    fiscal_years: Optional[List[int]] = None
    max_filings: int = 10


class IngestJobResponse(BaseModel):
    job_id: uuid.UUID
    ticker: str
    status: str
    message: str
