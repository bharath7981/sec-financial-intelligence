"""Extract and structure financial tables from SEC filings."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from app.core.logging import get_logger

logger = get_logger(__name__)


def extract_table_text(table: Dict[str, Any]) -> str:
    """Convert a parsed table to searchable text, preserving headers and structure."""
    parts: List[str] = []

    if table.get("caption"):
        parts.append(table["caption"])

    headers = table.get("headers", [])
    if headers:
        parts.append(" | ".join(h for h in headers if h))

    for row in table.get("rows", []):
        row_text = " | ".join(str(cell) for cell in row if cell)
        if row_text.strip():
            parts.append(row_text)

    return "\n".join(parts)


def detect_periods_from_headers(headers: List[str]) -> List[str]:
    """Detect fiscal periods from table column headers.

    Looks for patterns like:
    - 'December 31, 2024'
    - 'Year Ended June 30, 2023'
    - 'Three Months Ended March 31, 2024'
    - '2024', '2023'
    - 'FY2024'
    """
    periods: List[str] = []
    for header in headers:
        if not header:
            continue
        # Year patterns
        years = re.findall(r'\b(20\d{2})\b', header)
        for year in years:
            if year not in periods:
                periods.append(year)

        # Full date patterns
        date_match = re.search(
            r'(?:January|February|March|April|May|June|July|August|'
            r'September|October|November|December)\s+\d{1,2},?\s*\d{4}',
            header,
            re.IGNORECASE,
        )
        if date_match:
            full_date = date_match.group()
            if full_date not in periods:
                periods.append(full_date)

    return periods


def detect_units_from_table(table: Dict[str, Any]) -> str:
    """Detect the unit of measurement from table context."""
    searchable = " ".join([
        table.get("caption", ""),
        " ".join(table.get("headers", [])),
    ]).lower()

    if "billion" in searchable:
        return "billions"
    if "million" in searchable:
        return "millions"
    if "thousand" in searchable:
        return "thousands"
    if "per share" in searchable:
        return "per_share"
    return "units"


def is_financial_statement_table(table: Dict[str, Any]) -> bool:
    """Check if a table appears to be a core financial statement."""
    text = extract_table_text(table).lower()
    indicators = [
        "total revenue", "net income", "total assets",
        "total liabilities", "stockholders", "shareholders",
        "operating income", "gross profit", "cash flow",
        "earnings per share", "net sales", "cost of",
    ]
    matches = sum(1 for ind in indicators if ind in text)
    return matches >= 2
