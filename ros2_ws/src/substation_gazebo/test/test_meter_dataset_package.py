from __future__ import annotations

from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import zipfile

import cv2
import numpy as np
import pytest

from substation_gazebo.meter_dataset_package import (
    MeterDatasetPackageError,
    create_deterministic_zip,
    package_generated_dataset,
    validate_generated_dataset,
)
from substation_gazebo.meter_dataset_plan import load_generation_config


ROOT = Path(__file__).resolve().parents[4]
CONFIG = ROOT / "configs/meter_dataset_generation.yaml"
DEVICES = ROOT / "configs/devices.yaml"


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _fixture(tmp_path: Path):
    loaded = load_generation_config(CONFIG, DEVICES)
    samples = loaded.samples[:2]
    config = replace(loaded, samples=samples)
    root = tmp_path / "gazebo-meter-locator-v1"
    metadata = []
    for index, sample in enumerate(samples):
        image = np.full((config.height, config.width, 3), 40 + index * 80, dtype=np.uint8)
        image_path = root / sample.image_path
        image_path.parent.mkdir(parents=True, exist_ok=True)
        assert cv2.imwrite(str(image_path), image)
        label_path = root / sample.label_path
        label_path.parent.mkdir(parents=True, exist_ok=True)
        bbox = [0.5, 0.5, 0.25, 0.25]
        label_path.write_text("0 0.500000000 0.500000000 0.250000000 0.250000000\n")
        meter = config.meters[sample.asset_id]
        metadata.append(
            {
                **asdict(sample),
                "dataset_id": config.dataset_id,
                "class_id": 0,
                "class_name": "meter",
                "sensor_id": meter.sensor_id,
                "range_minimum": meter.minimum,
                "range_maximum": meter.maximum,
                "unit": meter.unit,
                "bbox_yolo": bbox,
                "generator_git_commit": "a" * 40,
            }
        )
    (root / "metadata.jsonl").write_text(
        "".join(_canonical_json(row) + "\n" for row in metadata), encoding="utf-8"
    )
    (root / "generation-result.json").write_text(
        _canonical_json(
            {
                "schema_version": 1,
                "status": "accepted",
                "sample_mode": "full",
                "expected_count": len(samples),
                "accepted_count": len(samples),
                "failure": "",
                "generator_git_commit": "a" * 40,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return root, config, metadata


def test_happy_path_is_valid_and_zip_is_byte_identical(tmp_path: Path) -> None:
    first_root, config, _ = _fixture(tmp_path / "first")
    second_root, _, _ = _fixture(tmp_path / "second")
    provenance = {"generator_git_commit": "a" * 40, "generation_id": "fixture"}

    first_summary = package_generated_dataset(
        first_root, config, "full", provenance, tmp_path / "first.zip"
    )
    second_summary = package_generated_dataset(
        second_root, config, "full", provenance, tmp_path / "second.zip"
    )

    assert first_summary.total_images == 2
    assert first_summary.split_counts == {"train": 2, "val": 0, "test": 0}
    assert first_summary.asset_counts == {
        "meter-oil-01": 2,
        "meter-pressure-01": 0,
    }
    assert first_summary.zip_sha256 == second_summary.zip_sha256
    assert (tmp_path / "first.zip").read_bytes() == (tmp_path / "second.zip").read_bytes()
    with zipfile.ZipFile(tmp_path / "first.zip") as archive:
        assert archive.namelist() == sorted(archive.namelist())
        assert all(info.date_time == (1980, 1, 1, 0, 0, 0) for info in archive.infolist())
        assert all(name.startswith("gazebo-meter-locator-v1/") for name in archive.namelist())
        assert "gazebo-meter-locator-v1/file-manifest.tsv" in archive.namelist()
        assert "gazebo-meter-locator-v1/dataset-manifest.yaml" in archive.namelist()
        assert "gazebo-meter-locator-v1/SHA256SUMS" in archive.namelist()


@pytest.mark.parametrize("kind", ["missing", "extra", "invalid_png", "wrong_dimensions"])
def test_image_contract_failures_are_rejected(tmp_path: Path, kind: str) -> None:
    root, config, _ = _fixture(tmp_path)
    if kind == "missing":
        (root / config.samples[0].image_path).unlink()
    elif kind == "extra":
        extra = root / "images/train/extra.png"
        extra.write_bytes((root / config.samples[0].image_path).read_bytes())
    elif kind == "invalid_png":
        (root / config.samples[0].image_path).write_bytes(b"not a png")
    else:
        cv2.imwrite(str(root / config.samples[0].image_path), np.zeros((10, 10, 3), np.uint8))

    with pytest.raises(MeterDatasetPackageError):
        validate_generated_dataset(root, config, "full")


@pytest.mark.parametrize(
    ("label", "code"),
    [
        ("1 0.5 0.5 0.2 0.2\n", "LABEL_CLASS_INVALID"),
        ("0 0.5 0.5 0.2\n", "LABEL_FORMAT_INVALID"),
        ("0 nan 0.5 0.2 0.2\n", "LABEL_NUMBER_INVALID"),
        ("0 0.5 0.5 1.2 0.2\n", "LABEL_BOUNDS_INVALID"),
        ("0 0.99 0.5 0.2 0.2\n", "LABEL_BOUNDS_INVALID"),
    ],
)
def test_bad_yolo_labels_are_rejected(tmp_path: Path, label: str, code: str) -> None:
    root, config, _ = _fixture(tmp_path)
    (root / config.samples[0].label_path).write_text(label, encoding="ascii")
    with pytest.raises(MeterDatasetPackageError, match=code):
        validate_generated_dataset(root, config, "full")


def test_duplicate_images_are_rejected(tmp_path: Path) -> None:
    root, config, _ = _fixture(tmp_path)
    second = root / config.samples[1].image_path
    second.write_bytes((root / config.samples[0].image_path).read_bytes())
    with pytest.raises(MeterDatasetPackageError, match="IMAGE_HASH_DUPLICATE"):
        validate_generated_dataset(root, config, "full")


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("scene_group_id", "foreign-test-group", "METADATA_PLAN_MISMATCH"),
        ("reading", float("nan"), "METADATA_NUMBER_INVALID"),
        ("unit", "bar", "METADATA_METER_MISMATCH"),
        ("range_maximum", 999.0, "METADATA_METER_MISMATCH"),
        ("image_path", "../escape.png", "PATH_UNSAFE"),
    ],
)
def test_metadata_mismatches_are_rejected(
    tmp_path: Path, field: str, value: object, code: str
) -> None:
    root, config, metadata = _fixture(tmp_path)
    metadata[0][field] = value
    (root / "metadata.jsonl").write_text(
        "".join(_canonical_json(row) + "\n" for row in metadata), encoding="utf-8"
    )
    with pytest.raises(MeterDatasetPackageError, match=code):
        validate_generated_dataset(root, config, "full")


def test_scene_group_may_not_cross_splits(tmp_path: Path) -> None:
    root, config, metadata = _fixture(tmp_path)
    second = config.samples[1]
    crossed = replace(
        second,
        split="val",
        image_path=second.image_path.replace("/train/", "/val/"),
        label_path=second.label_path.replace("/train/", "/val/"),
    )
    crossed_config = replace(config, samples=(config.samples[0], crossed))
    (root / crossed.image_path).parent.mkdir(parents=True, exist_ok=True)
    (root / crossed.label_path).parent.mkdir(parents=True, exist_ok=True)
    (root / second.image_path).replace(root / crossed.image_path)
    (root / second.label_path).replace(root / crossed.label_path)
    metadata[1].update(asdict(crossed))
    metadata[1]["scene_group_id"] = metadata[0]["scene_group_id"]
    (root / "metadata.jsonl").write_text(
        "".join(_canonical_json(row) + "\n" for row in metadata), encoding="utf-8"
    )
    with pytest.raises(MeterDatasetPackageError, match="SCENE_GROUP_SPLIT_CROSSING"):
        validate_generated_dataset(root, crossed_config, "full")


def test_incomplete_result_is_rejected(tmp_path: Path) -> None:
    root, config, _ = _fixture(tmp_path)
    result = json.loads((root / "generation-result.json").read_text())
    result["status"] = "incomplete"
    (root / "generation-result.json").write_text(_canonical_json(result) + "\n")
    with pytest.raises(MeterDatasetPackageError, match="GENERATION_RESULT_INVALID"):
        validate_generated_dataset(root, config, "full")


def test_zip_refuses_unsafe_or_unsorted_manifest_paths(tmp_path: Path) -> None:
    root, config, _ = _fixture(tmp_path)
    validate_generated_dataset(root, config, "full")
    (root / "unsafe\\name").write_text("bad")
    with pytest.raises(MeterDatasetPackageError, match="PATH_UNSAFE"):
        create_deterministic_zip(root, tmp_path / "bad.zip")


def test_packaged_manifests_match_payload(tmp_path: Path) -> None:
    root, config, _ = _fixture(tmp_path)
    summary = package_generated_dataset(
        root,
        config,
        "full",
        {"generator_git_commit": "a" * 40},
        tmp_path / "dataset.zip",
    )
    rows = (root / "file-manifest.tsv").read_text().splitlines()
    paths = [row.split("\t", 2)[2] for row in rows]
    assert paths == sorted(paths)
    assert "file-manifest.tsv" not in paths
    assert hashlib.sha256((root / "file-manifest.tsv").read_bytes()).hexdigest() == summary.file_manifest_sha256
    for line in (root / "SHA256SUMS").read_text().splitlines():
        digest, relative = line.split("  ", 1)
        assert hashlib.sha256((root / relative).read_bytes()).hexdigest() == digest
