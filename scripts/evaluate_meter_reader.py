#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ros2_ws/src/substation_perception"))

from substation_perception.meter_reader import (  # noqa: E402
    load_meter_calibrations,
    read_meter_crop,
)


def _stats(records: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [item for item in records if item["valid"]]
    errors = np.asarray([item["absolute_error"] for item in valid], dtype=float)
    return {
        "count": len(records),
        "valid_count": len(valid),
        "valid_rate": len(valid) / len(records) if records else 0.0,
        "mean_absolute_error": float(np.mean(errors)) if len(errors) else None,
        "p95_absolute_error": float(np.percentile(errors, 95)) if len(errors) else None,
    }


def evaluate_dataset(dataset_root: Path, metadata_path: Path) -> dict[str, Any]:
    calibrations = load_meter_calibrations(ROOT / "configs/meter_reader.yaml")
    samples: list[dict[str, Any]] = []
    group_fields = {
        "asset_id": "asset_id",
        "light_family": "light_family",
        "viewpoint": "scene_group_id",
        "blur_sigma": "blur_sigma",
        "occlusion_regime": "occlusion_regime",
    }
    groups: dict[str, dict[str, list[dict[str, Any]]]] = {
        output: {} for output in group_fields
    }
    for line in metadata_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        source = json.loads(line)
        if source.get("split") != "test":
            continue
        calibration = calibrations[source["asset_id"]]
        image_path = dataset_root / source["image_path"]
        bgr = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if bgr is None:
            raise RuntimeError(f"IMAGE_UNREADABLE:{source['image_path']}")
        image = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        box = source["bbox_pixels"]
        x1 = max(0, int(np.floor(float(box["x_min"]))))
        y1 = max(0, int(np.floor(float(box["y_min"]))))
        x2 = min(image.shape[1], int(np.ceil(float(box["x_max"]))))
        y2 = min(image.shape[0], int(np.ceil(float(box["y_max"]))))
        result = read_meter_crop(image[y1:y2, x1:x2], calibration)
        expected = float(source["reading"])
        sample = {
            "image_path": source["image_path"],
            "asset_id": source["asset_id"],
            "expected": expected,
            "observed": result.reading if result.valid else None,
            "unit": source["unit"],
            "valid": result.valid,
            "confidence_0_1": result.confidence_0_1,
            "absolute_error": abs(result.reading - expected) if result.valid else None,
            "error_code": result.error_code,
        }
        samples.append(sample)
        for output_name, source_name in group_fields.items():
            key = str(source[source_name])
            groups[output_name].setdefault(key, []).append(sample)
    summary = _stats(samples)
    return {
        "schema_version": 1,
        "method": "hsv-red-needle-vector-v1",
        "dataset_root": str(dataset_root),
        "metadata_path": str(metadata_path),
        "sample_count": summary["count"],
        "valid_count": summary["valid_count"],
        "valid_rate": summary["valid_rate"],
        "absolute_error": {
            "mean": summary["mean_absolute_error"],
            "p95": summary["p95_absolute_error"],
        },
        "groups": {
            name: {key: _stats(values) for key, values in sorted(items.items())}
            for name, items in groups.items()
        },
        "samples": samples,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", required=True, type=Path)
    parser.add_argument("--metadata", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = evaluate_dataset(args.dataset_root.resolve(), args.metadata.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_name(f".{args.output.name}.tmp-{os.getpid()}")
    temporary.write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, args.output)
    print(
        f"meter-evaluation: samples={report['sample_count']} "
        f"valid_rate={report['valid_rate']:.6f} "
        f"mae={report['absolute_error']['mean']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
