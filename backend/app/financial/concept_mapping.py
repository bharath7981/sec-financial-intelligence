"""Financial concept mapping — maps friendly metric names to XBRL concepts."""

from __future__ import annotations

from typing import Dict, List

from app.ingestion.xbrl_normalizer import CONCEPT_MAP, METRIC_TO_CONCEPTS

# Re-export for convenience
FRIENDLY_TO_XBRL = METRIC_TO_CONCEPTS
XBRL_TO_FRIENDLY = CONCEPT_MAP

# Standard metric definitions with formulas and dependencies
METRIC_DEFINITIONS: Dict[str, Dict] = {
    "revenue": {
        "label": "Revenue",
        "concepts": METRIC_TO_CONCEPTS.get("revenue", []),
        "type": "reported",
        "unit": "USD",
    },
    "cost_of_revenue": {
        "label": "Cost of Revenue",
        "concepts": METRIC_TO_CONCEPTS.get("cost_of_revenue", []),
        "type": "reported",
        "unit": "USD",
    },
    "gross_profit": {
        "label": "Gross Profit",
        "concepts": METRIC_TO_CONCEPTS.get("gross_profit", []),
        "type": "reported",
        "unit": "USD",
        "formula": "revenue - cost_of_revenue",
        "inputs": ["revenue", "cost_of_revenue"],
    },
    "operating_income": {
        "label": "Operating Income",
        "concepts": METRIC_TO_CONCEPTS.get("operating_income", []),
        "type": "reported",
        "unit": "USD",
    },
    "net_income": {
        "label": "Net Income",
        "concepts": METRIC_TO_CONCEPTS.get("net_income", []),
        "type": "reported",
        "unit": "USD",
    },
    "total_assets": {
        "label": "Total Assets",
        "concepts": METRIC_TO_CONCEPTS.get("total_assets", []),
        "type": "reported",
        "unit": "USD",
        "period_type": "instant",
    },
    "total_liabilities": {
        "label": "Total Liabilities",
        "concepts": METRIC_TO_CONCEPTS.get("total_liabilities", []),
        "type": "reported",
        "unit": "USD",
        "period_type": "instant",
    },
    "stockholders_equity": {
        "label": "Stockholders' Equity",
        "concepts": METRIC_TO_CONCEPTS.get("stockholders_equity", []),
        "type": "reported",
        "unit": "USD",
        "period_type": "instant",
    },
    "operating_cash_flow": {
        "label": "Operating Cash Flow",
        "concepts": METRIC_TO_CONCEPTS.get("operating_cash_flow", []),
        "type": "reported",
        "unit": "USD",
    },
    "capital_expenditures": {
        "label": "Capital Expenditures",
        "concepts": METRIC_TO_CONCEPTS.get("capital_expenditures", []),
        "type": "reported",
        "unit": "USD",
    },
    "cash_and_equivalents": {
        "label": "Cash and Cash Equivalents",
        "concepts": METRIC_TO_CONCEPTS.get("cash_and_equivalents", []),
        "type": "reported",
        "unit": "USD",
        "period_type": "instant",
    },
    "long_term_debt": {
        "label": "Long-term Debt",
        "concepts": METRIC_TO_CONCEPTS.get("long_term_debt", []),
        "type": "reported",
        "unit": "USD",
        "period_type": "instant",
    },
    # Calculated ratios
    "revenue_growth": {
        "label": "Revenue Growth",
        "type": "calculated",
        "unit": "%",
        "formula": "(current_revenue - previous_revenue) / previous_revenue * 100",
        "inputs": ["revenue"],
        "requires_comparison": True,
    },
    "gross_margin": {
        "label": "Gross Margin",
        "type": "calculated",
        "unit": "%",
        "formula": "gross_profit / revenue * 100",
        "inputs": ["gross_profit", "revenue"],
    },
    "operating_margin": {
        "label": "Operating Margin",
        "type": "calculated",
        "unit": "%",
        "formula": "operating_income / revenue * 100",
        "inputs": ["operating_income", "revenue"],
    },
    "net_profit_margin": {
        "label": "Net Profit Margin",
        "type": "calculated",
        "unit": "%",
        "formula": "net_income / revenue * 100",
        "inputs": ["net_income", "revenue"],
    },
    "debt_to_equity": {
        "label": "Debt-to-Equity Ratio",
        "type": "calculated",
        "unit": "ratio",
        "formula": "total_liabilities / stockholders_equity",
        "inputs": ["total_liabilities", "stockholders_equity"],
        "note": "Expressed as a ratio (not percentage). Multiply by 100 for percentage.",
    },
    "free_cash_flow": {
        "label": "Free Cash Flow",
        "type": "calculated",
        "unit": "USD",
        "formula": "operating_cash_flow - abs(capital_expenditures)",
        "inputs": ["operating_cash_flow", "capital_expenditures"],
        "note": "CapEx sign normalized (always subtracted as positive).",
    },
    "cagr": {
        "label": "Compound Annual Growth Rate",
        "type": "calculated",
        "unit": "%",
        "formula": "(end_value / start_value) ** (1 / n) - 1",
        "inputs": ["revenue"],
        "requires_comparison": True,
    },
}


def get_concepts_for_metric(metric: str) -> List[str]:
    """Get XBRL concepts that map to a friendly metric name."""
    defn = METRIC_DEFINITIONS.get(metric, {})
    return defn.get("concepts", METRIC_TO_CONCEPTS.get(metric, []))
