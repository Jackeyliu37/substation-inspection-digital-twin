# 系统架构

## 1. 范围、权威与边界

本文固定项目的组件边界、进程放置、数据流和运行降级方式；接口字段、QoS 和 HTTP/WebSocket 契约由 `docs/INTERFACES.md` 定义，版本由 `docs/VERSION_MATRIX.md` 锁定。项目计划是范围和最终架构的唯一事实来源；已接受的具体决定见 [ADR](adr/)。

运行环境是 Ubuntu 24.04 服务器。ROS 2 Jazzy、Gazebo Harmonic（`gz-sim 8.x`；精确锁定见 `docs/VERSION_MATRIX.md`）、GPU 推理、SQLite、FastAPI、Next.js 和 Nginx 都在服务器上运行。普通操作员只使用 `http://ros-server/`。产品 Web UI 的全部状态读取和控制都经 FastAPI ROS Web Gateway；Foxglove Web 则仅经服务器 Foxglove Bridge 走独立的只读开发诊断路径，不是日常操作路径，不能发布命令或 Topic，浏览器从不直接连接 ROS DDS。

## 2. 边界、所有权与依赖方向

| 组件 / 对应包 | 责任与拥有的状态 | 只可依赖 / 向下游输出 |
|---|---|---|
| `substation_description` | 版本控制的机器人、传感器和设备 URDF/Xacro；稳定 `asset_id`、类别、坐标、阈值、巡检点和报告名称的静态定义 | 被 Gazebo、TF 和数字孪生读取；不拥有运行时传感器或风险状态 |
| `substation_gazebo` | Harmonic `gz-sim 8.x` SDF 世界、OGRE2/EGL 无头物理与传感器仿真、可重复场景事件和仿真真值 | 使用描述与配置，发布原始 RGB、LiDAR、温度、烟雾/气体和仿真状态；真值仅供场景控制、验收和证据，绝不进入感知推理 |
| SLAM / Nav2 | 地图、定位、路径和导航执行状态 | 消费 LiDAR、TF、地图与经任务管理器验证的目标；不决定风险优先级 |
| `substation_perception` | 安全检测、设备检测、缺陷分类、仪表读数和传感归一化的推理结果与置信度 | 消费传感器和模型/配置，向数字孪生输出观测；四个模块保持独立，仪表训练数据只来自 Gazebo 合成数据 |
| `substation_digital_twin` | 每个 `asset_id` 的语义运行状态、观测关联、设备状态快照和时间序列 | 消费描述、感知和归一化传感数据；向风险、任务、报告和 Gateway 输出语义状态，不控制机器人 |
| `substation_risk` | 风险构成、连续帧确认、滑动平均、滞回、告警和风险等级 | 消费数字孪生、感知与传感数据及 `risk_weights.yaml`；向任务、报告和 Gateway 输出派生风险，权重不得硬编码 |
| `substation_mission` | 巡检任务队列、优先级、模式、导航目标、重规划、恢复/跳过和紧急停止状态 | 消费风险、数字孪生和操作命令，调用 Nav2；向 Gateway 与报告输出任务状态。它不直接修改风险或传感器数据 |
| `substation_reporting` | 可追溯巡检记录、图表、HTML/PDF 报告内容和报告生成状态 | 消费已确认的数字孪生、风险、任务与证据引用；将报告交给证据存储，不重新解释原始传感器数据 |
| 证据存储 | `/var/lib/substation` 内的 SQLite、证据帧/清单、报告和 rosbag2 的持久化与校验 | 为数字孪生、风险、任务、报告和 Gateway 提供受控持久化；物理文件与数据库事务由它拥有，Git 只保存脚本、manifest 和校验值 |
| `substation_web_gateway` | ROS `rclpy` 适配、状态聚合/限频、单位转换、JPEG 编码、REST/WebSocket、命令校验和 `command_id` 生命周期 | 消费 ROS 状态并调用任务/导航安全接口和证据存储；只监听本机回环地址，是唯一的产品 Web UI—ROS 状态与控制边界 |
| Next.js 前端 | 页面路由、当前 UI 状态、Three.js 数字孪生渲染、REST 快照与 WebSocket 流展示 | 只依赖 Nginx 代理的 Gateway；不保存长期历史、不含 ROS 客户端、不能绕过 Gateway 控制机器人 |
| Nginx | 对 LAN 暴露唯一的 `http://ros-server/` 入口，反向代理 `/api` 和 `/ws` 到回环服务 | 依赖本机 Gateway 和前端；不承载 ROS、SQLite 或业务状态 |
| Foxglove Bridge / Foxglove Web | Foxglove Bridge 在服务器侧读取 ROS 数据，开发者在浏览器中诊断 Topic、TF、地图和图像 | 独立只读诊断旁路；浏览器只连接 Bridge、不直连 DDS，不能发布命令或 Topic，不能成为普通操作员控制路径，也不替代 Gateway、前端或证据记录 |

依赖只能从世界与静态定义流向感知、语义状态、风险、任务、Web/报告；反向影响只能通过明确的任务命令、场景控制或配置装载发生。数字孪生是运行时资产状态的唯一语义所有者，风险是唯一风险等级所有者，任务管理器是唯一任务队列与 Nav2 目标所有者。Gateway 和前端是适配层，不复制这些业务所有权。

## 3. 进程放置

| 服务器进程组 | 进程内容 | 网络边界 |
|---|---|---|
| 仿真与 ROS 核心 | Gazebo、机器人描述/TF、SLAM、Nav2、感知、数字孪生、风险、任务和报告 ROS 节点 | DDS 仅在服务器 ROS 域内；不暴露给浏览器 |
| 持久化 | SQLite 和证据/报告/rosbag2 文件 | 本机文件系统；没有独立数据库网络端口 |
| Web Gateway | FastAPI/Uvicorn 加载 `rclpy` | 仅 `127.0.0.1`；由 Nginx 代理 |
| Web 前端 | Next.js 生产服务 | 仅 `127.0.0.1`；由 Nginx 代理 |
| 入口 | Nginx | LAN 的 TCP/80，提供 `http://ros-server/`、`/api/` 和 `/ws/` |
| 诊断 | Foxglove Bridge 与浏览器 Foxglove Web | Bridge 在服务器侧读取 DDS，浏览器只读连接 Bridge；仅开发/排错时启用，与日常 Web 入口和产品控制面分离 |

## 4. 主数据流与控制流

```text
Gazebo Harmonic gz-sim 8.x (OGRE2/EGL, headless)
  ├─ RGB ────────────────> 感知：安全 / 设备 / 缺陷 / 仪表
  ├─ 温度、烟雾/气体 ────> 归一化感知 ─┐
  ├─ LiDAR ──────────────> SLAM / Nav2 │
  └─ 场景真值 ───────────> 场景验收与证据（不进推理）
                                           v
描述静态资产 ───────────────────────> 数字孪生 ──> 风险 ──> 任务 ──> Nav2
                                           │            │         │
                                           └─────> 证据存储 <──────┘
                                                        │
ROS 状态 / 命令 <── FastAPI Gateway <── Nginx <── Next.js <── Windows 浏览器
ROS 诊断数据（只读）<── 服务器 Foxglove Bridge <── Foxglove Web 开发者浏览器
```

Gateway 以 REST 提供产品 Web UI 快照和命令受理，以 WebSocket 提供实时遥测、事件和 JPEG 图像。产品浏览器控制请求首先经过 Gateway 的验证、模式检查和命令生命周期；任务管理器才可创建或修改 Nav2 任务。紧急停止保留 Gateway 到 ROS 安全控制接口的优先路径：取消导航、发送零速度、锁存停止，且必须显式复位后才可恢复。Foxglove Web 只经服务器 Foxglove Bridge 读取诊断数据；它没有命令或 Topic 发布路径，且客户端浏览器不连接 DDS。

## 5. 降级模式与安全行为

| 故障或不可用组件 | 可继续的能力 | 强制降级与恢复条件 |
|---|---|---|
| EGL/OGRE2 或 Gazebo 启动失败 | 已存历史、报告和系统诊断仍可经 Web 查看 | 不启动仿真巡检；Gateway 报告不可用。先检查 NVIDIA 驱动、EGL、OGRE2 和无头传感器日志，禁止以桌面或虚拟显示栈规避 |
| 单个视觉模块或视频流失败 | 温度、烟雾/气体、已有语义状态和其他独立感知模块继续参与风险 | 在资产状态中标出缺失视觉来源，视觉项不伪造为正常；降低视频帧率或停止该相机订阅，修复后经健康检查重新接入 |
| 数字孪生或风险引擎失败 | 原始诊断和历史可读；紧急停止仍可用 | 暂停自动任务创建与风险驱动重排，任务状态标记为降级；恢复一致快照后才允许自动巡检 |
| Nav2 或任务管理器失败 | 监测、告警、报告与历史仍可用 | 禁止新的普通移动命令；Gateway 紧急停止仍执行零速度/取消可见导航，人工经开发诊断确认后恢复 |
| 证据存储或 SQLite 写入失败 | 实时只读遥测可展示，紧急停止保持可用 | 显示“不可审计”状态，拒绝需要新审计记录的开始/继续巡检和报告生成；恢复持久化和一致性检查后解除 |
| Gateway、WebSocket 或前端失败 | ROS 核心可继续已接受的自治任务；服务器 SSH/ROS CLI 仅用于开发恢复 | 浏览器 5 秒无心跳时禁用普通控制；WebSocket 恢复后先 REST 快照再续流。视频/三维/图表单独失败不得影响紧急停止和基础任务控制 |
| Nginx 不可用 | 本机回环服务可由运维检查，ROS 核心不受影响 | `http://ros-server/` 暂不可用；修复 Nginx 后执行 Gateway/前端回环健康检查，绝不改为浏览器直连 ROS DDS |
| Foxglove 不可用 | 日常 Web、ROS 核心和证据链不受影响 | 仅失去开发诊断；不影响任务或操作员入口 |

资源不足时训练与仿真分时运行，优先降低非关键传感器和 Web 视频更新频率；风险确认、紧急停止和证据可追溯性不通过静默丢弃来降级。

## 6. 关联决定

- [ADR-0001：OGRE2/EGL 无头 Gazebo](adr/0001-headless-gazebo.md)
- [ADR-0002：服务器集中部署与统一 Web 入口](adr/0002-server-web-deployment.md)
- [ADR-0003：独立多模型感知](adr/0003-multimodel-perception.md)
