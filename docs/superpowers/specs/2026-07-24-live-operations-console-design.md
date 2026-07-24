# Live Operations Console Design

## Goal

Replace the placeholder Phase 7/8 console with a browser-only operations view backed by the existing production ROS/Gazebo graph. The operator must see the real occupancy map, robot pose and route, all ten registered substation assets, continuous annotated camera frames, the four imported production model records, and working scenario controls.

## Architecture

The browser continues to use only the FastAPI Gateway. The Gateway projects ROS state into REST snapshots and framed WebSocket camera messages; it does not fabricate operational state. Gazebo remains headless with OGRE2/EGL. The Three.js view reconstructs the yard from authoritative asset poses and categories, while a Canvas/SVG map renders the occupancy grid and overlays the robot and mission goals.

## Contracts

- `GET /api/v1/assets` returns every digital-twin asset; assets without a risk sample carry an explicit `unknown` risk object.
- `GET /api/v1/models` reports the four entries from `models/manifest.yaml` and verifies their production weight files under `/var/lib/substation/models/production`.
- `GET/POST /api/v1/simulation/scenario` exposes scenario state and dispatches the documented atomic parameter command to `scenario_manager`.
- `/ws/camera` continuously sends the documented 64-byte `SSCF` header, canonical metadata JSON, and the newest JPEG without queue buildup.
- An ended or restarted run still queries its persisted time mapping so Gateway readiness does not remain at 503.

## User Interface

The twin view includes the yard boundary, inspection lanes, transformer exclusion zone, category-specific equipment geometry, the robot, mission goal markers, and a robot trail. The map decodes `base64-int8-row-major-v1`, paints occupancy cells, and overlays the same robot and mission coordinates. The perception view shows live framed JPEGs and the actual imported model name, metric, classes, checksum prefix, and installed status. Scenario cards use catalog IDs and expose trigger/reset with persistent command feedback.

## Verification

Gateway contract tests cover asset projection, model discovery, scenario dispatch, camera framing, and ended-run time mapping. Frontend contract tests cover real API fields, map decoding, production model rendering, real asset poses, robot geometry, and valid scenario request bodies. The release must pass Gateway tests, frontend tests/build, deployment contract tests, and live HTTP/WebSocket smoke checks before manual acceptance.
