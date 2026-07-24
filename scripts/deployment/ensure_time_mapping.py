#!/usr/bin/env python3
"""Ensure the active production run has one authoritative ROS-to-UTC mapping."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy

from substation_interfaces.msg import RunContext
from substation_interfaces.srv import QueryRunTimeMapping, RecordRunTimeMapping


class MappingEnsurer(Node):
    def __init__(self, run_id: str) -> None:
        super().__init__("deployment_time_mapping_ensurer")
        self.run_id = run_id
        self.run_context: RunContext | None = None
        state_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        self.create_subscription(
            RunContext, "/system/run_context", self._on_context, state_qos
        )
        self.query = self.create_client(
            QueryRunTimeMapping, "/reporting/query_run_time_mapping"
        )
        self.record = self.create_client(
            RecordRunTimeMapping, "/reporting/record_run_time_mapping"
        )

    def _on_context(self, message: RunContext) -> None:
        if (
            message.run_id == self.run_id
            and message.lifecycle == RunContext.LIFECYCLE_ACTIVE
        ):
            self.run_context = message


def wait_until(node: Node, predicate, deadline: float) -> bool:
    while time.monotonic() < deadline:
        if predicate():
            return True
        rclpy.spin_once(node, timeout_sec=0.2)
    return predicate()


def wait_future(node: Node, future, deadline: float):
    if not wait_until(node, future.done, deadline):
        raise TimeoutError("TIME_MAPPING_SERVICE_TIMEOUT")
    return future.result()


def ensure_mapping(run_id: str, timeout_s: float) -> None:
    rclpy.init()
    node = MappingEnsurer(run_id)
    deadline = time.monotonic() + timeout_s
    try:
        if not wait_until(node, lambda: node.run_context is not None, deadline):
            raise RuntimeError("ACTIVE_RUN_CONTEXT_UNAVAILABLE")
        if not wait_until(
            node,
            lambda: node.query.service_is_ready() and node.record.service_is_ready(),
            deadline,
        ):
            raise RuntimeError("TIME_MAPPING_SERVICES_UNAVAILABLE")

        query = QueryRunTimeMapping.Request(schema_version=1, run_id=run_id)
        existing = wait_future(node, node.query.call_async(query), deadline)
        if existing.found:
            print(f"ensure-time-mapping: PASS: existing mapping for {run_id}")
            return
        if existing.error_code != "TIME_MAPPING_UNAVAILABLE":
            raise RuntimeError(existing.error_code or "TIME_MAPPING_QUERY_FAILED")

        context = node.run_context
        if context is None:
            raise RuntimeError("ACTIVE_RUN_CONTEXT_UNAVAILABLE")
        request = RecordRunTimeMapping.Request()
        request.schema_version = 1
        request.run_id = run_id
        request.context_revision = context.context_revision
        request.anchor_ros_sec = context.header.stamp.sec
        request.anchor_ros_nanosec = context.header.stamp.nanosec
        request.anchor_utc = (
            datetime.now(timezone.utc)
            .isoformat(timespec="microseconds")
            .replace("+00:00", "Z")
        )
        recorded = wait_future(node, node.record.call_async(request), deadline)
        if not recorded.accepted:
            raise RuntimeError(recorded.error_code or "TIME_MAPPING_RECORD_FAILED")
        print(f"ensure-time-mapping: PASS: recorded mapping for {run_id}")
    finally:
        node.destroy_node()
        rclpy.shutdown()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--timeout-s", type=float, default=30.0)
    args = parser.parse_args()
    ensure_mapping(args.run_id, args.timeout_s)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
