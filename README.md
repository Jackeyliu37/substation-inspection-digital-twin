# 变电站智能巡检数字孪生

本项目在 Ubuntu 24.04 服务器上构建可重复部署的 ROS 2 变电站巡检仿真系统：TurtleBot3 Waffle Pi 在 Gazebo Harmonic 场景中自主巡检，以 YOLO11n 和模拟温度、烟雾、气体传感器生成多模态证据；系统围绕设备 ID 维护数字孪生状态，计算 0～100 风险分数，并通过任务重排序和 Nav2 重规划形成“感知—风险—行动—证据—报告”的闭环。

## 部署与访问

核心服务、源码、数据、模型、运行证据和唯一 Codex 实例均位于 Ubuntu 服务器。Gazebo 以 OGRE2/EGL 无头模式运行；Windows 和其他客户端只需现代浏览器访问 `http://ros-server/`，SSH 仅用于维护，Foxglove Web 仅用于开发诊断。浏览器通过 FastAPI ROS Web Gateway 访问 REST/WebSocket，绝不直接连接 ROS DDS。

```text
Gazebo Harmonic / 机器人传感器
  -> 感知与传感归一化
  -> 语义数字孪生与风险引擎
  -> 风险驱动任务管理器 / Nav2
  -> FastAPI ROS Web Gateway / SQLite
  -> Next.js 综合控制平台 / Nginx
  -> Windows 浏览器：http://ros-server/
```

## 文档入口

- [项目计划](./基于数字孪生与多模态风险感知的变电站智能巡检系统_项目计划.md)：范围、架构、里程碑、验收与完成定义的唯一事实来源。
- [ARCHITECTURE](./docs/ARCHITECTURE.md) 与 [DEPLOYMENT](./docs/DEPLOYMENT.md)：组件边界、数据流、服务器部署和恢复。
- [INTERFACES](./docs/INTERFACES.md)：ROS、TF、REST、WebSocket、错误码和命令确认契约。
- [TEST_ACCEPTANCE](./docs/TEST_ACCEPTANCE.md) 与 [VERSION_MATRIX](./docs/VERSION_MATRIX.md)：验证入口、阈值、证据规则和依赖锁定。
- [DATA_AND_MODELS](./docs/DATA_AND_MODELS.md)：数据许可、类别映射、合成规则、模型校验和评估。
- [ADR](./docs/adr/)：已批准且不可静默推翻的架构决定。
- [PHASE-01-ENVIRONMENT](./docs/plans/PHASE-01-ENVIRONMENT.md)：环境基线的可执行计划。
- [PROJECT_STATUS](./docs/PROJECT_STATUS.md) 与 [HANDOFF](./docs/HANDOFF.md)：当前事实、验证摘要和恢复入口。
- [AGENTS.md](./AGENTS.md)：Codex 自动加载的执行规则与文档优先级。

## 计划目录

```text
ros2_ws/src/       ROS 2 接口、仿真、感知、数字孪生、风险、任务、报告与 Gateway 包
web/frontend/      Next.js/TypeScript 综合控制平台
web/nginx/         单一 Web 地址和 WebSocket 反向代理
configs/           设备、风险权重、巡检路线和 Nav2 参数
datasets/          数据 manifest、下载与转换说明
models/            模型 manifest 和权重校验值
scripts/           安装、环境、构建、部署和验证脚本
tests/             单元、集成、场景与 Web 端到端测试
foxglove/          仅用于开发诊断的布局
docs/              架构、部署、接口、版本、验收、状态、交接与阶段计划
```

## 当前阶段

当前处于阶段 0“文档门槛”：先冻结规则、架构、接口、版本、验收、ADR、状态、交接和环境计划，再进入阶段 1“环境基线”。本阶段不安装依赖、不下载数据或模型、不启动 Gazebo/Nav2/Web 服务，也不创建功能代码。

## 只读快速检查

以下命令只检查仓库或主机状态，不安装、构建、启动或修改任何内容：

```bash
pwd
git status --short
git log -1 --oneline
find . -maxdepth 2 -type f -name '*.md' | sort
uname -a
lsb_release -ds
nvidia-smi
```
