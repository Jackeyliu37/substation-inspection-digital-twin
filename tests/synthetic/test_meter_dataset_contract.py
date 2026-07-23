from __future__ import annotations

import ast
from pathlib import Path
import xml.etree.ElementTree as ET

import yaml


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "ros2_ws/src/substation_gazebo"


def required(relative: str) -> Path:
    path = ROOT / relative
    assert path.is_file(), f"missing meter dataset file: {relative}"
    return path


def test_meter_model_has_controllable_needle_and_no_external_resources() -> None:
    path = required("ros2_ws/src/substation_gazebo/models/synthetic_meter/model.sdf")
    tree = ET.parse(path)
    model = tree.find(".//model[@name='synthetic_meter']")
    assert model is not None
    joint = model.find("joint[@name='needle_joint']")
    assert joint is not None and joint.attrib["type"] == "revolute"
    plugins = {node.attrib.get("filename"): node for node in model.findall("plugin")}
    assert "gz-sim-joint-position-controller-system" in plugins
    assert "gz-sim-joint-state-publisher-system" in plugins
    assert plugins["gz-sim-joint-position-controller-system"].findtext("joint_name") == "needle_joint"
    assert plugins["gz-sim-joint-position-controller-system"].find("topic") is None
    text = path.read_text(encoding="utf-8")
    assert "fuel.gazebosim" not in text
    assert "http://" not in text and "https://" not in text


def test_meter_world_is_headless_ogre2_camera_scene() -> None:
    tree = ET.parse(required("ros2_ws/src/substation_gazebo/worlds/meter_dataset_world.sdf"))
    world = tree.find(".//world[@name='meter_dataset']")
    assert world is not None
    plugins = {node.attrib.get("filename") for node in world.findall("plugin")}
    assert {
        "gz-sim-physics-system",
        "gz-sim-sensors-system",
        "gz-sim-scene-broadcaster-system",
        "gz-sim-user-commands-system",
    }.issubset(plugins)
    assert world.find("plugin[@filename='gz-sim-sensors-system']/render_engine").text == "ogre2"
    camera = world.find(".//sensor[@name='meter_dataset_camera'][@type='camera']")
    assert camera is not None
    assert camera.findtext("topic") == "meter_dataset/camera/image_raw"
    assert camera.findtext("camera/image/width") == "640"
    assert camera.findtext("camera/image/height") == "480"
    model_names = {node.attrib["name"] for node in world.findall("model")}
    assert {
        "meter_occluder",
        "background_industrial_light",
        "background_industrial_dark",
        "background_concrete",
    }.issubset(model_names)
    include_names = {node.findtext("name") for node in world.findall("include")}
    assert include_names == {"synthetic_meter_pressure", "synthetic_meter_oil"}


def test_meter_bridge_has_exact_capture_and_control_topics() -> None:
    rows = yaml.safe_load(
        required("ros2_ws/src/substation_gazebo/config/meter_dataset_bridge.yaml").read_text(
            encoding="utf-8"
        )
    )
    by_ros = {row["ros_topic_name"]: row for row in rows}
    assert set(by_ros) == {
        "clock",
        "meter_dataset/camera/camera_info",
        "meter_dataset/joint_states",
        "meter_dataset/pressure/needle_cmd",
        "meter_dataset/oil/needle_cmd",
    }
    assert by_ros["meter_dataset/pressure/needle_cmd"]["gz_topic_name"] == "/model/synthetic_meter_pressure/joint/needle_joint/0/cmd_pos"
    assert by_ros["meter_dataset/oil/needle_cmd"]["gz_topic_name"] == "/model/synthetic_meter_oil/joint/needle_joint/0/cmd_pos"
    assert by_ros["meter_dataset/pressure/needle_cmd"]["direction"] == "ROS_TO_GZ"


def test_meter_launch_is_server_only_and_starts_generator() -> None:
    path = required("ros2_ws/src/substation_gazebo/launch/meter_dataset.launch.py")
    source = path.read_text(encoding="utf-8")
    ast.parse(source, filename=str(path))
    assert 'UnsetEnvironmentVariable("DISPLAY")' in source
    assert "--headless-rendering" in source
    assert 'SetEnvironmentVariable("ROS_LOCALHOST_ONLY", "1")' in source
    assert 'SetEnvironmentVariable("GZ_PARTITION"' in source
    assert 'executable="meter_dataset_generator"' in source
    assert "/world/meter_dataset/set_pose@ros_gz_interfaces/srv/SetEntityPose" in source
    assert "/meter_dataset/camera/image_raw" in source
    assert '"-g"' not in source and "Xvfb" not in source


def test_generator_cli_and_package_runtime_contract() -> None:
    source_path = required(
        "ros2_ws/src/substation_gazebo/substation_gazebo/meter_dataset_generator.py"
    )
    source = source_path.read_text(encoding="utf-8")
    ast.parse(source, filename=str(source_path))
    for token in (
        "output_dir",
        "generation_config",
        "registry_path",
        "run_id",
        "expected_commit",
        "sample_mode",
        "maximum_retries_per_sample",
        "fresh_frames_after_command",
        "generation-result.json",
    ):
        assert token in source
    package = ET.parse(PACKAGE / "package.xml")
    dependencies = {node.text for node in package.findall("exec_depend")}
    assert {"cv_bridge", "std_msgs", "sensor_msgs", "ros_gz_interfaces", "substation_description"}.issubset(dependencies)
    setup = (PACKAGE / "setup.py").read_text(encoding="utf-8")
    assert "meter_dataset_generator = substation_gazebo.meter_dataset_generator:main" in setup
    assert "meter_dataset_package = substation_gazebo.meter_dataset_package:main" in setup


def test_generation_harness_is_bounded_and_process_group_scoped() -> None:
    source = required("tests/synthetic/run_meter_dataset_generation.sh").read_text(
        encoding="utf-8"
    )
    for token in (
        "setsid env -u DISPLAY",
        "ROS_LOCALHOST_ONLY=1",
        "GZ_PARTITION=",
        "check_environment_seal.sh",
        "2700",
        'kill -TERM -- "-$launch_pid"',
        "meter_dataset_package package",
    ):
        assert token in source
    assert "pkill" not in source and "killall" not in source
