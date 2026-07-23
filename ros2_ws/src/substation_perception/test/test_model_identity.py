from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from substation_perception.model_identity import (
    ModelIdentityError,
    verify_development_placeholder,
)


def _arguments(weights: Path) -> dict[str, object]:
    payload = weights.read_bytes()
    return {
        "path": weights,
        "expected_path": weights,
        "expected_sha256": hashlib.sha256(payload).hexdigest(),
        "expected_size_bytes": len(payload),
        "runtime_mode": "development_placeholder",
        "logical_model": "yolo11n_base",
        "production_ready": False,
    }


def test_accepts_exact_placeholder_identity(tmp_path: Path) -> None:
    weights = tmp_path / "yolo11n.pt"
    weights.write_bytes(b"locked")

    verified = verify_development_placeholder(**_arguments(weights))

    assert verified.path == weights.resolve()
    assert verified.sha256 == hashlib.sha256(b"locked").hexdigest()
    assert verified.size_bytes == 6


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("runtime_mode", "production"),
        ("logical_model", "yolo11n_safety"),
        ("production_ready", True),
    ],
)
def test_rejects_non_placeholder_runtime_identity(
    tmp_path: Path, field: str, value: object
) -> None:
    weights = tmp_path / "yolo11n.pt"
    weights.write_bytes(b"locked")
    arguments = _arguments(weights)
    arguments[field] = value

    with pytest.raises(ModelIdentityError, match="PLACEHOLDER_IDENTITY_INVALID"):
        verify_development_placeholder(**arguments)


def test_rejects_missing_model(tmp_path: Path) -> None:
    missing = tmp_path / "yolo11n.pt"
    arguments = {
        "path": missing,
        "expected_path": missing,
        "expected_sha256": "0" * 64,
        "expected_size_bytes": 1,
        "runtime_mode": "development_placeholder",
        "logical_model": "yolo11n_base",
        "production_ready": False,
    }

    with pytest.raises(ModelIdentityError, match="MODEL_PATH_INVALID"):
        verify_development_placeholder(**arguments)


def test_rejects_unexpected_resolved_path(tmp_path: Path) -> None:
    weights = tmp_path / "yolo11n.pt"
    other = tmp_path / "other.pt"
    weights.write_bytes(b"locked")
    other.write_bytes(b"locked")
    arguments = _arguments(weights)
    arguments["expected_path"] = other

    with pytest.raises(ModelIdentityError, match="MODEL_PATH_INVALID"):
        verify_development_placeholder(**arguments)


def test_rejects_non_pt_file(tmp_path: Path) -> None:
    weights = tmp_path / "yolo11n.bin"
    weights.write_bytes(b"locked")

    with pytest.raises(ModelIdentityError, match="MODEL_PATH_INVALID"):
        verify_development_placeholder(**_arguments(weights))


def test_rejects_wrong_size_before_hashing(tmp_path: Path) -> None:
    weights = tmp_path / "yolo11n.pt"
    weights.write_bytes(b"locked")
    arguments = _arguments(weights)
    arguments["expected_size_bytes"] = 7

    with pytest.raises(ModelIdentityError, match="MODEL_SIZE_MISMATCH"):
        verify_development_placeholder(**arguments)


def test_rejects_wrong_digest(tmp_path: Path) -> None:
    weights = tmp_path / "yolo11n.pt"
    weights.write_bytes(b"locked")
    arguments = _arguments(weights)
    arguments["expected_sha256"] = "0" * 64

    with pytest.raises(ModelIdentityError, match="MODEL_SHA256_MISMATCH"):
        verify_development_placeholder(**arguments)
