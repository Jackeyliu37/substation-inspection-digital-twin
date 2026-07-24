# Acceptance Visual and Navigation Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复巡检重规划与场景竞态，并完善三维、地图、视频和模型效果验收界面。

**Architecture:** 后端只修复两个已定位的状态机边界；前端把可测试的相机与地图运算放入独立模块，页面组件只负责渲染。训练展示素材从既有归档机械提取，不引入网络或新依赖。

**Tech Stack:** ROS 2 Jazzy、Python 3.12、FastAPI、Next.js 16、React 19、React Three Fiber、Three.js。

## Global Constraints

- 不新增 npm 或 Python 依赖。
- 不使用 Playwright，采用契约测试、构建测试和真实运行探测。
- 所有生产控制仍只经 Gateway REST/WebSocket 契约。
- 训练展示素材必须来自 `artifacts/phase4/substation_yolo_runs.zip`。

---

### Task 1: 稳定任务队列

**Files:**
- Modify: `ros2_ws/src/substation_mission/substation_mission/mission_engine.py`
- Test: `ros2_ws/src/substation_mission/test/test_mission_engine.py`

- [ ] 添加“相同风险快照不触发重排”的失败测试。
- [ ] 运行定向测试确认因重复快照仍返回 `True` 而失败。
- [ ] 仅在风险字段或任务顺序实际变化时返回 `True`。
- [ ] 运行任务引擎和任务节点测试。

### Task 2: 消除场景终态竞态

**Files:**
- Modify: `ros2_ws/src/substation_web_gateway/substation_web_gateway/ros_adapter.py`
- Test: `tests/gateway/test_ros_adapter.py`

- [ ] 添加参数服务回调期间投影版本前进的失败测试。
- [ ] 确认 `dispatch_scenario` 错误返回调用后的版本。
- [ ] 改为返回调用前捕获的场景版本。
- [ ] 运行 Gateway 测试。

### Task 3: 三维、地图与感知界面

**Files:**
- Create: `web/frontend/app/twin-camera.mjs`
- Modify: `web/frontend/app/map-utils.mjs`
- Modify: `web/frontend/app/page.js`
- Modify: `web/frontend/app/globals.css`
- Modify: `web/frontend/scripts/test-contract.mjs`
- Create: `web/frontend/public/model-showcase/*`

- [ ] 先扩展前端契约，覆盖轨道相机、等比地图、视频旋转、场景效果、四组轮播和删除豁免文案。
- [ ] 运行 `npm --prefix web/frontend test` 确认失败。
- [ ] 实现最小功能并从训练 zip 提取 12 张预测图。
- [ ] 运行前端契约和 production build。

### Task 4: 集成与发布

**Files:**
- Modify: `docs/superpowers/specs/2026-07-24-acceptance-visual-navigation-fixes-design.md`（仅在验证揭示歧义时）

- [ ] 运行 Mission、Gateway、前端和集成测试。
- [ ] 提交并推送 `main`。
- [ ] 构建 release，交付单条 sudo 激活命令。
- [ ] 激活后验证连续导航、连续场景、地图、视频与模型素材。
