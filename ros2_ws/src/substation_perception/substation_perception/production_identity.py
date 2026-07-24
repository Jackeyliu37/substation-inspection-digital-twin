from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Any

import yaml


class ProductionIdentityError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProductionModel:
    logical_model: str
    module: str
    path: Path
    sha256: str
    size_bytes: int
    task: str
    class_names: tuple[str, ...]
    threshold_waived: bool


def _digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load_production_models(
    manifest_path: Path, production_root: Path
) -> dict[str, ProductionModel]:
    try:
        document = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise ProductionIdentityError("MODEL_MANIFEST_INVALID") from error
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        raise ProductionIdentityError("MODEL_MANIFEST_INVALID")
    artifacts = document.get("artifacts")
    production = document.get("production_artifact_sha256")
    filenames = document.get("deployment_filenames")
    if not isinstance(artifacts, list) or not isinstance(production, dict) or not isinstance(filenames, dict):
        raise ProductionIdentityError("MODEL_MANIFEST_INVALID")

    loaded: dict[str, ProductionModel] = {}
    root = production_root.resolve()
    for raw in artifacts:
        if not isinstance(raw, dict) or raw.get("acceptance_status") != "passed":
            raise ProductionIdentityError("MODEL_NOT_ACCEPTED")
        logical = raw.get("logical_model")
        sha256 = raw.get("sha256")
        size_bytes = raw.get("size_bytes")
        if (
            not isinstance(logical, str)
            or not isinstance(sha256, str)
            or len(sha256) != 64
            or production.get(logical) != sha256
            or not isinstance(size_bytes, int)
            or size_bytes <= 0
            or not isinstance(filenames.get(logical), str)
        ):
            raise ProductionIdentityError("MODEL_MANIFEST_INVALID")
        path = (root / sha256 / filenames[logical]).resolve()
        if root not in path.parents or not path.is_file() or path.suffix != ".pt":
            raise ProductionIdentityError("MODEL_PATH_INVALID")
        actual_size = path.stat().st_size
        if actual_size != size_bytes:
            raise ProductionIdentityError("MODEL_SIZE_MISMATCH")
        if _digest(path) != sha256:
            raise ProductionIdentityError("MODEL_SHA256_MISMATCH")
        class_names = raw.get("class_names")
        if not isinstance(class_names, list) or not all(isinstance(item, str) and item for item in class_names):
            raise ProductionIdentityError("MODEL_CLASSES_INVALID")
        loaded[logical] = ProductionModel(
            logical_model=logical,
            module=str(raw.get("module", "")),
            path=path,
            sha256=sha256,
            size_bytes=size_bytes,
            task=str(raw.get("task", "")),
            class_names=tuple(class_names),
            threshold_waived=bool(raw.get("threshold_waived", False)),
        )
    if set(loaded) != set(production):
        raise ProductionIdentityError("MODEL_SET_INVALID")
    return loaded
