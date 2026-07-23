from __future__ import annotations

from dataclasses import asdict
import json
import math
import os
from pathlib import Path
import subprocess
from threading import Condition, Thread
import time
import uuid

from cv_bridge import CvBridge
from geometry_msgs.msg import Pose
import cv2
import numpy as np
import rclpy
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from ros_gz_interfaces.msg import Entity
from ros_gz_interfaces.srv import SetEntityPose
from sensor_msgs.msg import CameraInfo, Image, JointState
from std_msgs.msg import Float64

from .meter_dataset_plan import GenerationConfig, SamplePlan, load_generation_config
from .meter_dataset_projection import CameraIntrinsics, Pose3D, project_dial, validate_projection


HIDDEN_POSE = (0.0, 0.0, -10.0, 0.0, 0.0, 0.0)
CAMERA_HEIGHT_M = 1.2
DIAL_RADIUS_M = 0.18
WAIT_SECONDS = 5.0
RUN_SECONDS = 40.0 * 60.0
METER_MODELS = {
    "meter-pressure-01": "synthetic_meter_pressure",
    "meter-oil-01": "synthetic_meter_oil",
}
NEEDLE_TOPICS = {
    "meter-pressure-01": "/meter_dataset/pressure/needle_cmd",
    "meter-oil-01": "/meter_dataset/oil/needle_cmd",
}
BACKGROUND_MODELS = {
    "industrial_light": "background_industrial_light",
    "industrial_dark": "background_industrial_dark",
    "concrete": "background_concrete",
}


class MeterGenerationError(RuntimeError):
    pass


def _fail(code: str, detail: str) -> None:
    raise MeterGenerationError(f"{code}: {detail}")


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


def _canonical_json(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _git_output(*arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments], check=True, capture_output=True, text=True, timeout=5.0
    )
    return result.stdout.strip()


def _validate_run_inputs(
    run_id: str, output_dir: Path, expected_commit: str, sample_mode: str
) -> Path:
    try:
        parsed_run_id = uuid.UUID(run_id)
    except ValueError:
        _fail("RUN_ID_INVALID", run_id)
    if parsed_run_id.version != 4 or str(parsed_run_id) != run_id.lower():
        _fail("RUN_ID_INVALID", run_id)
    if sample_mode not in {"smoke", "full"}:
        _fail("SAMPLE_MODE_INVALID", sample_mode)
    if not output_dir.is_absolute() or output_dir.name.endswith(".staging") is False:
        _fail("OUTPUT_DIRECTORY_INVALID", str(output_dir))
    if output_dir.is_symlink() or not output_dir.is_dir() or any(output_dir.iterdir()):
        _fail("OUTPUT_DIRECTORY_NOT_EMPTY", str(output_dir))
    repository = Path(_git_output("rev-parse", "--show-toplevel")).resolve()
    resolved_output = output_dir.resolve()
    try:
        resolved_output.relative_to(repository)
    except ValueError:
        pass
    else:
        _fail("OUTPUT_DIRECTORY_INSIDE_GIT", str(resolved_output))
    actual_commit = _git_output("rev-parse", "HEAD")
    if actual_commit != expected_commit:
        _fail("GIT_COMMIT_MISMATCH", f"expected={expected_commit} actual={actual_commit}")
    if _git_output("status", "--porcelain", "--untracked-files=no"):
        _fail("GIT_TRACKED_WORKTREE_DIRTY", str(repository))
    return repository


def _select_samples(config: GenerationConfig, sample_mode: str) -> tuple[SamplePlan, ...]:
    if sample_mode == "full":
        return config.samples
    selected: list[SamplePlan] = []
    for split in ("train", "val", "test"):
        for asset_id in config.meter_asset_ids:
            candidates = [
                sample
                for sample in config.samples
                if sample.split == split and sample.asset_id == asset_id
            ]
            selected.extend(candidates[:2])
    if len(selected) != 12:
        _fail("SMOKE_PLAN_INVALID", str(len(selected)))
    return tuple(selected)


def _postprocess(image_rgb: np.ndarray, brightness_scale: float, blur_sigma: float) -> np.ndarray:
    result = np.clip(image_rgb.astype(np.float32) * brightness_scale, 0.0, 255.0).astype(np.uint8)
    if blur_sigma > 0.0:
        result = cv2.GaussianBlur(result, (0, 0), sigmaX=blur_sigma, sigmaY=blur_sigma)
    return result


class MeterDatasetGenerator(Node):
    def __init__(self) -> None:
        super().__init__("meter_dataset_generator")
        self.run_id = str(self.declare_parameter("run_id", "").value)
        self.output_dir = Path(str(self.declare_parameter("output_dir", "").value))
        self.generation_config_path = Path(
            str(self.declare_parameter("generation_config", "").value)
        )
        self.registry_path = Path(str(self.declare_parameter("registry_path", "").value))
        self.expected_commit = str(self.declare_parameter("expected_commit", "").value)
        self.sample_mode = str(self.declare_parameter("sample_mode", "").value)

        self.repository = _validate_run_inputs(
            self.run_id, self.output_dir, self.expected_commit, self.sample_mode
        )
        self.config = load_generation_config(self.generation_config_path, self.registry_path)
        self.samples = _select_samples(self.config, self.sample_mode)
        self.bridge = CvBridge()
        self.condition = Condition()
        self.latest_image: np.ndarray | None = None
        self.latest_camera_info: CameraIntrinsics | None = None
        self.latest_joint_positions: tuple[float, ...] = ()
        self.image_sequence = 0

        sensor_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=5,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
        )
        control_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=5,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
        )
        self.create_subscription(
            Image, "/meter_dataset/camera/image_raw", self._on_image, sensor_qos
        )
        self.create_subscription(
            CameraInfo, "/meter_dataset/camera/camera_info", self._on_camera_info, sensor_qos
        )
        self.create_subscription(
            JointState, "/meter_dataset/joint_states", self._on_joint_state, sensor_qos
        )
        self.needle_publishers = {
            asset_id: self.create_publisher(Float64, topic, control_qos)
            for asset_id, topic in NEEDLE_TOPICS.items()
        }
        self.pose_client = self.create_client(
            SetEntityPose, "/world/meter_dataset/set_pose"
        )

    def _on_image(self, message: Image) -> None:
        try:
            image = self.bridge.imgmsg_to_cv2(message, desired_encoding="rgb8")
        except Exception as error:
            self.get_logger().warning(f"IMAGE_DECODE_FAILED: {error}")
            return
        with self.condition:
            self.latest_image = np.asarray(image).copy()
            self.image_sequence += 1
            self.condition.notify_all()

    def _on_camera_info(self, message: CameraInfo) -> None:
        intrinsics = CameraIntrinsics(
            width=int(message.width),
            height=int(message.height),
            fx=float(message.k[0]),
            fy=float(message.k[4]),
            cx=float(message.k[2]),
            cy=float(message.k[5]),
        )
        with self.condition:
            self.latest_camera_info = intrinsics
            self.condition.notify_all()

    def _on_joint_state(self, message: JointState) -> None:
        with self.condition:
            self.latest_joint_positions = tuple(float(value) for value in message.position)
            self.condition.notify_all()

    def _set_pose(self, name: str, values: tuple[float, float, float, float, float, float]) -> None:
        if not self.pose_client.wait_for_service(timeout_sec=WAIT_SECONDS):
            _fail("POSE_SERVICE_TIMEOUT", name)
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
        response = self.pose_client.call(request, timeout_sec=WAIT_SECONDS)
        if response is None or not response.success:
            _fail("POSE_SET_FAILED", name)

    def _arrange_scene(self, sample: SamplePlan) -> None:
        active_meter = METER_MODELS[sample.asset_id]
        active_background = BACKGROUND_MODELS[sample.background_family]
        for model in METER_MODELS.values():
            self._set_pose(model, HIDDEN_POSE)
        for model in BACKGROUND_MODELS.values():
            self._set_pose(model, HIDDEN_POSE)
        self._set_pose("meter_occluder", HIDDEN_POSE)

        self._set_pose(
            active_background,
            (sample.distance_m + 0.10, 0.0, CAMERA_HEIGHT_M, 0.0, 0.0, 0.0),
        )
        self._set_pose(
            active_meter,
            (
                sample.distance_m,
                0.0,
                CAMERA_HEIGHT_M,
                sample.roll_radians,
                -math.pi / 2.0 + sample.pitch_radians,
                sample.yaw_radians,
            ),
        )
        occluder = {
            "edge_left": (sample.distance_m - 0.08, 0.16, CAMERA_HEIGHT_M, 0.0, 0.0, 0.0),
            "edge_right": (sample.distance_m - 0.08, -0.16, CAMERA_HEIGHT_M, 0.0, 0.0, 0.0),
            "partial_bottom": (sample.distance_m - 0.08, 0.0, CAMERA_HEIGHT_M - 0.18, 0.0, 0.0, 0.0),
        }.get(sample.occlusion_regime)
        if occluder is not None:
            self._set_pose("meter_occluder", occluder)

    def _publish_needle_and_wait(self, sample: SamplePlan) -> None:
        publisher = self.needle_publishers[sample.asset_id]
        deadline = time.monotonic() + WAIT_SECONDS
        while time.monotonic() < deadline:
            publisher.publish(Float64(data=sample.needle_angle_radians))
            with self.condition:
                if any(
                    abs(position - sample.needle_angle_radians) <= 0.02
                    for position in self.latest_joint_positions
                ):
                    return
                self.condition.wait(timeout=0.1)
        _fail("JOINT_FEEDBACK_TIMEOUT", sample.sample_id)

    def _fresh_frame(self) -> tuple[np.ndarray, CameraIntrinsics]:
        with self.condition:
            starting_sequence = self.image_sequence
            target = starting_sequence + self.config.fresh_frames_after_command
            deadline = time.monotonic() + WAIT_SECONDS
            while time.monotonic() < deadline:
                if (
                    self.image_sequence >= target
                    and self.latest_image is not None
                    and self.latest_camera_info is not None
                ):
                    return self.latest_image.copy(), self.latest_camera_info
                self.condition.wait(timeout=max(0.0, deadline - time.monotonic()))
        _fail("FRESH_FRAME_TIMEOUT", str(starting_sequence))

    def _capture(self, sample: SamplePlan) -> dict[str, object]:
        self._arrange_scene(sample)
        self._publish_needle_and_wait(sample)
        image, intrinsics = self._fresh_frame()
        if image.shape != (self.config.height, self.config.width, 3):
            _fail("IMAGE_DIMENSIONS_INVALID", repr(image.shape))
        if image.dtype != np.uint8 or float(image.std()) < 2.0:
            _fail("IMAGE_NOT_NON_UNIFORM", f"dtype={image.dtype} std={float(image.std()):.3f}")
        if (
            intrinsics.width != self.config.width
            or intrinsics.height != self.config.height
            or min(intrinsics.fx, intrinsics.fy) <= 0.0
        ):
            _fail("CAMERA_INFO_INVALID", repr(intrinsics))

        projection = project_dial(
            intrinsics,
            Pose3D(
                x=0.0,
                y=0.0,
                z=sample.distance_m,
                roll=sample.roll_radians,
                pitch=sample.pitch_radians,
                yaw=sample.yaw_radians,
            ),
            DIAL_RADIUS_M,
        )
        validate_projection(projection, self.config.minimum_bbox_pixels)
        processed = _postprocess(image, sample.brightness_scale, sample.blur_sigma)
        encoded_ok, encoded = cv2.imencode(
            ".png", cv2.cvtColor(processed, cv2.COLOR_RGB2BGR)
        )
        if not encoded_ok:
            _fail("PNG_ENCODE_FAILED", sample.sample_id)
        decoded = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
        if decoded is None or decoded.shape[:2] != (self.config.height, self.config.width):
            _fail("PNG_REVALIDATION_FAILED", sample.sample_id)

        image_path = self.output_dir / sample.image_path
        label_path = self.output_dir / sample.label_path
        _atomic_write(image_path, encoded.tobytes())
        label = "0 " + " ".join(f"{value:.9f}" for value in projection.bbox_yolo) + "\n"
        _atomic_write(label_path, label.encode("ascii"))
        meter = self.config.meters[sample.asset_id]
        return {
            **asdict(sample),
            "run_id": self.run_id,
            "dataset_id": self.config.dataset_id,
            "class_id": 0,
            "class_name": "meter",
            "sensor_id": meter.sensor_id,
            "range_minimum": meter.minimum,
            "range_maximum": meter.maximum,
            "unit": meter.unit,
            "camera_intrinsics": asdict(intrinsics),
            "bbox_yolo": list(projection.bbox_yolo),
            "bbox_pixels": asdict(projection.bbox_pixels),
            "dial_radius_m": DIAL_RADIUS_M,
            "generator_git_commit": self.expected_commit,
        }

    def run(self) -> bool:
        started = time.monotonic()
        metadata: list[dict[str, object]] = []
        rejected: dict[str, int] = {}
        failure = ""
        for accepted_index, sample in enumerate(self.samples, start=1):
            if time.monotonic() - started > RUN_SECONDS:
                failure = "RUN_TIMEOUT"
                break
            last_error = "SAMPLE_RETRIES_EXHAUSTED"
            for _attempt in range(1, self.config.maximum_retries_per_sample + 1):
                try:
                    metadata.append(self._capture(sample))
                    last_error = ""
                    break
                except Exception as error:
                    last_error = str(error).split(":", maxsplit=1)[0]
                    rejected[last_error] = rejected.get(last_error, 0) + 1
                    self.get_logger().warning(
                        f"sample={sample.sample_id} retry={_attempt} reason={error}"
                    )
            if last_error:
                failure = f"SAMPLE_INCOMPLETE:{sample.sample_id}:{last_error}"
                break
            if accepted_index == 1 or accepted_index % 100 == 0:
                self.get_logger().info(
                    f"meter-dataset-progress: accepted={accepted_index}/{len(self.samples)}"
                )

        _atomic_write(
            self.output_dir / "metadata.jsonl",
            b"".join(
                _canonical_json(row)
                for row in sorted(metadata, key=lambda item: str(item["sample_id"]))
            ),
        )
        complete = len(metadata) == len(self.samples) and not failure
        result = {
            "schema_version": 1,
            "status": "accepted" if complete else "incomplete",
            "run_id": self.run_id,
            "sample_mode": self.sample_mode,
            "expected_count": len(self.samples),
            "accepted_count": len(metadata),
            "rejected_attempt_counts": dict(sorted(rejected.items())),
            "failure": failure,
            "generator_git_commit": self.expected_commit,
        }
        _atomic_write(self.output_dir / "generation-result.json", _canonical_json(result))
        return complete


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node: MeterDatasetGenerator | None = None
    executor: MultiThreadedExecutor | None = None
    spin_thread: Thread | None = None
    success = False
    try:
        node = MeterDatasetGenerator()
        executor = MultiThreadedExecutor(num_threads=4)
        executor.add_node(node)
        spin_thread = Thread(target=executor.spin, daemon=True)
        spin_thread.start()
        success = node.run()
    except Exception as error:
        if node is not None:
            node.get_logger().error(f"meter-dataset-generator: FAIL: {error}")
        else:
            print(f"meter-dataset-generator: FAIL: {error}", flush=True)
    finally:
        if executor is not None:
            executor.shutdown(timeout_sec=2.0)
        if spin_thread is not None:
            spin_thread.join(timeout=2.0)
        if node is not None:
            node.destroy_node()
        rclpy.shutdown()
    if not success:
        raise SystemExit(1)
    print("meter-dataset-generator: PASS", flush=True)


if __name__ == "__main__":
    main()
