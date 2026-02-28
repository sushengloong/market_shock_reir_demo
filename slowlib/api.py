from __future__ import annotations

import asyncio
import json
import random
from dataclasses import dataclass
from typing import Iterator

from .slow_ops import (
    process_json_lines,
    process_json_lines_py,
    process_json_lines_py_async,
    process_json_lines_py_mt,
)


@dataclass(frozen=True)
class WorkloadConfig:
    seed: int = 42
    size: int = 20_000
    story_mode: str = "normal"


def _iter_json_lines(size: int, seed: int = 42, story_mode: str = "normal") -> Iterator[str]:
    rnd = random.Random(seed)
    services = ["auth-api", "payments-api", "orders-api", "profile-api", "search-api", "edge-gateway"]
    regions = ["sg-1", "us-2", "eu-1", "au-1"]
    methods = ["password", "otp", "webauthn", "magic_link"]
    user_agents = ["chrome", "safari", "firefox", "mobile-app"]

    for i in range(size):
        symbol = services[i % len(services)]
        venue = regions[(i * 5) % len(regions)]

        base_latency_ms = {
            "auth-api": 42.0,
            "payments-api": 88.0,
            "orders-api": 61.0,
            "profile-api": 35.0,
            "search-api": 54.0,
            "edge-gateway": 28.0,
        }[symbol]

        jitter = rnd.uniform(-8.0, 8.0)
        price = max(1.0, base_latency_ms + jitter)
        size_qty = rnd.randint(20, 700)
        headline = f"Normal auth flow in {symbol} {venue}."

        if story_mode == "credential_stuffing_spike":
            spike_window = size // 3 <= i < (size // 3 + max(200, size // 20))
            if spike_window:
                price += rnd.uniform(20.0, 120.0)
                size_qty = rnd.randint(1200, 14000)
                headline = (
                    "Credential stuffing burst: elevated failed logins and retry storms; "
                    f"{symbol} in {venue} sees lockout pressure."
                )
            elif i % 17 == 0:
                headline = f"SOC alert: suspicious bot retries detected on {symbol} in {venue}."

        obj = {
            "ts": 1_700_000_000 + i,
            "symbol": symbol,
            "venue": venue,
            "price": round(price, 4),
            "size": size_qty,
            "side": "B" if (i % 2 == 0) else "S",
            "headline": headline,
            "event_id": i,
            "trace": {
                "ip_octets": [rnd.randint(1, 255) for _ in range(4)],
                "asn": rnd.randint(1_000, 99_999),
                "country": ["SG", "US", "DE", "AU"][i % 4],
                "agent": user_agents[(i * 7) % len(user_agents)],
            },
            "auth": {
                "method": methods[(i * 11) % len(methods)],
                "attempts": rnd.randint(1, 12),
                "signals": [
                    {"k": "velocity_1m", "v": round(rnd.uniform(0.0, 1.0), 4)},
                    {"k": "velocity_5m", "v": round(rnd.uniform(0.0, 1.0), 4)},
                    {"k": "ip_reputation", "v": round(rnd.uniform(0.0, 1.0), 4)},
                    {"k": "device_age", "v": round(rnd.uniform(0.0, 1.0), 4)},
                ],
            },
            "evidence": [
                {"rule": "geo_mismatch", "score": round(rnd.uniform(0.0, 1.0), 4)},
                {"rule": "impossible_travel", "score": round(rnd.uniform(0.0, 1.0), 4)},
                {"rule": "ua_churn", "score": round(rnd.uniform(0.0, 1.0), 4)},
            ],
        }
        yield json.dumps(obj, separators=(",", ":"))


def generate_json_lines(size: int, seed: int = 42, story_mode: str = "normal") -> list[str]:
    return list(_iter_json_lines(size=size, seed=seed, story_mode=story_mode))


def run_workload(
    size: int = 20_000,
    seed: int = 42,
    story_mode: str = "normal",
    execution_mode: str = "auto",
    workers: int = 4,
) -> dict[str, object]:
    lines = generate_json_lines(size=size, seed=seed, story_mode=story_mode)
    return run_processing(lines=lines, execution_mode=execution_mode, workers=workers)


def run_processing(
    lines: list[str],
    execution_mode: str = "auto",
    workers: int = 4,
) -> dict[str, object]:
    if execution_mode == "auto":
        return process_json_lines(lines, workers=workers)
    if execution_mode == "python_st":
        return process_json_lines_py(lines)
    if execution_mode == "python_mt":
        return process_json_lines_py_mt(lines, workers=workers)
    if execution_mode == "python_async":
        return asyncio.run(process_json_lines_py_async(lines, workers=workers))

    raise ValueError(f"Unknown execution_mode: {execution_mode}")
