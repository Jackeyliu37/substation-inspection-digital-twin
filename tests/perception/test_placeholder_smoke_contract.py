from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROBE = ROOT / "tests/perception/probe_placeholder_pipeline.py"
SMOKE = ROOT / "tests/perception/run_placeholder_smoke.sh"


def test_probe_observes_only_development_pipeline_topics() -> None:
    source = PROBE.read_text(encoding="utf-8")
    ast.parse(source, filename=str(PROBE))

    for required in (
        '"/camera/image_raw"',
        '"/perception/development/detections"',
        '"/perception/development/annotated_image"',
        '"/diagnostics"',
        '"backend_ready"',
    ):
        assert required in source
    for forbidden in (
        "/simulation/scenario_truth",
        "/perception/safety",
        "/perception/equipment",
        "/perception/defects",
        "/perception/meters",
        '"/perception/detections"',
        '"/perception/annotated_image"',
    ):
        assert forbidden not in source


def test_smoke_is_bounded_headless_and_seals_external_evidence() -> None:
    source = SMOKE.read_text(encoding="utf-8")

    for required in (
        "--expected-commit",
        "timeout 90s python3 tests/perception/probe_placeholder_pipeline.py",
        "setsid env -u DISPLAY",
        "ROS_LOCALHOST_ONLY=1",
        "GZ_PARTITION",
        "nvidia-smi",
        "sha256sum",
        "trap cleanup EXIT INT TERM",
        'mv -- "$evidence_dir" "$final_dir"',
        "/04-perception-placeholder.staging",
    ):
        assert required in source
    assert "/simulation/scenario_truth" not in source
