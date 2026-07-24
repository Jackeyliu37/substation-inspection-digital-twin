# Phase 4 model handoff

The user-provided training bundle is recorded at
`artifacts/phase4/substation_yolo_runs.zip`. Its SHA-256 is recorded in
`manifest.yaml` and `artifacts/phase4/model-import-report.json`.

The four best weights were verified for task and class identity and promoted
outside Git to `/var/lib/substation/models/production/<sha256>/`. The archive
contains training arguments, `results.csv`, plots, and both `best.pt` and
`last.pt` for each run.

The safety run reached best `mAP50=0.69297`, below the documented `0.75`
threshold. The manifest records the explicit operator-approved time-box waiver
instead of hiding this exception. This is a local handoff, not an immutable
GitHub release; a future strict acceptance can replace the production mapping
without modifying the archived bundle.
