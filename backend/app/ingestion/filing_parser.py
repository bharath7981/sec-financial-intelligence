"""Parse SEC filing HTML to extract sections, tables, and structured content."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from bs4 import BeautifulSoup, Tag

from app.core.logging import get_logger

logger = get_logger(__name__)

# Common SEC 10-K section patterns
SECTION_PATTERNS = {
    "item_1": [
        r"item\s*1[.\s:—–-]+business",
        r"item\s*1\b(?!\s*[a-z0-9])",
    ],
    "item_1a": [
        r"item\s*1a[.\s:—–-]+risk\s+factors",
        r"item\s*1a\b",
    ],
    "item_1b": [
        r"item\s*1b[.\s:—–-]+unresolved\s+staff\s+comments",
    ],
    "item_2": [
        r"item\s*2[.\s:—–-]+properties",
    ],
    "item_3": [
        r"item\s*3[.\s:—–-]+legal\s+proceedings",
    ],
    "item_5": [
        r"item\s*5[.\s:—–-]+market",
    ],
    "item_6": [
        r"item\s*6[.\s:—–-]+selected\s+financial",
        r"item\s*6[.\s:—–-]+reserved",
    ],
    "item_7": [
        r"item\s*7[.\s:—–-]+management",
        r"item\s*7\b(?!\s*a)",
    ],
    "item_7a": [
        r"item\s*7a[.\s:—–-]+quantitative",
    ],
    "item_8": [
        r"item\s*8[.\s:—–-]+financial\s+statements",
    ],
    "item_9": [
        r"item\s*9[.\s:—–-]+changes\s+in\s+and\s+disagreements",
        r"item\s*9\b(?!\s*[a-z])",
    ],
    "item_9a": [
        r"item\s*9a[.\s:—–-]+controls",
    ],
}


def parse_filing_html(html: str) -> Dict[str, Any]:
    """Parse a filing HTML document and extract structured content.

    Returns:
        {
            "sections": [{"id": ..., "heading": ..., "content": ..., "tables": [...]}],
            "tables": [{"html": ..., "headers": [...], "rows": [...]}],
            "footnotes": [{"id": ..., "text": ...}],
            "full_text": str,
        }
    """
    soup = BeautifulSoup(html, "lxml")

    # Remove script and style tags
    for tag in soup.find_all(["script", "style", "meta", "link"]):
        tag.decompose()

    sections = _extract_sections(soup)
    tables = _extract_tables(soup)

    full_text = soup.get_text(separator="\n", strip=True)
    # Truncate very long filings for manageable processing
    if len(full_text) > 500_000:
        full_text = full_text[:500_000]

    return {
        "sections": sections,
        "tables": tables,
        "footnotes": [],
        "full_text": full_text,
    }


def _extract_sections(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    """Extract sections by finding headings that match SEC item patterns."""
    sections: List[Dict[str, Any]] = []

    # Find all potential heading elements
    heading_tags = soup.find_all(
        ["h1", "h2", "h3", "h4", "p", "div", "span", "b", "strong"],
    )

    # Match headings to section patterns
    section_starts: List[Tuple[str, str, Tag]] = []
    for tag in heading_tags:
        text = tag.get_text(strip=True).lower()
        if len(text) < 3 or len(text) > 200:
            continue
        for section_id, patterns in SECTION_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    section_starts.append((section_id, tag.get_text(strip=True), tag))
                    break
            else:
                continue
            break

    if not section_starts:
        # Fallback: treat entire document as one section
        full_text = soup.get_text(separator="\n", strip=True)
        if full_text.strip():
            sections.append({
                "id": "full_document",
                "heading": "Full Document",
                "content": full_text[:100_000],
                "tables": [],
            })
        return sections

    # Extract content between section headings
    for i, (sec_id, heading_text, tag) in enumerate(section_starts):
        # Get content until next section or end
        content_parts: List[str] = []
        section_tables: List[Dict[str, Any]] = []
        current = tag.next_sibling

        # Also get siblings and next elements
        end_tag = section_starts[i + 1][2] if i + 1 < len(section_starts) else None
        content_parts.append(tag.get_text(strip=True))

        # Walk through siblings
        visited = set()
        for sibling in tag.find_all_next():
            if end_tag and sibling == end_tag:
                break
            if id(sibling) in visited:
                continue
            visited.add(id(sibling))

            if sibling.name == "table":
                table_data = _parse_single_table(sibling)
                if table_data:
                    section_tables.append(table_data)
                continue

            text = sibling.get_text(strip=True)
            if text and len(text) > 1:
                content_parts.append(text)

            # Limit section size
            if sum(len(p) for p in content_parts) > 100_000:
                break

        content = "\n".join(content_parts)
        sections.append({
            "id": sec_id,
            "heading": heading_text,
            "content": content,
            "tables": section_tables,
        })

    logger.info("Extracted %d sections from filing", len(sections))
    return sections


def _extract_tables(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    """Extract all tables from the document."""
    tables: List[Dict[str, Any]] = []
    for table_tag in soup.find_all("table"):
        table_data = _parse_single_table(table_tag)
        if table_data and table_data.get("rows"):
            tables.append(table_data)
    return tables


def _parse_single_table(table_tag: Tag) -> Optional[Dict[str, Any]]:
    """Parse a single HTML table into structured data."""
    rows = table_tag.find_all("tr")
    if not rows:
        return None

    parsed_rows: List[List[str]] = []
    for row in rows:
        cells = row.find_all(["th", "td"])
        cell_texts = [cell.get_text(strip=True) for cell in cells]
        if any(t for t in cell_texts):
            parsed_rows.append(cell_texts)

    if len(parsed_rows) < 2:
        return None

    # First row with meaningful content is likely headers
    headers = parsed_rows[0] if parsed_rows else []
    data_rows = parsed_rows[1:] if len(parsed_rows) > 1 else []

    # Detect if this is a financial table
    html_str = str(table_tag)
    is_financial = any(
        term in html_str.lower()
        for term in [
            "revenue", "income", "loss", "assets", "liabilities",
            "equity", "cash", "earnings", "shares", "per share",
            "operating", "net", "gross", "total", "$", "thousand",
            "million", "billion",
        ]
    )

    # Extract caption
    caption = ""
    caption_tag = table_tag.find("caption")
    if caption_tag:
        caption = caption_tag.get_text(strip=True)
    else:
        prev = table_tag.find_previous(["p", "div", "b", "strong"])
        if prev:
            prev_text = prev.get_text(strip=True)
            if len(prev_text) < 200:
                caption = prev_text

    return {
        "html": html_str[:50_000],  # Preserve original HTML
        "headers": headers,
        "rows": data_rows,
        "caption": caption,
        "is_financial": is_financial,
        "row_count": len(data_rows),
        "col_count": len(headers),
    }
