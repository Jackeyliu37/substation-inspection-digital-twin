#!/usr/bin/env python3
"""Verify the checked-in Phase 4 model manifest and archive identities."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import re
import sys


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-manifest", type=Path, required=True)
    parser.add_argument("--model-manifest", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--model-root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    try:
        import yaml
        dataset = yaml.safe_load(args.dataset_manifest.read_text(encoding="utf-8"))
        model = yaml.safe_load(args.model_manifest.read_text(encoding="utf-8"))
        if not isinstance(dataset, dict) or dataset.get("schema_version") != 1:
            raise ValueError("DATASET_MANIFEST_INVALID")
        if not isinstance(model, dict) or model.get("schema_version") != 1:
            raise ValueError("MODEL_MANIFEST_INVALID")
        archive = Path(str(model["source_bundle"]["path"]))
        if not archive.is_file() or _sha256(archive) != model["source_bundle"]["sha256"]:
            raise ValueError("MODEL_ARCHIVE_HASH_MISMATCH")
        artifacts = model.get("artifacts")
        required = set(model.get("required_logical_models", []))
        if not isinstance(artifacts, list) or {item.get("logical_model") for item in artifacts} != required:
            raise ValueError("MODEL_ARTIFACT_SET_INVALID")
        for item in artifacts:
            if not re.fullmatch(r"[0-9a-f]{64}", str(item.get("sha256", ""))):
                raise ValueError("MODEL_SHA256_INVALID")
            if item.get("acceptance_status") != "passed":
                raise ValueError("MODEL_NOT_ACCEPTED")
        result = {"status": "passed", "model_manifest": str(args.model_manifest), "dataset_manifest": str(args.dataset_manifest)}
        args.report.parent.mkdir(parents=True, exist_ok=True)
        import json
        args.report.write_text(json.dumps(result, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    except (OSError, KeyError, TypeError, ValueError, ImportError) as exc:
        print(f"data-model-verification: FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"data-model-verification: PASS: {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
