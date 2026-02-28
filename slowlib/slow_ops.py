from __future__ import annotations

import asyncio
import json
import math
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Iterable

MACRO_KEYWORDS = (
    "liberation",
    "day",
    "trump",
    "tariff",
    "sanction",
    "hike",
    "cut",
    "fed",
    "panic",
    "relief",
)
VENUES = ("XNYS", "XNAS", "ARCX", "BATS")
CHECKSUM_MOD = 1_000_000_007

def process_json_lines(lines: Iterable[str], workers: int = 4) -> dict[str, object]:
    """Default path before Rust apply: pure Python single-thread."""
    _ = workers
    return process_json_lines_py(lines)

def _merge_results(parts: list[dict[str, object]]) -> dict[str, object]:
    merged_notional: dict[str, float] = {}
    merged_venue: dict[str, int] = {}
    shock = 0
    checksum = 0
    count = 0

    for part in parts:
        for sym, val in dict(part["notional_by_symbol"]).items():
            merged_notional[sym] = merged_notional.get(sym, 0.0) + float(val)
        for venue, vol in dict(part["venue_volume"]).items():
            merged_venue[venue] = merged_venue.get(venue, 0) + int(vol)
        shock += int(part["shock_score"])
        checksum = (checksum + int(part["checksum"])) % CHECKSUM_MOD
        count += int(part["count"])

    rounded_notional = {k: round(v, 4) for k, v in merged_notional.items()}
    return {
        "notional_by_symbol": rounded_notional,
        "venue_volume": merged_venue,
        "shock_score": shock,
        "checksum": checksum,
        "count": count,
    }

def process_json_lines_py(lines: Iterable[str]) -> dict[str, object]:
    notional_by_symbol: dict[str, float] = {}
    venue_volume: dict[str, int] = {}
    shock_score = 0
    checksum_blob = ""
    count = 0

    for line in lines:
        count += 1

        # Intentionally bad: compile regex for each line.
        ticker_rx = re.compile(r'"symbol"\s*:\s*"([A-Z]{1,5})"')
        headline_rx = re.compile(r"(Liberation Day|Trump tariff|tariff|sanction|Fed)", re.IGNORECASE)

        if ticker_rx.search(line):
            shock_score += 1

        obj = json.loads(line)
        symbol = str(obj["symbol"])
        venue = str(obj["venue"])
        px = float(obj["price"])
        qty = int(obj["size"])
        headline = str(obj["headline"])

        notional = px * qty
        if symbol not in notional_by_symbol:
            notional_by_symbol[symbol] = 0.0
        notional_by_symbol[symbol] += notional

        if venue not in venue_volume:
            venue_volume[venue] = 0
        venue_volume[venue] += qty

        shock_score += len(headline_rx.findall(headline))

        # Intentionally bad: repeated string concat in loop.
        checksum_blob += f"{symbol}:{venue}:{px:.4f}:{qty}:{headline}|"

        # Intentionally bad: nested loops with char-by-char keyword checks.
        for token in headline.lower().split():
            cleaned = token.strip(".,!?;:'\"()[]{}")
            for kw in MACRO_KEYWORDS:
                if len(cleaned) == len(kw):
                    same = True
                    for i, ch in enumerate(cleaned):
                        if ch != kw[i]:
                            same = False
                            break
                    if same:
                        shock_score += 1
            for mic in VENUES:
                if mic.lower() in cleaned:
                    shock_score += 1

    checksum = 0
    for ch in checksum_blob:
        checksum = (checksum + ord(ch)) % CHECKSUM_MOD

    rounded_notional = {k: round(v, 4) for k, v in notional_by_symbol.items()}
    return {
        "notional_by_symbol": rounded_notional,
        "venue_volume": venue_volume,
        "shock_score": shock_score,
        "checksum": checksum,
        "count": count,
    }

def _aggregate_from_objects(objs: Iterable[dict[str, object]]) -> dict[str, object]:
    notional_by_symbol: dict[str, float] = {}
    venue_volume: dict[str, int] = {}
    shock_score = 0
    checksum_blob = ""
    count = 0

    headline_rx = re.compile(r"(Liberation Day|Trump tariff|tariff|sanction|Fed)", re.IGNORECASE)
    for obj in objs:
        count += 1
        symbol = str(obj["symbol"])
        venue = str(obj["venue"])
        px = float(obj["price"])
        qty = int(obj["size"])
        headline = str(obj["headline"])

        # Equivalent to ticker regex match in baseline input lines.
        shock_score += 1
        notional = px * qty
        notional_by_symbol[symbol] = notional_by_symbol.get(symbol, 0.0) + notional
        venue_volume[venue] = venue_volume.get(venue, 0) + qty

        shock_score += len(headline_rx.findall(headline))
        checksum_blob += f"{symbol}:{venue}:{px:.4f}:{qty}:{headline}|"

        for token in headline.lower().split():
            cleaned = token.strip(".,!?;:'\"()[]{}")
            for kw in MACRO_KEYWORDS:
                if len(cleaned) == len(kw):
                    same = True
                    for i, ch in enumerate(cleaned):
                        if ch != kw[i]:
                            same = False
                            break
                    if same:
                        shock_score += 1
            for mic in VENUES:
                if mic.lower() in cleaned:
                    shock_score += 1

    checksum = 0
    for ch in checksum_blob:
        checksum = (checksum + ord(ch)) % CHECKSUM_MOD

    rounded_notional = {k: round(v, 4) for k, v in notional_by_symbol.items()}
    return {
        "notional_by_symbol": rounded_notional,
        "venue_volume": venue_volume,
        "shock_score": shock_score,
        "checksum": checksum,
        "count": count,
    }

def _chunk_lines(lines: list[str], workers: int) -> list[list[str]]:
    if workers <= 1:
        return [lines]
    chunk_size = max(1, math.ceil(len(lines) / workers))
    return [lines[i : i + chunk_size] for i in range(0, len(lines), chunk_size)]

def process_json_lines_py_mt(lines: Iterable[str], workers: int = 4) -> dict[str, object]:
    line_list = list(lines)
    if not line_list:
        return process_json_lines_py([])
    chunks = _chunk_lines(line_list, workers)
    with ThreadPoolExecutor(max_workers=min(max(1, workers), len(chunks))) as pool:
        parts = list(pool.map(process_json_lines_py, chunks))
    return _merge_results(parts)

async def process_json_lines_py_async(lines: Iterable[str], workers: int = 4) -> dict[str, object]:
    line_list = list(lines)
    if not line_list:
        return process_json_lines_py([])

    loop = asyncio.get_running_loop()
    chunks = _chunk_lines(line_list, workers)
    with ThreadPoolExecutor(max_workers=min(max(1, workers), len(chunks))) as pool:
        tasks = [loop.run_in_executor(pool, process_json_lines_py, chunk) for chunk in chunks]
        parts = await asyncio.gather(*tasks)
    return _merge_results(list(parts))

def process_json_lines_rust(lines: Iterable[str], rust_mode: str = "st", workers: int = 4) -> dict[str, object]:
    line_list = list(lines)
    try:
        import reir_ext  # type: ignore

        parsed = None
        if rust_mode == "mt" and hasattr(reir_ext, "loads_many_mt"):
            parsed = reir_ext.loads_many_mt(line_list, int(max(1, workers)))
        elif rust_mode == "async" and hasattr(reir_ext, "loads_many_async"):
            parsed = reir_ext.loads_many_async(line_list)
        elif hasattr(reir_ext, "loads_many_st"):
            parsed = reir_ext.loads_many_st(line_list)
        elif hasattr(reir_ext, "loads"):
            parsed = [reir_ext.loads(line) for line in line_list]

        if parsed is not None:
            return _aggregate_from_objects(list(parsed))
    except Exception:
        pass

    if rust_mode == "mt":
        return process_json_lines_py_mt(line_list, workers=workers)
    if rust_mode == "async":
        return asyncio.run(process_json_lines_py_async(line_list, workers=workers))
    return process_json_lines_py(line_list)

async def process_json_lines_rust_async(lines: Iterable[str], workers: int = 4) -> dict[str, object]:
    line_list = list(lines)
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, process_json_lines_rust, line_list, "async", workers)
