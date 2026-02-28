from slowlib.api import generate_json_lines, run_workload
from slowlib.slow_ops import process_json_lines_py


def test_workload_deterministic_checksum() -> None:
    a = run_workload(size=300, seed=123, story_mode="credential_stuffing_spike", execution_mode="python_st")
    b = run_workload(size=300, seed=123, story_mode="credential_stuffing_spike", execution_mode="python_st")
    assert a["checksum"] == b["checksum"]
    assert a["notional_by_symbol"] == b["notional_by_symbol"]


def test_python_impl_matches_public_api() -> None:
    lines = generate_json_lines(size=500, seed=77, story_mode="normal")
    expected = process_json_lines_py(lines)
    got = run_workload(size=500, seed=77, story_mode="normal", execution_mode="python_st")
    assert got["notional_by_symbol"] == expected["notional_by_symbol"]
    assert got["venue_volume"] == expected["venue_volume"]
    assert got["checksum"] == expected["checksum"]
    assert got["shock_score"] == expected["shock_score"]


def test_mode_parity() -> None:
    baseline = run_workload(size=400, seed=17, story_mode="normal", execution_mode="python_st")
    mt = run_workload(size=400, seed=17, story_mode="normal", execution_mode="python_mt", workers=4)
    py_async = run_workload(size=400, seed=17, story_mode="normal", execution_mode="python_async", workers=4)

    assert mt == baseline
    assert py_async == baseline
