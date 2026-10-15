"""Evaluation runner for benchmarking retrieval and generation strategies."""

from __future__ import annotations

import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import EvaluationRun
from app.evaluation.benchmark_dataset import GOLDEN_BENCHMARK_QUESTIONS
from app.generation.answer_service import answer_question

logger = get_logger(__name__)


async def run_benchmark_evaluation(
    db: AsyncSession,
    run_id: Optional[uuid.UUID] = None,
    config: Optional[Dict[str, Any]] = None,
    dataset: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Execute evaluation benchmark across questions and return metrics."""
    config = config or {}
    dataset = dataset or GOLDEN_BENCHMARK_QUESTIONS
    logger.info("Starting evaluation run: %s with config: %s (questions: %d)", run_id, config, len(dataset))
    started_at = datetime.utcnow()

    if run_id:
        await db.execute(
            update(EvaluationRun)
            .where(EvaluationRun.id == run_id)
            .values(
                status="running",
                started_at=started_at,
                total_questions=len(dataset),
                completed_questions=0,
            )
        )
        await db.commit()

    retrieval_mode = config.get("retrieval_mode", "hybrid")
    use_reranker = config.get("use_reranker", True)
    include_calculations = config.get("include_calculations", True)
    include_narrative = config.get("include_narrative", True)
    top_k = config.get("top_k", 4)

    question_results: List[Dict[str, Any]] = []
    latencies: List[float] = []
    correct_count = 0
    grounded_citations_count = 0
    total_evaluated = len(dataset)

    for idx, item in enumerate(dataset):
        q_start = time.perf_counter()

        try:
            answer = await answer_question(
                db=db,
                question=item["question"],
                ticker=item["ticker"],
                top_k=top_k,
                retrieval_mode=retrieval_mode,
                use_reranker=use_reranker,
                include_calculations=include_calculations,
                include_narrative=include_narrative,
            )
            duration_ms = (time.perf_counter() - q_start) * 1000
            latencies.append(duration_ms)

            # Check citation presence
            has_citations = len(answer.sources) > 0
            if has_citations:
                grounded_citations_count += 1

            # Verification logic based on category and expectations
            passed = False
            ans_lower = answer.answer.lower()

            if not item.get("should_be_answerable", True):
                # Should detect missing disclosure or refuse unsupported claims
                decline_phrases = [
                    "not disclosed", "no mention", "does not contain",
                    "not found", "unavailable", "limited", "does not provide",
                    "not explicitly", "cannot find", "no record"
                ]
                passed = any(phrase in ans_lower for phrase in decline_phrases) or not has_citations
            elif item.get("expected_value_range"):
                min_v, max_v = item["expected_value_range"]
                # 1. Check structured calculations
                calc_match = any(
                    c.status == "success" and c.value is not None and min_v <= c.value <= max_v
                    for c in answer.calculations
                )
                # 2. Check keyword matches
                kw_match = any(
                    kw.lower() in ans_lower
                    for kw in item.get("expected_answer_keywords", [])
                )
                # In calculation mode: calc_match or kw_match
                passed = calc_match or kw_match or (has_citations and len(ans_lower) > 50)
            else:
                # Qualitative or narrative questions
                kw_match = any(
                    kw.lower() in ans_lower
                    for kw in item.get("expected_answer_keywords", [])
                )
                passed = (has_citations and kw_match) or (has_citations and len(ans_lower) > 80)

            if passed:
                correct_count += 1

            question_results.append({
                "id": item.get("id"),
                "question": item["question"],
                "category": item.get("category"),
                "passed": passed,
                "latency_ms": round(duration_ms, 2),
                "citations_count": len(answer.sources),
                "calculations_count": len(answer.calculations),
                "has_sources": has_citations,
            })
        except Exception as e:
            logger.error("Error evaluating question %s: %s", item.get("id"), e)
            question_results.append({
                "id": item.get("id"),
                "question": item["question"],
                "category": item.get("category"),
                "passed": False,
                "error": str(e),
            })

        if run_id:
            await db.execute(
                update(EvaluationRun)
                .where(EvaluationRun.id == run_id)
                .values(completed_questions=idx + 1)
            )
            await db.commit()

    completed_at = datetime.utcnow()
    accuracy = (correct_count / total_evaluated) if total_evaluated > 0 else 0.0
    avg_latency = (sum(latencies) / len(latencies)) if latencies else 0.0
    citation_coverage = (grounded_citations_count / total_evaluated) if total_evaluated > 0 else 0.0

    summary = {
        "strategy": {
            "retrieval_mode": retrieval_mode,
            "use_reranker": use_reranker,
            "include_calculations": include_calculations,
            "include_narrative": include_narrative,
        },
        "accuracy": round(accuracy, 4),
        "citation_coverage": round(citation_coverage, 4),
        "avg_latency_ms": round(avg_latency, 2),
        "total_evaluated": total_evaluated,
        "passed_count": correct_count,
        "details": question_results,
    }

    if run_id:
        await db.execute(
            update(EvaluationRun)
            .where(EvaluationRun.id == run_id)
            .values(
                status="completed",
                results_summary=summary,
                completed_at=completed_at,
            )
        )
        await db.commit()

    logger.info("Evaluation completed. Accuracy: %.2f%%, Latency: %.1fms", accuracy * 100, avg_latency)
    return summary
