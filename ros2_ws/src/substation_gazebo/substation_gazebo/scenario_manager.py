from __future__ import annotations

import math
from pathlib import Path
from threading import Lock, Thread

from ament_index_python.packages import get_package_share_directory
from builtin_interfaces.msg import Time
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from geometry_msgs.msg import Pose
import rclpy
from rcl_interfaces.msg import SetParametersResult
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from ros_gz_interfaces.msg import Entity
from ros_gz_interfaces.srv import SetEntityPose
from sensor_msgs.msg import BatteryState

from .scenario_catalog import ApplyResult, Command, Pose as ScenarioPose
from .scenario_catalog import ScenarioCatalog, ScenarioEngine, ScenarioError


COMMAND_PARAMETER_NAMES = frozenset(
    {"command_id", "scenario_id", "scenario_action", "scenario_parameters_json"}
)


def _key_values(items: list[tuple[str, object]]) -> list[KeyValue]:
    return [KeyValue(key=key, value=str(value)) for key, value in items]


def _bool(value: bool) -> str:
    return "true" if value else "false"


def build_measurement_array(
    *,
    stamp: Time,
    asset_id: str,
    sensor_id: str,
    run_id: str,
    value_key: str,
    value: float,
) -> DiagnosticArray:
    status = DiagnosticStatus(
        level=DiagnosticStatus.OK,
        name=asset_id,
        message="SIMULATION_VALID",
        hardware_id=sensor_id,
        values=_key_values(
            [
                ("run_id", run_id),
                (value_key, float(value)),
                ("confidence_0_1", 1.0),
                ("valid", "true"),
            ]
        ),
    )
    message = DiagnosticArray()
    message.header.stamp = stamp
    message.status = [status]
    return message


def build_scenario_state(
    *,
    stamp: Time,
    scenario_id: str,
    run_id: str,
    command_id: str,
    action: str,
    status: str,
    active: bool,
    revision: int,
    error_code: str,
) -> DiagnosticArray:
    item = DiagnosticStatus(
        level=DiagnosticStatus.OK if status != "failed" else DiagnosticStatus.ERROR,
        name=scenario_id,
        message="SCENARIO_STATE",
        hardware_id="gazebo",
        values=_key_values(
            [
                ("run_id", run_id),
                ("command_id", command_id),
                ("action", action),
                ("status", status),
                ("active", _bool(active)),
                ("scenario_revision", revision),
                ("applied_ros_sec", stamp.sec),
                ("applied_ros_nanosec", stamp.nanosec),
                ("error_code", error_code),
            ]
        ),
    )
    message = DiagnosticArray()
    message.header.stamp = stamp
    message.status = [item]
    return message


def build_scenario_truth(
    *,
    stamp: Time,
    started_stamp: Time,
    scenario_id: str,
    run_id: str,
    active: bool,
    revision: int,
) -> DiagnosticArray:
    item = DiagnosticStatus(
        level=DiagnosticStatus.OK,
        name=scenario_id,
        message="SIMULATION_TRUTH",
        hardware_id="gazebo",
        values=_key_values(
            [
                ("run_id", run_id),
                ("active", _bool(active)),
                ("scenario_revision", revision),
                ("started_ros_sec", started_stamp.sec),
                ("started_ros_nanosec", started_stamp.nanosec),
            ]
        ),
    )
    message = DiagnosticArray()
    message.header.stamp = stamp
    message.status = [item]
    return message


def _quaternion_from_rpy(roll: float, pitch: float, yaw: float) -> tuple[float, float, float, float]:
    cr, sr = math.cos(roll / 2.0), math.sin(roll / 2.0)
    cp, sp = math.cos(pitch / 2.0), math.sin(pitch / 2.0)
    cy, sy = math.cos(yaw / 2.0), math.sin(yaw / 2.0)
    return (
        sr * cp * cy - cr * sp * sy,
        cr * sp * cy + sr * cp * sy,
        cr * cp * sy - sr * sp * cy,
        cr * cp * cy + sr * sp * sy,
    )


class ScenarioManager(Node):
    def __init__(self) -> None:
        super().__init__("scenario_manager")
        gazebo_share = Path(get_package_share_directory("substation_gazebo"))
        description_share = Path(get_package_share_directory("substation_description"))
        catalog_path = Path(
            self.declare_parameter(
                "catalog_path", str(gazebo_share / "config/scenarios.yaml")
            ).value
        )
        registry_path = Path(
            self.declare_parameter(
                "registry_path", str(description_share / "config/devices.yaml")
            ).value
        )
        self.run_id = str(self.declare_parameter("run_id", "").value)
        self.declare_parameter("command_id", "")
        self.declare_parameter("scenario_id", "normal")
        self.declare_parameter("scenario_action", "reset")
        self.declare_parameter("scenario_parameters_json", "{}")

        from substation_description.asset_registry import load_asset_registry

        registry = load_asset_registry(registry_path)
        self.catalog = ScenarioCatalog.load(
            catalog_path, {asset.asset_id for asset in registry.assets}
        )
        self.engine = ScenarioEngine(self.catalog)
        self._active_asset_id = "transformer-01"
        self._last_command_id = ""
        self._last_action = "reset"
        self._last_status = "applied"
        self._last_error = ""
        self._started_stamp = Time()
        self._pending: Command | None = None
        self._pending_lock = Lock()
        self._applying_command: Command | None = None
        self._apply_thread: Thread | None = None
        self._completed_application: tuple[Command, ApplyResult] | None = None

        q_sensor = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=5,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
        )
        q_state = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        q_event = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=100,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
        )
        q_stream = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
        )
        self.temperature_pub = self.create_publisher(
            DiagnosticArray, "/simulation/environment/temperature_raw", q_sensor
        )
        self.smoke_pub = self.create_publisher(
            DiagnosticArray, "/simulation/environment/smoke_raw", q_sensor
        )
        self.gas_pub = self.create_publisher(
            DiagnosticArray, "/simulation/environment/gas_raw", q_sensor
        )
        self.truth_pub = self.create_publisher(
            DiagnosticArray, "/simulation/scenario_truth", q_event
        )
        self.state_pub = self.create_publisher(
            DiagnosticArray, "/simulation/scenario_state", q_state
        )
        self.battery_pub = self.create_publisher(
            BatteryState, "/battery_state", q_stream
        )
        callback_group = ReentrantCallbackGroup()
        self.pose_client = self.create_client(
            SetEntityPose,
            "/world/substation/set_pose",
            callback_group=callback_group,
        )
        self.add_on_set_parameters_callback(self._on_parameters)
        self.create_timer(0.1, self._process_pending, callback_group=callback_group)
        self.create_timer(0.5, self.publish_environment)
        self.create_timer(1.0, self.publish_truth_state_and_battery)

    def _on_parameters(self, parameters: list[Parameter]) -> SetParametersResult:
        changed = {parameter.name for parameter in parameters}
        command_fields = changed & COMMAND_PARAMETER_NAMES
        if not command_fields:
            return SetParametersResult(successful=True)
        if command_fields != COMMAND_PARAMETER_NAMES or changed != COMMAND_PARAMETER_NAMES:
            return SetParametersResult(
                successful=False, reason="COMMAND_FIELDS_INCOMPLETE"
            )
        incoming = {parameter.name: parameter.value for parameter in parameters}
        if not all(isinstance(incoming[name], str) for name in COMMAND_PARAMETER_NAMES):
            return SetParametersResult(
                successful=False, reason="SCENARIO_PARAMETERS_INVALID"
            )
        try:
            command = Command.from_parameters(
                command_id=incoming["command_id"],
                scenario_id=incoming["scenario_id"],
                action=incoming["scenario_action"],
                parameters_json=incoming["scenario_parameters_json"],
            )
            self.catalog.validate(command)
        except ScenarioError as error:
            return SetParametersResult(successful=False, reason=str(error))
        with self._pending_lock:
            if self._pending is not None or self._applying_command is not None:
                return SetParametersResult(successful=False, reason="SCENARIO_CONFLICT")
            self._pending = command
        stamp = self.get_clock().now().to_msg()
        self.state_pub.publish(
            build_scenario_state(
                stamp=stamp,
                scenario_id=command.scenario_id,
                run_id=self.run_id,
                command_id=command.command_id,
                action=command.action,
                status="applying",
                active=self.engine.active,
                revision=self.engine.revision,
                error_code="",
            )
        )
        return SetParametersResult(successful=True)

    def _set_pose(self, name: str, values: ScenarioPose) -> bool:
        if not self.pose_client.wait_for_service(timeout_sec=2.0):
            return False
        x, y, z, roll, pitch, yaw = values
        request = SetEntityPose.Request()
        request.entity = Entity(name=name, type=Entity.MODEL)
        request.pose = Pose()
        request.pose.position.x = x
        request.pose.position.y = y
        request.pose.position.z = z
        qx, qy, qz, qw = _quaternion_from_rpy(roll, pitch, yaw)
        request.pose.orientation.x = qx
        request.pose.orientation.y = qy
        request.pose.orientation.z = qz
        request.pose.orientation.w = qw
        response = self.pose_client.call(request, timeout_sec=2.0)
        return response is not None and response.success

    def _apply_command(self, command: Command) -> None:
        try:
            result = self.engine.apply(command, self._set_pose)
        except Exception as error:
            self.get_logger().error(f"scenario application failed unexpectedly: {error}")
            result = ApplyResult(
                status="failed",
                revision=self.engine.revision,
                active=self.engine.active,
                scenario_id=command.scenario_id,
                error_code="SCENARIO_APPLICATION_FAILED",
            )
        with self._pending_lock:
            self._completed_application = (command, result)

    def _process_pending(self) -> None:
        with self._pending_lock:
            completed = self._completed_application
            if completed is not None:
                self._completed_application = None
                self._applying_command = None
                self._apply_thread = None
        if completed is not None:
            command, result = completed
            self._finish_application(command, result)
            return

        with self._pending_lock:
            if self._applying_command is not None or self._pending is None:
                return
            command = self._pending
            self._pending = None
            self._applying_command = command
            worker = Thread(
                target=self._apply_command,
                args=(command,),
                name=f"scenario-apply-{command.command_id[:8]}",
                daemon=True,
            )
            self._apply_thread = worker
        worker.start()

    def _finish_application(self, command: Command, result: ApplyResult) -> None:
        if result.status == "applied":
            asset_id = command.parameters.get("asset_id")
            if isinstance(asset_id, str):
                self._active_asset_id = asset_id
            self._last_command_id = command.command_id
            self._last_action = command.action
            self._last_status = result.status
            self._last_error = result.error_code
            self._started_stamp = self.get_clock().now().to_msg() if result.active else Time()
        self._publish_result(command, result)

    def _publish_result(self, command: Command, result: ApplyResult) -> None:
        stamp = self.get_clock().now().to_msg()
        self.state_pub.publish(
            build_scenario_state(
                stamp=stamp,
                scenario_id=command.scenario_id,
                run_id=self.run_id,
                command_id=command.command_id,
                action=command.action,
                status=result.status,
                active=result.active,
                revision=result.revision,
                error_code=result.error_code,
            )
        )
        self.truth_pub.publish(
            build_scenario_truth(
                stamp=stamp,
                started_stamp=self._started_stamp,
                scenario_id=self.engine.active_scenario,
                run_id=self.run_id,
                active=self.engine.active,
                revision=self.engine.revision,
            )
        )

    def publish_environment(self) -> None:
        stamp = self.get_clock().now().to_msg()
        asset_id = self._active_asset_id
        self.temperature_pub.publish(
            build_measurement_array(
                stamp=stamp,
                asset_id=asset_id,
                sensor_id=f"{asset_id}-temperature-01",
                run_id=self.run_id,
                value_key="value_celsius",
                value=self.engine.values["temperature_celsius"],
            )
        )
        self.smoke_pub.publish(
            build_measurement_array(
                stamp=stamp,
                asset_id=asset_id,
                sensor_id=f"{asset_id}-smoke-01",
                run_id=self.run_id,
                value_key="value_0_1",
                value=self.engine.values["smoke_0_1"],
            )
        )
        self.gas_pub.publish(
            build_measurement_array(
                stamp=stamp,
                asset_id=asset_id,
                sensor_id=f"{asset_id}-gas-01",
                run_id=self.run_id,
                value_key="value_ppm",
                value=self.engine.values["gas_ppm"],
            )
        )

    def publish_truth_state_and_battery(self) -> None:
        stamp = self.get_clock().now().to_msg()
        self.state_pub.publish(
            build_scenario_state(
                stamp=stamp,
                scenario_id=self.engine.active_scenario,
                run_id=self.run_id,
                command_id=self._last_command_id,
                action=self._last_action,
                status=self._last_status,
                active=self.engine.active,
                revision=self.engine.revision,
                error_code=self._last_error,
            )
        )
        self.truth_pub.publish(
            build_scenario_truth(
                stamp=stamp,
                started_stamp=self._started_stamp,
                scenario_id=self.engine.active_scenario,
                run_id=self.run_id,
                active=self.engine.active,
                revision=self.engine.revision,
            )
        )
        battery = BatteryState()
        battery.header.stamp = stamp
        battery.header.frame_id = "base_link"
        battery.percentage = self.engine.values["battery_percentage"]
        battery.present = True
        self.battery_pub.publish(battery)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = ScenarioManager()
    executor = MultiThreadedExecutor(num_threads=2)
    executor.add_node(node)
    try:
        executor.spin()
    finally:
        executor.shutdown()
        node.destroy_node()
        rclpy.shutdown()
