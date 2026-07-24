const ACTIVE_MISSION_STATES = new Set(["ready", "running", "paused", "stopping"]);
const STARTABLE_MISSION_STATES = new Set(["idle", "ready", "stopped", "succeeded", "failed"]);

export function needsMissionStop(robot, mission) {
  return Boolean(robot?.emergency_stop?.latched && ACTIVE_MISSION_STATES.has(mission?.state));
}

export function needsMissionStart(mission) {
  return !mission?.state || STARTABLE_MISSION_STATES.has(mission.state);
}

export function needsAutonomousMode(robot) {
  return robot?.mode !== "autonomous";
}

export function recoverySteps(robot, mission) {
  const steps = [];
  const stopFirst = needsMissionStop(robot, mission);
  if (stopFirst) steps.push("stop");
  if (robot?.emergency_stop?.latched) steps.push("reset");
  if (stopFirst || needsMissionStart(mission)) {
    steps.push("start");
  } else if (mission?.state === "paused") {
    steps.push("resume");
  }
  if (needsAutonomousMode(robot)) steps.push("autonomous");
  return steps;
}
