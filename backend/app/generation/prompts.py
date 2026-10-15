"""System prompts for the financial research assistant."""

from __future__ import annotations

SYSTEM_PROMPT = """You are a financial research assistant. Answer only from the supplied verified financial facts and retrieved filing evidence. Do not invent financial values, citations, accounting definitions, or management explanations. Keep fiscal periods and units explicit. Distinguish directly reported figures from calculated metrics. If evidence is insufficient or contradictory, explain the limitation. Every material financial claim must be linked to a supplied source. Never claim that a source supports a statement unless the supplied evidence actually supports it.

DISCLAIMER: This tool provides financial data analysis for research and educational purposes only. It is not investment advice. Always verify financial data against original SEC filings."""


def build_answer_prompt(
    question: str,
    query_type: str,
    financial_facts: str,
    calculations: str,
    narrative_evidence: str,
    source_ids: str,
    warnings: str,
) -> str:
    """Build the full prompt for answer generation."""
    prompt_parts = [
        f"## User Question\n{question}\n",
        f"## Query Type\n{query_type}\n",
    ]

    if financial_facts:
        prompt_parts.append(f"## Verified Financial Facts\n{financial_facts}\n")

    if calculations:
        prompt_parts.append(f"## Calculation Results\n{calculations}\n")

    if narrative_evidence:
        prompt_parts.append(f"## Retrieved Filing Evidence\n{narrative_evidence}\n")

    if source_ids:
        prompt_parts.append(f"## Available Source IDs\n{source_ids}\n")

    if warnings:
        prompt_parts.append(f"## Warnings\n{warnings}\n")

    prompt_parts.append(
        "## Instructions\n"
        "Provide a clear, structured answer addressing the question. Include:\n"
        "1. Direct answer with specific numbers when available\n"
        "2. Period comparison if multiple years are involved\n"
        "3. Calculation details if metrics were computed\n"
        "4. Narrative context from filings when relevant\n"
        "5. Source citations in [SOURCE: id] format\n"
        "6. Any limitations or missing data\n"
        "\nDo NOT invent values not present in the supplied evidence."
    )

    return "\n".join(prompt_parts)
