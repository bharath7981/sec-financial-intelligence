"""Benchmark script comparing the 5 retrieval and reasoning strategies on the golden dataset."""

from __future__ import annotations

import asyncio
import json
import sys
import os
import time
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import AsyncSessionLocal, init_db
from app.evaluation.benchmark_dataset import GOLDEN_BENCHMARK_QUESTIONS
from app.evaluation.evaluator import run_benchmark_evaluation


STRATEGIES = [
    {
        "name": "Strategy A: Dense Only",
        "description": "Dense vector search via embeddings + Qdrant, narrative only, no calculations",
        "config": {
            "retrieval_mode": "dense",
            "use_reranker": False,
            "include_calculations": False,
            "include_narrative": True,
            "top_k": 4,
        },
    },
    {
        "name": "Strategy B: Sparse BM25 Only",
        "description": "Keyword/token frequency BM25 search, narrative only, no calculations",
        "config": {
            "retrieval_mode": "sparse",
            "use_reranker": False,
            "include_calculations": False,
            "include_narrative": True,
            "top_k": 4,
        },
    },
    {
        "name": "Strategy C: Hybrid + RRF",
        "description": "Dense + Sparse reciprocal rank fusion without reranking",
        "config": {
            "retrieval_mode": "hybrid",
            "use_reranker": False,
            "include_calculations": False,
            "include_narrative": True,
            "top_k": 4,
        },
    },
    {
        "name": "Strategy D: Hybrid + Reranking",
        "description": "Dense + Sparse RRF with relevance reranking",
        "config": {
            "retrieval_mode": "hybrid",
            "use_reranker": True,
            "include_calculations": False,
            "include_narrative": True,
            "top_k": 4,
        },
    },
    {
        "name": "Strategy E: Full Pipeline",
        "description": "Hybrid + Reranking + Structured XBRL Calculations + Provenance",
        "config": {
            "retrieval_mode": "hybrid",
            "use_reranker": True,
            "include_calculations": True,
            "include_narrative": True,
            "top_k": 4,
        },
    },
]


async def run_all_benchmarks():
    print("=" * 70)
    print("SEC FINANCIAL INTELLIGENCE ENGINE — BENCHMARK STRATEGY COMPARISON")
    print(f"Total Golden Questions: {len(GOLDEN_BENCHMARK_QUESTIONS)}")
    print("=" * 70)

    await init_db()

    overall_results = []

    # Run on all 52 questions (focusing on MSFT real-world ingestion + un-ingested tickers)
    for strategy in STRATEGIES:
        print(f"\n---> Evaluating: {strategy['name']} ...")
        t0 = time.perf_counter()

        async with AsyncSessionLocal() as db:
            summary = await run_benchmark_evaluation(
                db=db,
                config=strategy["config"],
                dataset=GOLDEN_BENCHMARK_QUESTIONS,
            )

        elapsed = time.perf_counter() - t0
        print(
            f"     Accuracy: {summary['accuracy'] * 100:.1f}% | "
            f"Citation Coverage: {summary['citation_coverage'] * 100:.1f}% | "
            f"Avg Latency: {summary['avg_latency_ms']:.1f}ms | "
            f"Passed: {summary['passed_count']}/{summary['total_evaluated']} | "
            f"Run Time: {elapsed:.2f}s"
        )

        overall_results.append({
            "strategy": strategy["name"],
            "description": strategy["description"],
            "accuracy_pct": round(summary["accuracy"] * 100, 1),
            "citation_coverage_pct": round(summary["citation_coverage"] * 100, 1),
            "avg_latency_ms": summary["avg_latency_ms"],
            "passed": summary["passed_count"],
            "total": summary["total_evaluated"],
            "details": summary["details"],
        })

    # Output Markdown Summary Table
    print("\n" + "=" * 70)
    print("FINAL BENCHMARK COMPARISON MATRIX")
    print("=" * 70)
    print("| Strategy | Accuracy (%) | Citation Coverage (%) | Avg Latency (ms) | Passed / Total |")
    print("| :--- | :---: | :---: | :---: | :---: |")
    for r in overall_results:
        print(
            f"| **{r['strategy']}** | {r['accuracy_pct']}% | "
            f"{r['citation_coverage_pct']}% | {r['avg_latency_ms']:.1f} ms | "
            f"{r['passed']} / {r['total']} |"
        )

    # Save results to a json file for report integration
    output_path = os.path.join(os.path.dirname(__file__), "benchmark_results.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(overall_results, f, indent=2)
    print(f"\nFull detailed results saved to {output_path}")

    return overall_results


if __name__ == "__main__":
    asyncio.run(run_all_benchmarks())
