"""Orchestrates the full SEC data ingestion pipeline."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import IngestionError, NotFoundError
from app.core.logging import get_logger
from app.db import repositories as repo
from app.ingestion.document_downloader import download_filing_document
from app.ingestion.filing_discovery import (
    discover_filings,
    extract_company_info,
    fetch_submissions,
)
from app.ingestion.filing_parser import parse_filing_html
from app.ingestion.table_extractor import extract_table_text, is_financial_statement_table
from app.ingestion.ticker_registry import resolve_ticker
from app.ingestion.xbrl_normalizer import fetch_company_facts, normalize_facts
from app.chunking.section_splitter import split_into_chunks

logger = get_logger(__name__)


async def run_ingestion(
    db: AsyncSession,
    ticker: str,
    form_types: List[str] = None,
    fiscal_years: Optional[List[int]] = None,
    max_filings: int = 10,
    job_id: Optional[uuid.UUID] = None,
) -> Dict[str, Any]:
    """Full ingestion pipeline for a company.

    Steps:
    1. Resolve ticker -> CIK
    2. Fetch submissions metadata
    3. Upsert company record
    4. Discover filings
    5. Fetch XBRL company facts
    6. For each filing: download, parse, chunk, index
    7. Track progress and errors
    """
    if form_types is None:
        form_types = ["10-K"]

    result = {
        "ticker": ticker,
        "filings_processed": 0,
        "filings_failed": 0,
        "facts_ingested": 0,
        "chunks_created": 0,
        "errors": [],
    }

    try:
        # Step 1: Resolve ticker
        ticker_info = await resolve_ticker(ticker)
        cik = ticker_info["cik"]
        logger.info("Resolved %s -> CIK %s (%s)", ticker, cik, ticker_info["name"])

        # Step 2: Fetch submissions
        submissions = await fetch_submissions(cik)
        company_info = extract_company_info(submissions)

        # Step 3: Upsert company
        company = await repo.upsert_company(db, {
            "ticker": ticker.upper(),
            "cik": cik,
            "name": company_info["name"],
            "sic": company_info.get("sic"),
            "sic_description": company_info.get("sic_description"),
            "state": company_info.get("state"),
            "fiscal_year_end": company_info.get("fiscal_year_end"),
            "exchange": company_info.get("exchange"),
            "entity_type": company_info.get("entity_type"),
        })
        await db.commit()
        logger.info("Company upserted: %s (id=%s)", company.name, company.id)

        # Step 4: Discover filings
        filing_metas = discover_filings(
            submissions, form_types=form_types,
            fiscal_years=fiscal_years, max_filings=max_filings,
        )
        logger.info("Found %d filings to ingest", len(filing_metas))

        if job_id:
            await repo.update_ingestion_job(
                db, job_id, total_filings=len(filing_metas), status="running",
                started_at=datetime.utcnow(),
            )
            await db.commit()

        # Step 5: Fetch XBRL facts
        try:
            company_facts_data = await fetch_company_facts(cik)
            facts = normalize_facts(
                company_facts_data,
                company_id=company.id,
                ticker=ticker.upper(),
                cik=cik,
                fiscal_years=fiscal_years,
            )
            for fact_data in facts:
                await repo.upsert_financial_fact(db, fact_data)
            result["facts_ingested"] = len(facts)
            await db.commit()
            logger.info("Ingested %d XBRL facts", len(facts))
        except Exception as e:
            logger.error("Failed to fetch/normalize XBRL facts: %s", e)
            result["errors"].append(f"XBRL facts: {str(e)}")

        # Step 6: Process each filing
        for i, meta in enumerate(filing_metas):
            try:
                filing = await _process_single_filing(
                    db, company, meta, ticker.upper(), cik,
                )
                result["filings_processed"] += 1
                result["chunks_created"] += filing.chunk_count

                if job_id:
                    progress = (i + 1) / len(filing_metas) * 100
                    await repo.update_ingestion_job(
                        db, job_id,
                        completed_filings=result["filings_processed"],
                        failed_filings=result["filings_failed"],
                        progress=progress,
                    )
                    await db.commit()

            except Exception as e:
                logger.error(
                    "Failed to process filing %s: %s",
                    meta.get("accession_number"), e,
                )
                result["filings_failed"] += 1
                result["errors"].append(
                    f"Filing {meta.get('accession_number')}: {str(e)}"
                )

        # Update job status
        if job_id:
            status = "completed" if result["filings_failed"] == 0 else "partial"
            await repo.update_ingestion_job(
                db, job_id, status=status, progress=100.0,
                completed_at=datetime.utcnow(),
            )
            await db.commit()

    except NotFoundError:
        raise
    except Exception as e:
        logger.error("Ingestion failed for %s: %s", ticker, e)
        if job_id:
            await repo.update_ingestion_job(
                db, job_id, status="failed",
                error=str(e), completed_at=datetime.utcnow(),
            )
            await db.commit()
        raise IngestionError(f"Ingestion failed: {e}")

    return result


async def _process_single_filing(
    db: AsyncSession,
    company: Any,
    meta: Dict[str, Any],
    ticker: str,
    cik: str,
) -> Any:
    """Process a single filing: download, parse, chunk, store."""
    accession = meta["accession_number"]
    primary_doc = meta.get("primary_document", "")

    # Upsert filing record
    filing = await repo.upsert_filing(db, {
        "company_id": company.id,
        "accession_number": accession,
        "form_type": meta["form_type"],
        "filing_date": meta["filing_date"],
        "period_of_report": meta.get("period_of_report"),
        "fiscal_year": meta.get("fiscal_year"),
        "fiscal_period": meta.get("fiscal_period"),
        "primary_document": primary_doc,
        "filing_url": meta.get("filing_url"),
        "is_amendment": meta.get("is_amendment", False),
        "amendment_type": meta.get("amendment_type"),
        "ingestion_status": "processing",
        "ingestion_started_at": datetime.utcnow(),
    })
    await db.commit()

    chunk_count = 0

    if primary_doc:
        try:
            # Download document
            html = await download_filing_document(
                cik, accession, primary_doc, meta.get("filing_url"),
            )

            # Parse
            parsed = parse_filing_html(html)

            # Delete existing chunks for re-ingestion safety
            await repo.delete_chunks_for_filing(db, filing.id)

            # Create chunks
            chunks = split_into_chunks(
                parsed,
                company_id=company.id,
                filing_id=filing.id,
                ticker=ticker,
                cik=cik,
                fiscal_year=meta.get("fiscal_year"),
                fiscal_period=meta.get("fiscal_period"),
                form_type=meta["form_type"],
                filing_date=meta.get("filing_date"),
                accession_number=accession,
                source_url=meta.get("filing_url"),
            )

            inserted_chunks = []
            for chunk_data in chunks:
                chk = await repo.insert_chunk(db, chunk_data)
                inserted_chunks.append(chk)
                chunk_count += 1
            await db.commit()

            # Update PostgreSQL full-text search vectors
            from app.retrieval.bm25_search import update_search_vectors
            await update_search_vectors(db, filing.id)

            # Generate embeddings and index in Qdrant
            try:
                from app.retrieval.dense_search import DenseSearchEngine
                from app.retrieval.embeddings import get_embedding_provider
                dense_engine = DenseSearchEngine()
                dense_engine.delete_by_filing(str(filing.id))

                child_chunks = [c for c in inserted_chunks if c.chunk_type == "child"]
                if child_chunks:
                    embedder = get_embedding_provider()
                    texts_to_embed = [c.content for c in child_chunks]
                    embeddings = await embedder.embed_texts(texts_to_embed)

                    chunk_ids = [str(c.id) for c in child_chunks]
                    payloads = [
                        {
                            "filing_id": str(c.filing_id),
                            "company_id": str(c.company_id),
                            "ticker": c.ticker,
                            "fiscal_year": c.fiscal_year,
                            "fiscal_period": c.fiscal_period,
                            "form_type": c.form_type,
                            "section": c.section,
                            "chunk_type": c.chunk_type,
                            "content_type": c.content_type,
                            "content_preview": (c.content or "")[:300],
                            "parent_id": str(c.parent_id) if c.parent_id else None,
                            "accession_number": c.accession_number,
                            "source_url": c.source_url,
                            "filing_date": str(c.filing_date) if c.filing_date else None,
                        }
                        for c in child_chunks
                    ]
                    dense_engine.index_chunks(chunk_ids, embeddings, payloads)
                    logger.info("Indexed %d child chunks in Qdrant for filing %s", len(child_chunks), accession)
            except Exception as emb_err:
                logger.warning("Vector indexing skipped/failed for filing %s: %s", accession, emb_err)

        except Exception as e:
            logger.error("Document processing failed for %s: %s", accession, e)
            filing.ingestion_status = "partial"
            filing.ingestion_error = str(e)

    filing.chunk_count = chunk_count
    filing.ingestion_status = "completed" if chunk_count > 0 else "partial"
    filing.ingestion_completed_at = datetime.utcnow()
    await db.commit()

    logger.info(
        "Filing %s: %d chunks created (status=%s)",
        accession, chunk_count, filing.ingestion_status,
    )
    return filing
