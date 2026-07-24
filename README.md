# 变电站智能巡检数字孪生

基于 ROS 2、Gazebo 和多模态风险感知的变电站智能巡检系统。项目在 Ubuntu 24.04 服务器上运行无头 Gazebo 仿真，使用 TurtleBot3 Waffle Pi 执行巡检，通过设备语义状态、视觉检测、仪表读数和温度/烟雾/气体等传感信息计算风险，并由 Nav2 和任务管理器调整巡检顺序。Windows 端只需要浏览器访问统一 Web 入口。

## 核心能力

- OGRE2/EGL 无头 Gazebo 变电站世界、TurtleBot3 Waffle Pi、RGB/LiDAR 和环境传感器；
- 安全、设备、缺陷和仪表四条独立感知链，OpenCV 完成仪表读数后处理；
- 以设备 ID 为中心的语义数字孪生和 0～100 多模态风险评分；
- 风险驱动的任务重排、Nav2 目标替换、失败恢复、手动/自动速度仲裁和锁存急停；
- 内容寻址 evidence、rosbag2、告警/轨迹/任务记录以及 HTML/PDF 巡检报告；
- FastAPI ROS Gateway、Next.js 综合控制中心、Nginx 单一 LAN 入口和只读 Foxglove 诊断。

## 文档入口

- [项目计划](基于数字孪生与多模态风险感知的变电站智能巡检系统_项目计划.md)：范围、阶段、技术栈、验收指标和完成定义的上游事实来源。
- [项目结构](docs/PROJECT_STRUCTURE.md)：源码、配置、模型、数据、部署和测试目录的职责说明。
- [计划差异清单](docs/PLAN_GAP_ANALYSIS.md)：项目计划与当前实现的核对记录。
- [架构](docs/ARCHITECTURE.md)：组件边界、数据流和 ROS/Web 分层。
- [接口契约](docs/INTERFACES.md)：ROS、REST、WebSocket、命令终态和错误语义。
- [部署手册](docs/DEPLOYMENT.md)：release、systemd、Nginx、网络边界、安全停止和回滚。
- [数据与模型规范](docs/DATA_AND_MODELS.md)：数据来源、许可、类别映射和模型接纳规则。
- [测试与验收](docs/TEST_ACCEPTANCE.md)：可执行测试、证据目录、人工浏览器验收和性能门槛。
- [版本矩阵](docs/VERSION_MATRIX.md)：ROS、Gazebo、Python、CUDA、Node 和前端依赖锁定。
- [ADR](docs/adr/)：无头 Gazebo、服务器 Web、四模型拆分和 NVIDIA 打包决策。

## 系统架构

```text
Gazebo Harmonic（OGRE2/EGL，无 DISPLAY）
  ├─ RGB / LiDAR / 温度 / 烟雾 / 气体
  └─ 设备语义与场景事件
        ↓
ROS 2 感知 → 数字孪生 → 风险融合 → 任务重排 → Nav2
        ↓                         ↓
  reporting/evidence          FastAPI Gateway
                                      ↓
                         Nginx（唯一 LAN 入口）
                           ├─ Next.js 控制中心
                           └─ REST / WebSocket
```

浏览器只连接 Nginx；Gateway 和 Next.js 绑定 `127.0.0.1`；ROS 使用 `ROS_LOCALHOST_ONLY=1`；Foxglove 只作为默认关闭的只读诊断旁路。

## 技术栈

| 层 | 技术 |
|---|---|
| 主机 | Ubuntu 24.04 LTS、NVIDIA RTX 3060 Ti、CUDA 12.6 |
| 机器人与仿真 | ROS 2 Jazzy、Gazebo Harmonic、TurtleBot3 Waffle Pi、Nav2、SLAM Toolbox、ros_gz |
| AI 与感知 | PyTorch、Ultralytics YOLO11n、OpenCV、`vision_msgs` |
| 后端 | Python 3.12、FastAPI、Uvicorn、rclpy、SQLite |
| 前端 | Node.js 24.18.0、Next.js 16.2.11、React 19、TypeScript、Three.js、React Three Fiber、ECharts |
| 交付 | Nginx、systemd、Foxglove Bridge（只读维护）、Git、SHA-256 evidence |

## 开发检查

以下命令不会启动生产服务，适合在当前检出上复核代码和契约：

```bash
cd ~/substation-inspection-digital-twin

# ROS 工作区构建与测试
set +u
source /opt/ros/jazzy/setup.bash
source install/setup.bash
set -u
export ROS_LOCALHOST_ONLY=1
colcon build --symlink-install
colcon test --event-handlers console_direct+
colcon test-result --all --verbose

# Gateway、接口和部署契约
.venv-web/bin/python -m pytest \
  tests/gateway \
  tests/integration/test_deployment_contract.py \
  tests/phase5_6/test_interfaces_contract.py -q

# 前端契约与生产构建
npm --prefix web/frontend test
npm --prefix web/frontend run build

# 文档门禁
bash scripts/verify_documentation_gate.sh
```

这些命令只验证源码、接口和构建产物，不会启动生产服务。

## 如何启动

### 生产部署与人工集成验收

生产启动必须使用经过验证的 `/opt/substation/current` release、`substation` 服务账户和 [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) 中的启动顺序；不要直接从开发检出执行 `systemctl start`。人工验收至少确认：

1. Gazebo 无头启动且相机、LiDAR、`/clock` 就绪；
2. reporting、数字孪生、风险、感知、Nav2 和任务管理器 readiness 一致；
3. Gateway `127.0.0.1:8000`、前端 `127.0.0.1:3000`，Nginx 是唯一 LAN 入口；
4. 浏览器通过 `http://ros-server/` 完成八个工作区、任务控制、紧停、风险查看和报告下载；
5. Foxglove 默认关闭，维护时只读启用，完成后立即禁用；
6. 安全停止证据确认急停锁存、Nav2 goal 清理和速度归零。

### 仅前端本地预览

```bash
cd web/frontend
npm ci
npm run dev       # 仅绑定 127.0.0.1:3000；需要真实 Gateway 时不要把它当完整系统
```

Gateway 的正式入口会加载 ROS 环境并使用 `/var/lib/substation/sqlite`，请按部署手册通过 release wrapper 启动，不要用临时命令绕过安全边界。

## 贡献与边界

- 外部数据与模型资产按仓库的数据/模型规范接入，并通过固定身份和 SHA-256 校验。
- 不把真实设备控制、远程桌面、DDS 直连、公网访问或多租户权限混入本期范围。
- 大文件和可变运行证据放在服务器受控目录；仓库只提交源码、配置、文档和可复核的校验信息。
