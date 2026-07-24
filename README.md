# 变电站智能巡检数字孪生

基于 ROS 2、Gazebo 和多模态风险感知的变电站智能巡检系统。项目在 Ubuntu 24.04 服务器上运行无头 Gazebo 仿真，使用 TurtleBot3 Waffle Pi 执行巡检，通过设备语义状态、视觉检测、仪表读数和温度/烟雾/气体等传感信息计算风险，并由 Nav2 和任务管理器调整巡检顺序。Windows 端只需要浏览器访问统一 Web 入口。

> 当前仓库是“可验证开发检查点”，不是已经启动的生产服务。Phase 8/9 的构建、契约和静态部署检查已完成；真实服务启动、Windows 局域网和完整演示由操作员人工验收。

## 项目状态

| 范围 | 当前状态 |
|---|---|
| Phase 0～3 | 环境、Gazebo 世界、合成仪表数据和导航已有 immutable evidence |
| Phase 4 | 四个用户训练结果已上传并导入；安全模型 `mAP50=0.69297` 低于 `0.75` 门槛，按明确 operator waiver 记录 |
| Phase 5～6 | 风险重排、任务持久化、Nav2 执行、速度仲裁和报告/证据服务已有测试与 live 检查点 |
| Phase 7 | ROS Gateway、状态聚合、控制命令、命令终态、报告索引和下载契约已验证；真实相机帧仍待接入验收 |
| Phase 8 | 八个前端工作区、REST/WebSocket 边界、`npm test` 和生产构建已通过 |
| Phase 9 | systemd/Nginx/Foxglove/safe-stop 静态契约已通过；未启动生产服务，待人工集成验收 |

完整差异清单见 [`docs/PLAN_GAP_ANALYSIS.md`](docs/PLAN_GAP_ANALYSIS.md)，当前事实以 [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md) 为准。

## 模型训练结果是否已上传

已上传。Git 中的交付包为 [`artifacts/phase4/substation_yolo_runs.zip`](artifacts/phase4/substation_yolo_runs.zip)，SHA-256 为 `fae3721cbe65b9fa09f24972ab36a5c45df54d0a9f97fa7e9d5cb87e619235ce`，大小 `83,036,921` 字节。导入和校验记录位于 [`models/manifest.yaml`](models/manifest.yaml) 与 [`artifacts/phase4/model-import-report.json`](artifacts/phase4/model-import-report.json)。四个逻辑模型均已建立 production artifact 映射：

| 逻辑模型 | 任务 | 结果 | 备注 |
|---|---|---:|---|
| `yolo11n_safety` | 安全检测 | mAP50 `0.69297` | 低于 `0.75`，仅按 operator waiver 纳入，不是严格达标 |
| `yolo11n_equipment` | 15 类设备检测 | mAP50 `0.84187` | 达到文档门槛 |
| `yolo11n_fault` | 缺陷分类 | accuracy top-1 `0.99673` | 计划未规定数值下限，保留训练摘要 |
| `meter_locator` | 仪表定位 | mAP50 `0.99500` | OpenCV 读数下游仍需完整运行验收 |

权重本体在服务器 `/var/lib/substation/models/production/<sha256>/` 保存；仓库提交 ZIP、manifest、指标和训练配置摘要，不把训练目录拆成散落文件。四个模型的完整 ROS 15 FPS/300 秒、仪表 OpenCV 读数和严格安全指标复验尚未完成。

## 文档入口

- [项目计划](基于数字孪生与多模态风险感知的变电站智能巡检系统_项目计划.md)：范围、阶段、技术栈、验收指标和完成定义的上游事实来源。
- [项目结构](docs/PROJECT_STRUCTURE.md)：源码、配置、模型、数据、部署和测试目录的职责说明。
- [计划差异清单](docs/PLAN_GAP_ANALYSIS.md)：按 Phase 0～9 标记已完成、部分完成、待人工验收和明确缺口。
- [架构](docs/ARCHITECTURE.md)：组件边界、数据流和 ROS/Web 分层。
- [接口契约](docs/INTERFACES.md)：ROS、REST、WebSocket、命令终态和错误语义。
- [部署手册](docs/DEPLOYMENT.md)：release、systemd、Nginx、网络边界、安全停止和回滚。
- [数据与模型治理](docs/DATA_AND_MODELS.md)：数据来源、许可、训练交付、类别映射和模型接纳规则。
- [测试与验收](docs/TEST_ACCEPTANCE.md)：可执行测试、证据目录、人工浏览器验收和性能门槛。
- [版本矩阵](docs/VERSION_MATRIX.md)：ROS、Gazebo、Python、CUDA、Node 和前端依赖锁定。
- [当前状态](docs/PROJECT_STATUS.md) / [交接入口](docs/HANDOFF.md)：本机验证事实、运行限制和恢复命令。
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

## 本机开发检查

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

本机当前未运行 Gazebo、ROS 项目节点、Gateway、Next.js、Nginx 或 Foxglove 产品服务。不要把上述构建检查误当成部署成功。

## 如何启动

### 生产/人工集成验收

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

- 公开数据下载和模型微调在仓库外完成；仓库只接收有固定身份、manifest、指标和 SHA-256 的模型交付。
- 不把真实设备控制、远程桌面、DDS 直连、公网访问或多租户权限混入本期范围。
- 每次阶段收口都应更新状态/交接文档，运行测试后再提交；大文件和可变运行证据放在服务器受控目录。
- 如需确认剩余工作，先查看 [`docs/PLAN_GAP_ANALYSIS.md`](docs/PLAN_GAP_ANALYSIS.md)，其中列出了需要操作员决定的项目。
