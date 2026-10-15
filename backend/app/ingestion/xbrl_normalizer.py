"""XBRL Company Facts normalization — extract structured financial facts from SEC API."""

from __future__ import annotations

import hashlib
import uuid
from datetime import date
from typing import Any, Dict, List, Optional

from app.core.logging import get_logger
from app.ingestion.sec_client import EDGAR_DATA, sec_get_json

logger = get_logger(__name__)

# Standard XBRL concept → friendly name mappings
CONCEPT_MAP: Dict[str, str] = {
    # Revenue
    "us-gaap:Revenues": "revenue",
    "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax": "revenue",
    "us-gaap:SalesRevenueNet": "revenue",
    "us-gaap:RevenueFromContractWithCustomerIncludingAssessedTax": "revenue",
    # Cost of revenue
    "us-gaap:CostOfRevenue": "cost_of_revenue",
    "us-gaap:CostOfGoodsAndServicesSold": "cost_of_revenue",
    "us-gaap:CostOfGoodsSold": "cost_of_revenue",
    # Gross profit
    "us-gaap:GrossProfit": "gross_profit",
    # Operating income
    "us-gaap:OperatingIncomeLoss": "operating_income",
    # Net income
    "us-gaap:NetIncomeLoss": "net_income",
    "us-gaap:ProfitLoss": "net_income",
    # Total assets
    "us-gaap:Assets": "total_assets",
    # Total liabilities
    "us-gaap:Liabilities": "total_liabilities",
    "us-gaap:LiabilitiesAndStockholdersEquity": "total_liabilities_and_equity",
    # Stockholders' equity
    "us-gaap:StockholdersEquity": "stockholders_equity",
    "us-gaap:StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest": "stockholders_equity",
    # Operating cash flow
    "us-gaap:NetCashProvidedByUsedInOperatingActivities": "operating_cash_flow",
    # Capital expenditures
    "us-gaap:PaymentsToAcquirePropertyPlantAndEquipment": "capital_expenditures",
    "us-gaap:CapitalExpendituresIncurredButNotYetPaid": "capital_expenditures",
    # Cash
    "us-gaap:CashAndCashEquivalentsAtCarryingValue": "cash_and_equivalents",
    "us-gaap:CashCashEquivalentsAndShortTermInvestments": "cash_and_equivalents",
    # Debt
    "us-gaap:LongTermDebt": "long_term_debt",
    "us-gaap:LongTermDebtNoncurrent": "long_term_debt",
    # EPS
    "us-gaap:EarningsPerShareBasic": "eps_basic",
    "us-gaap:EarningsPerShareDiluted": "eps_diluted",
}

# Reverse lookup: friendly name → XBRL concepts
METRIC_TO_CONCEPTS: Dict[str, List[str]] = {}
for concept, metric in CONCEPT_MAP.items():
    METRIC_TO_CONCEPTS.setdefault(metric, []).append(concept)


async def fetch_company_facts(cik: str) -> Dict[str, Any]:
    """Fetch XBRL Company Facts from SEC API."""
    padded = cik.zfill(10)
    url = f"{EDGAR_DATA}/api/xbrl/companyfacts/CIK{padded}.json"
    logger.info("Fetching company facts for CIK %s", padded)
    return await sec_get_json(url)


def normalize_facts(
    company_facts: Dict[str, Any],
    company_id: uuid.UUID,
    ticker: str,
    cik: str,
    target_concepts: Optional[List[str]] = None,
    fiscal_years: Optional[List[int]] = None,
) -> List[Dict[str, Any]]:
    """Extract and normalize financial facts from SEC Company Facts JSON.

    Returns a list of fact dicts ready for database insertion.
    """
    facts_data = company_facts.get("facts", {})
    normalized: List[Dict[str, Any]] = []
    seen_keys = set()

    for taxonomy, concepts in facts_data.items():
        for concept_name, concept_data in concepts.items():
            full_concept = f"{taxonomy}:{concept_name}"
            friendly = CONCEPT_MAP.get(full_concept)

            # If target_concepts specified, only include those
            if target_concepts:
                if full_concept not in target_concepts and friendly not in target_concepts:
                    continue
            elif friendly is None:
                # Skip unmapped concepts unless explicitly requested
                continue

            units_data = concept_data.get("units", {})
            label = concept_data.get("label", concept_name)

            for unit_key, entries in units_data.items():
                for entry in entries:
                    val = entry.get("val")
                    if val is None:
                        continue

                    try:
                        value = float(val)
                    except (ValueError, TypeError):
                        continue

                    fy = entry.get("fy")
                    fp = entry.get("fp", "")
                    form = entry.get("form", "")
                    filed = entry.get("filed", "")
                    accn = entry.get("accn", "")
                    start = entry.get("start")
                    end = entry.get("end")

                    # Filter by fiscal year if specified
                    if fiscal_years and fy and fy not in fiscal_years:
                        continue

                    # Parse dates
                    start_date = _parse_date(start)
                    end_date = _parse_date(end)
                    instant_date = end_date if not start else None

                    # Period type
                    period_type = "instant" if instant_date else "duration"

                    # Filing date
                    filing_date = _parse_date(filed)

                    # Deduplication key
                    dim_hash = "none"
                    dedup_key = (
                        full_concept, accn, str(start_date),
                        str(end_date), str(instant_date), dim_hash,
                    )
                    if dedup_key in seen_keys:
                        continue
                    seen_keys.add(dedup_key)

                    # Source URL
                    accn_clean = accn.replace("-", "")
                    source_url = (
                        f"https://www.sec.gov/cgi-bin/viewer?action=view&"
                        f"cik={cik.zfill(10)}&type=&dateb=&owner=include&count=40&"
                        f"search_text=&action=getcompany"
                    ) if accn else None

                    normalized.append({
                        "company_id": company_id,
                        "ticker": ticker,
                        "cik": cik.zfill(10),
                        "accession_number": accn,
                        "taxonomy": taxonomy,
                        "concept": friendly or full_concept,
                        "label": label,
                        "value": value,
                        "unit": unit_key,
                        "normalized_value": value,
                        "normalized_unit": unit_key,
                        "start_date": start_date,
                        "end_date": end_date,
                        "instant_date": instant_date,
                        "period_type": period_type,
                        "fiscal_year": fy,
                        "fiscal_period": fp if fp else None,
                        "form_type": form,
                        "filing_date": filing_date,
                        "is_amendment": False,
                        "dimensions": {},
                        "dimensions_hash": dim_hash,
                        "source_url": source_url,
                        "source_ref": f"{taxonomy}:{concept_name}",
                        "provenance": "xbrl",
                    })

    logger.info("Normalized %d financial facts", len(normalized))
    return normalized


def _parse_date(date_str: Optional[str]) -> Optional[date]:
    """Parse an ISO date string safely."""
    if not date_str:
        return None
    try:
        return date.fromisoformat(date_str)
    except (ValueError, TypeError):
        return None
