from __future__ import annotations

import math
import uuid

import cv2
import numpy as np
import pytest
from std_msgs.msg import Header

from substation_perception.meter_reader import (
    MeterCalibration,
    make_meter_reading,
    read_meter_crop,
)


def _dial(angle: float) -> np.ndarray:
    image = np.full((101, 101, 3), 220, dtype=np.uint8)
    center = (50, 50)
    end = (
        int(round(center[0] + 38 * math.cos(angle))),
        int(round(center[1] + 38 * math.sin(angle))),
    )
    cv2.line(image, center, end, (255, 0, 0), 4)
    cv2.circle(image, center, 4, (40, 40, 40), -1)
    return image


def test_red_needle_angle_maps_to_configured_reading() -> None:
    calibration = MeterCalibration(
        asset_id="meter-pressure-01",
        sensor_id="meter-pressure-sensor-01",
        minimum=0.0,
        maximum=2.0,
        unit="MPa",
        start_angle_radians=-3.0 * math.pi / 4.0,
        end_angle_radians=3.0 * math.pi / 4.0,
    )

    result = read_meter_crop(_dial(0.0), calibration)

    assert result.valid is True
    assert result.reading == pytest.approx(1.0, abs=0.04)
    assert result.confidence_0_1 > 0.8


def test_missing_red_needle_is_invalid() -> None:
    calibration = MeterCalibration("meter-oil-01", "sensor", 0, 100, "percent")
    result = read_meter_crop(np.zeros((50, 50, 3), dtype=np.uint8), calibration)
    assert result.valid is False
    assert result.error_code == "NEEDLE_NOT_FOUND"


def test_meter_diagnostic_has_exact_contract_fields() -> None:
    calibration = MeterCalibration("meter-oil-01", "meter-oil-sensor-01", 0, 100, "percent")
    result = read_meter_crop(_dial(-3.0 * math.pi / 4.0), calibration)
    header = Header(frame_id="camera_optical_frame")
    output = make_meter_reading(
        header,
        run_id="run-1",
        calibration=calibration,
        result=result,
        evidence_id=uuid.UUID("11111111-1111-4111-8111-111111111111"),
    )

    assert output.header == header
    assert len(output.status) == 1
    status = output.status[0]
    assert status.name == "meter-oil-01"
    assert status.hardware_id == "meter-oil-sensor-01"
    assert {item.key for item in status.values} == {
        "run_id", "reading", "unit", "confidence_0_1", "valid", "evidence_id"
    }
    values = {item.key: item.value for item in status.values}
    assert values["reading"] == "0"
    assert values["unit"] == "percent"
    assert values["valid"] == "true"
