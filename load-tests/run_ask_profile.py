"""Measure real RAG requests with explicit warm-up and request-level evidence."""

from __future__ import annotations

import argparse
import json
import math
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

QUESTIONS = [
    "Delta Lake lưu dữ liệu phản hồi như thế nào?",
    "Feast có vai trò gì trong nền tảng này?",
    "Qdrant hỗ trợ tìm kiếm tài liệu như thế nào?",
    "MLflow được dùng để quản lý phiên bản nào?",
    "Kafka giúp hệ thống tiếp nhận dữ liệu như thế nào?",
]


def percentiles(values: list[float]) -> dict[str, float] | None:
    if not values:
        return None
    ordered = sorted(values)
    return {
        name: round(ordered[math.ceil(q * len(ordered)) - 1], 3)
        for name, q in (("p50", 0.50), ("p95", 0.95), ("p99", 0.99))
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8080")
    parser.add_argument("--requests", type=int, default=30)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--asker-id", default="load-profile")
    parser.add_argument("--out", type=Path, default=Path("reports/runtime/ask-load.json"))
    args = parser.parse_args()
    if args.requests < 1 or args.workers < 1 or args.warmup < 0:
        parser.error("requests/workers must be positive; warmup must be non-negative")

    started_at = datetime.now(UTC).isoformat()
    with httpx.Client(base_url=args.url.rstrip("/"), timeout=90.0) as client:

        def request(index: int) -> dict[str, Any]:
            question = QUESTIONS[index % len(QUESTIONS)]
            result: dict[str, Any] = {"index": index, "question": question, "status": 0}
            started = time.perf_counter()
            try:
                response = client.post(
                    "/api/v1/ask",
                    json={"asker_id": args.asker_id, "question": question, "top_k": 3},
                )
                result["status"] = response.status_code
                result["request_id"] = response.headers.get("x-request-id")
                body = response.json()
                if response.status_code == 200:
                    result.update(
                        answer=body.get("answer"),
                        evidence=body.get("evidence"),
                        audit=body.get("audit"),
                        source_ids=[s.get("doc_id") for s in body.get("sources", [])],
                    )
                else:
                    result["error"] = body
            except (httpx.HTTPError, ValueError) as error:
                result["error"] = f"{type(error).__name__}: {error}"
            result["latency_ms"] = round((time.perf_counter() - started) * 1000, 3)
            return result

        warmup = [request(i) for i in range(args.warmup)]
        started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            measured = list(pool.map(request, range(args.requests)))
        elapsed = time.perf_counter() - started

    successful = [row for row in measured if row["status"] == 200 and row.get("answer")]
    report = {
        "started_at_utc": started_at,
        "finished_at_utc": datetime.now(UTC).isoformat(),
        "url": args.url.rstrip("/") + "/api/v1/ask",
        "model_scope": "Real configured serving endpoint; no response substitution",
        "questions": QUESTIONS,
        "requests": args.requests,
        "workers": args.workers,
        "asker_id": args.asker_id,
        "warmup_excluded_from_measurement": warmup,
        "elapsed_seconds": round(elapsed, 3),
        "throughput_requests_per_second": round(args.requests / elapsed, 3),
        "status_counts": dict(Counter(str(row["status"]) for row in measured)),
        "successful_answers": len(successful),
        "latency_ms_all_requests": percentiles([row["latency_ms"] for row in measured]),
        "latency_ms_successful_answers": percentiles([row["latency_ms"] for row in successful]),
        "requests_detail": measured,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k not in {
        "questions", "warmup_excluded_from_measurement", "requests_detail"
    }}, indent=2))
    return 0 if len(successful) == args.requests else 1


if __name__ == "__main__":
    raise SystemExit(main())
