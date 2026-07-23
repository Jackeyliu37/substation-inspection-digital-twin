#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

test -x scripts/smoke_headless_egl.sh
test -s tests/environment/fixtures/headless_camera.sdf
grep -F '<render_engine>ogre2</render_engine>' tests/environment/fixtures/headless_camera.sdf
grep -F '<topic>/phase1/camera</topic>' tests/environment/fixtures/headless_camera.sdf
! rg -n 'Xvfb|VirtualGL|DISPLAY=|xvfb-run' scripts/smoke_headless_egl.sh tests/environment/fixtures/headless_camera.sdf
