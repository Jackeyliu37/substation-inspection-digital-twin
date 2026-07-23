from __future__ import annotations

import math
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from geometry_msgs.msg import TransformStamped
import rclpy
from rclpy.node import Node
from tf2_ros.static_transform_broadcaster import StaticTransformBroadcaster

from .asset_registry import load_asset_registry


def quaternion_from_rpy(roll: float, pitch: float, yaw: float) -> tuple[float, float, float, float]:
    cr, sr = math.cos(roll / 2.0), math.sin(roll / 2.0)
    cp, sp = math.cos(pitch / 2.0), math.sin(pitch / 2.0)
    cy, sy = math.cos(yaw / 2.0), math.sin(yaw / 2.0)
    return (
        sr * cp * cy - cr * sp * sy,
        cr * sp * cy + sr * cp * sy,
        cr * cp * sy - sr * sp * cy,
        cr * cp * cy + sr * sp * sy,
    )


class AssetTfBroadcaster(Node):
    def __init__(self) -> None:
        super().__init__("asset_tf_broadcaster")
        default_path = str(
            Path(get_package_share_directory("substation_description"))
            / "config/devices.yaml"
        )
        registry_path = Path(
            self.declare_parameter("registry_path", default_path).value
        )
        registry = load_asset_registry(registry_path)
        broadcaster = StaticTransformBroadcaster(self)
        stamp = self.get_clock().now().to_msg()
        transforms = []
        for asset in registry.assets:
            transform = TransformStamped()
            transform.header.stamp = stamp
            transform.header.frame_id = "map"
            transform.child_frame_id = f"asset/{asset.asset_id}"
            transform.transform.translation.x = asset.pose.x
            transform.transform.translation.y = asset.pose.y
            transform.transform.translation.z = asset.pose.z
            qx, qy, qz, qw = quaternion_from_rpy(
                asset.pose.roll, asset.pose.pitch, asset.pose.yaw
            )
            transform.transform.rotation.x = qx
            transform.transform.rotation.y = qy
            transform.transform.rotation.z = qz
            transform.transform.rotation.w = qw
            transforms.append(transform)
        broadcaster.sendTransform(transforms)
        self._broadcaster = broadcaster
        self.get_logger().info(f"published {len(transforms)} asset transforms")


def main(args=None) -> None:
    rclpy.init(args=args)
    node = AssetTfBroadcaster()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
