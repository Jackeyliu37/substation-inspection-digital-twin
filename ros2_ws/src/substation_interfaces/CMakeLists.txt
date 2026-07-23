cmake_minimum_required(VERSION 3.8)
project(substation_interfaces)

find_package(ament_cmake REQUIRED)
find_package(builtin_interfaces REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(std_msgs REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/RunContext.msg"
  "msg/ManualVelocityCommand.msg"
  "msg/ManualVelocityStatus.msg"
  "msg/AssetRisk.msg"
  "msg/AssetRiskArray.msg"
  "msg/RiskAlert.msg"
  "msg/AlertAcknowledgement.msg"
  "msg/InspectionTask.msg"
  "msg/InspectionTaskArray.msg"
  "srv/ManageMission.srv"
  "srv/QueueNavigationGoal.srv"
  "srv/EmergencyStop.srv"
  "srv/ResetEmergencyStop.srv"
  "srv/SetRobotMode.srv"
  "srv/PrioritizeAsset.srv"
  "srv/ReplanMission.srv"
  "srv/RequestReinspection.srv"
  "srv/AcknowledgeAlert.srv"
  "action/ExecuteInspection.action"
  DEPENDENCIES builtin_interfaces geometry_msgs std_msgs
)

ament_export_dependencies(rosidl_default_runtime)
ament_package()
