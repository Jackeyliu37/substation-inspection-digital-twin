from diagnostic_msgs.msg import DiagnosticStatus, KeyValue
from substation_interfaces.msg import InspectionTask, InspectionTaskArray

from substation_risk.risk_node import completed_assets, components_from_twin_status


def test_combined_environment_builds_high_context_risk_components() -> None:
    status = DiagnosticStatus(
        name="transformer-01",
        values=[
            KeyValue(key="run_id", value="run-1"),
            KeyValue(key="temperature_celsius", value="90.0"),
            KeyValue(key="smoke_0_1", value="0.7"),
            KeyValue(key="gas_ppm", value="180.0"),
        ],
    )
    thresholds = {
        "temperature_celsius": {"warning": 65.0, "critical": 80.0},
        "smoke_0_1": {"warning": 0.25, "critical": 0.6},
        "gas_ppm": {"warning": 100.0, "critical": 200.0},
    }

    components = components_from_twin_status(status, thresholds, "run-1")

    assert components == {
        "visual": 0.0,
        "temperature": 1.0,
        "smoke": 1.0,
        "gas": 0.8,
        "context": 1.0,
    }


def test_missing_optional_measurements_evaluate_as_zero_components() -> None:
    status = DiagnosticStatus(
        name="breaker-01",
        values=[
            KeyValue(key="run_id", value="run-1"),
            KeyValue(key="temperature_celsius", value=""),
            KeyValue(key="smoke_0_1", value=""),
            KeyValue(key="gas_ppm", value=""),
        ],
    )
    thresholds = {
        "temperature_celsius": {"warning": 65.0, "critical": 80.0},
        "smoke_0_1": {"warning": 0.25, "critical": 0.6},
        "gas_ppm": {"warning": 100.0, "critical": 200.0},
    }

    assert components_from_twin_status(status, thresholds, "run-1") == {
        "visual": 0.0,
        "temperature": 0.0,
        "smoke": 0.0,
        "gas": 0.0,
        "context": 0.0,
    }


def test_completed_assets_returns_only_newly_succeeded_asset_ids() -> None:
    first = InspectionTaskArray(
        run_id="run-1",
        tasks=[InspectionTask(asset_id="breaker-01", state=InspectionTask.STATE_ACTIVE)],
    )
    second = InspectionTaskArray(
        run_id="run-1",
        tasks=[InspectionTask(asset_id="breaker-01", state=InspectionTask.STATE_SUCCEEDED)],
    )

    assert completed_assets(None, first) == set()
    assert completed_assets(first, second) == {"breaker-01"}
    assert completed_assets(second, second) == set()

    skipped = InspectionTaskArray(
        run_id="run-1",
        tasks=[InspectionTask(asset_id="breaker-01", state=InspectionTask.STATE_SKIPPED)],
    )
    assert completed_assets(first, skipped) == {"breaker-01"}
