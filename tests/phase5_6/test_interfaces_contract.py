from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "ros2_ws/src/substation_interfaces"


def test_phase5_6_interfaces_are_generated_ros_definitions() -> None:
    assert (PACKAGE / "CMakeLists.txt").is_file()
    assert (PACKAGE / "package.xml").is_file()
    for relative in (
        "msg/RunContext.msg", "msg/AssetRisk.msg", "msg/AssetRiskArray.msg",
        "msg/RiskAlert.msg", "msg/InspectionTask.msg", "msg/InspectionTaskArray.msg",
        "msg/ManualVelocityCommand.msg", "msg/ManualVelocityStatus.msg",
        "srv/EmergencyStop.srv", "srv/ResetEmergencyStop.srv", "srv/ManageMission.srv",
        "srv/PrioritizeAsset.srv", "srv/ReplanMission.srv", "action/ExecuteInspection.action",
        "srv/RecordRunTimeMapping.srv", "srv/QueryRunTimeMapping.srv",
        "srv/StoreEvidence.srv", "srv/FreezeEvidence.srv", "srv/QueryEvidence.srv",
        "srv/ReadEvidenceChunk.srv", "srv/GetReportingReadiness.srv",
        "srv/GenerateReport.srv", "srv/GenerateDiagnosticBundle.srv",
    ):
        assert (PACKAGE / relative).is_file(), relative
    cmake = (PACKAGE / "CMakeLists.txt").read_text(encoding="utf-8")
    for service in (
        "RecordRunTimeMapping", "QueryRunTimeMapping", "StoreEvidence",
        "FreezeEvidence", "QueryEvidence", "ReadEvidenceChunk",
        "GetReportingReadiness", "GenerateReport", "GenerateDiagnosticBundle",
    ):
        assert f'"srv/{service}.srv"' in cmake


def test_phase5_6_sources_do_not_consume_truth_or_placeholder_topics() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for package in ("substation_digital_twin", "substation_risk", "substation_mission")
        for path in (ROOT / "ros2_ws/src" / package / package).rglob("*.py")
    )
    assert "/simulation/scenario_truth" not in source
    assert "/perception/development/" not in source
