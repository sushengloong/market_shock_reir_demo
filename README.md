# market_shock_reir_demo

Intentionally slow Python project for `reir` demos.

## Scenario
A simulated market-data pipeline ingests JSON trade events and policy headlines, then computes:
- per-symbol traded notional
- per-venue volume totals
- a macro "shock score" from headline keywords
- deterministic checksum for correctness checks

## Story mode
Use `--story-mode liberation_day_tariff_spike` to simulate a deterministic burst of volume/headline intensity after a fictional policy shock.

## What is slow on purpose?
- `json.loads` in a tight loop
- `re.compile` inside the hot loop
- string concatenation in a loop
- nested loops with char-by-char keyword checks

## Execution modes
`run_workload(..., execution_mode=...)` supports:
- `python_st`, `python_mt`, `python_async`
- `rust_st`, `rust_mt`, `rust_async`
- `auto` (default; switches when patched by `reir apply`)

## Demo scenarios (`bench.py`)
- `1a`: Python ST -> Rust ST
- `1b`: Python ST -> Rust MT
- `1c`: Python ST -> Rust async
- `2`: Python MT -> Rust MT
- `3`: Python async -> Rust async

## Install
```bash
pip install -e .
```

## Rust folder policy
- This repo is kept as a pure Python target by default.
- `reir apply` generates `rust/reir_ext/` on demand.
- `rust/` is ignored in `.gitignore` and should not be committed.

## Run benchmark
```bash
python -m slowlib.benchmarks.bench --scenario 1a --phase before --json-out .reir/before_1a.json
python -m slowlib.benchmarks.bench --scenario 1a --phase after --json-out .reir/after_1a.json
python -m slowlib.benchmarks.bench --scenario 2 --phase before --workers 4 --gil-demo --scaling-workers 1,2,4,8 --json-out .reir/scenario2_before.json
```

The benchmark prints deterministic JSON with median/p95 and optional scaling table.
