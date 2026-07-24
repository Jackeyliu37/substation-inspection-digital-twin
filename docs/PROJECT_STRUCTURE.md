# 项目结构

本文是仓库目录的导航页。源代码、受控配置和验证入口进入 Git；构建产物、虚拟环境、运行数据库、rosbag2 和大部分 evidence 位于 Git 外的服务器受控目录。

## 顶层目录

```text
.
├── ros2_ws/src/       ROS 2 接口、仿真、感知、孪生、风险、任务、报告、Gateway
├── web/frontend/      Next.js/React 控制中心（八个工作区）
├── configs/            设备、风险权重、任务排序、仪表 OpenCV 配置
├── datasets/           数据集入口、manifest 和生成说明（不放公开原始数据）
├── models/             模型接纳规则、manifest 和模型说明
├── artifacts/          用户上传的 Phase 4 模型 handoff 与导入报告
├── deploy/              systemd、Nginx 和 Foxglove 只读部署配置
├── scripts/             环境、构建、导入、验证、安全停止和发布辅助脚本
├── tests/               环境、世界、导航、感知、风险任务、Gateway、部署和数据契约
├── docs/                架构、接口、部署、验收、状态、交接、ADR 和计划差异
├── requirements*.lock   Python/Web 依赖锁与 provenance
└── AGENTS.md            执行规则、文档优先级和安全边界
```

## ROS 2 包

| 包 | 职责 |
|---|---|
| `substation_interfaces` | RunContext、风险、任务、手动控制、急停、报告等 ROSIDL 契约 |
| `substation_description` | TurtleBot3 与变电站设备 URDF/语义描述 |
| `substation_gazebo` | Gazebo 世界、资产、传感器、地图、场景事件和无头启动 |
| `substation_perception` | YOLO 推理边界、图像背压、检测消息和开发占位管线 |
| `substation_digital_twin` | 设备 ID、语义状态和来源边界 |
| `substation_risk` | 多模态风险评分、连续确认、滑动平均、滞回和告警 |
| `substation_mission` | 任务队列、SQLite 持久化、Nav2 执行、速度仲裁和急停 |
| `substation_reporting` | 时间映射、内容寻址 evidence、报告/诊断 artifact 和索引 |
| `substation_web_gateway` | rclpy 适配、FastAPI REST、WebSocket、命令终态和下载边界 |

## Web 与部署

```text
web/frontend/app/              页面和控制中心 UI
web/frontend/scripts/           前端契约测试
deploy/systemd/                 Gateway、前端、Foxglove unit
deploy/nginx/                   LAN 唯一反向代理片段
deploy/foxglove/                只读 topic allowlist
```

浏览器 → Nginx → `127.0.0.1:3000`（前端）或 `127.0.0.1:8000`（Gateway）；浏览器和 Nginx 不接触 ROS DDS。

## 数据、模型与运行时目录

仓库内保存身份和校验信息：

```text
datasets/manifest.yaml
models/manifest.yaml
artifacts/phase4/substation_yolo_runs.zip
```

服务器运行时保存本体和可变证据：

```text
/var/lib/substation/models/production/<sha256>/
/var/lib/substation/datasets/synthetic/<generator>/<generation>/
/var/lib/substation/sqlite/{mission,gateway,evidence}.sqlite3
/var/lib/substation/evidence/ /var/lib/substation/reports/
/var/lib/substation/diagnostics/ /var/lib/substation/rosbag2/
/opt/substation/releases/<git-commit>
/opt/substation/current -> /opt/substation/releases/<git-commit>
```

`build/`、`install/`、`log/`、`.venv*`、`node_modules/` 和 `.next/` 是本机生成物，不是源码入口。生产 release 不应从开发检出目录直接启动。

## 从哪里开始

1. 先读 [项目计划](../基于数字孪生与多模态风险感知的变电站智能巡检系统_项目计划.md) 和 [AGENTS.md](../AGENTS.md)。
2. 按 [ARCHITECTURE.md](ARCHITECTURE.md) 理解边界，按 [INTERFACES.md](INTERFACES.md) 修改 ROS/Web 契约。
3. 使用 [TEST_ACCEPTANCE.md](TEST_ACCEPTANCE.md) 的命令验证，使用 [PROJECT_STATUS.md](PROJECT_STATUS.md) 判断当前事实。
4. 部署或人工验收时只按 [DEPLOYMENT.md](DEPLOYMENT.md) 的 release、systemd、Nginx 和安全停止流程执行。
