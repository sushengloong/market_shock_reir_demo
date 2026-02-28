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
- `auto` (defaults to `python_st`)

## Demo scenarios (`bench.py`)
- `1a`: single-thread parser hot path
- `1b`: single-thread parser hot path (denser payload)
- `1c`: single-thread parser hot path (max pressure)
- `2`: multi-thread parser hot path
- `3`: async parser hot path

Before/after compare the same Python execution mode. The delta comes from `reir apply` patching selected functions.

## Install
```bash
pip install -e .
```

## Repo policy
- Keep this repo pure Python.
- Commit only the Python source and benchmark assets used by this demo.

## Run benchmark
```bash
python -m slowlib.benchmarks.bench --scenario 1a --phase before --json-out .reir/before_1a.json
python -m slowlib.benchmarks.bench --scenario 1a --phase after --json-out .reir/after_1a.json
python -m slowlib.benchmarks.bench --scenario 2 --phase before --workers 4 --gil-demo --scaling-workers 1,2,4 --json-out .reir/scenario2_before.json
```

The benchmark prints deterministic JSON with median/p95 and optional scaling table.
