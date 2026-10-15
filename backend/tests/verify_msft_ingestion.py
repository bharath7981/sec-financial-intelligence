"""End-to-End Real SEC Ingestion and Verification for Microsoft (MSFT)."""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.session import init_db, AsyncSessionLocal
from app.db import repositories as repo
from app.ingestion.ingestion_service import run_ingestion
from app.retrieval.dense_search import DenseSearchEngine
from app.retrieval.bm25_search import BM25SearchEngine
from app.retrieval.embeddings import get_embedding_provider


async def verify_msft():
    print("=" * 70)
    print("PHASE 3: VERIFYING REAL SEC INGESTION FOR MICROSOFT (MSFT)")
    print("=" * 70)

    await init_db()

    async with AsyncSessionLocal() as db:
        print("\n1. Running Ingestion for MSFT (FY2023-FY2024, 10-K & 10-Q)...")
        res1 = await run_ingestion(
            db=db,
            ticker="MSFT",
            form_types=["10-K", "10-Q"],
            fiscal_years=[2023, 2024],
            max_filings=2,
        )
        print("Ingestion Result:", res1)

        # Verify Company Record
        company = await repo.get_company_by_ticker(db, "MSFT")
        assert company is not None, "MSFT company record not found in database!"
        print(f"\n2. Company Persisted: {company.name} | CIK: {company.cik} | SIC: {company.sic} ({company.sic_description})")
        assert company.cik == "0000789019", f"Expected CIK 0000789019, got {company.cik}"

        # Verify Filings Persisted
        filings = await repo.get_filings_for_company(db, company.id)
        print(f"\n3. Filings Persisted ({len(filings)} filings):")
        for f in filings:
            print(f"   - {f.form_type} | Acc: {f.accession_number} | Period: FY{f.fiscal_year} ({f.fiscal_period}) | Date: {f.filing_date} | Chunks: {f.chunk_count} | Status: {f.ingestion_status}")
            assert f.chunk_count > 0, f"Filing {f.accession_number} has 0 chunks!"
            assert f.ingestion_status == "completed", f"Filing status is {f.ingestion_status}"

        # Verify Financial Facts Persisted
        facts = await repo.get_facts_for_company(db, company.id)
        print(f"\n4. Financial Facts Persisted: {len(facts)} facts")
        sample_concepts = ["revenue", "net_income", "operating_income", "gross_profit", "operating_cash_flow", "capital_expenditures"]
        for c in sample_concepts:
            matching = [f for f in facts if f.concept == c]
            if matching:
                latest = matching[0]
                print(f"   - {c.upper()}: FY{latest.fiscal_year} ({latest.fiscal_period}) = ${latest.value:,.0f} {latest.unit} (Form {latest.form_type}, Acc: {latest.accession_number})")

        # Verify Document Chunks (Parent-Child Hierarchy)
        parent_chunks = [c for c in filings[0].chunks if c.chunk_type == "parent"] if hasattr(filings[0], "chunks") and filings[0].chunks else []
        if not parent_chunks:
            # Query directly from DB
            from sqlalchemy import select
            from app.db.models import DocumentChunk
            q_p = await db.execute(select(DocumentChunk).where(DocumentChunk.filing_id == filings[0].id, DocumentChunk.chunk_type == "parent"))
            parent_chunks = q_p.scalars().all()
            q_c = await db.execute(select(DocumentChunk).where(DocumentChunk.filing_id == filings[0].id, DocumentChunk.chunk_type == "child"))
            child_chunks = q_c.scalars().all()
        print(f"\n5. Chunks in Filing {filings[0].accession_number}:")
        print(f"   - Parent Chunks (Sections/Tables): {len(parent_chunks)}")
        print(f"   - Child Chunks (Passages): {len(child_chunks)}")
        assert len(parent_chunks) > 0, "No parent chunks created!"
        assert len(child_chunks) > 0, "No child chunks created!"

        # Check child parent_id linkage
        linked_children = [c for c in child_chunks if c.parent_id is not None]
        print(f"   - Children linked to parent: {len(linked_children)} / {len(child_chunks)} ({len(linked_children)/len(child_chunks)*100:.1f}%)")

        # Verify Sparse (BM25) Search
        bm25 = BM25SearchEngine()
        bm25_hits = await bm25.search(db, query="cloud revenue intelligent cloud", ticker="MSFT", top_k=5)
        print(f"\n6. Sparse Search Test ('cloud revenue intelligent cloud'): {len(bm25_hits)} hits")
        for h in bm25_hits[:2]:
            print(f"   - [{h['score']:.2f}] {h['section']}: {h['content_preview'][:100]}...")

        # Verify Dense (Qdrant) Search
        dense = DenseSearchEngine()
        embedder = get_embedding_provider()
        q_vec = (await embedder.embed_texts(["cloud revenue intelligent cloud"]))[0]
        dense_hits = dense.search(q_vec, top_k=5, filters={"ticker": "MSFT"})
        print(f"\n7. Dense Search Test (Qdrant): {len(dense_hits)} hits")
        for h in dense_hits[:2]:
            print(f"   - [{h['score']:.4f}] {h.get('payload', {}).get('section')}: {h.get('payload', {}).get('content_preview', '')[:100]}...")

        # Verify Deduplication on Repeated Ingestion
        print("\n8. Testing Repeated Ingestion Idempotency (no duplicates)...")
        initial_fact_count = len(facts)
        initial_filing_count = len(filings)
        initial_chunk_count = len(parent_chunks) + len(child_chunks)

        res2 = await run_ingestion(
            db=db,
            ticker="MSFT",
            form_types=["10-K", "10-Q"],
            fiscal_years=[2023, 2024],
            max_filings=2,
        )

        filings_after = await repo.get_filings_for_company(db, company.id)
        facts_after = await repo.get_facts_for_company(db, company.id)
        q_c_after = await db.execute(select(DocumentChunk).where(DocumentChunk.filing_id == filings[0].id))
        chunks_after = q_c_after.scalars().all()

        print(f"   - Filings: before={initial_filing_count}, after={len(filings_after)} (Diff: {len(filings_after) - initial_filing_count})")
        print(f"   - Facts: before={initial_fact_count}, after={len(facts_after)} (Diff: {len(facts_after) - initial_fact_count})")
        print(f"   - Chunks for filing 0: before={initial_chunk_count}, after={len(chunks_after)} (Diff: {len(chunks_after) - initial_chunk_count})")
        assert len(filings_after) == initial_filing_count, "Duplicate filings created on re-ingestion!"
        assert len(facts_after) == initial_fact_count, "Duplicate facts created on re-ingestion!"
        assert len(chunks_after) == initial_chunk_count, "Duplicate chunks created on re-ingestion!"

        print("\n>>> ALL PHASE 3 INGESTION & IDEMPOTENCY CHECKS PASSED SUCCESSFULLY! <<<")


if __name__ == "__main__":
    asyncio.run(verify_msft())
