from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_phase5_6_acceptance_has_live_probe_and_atomic_runner() -> None:
    probe = ROOT / "tests/phase5_6/probe_phase5_6_pipeline.py"
    runner = ROOT / "tests/phase5_6/run_phase5_6_acceptance.sh"
    assert probe.is_file()
    assert runner.is_file()
    source = probe.read_text(encoding="utf-8")
    assert "/risk/assets" in source
    assert "/mission/inspection_tasks" in source
    assert "/simulation/scenario_truth" not in source
    runner_source = runner.read_text(encoding="utf-8")
    assert ".staging" in runner_source
    assert "SHA256SUMS" in runner_source
