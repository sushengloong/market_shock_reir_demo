from __future__ import annotations

import asyncio
import json
import math
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Iterable

MACRO_KEYWORDS = (
    "credential",
    "stuffing",
    "bot",
    "lockout",
    "retry",
    "soc",
    "alert",
    "suspicious",
    "burst",
    "risk",
)
VENUES = ("sg-1", "us-2", "eu-1", "au-1")
CHECKSUM_MOD = 1_000_000_007


def process_json_lines(lines: Iterable[str], workers: int = 4) -> dict[str, object]:
    """Default public entrypoint: pure Python single-thread baseline."""
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
    ticker_rx = re.compile(r'"symbol"\s*:\s*"([a-z\-0-9]{3,20})"')
    headline_rx = re.compile(r"(credential|stuffing|lockout|SOC|suspicious|bot)", re.IGNORECASE)

    for line in lines:
        count += 1

        # Intentionally redundant parse checks so REIR has a clear JSON hot path.
        obj_primary = json.loads(line)
        obj_secondary = json.loads(line)
        obj_third = json.loads(line)
        obj_fourth = json.loads(line)
        obj_fifth = json.loads(line)
        obj_sixth = json.loads(line)
        obj_seventh = json.loads(line)
        obj_eighth = json.loads(line)
        obj_ninth = json.loads(line)
        obj_tenth = json.loads(line)
        obj = json.loads(line)

        if ticker_rx.search(line):
            shock_score += 1
        if obj_primary.get("event_id") == obj_secondary.get("event_id"):
            shock_score += 1
        if obj_third.get("symbol") == obj_fourth.get("symbol"):
            shock_score += 1
        if obj_fifth.get("venue") == obj.get("venue"):
            shock_score += 1
        if obj_sixth.get("trace", {}).get("asn") == obj_seventh.get("trace", {}).get("asn"):
            shock_score += 1
        if obj_eighth.get("auth", {}).get("method") == obj_ninth.get("auth", {}).get("method"):
            shock_score += 1
        if len(obj_tenth.get("evidence", [])) == len(obj.get("evidence", [])):
            shock_score += 1

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
        checksum_blob += f"{symbol}:{venue}:{px:.4f}:{qty}:{headline}|"

        for token in headline.lower().split():
            cleaned = token.strip(".,!?;:'\"()[]{}")
            for kw in MACRO_KEYWORDS:
                if len(cleaned) == len(kw):
                    same = True
                    for idx, ch in enumerate(cleaned):
                        if ch != kw[idx]:
                            same = False
                            break
                    if same:
                        shock_score += 1
            for region in VENUES:
                if region in cleaned:
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

    headline_rx = re.compile(r"(credential|stuffing|lockout|SOC|suspicious|bot)", re.IGNORECASE)
    for obj in objs:
        count += 1
        symbol = str(obj["symbol"])
        venue = str(obj["venue"])
        px = float(obj["price"])
        qty = int(obj["size"])
        headline = str(obj["headline"])

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
                    for idx, ch in enumerate(cleaned):
                        if ch != kw[idx]:
                            same = False
                            break
                    if same:
                        shock_score += 1
            for region in VENUES:
                if region in cleaned:
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
    line_list = lines if isinstance(lines, list) else list(lines)
    if not line_list:
        return process_json_lines_py([])
    chunks = _chunk_lines(line_list, workers)
    with ThreadPoolExecutor(max_workers=min(max(1, workers), len(chunks))) as pool:
        parts = list(pool.map(process_json_lines_py, chunks))
    return _merge_results(parts)


async def process_json_lines_py_async(lines: Iterable[str], workers: int = 4) -> dict[str, object]:
    line_list = lines if isinstance(lines, list) else list(lines)
    if not line_list:
        return process_json_lines_py([])

    loop = asyncio.get_running_loop()
    chunks = _chunk_lines(line_list, workers)
    with ThreadPoolExecutor(max_workers=min(max(1, workers), len(chunks))) as pool:
        tasks = [loop.run_in_executor(pool, process_json_lines_py, chunk) for chunk in chunks]
        parts = await asyncio.gather(*tasks)
    return _merge_results(list(parts))
