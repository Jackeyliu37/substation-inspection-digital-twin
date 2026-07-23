from diagnostic_msgs.msg import DiagnosticStatus, KeyValue

from substation_risk.risk_node import components_from_twin_status


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
