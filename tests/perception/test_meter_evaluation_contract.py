from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import cv2
import numpy as np


ROOT = Path(__file__).parents[2]
SCRIPT = ROOT / "scripts/evaluate_meter_reader.py"
SPEC = importlib.util.spec_from_file_location("evaluate_meter_reader", SCRIPT)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


def test_evaluation_reports_frozen_sample_errors_and_groups(tmp_path: Path) -> None:
    image_dir = tmp_path / "images/test"
    image_dir.mkdir(parents=True)
    image = np.full((101, 101, 3), 220, dtype=np.uint8)
    cv2.line(image, (50, 50), (88, 50), (0, 0, 255), 4)
    cv2.imwrite(str(image_dir / "one.png"), image)
    record = {
        "asset_id": "meter-pressure-01",
        "sensor_id": "meter-pressure-sensor-01",
        "image_path": "images/test/one.png",
        "split": "test",
        "bbox_pixels": {"x_min": 0, "y_min": 0, "x_max": 101, "y_max": 101},
        "reading": 1.0,
        "unit": "MPa",
        "light_family": "bright",
        "scene_group_id": "view-1",
        "blur_sigma": 0.0,
        "occlusion_regime": "none",
    }
    metadata = tmp_path / "metadata.jsonl"
    metadata.write_text(json.dumps(record) + "\n", encoding="utf-8")

    report = module.evaluate_dataset(tmp_path, metadata)

    assert report["schema_version"] == 1
    assert report["sample_count"] == 1
    assert report["valid_count"] == 1
    assert report["valid_rate"] == 1.0
    assert report["absolute_error"]["mean"] < 0.05
    assert report["groups"]["asset_id"]["meter-pressure-01"]["count"] == 1
    assert report["groups"]["light_family"]["bright"]["count"] == 1
    assert report["groups"]["viewpoint"]["view-1"]["count"] == 1
    assert report["groups"]["blur_sigma"]["0.0"]["count"] == 1
    assert report["groups"]["occlusion_regime"]["none"]["count"] == 1
