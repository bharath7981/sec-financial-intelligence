"""Full-stack integration tests covering the complete user journey.

End-to-end verification of:
1. System health check
2. Company ticker discovery
3. Company details & metadata
4. Ingested filings verification
5. Normalized financial facts retrieval
6. Calculated financial ratios & CAGR
7. Natural language query answering with verifiable citations
8. Multi-period comparison with percentage changes
9. Boundary unanswerable questions handling
10. Graceful error handling for missing/unsupported inputs
"""

from __future__ import annotations

import pytest
import pytest_asyncio
import httpx

from app.main import create_app
from app.db.session import init_db


@pytest_asyncio.fixture(scope="module")
async def client():
    """Async test client with initialized database."""
    await init_db()
    app = create_app()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_01_health_check(client: httpx.AsyncClient):
    """Verify health endpoint reports system status."""
    res = await client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ("healthy", "degraded")
    assert "services" in data
    assert "database" in data["services"]


@pytest.mark.asyncio
async def test_02_company_search(client: httpx.AsyncClient):
    """Verify company search resolves Microsoft."""
    res = await client.get("/api/companies/search?q=MSFT")
    assert res.status_code == 200
    data = res.json()
    results = data["results"]
    assert len(results) > 0
    match = next((c for c in results if c["ticker"] == "MSFT"), None)
    assert match is not None
    assert match["cik"] == "0000789019"
    assert "MICROSOFT" in match["name"].upper()


@pytest.mark.asyncio
async def test_03_company_profile(client: httpx.AsyncClient):
    """Verify company profile retrieval."""
    res = await client.get("/api/companies/MSFT")
    assert res.status_code == 200
    data = res.json()
    assert data["ticker"] == "MSFT"
    assert data["cik"] == "0000789019"
    assert data["fiscal_year_end"] == "0630"


@pytest.mark.asyncio
async def test_04_filings_list(client: httpx.AsyncClient):
    """Verify ingested filings for MSFT."""
    res = await client.get("/api/companies/MSFT/filings")
    assert res.status_code == 200
    data = res.json()
    filings = data["filings"]
    assert len(filings) > 0
    form_types = {f["form_type"] for f in filings}
    assert "10-K" in form_types
    # Verify FY attribution
    years = {f["fiscal_year"] for f in filings if f.get("fiscal_year")}
    assert 2023 in years or 2024 in years


@pytest.mark.asyncio
async def test_05_financial_facts_retrieval(client: httpx.AsyncClient):
    """Verify retrieval of normalized financial facts via metrics endpoint."""
    res = await client.get("/api/companies/MSFT/metrics?concepts=revenue,net_income&fiscal_years=2023,2024")
    assert res.status_code == 200
    data = res.json()
    assert data["ticker"] == "MSFT"
    assert "revenue" in data["metrics"]
    rev_facts = data["metrics"]["revenue"]
    rev_2023 = next((f for f in rev_facts if f["fiscal_year"] == 2023 and f.get("fiscal_period") == "FY" and f["value"] > 200_000_000_000), None)
    assert rev_2023 is not None
    assert 211_000_000_000 <= rev_2023["value"] <= 212_500_000_000
    assert rev_2023["unit"] == "USD"


@pytest.mark.asyncio
async def test_06_calculated_metrics(client: httpx.AsyncClient):
    """Verify deterministic calculated metrics endpoint."""
    res = await client.get("/api/companies/MSFT/metrics?fiscal_years=2023,2024")
    assert res.status_code == 200
    data = res.json()
    calculated = data["calculated"]
    assert len(calculated) > 0
    metrics_by_name = {m["metric"]: m for m in calculated}
    assert "gross_margin" in metrics_by_name
    assert "operating_margin" in metrics_by_name
    assert "net_profit_margin" in metrics_by_name
    assert "free_cash_flow" in metrics_by_name
    # Gross margin should be ~68-70%
    gm = metrics_by_name["gross_margin"]
    assert gm["status"] == "success"
    assert 65.0 <= gm["value"] <= 72.0


@pytest.mark.asyncio
async def test_07_query_direct_revenue_with_citations(client: httpx.AsyncClient):
    """Verify asking direct question produces grounded answer and source citations."""
    payload = {
        "ticker": "MSFT",
        "question": "What was Microsoft total revenue in fiscal year 2023?",
        "fiscal_years": [2023],
        "top_k": 4,
    }
    res = await client.post("/api/query", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "211,915" in data["answer"] or "211.9" in data["answer"]
    assert len(data["calculations"]) > 0
    assert len(data["sources"]) > 0
    # First source should cite Form 10-K with accession number
    src = data["sources"][0]
    assert "10-K" in (src["form_type"] or "")
    assert src["accession_number"] is not None


@pytest.mark.asyncio
async def test_08_query_multi_year_comparison(client: httpx.AsyncClient):
    """Verify multi-period comparison query calculates percentage growth accurately."""
    payload = {
        "ticker": "MSFT",
        "question": "Compare Microsoft total revenue between FY2023 and FY2024. What was the percentage growth?",
        "fiscal_years": [2023, 2024],
        "top_k": 4,
    }
    res = await client.post("/api/query", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert len(data["comparison_table"]) > 0
    rev_row = next((r for r in data["comparison_table"] if r["metric"] == "revenue"), None)
    assert rev_row is not None
    assert rev_row["change"] is not None
    # Growth should be ~15.67%
    assert 15.0 <= rev_row["change_pct"] <= 16.5


@pytest.mark.asyncio
async def test_09_query_financial_ratios(client: httpx.AsyncClient):
    """Verify ratio question calculates free cash flow and margins."""
    payload = {
        "ticker": "MSFT",
        "question": "What was Microsoft free cash flow and operating margin for FY2024?",
        "fiscal_years": [2024],
        "top_k": 4,
    }
    res = await client.post("/api/query", json=payload)
    assert res.status_code == 200
    data = res.json()
    fcf = next((c for c in data["calculations"] if c["metric"] == "free_cash_flow"), None)
    assert fcf is not None
    assert fcf["status"] == "success"
    # FY2024 FCF should be positive (~$74B)
    assert fcf["value"] > 50_000_000_000


@pytest.mark.asyncio
async def test_10_boundary_unsupported_question(client: httpx.AsyncClient):
    """Verify system gracefully declines questions outside SEC disclosures."""
    payload = {
        "ticker": "MSFT",
        "question": "What is CEO Satya Nadella favorite video game according to the 10-K?",
    }
    res = await client.post("/api/query", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["query_type"] == "unsupported"
    assert "not disclosed" in data["answer"].lower() or "not contain" in data["answer"].lower()


@pytest.mark.asyncio
async def test_11_un_ingested_ticker_error_handling(client: httpx.AsyncClient):
    """Verify asking about a non-ingested ticker prompts the user to ingest first."""
    payload = {
        "ticker": "XYZ",
        "question": "What was total revenue in fiscal year 2023?",
    }
    res = await client.post("/api/query", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "not found" in data["answer"].lower()
    assert "ingest" in data["answer"].lower()
