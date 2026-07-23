# 系统架构

## 1. 范围、权威与边界

本文固定组件边界、进程放置、数据流、持久化单写者和运行降级方式；部署细节由 [DEPLOYMENT](DEPLOYMENT.md) 约束，接口字段、QoS 和 HTTP/WebSocket 契约由 [INTERFACES](INTERFACES.md) 约束，版本由 [VERSION_MATRIX](VERSION_MATRIX.md) 锁定。项目计划是范围和最终架构的唯一事实来源；已接受的具体决定见 [ADR](adr/)。

运行环境是 Ubuntu 24.04 服务器。ROS 2 Jazzy、Gazebo Harmonic（release series 固定为 `gz-sim 8.x`；实际安装的完整 Debian revisions 由环境清单内容锁定）、GPU 推理、SQLite、FastAPI、Next.js 和 Nginx 都在服务器上运行。`ROS_LOCALHOST_ONLY=1`。普通操作员只使用 `http://ros-server/`；产品 Web UI 的全部状态读取和控制都经 FastAPI ROS Web Gateway。Foxglove Web 仅在维护窗口经服务器 Foxglove Bridge 走独立只读诊断路径，不能发布 Topic、调用 Service 或发送 Action goal，浏览器从不直接连接 ROS DDS。

## 2. 边界、所有权与依赖方向

| 组件 / 对应包 | 责任与拥有的状态 | 只可依赖 / 向下游输出 |
|---|---|---|
| `substation_description` | 版本控制的机器人、传感器和设备 URDF/Xacro；稳定 `asset_id`、类别、坐标、阈值、巡检点和报告名称 | 被 Gazebo、TF 和数字孪生读取；不拥有运行时传感器或风险状态 |
| `substation_gazebo` | Harmonic `gz-sim 8.x` SDF 世界、OGRE2/EGL 无头物理与传感器仿真、可重复场景事件和仿真真值 | 发布原始 RGB、LiDAR、温度、烟雾/气体和仿真状态；真值只供场景控制、验收和证据，绝不进入感知推理 |
| SLAM / Nav2 | 地图、定位、路径和导航执行状态 | 消费 LiDAR、TF、地图与经任务管理器验证的目标；不决定风险优先级 |
| `substation_perception` | 四个独立模块：安全检测、设备检测、缺陷分类、仪表模块（YOLO 表盘定位器加 OpenCV 读数后处理），以及传感归一化 | 消费传感器和模型/配置，向数字孪生输出观测；仪表训练与评估数据只来自 Gazebo 合成数据 |
| `substation_digital_twin` | 每个 `asset_id` 的语义运行状态、观测关联、设备状态快照和时间序列 | 消费描述、感知和归一化传感数据；向风险、任务、报告和 Gateway 输出语义状态，不控制机器人 |
| `substation_risk` | 风险构成、连续帧确认、滑动平均、滞回、告警及告警确认状态 | 消费数字孪生、感知与传感数据及 `risk_weights.yaml`；向任务、报告和 Gateway 输出派生风险 |
| `substation_mission` | RunContext、巡检任务队列、优先级、机器人模式、Nav2 目标、重规划、复检、恢复/跳过和紧急停止状态 | 消费风险、数字孪生和操作命令，调用 Nav2；不直接修改风险或传感器数据 |
| `substation_reporting/evidence_store` | 运行时钟映射、不可变证据、报告/诊断包索引、rosbag2 引用、最终文件事务与 `evidence.sqlite3` | 通过 ROS Service 接收存储/冻结/查询/发布请求；是证据、报告、诊断包和相应 SQLite 表的唯一最终写入者 |
| `substation_reporting/report_generator` | 从已确认的数字孪生、风险、任务和证据引用生成 HTML/PDF/evidence ZIP/诊断包暂存产物 | 只写自己的受控工作目录；完成后经 evidence store 原子提交，不直接写 `evidence.sqlite3` 或最终目录 |
| `substation_system/maintenance_supervisor` | 组件健康聚合及配置 allowlist 内非关键服务的受控重连 | 不拥有业务状态；不得重启 mission、risk、Nav2、Gazebo、Gateway、Nginx 或紧急停止链路 |
| `substation_web_gateway` | ROS `rclpy` 适配、状态聚合/限频、单位转换、JPEG 编码、REST/WebSocket、命令校验与生命周期，以及独占 `gateway.sqlite3` | 消费 ROS 状态并调用领域 Service/Action；只读查询 evidence store；不能写报告/证据表或直接调用 Nav2 |
| Next.js 前端 | 页面路由、当前 UI 状态、Three.js 数字孪生渲染、REST 快照与 WebSocket 流展示 | 只依赖 Nginx 代理的 Gateway；不保存长期历史、不含 ROS 客户端 |
| Nginx | 对 LAN 暴露唯一产品入口，按路径分支代理前端、Gateway 和维护期 Foxglove | 不承载 ROS、SQLite 或业务状态；产品路径不能绕过 Gateway |
| Foxglove Bridge / Foxglove Web | Bridge 在服务器侧只读订阅受允许的 ROS Topic/TF；开发者浏览器用于诊断 | `127.0.0.1:8765`、默认 disabled；仅维护时经 Nginx `/foxglove/` 暴露，发布/Service/Action/参数写能力全部关闭 |

依赖只能从世界与静态定义流向感知、语义状态、风险、任务、Web/报告；反向影响只能通过明确的任务命令、场景控制或配置装载发生。数字孪生是资产语义状态唯一所有者，风险是风险与告警唯一所有者，任务管理器是 RunContext、任务队列、模式和 Nav2 目标唯一所有者。Gateway 和前端是适配层，不复制业务所有权。

## 3. 持久化单写者

| 数据库 / 最终路径 | 唯一写入者 | 内容 | 其他组件访问方式 |
|---|---|---|---|
| `/var/lib/substation/sqlite/mission.sqlite3` | `substation_mission` | RunContext、mission/task、mode/latch revisions 和恢复状态 | ROS 状态 Topic/Service；其他进程不得打开写连接 |
| `/var/lib/substation/sqlite/gateway.sqlite3` | `substation_web_gateway` | command、Idempotency-Key、Web event outbox、Web map/snapshot revision | Gateway 自用；报告通过只读导出/证据引用消费 |
| `/var/lib/substation/sqlite/evidence.sqlite3` | `substation_reporting/evidence_store` | ROS-time→UTC 映射、证据 metadata、报告/诊断包索引、artifact manifest | ROS reporting Service；Gateway 和 report_generator 不直接写表 |
| `/var/lib/substation/evidence/objects` | `evidence_store` | 内容寻址的原始/冻结证据及 SHA-256 | Gateway 经 QueryEvidence 后只读下载 |
| `/var/lib/substation/reports` | `evidence_store` | 已发布 HTML/PDF/evidence ZIP | report_generator 只提交暂存产物 |
| `/var/lib/substation/diagnostics` | `evidence_store` | 已发布诊断包与 manifest | maintenance supervisor/report_generator 提交，Gateway 只读下载 |
| `/var/lib/substation/rosbag2` | `evidence_store` 受控 recorder | run-scoped rosbag2 与 metadata | 报告引用，不进入 Git |

任何迁移都必须保持单写者。禁止 Gateway 和 reporting 进程连接同一 SQLite 表进行写入；跨域关联只保存稳定 ID、revision、时间与 SHA-256。

## 4. 进程与网络放置

| 服务器进程组 | 进程内容 | 网络边界 |
|---|---|---|
| 仿真与 ROS 核心 | Gazebo、描述/TF、SLAM、Nav2、感知、数字孪生、风险、任务、reporting 和 maintenance supervisor | 统一 `ROS_LOCALHOST_ONLY=1`；DDS 不暴露给 LAN |
| 持久化 | 三个 SQLite 文件和证据/报告/诊断/rosbag2 文件 | 本机文件系统；无数据库网络端口 |
| Web Gateway | FastAPI/Uvicorn 加载 `rclpy` | 仅 `127.0.0.1:8000` |
| Web 前端 | Next.js 生产服务 | 仅 `127.0.0.1:3000` |
| 产品入口 | Nginx | LAN TCP/80，主机名 `ros-server`；唯一产品监听者 |
| 诊断 | Foxglove Bridge | 仅 `127.0.0.1:8765`，默认 disabled；维护时由 Nginx 代理 |

```text
Gazebo Harmonic gz-sim 8.x (OGRE2/EGL, headless)
  ├─ RGB ────────────────> 感知：安全 / 设备 / 缺陷 / 仪表定位+OpenCV
  ├─ 温度、烟雾/气体 ────> 归一化感知 ─┐
  ├─ LiDAR ──────────────> SLAM / Nav2 │
  └─ 场景真值 ───────────> 场景验收与证据（不进推理）
                                           v
描述静态资产 ───────────────────────> 数字孪生 ──> 风险 ──> 任务 ──> Nav2
                                           │            │         │
                                           └────> evidence_store <─┘
                                                     ^
                                             report_generator

Windows 浏览器 ──> Nginx
                    ├─ / ───────────> Next.js 127.0.0.1:3000
                    ├─ /api、/ws ───> Gateway 127.0.0.1:8000 ──> ROS/reporting Service
                    └─ /foxglove ───> Bridge 127.0.0.1:8765（维护时、只读）
```

## 5. 降级模式与安全行为

| 故障或不可用组件 | 可继续的能力 | 强制降级与恢复条件 |
|---|---|---|
| EGL/OGRE2 或 Gazebo 启动失败 | 已存历史、报告和系统诊断仍可经 Web 查看 | 不启动仿真巡检；检查官方 NVIDIA 驱动、EGL、OGRE2 和传感器日志，禁止启用桌面/虚拟显示规避 |
| 单个视觉模块或视频流失败 | 其他三个视觉模块、环境传感器和已有语义状态继续 | 标出缺失来源，不伪造为正常；修复后经健康检查重新接入 |
| 数字孪生或风险引擎失败 | 原始诊断和历史可读；紧急停止仍可用 | 暂停自动任务创建与风险重排，恢复一致快照后才允许自动巡检 |
| Nav2 或任务管理器失败 | 监测、告警、报告与历史仍可用 | 拒绝普通移动命令；紧急停止仍取消可见 goal 并确认零速度 |
| evidence store/SQLite 写入失败 | 实时只读遥测和紧急停止可用 | `readyz` 标记审计不可用；拒绝 start/resume、冻结证据、报告和诊断包生成，恢复一致性后解除 |
| report generator 失败 | 已有证据和报告仍可读 | 新报告/诊断包失败，不影响任务控制；重连仅可通过 allowlist maintenance 命令 |
| Gateway、WebSocket 或前端失败 | ROS 核心可继续已接受自治任务 | 浏览器超过 5 秒无应用消息时禁用普通控制；恢复后先 REST 快照再续流 |
| Nginx 不可用 | 回环服务可由运维检查，ROS 核心不受影响 | `http://ros-server/` 不可用；不得改为 LAN 直连 Gateway/DDS |
| Foxglove 不可用 | 产品 Web、ROS 核心和证据链不受影响 | 仅失去维护诊断；不得改造为控制替代路径 |

资源不足时训练与仿真分时运行，优先降低非关键传感器和视频更新频率；风险确认、紧急停止和证据追溯不得静默丢弃。

## 6. 关联决定

- [ADR-0001：OGRE2/EGL 无头 Gazebo](adr/0001-headless-gazebo.md)
- [ADR-0002：服务器集中部署与统一 Web 入口](adr/0002-server-web-deployment.md)
- [ADR-0003：独立多模型感知](adr/0003-multimodel-perception.md)
- [ADR-0004：无头 NVIDIA 驱动与图形包依赖边界](adr/0004-nvidia-headless-packaging.md)
