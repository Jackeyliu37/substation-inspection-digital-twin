from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import uuid

import pytest
from std_msgs.msg import Header
from substation_interfaces.msg import RunContext

from substation_perception.detection_contract import to_production_detections
from substation_perception.detection_aggregator import merge_detection_arrays
from substation_perception.production_identity import (
    ProductionIdentityError,
    load_production_models,
)
import numpy as np

from substation_perception.production_nodes import (
    ProductionRuntimeGate,
    classify_equipment_crops,
)
from substation_perception.yolo_backend import RawDetection


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_LAUNCH = PACKAGE_ROOT / "launch/production_perception.launch.py"


def _load_production_launch():
    spec = importlib.util.spec_from_file_location(
        "production_perception_launch", PRODUCTION_LAUNCH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_production_launch_resolves_isolated_and_merged_release_roots() -> None:
    module = _load_production_launch()

    assert module.repository_root_from_share(
        Path("/work/project/ros2_ws/install/substation_perception/share/substation_perception")
    ) == Path("/work/project")
    assert module.repository_root_from_share(
        Path("/opt/substation/releases/commit/install/share/substation_perception")
    ) == Path("/opt/substation/releases/commit")
    assert module.repository_root_from_share(
        Path("/opt/substation/current/install/share/substation_perception")
    ) == Path("/opt/substation/current")


def _write_manifest(path: Path, sha256: str, size_bytes: int) -> None:
    path.write_text(
        f"""schema_version: 1
artifacts:
  - logical_model: yolo11n_safety
    module: safety
    filename: safety.pt
    sha256: {sha256}
    size_bytes: {size_bytes}
    task: detect
    class_names: [person]
    acceptance_status: passed
    threshold_waived: true
production_artifact_sha256:
  yolo11n_safety: {sha256}
deployment_filenames:
  yolo11n_safety: safety.pt
""",
        encoding="utf-8",
    )


def test_load_production_models_verifies_manifest_path_size_and_hash(tmp_path: Path) -> None:
    payload = b"trained-model"
    digest = hashlib.sha256(payload).hexdigest()
    model = tmp_path / digest / "safety.pt"
    model.parent.mkdir()
    model.write_bytes(payload)
    manifest = tmp_path / "manifest.yaml"
    _write_manifest(manifest, digest, len(payload))

    loaded = load_production_models(manifest, tmp_path)

    assert loaded["yolo11n_safety"].path == model
    assert loaded["yolo11n_safety"].sha256 == digest
    assert loaded["yolo11n_safety"].module == "safety"
    assert loaded["yolo11n_safety"].threshold_waived is True

    model.write_bytes(b"changed")
    with pytest.raises(ProductionIdentityError, match="MODEL_SIZE_MISMATCH"):
        load_production_models(manifest, tmp_path)


def test_runtime_gate_only_allows_matching_active_context() -> None:
    gate = ProductionRuntimeGate()
    context = RunContext()
    context.run_id = "run-1"
    context.context_revision = 4
    context.lifecycle = RunContext.LIFECYCLE_STARTING
    gate.update(context)
    assert gate.active is False

    context.lifecycle = RunContext.LIFECYCLE_ACTIVE
    gate.update(context)
    assert gate.active is True
    assert gate.run_id == "run-1"
    assert gate.context_revision == 4

    context.lifecycle = RunContext.LIFECYCLE_ENDING
    gate.update(context)
    assert gate.active is False


def test_production_detection_prefix_and_evidence_id_are_preserved_by_merge() -> None:
    header = Header(frame_id="camera_optical_frame")
    header.stamp.sec = 8
    ids = iter([
        uuid.UUID("11111111-1111-4111-8111-111111111111"),
        uuid.UUID("22222222-2222-4222-8222-222222222222"),
    ])
    safety = to_production_detections(
        header,
        640,
        480,
        [RawDetection(0, "no_hardhat", 0.9, (10, 20, 30, 50))],
        module="safety",
        id_factory=lambda: next(ids),
    )
    equipment = to_production_detections(
        header,
        640,
        480,
        [RawDetection(0, "breaker", 0.8, (50, 60, 90, 120))],
        module="equipment",
        id_factory=lambda: next(ids),
    )

    merged = merge_detection_arrays(header, [safety, equipment])

    assert [item.id for item in merged.detections] == [
        "11111111-1111-4111-8111-111111111111",
        "22222222-2222-4222-8222-222222222222",
    ]
    assert [item.results[0].hypothesis.class_id for item in merged.detections] == [
        "safety/no_hardhat",
        "equipment/breaker",
    ]


def test_merge_rejects_mixed_frame_or_stamp() -> None:
    header = Header(frame_id="camera_optical_frame")
    one = to_production_detections(header, 10, 10, [], module="safety")
    other_header = Header(frame_id="camera_optical_frame")
    other_header.stamp.sec = 1
    other = to_production_detections(other_header, 10, 10, [], module="equipment")

    with pytest.raises(ValueError, match="DETECTION_HEADER_MISMATCH"):
        merge_detection_arrays(header, [one, other])


def test_fault_classifier_uses_equipment_crop_and_preserves_box() -> None:
    header = Header(frame_id="camera_optical_frame")
    equipment = to_production_detections(
        header,
        20,
        20,
        [RawDetection(0, "breaker", 0.9, (2, 3, 12, 15))],
        module="equipment",
        id_factory=lambda: uuid.UUID("11111111-1111-4111-8111-111111111111"),
    )

    class Backend:
        def __init__(self) -> None:
            self.shapes = []

        def classify(self, crop):
            self.shapes.append(crop.shape)
            return "2_broken_component", 0.87

    backend = Backend()
    output = classify_equipment_crops(
        header,
        np.zeros((20, 20, 3), dtype=np.uint8),
        equipment,
        backend,
        id_factory=lambda: uuid.UUID("22222222-2222-4222-8222-222222222222"),
    )

    assert backend.shapes == [(12, 10, 3)]
    assert output.detections[0].bbox == equipment.detections[0].bbox
    assert output.detections[0].results[0].hypothesis.class_id == "defect/2_broken_component"
    assert output.detections[0].results[0].hypothesis.score == pytest.approx(0.87)
