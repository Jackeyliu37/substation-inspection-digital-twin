from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path


class ModelIdentityError(RuntimeError):
    """Raised when a model file cannot be used by the placeholder runtime."""


@dataclass(frozen=True)
class VerifiedModel:
    path: Path
    sha256: str
    size_bytes: int


def verify_development_placeholder(
    path: Path,
    expected_path: Path,
    expected_sha256: str,
    expected_size_bytes: int,
    runtime_mode: str,
    logical_model: str,
    production_ready: bool,
) -> VerifiedModel:
    """Return a verified official base weight for development use only."""
    if (runtime_mode, logical_model, production_ready) != (
        "development_placeholder",
        "yolo11n_base",
        False,
    ):
        raise ModelIdentityError("PLACEHOLDER_IDENTITY_INVALID")

    try:
        resolved_path = Path(path).resolve(strict=True)
        resolved_expected_path = Path(expected_path).resolve(strict=True)
    except (OSError, ValueError) as error:
        raise ModelIdentityError("MODEL_PATH_INVALID") from error

    if resolved_path != resolved_expected_path or resolved_path.suffix != ".pt":
        raise ModelIdentityError("MODEL_PATH_INVALID")

    size_bytes = resolved_path.stat().st_size
    if size_bytes != expected_size_bytes:
        raise ModelIdentityError("MODEL_SIZE_MISMATCH")

    with resolved_path.open("rb") as stream:
        sha256 = hashlib.file_digest(stream, "sha256").hexdigest()
    if sha256 != expected_sha256:
        raise ModelIdentityError("MODEL_SHA256_MISMATCH")

    return VerifiedModel(path=resolved_path, sha256=sha256, size_bytes=size_bytes)
