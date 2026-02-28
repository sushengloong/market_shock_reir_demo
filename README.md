# auth_stream_reir_demo

Repository: `git@github.com:sushengloong/auth_stream_reir_demo.git`

Plain-vanilla Python target project for `reir` demos.

## Scenario
A simulated auth/security telemetry pipeline ingests JSONL events and computes:
- per-service weighted load (`notional_by_symbol`)
- per-region volume totals (`venue_volume`)
- alert/shock score from incident keywords
- deterministic checksum for correctness checks

## Story mode
Use `--story-mode credential_stuffing_spike` to simulate a deterministic burst of suspicious login activity.

## What is intentionally slow?
- repeated `json.loads` in the same hot loop
- `re.compile` inside the loop
- string concatenation in a loop
- nested token scans with char-by-char checks

This repo includes no built-in Rust paths; it is standard Python code only.

## Execution modes
`run_workload(..., execution_mode=...)` supports:
- `python_st`
- `python_mt`
- `python_async`
- `rust_st` (alias mode for REIR-applied runs)
- `rust_mt` (alias mode for REIR-applied runs)
- `async_rust` (alias mode for REIR-applied runs)
- `auto` (defaults to `python_st`)

## Demo scenarios (`bench.py`)
- `1`: `python_st -> rust_st` (workers `1`)
- `3`: `python_st -> rust_mt` (workers `1,2,4`)
- `4`: `python_mt -> rust_mt` (workers `1,2,4`)

## Install
```bash
pip install -e .
```

## Repo policy
- Keep this repo pure Python.
- Commit only the Python source and benchmark assets used by this demo.

## Run benchmark
```bash
python -m slowlib.benchmarks.bench --scenario 1 --phase before --json-out .reir/before_1.json
python -m slowlib.benchmarks.bench --scenario 1 --phase after --json-out .reir/after_1.json
python -m slowlib.benchmarks.bench --scenario 4 --phase before --gil-demo --json-out .reir/scenario4_before.json
```

The benchmark prints deterministic JSON with median/p95 and optional scaling table.
