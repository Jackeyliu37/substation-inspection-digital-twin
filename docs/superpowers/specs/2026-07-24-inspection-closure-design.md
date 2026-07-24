# Inspection Closure Design

## Goal

Make one autonomous inspection run visibly and truthfully complete the full business loop: navigate to every asset, settle each task immediately, publish an evaluated risk for that asset, expose meaningful live telemetry and events, and generate one report when the mission reaches a terminal state.

## Design

The existing ROS interfaces remain unchanged. `ExecuteInspection` feedback is the per-task boundary: when feedback advances from task A to task B, the mission runtime marks A succeeded before marking B active. The final empty feedback settles the last task. Navigation failures that are configured as skippable settle the task as skipped. The task array therefore always contains at most one active task and its completed count advances during the run.

The risk node subscribes to the task array as an inspection trigger. It keeps the latest real digital-twin observations for every asset. When an asset task becomes succeeded, it commits a risk observation for that asset; if a sensor is not applicable or has no reading, that component remains zero and the asset is explicitly evaluated as normal rather than left unknown. The weighted score remains authoritative in `risk_weights.yaml` and the Gateway only exposes its components and formula metadata.

The report generator subscribes to mission state and generates HTML/PDF exactly once for each succeeded mission. It uses the latest task and risk snapshots and the existing immutable evidence-store path. Failure is logged and remains retryable rather than silently claiming a report exists.

The Gateway projects robot pose, velocity, battery, camera freshness/frame rate, detections, environmental readings, meter readings, current asset/task and risk components into its existing REST/WebSocket snapshots. It also emits semantic event records for task activation/completion, risk evaluation, mission completion, report creation, and scenario command completion. The frontend renders all ten assets, a Chinese event description, a live sensor panel beside the camera, and a risk-formula panel sourced from authoritative component values.

Navigation inspection goals remain outside asset collision geometry. Progress-checker timeouts are reduced so an unreachable point cannot look frozen for half a minute, while successful arrival uses only a short stabilization window. Scenario commands complete from the matching Gazebo terminal state and the frontend retains the command result instead of replacing it with an unexplained timeout.

## Acceptance

- At most one task is active; the completed count advances after every reached asset.
- Every succeeded asset has a non-unknown risk level and a timestamp.
- A succeeded ten-asset mission produces exactly one downloadable report group.
- The dashboard lists all ten assets.
- The event stream names the asset, action, result, and time in Chinese.
- The perception view shows live project sensor fields and the authoritative weighted risk calculation.
- Scenario trigger/reset commands reach a terminal command state.

