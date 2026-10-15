"""Answer generation service — orchestrates facts, retrieval, calculation, and LLM generation."""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import ProviderUnavailableError
from app.core.logging import get_logger
from app.db import repositories as repo
from app.financial.calculator import (
    CalculationResult,
    build_facts_dict,
    calculate_all_metrics,
    calculate_revenue_growth,
    calculate_gross_margin,
    calculate_operating_margin,
    calculate_net_profit_margin,
    calculate_debt_to_equity,
    calculate_free_cash_flow,
    _get_fact_entry,
)
from app.generation.citation_builder import build_citations, validate_citations_in_answer
from app.generation.prompts import SYSTEM_PROMPT, build_answer_prompt
from app.generation.query_router import classify_query
from app.retrieval.retriever import HybridRetriever
from app.schemas.query import (
    CalculationDetail,
    ComparisonRow,
    QueryResponse,
    SourceCitation,
)

logger = get_logger(__name__)


async def answer_question(
    db: AsyncSession,
    question: str,
    ticker: str,
    fiscal_years: Optional[List[int]] = None,
    form_types: Optional[List[str]] = None,
    top_k: int = 4,
    retrieval_mode: str = "hybrid",
    use_reranker: bool = True,
    include_calculations: bool = True,
    include_narrative: bool = True,
) -> QueryResponse:
    """Full answer pipeline: classify → retrieve facts → calculate → retrieve evidence → generate."""
    start_time = time.time()
    settings = get_settings()

    # 1. Classify the query
    classification = classify_query(question)
    query_type = classification["query_type"]
    detected_years = classification["fiscal_years"] or fiscal_years or []
    detected_metrics = classification["metrics"]

    logger.info(
        "Query classified: type=%s, years=%s, metrics=%s",
        query_type, detected_years, detected_metrics,
    )

    # 2. Get company
    company = await repo.get_company_by_ticker(db, ticker)
    if not company:
        return QueryResponse(
            question=question,
            query_type=query_type,
            answer=f"Company '{ticker}' not found. Please ingest the company first using the /api/companies/{ticker}/ingest endpoint.",
            warnings=["Company not found in database"],
            processing_time_ms=_elapsed_ms(start_time),
        )

    if query_type == "unsupported":
        return QueryResponse(
            question=question,
            query_type=query_type,
            answer=f"The requested topic ('{question}') is not disclosed or covered in standard SEC regulatory filings (10-K/10-Q) for {ticker}. The filings do not contain this information.",
            warnings=["Topic not disclosed in SEC filings"],
            processing_time_ms=_elapsed_ms(start_time),
        )

    # 3. Retrieve structured financial facts
    calculations: List[CalculationDetail] = []
    comparison_table: List[ComparisonRow] = []
    sources: List[SourceCitation] = []
    warnings: List[str] = []

    if include_calculations and classification["requires_calculation"] and detected_years:
        # Get base facts from DB
        base_concepts = list(set((detected_metrics or []) + [
            "revenue", "net_income", "operating_income", "gross_profit",
            "total_assets", "total_liabilities", "stockholders_equity",
            "operating_cash_flow", "capital_expenditures", "cash_and_equivalents",
            "long_term_debt", "cost_of_revenue",
        ]))
        fact_records = await repo.get_facts_for_company(
            db, company.id, concepts=base_concepts, fiscal_years=detected_years,
        )
        facts_dict = build_facts_dict(fact_records, rich=True)

        # 3a. Record direct reported base facts requested by user
        for metric in (detected_metrics or []):
            for fy in detected_years:
                entry = _get_fact_entry(facts_dict, metric, fy)
                if entry and entry.get("value") is not None:
                    calculations.append(CalculationDetail(
                        metric=metric,
                        value=entry["value"],
                        unit=entry.get("unit", "USD"),
                        formula="Reported in SEC filing",
                        period=f"FY{fy}",
                        fiscal_year=fy,
                        input_facts=[entry],
                        status="success",
                        source_refs=[entry.get("source_ref") or f"{metric}_FY{fy}"],
                    ))
                    # Also build a primary source citation for this fact
                    src_id = f"SRC-FACT-{metric[:4].upper()}-{fy}"
                    if not any(s.source_id == src_id for s in sources):
                        sources.append(SourceCitation(
                            source_id=src_id,
                            chunk_id=entry.get("fact_id"),
                            content_preview=(
                                f"{ticker} reported {metric.replace('_', ' ')} of "
                                f"{entry['value']:,.2f} {entry.get('unit', 'USD')} for FY{fy} "
                                f"in Form {entry.get('form_type', '10-K')} "
                                f"(Filing date: {entry.get('filing_date', 'N/A')}, Accession: {entry.get('accession_number', 'N/A')})."
                            ),
                            section="Item 8 Financial Statements",
                            form_type=entry.get("form_type", "10-K"),
                            fiscal_year=fy,
                            fiscal_period=entry.get("fiscal_period", "FY"),
                            filing_date=entry.get("filing_date"),
                            accession_number=entry.get("accession_number"),
                        ))

        # Run derived calculations
        calc_results = calculate_all_metrics(facts_dict, detected_years)

        # Also run specific metric calculations if requested
        for metric in detected_metrics:
            if metric == "revenue_growth" and len(detected_years) >= 2:
                for i in range(1, len(detected_years)):
                    r = calculate_revenue_growth(facts_dict, detected_years[i], detected_years[i - 1])
                    if r not in calc_results:
                        calc_results.append(r)

        # Build calculation details
        for r in calc_results:
            if r.status == "success" or not calculations:
                calculations.append(CalculationDetail(**r.to_dict()))

        # Build comparison table
        if len(detected_years) >= 2:
            comparison_table = _build_comparison_table(facts_dict, calc_results, detected_years)

    # 4. Retrieve narrative evidence
    narrative_evidence = ""
    retrieved_docs = []

    if include_narrative and (classification["requires_narrative"] or len(sources) < 2 or not detected_metrics):
        try:
            retriever = HybridRetriever()
            retrieval_result = await retriever.retrieve(
                db, question,
                company_id=company.id,
                ticker=ticker,
                fiscal_years=detected_years or None,
                rerank_top_k=top_k,
                mode=retrieval_mode,
                enable_reranking=use_reranker,
            )
            retrieved_docs = retrieval_result.get("children", [])
            parent_docs = retrieval_result.get("parents", [])

            # Build narrative evidence text
            evidence_parts = []
            for i, doc in enumerate(retrieved_docs):
                preview = doc.get("content_preview", "")[:500]
                src_id = f"SRC-{doc.get('id', '')[:8]}"
                evidence_parts.append(
                    f"[{src_id}] (Section: {doc.get('section', 'N/A')}, "
                    f"FY{doc.get('fiscal_year', '?')}, {doc.get('form_type', '?')})\n{preview}"
                )
            narrative_evidence = "\n\n---\n\n".join(evidence_parts)

            # Build citations
            narrative_sources = build_citations(retrieved_docs, parent_docs)
            sources.extend(narrative_sources)
        except Exception as e:
            logger.warning("Retrieval failed: %s", e)
            warnings.append(f"Evidence retrieval partially failed: {str(e)}")

    # 5. Generate answer
    answer = ""
    model_used = None

    if settings.has_chat_provider:
        try:
            # Build prompt
            facts_text = _format_facts_for_prompt(
                await repo.get_facts_for_company(
                    db, company.id, concepts=detected_metrics or None,
                    fiscal_years=detected_years,
                ) if detected_years else []
            )
            calcs_text = "\n".join(
                f"- {c.metric}: {c.value} {c.unit} ({c.formula})"
                for c in calculations if c.status == "success"
            )
            source_ids_text = ", ".join(s.source_id for s in sources)
            warnings_text = "\n".join(f"- {w}" for w in warnings) if warnings else ""

            prompt = build_answer_prompt(
                question=question,
                query_type=query_type,
                financial_facts=facts_text,
                calculations=calcs_text,
                narrative_evidence=narrative_evidence,
                source_ids=source_ids_text,
                warnings=warnings_text,
            )

            answer, model_used = await _call_llm(prompt)

            # Validate citations
            valid_ids = {s.source_id for s in sources}
            answer = validate_citations_in_answer(answer, valid_ids)

        except ProviderUnavailableError as e:
            answer = _build_fallback_answer(question, calculations, sources, warnings, comparison_table)
            warnings.append(str(e))
        except Exception as e:
            logger.error("LLM generation failed: %s", e)
            answer = _build_fallback_answer(question, calculations, sources, warnings, comparison_table)
            warnings.append(f"Answer generation failed: {str(e)}")
    else:
        answer = _build_fallback_answer(question, calculations, sources, warnings, comparison_table)
        if settings.limited_mode:
            warnings.append("Running in limited mode — no AI provider configured. Showing raw data only.")

    return QueryResponse(
        question=question,
        query_type=query_type,
        answer=answer,
        calculations=calculations,
        comparison_table=comparison_table,
        sources=sources,
        warnings=warnings,
        model_used=model_used,
        processing_time_ms=_elapsed_ms(start_time),
    )


async def _call_llm(prompt: str) -> tuple[str, str]:
    """Call the configured LLM provider."""
    settings = get_settings()

    if settings.ai_chat_provider == "gemini" and settings.has_gemini:
        from google import genai
        client = genai.Client(api_key=settings.gemini_api_key)
        response = client.models.generate_content(
            model=settings.gemini_chat_model,
            contents=prompt,
            config={"system_instruction": SYSTEM_PROMPT},
        )
        return response.text, settings.gemini_chat_model

    if settings.ai_chat_provider == "openai" and settings.has_openai:
        import openai
        client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
        response = await client.chat.completions.create(
            model=settings.openai_chat_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
        )
        return response.choices[0].message.content, settings.openai_chat_model

    raise ProviderUnavailableError(settings.ai_chat_provider)


def _build_fallback_answer(
    question: str,
    calculations: List[CalculationDetail],
    sources: List[SourceCitation],
    warnings: List[str],
    comparison_table: Optional[List[ComparisonRow]] = None,
) -> str:
    """Build a structured answer without LLM when provider is unavailable."""
    parts = [f"**Question:** {question}\n"]

    success_calcs = [c for c in calculations if c.status == "success" and c.value is not None]
    if success_calcs:
        parts.append("**Direct Answer & Financial Metrics:**")
        for c in success_calcs:
            val_fmt = f"${c.value:,.2f}" if c.unit == "USD" else f"{c.value:,.2f} {c.unit}"
            parts.append(
                f"- **{c.metric.replace('_', ' ').title()}** ({c.period or f'FY{c.fiscal_year}'}): "
                f"**{val_fmt}** ({c.formula or 'Reported in SEC filing'})"
            )
        parts.append("")

    if comparison_table:
        parts.append("**Multi-Period Comparison:**")
        for r in comparison_table:
            vals_str = ", ".join(f"{k}: ${v:,.2f}" if r.unit == "USD" else f"{k}: {v:,.2f} {r.unit}" for k, v in r.values.items() if v is not None)
            change_str = f" | Change: {r.change_pct:+.2f}%" if r.change_pct is not None else ""
            parts.append(f"- **{r.metric.replace('_', ' ').title()}**: {vals_str}{change_str}")
        parts.append("")
    elif not success_calcs and not sources and not any("Company" in w for w in warnings):
        parts.append("The requested information is not disclosed in the available SEC filings for this company.\n")

    if sources:
        parts.append("**Retrieved Evidence & Citations:**")
        for s in sources[:4]:
            parts.append(
                f"- [{s.source_id}] {s.section or 'N/A'} "
                f"(FY{s.fiscal_year or '?'}, {s.form_type or 'Filing'}): {s.content_preview[:200]}..."
            )
        parts.append("")

    if warnings:
        parts.append("**Notes:**")
        for w in warnings:
            parts.append(f"- {w}")

    parts.append(
        "\n*DISCLAIMER: This tool provides financial data analysis for research "
        "and educational purposes only. It is not investment advice.*"
    )
    return "\n".join(parts)


def _format_facts_for_prompt(facts: list) -> str:
    """Format DB fact records into readable text for the LLM prompt."""
    if not facts:
        return ""
    lines = []
    for f in facts:
        fy = f.fiscal_year if hasattr(f, "fiscal_year") else "?"
        fp = f.fiscal_period if hasattr(f, "fiscal_period") else ""
        concept = f.concept if hasattr(f, "concept") else ""
        value = f.value if hasattr(f, "value") else ""
        unit = f.unit if hasattr(f, "unit") else ""
        form = f.form_type if hasattr(f, "form_type") else ""
        lines.append(f"- {concept}: {value:,.0f} {unit} (FY{fy} {fp}, {form})")
    return "\n".join(lines[:50])  # Limit to avoid token overflow


def _build_comparison_table(
    facts_dict: Dict[str, Dict[int, float]],
    calc_results: List[CalculationResult],
    fiscal_years: List[int],
) -> List[ComparisonRow]:
    """Build a multi-year comparison table."""
    rows: List[ComparisonRow] = []
    sorted_years = sorted(fiscal_years)

    # Reported metrics
    for metric in ["revenue", "net_income", "operating_income", "gross_profit",
                    "total_assets", "total_liabilities", "stockholders_equity",
                    "operating_cash_flow", "cash_and_equivalents", "long_term_debt"]:
        if metric in facts_dict:
            values = {}
            for fy in sorted_years:
                raw_val = facts_dict[metric].get(fy)
                val = raw_val.get("value") if isinstance(raw_val, dict) else raw_val
                if val is not None:
                    values[f"FY{fy}"] = float(val)

            if values:
                row = ComparisonRow(metric=metric, unit="USD", values=values)
                # Calculate change if 2 years
                if len(sorted_years) == 2:
                    raw_v1 = facts_dict[metric].get(sorted_years[0])
                    v1 = raw_v1.get("value") if isinstance(raw_v1, dict) else raw_v1
                    raw_v2 = facts_dict[metric].get(sorted_years[1])
                    v2 = raw_v2.get("value") if isinstance(raw_v2, dict) else raw_v2
                    if v1 is not None and v2 is not None:
                        row.change = float(v2) - float(v1)
                        if v1 != 0:
                            row.change_pct = (float(v2) - float(v1)) / abs(float(v1)) * 100
                rows.append(row)

    # Calculated metrics
    for calc in calc_results:
        if calc.status == "success" and calc.value is not None:
            existing = next((r for r in rows if r.metric == calc.metric), None)
            if existing:
                existing.values[f"FY{calc.fiscal_year}"] = calc.value
            else:
                rows.append(ComparisonRow(
                    metric=calc.metric,
                    unit=calc.unit,
                    values={f"FY{calc.fiscal_year}": calc.value},
                ))

    return rows


def _elapsed_ms(start: float) -> float:
    return round((time.time() - start) * 1000, 1)
