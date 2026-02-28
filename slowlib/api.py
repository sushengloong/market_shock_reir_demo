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
    process_json_lines_rust,
    process_json_lines_rust_async,
)


@dataclass(frozen=True)
class WorkloadConfig:
    seed: int = 42
    size: int = 20_000
    story_mode: str = "normal"


def _iter_json_lines(size: int, seed: int = 42, story_mode: str = "normal") -> Iterator[str]:
    rnd = random.Random(seed)
    symbols = ["AAPL", "MSFT", "NVDA", "TSLA", "AMD", "AMZN"]
    venues = ["XNYS", "XNAS", "ARCX", "BATS"]

    for i in range(size):
        symbol = symbols[i % len(symbols)]
        venue = venues[(i * 3) % len(venues)]

        base_px = {
            "AAPL": 190.0,
            "MSFT": 420.0,
            "NVDA": 880.0,
            "TSLA": 205.0,
            "AMD": 165.0,
            "AMZN": 178.0,
        }[symbol]

        jitter = rnd.uniform(-2.5, 2.5)
        price = base_px + jitter
        size_qty = rnd.randint(10, 400)
        headline = f"Routine session flow in {symbol} on {venue}."

        if story_mode == "liberation_day_tariff_spike":
            spike_window = size // 3 <= i < (size // 3 + max(200, size // 20))
            if spike_window:
                price += rnd.uniform(-12.0, 12.0)
                size_qty = rnd.randint(500, 4000)
                headline = (
                    "Liberation Day remarks: Trump tariff escalation hits risk assets; "
                    f"{symbol} sees panic then relief bids on {venue}."
                )
            elif i % 17 == 0:
                headline = f"Desk chatter: possible tariff carve-outs and Fed response for {symbol} on {venue}."

        obj = {
            "ts": 1_700_000_000 + i,
            "symbol": symbol,
            "venue": venue,
            "price": round(price, 4),
            "size": size_qty,
            "side": "B" if (i % 2 == 0) else "S",
            "headline": headline,
            "event_id": i,
        }
        yield json.dumps(obj, separators=(",", ":"))


def generate_json_lines(size: int, seed: int = 42, story_mode: str = "normal") -> list[str]:
    return list(_iter_json_lines(size=size, seed=seed, story_mode=story_mode))


def generate_json_payload(size: int, seed: int = 42, story_mode: str = "normal") -> str:
    # Use a single JSONL payload for Rust paths to avoid per-line Python->Rust
    # conversion/allocation overhead across the FFI boundary.
    return "\n".join(_iter_json_lines(size=size, seed=seed, story_mode=story_mode))


def run_workload(
    size: int = 20_000,
    seed: int = 42,
    story_mode: str = "normal",
    execution_mode: str = "auto",
    workers: int = 4,
) -> dict[str, object]:
    if execution_mode == "auto":
        lines = generate_json_lines(size=size, seed=seed, story_mode=story_mode)
        return process_json_lines(lines, workers=workers)
    if execution_mode == "python_st":
        lines = generate_json_lines(size=size, seed=seed, story_mode=story_mode)
        return process_json_lines_py(lines)
    if execution_mode == "python_mt":
        lines = generate_json_lines(size=size, seed=seed, story_mode=story_mode)
        return process_json_lines_py_mt(lines, workers=workers)
    if execution_mode == "python_async":
        lines = generate_json_lines(size=size, seed=seed, story_mode=story_mode)
        return asyncio.run(process_json_lines_py_async(lines, workers=workers))

    if execution_mode == "rust_st":
        payload = generate_json_payload(size=size, seed=seed, story_mode=story_mode)
        return process_json_lines_rust(payload, rust_mode="st", workers=workers)
    if execution_mode == "rust_mt":
        payload = generate_json_payload(size=size, seed=seed, story_mode=story_mode)
        return process_json_lines_rust(payload, rust_mode="mt", workers=workers)
    if execution_mode == "rust_async":
        payload = generate_json_payload(size=size, seed=seed, story_mode=story_mode)
        return asyncio.run(process_json_lines_rust_async(payload, workers=workers))

    raise ValueError(f"Unknown execution_mode: {execution_mode}")
