"""Unit tests for citation construction and validation."""

from app.generation.citation_builder import build_citations, validate_citations_in_answer


def test_build_citations():
    retrieved = [
        {
            "id": "chunk-12345678",
            "content_preview": "Total revenues for fiscal 2023 were $383,285 million.",
            "section": "Item 8",
            "form_type": "10-K",
            "fiscal_year": 2023,
            "accession_number": "0000320193-23-000106",
            "score": 0.92,
        }
    ]
    citations = build_citations(retrieved, [])
    assert len(citations) == 1
    assert citations[0].source_id == "SRC-chunk-12"
    assert citations[0].chunk_id == "chunk-12345678"
    assert citations[0].fiscal_year == 2023


def test_validate_citations_strips_hallucinated():
    valid_ids = {"SRC-chunk-12", "FACT-rev-2023"}
    answer_text = (
        "Revenues reached $383B in 2023 [SOURCE: SRC-chunk-12]. "
        "Invented claim [SOURCE: FAKE-999]."
    )
    validated = validate_citations_in_answer(answer_text, valid_ids)
    assert "[SOURCE: SRC-chunk-12]" in validated
    assert "FAKE-999" not in validated
