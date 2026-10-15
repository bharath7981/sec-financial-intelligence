"""Unit tests for the deterministic financial calculation engine."""

import pytest
from app.financial.calculator import (
    calculate_gross_margin,
    calculate_operating_margin,
    calculate_net_profit_margin,
    calculate_debt_to_equity,
    calculate_free_cash_flow,
    calculate_revenue_growth,
    build_facts_dict,
)


@pytest.fixture
def sample_facts():
    return {
        "revenue": {2022: 100_000.0, 2023: 120_000.0},
        "gross_profit": {2022: 40_000.0, 2023: 54_000.0},
        "operating_income": {2022: 25_000.0, 2023: 36_000.0},
        "net_income": {2022: 20_000.0, 2023: 30_000.0},
        "total_liabilities": {2023: 80_000.0},
        "stockholders_equity": {2023: 40_000.0},
        "operating_cash_flow": {2023: 35_000.0},
        "capital_expenditures": {2023: -10_000.0},
    }


def test_calculate_gross_margin(sample_facts):
    res = calculate_gross_margin(sample_facts, 2023)
    assert res.status == "success"
    assert res.value == 45.0  # 54k / 120k * 100
    assert res.unit == "%"


def test_calculate_operating_margin(sample_facts):
    res = calculate_operating_margin(sample_facts, 2023)
    assert res.status == "success"
    assert res.value == 30.0  # 36k / 120k * 100


def test_calculate_net_profit_margin(sample_facts):
    res = calculate_net_profit_margin(sample_facts, 2023)
    assert res.status == "success"
    assert res.value == 25.0  # 30k / 120k * 100


def test_calculate_debt_to_equity(sample_facts):
    res = calculate_debt_to_equity(sample_facts, 2023)
    assert res.status == "success"
    assert res.value == 2.0  # 80k / 40k


def test_calculate_free_cash_flow_negative_capex(sample_facts):
    # CapEx reported as -10k -> normalized to abs 10k -> FCF = 35k - 10k = 25k
    res = calculate_free_cash_flow(sample_facts, 2023)
    assert res.status == "success"
    assert res.value == 25_000.0


def test_calculate_free_cash_flow_positive_capex(sample_facts):
    sample_facts["capital_expenditures"][2023] = 10_000.0
    res = calculate_free_cash_flow(sample_facts, 2023)
    assert res.status == "success"
    assert res.value == 25_000.0
    assert any("positive" in w for w in res.warnings)


def test_calculate_revenue_growth(sample_facts):
    res = calculate_revenue_growth(sample_facts, 2023, 2022)
    assert res.status == "success"
    assert res.value == 20.0  # (120k - 100k) / 100k * 100


def test_missing_data_handling():
    empty_facts = {}
    res = calculate_gross_margin(empty_facts, 2023)
    assert res.status == "missing_data"
    assert res.value is None


def test_zero_denominator_handling():
    zero_rev_facts = {
        "revenue": {2023: 0.0},
        "gross_profit": {2023: 10_000.0},
    }
    res = calculate_gross_margin(zero_rev_facts, 2023)
    assert res.status == "error"
    assert res.value is None
    assert any("zero" in w for w in res.warnings)


def test_build_facts_dict():
    records = [
        {"concept": "revenue", "fiscal_year": 2023, "value": 100.0, "fiscal_period": "Q3", "form_type": "10-Q"},
        {"concept": "revenue", "fiscal_year": 2023, "value": 400.0, "fiscal_period": "FY", "form_type": "10-K"},
    ]
    facts = build_facts_dict(records)
    # Annual 10-K fact must supersede quarterly 10-Q fact
    assert facts["revenue"][2023] == 400.0


def test_calculate_cagr():
    from app.financial.calculator import calculate_cagr
    # $100 in 2020 to $144 in 2022 -> (144/100)**(1/2) - 1 = 1.2 - 1 = 20%
    facts = {"revenue": {2020: 100.0, 2022: 144.0}}
    res = calculate_cagr(facts, 2020, 2022)
    assert res.status == "success"
    assert res.value == 20.0
    assert res.unit == "%"


def test_calculate_cagr_invalid_periods():
    from app.financial.calculator import calculate_cagr
    facts = {"revenue": {2022: 100.0, 2020: 144.0}}
    res = calculate_cagr(facts, 2022, 2020)
    assert res.status == "error"
    assert "greater" in res.warnings[0].lower()


def test_calculate_cagr_negative_base():
    from app.financial.calculator import calculate_cagr
    facts = {"net_income": {2020: -50.0, 2022: 100.0}}
    res = calculate_cagr(facts, 2020, 2022, metric="net_income")
    assert res.status == "error"
    assert "non-positive" in res.warnings[0].lower()

