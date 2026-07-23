from __future__ import annotations

from dataclasses import dataclass

from .meter_dataset_plan import SamplePlan


PoseValues = tuple[float, float, float, float, float, float]
SceneCommand = tuple[str, PoseValues]

HIDDEN_POSE: PoseValues = (0.0, 0.0, -10.0, 0.0, 0.0, 0.0)
CAMERA_HEIGHT_M = 1.2
METER_MODELS = {
    "meter-pressure-01": "synthetic_meter_pressure",
    "meter-oil-01": "synthetic_meter_oil",
}
BACKGROUND_MODELS = {
    "industrial_light": "background_industrial_light",
    "industrial_dark": "background_industrial_dark",
    "concrete": "background_concrete",
}


@dataclass(frozen=True)
class SceneState:
    active_meter: str | None = None
    active_background: str | None = None
    occluder_visible: bool = False


def scene_commands(
    sample: SamplePlan, previous: SceneState
) -> tuple[tuple[SceneCommand, ...], SceneState]:
    active_meter = METER_MODELS[sample.asset_id]
    active_background = BACKGROUND_MODELS[sample.background_family]
    occluder_pose = {
        "edge_left": (
            sample.distance_m - 0.08,
            0.16,
            CAMERA_HEIGHT_M,
            0.0,
            0.0,
            0.0,
        ),
        "edge_right": (
            sample.distance_m - 0.08,
            -0.16,
            CAMERA_HEIGHT_M,
            0.0,
            0.0,
            0.0,
        ),
        "partial_bottom": (
            sample.distance_m - 0.08,
            0.0,
            CAMERA_HEIGHT_M - 0.18,
            0.0,
            0.0,
            0.0,
        ),
    }.get(sample.occlusion_regime)

    commands: list[SceneCommand] = []
    if previous.active_meter is not None and previous.active_meter != active_meter:
        commands.append((previous.active_meter, HIDDEN_POSE))
    if (
        previous.active_background is not None
        and previous.active_background != active_background
    ):
        commands.append((previous.active_background, HIDDEN_POSE))
    if previous.occluder_visible and occluder_pose is None:
        commands.append(("meter_occluder", HIDDEN_POSE))

    commands.append(
        (
            active_background,
            (sample.distance_m + 0.10, 0.0, CAMERA_HEIGHT_M, 0.0, 0.0, 0.0),
        )
    )
    commands.append(
        (
            active_meter,
            (
                sample.distance_m,
                0.0,
                CAMERA_HEIGHT_M,
                sample.roll_radians,
                -1.5707963267948966 + sample.pitch_radians,
                sample.yaw_radians,
            ),
        )
    )
    if occluder_pose is not None:
        commands.append(("meter_occluder", occluder_pose))

    return tuple(commands), SceneState(
        active_meter=active_meter,
        active_background=active_background,
        occluder_visible=occluder_pose is not None,
    )
