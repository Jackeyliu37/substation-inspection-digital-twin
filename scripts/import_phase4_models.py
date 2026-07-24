#!/usr/bin/env python3
"""Validate and optionally promote the four user-trained Phase 4 artifacts.

The importer never downloads data or models.  A promotion is immutable and is
only allowed after all four model identities and the recorded metrics pass.  A
threshold waiver can be recorded explicitly by the operator when project time
constraints require accepting a known metric exception.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
from typing import Any, Callable
import zipfile


class ImportError(RuntimeError):
    pass


EXPECTED: dict[str, dict[str, Any]] = {
    "yolo11n_safety": {
        "folder": "yolo11n_safety",
        "module": "safety",
        "task": "detect",
        "classes": ["person", "no_hardhat", "hardhat", "fire", "smoke"],
        "metric": "metrics/mAP50(B)",
        "threshold": 0.75,
        "deployment_filename": "yolo11n_safety.pt",
    },
    "yolo11n_equipment": {
        "folder": "yolo11n_equipment",
        "module": "equipment",
        "task": "detect",
        "classes": [
            "open_blade_disconnect_switch", "closed_blade_disconnect_switch",
            "open_tandem_disconnect_switch", "closed_tandem_disconnect_switch",
            "breaker", "fuse_disconnect_switch", "glass_disc_insulator",
            "porcelain_pin_insulator", "muffle", "lightning_arrester",
            "recloser", "power_transformer", "current_transformer",
            "potential_transformer", "tripolar_disconnect_switch",
        ],
        "metric": "metrics/mAP50(B)",
        "threshold": 0.75,
        "deployment_filename": "yolo11n_equipment.pt",
    },
    "yolo11n_fault": {
        "folder": "yolo11n_fault",
        "module": "fault",
        "task": "classify",
        "classes": ["0_normal", "1_corrosion", "2_broken_component", "3_bird_nest"],
        "metric": "metrics/accuracy_top1",
        "threshold": None,
        "deployment_filename": "yolo11n_fault.pt",
    },
    "meter_locator": {
        "folder": "yolo11n_meter_locator",
        "module": "meter",
        "task": "detect",
        "classes": ["meter"],
        "metric": "metrics/mAP50(B)",
        "threshold": None,
        "deployment_filename": "yolo11n_meter.pt",
    },
}


@dataclass(frozen=True)
class _ModelView:
    task: str
    names: dict[int, str]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_member(name: str) -> None:
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ImportError("ARCHIVE_PATH_INVALID")
    if "\\" in name:
        raise ImportError("ARCHIVE_PATH_INVALID")


def _task_from_args(path: Path) -> str:
    match = re.search(r"^task:\s*([^#\s]+)", path.read_text(encoding="utf-8"), re.MULTILINE)
    if match is None:
        raise ImportError("TRAINING_CONFIG_INVALID")
    return match.group(1)


def _metrics(path: Path, metric: str) -> tuple[float, int]:
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    values: list[float] = []
    for row in rows:
        value = row.get(metric, "")
        if value in (None, ""):
            continue
        try:
            parsed = float(value)
        except ValueError as exc:
            raise ImportError("METRICS_INVALID") from exc
        if parsed != parsed or parsed in (float("inf"), float("-inf")):
            raise ImportError("METRICS_INVALID")
        values.append(parsed)
    if not values:
        raise ImportError("METRIC_MISSING")
    best = max(values)
    return best, len(rows)


def _default_loader(path: str) -> _ModelView:
    try:
        from ultralytics import YOLO
        model = YOLO(path)
    except Exception as exc:  # pragma: no cover - exercised on host import
        raise ImportError("MODEL_LOAD_FAILED") from exc
    names = getattr(model, "names", None)
    if isinstance(names, dict):
        normalized = {int(key): str(value) for key, value in names.items()}
    elif isinstance(names, list):
        normalized = {index: str(value) for index, value in enumerate(names)}
    else:
        raise ImportError("MODEL_NAMES_INVALID")
    return _ModelView(str(getattr(model, "task", "")), normalized)


def inspect_archive(
    archive: Path,
    *,
    model_loader: Callable[[str], Any] | None = None,
    accept_threshold_waiver: bool = False,
) -> dict[str, Any]:
    archive = archive.resolve(strict=True)
    if archive.suffix.lower() != ".zip":
        raise ImportError("ARCHIVE_TYPE_INVALID")
    archive_sha256 = _sha256(archive)
    loader = model_loader or _default_loader
    with tempfile.TemporaryDirectory(prefix="phase4-import-") as temporary:
        root = Path(temporary)
        with zipfile.ZipFile(archive) as payload:
            for member in payload.infolist():
                _safe_member(member.filename)
            payload.extractall(root)
        candidates = list(root.rglob("weights/best.pt"))
        artifacts: dict[str, dict[str, Any]] = {}
        for logical_model, spec in EXPECTED.items():
            matches = [path for path in candidates if path.parent.parent.name == spec["folder"]]
            if len(matches) != 1:
                raise ImportError(f"ARTIFACT_MISSING:{logical_model}")
            weight = matches[0]
            run_dir = weight.parent.parent
            args = run_dir / "args.yaml"
            results = run_dir / "results.csv"
            if not args.is_file() or not results.is_file():
                raise ImportError(f"TRAINING_EVIDENCE_MISSING:{logical_model}")
            task = _task_from_args(args)
            if task != spec["task"]:
                raise ImportError(f"MODEL_TASK_INVALID:{logical_model}")
            view = loader(str(weight))
            names = getattr(view, "names", None)
            actual_task = str(getattr(view, "task", ""))
            if actual_task != spec["task"] or names is None:
                raise ImportError(f"MODEL_IDENTITY_INVALID:{logical_model}")
            ordered_names = [str(names[index]) for index in sorted(names)]
            if ordered_names != spec["classes"]:
                raise ImportError(f"MODEL_CLASSES_INVALID:{logical_model}")
            best_metric, epochs = _metrics(results, spec["metric"])
            threshold = spec["threshold"]
            threshold_passed = threshold is None or best_metric >= threshold
            waived = bool(accept_threshold_waiver and not threshold_passed)
            status = "passed" if threshold_passed or waived else "rejected"
            weight_sha256 = _sha256(weight)
            artifacts[logical_model] = {
                "logical_model": logical_model,
                "module": spec["module"],
                "filename": spec["deployment_filename"],
                "source_path": str(weight.relative_to(root)).replace("\\", "/"),
                "sha256": weight_sha256,
                "size_bytes": weight.stat().st_size,
                "task": task,
                "class_names": ordered_names,
                "metric_name": spec["metric"],
                "best_metric": best_metric,
                "epochs": epochs,
                "threshold": threshold,
                "threshold_passed": threshold_passed,
                "threshold_waived": waived,
                "acceptance_status": status,
                "metrics_sha256": _sha256(results),
                "training_config_sha256": _sha256(args),
            }
    ready = all(item["acceptance_status"] == "passed" for item in artifacts.values())
    return {
        "schema_version": 1,
        "archive": {
            "path": str(archive),
            "sha256": archive_sha256,
            "size_bytes": archive.stat().st_size,
        },
        "artifacts": artifacts,
        "production_ready": ready,
        "threshold_waiver": {
            "accepted": bool(accept_threshold_waiver),
            "reason": "operator-approved Phase 4 time-box exception" if accept_threshold_waiver else "",
        },
    }


def _promote(archive: Path, report: dict[str, Any], destination: Path) -> None:
    if not report["production_ready"]:
        raise ImportError("PRODUCTION_GATE_FAILED")
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as payload:
        for logical_model, item in report["artifacts"].items():
            target_dir = destination / item["sha256"]
            target_dir.mkdir(parents=True, exist_ok=True)
            source = item["source_path"]
            member = payload.getinfo("substation_yolo_runs/" + source.split("substation_yolo_runs/", 1)[-1])
            target = target_dir / item["filename"]
            with payload.open(member) as source_stream, target.open("wb") as target_stream:
                shutil.copyfileobj(source_stream, target_stream)
            if _sha256(target) != item["sha256"]:
                raise ImportError(f"PROMOTION_HASH_MISMATCH:{logical_model}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--promote-root", type=Path)
    parser.add_argument("--accept-threshold-waiver", action="store_true")
    args = parser.parse_args()
    try:
        report = inspect_archive(
            args.archive,
            accept_threshold_waiver=args.accept_threshold_waiver,
        )
        if args.promote_root is not None:
            _promote(args.archive, report, args.promote_root)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    except (ImportError, OSError, zipfile.BadZipFile) as exc:
        print(f"phase4-import: FAIL: {exc}")
        return 1
    print(f"phase4-import: {'PASS' if report['production_ready'] else 'BLOCKED'}: {args.report}")
    return 0 if report["production_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
