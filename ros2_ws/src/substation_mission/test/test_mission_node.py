from substation_interfaces.msg import AssetRisk, AssetRiskArray

from substation_mission.mission_engine import MissionPolicy
from substation_mission.mission_node import AssetGoal, MissionRuntime


def test_runtime_reorders_queue_when_asset_risk_changes() -> None:
    runtime = MissionRuntime(
        MissionPolicy(normal_replan_cooldown_s=0.0),
        "run-1",
        "mission-1",
        (
            AssetGoal("breaker-01", 0.5, 1.8, 1.57),
            AssetGoal("transformer-01", 4.0, 1.0, 1.57),
        ),
    )
    risks = AssetRiskArray(run_id="run-1", assets=[
        AssetRisk(asset_id="breaker-01", score_0_100=5.0),
        AssetRisk(asset_id="transformer-01", score_0_100=70.0),
    ])

    changed = runtime.apply_risks(risks, monotonic_s=12.0)
    snapshot = runtime.snapshot()

    assert changed is True
    assert snapshot.tasks[0].asset_id == "transformer-01"
    assert snapshot.tasks[0].computed_priority > snapshot.tasks[1].computed_priority
    assert snapshot.run_id == "run-1"
    assert snapshot.queue_revision == 2
