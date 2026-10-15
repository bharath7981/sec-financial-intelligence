"""Unit tests for query classification and extraction."""

import pytest
from app.generation.query_router import (
    classify_query,
    extract_fiscal_years,
    extract_metrics,
    QUERY_NUMERIC,
    QUERY_CALCULATION,
    QUERY_COMPARISON,
    QUERY_RISK,
    QUERY_NARRATIVE,
    QUERY_COMBINED,
)


def test_classify_numeric():
    res = classify_query("What was the total revenue in 2023?")
    assert res["query_type"] == QUERY_NUMERIC
    assert 2023 in res["fiscal_years"]
    assert "revenue" in res["metrics"]


def test_classify_margin_calculation():
    res = classify_query("Calculate Apple's operating margin for FY2023")
    assert res["query_type"] == QUERY_CALCULATION
    assert 2023 in res["fiscal_years"]
    assert "operating_margin" in res["metrics"]
    assert res["requires_calculation"] is True


def test_classify_multi_year_comparison():
    res = classify_query("Compare revenue from FY2021 to FY2023")
    assert res["query_type"] == QUERY_COMPARISON
    assert 2021 in res["fiscal_years"]
    assert 2023 in res["fiscal_years"]


def test_classify_risk_analysis():
    res = classify_query("What are the key risk factors regarding supply chain dependencies?")
    assert res["query_type"] == QUERY_RISK
    assert res["requires_narrative"] is True


def test_extract_fiscal_years():
    assert extract_fiscal_years("in fiscal 2022 and FY 2023") == [2022, 2023]
    assert extract_fiscal_years("FY2020 vs FY2024") == [2020, 2024]
    assert extract_fiscal_years("no years here") == []
