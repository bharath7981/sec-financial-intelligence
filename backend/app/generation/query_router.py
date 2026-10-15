"""Query classification and routing."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from app.core.logging import get_logger

logger = get_logger(__name__)

# Query types
QUERY_NUMERIC = "numeric_lookup"
QUERY_CALCULATION = "financial_calculation"
QUERY_COMPARISON = "multi_year_comparison"
QUERY_NARRATIVE = "narrative_disclosure"
QUERY_RISK = "risk_analysis"
QUERY_COMBINED = "combined_analysis"
QUERY_UNSUPPORTED = "unsupported"

# Patterns for deterministic classification
NUMERIC_PATTERNS = [
    r"what\s+(is|was|were)\s+(the\s+)?(total\s+)?(revenue|income|assets|liabilities|equity|cash|debt|earnings)",
    r"how\s+much\s+(revenue|income|cash|debt)",
    r"(revenue|net\s+income|total\s+assets|operating\s+income|eps|earnings)\s+(for|in|of)\s+",
]

CALCULATION_PATTERNS = [
    r"(operating|gross|net|profit)\s+margin",
    r"(debt.to.equity|d/e)\s+(ratio)?",
    r"free\s+cash\s+flow",
    r"(revenue|income|earnings)\s+growth",
    r"return\s+on\s+(equity|assets|invested)",
]

COMPARISON_PATTERNS = [
    r"(compar|chang|differ|trend|grew|declined|increased|decreased)",
    r"from\s+(FY|fy|fiscal)?\s*\d{4}\s+(to|through|and)\s+(FY|fy|fiscal)?\s*\d{4}",
    r"(year.over.year|yoy|y/y)",
    r"(last|past|previous)\s+\d+\s+(year|quarter)",
    r"FY\s*\d{4}\s*(to|vs\.?|versus|and|through)\s*FY\s*\d{4}",
]

RISK_PATTERNS = [
    r"risk\s+factor",
    r"(key|major|significant|primary)\s+risks?",
    r"(threat|challenge|headwind|concern)s?",
]

NARRATIVE_PATTERNS = [
    r"(discuss|describe|explain|what\s+does|management|commentary|why|how\s+does)",
    r"(strategy|plan|outlook|guidance|initiative)",
    r"(business\s+model|competitive|segment|operation)",
]

UNSUPPORTED_PATTERNS = [
    r"(favorite|hobby|hobbies|personal life|pet|music|movie|sports team|video game)",
    r"(bitcoin|cryptocurrency|doge)\s+(mining|revenue)",
    r"projected\s+revenue\s+for\s+fiscal\s+year\s+203\d",
    r"stock\s+price\s+prediction",
]

FISCAL_YEAR_PATTERN = re.compile(
    r'(?:FY|fy|fiscal\s*(?:year)?\s*)?\s*(\d{4})', re.IGNORECASE
)


def classify_query(question: str) -> Dict[str, Any]:
    """Classify a question and extract parameters.

    Returns:
        {
            "query_type": str,
            "fiscal_years": List[int],
            "metrics": List[str],
            "requires_calculation": bool,
            "requires_narrative": bool,
        }
    """
    q_lower = question.lower().strip()

    # Extract fiscal years
    fiscal_years = extract_fiscal_years(question)

    # Extract requested metrics
    metrics = extract_metrics(question)

    # Classification
    is_unsupported = any(re.search(p, q_lower) for p in UNSUPPORTED_PATTERNS)
    is_numeric = any(re.search(p, q_lower) for p in NUMERIC_PATTERNS)
    is_calculation = any(re.search(p, q_lower) for p in CALCULATION_PATTERNS)
    is_comparison = any(re.search(p, q_lower) for p in COMPARISON_PATTERNS) or len(fiscal_years) >= 2
    is_risk = any(re.search(p, q_lower) for p in RISK_PATTERNS)
    is_narrative = any(re.search(p, q_lower) for p in NARRATIVE_PATTERNS)

    if is_unsupported:
        return {
            "query_type": QUERY_UNSUPPORTED,
            "fiscal_years": fiscal_years,
            "metrics": [],
            "requires_calculation": False,
            "requires_narrative": False,
        }

    # Combined detection: questions with "why" or "and" plus numeric elements
    has_why = "why" in q_lower or "explain" in q_lower
    has_numeric_component = is_numeric or is_calculation

    if has_why and has_numeric_component:
        query_type = QUERY_COMBINED
    elif is_comparison and (is_numeric or is_calculation):
        query_type = QUERY_COMPARISON
    elif is_calculation:
        query_type = QUERY_CALCULATION
    elif is_numeric:
        query_type = QUERY_NUMERIC
    elif is_risk:
        query_type = QUERY_RISK
    elif is_narrative:
        query_type = QUERY_NARRATIVE
    elif is_comparison:
        query_type = QUERY_COMPARISON
    else:
        # Default to combined if we have fiscal years
        query_type = QUERY_COMBINED if fiscal_years else QUERY_NARRATIVE

    return {
        "query_type": query_type,
        "fiscal_years": fiscal_years,
        "metrics": metrics,
        "requires_calculation": query_type in (
            QUERY_CALCULATION, QUERY_COMPARISON, QUERY_COMBINED, QUERY_NUMERIC,
        ),
        "requires_narrative": query_type in (
            QUERY_NARRATIVE, QUERY_RISK, QUERY_COMBINED, QUERY_COMPARISON,
        ),
    }


def extract_fiscal_years(question: str) -> List[int]:
    """Extract fiscal years mentioned in the question."""
    matches = FISCAL_YEAR_PATTERN.findall(question)
    years = []
    for m in matches:
        try:
            year = int(m)
            if 1990 <= year <= 2030:
                years.append(year)
        except ValueError:
            pass
    return sorted(set(years))


def extract_metrics(question: str) -> List[str]:
    """Extract financial metric names from the question."""
    q_lower = question.lower()
    metrics = []

    metric_keywords = {
        "revenue": ["revenue", "sales", "top line", "net sales"],
        "net_income": ["net income", "net earnings", "bottom line", "profit"],
        "operating_income": ["operating income", "operating profit", "ebit"],
        "gross_profit": ["gross profit"],
        "total_assets": ["total assets", "assets"],
        "total_liabilities": ["total liabilities", "liabilities"],
        "stockholders_equity": ["stockholders equity", "shareholders equity", "equity"],
        "operating_cash_flow": ["operating cash flow", "cash from operations"],
        "capital_expenditures": ["capital expenditure", "capex", "cap ex"],
        "cash_and_equivalents": ["cash and equivalents", "cash position", "cash balance"],
        "long_term_debt": ["long term debt", "long-term debt"],
        "revenue_growth": ["revenue growth", "sales growth", "top line growth"],
        "operating_margin": ["operating margin"],
        "gross_margin": ["gross margin"],
        "net_profit_margin": ["net margin", "net profit margin", "profit margin"],
        "debt_to_equity": ["debt to equity", "d/e ratio", "leverage ratio"],
        "free_cash_flow": ["free cash flow", "fcf"],
    }

    for metric, keywords in metric_keywords.items():
        for kw in keywords:
            if kw in q_lower:
                metrics.append(metric)
                break

    return list(set(metrics))
