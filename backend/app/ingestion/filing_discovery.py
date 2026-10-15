"""Discover 10-K and 10-Q filings from SEC EDGAR submissions API."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from app.core.logging import get_logger
from app.ingestion.sec_client import EDGAR_DATA, sec_get_json

logger = get_logger(__name__)


async def fetch_submissions(cik: str) -> Dict[str, Any]:
    """Fetch the full submissions metadata for a CIK."""
    padded = cik.zfill(10)
    url = f"{EDGAR_DATA}/submissions/CIK{padded}.json"
    logger.info("Fetching submissions for CIK %s", padded)
    return await sec_get_json(url)


def extract_company_info(submissions: Dict[str, Any]) -> Dict[str, Any]:
    """Extract company metadata from submissions response."""
    return {
        "name": submissions.get("name", ""),
        "cik": str(submissions.get("cik", "")).zfill(10),
        "sic": submissions.get("sic", ""),
        "sic_description": submissions.get("sicDescription", ""),
        "state": submissions.get("stateOfIncorporation", ""),
        "fiscal_year_end": submissions.get("fiscalYearEnd", ""),
        "exchange": submissions.get("exchanges", [""])[0] if submissions.get("exchanges") else "",
        "entity_type": submissions.get("entityType", ""),
    }


def infer_fiscal_year_and_period(
    form: str,
    base_form: str,
    report_date: Optional[date],
    filing_date: Optional[date],
    fiscal_year_end: Optional[str] = None,
) -> Tuple[Optional[int], str]:
    """Calculate correct fiscal year and period (FY, Q1-Q4) accounting for non-calendar fiscal year ends."""
    if not report_date:
        fy = filing_date.year if filing_date else None
        return fy, "FY" if base_form == "10-K" else "Q"

    fye_month = 12
    if fiscal_year_end and len(fiscal_year_end) >= 2:
        try:
            fye_month = int(fiscal_year_end[:2])
        except ValueError:
            fye_month = 12

    # If the report month is strictly after the fiscal year end month, it falls into the subsequent fiscal year
    if fye_month != 12 and report_date.month > fye_month:
        fy = report_date.year + 1
    else:
        fy = report_date.year

    if base_form == "10-K":
        return fy, "FY"

    # For 10-Q, determine quarter offset from fiscal year end
    months_after_fye = (report_date.month - fye_month) % 12
    quarter_num = (months_after_fye - 1) // 3 + 1 if months_after_fye > 0 else 4
    if quarter_num in (1, 2, 3, 4):
        return fy, f"Q{quarter_num}"
    return fy, "Q"


def discover_filings(
    submissions: Dict[str, Any],
    form_types: List[str] = None,
    fiscal_years: Optional[List[int]] = None,
    max_filings: int = 50,
) -> List[Dict[str, Any]]:
    """Extract filing metadata from submissions, filtering by form type and fiscal years.

    Returns a list of filing metadata dicts.
    """
    if form_types is None:
        form_types = ["10-K", "10-Q"]
    form_types_upper = [f.upper() for f in form_types]

    fiscal_year_end = submissions.get("fiscalYearEnd")
    recent = submissions.get("filings", {}).get("recent", {})
    if not recent:
        logger.warning("No recent filings found in submissions")
        return []

    accessions = recent.get("accessionNumber", [])
    forms = recent.get("form", [])
    filing_dates = recent.get("filingDate", [])
    primary_docs = recent.get("primaryDocument", [])
    report_dates = recent.get("reportDate", [])

    filings: List[Dict[str, Any]] = []
    seen_accessions = set()

    for i in range(len(accessions)):
        form = forms[i] if i < len(forms) else ""
        base_form = form.replace("/A", "").replace("-A", "").strip().upper()

        if base_form not in form_types_upper:
            continue

        accession = accessions[i]
        if accession in seen_accessions:
            continue
        seen_accessions.add(accession)

        filing_date_str = filing_dates[i] if i < len(filing_dates) else ""
        report_date_str = report_dates[i] if i < len(report_dates) else ""

        # Parse dates
        try:
            f_date = date.fromisoformat(filing_date_str) if filing_date_str else None
        except ValueError:
            f_date = None
        try:
            r_date = date.fromisoformat(report_date_str) if report_date_str else None
        except ValueError:
            r_date = None

        # Determine accurate fiscal year and period
        fy, fp = infer_fiscal_year_and_period(
            form, base_form, r_date, f_date, fiscal_year_end
        )

        # Filter by fiscal year if specified
        if fiscal_years and fy not in fiscal_years:
            continue

        is_amendment = "/A" in form or "-A" in form

        primary_doc = primary_docs[i] if i < len(primary_docs) else ""
        accession_clean = accession.replace("-", "")
        filing_url = (
            f"https://www.sec.gov/Archives/edgar/data/"
            f"{submissions.get('cik', '')}/{accession_clean}/{primary_doc}"
        )

        filings.append({
            "accession_number": accession,
            "form_type": form,
            "filing_date": f_date,
            "period_of_report": r_date,
            "fiscal_year": fy,
            "fiscal_period": fp,
            "primary_document": primary_doc,
            "filing_url": filing_url,
            "is_amendment": is_amendment,
            "amendment_type": form if is_amendment else None,
        })

        if len(filings) >= max_filings:
            break

    logger.info("Discovered %d filings matching criteria", len(filings))
    return filings
