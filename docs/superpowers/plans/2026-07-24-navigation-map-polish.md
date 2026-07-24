# Navigation and Map Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复自动巡检导航目标互相取消，并用真实 Nav2 规划、实际轨迹和十台设备轮廓重做二维地图叠加层。

**Architecture:** MissionRuntime 负责恢复期状态归一化，TaskManagerNode 只在显式替换时取消活动动作。Gateway 将 `/plan` 投影进地图快照，前端纯函数负责设备轮廓和标签布局。

**Tech Stack:** ROS 2 Jazzy、rclpy、Nav2、FastAPI Gateway、React 19、Next.js 16、SVG/Canvas。

## Global Constraints

- 任意时刻最多一个巡检任务为 active。
- 地图路径必须来自 `/plan` 或机器人实际位姿，不得由静态目标直线伪造。
- 全部十台设备必须具有可区分的轮廓和编号。
- 不使用 Playwright；采用自动契约测试与用户人工验收。

---

### Task 1: 单目标任务调度

**Files:**
- Modify: `ros2_ws/src/substation_mission/substation_mission/mission_node.py`
- Test: `ros2_ws/src/substation_mission/test/test_mission_node.py`

- [x] 写失败测试：活动执行目标存在时周期分发不取消；恢复快照把 active 恢复为 queued；反馈不会留下多个 active。
- [x] 运行目标测试确认失败。
- [x] 实现显式替换、单 active 和恢复归一化。
- [x] 运行 mission 测试确认通过。

### Task 2: 真实 Nav2 路径投影

**Files:**
- Modify: `ros2_ws/src/substation_web_gateway/substation_web_gateway/app.py`
- Modify: `ros2_ws/src/substation_web_gateway/substation_web_gateway/ros_adapter.py`
- Test: `tests/gateway/test_ros_adapter.py`

- [x] 写失败测试：合法 `map` Path 写入地图快照，错误坐标系和非有限点被拒绝。
- [x] 运行测试确认失败。
- [x] 订阅 `/plan` 并投影为 `planned_path`。
- [x] 运行 Gateway 全套测试。

### Task 3: 地图叠加层与滚动条

**Files:**
- Create: `web/frontend/app/map-presentation.mjs`
- Modify: `web/frontend/app/page.js`
- Modify: `web/frontend/app/globals.css`
- Modify: `web/frontend/scripts/test-contract.mjs`

- [x] 写失败契约：十台设备轮廓、标签避让、规划路径、实际轨迹和黑色滚动条。
- [x] 运行前端测试确认失败。
- [x] 实现设备 footprint、标签布局、规划/轨迹双路径并调整样式。
- [x] 运行前端测试和生产构建。

### Task 4: 集成验证与发布

**Files:**
- Verify only.

- [ ] 运行 ROS、Gateway、前端相关测试和 `git diff --check`。
- [ ] 提交并推送 `main`。
- [ ] 构建不可变 release，并交付一条激活命令。
