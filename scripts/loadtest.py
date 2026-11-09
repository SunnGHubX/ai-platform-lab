#!/usr/bin/env python3
"""Tiny dependency-free load generator for an OpenAI-compatible endpoint (vLLM).

Use it to push vllm:num_requests_waiting above the KEDA threshold and watch replicas scale.

    python3 scripts/loadtest.py --url http://localhost:8000 --concurrency 64 --requests 500
"""
import argparse
import json
import statistics
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor


def one_request(url: str, model: str, max_tokens: int) -> float:
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": "Explain GitOps in three sentences."}],
        "max_tokens": max_tokens,
    }).encode()
    req = urllib.request.Request(f"{url}/v1/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    start = time.perf_counter()
    with urllib.request.urlopen(req, timeout=300) as resp:
        resp.read()
    return time.perf_counter() - start


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://localhost:8000")
    p.add_argument("--model", default="qwen")
    p.add_argument("--concurrency", type=int, default=32)
    p.add_argument("--requests", type=int, default=200)
    p.add_argument("--max-tokens", type=int, default=256)
    a = p.parse_args()

    latencies, errors = [], 0
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=a.concurrency) as pool:
        futures = [pool.submit(one_request, a.url, a.model, a.max_tokens) for _ in range(a.requests)]
        for f in futures:
            try:
                latencies.append(f.result())
            except Exception as exc:  # noqa: BLE001 - report and keep going
                errors += 1
                print(f"error: {exc}")
    wall = time.perf_counter() - t0

    if latencies:
        latencies.sort()
        p95 = latencies[int(len(latencies) * 0.95) - 1]
        print(f"ok={len(latencies)} errors={errors} wall={wall:.1f}s rps={len(latencies)/wall:.2f}")
        print(f"latency p50={statistics.median(latencies):.2f}s p95={p95:.2f}s max={latencies[-1]:.2f}s")
    else:
        print(f"all {errors} requests failed")


if __name__ == "__main__":
    main()
