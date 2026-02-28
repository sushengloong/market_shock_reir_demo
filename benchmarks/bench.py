from __future__ import annotations

import argparse
import concurrent.futures
import json
import resource
import statistics
import sys
import time
from pathlib import Path

from slowlib.api import run_workload


SCENARIOS: dict[str, dict[str, str]] = {
    "1a": {
        "label": "LLM auto: single-threaded Python -> single-threaded Rust",
        "before_mode": "python_st",
        "after_mode": "rust_st",
    },
    "1b": {
        "label": "LLM auto: single-threaded Python -> multi-threaded Rust",
        "before_mode": "python_st",
        "after_mode": "rust_mt",
    },
    "1c": {
        "label": "LLM auto: single-threaded Python -> async Rust",
        "before_mode": "python_st",
        "after_mode": "rust_async",
    },
    "2": {
        "label": "multi-threaded Python -> multi-threaded Rust",
        "before_mode": "python_mt",
        "after_mode": "rust_mt",
    },
    "3": {
        "label": "async Python -> async Rust",
        "before_mode": "python_async",
        "after_mode": "rust_async",
    },
}


def _ru_maxrss_to_mb(raw_value: float) -> float:
    # On macOS ru_maxrss is bytes; on Linux it's KiB.
    if sys.platform == "darwin":
        return float(raw_value) / (1024.0 * 1024.0)
    return float(raw_value) / 1024.0


def parse_workers(workers_spec: str) -> list[int]:
    parts = [p.strip() for p in workers_spec.split(",") if p.strip()]
    workers: list[int] = []
    for part in parts:
        w = int(part)
        if w < 1:
            raise ValueError("workers must be >= 1")
        workers.append(w)
    if not workers:
        raise ValueError("workers list cannot be empty")
    seen: set[int] = set()
    deduped: list[int] = []
    for w in workers:
        if w not in seen:
            seen.add(w)
            deduped.append(w)
    return deduped


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    idx = int(round((len(values) - 1) * q))
    return sorted(values)[idx]


def execution_mode_for_scenario(scenario: str, phase: str) -> str:
    config = SCENARIOS[scenario]
    return config["before_mode"] if phase == "before" else config["after_mode"]


def run_benchmark(
    size: int,
    runs: int,
    seed: int,
    story_mode: str,
    scenario: str,
    phase: str,
    workers: int,
) -> dict[str, object]:
    mode = execution_mode_for_scenario(scenario, phase)
    timings_ms: list[float] = []
    cpu_util_pct: list[float] = []
    peak_rss_mb: list[float] = []
    peak_rss_delta_mb: list[float] = []
    checksum = None

    for run_idx in range(runs):
        rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        cpu_t0 = time.process_time()
        t0 = time.perf_counter()
        result = run_workload(
            size=size,
            seed=seed + run_idx * 100_003,
            story_mode=story_mode,
            execution_mode=mode,
            workers=workers,
        )
        elapsed_s = time.perf_counter() - t0
        elapsed_ms = elapsed_s * 1000.0
        cpu_elapsed = time.process_time() - cpu_t0
        rss_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

        timings_ms.append(elapsed_ms)
        cpu_util_pct.append((cpu_elapsed / elapsed_s) * 100.0 if elapsed_s > 0 else 0.0)
        peak_rss_mb.append(_ru_maxrss_to_mb(rss_after))
        peak_rss_delta_mb.append(_ru_maxrss_to_mb(max(0.0, float(rss_after - rss_before))))
        checksum = result["checksum"]

    return {
        "workload": f"market_data_{scenario}_{phase}_{story_mode}_size_{size}",
        "scenario": scenario,
        "scenario_label": SCENARIOS[scenario]["label"],
        "phase": phase,
        "execution_mode": mode,
        "runs": runs,
        "workers": workers,
        "story_mode": story_mode,
        "median_ms": round(statistics.median(timings_ms), 3),
        "p95_ms": round(percentile(timings_ms, 0.95), 3),
        "cpu_util_pct_median": round(statistics.median(cpu_util_pct), 3),
        "cpu_util_pct_p95": round(percentile(cpu_util_pct, 0.95), 3),
        "peak_rss_mb_max": round(max(peak_rss_mb), 3) if peak_rss_mb else 0.0,
        "peak_rss_delta_mb_median": round(statistics.median(peak_rss_delta_mb), 3),
        "checksum": checksum,
    }


def run_scaling_demo(
    size: int,
    runs: int,
    seed: int,
    story_mode: str,
    scenario: str,
    phase: str,
    workers: list[int],
    workers_per_job: int,
) -> dict[str, object]:
    mode = execution_mode_for_scenario(scenario, phase)

    rows: list[dict[str, object]] = []
    baseline_median_ms = None
    baseline_throughput = None

    def parallel_once(concurrency: int, run_seed: int) -> int:
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = [
                pool.submit(
                    run_workload,
                    size=size,
                    seed=run_seed + idx * 10_007,
                    story_mode=story_mode,
                    execution_mode=mode,
                    workers=workers_per_job,
                )
                for idx in range(concurrency)
            ]
            results = [f.result() for f in futures]
        return int(sum(int(r["checksum"]) for r in results) % 1_000_000_007)

    for worker_count in workers:
        timings_ms: list[float] = []
        cpu_util_pct: list[float] = []
        peak_rss_mb: list[float] = []
        peak_rss_delta_mb: list[float] = []
        checksum = None

        for run_idx in range(runs):
            rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            cpu_t0 = time.process_time()
            t0 = time.perf_counter()
            result_checksum = parallel_once(worker_count, seed + run_idx * 100_003)
            elapsed_s = time.perf_counter() - t0
            elapsed_ms = elapsed_s * 1000.0
            cpu_elapsed = time.process_time() - cpu_t0
            rss_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

            timings_ms.append(elapsed_ms)
            cpu_util_pct.append((cpu_elapsed / elapsed_s) * 100.0 if elapsed_s > 0 else 0.0)
            peak_rss_mb.append(_ru_maxrss_to_mb(rss_after))
            peak_rss_delta_mb.append(_ru_maxrss_to_mb(max(0.0, float(rss_after - rss_before))))
            checksum = result_checksum

        median_ms = statistics.median(timings_ms)
        p95_ms = percentile(timings_ms, 0.95)
        throughput_eps = (worker_count * size) / (median_ms / 1000.0)

        if baseline_median_ms is None:
            baseline_median_ms = median_ms
            baseline_throughput = throughput_eps

        rows.append(
            {
                "workers": worker_count,
                "median_ms": round(median_ms, 3),
                "p95_ms": round(p95_ms, 3),
                "throughput_events_per_s": round(throughput_eps, 3),
                "latency_speedup_vs_1_worker": round(baseline_median_ms / median_ms, 3),
                "throughput_gain_vs_1_worker": round(throughput_eps / baseline_throughput, 3),
                "cpu_util_pct_median": round(statistics.median(cpu_util_pct), 3),
                "cpu_util_pct_p95": round(percentile(cpu_util_pct, 0.95), 3),
                "peak_rss_mb_max": round(max(peak_rss_mb), 3) if peak_rss_mb else 0.0,
                "peak_rss_delta_mb_median": round(statistics.median(peak_rss_delta_mb), 3),
                "checksum": checksum,
            }
        )

    return {
        "scenario": scenario,
        "scenario_label": SCENARIOS[scenario]["label"],
        "phase": phase,
        "execution_mode": mode,
        "workers_per_job": workers_per_job,
        "size_per_worker": size,
        "scaling": rows,
        "note": "Scaling run for selected scenario/phase.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Deterministic benchmark for market_shock_reir_demo")
    parser.add_argument("--runs", type=int, default=7)
    parser.add_argument("--size", type=int, default=20_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--story-mode", default="normal", choices=["normal", "liberation_day_tariff_spike"])
    parser.add_argument("--scenario", default="1a", choices=sorted(SCENARIOS.keys()))
    parser.add_argument("--phase", default="before", choices=["before", "after"])
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--gil-demo", action="store_true", help="Add worker-scaling table for current scenario phase")
    parser.add_argument("--scaling-workers", default="1,2,4,8", help="Comma-separated worker counts for --gil-demo")
    parser.add_argument("--json-out", type=Path, default=None)
    parser.add_argument("--profile", action="store_true", help="No-op flag for compatibility")
    args = parser.parse_args()

    size = 5_000 if args.quick else args.size
    runs = 3 if args.quick else args.runs

    report = run_benchmark(
        size=size,
        runs=runs,
        seed=args.seed,
        story_mode=args.story_mode,
        scenario=args.scenario,
        phase=args.phase,
        workers=max(1, args.workers),
    )
    if args.gil_demo:
        report["gil_demo"] = run_scaling_demo(
            size=size,
            runs=runs,
            seed=args.seed,
            story_mode=args.story_mode,
            scenario=args.scenario,
            phase=args.phase,
            workers=parse_workers(args.scaling_workers),
            workers_per_job=max(1, args.workers),
        )

    output = json.dumps(report, indent=2)
    print(output)

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(output + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
