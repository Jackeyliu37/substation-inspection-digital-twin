# Uploaded Phase 4 training results

`substation_yolo_runs.zip` is the four-model bundle copied from the user's
machine. It is intentionally retained as the exact handoff archive so the
weights, training arguments, metrics CSVs, plots, and `best.pt`/`last.pt` pairs
remain available for audit.

- archive SHA-256: `fae3721cbe65b9fa09f24972ab36a5c45df54d0a9f97fa7e9d5cb87e619235ce`
- archive size: `83,036,921` bytes
- import command: `scripts/import_phase4_models.py`
- report: `model-import-report.json`
- production copies: `/var/lib/substation/models/production/<sha256>/`

The import used the explicitly requested operator waiver for safety mAP50.
The measured best values are safety `0.69297`, equipment `0.84187`, fault
top-1 `0.99673`, and meter locator mAP50 `0.99500`.
