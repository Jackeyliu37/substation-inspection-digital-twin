from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue

from substation_digital_twin.twin_node import TwinTelemetry


def measurement(key: str, value: str) -> DiagnosticArray:
    message = DiagnosticArray()
    message.header.stamp.sec = 7
    message.status = [DiagnosticStatus(
        name="transformer-01",
        hardware_id="sensor-01",
        values=[
            KeyValue(key="run_id", value="run-1"),
            KeyValue(key=key, value=value),
            KeyValue(key="confidence_0_1", value="1.0"),
            KeyValue(key="valid", value="true"),
        ],
    )]
    return message


def test_twin_merges_environment_measurements_into_asset_snapshot() -> None:
    twin = TwinTelemetry({"transformer-01": ("transformer", (4.0, 3.0, 0.0))})
    twin.apply(measurement("value_celsius", "90.0"), "temperature_celsius", "value_celsius", "run-1")
    twin.apply(measurement("value_0_1", "0.7"), "smoke_0_1", "value_0_1", "run-1")
    twin.apply(measurement("value_ppm", "180.0"), "gas_ppm", "value_ppm", "run-1")

    snapshot = twin.snapshot("run-1")

    assert snapshot.header.frame_id == "map"
    assert len(snapshot.status) == 1
    values = {item.key: item.value for item in snapshot.status[0].values}
    assert values["temperature_celsius"] == "90.0"
    assert values["smoke_0_1"] == "0.7"
    assert values["gas_ppm"] == "180.0"
    assert values["run_id"] == "run-1"
