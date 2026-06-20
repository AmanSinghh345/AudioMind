from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

from audiomind.services import get_services


def evaluate(dataset_path: Path) -> dict:
    services = get_services()
    cases = [json.loads(line) for line in dataset_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    results = []
    for case in cases:
        started = time.perf_counter()
        answer = services.rag.ask(case["collection_id"], case["question"])
        latency = time.perf_counter() - started
        expected_file = case.get("expected_filename")
        expected_page = case.get("expected_page")
        citation_hit = any(
            source.filename == expected_file and
            (expected_page is None or source.page_number == expected_page)
            for source in answer.sources
        )
        results.append(
            {
                "question": case["question"], "latency_seconds": latency,
                "citation_hit": citation_hit, "grounded": answer.grounded,
                "refused": answer.method == "refusal", "sources": len(answer.sources),
            }
        )
    count = len(results)
    return {
        "cases": count,
        "citation_hit_rate": sum(item["citation_hit"] for item in results) / count if count else 0,
        "grounded_answer_rate": sum(item["grounded"] for item in results) / count if count else 0,
        "mean_latency_seconds": statistics.mean(item["latency_seconds"] for item in results) if count else 0,
        "results": results,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--output", type=Path, default=Path("evaluation/report.json"))
    args = parser.parse_args()
    report = evaluate(args.dataset)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "results"}, indent=2))
