from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue

from substation_perception.environment_normalizer import normalize_measurement


def make_message(run_id: str, key: str, value: str) -> DiagnosticArray:
    message = DiagnosticArray()
    message.header.stamp.sec = 12
    message.status = [DiagnosticStatus(
        name="transformer-01",
        hardware_id="transformer-01-sensor",
        message="SIMULATION_VALID",
        values=[
            KeyValue(key="run_id", value=run_id),
            KeyValue(key=key, value=value),
            KeyValue(key="confidence_0_1", value="1.0"),
            KeyValue(key="valid", value="true"),
        ],
    )]
    return message


def test_normalizer_preserves_measurement_and_active_run() -> None:
    source = make_message("run-1", "value_celsius", "90.0")

    output = normalize_measurement(source, "value_celsius", "run-1")

    assert output.header == source.header
    assert output.status[0].name == "transformer-01"
    assert output.status[0].message == "NORMALIZED_VALID"
    assert {item.key: item.value for item in output.status[0].values}["value_celsius"] == "90.0"


def test_normalizer_rejects_wrong_run_and_malformed_values() -> None:
    assert normalize_measurement(
        make_message("old-run", "value_celsius", "90.0"), "value_celsius", "run-1"
    ).status == []
    assert normalize_measurement(
        make_message("run-1", "value_celsius", "nan"), "value_celsius", "run-1"
    ).status == []
