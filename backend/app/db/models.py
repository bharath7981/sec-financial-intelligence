"""SQLAlchemy ORM models for SEC Financial Intelligence Engine."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import CHAR, JSON, TypeDecorator


class GUID(TypeDecorator):
    """Platform-independent GUID type.

    Uses PostgreSQL's native UUID type, otherwise CHAR(36).
    """

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return value
        if not isinstance(value, uuid.UUID):
            return str(uuid.UUID(str(value)))
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if not isinstance(value, uuid.UUID):
            return uuid.UUID(str(value))
        return value


# Portable JSON and TSVECTOR types
JSON_TYPE = JSON().with_variant(JSONB, "postgresql")
TSVECTOR_TYPE = Text().with_variant(TSVECTOR, "postgresql")


class Base(DeclarativeBase):
    """Declarative base for all models."""
    pass


# ── Company ────────────────────────────────────────────────────────────────

class Company(Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID, primary_key=True, default=uuid.uuid4
    )
    ticker: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    cik: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    sic: Mapped[Optional[str]] = mapped_column(String(10))
    sic_description: Mapped[Optional[str]] = mapped_column(String(500))
    state: Mapped[Optional[str]] = mapped_column(String(10))
    fiscal_year_end: Mapped[Optional[str]] = mapped_column(String(4))
    exchange: Mapped[Optional[str]] = mapped_column(String(50))
    entity_type: Mapped[Optional[str]] = mapped_column(String(50))
    metadata_json: Mapped[Optional[Dict]] = mapped_column(JSON_TYPE, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    filings: Mapped[List["Filing"]] = relationship(back_populates="company", lazy="selectin")
    financial_facts: Mapped[List["FinancialFact"]] = relationship(
        back_populates="company", lazy="noload"
    )


# ── Filing ─────────────────────────────────────────────────────────────────

class Filing(Base):
    __tablename__ = "filings"
    __table_args__ = (
        UniqueConstraint("accession_number", name="uq_filing_accession"),
        Index("ix_filing_company_date", "company_id", "filing_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID, primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("companies.id"), nullable=False
    )
    accession_number: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    form_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # 10-K | 10-Q
    filing_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    period_of_report: Mapped[Optional[date]] = mapped_column(Date)
    fiscal_year: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    fiscal_period: Mapped[Optional[str]] = mapped_column(String(10))  # FY, Q1, Q2, Q3, Q4
    primary_document: Mapped[Optional[str]] = mapped_column(String(200))
    filing_url: Mapped[Optional[str]] = mapped_column(String(500))
    is_amendment: Mapped[bool] = mapped_column(Boolean, default=False)
    amendment_type: Mapped[Optional[str]] = mapped_column(String(20))
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    fact_count: Mapped[int] = mapped_column(Integer, default=0)
    ingestion_status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )  # pending | processing | completed | partial | failed
    ingestion_error: Mapped[Optional[str]] = mapped_column(Text)
    ingestion_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    ingestion_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    metadata_json: Mapped[Optional[Dict]] = mapped_column(JSON_TYPE, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    company: Mapped["Company"] = relationship(back_populates="filings")
    chunks: Mapped[List["DocumentChunk"]] = relationship(
        back_populates="filing", lazy="noload", cascade="all, delete-orphan"
    )
    financial_facts: Mapped[List["FinancialFact"]] = relationship(
        back_populates="filing", lazy="noload"
    )

    @property
    def is_processed(self) -> bool:
        return self.ingestion_status == "completed"

    @property
    def sec_filing_url(self) -> Optional[str]:
        return self.filing_url


# ── Financial Fact ─────────────────────────────────────────────────────────

class FinancialFact(Base):
    __tablename__ = "financial_facts"
    __table_args__ = (
        Index("ix_fact_lookup", "company_id", "concept", "fiscal_year", "fiscal_period"),
        Index("ix_fact_concept_period", "concept", "fiscal_year"),
        Index("ix_fact_dedup", "company_id", "accession_number", "concept", "start_date", "end_date", "instant_date", "dimensions_hash", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID, primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("companies.id"), nullable=False
    )
    filing_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID, ForeignKey("filings.id")
    )
    ticker: Mapped[str] = mapped_column(String(20), nullable=False)
    cik: Mapped[str] = mapped_column(String(20), nullable=False)
    accession_number: Mapped[str] = mapped_column(String(30), nullable=False)
    taxonomy: Mapped[str] = mapped_column(String(50), nullable=False)
    concept: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    label: Mapped[Optional[str]] = mapped_column(String(500))
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    normalized_value: Mapped[float] = mapped_column(Float, nullable=False)
    normalized_unit: Mapped[str] = mapped_column(String(50), nullable=False)
    start_date: Mapped[Optional[date]] = mapped_column(Date)
    end_date: Mapped[Optional[date]] = mapped_column(Date)
    instant_date: Mapped[Optional[date]] = mapped_column(Date)
    period_type: Mapped[str] = mapped_column(
        String(10), nullable=False
    )  # instant | duration
    fiscal_year: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    fiscal_period: Mapped[Optional[str]] = mapped_column(String(10))
    form_type: Mapped[str] = mapped_column(String(20), nullable=False)
    filing_date: Mapped[Optional[date]] = mapped_column(Date)
    is_amendment: Mapped[bool] = mapped_column(Boolean, default=False)
    dimensions: Mapped[Optional[Dict]] = mapped_column(JSON_TYPE, default=dict)
    dimensions_hash: Mapped[str] = mapped_column(String(64), default="none")
    source_url: Mapped[Optional[str]] = mapped_column(String(1000))
    source_ref: Mapped[Optional[str]] = mapped_column(String(200))
    provenance: Mapped[Optional[str]] = mapped_column(
        String(20), default="xbrl"
    )  # xbrl | normalized | calculated
    transformation: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    company: Mapped["Company"] = relationship(back_populates="financial_facts")
    filing: Mapped[Optional["Filing"]] = relationship(back_populates="financial_facts")


# ── Document Chunk ─────────────────────────────────────────────────────────

class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        Index("ix_chunk_parent", "parent_id"),
        Index("ix_chunk_search", "company_id", "filing_id", "section"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID, primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("companies.id"), nullable=False
    )
    filing_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("filings.id"), nullable=False
    )
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(GUID)
    chunk_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # parent | child
    content_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # narrative | table | footnote
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_html: Mapped[Optional[str]] = mapped_column(Text)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    section: Mapped[Optional[str]] = mapped_column(String(200))
    heading: Mapped[Optional[str]] = mapped_column(String(500))
    table_headers: Mapped[Optional[List]] = mapped_column(JSON_TYPE)
    table_periods: Mapped[Optional[List]] = mapped_column(JSON_TYPE)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False)
    cik: Mapped[str] = mapped_column(String(20), nullable=False)
    fiscal_year: Mapped[Optional[int]] = mapped_column(Integer)
    fiscal_period: Mapped[Optional[str]] = mapped_column(String(10))
    form_type: Mapped[Optional[str]] = mapped_column(String(20))
    filing_date: Mapped[Optional[date]] = mapped_column(Date)
    accession_number: Mapped[Optional[str]] = mapped_column(String(30))
    source_url: Mapped[Optional[str]] = mapped_column(String(1000))
    source_ref: Mapped[Optional[str]] = mapped_column(String(200))
    extraction_confidence: Mapped[Optional[float]] = mapped_column(Float)
    search_vector: Mapped[Optional[Any]] = mapped_column(TSVECTOR_TYPE)
    embedding_indexed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    filing: Mapped["Filing"] = relationship(back_populates="chunks")


# ── Ingestion Job ──────────────────────────────────────────────────────────

class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID, primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID, ForeignKey("companies.id")
    )
    ticker: Mapped[str] = mapped_column(String(20), nullable=False)
    form_types: Mapped[Optional[List]] = mapped_column(JSON_TYPE, default=list)
    fiscal_years: Mapped[Optional[List]] = mapped_column(JSON_TYPE, default=list)
    status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )  # pending | running | completed | failed | partial
    total_filings: Mapped[int] = mapped_column(Integer, default=0)
    completed_filings: Mapped[int] = mapped_column(Integer, default=0)
    failed_filings: Mapped[int] = mapped_column(Integer, default=0)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    error: Mapped[Optional[str]] = mapped_column(Text)
    log: Mapped[Optional[List]] = mapped_column(JSON_TYPE, default=list)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ── Evaluation ─────────────────────────────────────────────────────────────

class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID, primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    config: Mapped[Optional[Dict]] = mapped_column(JSON_TYPE, default=dict)
    total_questions: Mapped[int] = mapped_column(Integer, default=0)
    completed_questions: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )  # pending | running | completed | failed
    results_summary: Mapped[Optional[Dict]] = mapped_column(JSON_TYPE)
    results_detail: Mapped[Optional[List]] = mapped_column(JSON_TYPE)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
