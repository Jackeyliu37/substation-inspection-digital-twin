#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
from uuid import uuid4

from diagnostic_msgs.msg import DiagnosticArray
import rclpy
from rcl_interfaces.msg import Parameter, ParameterType, ParameterValue
from rcl_interfaces.srv import SetParametersAtomically
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from substation_interfaces.msg import AssetRiskArray, InspectionTaskArray, RunContext


def state_qos() -> QoSProfile:
    return QoSProfile(
        history=HistoryPolicy.KEEP_LAST,
        depth=1,
        reliability=ReliabilityPolicy.RELIABLE,
        durability=DurabilityPolicy.TRANSIENT_LOCAL,
    )


class Phase56Probe(Node):
    def __init__(self, run_id: str) -> None:
        super().__init__("phase5_6_pipeline_probe")
        self.run_id = run_id
        self._run_context: RunContext | None = None
        self.risks: AssetRiskArray | None = None
        self.tasks: InspectionTaskArray | None = None
        qos = state_qos()
        self.create_subscription(RunContext, "/system/run_context", self._on_context, qos)
        self.create_subscription(AssetRiskArray, "/risk/assets", self._on_risks, qos)
        self.create_subscription(InspectionTaskArray, "/mission/inspection_tasks", self._on_tasks, qos)
        self.client = self.create_client(
            SetParametersAtomically, "/scenario_manager/set_parameters_atomically"
        )

    def _on_context(self, message: RunContext) -> None:
        self._run_context = message

    def _on_risks(self, message: AssetRiskArray) -> None:
        self.risks = message

    def _on_tasks(self, message: InspectionTaskArray) -> None:
        self.tasks = message

    def spin_until(self, predicate, timeout: float, label: str) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
            if predicate():
                return
        raise RuntimeError(f"timeout waiting for {label}")

    @staticmethod
    def string_parameter(name: str, value: str) -> Parameter:
        return Parameter(
            name=name,
            value=ParameterValue(type=ParameterType.PARAMETER_STRING, string_value=value),
        )

    def apply_scenario(self, scenario_id: str, parameters_json: str) -> str:
        if not self.client.wait_for_service(timeout_sec=15.0):
            raise RuntimeError("scenario parameter service unavailable")
        command_id = str(uuid4())
        request = SetParametersAtomically.Request(
            parameters=[
                self.string_parameter("command_id", command_id),
                self.string_parameter("scenario_id", scenario_id),
                self.string_parameter("scenario_action", "trigger"),
                self.string_parameter("scenario_parameters_json", parameters_json),
            ]
        )
        future = self.client.call_async(request)
        self.spin_until(future.done, 15.0, "scenario command response")
        response = future.result()
        if response is None or not response.result.successful:
            reason = "no response" if response is None else response.result.reason
            raise RuntimeError(f"scenario command rejected: {reason}")
        return command_id

    @staticmethod
    def risk_for(risks: AssetRiskArray | None, asset_id: str):
        if risks is None:
            return None
        return next((item for item in risks.assets if item.asset_id == asset_id), None)

    def baseline_ready(self) -> bool:
        return (
            self._run_context is not None
            and self._run_context.lifecycle == RunContext.LIFECYCLE_ACTIVE
            and self._run_context.run_id == self.run_id
            and self.risks is not None
            and self.risks.run_id == self.run_id
            and self.tasks is not None
            and self.tasks.run_id == self.run_id
            and len(self.tasks.tasks) >= 10
            and self.risk_for(self.risks, "transformer-01") is not None
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    rclpy.init()
    node = Phase56Probe(args.run_id)
    try:
        node.spin_until(node.baseline_ready, 90.0, "active core baseline")
        assert node.risks is not None and node.tasks is not None
        baseline_risk = node.risk_for(node.risks, "transformer-01")
        baseline_queue_revision = node.tasks.queue_revision
        baseline_state_revision = node.tasks.state_revision
        command_id = node.apply_scenario(
            "combined-risk-obstacle",
            '{"asset_id":"transformer-01","gas_ppm":180.0,'
            '"obstacle_progress_0_1":0.5,"smoke_0_1":0.7,"temperature_celsius":90.0}',
        )
        node.spin_until(
            lambda: (
                (risk := node.risk_for(node.risks, "transformer-01")) is not None
                and risk.score_0_100 >= 60.0
                and risk.level >= 2
                and risk.confirmation_frames >= 3
                and node.tasks is not None
                and node.tasks.queue_revision > baseline_queue_revision
                and bool(node.tasks.tasks)
                and node.tasks.tasks[0].asset_id == "transformer-01"
                and node.tasks.transition_reason_code == "RISK_REPLAN"
            ),
            30.0,
            "confirmed transformer risk and mission replan",
        )
        assert node.risks is not None and node.tasks is not None
        risk = node.risk_for(node.risks, "transformer-01")
        assert risk is not None
        result = {
            "status": "passed",
            "run_id": args.run_id,
            "scenario": {
                "scenario_id": "combined-risk-obstacle",
                "command_id": command_id,
            },
            "baseline": {
                "risk_score_0_100": None if baseline_risk is None else baseline_risk.score_0_100,
                "queue_revision": baseline_queue_revision,
                "state_revision": baseline_state_revision,
            },
            "triggered": {
                "asset_id": risk.asset_id,
                "score_0_100": risk.score_0_100,
                "level": risk.level,
                "confirmation_frames": risk.confirmation_frames,
                "risk_revision": node.risks.risk_revision,
                "queue_revision": node.tasks.queue_revision,
                "state_revision": node.tasks.state_revision,
                "first_task_asset_id": node.tasks.tasks[0].asset_id,
                "transition_reason_code": node.tasks.transition_reason_code,
            },
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print("phase5-6-pipeline: PASS", flush=True)
        return 0
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
