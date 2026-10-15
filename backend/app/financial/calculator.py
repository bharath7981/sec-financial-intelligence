"""Deterministic financial calculation engine.

All arithmetic is performed in Python — never delegated to an LLM.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional, Sequence

from app.core.logging import get_logger
from app.financial.concept_mapping import METRIC_DEFINITIONS

logger = get_logger(__name__)


class CalculationResult:
    """Structured result of a financial calculation."""

    def __init__(
        self,
        metric: str,
        value: Optional[float] = None,
        unit: str = "USD",
        formula: Optional[str] = None,
        period: Optional[str] = None,
        fiscal_year: Optional[int] = None,
        input_facts: Optional[List[Dict[str, Any]]] = None,
        status: str = "success",
        warnings: Optional[List[str]] = None,
        source_refs: Optional[List[str]] = None,
    ):
        self.metric = metric
        self.value = value
        self.unit = unit
        self.formula = formula
        self.period = period
        self.fiscal_year = fiscal_year
        self.input_facts = input_facts or []
        self.status = status
        self.warnings = warnings or []
        self.source_refs = source_refs or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric": self.metric,
            "value": self.value,
            "unit": self.unit,
            "formula": self.formula,
            "period": self.period,
            "fiscal_year": self.fiscal_year,
            "input_facts": self.input_facts,
            "status": self.status,
            "warnings": self.warnings,
            "source_refs": self.source_refs,
        }


def _get_fact_entry(
    facts: Dict[str, Any],
    metric: str,
    fiscal_year: int,
) -> Optional[Dict[str, Any]]:
    """Get rich fact entry from dictionary."""
    metric_data = facts.get(metric, {})
    val = metric_data.get(fiscal_year)
    if val is None:
        return None
    if isinstance(val, dict):
        return val
    return {
        "metric": metric,
        "fiscal_year": fiscal_year,
        "value": float(val),
        "source_ref": f"{metric}_FY{fiscal_year}",
    }


def _get_fact_value(
    facts: Dict[str, Any],
    metric: str,
    fiscal_year: int,
) -> Optional[float]:
    """Get a fact value from the facts dictionary, keyed by metric → fiscal_year → value."""
    entry = _get_fact_entry(facts, metric, fiscal_year)
    return entry.get("value") if entry else None


def _fact_ref(metric: str, fy: int) -> Dict[str, Any]:
    return {"metric": metric, "fiscal_year": fy}


def calculate_revenue_growth(
    facts: Dict[str, Dict[int, float]],
    current_year: int,
    previous_year: int,
) -> CalculationResult:
    """Revenue growth = (current - previous) / previous * 100."""
    current = _get_fact_value(facts, "revenue", current_year)
    previous = _get_fact_value(facts, "revenue", previous_year)

    if current is None or previous is None:
        missing = []
        if current is None:
            missing.append(f"revenue for FY{current_year}")
        if previous is None:
            missing.append(f"revenue for FY{previous_year}")
        return CalculationResult(
            metric="revenue_growth",
            status="missing_data",
            warnings=[f"Missing: {', '.join(missing)}"],
            formula="(current_revenue - previous_revenue) / previous_revenue * 100",
            period=f"FY{previous_year}->FY{current_year}",
            input_facts=[_fact_ref("revenue", current_year), _fact_ref("revenue", previous_year)],
        )

    if previous == 0:
        return CalculationResult(
            metric="revenue_growth",
            status="error",
            warnings=["Previous revenue is zero — cannot compute growth rate"],
            formula="(current_revenue - previous_revenue) / previous_revenue * 100",
            period=f"FY{previous_year}->FY{current_year}",
            input_facts=[_fact_ref("revenue", current_year), _fact_ref("revenue", previous_year)],
        )

    value = (current - previous) / previous * 100
    return CalculationResult(
        metric="revenue_growth",
        value=round(value, 2),
        unit="%",
        formula="(current_revenue - previous_revenue) / previous_revenue * 100",
        period=f"FY{previous_year}->FY{current_year}",
        fiscal_year=current_year,
        input_facts=[
            {"metric": "revenue", "fiscal_year": current_year, "value": current},
            {"metric": "revenue", "fiscal_year": previous_year, "value": previous},
        ],
        source_refs=[f"revenue_FY{current_year}", f"revenue_FY{previous_year}"],
    )


def calculate_margin(
    facts: Dict[str, Dict[int, float]],
    numerator_metric: str,
    denominator_metric: str,
    result_metric: str,
    fiscal_year: int,
    formula_str: str,
) -> CalculationResult:
    """Generic margin calculation = numerator / denominator * 100."""
    numerator = _get_fact_value(facts, numerator_metric, fiscal_year)
    denominator = _get_fact_value(facts, denominator_metric, fiscal_year)

    if numerator is None or denominator is None:
        missing = []
        if numerator is None:
            missing.append(f"{numerator_metric} for FY{fiscal_year}")
        if denominator is None:
            missing.append(f"{denominator_metric} for FY{fiscal_year}")
        return CalculationResult(
            metric=result_metric,
            status="missing_data",
            warnings=[f"Missing: {', '.join(missing)}"],
            formula=formula_str,
            fiscal_year=fiscal_year,
            period=f"FY{fiscal_year}",
        )

    if denominator == 0:
        return CalculationResult(
            metric=result_metric,
            status="error",
            warnings=[f"{denominator_metric} is zero — cannot compute margin"],
            formula=formula_str,
            fiscal_year=fiscal_year,
            period=f"FY{fiscal_year}",
        )

    value = numerator / denominator * 100
    return CalculationResult(
        metric=result_metric,
        value=round(value, 2),
        unit="%",
        formula=formula_str,
        fiscal_year=fiscal_year,
        period=f"FY{fiscal_year}",
        input_facts=[
            {"metric": numerator_metric, "fiscal_year": fiscal_year, "value": numerator},
            {"metric": denominator_metric, "fiscal_year": fiscal_year, "value": denominator},
        ],
        source_refs=[f"{numerator_metric}_FY{fiscal_year}", f"{denominator_metric}_FY{fiscal_year}"],
    )


def calculate_gross_margin(facts: Dict[str, Dict[int, float]], fiscal_year: int) -> CalculationResult:
    return calculate_margin(facts, "gross_profit", "revenue", "gross_margin", fiscal_year,
                            "gross_profit / revenue * 100")


def calculate_operating_margin(facts: Dict[str, Dict[int, float]], fiscal_year: int) -> CalculationResult:
    return calculate_margin(facts, "operating_income", "revenue", "operating_margin", fiscal_year,
                            "operating_income / revenue * 100")


def calculate_net_profit_margin(facts: Dict[str, Dict[int, float]], fiscal_year: int) -> CalculationResult:
    return calculate_margin(facts, "net_income", "revenue", "net_profit_margin", fiscal_year,
                            "net_income / revenue * 100")


def calculate_debt_to_equity(facts: Dict[str, Dict[int, float]], fiscal_year: int) -> CalculationResult:
    """Debt-to-equity = total_liabilities / stockholders_equity (ratio, not %)."""
    liabilities = _get_fact_value(facts, "total_liabilities", fiscal_year)
    equity = _get_fact_value(facts, "stockholders_equity", fiscal_year)

    if liabilities is None or equity is None:
        missing = []
        if liabilities is None:
            missing.append(f"total_liabilities for FY{fiscal_year}")
        if equity is None:
            missing.append(f"stockholders_equity for FY{fiscal_year}")
        return CalculationResult(
            metric="debt_to_equity",
            status="missing_data",
            warnings=[f"Missing: {', '.join(missing)}"],
            formula="total_liabilities / stockholders_equity",
            fiscal_year=fiscal_year,
            period=f"FY{fiscal_year}",
        )

    if equity == 0:
        return CalculationResult(
            metric="debt_to_equity",
            status="error",
            warnings=["Stockholders' equity is zero — cannot compute ratio"],
            formula="total_liabilities / stockholders_equity",
            fiscal_year=fiscal_year,
            period=f"FY{fiscal_year}",
        )

    if equity < 0:
        value = liabilities / equity
        return CalculationResult(
            metric="debt_to_equity",
            value=round(value, 4),
            unit="ratio",
            formula="total_liabilities / stockholders_equity",
            fiscal_year=fiscal_year,
            period=f"FY{fiscal_year}",
            warnings=["Negative stockholders' equity — ratio is negative"],
            input_facts=[
                {"metric": "total_liabilities", "fiscal_year": fiscal_year, "value": liabilities},
                {"metric": "stockholders_equity", "fiscal_year": fiscal_year, "value": equity},
            ],
        )

    value = liabilities / equity
    return CalculationResult(
        metric="debt_to_equity",
        value=round(value, 4),
        unit="ratio",
        formula="total_liabilities / stockholders_equity",
        fiscal_year=fiscal_year,
        period=f"FY{fiscal_year}",
        input_facts=[
            {"metric": "total_liabilities", "fiscal_year": fiscal_year, "value": liabilities},
            {"metric": "stockholders_equity", "fiscal_year": fiscal_year, "value": equity},
        ],
        source_refs=[f"total_liabilities_FY{fiscal_year}", f"stockholders_equity_FY{fiscal_year}"],
    )


def calculate_free_cash_flow(facts: Dict[str, Dict[int, float]], fiscal_year: int) -> CalculationResult:
    """Free cash flow = operating_cash_flow - abs(capital_expenditures).

    CapEx is normalized: reported as negative (outflow) by convention,
    so we take absolute value before subtracting.
    """
    ocf = _get_fact_value(facts, "operating_cash_flow", fiscal_year)
    capex = _get_fact_value(facts, "capital_expenditures", fiscal_year)

    if ocf is None or capex is None:
        missing = []
        if ocf is None:
            missing.append(f"operating_cash_flow for FY{fiscal_year}")
        if capex is None:
            missing.append(f"capital_expenditures for FY{fiscal_year}")
        return CalculationResult(
            metric="free_cash_flow",
            status="missing_data",
            warnings=[f"Missing: {', '.join(missing)}"],
            formula="operating_cash_flow - abs(capital_expenditures)",
            fiscal_year=fiscal_year,
            period=f"FY{fiscal_year}",
        )

    # Normalize CapEx sign: always subtract as positive
    capex_abs = abs(capex)
    value = ocf - capex_abs

    warnings = []
    if capex > 0:
        warnings.append("CapEx reported as positive; sign normalized for FCF calculation")

    return CalculationResult(
        metric="free_cash_flow",
        value=round(value, 2),
        unit="USD",
        formula="operating_cash_flow - abs(capital_expenditures)",
        fiscal_year=fiscal_year,
        period=f"FY{fiscal_year}",
        input_facts=[
            {"metric": "operating_cash_flow", "fiscal_year": fiscal_year, "value": ocf},
            {"metric": "capital_expenditures", "fiscal_year": fiscal_year, "value": capex,
             "normalized": capex_abs},
        ],
        warnings=warnings,
        source_refs=[f"operating_cash_flow_FY{fiscal_year}", f"capital_expenditures_FY{fiscal_year}"],
    )


def calculate_cagr(
    facts: Dict[str, Any],
    start_year: int,
    end_year: int,
    metric: str = "revenue",
) -> CalculationResult:
    """Compound Annual Growth Rate = ((end_val / start_val) ** (1 / n) - 1) * 100.

    n = end_year - start_year.
    """
    n = end_year - start_year
    start_val = _get_fact_value(facts, metric, start_year)
    end_val = _get_fact_value(facts, metric, end_year)

    start_entry = _get_fact_entry(facts, metric, start_year) or {"metric": metric, "fiscal_year": start_year, "value": start_val}
    end_entry = _get_fact_entry(facts, metric, end_year) or {"metric": metric, "fiscal_year": end_year, "value": end_val}

    formula_str = f"({metric}_FY{end_year} / {metric}_FY{start_year}) ** (1 / {n}) - 1"
    period_str = f"FY{start_year}->FY{end_year}"

    if start_val is None or end_val is None:
        missing = []
        if start_val is None:
            missing.append(f"{metric} for FY{start_year}")
        if end_val is None:
            missing.append(f"{metric} for FY{end_year}")
        return CalculationResult(
            metric=f"{metric}_cagr",
            status="missing_data",
            warnings=[f"Missing: {', '.join(missing)}"],
            formula=formula_str,
            period=period_str,
            input_facts=[start_entry, end_entry],
        )

    if n <= 0:
        return CalculationResult(
            metric=f"{metric}_cagr",
            status="error",
            warnings=["End year must be strictly greater than start year to compute CAGR"],
            formula=formula_str,
            period=period_str,
            input_facts=[start_entry, end_entry],
        )

    if start_val <= 0 or end_val <= 0:
        return CalculationResult(
            metric=f"{metric}_cagr",
            status="error",
            warnings=["CAGR is undefined or non-standard for non-positive starting or ending values"],
            formula=formula_str,
            period=period_str,
            input_facts=[start_entry, end_entry],
        )

    cagr_value = ((end_val / start_val) ** (1.0 / n) - 1.0) * 100.0

    return CalculationResult(
        metric=f"{metric}_cagr",
        value=round(cagr_value, 2),
        unit="%",
        formula=formula_str,
        period=period_str,
        fiscal_year=end_year,
        input_facts=[start_entry, end_entry],
        source_refs=[
            start_entry.get("source_ref") or f"{metric}_FY{start_year}",
            end_entry.get("source_ref") or f"{metric}_FY{end_year}",
        ],
    )


def calculate_all_metrics(
    facts: Dict[str, Any],
    fiscal_years: List[int],
) -> List[CalculationResult]:
    """Calculate all standard metrics for the given fiscal years."""
    results: List[CalculationResult] = []
    sorted_years = sorted(fiscal_years)

    for fy in sorted_years:
        results.append(calculate_gross_margin(facts, fy))
        results.append(calculate_operating_margin(facts, fy))
        results.append(calculate_net_profit_margin(facts, fy))
        results.append(calculate_debt_to_equity(facts, fy))
        results.append(calculate_free_cash_flow(facts, fy))

    # Revenue growth for consecutive years
    for i in range(1, len(sorted_years)):
        results.append(calculate_revenue_growth(facts, sorted_years[i], sorted_years[i - 1]))

    # CAGR over entire window if >= 2 years
    if len(sorted_years) >= 2:
        results.append(calculate_cagr(facts, sorted_years[0], sorted_years[-1], "revenue"))

    return results


def build_facts_dict(fact_records: Sequence, rich: bool = False) -> Dict[str, Dict[int, Any]]:
    """Convert a list of FinancialFact records into the {metric: {fy: value_or_entry}} dict format.

    Prefers FY (annual) period and 10-K filings when duplicates exist.
    If rich=True, stores dict with fact_id, accession_number, unit, filing_date.
    If rich=False, stores float value directly.
    """
    facts: Dict[str, Dict[int, Any]] = {}
    priority: Dict[str, Dict[int, int]] = {}

    for f in fact_records:
        concept = f.concept if isinstance(f, object) and hasattr(f, "concept") else f.get("concept", "")
        fy = f.fiscal_year if hasattr(f, "fiscal_year") else f.get("fiscal_year")
        val = f.value if hasattr(f, "value") else f.get("value")
        fp = (f.fiscal_period if hasattr(f, "fiscal_period") else f.get("fiscal_period", "")) or ""
        ft = (f.form_type if hasattr(f, "form_type") else f.get("form_type", "")) or ""
        fact_id = str(f.id) if hasattr(f, "id") and f.id else str(f.get("id", ""))
        accn = f.accession_number if hasattr(f, "accession_number") else f.get("accession_number", "")
        unit = f.unit if hasattr(f, "unit") else f.get("unit", "USD")
        fdate = str(f.filing_date) if hasattr(f, "filing_date") and f.filing_date else str(f.get("filing_date", ""))

        if fy is None or val is None:
            continue

        # Priority scoring: FY > Q*, 10-K > 10-Q
        score = 0
        if fp.upper() == "FY":
            score += 10
        if "10-K" in ft.upper():
            score += 5

        facts.setdefault(concept, {})
        priority.setdefault(concept, {})

        existing_score = priority[concept].get(fy, -1)
        if score >= existing_score:
            if rich:
                entry = {
                    "value": float(val),
                    "metric": concept,
                    "fiscal_year": fy,
                    "fiscal_period": fp,
                    "fact_id": fact_id,
                    "accession_number": accn,
                    "form_type": ft,
                    "filing_date": fdate,
                    "unit": unit,
                    "source_ref": f"{concept}_FY{fy}",
                }
                facts[concept][fy] = entry
            else:
                facts[concept][fy] = float(val)
            priority[concept][fy] = score

    return facts


def build_rich_facts_dict(fact_records: Sequence) -> Dict[str, Dict[int, Any]]:
    """Convenience wrapper for build_facts_dict with rich=True."""
    return build_facts_dict(fact_records, rich=True)
