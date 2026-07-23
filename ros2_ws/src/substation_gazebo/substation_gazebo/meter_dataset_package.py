from __future__ import annotations

from dataclasses import asdict, dataclass
import argparse
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import subprocess
from typing import Mapping, Sequence
import zipfile

import cv2
import yaml

from .meter_dataset_plan import GenerationConfig, MeterDatasetError, SamplePlan, load_generation_config


class MeterDatasetPackageError(MeterDatasetError):
    """Raised when generated data cannot be accepted as a training package."""


@dataclass(frozen=True)
class DatasetSummary:
    total_images: int
    split_counts: Mapping[str, int]
    asset_counts: Mapping[str, int]
    file_manifest_sha256: str
    metadata_sha256: str
    zip_sha256: str = ""
    zip_size_bytes: int = 0


_SPLITS = ("train", "val", "test")
_PAYLOAD_EXCLUDES = {
    "file-manifest.tsv",
    "dataset-manifest.yaml",
    "SHA256SUMS",
    "generation-result.json",
}


def _fail(code: str, detail: object) -> None:
    raise MeterDatasetPackageError(f"{code}: {detail}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_relative(path: str) -> PurePosixPath:
    if not path or "\\" in path or "//" in path:
        _fail("PATH_UNSAFE", path)
    parsed = PurePosixPath(path)
    if parsed.is_absolute() or ".." in parsed.parts or "." in parsed.parts:
        _fail("PATH_UNSAFE", path)
    return parsed


def _expected_samples(config: GenerationConfig, sample_mode: str) -> tuple[SamplePlan, ...]:
    if sample_mode == "full":
        return config.samples
    if sample_mode != "smoke":
        _fail("SAMPLE_MODE_INVALID", sample_mode)
    result: list[SamplePlan] = []
    for split in _SPLITS:
        for asset_id in config.meter_asset_ids:
            candidates = [s for s in config.samples if s.split == split and s.asset_id == asset_id]
            result.extend(candidates[:2])
    return tuple(result)


def _read_metadata(root: Path) -> list[dict[str, object]]:
    path = root / "metadata.jsonl"
    if not path.is_file():
        _fail("METADATA_MISSING", path)
    rows: list[dict[str, object]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            _fail("METADATA_JSON_INVALID", f"line={line_number} {error}")
        if not isinstance(value, dict):
            _fail("METADATA_ROW_INVALID", line_number)
        rows.append(value)
    ids = [str(row.get("sample_id", "")) for row in rows]
    if ids != sorted(ids):
        _fail("METADATA_UNSORTED", path)
    return rows


def _read_label(path: Path, width: int, height: int) -> tuple[float, float, float, float]:
    try:
        lines = path.read_text(encoding="ascii").splitlines()
    except (OSError, UnicodeError) as error:
        _fail("LABEL_FORMAT_INVALID", f"{path}: {error}")
    if len(lines) != 1:
        _fail("LABEL_FORMAT_INVALID", path)
    fields = lines[0].split()
    if len(fields) != 5:
        _fail("LABEL_FORMAT_INVALID", path)
    if fields[0] != "0":
        _fail("LABEL_CLASS_INVALID", path)
    try:
        values = tuple(float(value) for value in fields[1:])
    except ValueError:
        _fail("LABEL_NUMBER_INVALID", path)
    if not all(math.isfinite(value) for value in values):
        _fail("LABEL_NUMBER_INVALID", path)
    x, y, box_width, box_height = values
    if not (0.0 < box_width <= 1.0 and 0.0 < box_height <= 1.0):
        _fail("LABEL_BOUNDS_INVALID", path)
    if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
        _fail("LABEL_BOUNDS_INVALID", path)
    if not (x - box_width / 2.0 >= 0.0 and x + box_width / 2.0 <= 1.0):
        _fail("LABEL_BOUNDS_INVALID", path)
    if not (y - box_height / 2.0 >= 0.0 and y + box_height / 2.0 <= 1.0):
        _fail("LABEL_BOUNDS_INVALID", path)
    if box_width * width < 1.0 or box_height * height < 1.0:
        _fail("LABEL_SIZE_INVALID", path)
    return values


def _check_metadata_number(value: object, field: str, sample_id: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        _fail("METADATA_NUMBER_INVALID", f"{sample_id}.{field}")
    return float(value)


def validate_generated_dataset(
    root: Path, config: GenerationConfig, sample_mode: str
) -> DatasetSummary:
    root = Path(root)
    if not root.is_absolute() or root.is_symlink() or not root.is_dir():
        _fail("OUTPUT_DIRECTORY_INVALID", root)
    expected = _expected_samples(config, sample_mode)
    expected_by_image = {sample.image_path: sample for sample in expected}
    expected_by_label = {sample.label_path: sample for sample in expected}
    image_paths = sorted(
        path.relative_to(root).as_posix()
        for path in root.glob("images/*/*.png")
        if path.is_file()
    )
    label_paths = sorted(
        path.relative_to(root).as_posix()
        for path in root.glob("labels/*/*.txt")
        if path.is_file()
    )
    if set(image_paths) != set(expected_by_image):
        _fail("IMAGE_SET_MISMATCH", f"expected={len(expected_by_image)} actual={len(image_paths)}")
    if set(label_paths) != set(expected_by_label):
        _fail("LABEL_SET_MISMATCH", f"expected={len(expected_by_label)} actual={len(label_paths)}")

    image_hashes: dict[str, str] = {}
    for relative in image_paths:
        image = cv2.imread(str(root / relative), cv2.IMREAD_COLOR)
        if image is None:
            _fail("IMAGE_PNG_INVALID", relative)
        if image.shape != (config.height, config.width, 3):
            _fail("IMAGE_DIMENSIONS_INVALID", f"{relative}: {image.shape}")
        digest = _sha256(root / relative)
        if digest in image_hashes.values():
            _fail("IMAGE_HASH_DUPLICATE", relative)
        image_hashes[relative] = digest
        _read_label(root / expected_by_image[relative].label_path, config.width, config.height)

    rows = _read_metadata(root)
    if len(rows) != len(expected):
        _fail("METADATA_COUNT_INVALID", len(rows))
    by_id = {str(row.get("sample_id", "")): row for row in rows}
    if len(by_id) != len(rows):
        _fail("METADATA_DUPLICATE", root / "metadata.jsonl")
    expected_by_id = {sample.sample_id: sample for sample in expected}
    if set(by_id) != set(expected_by_id):
        _fail("METADATA_SET_MISMATCH", root / "metadata.jsonl")

    group_splits: dict[str, str] = {}
    split_counts = {split: 0 for split in _SPLITS}
    asset_counts = {asset_id: 0 for asset_id in config.meter_asset_ids}
    for sample_id in sorted(expected_by_id):
        sample = expected_by_id[sample_id]
        row = by_id[sample_id]
        for path_field in ("image_path", "label_path"):
            _safe_relative(str(row.get(path_field, "")))
        if row.get("image_path") != sample.image_path or row.get("label_path") != sample.label_path:
            _fail("METADATA_PLAN_MISMATCH", sample_id)
        if row.get("split") != sample.split or row.get("asset_id") != sample.asset_id:
            _fail("METADATA_PLAN_MISMATCH", sample_id)
        if row.get("scene_group_id") != sample.scene_group_id:
            _fail("METADATA_PLAN_MISMATCH", sample_id)
        owner = group_splits.setdefault(sample.scene_group_id, sample.split)
        if owner != sample.split:
            _fail("SCENE_GROUP_SPLIT_CROSSING", sample.scene_group_id)
        meter = config.meters[sample.asset_id]
        try:
            minimum = float(row.get("range_minimum"))
            maximum = float(row.get("range_maximum"))
        except (TypeError, ValueError):
            _fail("METADATA_METER_MISMATCH", sample_id)
        if (
            row.get("sensor_id") != meter.sensor_id
            or row.get("unit") != meter.unit
            or minimum != meter.minimum
            or maximum != meter.maximum
        ):
            _fail("METADATA_METER_MISMATCH", sample_id)
        reading = _check_metadata_number(row.get("reading"), "reading", sample_id)
        normalized = _check_metadata_number(row.get("normalized_reading"), "normalized_reading", sample_id)
        if not (meter.minimum <= reading <= meter.maximum) or not (0.0 <= normalized <= 1.0):
            _fail("METADATA_READING_INVALID", sample_id)
        if abs(reading - sample.reading) > 1e-6 or abs(normalized - sample.normalized_reading) > 1e-6:
            _fail("METADATA_PLAN_MISMATCH", sample_id)
        label = _read_label(root / sample.label_path, config.width, config.height)
        recorded_label = row.get("bbox_yolo")
        if not isinstance(recorded_label, list) or len(recorded_label) != 4:
            _fail("METADATA_LABEL_MISMATCH", sample_id)
        try:
            if any(abs(float(value) - label[index]) > 1e-6 for index, value in enumerate(recorded_label)):
                _fail("METADATA_LABEL_MISMATCH", sample_id)
        except (TypeError, ValueError):
            _fail("METADATA_LABEL_MISMATCH", sample_id)
        for field in ("distance_m", "yaw_radians", "pitch_radians", "roll_radians", "needle_angle_radians"):
            _check_metadata_number(row.get(field), field, sample_id)
        split_counts[sample.split] += 1
        asset_counts[sample.asset_id] += 1

    result_path = root / "generation-result.json"
    if not result_path.is_file():
        _fail("GENERATION_RESULT_MISSING", result_path)
    try:
        result = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        _fail("GENERATION_RESULT_INVALID", error)
    if (
        result.get("status") != "accepted"
        or result.get("sample_mode") != sample_mode
        or result.get("expected_count") != len(expected)
        or result.get("accepted_count") != len(expected)
        or result.get("failure")
    ):
        _fail("GENERATION_RESULT_INVALID", result_path)
    return DatasetSummary(
        total_images=len(expected),
        split_counts=split_counts,
        asset_counts=asset_counts,
        file_manifest_sha256="",
        metadata_sha256=_sha256(root / "metadata.jsonl"),
    )


def _collected_paths(root: Path, excluded_names: set[str]) -> list[Path]:
    paths: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        _safe_relative(relative)
        if PurePosixPath(relative).name in excluded_names:
            continue
        paths.append(path)
    return sorted(paths, key=lambda path: path.relative_to(root).as_posix())


def write_file_manifest(root: Path, included_paths: Sequence[Path]) -> str:
    root = Path(root)
    entries: list[str] = []
    seen: set[str] = set()
    for path in included_paths:
        relative = path.relative_to(root).as_posix()
        _safe_relative(relative)
        if relative in seen:
            _fail("MANIFEST_DUPLICATE", relative)
        seen.add(relative)
        entries.append(f"{_sha256(path)}\t{path.stat().st_size}\t{relative}")
    entries.sort(key=lambda line: line.split("\t", 2)[2])
    payload = ("\n".join(entries) + "\n").encode("utf-8") if entries else b""
    (root / "file-manifest.tsv").write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def write_dataset_manifest(
    root: Path, summary: DatasetSummary, provenance: Mapping[str, object]
) -> Path:
    payload: dict[str, object] = {
        "schema_version": 1,
        "status": "accepted",
        "dataset_id": "gazebo-meter-locator-v1",
        "total_images": summary.total_images,
        "split_counts": dict(summary.split_counts),
        "asset_counts": dict(summary.asset_counts),
        "file_manifest_sha256": summary.file_manifest_sha256,
        "metadata_sha256": summary.metadata_sha256,
        **dict(provenance),
    }
    path = root / "dataset-manifest.yaml"
    path.write_text(yaml.safe_dump(payload, sort_keys=True), encoding="utf-8")
    return path


def _write_support_files(root: Path, config: GenerationConfig) -> None:
    data = {
        "path": ".",
        "train": "images/train",
        "val": "images/val",
        "test": "images/test",
        "nc": 1,
        "names": {0: "meter"},
    }
    (root / "data.yaml").write_text(
        yaml.safe_dump(data, sort_keys=False), encoding="utf-8"
    )
    generation = {
        "schema_version": config.schema_version,
        "dataset_id": config.dataset_id,
        "scenario_id": config.scenario_id,
        "global_seed": config.global_seed,
        "image": {
            "width": config.width,
            "height": config.height,
            "format": config.image_format,
        },
        "class_names": {0: "meter"},
        "frames_per_group": config.frames_per_group,
        "groups_per_meter": dict(config.groups_per_meter),
        "meter_asset_ids": list(config.meter_asset_ids),
    }
    (root / "generation-config.yaml").write_text(
        yaml.safe_dump(generation, sort_keys=False), encoding="utf-8"
    )
    readme_lines = [
        "# gazebo-meter-locator-v1",
        "",
        "This archive contains project-owned Gazebo-derived meter locator data.",
        "The only YOLO class is `0: meter`; ranges and units remain in the project registry.",
        "",
        "```bash",
        "unzip gazebo-meter-locator-v1.zip",
        "cd gazebo-meter-locator-v1",
        "sha256sum -c SHA256SUMS",
        "yolo detect train data=data.yaml model=yolo11n.pt imgsz=640 epochs=100 batch=8 device=0 workers=6 seed=42 patience=20",
        "```",
        "",
    ]
    (root / "README-AutoDL.md").write_text(
        "\n".join(readme_lines), encoding="utf-8"
    )


def _write_sha256sums(root: Path) -> None:
    paths = _collected_paths(root, {"SHA256SUMS", "generation-result.json"})
    lines = [
        f"{_sha256(path)}  {path.relative_to(root).as_posix()}" for path in paths
    ]
    (root / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")


def create_deterministic_zip(dataset_root: Path, output_path: Path) -> tuple[str, int]:
    dataset_root = Path(dataset_root)
    if not dataset_root.is_absolute() or not dataset_root.is_dir():
        _fail("OUTPUT_DIRECTORY_INVALID", dataset_root)
    paths = _collected_paths(dataset_root, {"SHA256SUMS", "generation-result.json"})
    checksum_path = dataset_root / "SHA256SUMS"
    if checksum_path.is_file():
        paths.append(checksum_path)
        paths.sort(key=lambda path: path.relative_to(dataset_root).as_posix())
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        output_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
    ) as archive:
        for path in paths:
            relative = path.relative_to(dataset_root).as_posix()
            info = zipfile.ZipInfo(f"{dataset_root.name}/{relative}")
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(
                info,
                path.read_bytes(),
                compress_type=zipfile.ZIP_DEFLATED,
                compresslevel=6,
            )
    return _sha256(output_path), output_path.stat().st_size


def package_generated_dataset(
    root: Path,
    config: GenerationConfig,
    sample_mode: str,
    provenance: Mapping[str, object],
    zip_output: Path,
) -> DatasetSummary:
    summary = validate_generated_dataset(root, config, sample_mode)
    _write_support_files(root, config)
    manifest_hash = write_file_manifest(root, _collected_paths(root, _PAYLOAD_EXCLUDES))
    summary = DatasetSummary(
        summary.total_images,
        summary.split_counts,
        summary.asset_counts,
        manifest_hash,
        summary.metadata_sha256,
    )
    write_dataset_manifest(root, summary, provenance)
    _write_sha256sums(root)
    zip_hash, zip_size = create_deterministic_zip(root, zip_output)
    return DatasetSummary(
        summary.total_images,
        summary.split_counts,
        summary.asset_counts,
        manifest_hash,
        summary.metadata_sha256,
        zip_hash,
        zip_size,
    )


def _repo_root() -> Path:
    output = subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"], text=True
    ).strip()
    return Path(output)


def _identity(
    config_path: Path, sample_mode: str, registry_path: Path | None = None
) -> str:
    repo = _repo_root()
    registry_path = registry_path or repo / "configs/devices.yaml"
    config = load_generation_config(config_path, registry_path)
    samples = _expected_samples(config, sample_mode)
    seed_payload = "\n".join(f"{sample.sample_id}:{sample.seed}" for sample in samples)
    files = [
        config_path,
        registry_path,
        repo / "ros2_ws/src/substation_gazebo/worlds/meter_dataset_world.sdf",
        repo / "ros2_ws/src/substation_gazebo/models/synthetic_meter/model.sdf",
    ]
    material = {
        "commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        "mode": sample_mode,
        "files": {str(path.relative_to(repo)): _sha256(path) for path in files},
        "seed_plan_sha256": hashlib.sha256(seed_payload.encode()).hexdigest(),
        "python": os.sys.version.split()[0],
        "ros_distro": os.environ.get("ROS_DISTRO", "jazzy"),
    }
    canonical = json.dumps(material, sort_keys=True, separators=(",", ":")) + "\n"
    return hashlib.sha256(canonical.encode()).hexdigest()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="meter_dataset_package")
    subparsers = parser.add_subparsers(dest="command", required=True)
    identity = subparsers.add_parser("identity")
    identity.add_argument("--config", type=Path, required=True)
    identity.add_argument("--registry", type=Path)
    identity.add_argument("--mode", choices=("smoke", "full"), required=True)
    package = subparsers.add_parser("package")
    package.add_argument("--dataset-root", type=Path, required=True)
    package.add_argument("--config", type=Path, required=True)
    package.add_argument("--registry", type=Path, required=True)
    package.add_argument("--mode", choices=("smoke", "full"), required=True)
    package.add_argument("--zip-output", type=Path, required=True)
    package.add_argument("--provenance-json", type=Path)
    args = parser.parse_args(argv)
    if args.command == "identity":
        registry = args.registry.resolve() if args.registry else None
        print(_identity(args.config.resolve(), args.mode, registry))
        return
    config = load_generation_config(args.config.resolve(), args.registry.resolve())
    provenance = {}
    if args.provenance_json:
        provenance = json.loads(args.provenance_json.read_text(encoding="utf-8"))
    summary = package_generated_dataset(
        args.dataset_root.resolve(),
        config,
        args.mode,
        provenance,
        args.zip_output.resolve(),
    )
    print(json.dumps(asdict(summary), sort_keys=True))
    print("meter-dataset-package: PASS")


if __name__ == "__main__":
    main()
