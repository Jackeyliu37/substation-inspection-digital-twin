# ROS、TF、REST 与 WebSocket 接口契约

## 1. 范围与不变边界

本文固定 ROS 2 Topic/Service/Action、TF、FastAPI REST 和 WebSocket 的跨组件契约。组件状态所有权遵循 [ARCHITECTURE](ARCHITECTURE.md)：数字孪生唯一拥有资产语义状态，风险模块唯一拥有风险分数与等级，任务模块唯一拥有任务队列、机器人模式、紧急停止锁存和 Nav2 目标，Gateway 只做适配、校验、限频、命令跟踪与 Web 编码。

产品浏览器只调用 Nginx 代理的 `/api/` 和 `/ws/`；它不连接 ROS DDS，不发布 Topic，也不直接调用 ROS Service/Action。Foxglove Web 仅通过服务器 Foxglove Bridge 订阅 ROS 诊断数据，是与本文产品 API 分离的只读开发诊断旁路；Bridge 和浏览器均不得发布 Topic、调用控制 Service/Action，且 Foxglove 不得成为操作员入口、命令恢复通道或证据系统。

项目计划要求优先使用标准接口且只为风险和巡检任务定义自有接口。因此图像、激光、检测、导航、环境测量、数字孪生快照和诊断复用标准消息；`substation_interfaces` 只包含第 4 节列出的风险、巡检任务及任务安全控制接口。Gazebo 场景控制复用标准参数服务，不另建场景自定义消息。

## 2. 跨接口基础规则

### 2.1 名称与标识符

| 名称 | 格式与所有权 |
|---|---|
| `run_id` | Gateway 在每次仿真/巡检运行开始时生成的 UUID；同一证据链、rosbag2、报告和 Web 快照共享该值。 |
| `mission_id` | 任务模块生成的 UUID；一轮任务队列一个值。 |
| `task_id` | 任务模块生成的 UUID；任务重排不改变已有任务的值，创建替代任务时生成新值。 |
| `command_id` | Gateway 为每个控制尝试生成的 UUID，包括被同步拒绝的请求；用于 REST 查询和事件关联。 |
| `alert_id` | 风险模块生成的 UUID；一次从较低等级进入告警/紧急等级的事件一个值，清除事件引用同一值。 |
| `evidence_id` | 证据存储生成的 UUID；每个冻结帧、检测裁剪或其他不可变证据对象一个值。 |
| `asset_id` | `substation_description` 配置拥有的稳定字符串；正则为 `^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$`，长度 1～64，同一站点永久不复用。 |
| `route_id`、`scenario_id`、`sensor_id` | 配置拥有的稳定字符串，使用与 `asset_id` 相同的正则和长度规则。 |
| `report_id` | 报告模块生成的 UUID。 |

所有 UUID 在 ROS 自定义字段和 Web JSON 中均使用小写、带连字符的 RFC 4122/9562 规范字符串 `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`；生成方使用随机 UUIDv4。接收方不得依赖 UUID 的排序含义。ROS Topic、Service、Action 和 TF frame 使用本文件的绝对名称；ROS 消息内的 `frame_id` 不以 `/` 开头。

### 2.2 时间、时钟与排序

- ROS 内全部时间字段使用 `builtin_interfaces/Time` 或 `std_msgs/Header.stamp`，并在仿真运行中统一设置 `use_sim_time=true`，以 `/clock` 为唯一 ROS 时间源。传感器消息使用采集时间，派生消息使用计算所依据的最新输入时间；不得用发布时刻覆盖源时间。
- Gateway 为每个 `run_id` 记录 `(run_started_at_utc, run_start_ros_time)` 映射。Web 中所有名称以 `_at` 结尾的时间均是 RFC 3339 UTC 字符串，固定六位小数和 `Z`，例如 `2026-07-22T14:03:05.123456Z`。若需要审计原始 ROS 时间，另给 `source_ros_time: {"sec": int32, "nanosec": uint32}`，它不是 Web 业务排序主键。
- 同一 ROS 发布者不得倒退消息时间；同一 Web 流以 `stream_epoch` 加 `sequence` 排序，不能用墙钟时间替代序号。系统墙钟回拨不改变已分配的 `sequence` 或 `snapshot_revision`。
- `duration`、超时和速率使用单调时钟计算。零值 ROS 时间只表示“未发生/不适用”，不得表示当前时间。

### 2.3 单位与数值范围

默认使用 SI：位置/距离为 m，线速度为 m/s，角度为 rad，角速度为 rad/s，持续时间为 s，压力为 Pa。例外只有温度 `°C`、气体浓度 `ppm`、名称明确以 `_percent` 结尾的 0～100 百分数，以及名称明确以 `_0_1`/`_0_100` 结尾的闭区间归一化值。检测置信度和风险公式的 `V/T/S/G/C` 分量使用 0～1，最终风险分数使用 0～100，模拟电量使用 0～100 percent。文件/内存/帧长度属于数字计数，统一使用 byte 并以 `_bytes` 或 framing 表中的 byte offset/length 明示。

所有浮点输入必须有限，禁止 `NaN` 和正负无穷。Web 中二维导航姿态以 `x_m`、`y_m`、`yaw_rad` 表示；ROS 中使用标准 pose/quaternion，四元数范数必须在 `[0.999, 1.001]`，否则拒绝。角度规范化到 `[-pi, pi]`。

### 2.4 版本规则

- REST 的破坏性版本由路径 `/api/v1` 固定；Web JSON 的 `schema_version` 初值为字符串 `"1.0"`。同一主版本只能新增可选字段或新事件类型，不能删除字段、改变单位、缩窄既有合法范围或复用枚举值。客户端必须拒绝未知主版本，可忽略同一主版本的未知字段。
- WebSocket 子协议固定为 `substation.v1`。握手未协商该子协议时，服务器返回 HTTP 426；消息仍携带 `schema_version`，以便存档和离线验证。
- `substation_interfaces` 每个自定义定义包含 `SCHEMA_VERSION=1` 和实例字段 `schema_version`。发布者必须写 `1`，消费者遇到其他值必须拒绝该样本并上报 `INTERFACE_VERSION_UNSUPPORTED`。
- ROS 自定义定义一经进入验收基线不得原地做破坏性修改。破坏性变化必须先按项目规则新增 ADR，再创建 `V2` 类型和新 Topic/Service/Action 名称；不得在相同 ROS 类型名下悄然改变字段语义。
- 枚举值只追加不复用。持久化记录同时保存 Git commit、Web `schema_version`、ROS `schema_version` 和配置/模型校验值。

### 2.5 快照修订号

Gateway 为每个 `run_id` 维护单调递增的无符号 64 位 `snapshot_revision`。任何会改变 `/system/status`、`/robot/state`、`/assets` 或 `/missions/current` 聚合结果的提交只增加一次修订号；同一原子提交产生的多个快照使用同一值。新 `run_id` 可从 1 重新开始，因此比较键是 `(run_id, snapshot_revision)`。

所有快照 REST 响应使用第 7.1 节的统一外壳，并返回弱 ETag `W/"<run_id-or-none>:<snapshot_revision>"`。匹配的 `If-None-Match` 返回 304 且无响应体。WebSocket 数据消息携带它所基于的 `snapshot_revision`；客户端发现 run 变化、修订号倒退或不可恢复的序号缺口时，必须重新读取 REST 快照，而不是猜测差量。

### 2.6 ROS 枚举到 Web 字符串

Gateway 只做下表无损映射，不自行推导状态。未知 ROS 枚举不得映射为 normal/idle，而应拒绝该样本并上报 `INTERFACE_VERSION_UNSUPPORTED`。

| 语义 | ROS uint8 → Web string |
|---|---|
| 风险等级 | `0 → normal`，`1 → attention`，`2 → alert`，`3 → emergency` |
| 风险事件 | `0 → opened`，`1 → level_changed`，`2 → cleared` |
| Mission 状态 | `0 → idle`，`1 → ready`，`2 → running`，`3 → paused`，`4 → stopping`，`5 → succeeded`，`6 → failed`，`7 → stopped` |
| 机器人模式 | `0 → autonomous`，`1 → manual`，`2 → estop` |
| 任务类型 | `0 → inspect_asset`，`1 → navigation_goal`，`2 → return_home` |
| 任务状态 | `0 → queued`，`1 → active`，`2 → succeeded`，`3 → skipped`，`4 → failed`，`5 → cancelled` |
| 数字孪生资产状态 | `DiagnosticStatus.level 0 → normal`，`1 → attention`，`2 → fault`，`3 → stale` |
| 巡检 Action 结果 | `0 → succeeded`，`1 → stopped`，`2 → failed`，`3 → cancelled` |

## 3. ROS 2 接口

### 3.1 QoS 配置文件

下表中的 QoS 均固定 history、depth、reliability 和 durability；未列出的 deadline/lifespan 表示未设置，liveliness 均为 `AUTOMATIC`。

| 名称 | History / depth | Reliability | Durability | 额外约束 |
|---|---|---|---|---|
| `Q_CLOCK` | `KEEP_LAST / 1` | `BEST_EFFORT` | `VOLATILE` | 只用于 `/clock`。 |
| `Q_IMAGE` | `KEEP_LAST / 2` | `BEST_EFFORT` | `VOLATILE` | 允许丢旧帧，不积压图像。 |
| `Q_SENSOR` | `KEEP_LAST / 5` | `BEST_EFFORT` | `VOLATILE` | 激光和高频原始测量。 |
| `Q_STREAM` | `KEEP_LAST / 10` | `RELIABLE` | `VOLATILE` | 派生流式状态。 |
| `Q_STATE` | `KEEP_LAST / 1` | `RELIABLE` | `TRANSIENT_LOCAL` | 最新完整快照；新订阅者立即取得一份。 |
| `Q_EVENT` | `KEEP_LAST / 100` | `RELIABLE` | `VOLATILE` | 事件必须由证据存储另行持久化；DDS depth 不是历史库。 |
| `Q_CONTROL` | `KEEP_LAST / 1` | `RELIABLE` | `VOLATILE` | deadline 0.1 s，lifespan 0.25 s；过期速度不得执行。 |
| `Q_TF_DYNAMIC` | `KEEP_LAST / 100` | `RELIABLE` | `VOLATILE` | 与 tf2 动态广播/监听配置一致。 |
| `Q_TF_STATIC` | `KEEP_LAST / 1` | `RELIABLE` | `TRANSIENT_LOCAL` | 与 tf2 静态广播/监听配置一致。 |
| `Q_MAP` | `KEEP_LAST / 1` | `RELIABLE` | `TRANSIENT_LOCAL` | 完整占据地图。 |
| `Q_DIAGNOSTIC` | `KEEP_LAST / 10` | `RELIABLE` | `VOLATILE` | 1 Hz 健康状态。 |

Service 和 Action 使用 ROS 2 默认的 reliable/volatile request-response QoS；Action 状态 Topic 使用 `KEEP_LAST / 10`、`RELIABLE`、`TRANSIENT_LOCAL`。发布/订阅两端必须兼容本表，不得用全局“system default”代替测试中可检查的显式配置。

### 3.2 Topic、Service 与 Action 总表

“速率”是仿真运行时名义发布率；`事件`表示状态变化时立即发布且不轮询，`事件 + N Hz` 表示变化立即发布并以 N Hz 重发当前状态。所有节点名是逻辑所有者，实际可组合进同一进程但不能改变所有权。表内简写固定映射为：数字孪生=`substation_digital_twin`，风险=`substation_risk`，任务=`substation_mission`，报告=`substation_reporting`，Gateway=`substation_web_gateway`，证据采集/存储=架构中证据存储拥有的采集节点，检测聚合器=`substation_perception/detection_aggregator`。

| 域 | ROS 名称 | 发布者 / Server | 订阅者 / Client | 精确类型 | 速率 | QoS |
|---|---|---|---|---|---:|---|
| 时钟 | `/clock` | Gazebo `ros_gz_bridge` | 所有 `use_sim_time` 节点 | `rosgraph_msgs/msg/Clock` | 100 Hz | `Q_CLOCK` |
| 原始 RGB | `/camera/image_raw` | `substation_gazebo` 相机桥 | 四个独立感知模块、证据采集 | `sensor_msgs/msg/Image` | 15 Hz | `Q_IMAGE` |
| 相机标定 | `/camera/camera_info` | `substation_gazebo` 相机桥 | 四个独立感知模块 | `sensor_msgs/msg/CameraInfo` | 15 Hz，与图像同 stamp | `Q_SENSOR` |
| 原始 LiDAR | `/scan` | `substation_gazebo` 激光桥 | SLAM、Nav2 costmap | `sensor_msgs/msg/LaserScan` | 10 Hz | `Q_SENSOR` |
| 原始环境 | `/simulation/environment/temperature_raw` | `substation_gazebo` | `substation_perception/environment_normalizer` | `diagnostic_msgs/msg/DiagnosticArray` | 2 Hz | `Q_SENSOR` |
| 原始环境 | `/simulation/environment/smoke_raw` | `substation_gazebo` | `substation_perception/environment_normalizer` | `diagnostic_msgs/msg/DiagnosticArray` | 2 Hz | `Q_SENSOR` |
| 原始环境 | `/simulation/environment/gas_raw` | `substation_gazebo` | `substation_perception/environment_normalizer` | `diagnostic_msgs/msg/DiagnosticArray` | 2 Hz | `Q_SENSOR` |
| 仿真真值 | `/simulation/scenario_truth` | `substation_gazebo` | 仅场景验收与证据记录 | `diagnostic_msgs/msg/DiagnosticArray` | 事件 + 1 Hz | `Q_EVENT` |
| 安全检测 | `/perception/safety/detections` | `substation_perception/safety_detector` | 检测聚合器、风险、证据采集 | `vision_msgs/msg/Detection2DArray` | 15 Hz | `Q_STREAM` |
| 设备检测 | `/perception/equipment/detections` | `substation_perception/equipment_detector` | 检测聚合器、数字孪生、证据采集 | `vision_msgs/msg/Detection2DArray` | 15 Hz | `Q_STREAM` |
| 缺陷分类 | `/perception/defects/detections` | `substation_perception/defect_classifier` | 检测聚合器、数字孪生、风险、证据采集 | `vision_msgs/msg/Detection2DArray` | 15 Hz | `Q_STREAM` |
| 仪表读数 | `/perception/meters/readings` | `substation_perception/meter_reader` | 数字孪生、风险、证据采集 | `diagnostic_msgs/msg/DiagnosticArray` | 5 Hz | `Q_STREAM` |
| 聚合检测 | `/perception/detections` | `substation_perception/detection_aggregator`（只合并、不重新推理） | 数字孪生、风险、Gateway、证据采集 | `vision_msgs/msg/Detection2DArray` | 15 Hz | `Q_STREAM` |
| 带框图像 | `/perception/annotated_image` | `substation_perception/detection_aggregator` | Gateway JPEG 编码、证据采集 | `sensor_msgs/msg/Image` | 15 Hz | `Q_IMAGE` |
| 规范化环境 | `/environment/temperature` | `substation_perception/environment_normalizer` | 数字孪生、风险、Gateway、报告 | `diagnostic_msgs/msg/DiagnosticArray` | 2 Hz | `Q_STREAM` |
| 规范化环境 | `/environment/smoke` | `substation_perception/environment_normalizer` | 数字孪生、风险、Gateway、报告 | `diagnostic_msgs/msg/DiagnosticArray` | 2 Hz | `Q_STREAM` |
| 规范化环境 | `/environment/gas` | `substation_perception/environment_normalizer` | 数字孪生、风险、Gateway、报告 | `diagnostic_msgs/msg/DiagnosticArray` | 2 Hz | `Q_STREAM` |
| 数字孪生 | `/digital_twin/assets` | `substation_digital_twin` | 风险、任务、报告、Gateway | `diagnostic_msgs/msg/DiagnosticArray` | 事件 + 2 Hz | `Q_STATE` |
| 资产风险 | `/risk/assets` | `substation_risk` | 任务、报告、Gateway | `substation_interfaces/msg/AssetRiskArray` | 事件 + 5 Hz | `Q_STATE` |
| 风险事件 | `/risk/alerts` | `substation_risk` | 任务、报告、Gateway、证据存储 | `substation_interfaces/msg/RiskAlert` | 事件 | `Q_EVENT` |
| 巡检队列 | `/mission/inspection_tasks` | `substation_mission` | 报告、Gateway、证据存储 | `substation_interfaces/msg/InspectionTaskArray` | 事件 + 2 Hz | `Q_STATE` |
| 地图 | `/map` | SLAM / map server（二者按运行模式二选一） | Nav2、任务目标校验、Gateway | `nav_msgs/msg/OccupancyGrid` | 事件 + 1 Hz | `Q_MAP` |
| 里程计 | `/odom` | `substation_gazebo` 底盘桥/里程计 | 定位、Nav2、任务、Gateway | `nav_msgs/msg/Odometry` | 30 Hz | `Q_SENSOR` |
| 模拟电量 | `/battery_state` | `substation_gazebo` 电源模拟器 | 任务、Gateway、报告 | `sensor_msgs/msg/BatteryState` | 1 Hz | `Q_STREAM` |
| 动态 TF | `/tf` | 第 5 节指定的唯一 frame 所有者 | 定位、Nav2、感知、数字孪生、Gateway、Foxglove 只读 | `tf2_msgs/msg/TFMessage` | 10～30 Hz | `Q_TF_DYNAMIC` |
| 静态 TF | `/tf_static` | `robot_state_publisher` 与资产静态广播器，各自拥有不重叠子 frame | 全部 TF 消费者、Foxglove 只读 | `tf2_msgs/msg/TFMessage` | 启动/配置变化 | `Q_TF_STATIC` |
| 全局路径 | `/plan` | Nav2 planner/controller server | 任务、Gateway、证据存储 | `nav_msgs/msg/Path` | 事件，最高 5 Hz | `Q_STREAM` |
| 局部路径 | `/local_plan` | Nav2 controller server | 任务、Gateway | `nav_msgs/msg/Path` | 5 Hz | `Q_STREAM` |
| Nav2 速度 | `/cmd_vel_nav` | Nav2 controller server | 任务安全速度仲裁器 | `geometry_msgs/msg/Twist` | 最高 20 Hz | `Q_CONTROL` |
| 手动速度 | `/cmd_vel_manual` | Gateway | 任务安全速度仲裁器 | `geometry_msgs/msg/Twist` | 0～10 Hz | `Q_CONTROL` |
| 底盘速度 | `/cmd_vel` | 任务安全速度仲裁器（唯一发布者） | Gazebo 底盘控制器 | `geometry_msgs/msg/Twist` | 最高 20 Hz；停止时立即发零并以 10 Hz 保持 0.5 s | `Q_CONTROL` |
| 系统诊断 | `/diagnostics` | 所有核心组件，经诊断聚合器汇总 | Gateway、证据存储、Foxglove 只读 | `diagnostic_msgs/msg/DiagnosticArray` | 事件 + 1 Hz | `Q_DIAGNOSTIC` |
| 场景状态 | `/simulation/scenario_state` | `substation_gazebo/scenario_manager` | Gateway、证据存储 | `diagnostic_msgs/msg/DiagnosticArray` | 事件 + 1 Hz | `Q_STATE` |
| 巡检执行 | `/mission/execute_inspection` | `substation_mission/inspection_executor` Action server | `substation_mission/task_manager` Action client | `substation_interfaces/action/ExecuteInspection` | 按 Action 反馈/结果 | Action 默认 QoS |
| 导航执行 | `/navigate_to_pose` | Nav2 `NavigateToPose` Action server | 仅 `substation_mission` Action client | `nav2_msgs/action/NavigateToPose` | 按 Action 反馈/结果 | Action 默认 QoS |
| 任务控制 | `/mission/manage` | `substation_mission` Service server | Gateway | `substation_interfaces/srv/ManageMission` | 请求触发 | Service 默认 QoS |
| 合法目标 | `/mission/queue_navigation_goal` | `substation_mission` Service server | Gateway | `substation_interfaces/srv/QueueNavigationGoal` | 请求触发 | Service 默认 QoS |
| 紧急停止 | `/mission/emergency_stop` | `substation_mission` Service server | Gateway | `substation_interfaces/srv/EmergencyStop` | 请求触发 | Service 默认 QoS |
| 紧停复位 | `/mission/emergency_stop_reset` | `substation_mission` Service server | Gateway | `substation_interfaces/srv/ResetEmergencyStop` | 请求触发 | Service 默认 QoS |
| 场景控制 | `/scenario_manager/set_parameters_atomically` | `substation_gazebo/scenario_manager` 标准参数 Service server | Gateway | `rcl_interfaces/srv/SetParametersAtomically` | 请求触发 | Service 默认 QoS |

`/navigate_to_pose` 必须使用标准 Nav2 `NavigateToPose`，Gateway 不得成为其客户端。任务模块先根据 `map`、资产碰撞体、危险区和安全观察距离验证/排序目标，再调用 Nav2。`/cmd_vel_nav` 是 Nav2 输出重映射；Nav2 和 Gateway 都不得直接发布最终 `/cmd_vel`。

### 3.3 标准消息的项目内字段约束

#### 图像与检测

- `/camera/image_raw`：`header.frame_id="camera_optical_frame"`，`encoding="rgb8"`；同一帧的 CameraInfo 具有相同 stamp，标定矩阵非零且 width/height 一致。
- 三个独立视觉检测 Topic 和 `/perception/detections`：`header.frame_id="camera_optical_frame"`；`Detection2D.id` 是该检测证据的 `evidence_id`；每个 `ObjectHypothesis.class_id` 使用 `<module>/<class>`，其中 module 只能是 `safety`、`equipment` 或 `defect`，score 为 `confidence_0_1`。聚合器保留来源前缀和证据 ID，不合并四个模型。
- `/perception/annotated_image`：`encoding="rgb8"`，stamp 与生成它的原始帧一致；若一帧推理未完成则丢弃该带框帧，不得复制旧框到新图像。
- `/battery_state`：使用标准 `BatteryState.percentage` 的 0～1 比例；Gateway 只在 Web 边界换算为 `battery_percent = 100 × percentage`。其余未知电池字段使用该标准消息定义的 NaN 语义，但 Gateway 不得把 NaN 输出到 JSON。

#### `DiagnosticArray` 测量编码

环境和仪表 Topic 的 `header.stamp` 是采样时间。每个 `DiagnosticStatus` 表示一个资产上的一个传感器：`name=asset_id`，`hardware_id=sensor_id`；`level` 只表示数据质量（0 OK、1 WARN/降级、2 ERROR/无效、3 STALE），不能借用为风险等级；`message` 是稳定原因短语。`values` 必须恰好包含下表键，`run_id` 必须是当前 run UUID，数值使用十进制点和无单位字符串表示，接收方拒绝缺键、重复键或无法解析的样本。

| Topic | 必需 `KeyValue.key` | 约束 |
|---|---|---|
| `*/temperature*` | `run_id`、`value_celsius`、`confidence_0_1`、`valid` | `valid` 为 `true`/`false`；有效时温度有限、confidence 在 0～1。 |
| `*/smoke*` | `run_id`、`value_0_1`、`confidence_0_1`、`valid` | 两个数均在 0～1。 |
| `*/gas*` | `run_id`、`value_ppm`、`confidence_0_1`、`valid` | ppm 非负。 |
| `/perception/meters/readings` | `run_id`、`reading`、`unit`、`confidence_0_1`、`valid`、`evidence_id` | `unit` 必须来自资产配置，不由模型自由生成；evidence_id 为 UUID。 |

`/simulation/scenario_truth` 使用 `name=scenario_id`、`hardware_id="gazebo"`，并含 `run_id`、`active`、`scenario_revision`、`started_ros_sec`、`started_ros_nanosec`；它只供验收和证据，感知、数字孪生和风险节点不得订阅。`/simulation/scenario_state` 的同名字段是控制状态而非感知输入。

#### 数字孪生快照编码

`/digital_twin/assets` 的 `header.frame_id="map"`。每个 `DiagnosticStatus.name=asset_id`，`hardware_id=category`；level 表示资产语义状态：0 `NORMAL`、1 `ATTENTION`、2 `FAULT`、3 `STALE`。每个 status 的 `values` 必须恰好含以下键：

`run_id`、`category`、`state`、`pose_x_m`、`pose_y_m`、`pose_z_m`、`orientation_x`、`orientation_y`、`orientation_z`、`orientation_w`、`temperature_celsius`、`smoke_0_1`、`gas_ppm`、`meter_reading`、`meter_unit`、`last_observed_ros_sec`、`last_observed_ros_nanosec`、`latest_evidence_id`。

没有测量的可空值编码为空字符串；`latest_evidence_id` 为空或 UUID；`state` 必须等于第 2.6 节中 level 对应的小写字符串。pose 来自 `substation_description` 的 `map` 坐标且不能被观测节点改写。未知键在 schema 1 中视为错误，以防不同模块对同名状态作不同解释。

#### 场景控制参数

Gateway 对一次场景请求原子设置四个标准 ROS 参数：`command_id`（UUID string）、`scenario_id`（稳定配置 string）、`scenario_action`（`start`、`trigger` 或 `reset`）、`scenario_parameters_json`（UTF-8、对象型 JSON 的 RFC 8785 canonical serialization）。`scenario_manager` 只接受配置中对该场景列入 allowlist 的参数名与范围；唯一 `command_id` 使重复的相同参数提交只执行一次。

## 4. `substation_interfaces` 自定义定义

包的直接接口依赖固定为 `builtin_interfaces`、`std_msgs`、`geometry_msgs` 和 `rosidl_default_generators`。下列代码块是未来文件的完整 schema 1 内容，可直接写入对应 `.msg`、`.srv`、`.action` 文件；注释不是字段，不需要额外的隐式属性。

### 4.1 消息

`msg/AssetRisk.msg`

```text
uint32 SCHEMA_VERSION=1
uint8 LEVEL_NORMAL=0
uint8 LEVEL_ATTENTION=1
uint8 LEVEL_ALERT=2
uint8 LEVEL_EMERGENCY=3

uint32 schema_version
string asset_id
float32 score_0_100
uint8 level
float32 visual_0_1
float32 temperature_0_1
float32 smoke_0_1
float32 gas_0_1
float32 context_0_1
uint32 confirmation_frames
builtin_interfaces/Time last_observed
string[] evidence_ids
```

`score_0_100` 必须按项目计划公式 `100 × (0.30V + 0.25T + 0.20S + 0.10G + 0.15C)` 计算，权重来自 `risk_weights.yaml` 而不是消息或代码常量。等级边界固定为 0～29、30～59、60～79、80～100；实现比较时使用连续分数区间 `[0,30)`、`[30,60)`、`[60,80)`、`[80,100]`。`evidence_ids` 去重并按证据时间升序。

`msg/AssetRiskArray.msg`

```text
uint32 SCHEMA_VERSION=1

uint32 schema_version
std_msgs/Header header
string run_id
uint64 risk_revision
substation_interfaces/AssetRisk[] assets
```

`header.frame_id` 固定为 `map`；`risk_revision` 在同一 `run_id` 内每次原子风险提交加一。`assets` 按 `asset_id` 字典序排列，且不得重复。

`msg/RiskAlert.msg`

```text
uint32 SCHEMA_VERSION=1
uint8 EVENT_OPENED=0
uint8 EVENT_LEVEL_CHANGED=1
uint8 EVENT_CLEARED=2
uint8 LEVEL_NORMAL=0
uint8 LEVEL_ATTENTION=1
uint8 LEVEL_ALERT=2
uint8 LEVEL_EMERGENCY=3

uint32 schema_version
std_msgs/Header header
string alert_id
string run_id
string asset_id
uint8 event_type
uint8 previous_level
uint8 current_level
float32 score_0_100
string summary
string[] evidence_ids
```

达到 60 分首次发 `EVENT_OPENED`；告警仍打开时跨等级发 `EVENT_LEVEL_CHANGED`；经滑动平均和回落滞回降到关闭阈值后发 `EVENT_CLEARED`。`summary` 仅用于显示，自动行为必须读取枚举和分数。

`msg/InspectionTask.msg`

```text
uint32 SCHEMA_VERSION=1
uint8 TYPE_INSPECT_ASSET=0
uint8 TYPE_NAVIGATION_GOAL=1
uint8 TYPE_RETURN_HOME=2
uint8 STATE_QUEUED=0
uint8 STATE_ACTIVE=1
uint8 STATE_SUCCEEDED=2
uint8 STATE_SKIPPED=3
uint8 STATE_FAILED=4
uint8 STATE_CANCELLED=5

uint32 schema_version
string task_id
string mission_id
string asset_id
uint8 task_type
uint8 state
int32 base_priority
float32 risk_score_0_100
float32 risk_gain
float32 path_length_m
float32 distance_penalty
float32 computed_priority
geometry_msgs/PoseStamped goal
float32 safety_standoff_m
uint32 attempt
string last_error_code
```

`computed_priority = base_priority + risk_gain × risk_score_0_100 - distance_penalty × path_length_m`。所有 goal 的 `header.frame_id` 为 `map`。`TYPE_NAVIGATION_GOAL` 的 `asset_id` 为空；另外两类必须引用配置资产或 `home` 资产。紧急资产目标使用配置中的安全观察点，`safety_standoff_m > 0`，不得位于资产碰撞体内。

`msg/InspectionTaskArray.msg`

```text
uint32 SCHEMA_VERSION=1
uint8 MISSION_IDLE=0
uint8 MISSION_READY=1
uint8 MISSION_RUNNING=2
uint8 MISSION_PAUSED=3
uint8 MISSION_STOPPING=4
uint8 MISSION_SUCCEEDED=5
uint8 MISSION_FAILED=6
uint8 MISSION_STOPPED=7
uint8 MODE_AUTONOMOUS=0
uint8 MODE_MANUAL=1
uint8 MODE_ESTOP=2

uint32 schema_version
std_msgs/Header header
string run_id
string mission_id
uint64 queue_revision
uint8 mission_state
uint8 robot_mode
bool emergency_stop_latched
uint64 emergency_stop_latch_revision
string active_task_id
uint32 completed_tasks
uint32 total_tasks
float32 progress_0_1
substation_interfaces/InspectionTask[] tasks
```

`tasks` 是当前排序后的完整队列，按执行顺序排列；重排原子地增加 `queue_revision`。`progress_0_1` 在一次 mission 内不得倒退，队列新增高风险任务时以“已完成数/当前总数”重新计算可能违反该条件，因此实现必须保存任务模块发布的单调任务进度，并另由 `completed_tasks/total_tasks` 表示即时比例。

### 4.2 Service

`srv/ManageMission.srv`

```text
uint32 SCHEMA_VERSION=1
uint8 ACTION_START=0
uint8 ACTION_PAUSE=1
uint8 ACTION_RESUME=2
uint8 ACTION_STOP=3
uint8 ACTION_RETURN_HOME=4

uint32 schema_version
string command_id
string run_id
string mission_id
uint8 action
string route_id
string reason
---
uint32 schema_version
bool accepted
string mission_id
uint64 queue_revision
string error_code
string error_message
```

`ACTION_START` 的 `mission_id` 为空且 `route_id` 必填，Service 生成并返回 mission UUID；其他 action 的 `mission_id` 必填且 `route_id` 为空。`reason` 长度 1～256。Service 的 `accepted` 只表示任务模块接管命令，最终状态由 Action/任务 Topic 和 Gateway 命令生命周期决定。

`srv/QueueNavigationGoal.srv`

```text
uint32 SCHEMA_VERSION=1

uint32 schema_version
string command_id
string run_id
string mission_id
geometry_msgs/PoseStamped goal
---
uint32 schema_version
bool accepted
string task_id
uint64 queue_revision
string error_code
string error_message
```

任务模块验证 `goal.header.frame_id == "map"`、四元数、占据栅格、资产碰撞体和危险区后才创建 `TYPE_NAVIGATION_GOAL`。Gateway 不能绕过该 Service 直接调用 Nav2。

`srv/EmergencyStop.srv`

```text
uint32 SCHEMA_VERSION=1

uint32 schema_version
string command_id
string reason
---
uint32 schema_version
bool accepted
bool latched
uint64 latch_revision
string error_code
string error_message
```

该 Service 必须先锁存再返回：取消所有可见 Nav2 goal、阻止新任务、选择零速度并发布 `/cmd_vel`。已锁存时再次调用是成功的幂等操作，返回当前 `latch_revision`。

`srv/ResetEmergencyStop.srv`

```text
uint32 SCHEMA_VERSION=1

uint32 schema_version
string command_id
uint64 observed_latch_revision
bool confirm
string reason
---
uint32 schema_version
bool accepted
bool latched
uint64 latch_revision
string error_code
string error_message
```

复位要求 `confirm=true`、观察到的 revision 与当前锁存 revision 相同、机器人线/角速度连续 0.5 s 为零、无活动 Nav2 goal、任务安全仲裁器和持久化审计可用。成功只释放锁存并将模式置为 `MANUAL`；不会恢复、重发或继续紧停前的 mission。

### 4.3 Action

`action/ExecuteInspection.action`

```text
uint32 SCHEMA_VERSION=1

uint32 schema_version
string command_id
string run_id
string mission_id
substation_interfaces/InspectionTask[] tasks
bool continue_on_unreachable
---
uint8 RESULT_SUCCEEDED=0
uint8 RESULT_STOPPED=1
uint8 RESULT_FAILED=2
uint8 RESULT_CANCELLED=3

uint32 schema_version
string command_id
string mission_id
uint8 result_state
uint32 completed_tasks
uint32 skipped_tasks
string error_code
string error_message
---
uint8 MISSION_RUNNING=2
uint8 MISSION_PAUSED=3
uint8 MISSION_STOPPING=4

uint32 schema_version
builtin_interfaces/Time stamp
string command_id
string mission_id
uint8 mission_state
string active_task_id
float32 progress_0_1
uint64 queue_revision
```

Gateway 的 `start` 请求只调用 `ManageMission`；任务管理器建立队列后，把任务快照作为此 Action goal 发给同包的巡检执行器。风险变化导致后续顺序改变时，任务管理器取消旧的内部 Action goal，并以相同 mission_id、最新任务快照发送替代 goal；这不产生新的操作员 command。巡检执行器对每个任务调用标准 `/navigate_to_pose` `nav2_msgs/action/NavigateToPose`。暂停取消当前 Nav2 goal 但保留队列；停止取消内部 Action；返航创建最高优先级 `TYPE_RETURN_HOME` 任务。Nav2 的局部避障职责不变。

## 5. TF 契约

### 5.1 树、所有者与语义

```text
map                                      (SLAM 或 AMCL，二选一)
├── odom                                 (定位融合节点；动态)
│   └── base_footprint                   (底盘平面里程计；动态)
│       └── base_link                    (robot_state_publisher；静态 z/roll/pitch 偏移)
│           ├── camera_link              (robot_state_publisher；静态)
│           │   └── camera_optical_frame (robot_state_publisher；静态 REP-103 optical)
│           └── laser_frame              (robot_state_publisher；静态)
└── asset/<asset_id>                     (资产静态广播器；按已配置资产重复该模式)
```

| 变换 | 唯一所有者 | 约束 |
|---|---|---|
| `map -> odom` | SLAM 运行时由 SLAM 拥有；预建地图运行时由 AMCL/定位拥有，不能同时广播 | 允许全局定位修正跳变；10 Hz 或每次修正立即发。 |
| `odom -> base_footprint` | 底盘里程计/定位融合节点 | 必须连续、不得因全局定位跳变重置；30 Hz。`base_footprint` 的 z、roll、pitch 为 0。 |
| `base_footprint -> base_link` | `robot_state_publisher` | 来自 URDF/Xacro 的静态底盘高度与姿态。 |
| `base_link -> camera_link` | `robot_state_publisher` | 来自 URDF/Xacro 标定，运行中不得由感知节点改写。 |
| `camera_link -> camera_optical_frame` | `robot_state_publisher` | 遵循 REP-103：optical frame 的 z 向前、x 向右、y 向下。 |
| `base_link -> laser_frame` | `robot_state_publisher` | 来自 URDF/Xacro 标定。LaserScan 使用该 frame。 |
| `map -> asset/<asset_id>` | `substation_description` 配置驱动的资产静态广播器 | pose 唯一来源是版本控制配置，frame 名中的 asset_id 必须已注册。 |

每个 child frame 在一个运行模式中只能有一个广播者。禁止 `map -> base_link` 捷径、`odom -> asset/*`、以视觉观测移动静态资产 frame、以 `Time(0)` 代替有证据时间的精确查询，或让 Gateway/前端广播 TF。

### 5.2 时间容差与失败行为

- 传感/检测关联必须查询消息 stamp 的 TF。相机、检测、环境和资产观测允许使用不早于消息 0.1 s 的最近变换；LiDAR、里程计和导航安全校验允许的最大过去外推为 0.05 s。任何业务链均不得使用超过消息时间 0.02 s 的未来变换。
- 静态变换不受年龄限制。动态变换超过上述容差、TF 树断开或 frame 不匹配时，该样本标记为 STALE/无效并从风险新增证据中排除；不得静默改用最新 pose。
- Gateway 对外 pose 的 source stamp 必须是成功组成 `map -> base_link` 时的 ROS 时间。若最近一份可用 pose 已老于 0.5 s，`robot.state.stale=true`，停止接受普通移动命令；紧急停止仍必须可用。
- `/digital_twin/assets` 和资产 REST pose 永远在 `map`。资产 pose 由描述配置创作和评审；运行时数字孪生只更新状态、风险和证据引用，不更新几何真值。

## 6. HTTP 通用契约

### 6.1 传输与媒体类型

产品 API 基础路径固定为 `/api/v1`，由 Nginx 同源代理到只监听 `127.0.0.1` 的 Gateway。JSON 请求必须是 UTF-8 `application/json`，JSON 成功响应是 `application/json`，错误是 `application/problem+json`。未知 JSON 字段在 schema 1 中返回 422，防止拼写错误被忽略。请求体上限 64 KiB；超限返回 413 `REQUEST_TOO_LARGE`，错误媒体类型返回 415 `UNSUPPORTED_MEDIA_TYPE`。报告下载不受此请求体限制。

列表分页使用 `limit` 和 `cursor`；`limit` 默认为 50、范围 1～100，`cursor` 是服务器生成的 opaque base64url 字符串，客户端不得解析。所有字符串去除首尾空白后验证；原因/备注最长 256 个 Unicode code point。所有控制响应和错误返回 `Cache-Control: no-store`；快照响应返回 ETag，报告文件返回内容 SHA-256 ETag。

### 6.2 快照成功外壳

除 health/readiness、命令查询和二进制下载外，所有 GET 快照使用：

```json
{
  "schema_version": "1.0",
  "run_id": "f93bf1d5-8bf6-4ad7-8f13-f6e3e148728f",
  "snapshot_revision": 1842,
  "generated_at": "2026-07-22T14:03:05.123456Z",
  "data": {}
}
```

系统未开始 run 时 `run_id` 为 `null`、revision 仍为当前 Gateway 进程的系统快照 revision；进入 run 后按第 2.5 节规则重置为 1。数组顺序在各 endpoint 中明确，不允许依赖数据库偶然顺序。

### 6.3 控制受理、幂等与命令查询

所有 POST 控制请求必须携带 `Idempotency-Key`，值为客户端生成的规范 UUID 字符串。Gateway 以 `(HTTP method, 规范化 route, Idempotency-Key)` 为作用域，保存请求体 RFC 8785 canonical JSON 的 SHA-256、原始 HTTP 结果和 `command_id` 24 小时：

- 首次请求先生成 `command_id`，完成同步 JSON/状态/安全校验；合法请求返回 202，非法请求返回 RFC 7807 错误且同样保存为 `rejected` 命令。
- 相同 key、method、route 和 canonical JSON 相同的请求在 24 小时内返回完全相同的原始状态码和响应体，并加 `Idempotent-Replayed: true`；对象 key 顺序和无意义空白不影响摘要，它不重复调用 ROS。命令当前状态另由查询 endpoint 获得。
- 相同作用域 key 配不同请求体返回 409 `IDEMPOTENCY_KEY_REUSED`，同时生成并记录一个新的 rejected `command_id`，但不覆盖原 key 的记录。
- Idempotency 持久化不可用时，除紧急停止外的控制返回 503 `AUDIT_STORAGE_UNAVAILABLE`。紧急停止改用进程内幂等表并继续走优先安全路径，同时产生系统降级事件。

202 响应体固定为：

```json
{
  "schema_version": "1.0",
  "command_id": "3181ea52-0d8b-4ab0-b2d0-c1c845ac33d2",
  "status": "accepted",
  "accepted_at": "2026-07-22T14:03:05.123456Z",
  "status_url": "/api/v1/commands/3181ea52-0d8b-4ab0-b2d0-c1c845ac33d2"
}
```

#### `GET /api/v1/commands/{command_id}` — `commands.lookup`

无请求体；path 参数必须是规范 UUID，否则返回 422 `VALIDATION_FAILED`。存在时返回 200：

```json
{
  "schema_version": "1.0",
  "command_id": "3181ea52-0d8b-4ab0-b2d0-c1c845ac33d2",
  "run_id": "f93bf1d5-8bf6-4ad7-8f13-f6e3e148728f",
  "kind": "navigation.goal",
  "status": "executing",
  "created_at": "2026-07-22T14:03:05.100000Z",
  "accepted_at": "2026-07-22T14:03:05.123456Z",
  "started_at": "2026-07-22T14:03:05.180000Z",
  "completed_at": null,
  "result": null,
  "error": null
}
```

`run_id` 在活动 run 中为 UUID，在 run 建立前的紧急停止可为 null。`kind` 固定为 `mission.start|mission.pause|mission.resume|mission.stop|mission.return_home|navigation.goal|robot.manual_velocity|robot.emergency_stop|robot.emergency_stop_reset|simulation.scenario` 之一；path 中的 `return-home` 在 kind 中规范化为 `return_home`。只有在 path action 本身无法映射时，被拒绝记录的 kind 为 `unknown`。`status` 只能是 `accepted`、`executing`、`succeeded`、`failed`、`timed_out`、`cancelled` 或 `rejected`。尚未发生的 `accepted_at`、`started_at`、`completed_at` 为 null。不存在返回 404 `COMMAND_NOT_FOUND`。命令记录至少保存到所属 run 的报告和证据保留期结束；无 run 的安全命令按系统审计保留策略保存。

### 6.4 RFC 7807 错误

所有非 2xx/304 错误使用 RFC 7807：

```json
{
  "type": "http://ros-server/problems/goal-in-hazard-zone",
  "title": "Navigation goal is inside a hazard zone",
  "status": 422,
  "detail": "Goal intersects hazard zone hz-transformer-01.",
  "instance": "/api/v1/navigation/goal",
  "code": "GOAL_IN_HAZARD_ZONE",
  "trace_id": "75d1a54e-bb49-48e1-a74a-74d6b576de45",
  "command_id": "1ebfdb5b-fcf6-4075-80c6-8cf6cc86d4c7",
  "violations": [
    {"field": "position", "reason": "hazard_zone", "value": {"x_m": 4.2, "y_m": 1.1}}
  ]
}
```

`code` 是第 10 节稳定机器码；`title/detail` 只用于人读。GET/握手错误没有 `command_id` 时该字段为 `null`。`violations` 无字段级错误时为空数组。响应不得暴露 traceback、主机路径、SQL 或 ROS 内部对象。

## 7. REST endpoint

下列 endpoint 除各自列出的错误外，都可能返回第 6 节通用的 400、413、415、422、500；所有 POST 还可能返回幂等键相关 400/409 和审计存储 503。除非 endpoint 明确例外，成功 GET 为 200、成功控制受理为 202。

### 7.1 健康与系统状态

#### `GET /healthz` — 存活

无参数。Gateway HTTP 事件循环可响应即返回 200：

```json
{"schema_version":"1.0","status":"alive","checked_at":"2026-07-22T14:03:05.123456Z"}
```

该 endpoint 不检查 ROS、SQLite、Gazebo 或模型，不能用作巡检就绪判据。

#### `GET /readyz` — 就绪

无参数。核心 ROS 图、数字孪生、风险、任务、Nav2、审计存储和当前模式所需的 Gazebo 均可用时返回 200：

```json
{
  "schema_version": "1.0",
  "status": "ready",
  "checked_at": "2026-07-22T14:03:05.123456Z",
  "dependencies": {"ros":true,"gazebo":true,"nav2":true,"storage":true,"risk":true,"mission":true}
}
```

任一强制依赖不可用返回 503 RFC 7807 `NOT_READY`，并在 `violations` 列出依赖；紧急停止本身仍不得依赖该 readiness 成功。

#### `GET /api/v1/system/status` — `system.status`

无参数；200 快照的 `data`：

```json
{
  "simulation_mode": true,
  "overall": "ready",
  "emergency_stop_latched": false,
  "components": [
    {
      "name": "substation_risk",
      "kind": "ros_node",
      "status": "ok",
      "message": "",
      "last_seen_at": "2026-07-22T14:03:05.000000Z"
    }
  ],
  "gpu": {"status":"ok","utilization_percent":37.0,"memory_used_bytes":2252341248,"temperature_celsius":58.0},
  "storage": {"status":"ok","free_bytes":128849018880,"audit_writable":true},
  "websocket": {"telemetry":"ok","events":"ok","camera":"ok"}
}
```

`overall` 与组件 status 只能是 `ready|degraded|unavailable` 和 `ok|degraded|error|stale`；components 按 name 排序。仅采集失败的 GPU 可空字段必须为 `null`，不能伪造 0。失败码：503 `DEPENDENCY_UNAVAILABLE` 仅在 Gateway 无法组成任何一致快照时使用；单组件故障仍返回 200 并在 data 标降级。

### 7.2 机器人、资产与任务快照

#### `GET /api/v1/robot/state` — `robot.state`

无参数；200 快照的 `data`：

```json
{
  "frame_id": "map",
  "pose": {"x_m":1.2,"y_m":2.3,"z_m":0.0,"qx":0.0,"qy":0.0,"qz":0.1,"qw":0.994987},
  "twist": {"linear_x_m_s":0.1,"linear_y_m_s":0.0,"angular_z_rad_s":0.0},
  "battery_percent": 87.0,
  "mode": "autonomous",
  "stale": false,
  "emergency_stop": {"latched":false,"latch_revision":12},
  "current_mission_id": "0c5efce1-655b-413d-9847-da203fb5ca5e",
  "current_task_id": "63b3e775-75cd-4443-a4a3-cc1b97ec4b3c",
  "source_ros_time": {"sec":123,"nanosec":450000000}
}
```

`mode` 为 `autonomous|manual|estop`；无当前 mission/task 时相应值为 `null`。pose 超过第 5.2 节时限仍返回最后值但 `stale=true`。失败码：503 `ROBOT_STATE_UNAVAILABLE`（从未取得合法 TF/odom）。

#### `GET /api/v1/assets` — `assets.list`

查询参数：`risk_level` 可重复且只能为 `normal|attention|alert|emergency`；`category` 使用配置字符串；`limit/cursor` 按第 6.1 节。200 `data`：

```json
{
  "items": [
    {
      "asset_id": "transformer-01",
      "category": "transformer",
      "state": "attention",
      "pose": {"frame_id":"map","x_m":4.0,"y_m":2.0,"z_m":0.0,"qx":0.0,"qy":0.0,"qz":0.0,"qw":1.0},
      "measurements": {"temperature_celsius":72.4,"smoke_0_1":0.05,"gas_ppm":8.0,"meter_reading":null,"meter_unit":null},
      "risk": {"score_0_100":48.2,"level":"attention","visual_0_1":0.2,"temperature_0_1":0.7,"smoke_0_1":0.05,"gas_0_1":0.08,"context_0_1":0.3},
      "latest_evidence_id": "ea6992e2-4398-414d-a587-ce8b33932266",
      "observed_at": "2026-07-22T14:03:04.900000Z",
      "stale": false
    }
  ],
  "next_cursor": null
}
```

按 `asset_id` 升序后分页；未知 category/risk_level 返回 422 `VALIDATION_FAILED`，cursor 失效返回 400 `INVALID_CURSOR`。

#### `GET /api/v1/missions/current` — `mission.current`

无参数；没有 mission 也返回 200，`data.mission_id=null`、state=`idle`、tasks 空数组。活动时 `data`：

```json
{
  "mission_id": "0c5efce1-655b-413d-9847-da203fb5ca5e",
  "route_id": "default-route",
  "state": "running",
  "queue_revision": 42,
  "active_task_id": "63b3e775-75cd-4443-a4a3-cc1b97ec4b3c",
  "completed_tasks": 3,
  "total_tasks": 8,
  "progress_0_1": 0.375,
  "tasks": [
    {
      "task_id":"63b3e775-75cd-4443-a4a3-cc1b97ec4b3c",
      "asset_id":"transformer-01",
      "type":"inspect_asset",
      "state":"active",
      "computed_priority":78.2,
      "risk_score_0_100":72.0,
      "goal":{"frame_id":"map","x_m":3.0,"y_m":2.0,"yaw_rad":0.0},
      "attempt":1,
      "last_error_code":null
    }
  ]
}
```

state 为 `idle|ready|running|paused|stopping|succeeded|failed|stopped`，任务顺序等于 ROS 完整队列。失败码：503 `MISSION_STATE_UNAVAILABLE`。

### 7.3 Mission 控制

#### `POST /api/v1/missions/{action}` — `mission.<action>`

`action` 只允许 `start|pause|resume|stop|return-home`，必须带 Idempotency-Key。请求体和同步前置条件：

| action | 请求 JSON | 同步验证 | 命令超时 |
|---|---|---|---:|
| `start` | `{"route_id":"default-route","reason":"operator start"}` | route 存在；当前 state 为 idle/ready/succeeded/failed/stopped；非紧停；数字孪生、风险、Nav2 与审计就绪 | 30 s |
| `pause` | `{"mission_id":"<uuid>","reason":"operator pause"}` | 指定 mission 是当前 mission 且 state=running | 10 s |
| `resume` | `{"mission_id":"<uuid>","reason":"operator resume"}` | state=paused；非紧停；所需依赖与审计恢复 | 10 s |
| `stop` | `{"mission_id":"<uuid>","reason":"operator stop"}` | state=ready/running/paused/stopping；重复 stop 由 Idempotency-Key 合并 | 10 s |
| `return-home` | `{"mission_id":"<uuid>","reason":"operator return"}` | 当前 mission 存在；非紧停；home 安全目标可用；state=running/paused | 300 s |

成功统一返回 202 命令受理体；最终由 `/ws/events` `command.status` 和命令查询给出。失败码：400 `INVALID_ACTION`；404 `MISSION_NOT_FOUND`/`ROUTE_NOT_FOUND`；409 `INVALID_STATE_TRANSITION`、`EMERGENCY_STOP_LATCHED`、`COMMAND_CONFLICT`；503 `NAVIGATION_UNAVAILABLE`、`AUDIT_STORAGE_UNAVAILABLE`、`DEPENDENCY_UNAVAILABLE`。

### 7.4 导航与手动速度

#### `POST /api/v1/navigation/goal` — `navigation.goal`

请求：

```json
{
  "mission_id": "0c5efce1-655b-413d-9847-da203fb5ca5e",
  "frame_id": "map",
  "position": {"x_m": 3.4, "y_m": 5.6},
  "yaw_rad": 1.570796,
  "reason": "operator map click"
}
```

必须带 Idempotency-Key；frame 只能是 `map`，坐标有限，yaw 在规范范围；mission 必须是当前 mission 且 state 为 running/paused，模式为 autonomous，未紧停。任务模块再验证地图边界、可通行栅格、膨胀后资产碰撞体、危险区域和预设安全距离。成功 202，超时 300 s；Gateway 调 `/mission/queue_navigation_goal`，绝不直调 NavigateToPose。失败码：404 `MISSION_NOT_FOUND`；409 `MANUAL_MODE_ACTIVE`、`EMERGENCY_STOP_LATCHED`、`INVALID_STATE_TRANSITION`；422 `GOAL_OUTSIDE_MAP`、`GOAL_OCCUPIED`、`GOAL_IN_ASSET_COLLISION`、`GOAL_IN_HAZARD_ZONE`、`INVALID_ORIENTATION`；503 `NAVIGATION_UNAVAILABLE`。

#### `POST /api/v1/robot/manual-velocity` — `robot.manual_velocity`

请求：

```json
{
  "linear_x_m_s": 0.2,
  "angular_z_rad_s": -0.3,
  "deadman": true,
  "duration_s": 0.15
}
```

必须带 Idempotency-Key；只在 `mode=manual`、非紧停、robot state 非 stale 时接受。`linear_x_m_s` 范围 `[-0.4,0.4]`，`angular_z_rad_s` 范围 `[-0.8,0.8]`，`duration_s` 为有限数且范围 `[0.05,0.25]`，非零速度要求 `deadman=true`。每个浏览器会话最高 10 请求/s；命令 1 s 超时。Gateway 发布 `/cmd_vel_manual`，任务安全仲裁器在 duration 到期、松键、浏览器失焦、WebSocket 心跳丢失或进程断线时立即选择零速度。成功 202；失败码：409 `MANUAL_MODE_REQUIRED`、`EMERGENCY_STOP_LATCHED`；422 `VELOCITY_LIMIT_EXCEEDED`、`DEADMAN_REQUIRED`；429 `MANUAL_COMMAND_RATE_EXCEEDED`；503 `ROBOT_STATE_UNAVAILABLE`。

### 7.5 紧急停止与复位

#### `POST /api/v1/robot/emergency-stop` — `robot.emergency_stop`

请求 `{"reason":"operator emergency stop"}`，reason 必填。必须带 Idempotency-Key，但该路径不要求 readiness、当前 mission、Nav2 或 SQLite 可用；Gateway 优先调用 ROS 安全 Service。成功 202，命令超时 2 s。重复调用在任务模块侧保持已锁存并成功返回。若 ROS 确认超时，命令为 `timed_out`，UI 必须继续显示“紧停状态未知/按已锁存处理”，禁用普通控制，直到 REST/ROS 状态明确；不能因超时推断机器人未停止。失败仅限 422 `VALIDATION_FAILED` 或 503 `EMERGENCY_STOP_PATH_UNAVAILABLE`。

#### `POST /api/v1/robot/emergency-stop/reset` — `robot.emergency_stop_reset`

请求：

```json
{
  "observed_latch_revision": 13,
  "confirm": true,
  "reason": "area verified clear"
}
```

必须带 Idempotency-Key；reason 必填，revision 必须等于最新 `/robot/state`，confirm 必须为 true。Gateway/任务模块执行第 4.2 节全部安全前置条件。成功 202，命令超时 5 s；成功后模式为 manual、旧 mission 不自动恢复。失败码：409 `EMERGENCY_STOP_NOT_LATCHED`、`LATCH_REVISION_MISMATCH`、`EMERGENCY_STOP_RESET_UNSAFE`；422 `RESET_CONFIRMATION_REQUIRED`；503 `AUDIT_STORAGE_UNAVAILABLE`、`EMERGENCY_STOP_PATH_UNAVAILABLE`。

### 7.6 仿真场景

#### `POST /api/v1/simulation/scenario` — `simulation.scenario`

请求：

```json
{
  "scenario_id": "gas-high",
  "action": "trigger",
  "parameters": {"asset_id":"transformer-01","value_ppm":180.0},
  "reason": "acceptance scenario 5"
}
```

必须带 Idempotency-Key；只在 `simulation_mode=true` 显示和接受。action 为 `start|trigger|reset`；scenario_id 必须存在；parameters 必须是该场景配置 allowlist 内的标量键值，不能传文件路径、ROS 名称或任意代码。Gateway 使用第 3.3 节标准参数服务，成功 202、超时 30 s。失败码：403 `SIMULATION_MODE_REQUIRED`；404 `SCENARIO_NOT_FOUND`；409 `SCENARIO_CONFLICT`；422 `SCENARIO_ACTION_INVALID`、`SCENARIO_PARAMETER_INVALID`；503 `GAZEBO_UNAVAILABLE`。

### 7.7 报告

#### `GET /api/v1/reports` — `reports.list`

查询参数：`run_id`、`mission_id` 为可选 UUID；`status` 为 `generating|ready|failed`；`from`/`to` 为 RFC 3339 UTC 且 from≤to；`limit/cursor` 按通用规则。200 `data`：

```json
{
  "items": [
    {
      "report_id":"74727656-b320-4fe8-9a14-6de3c0094f08",
      "run_id":"f93bf1d5-8bf6-4ad7-8f13-f6e3e148728f",
      "mission_id":"0c5efce1-655b-413d-9847-da203fb5ca5e",
      "status":"ready",
      "created_at":"2026-07-22T14:20:00.000000Z",
      "completed_at":"2026-07-22T14:20:02.000000Z",
      "formats":["html","pdf","evidence"],
      "download_urls": {
        "html":"/api/v1/reports/74727656-b320-4fe8-9a14-6de3c0094f08/download?format=html",
        "pdf":"/api/v1/reports/74727656-b320-4fe8-9a14-6de3c0094f08/download?format=pdf",
        "evidence":"/api/v1/reports/74727656-b320-4fe8-9a14-6de3c0094f08/download?format=evidence"
      },
      "sha256": {"html":"4f5c9f3ea8071fba9f0a663c0f0e7650e72b88d447441e4a680f49b594f894dd","pdf":"6d3557f4b074d722734ae44a9d8e659df33404d3bce13cdb679780aed44d8788","evidence":"591025894a28dc42b2d4f0293fe7e1cc6ae64128ee753186c96223e21fb99c6c"}
    }
  ],
  "next_cursor": null
}
```

排序固定为 `created_at` 降序、report_id 升序。失败码：400 `INVALID_CURSOR`；422 `VALIDATION_FAILED`；503 `REPORT_INDEX_UNAVAILABLE`。

#### `GET /api/v1/reports/{report_id}/download` — `reports.download`

`format` 必填且为 `html|pdf|evidence`。ready 时返回 200 字节流：HTML `text/html; charset=utf-8`，PDF `application/pdf`，证据包 `application/zip`；响应含 `Content-Disposition: attachment; filename="inspection-<report_id>.<ext>"`、`ETag: "sha256:<digest>"`、`X-Content-SHA256: <digest>` 和 `Content-Length`，其中 digest 必须匹配 `^[0-9a-f]{64}$`。支持标准单范围 `Range`，合法时 206，非法时 416 `RANGE_NOT_SATISFIABLE`。失败码：404 `REPORT_NOT_FOUND`/`REPORT_FORMAT_NOT_FOUND`；409 `REPORT_NOT_READY`；503 `REPORT_STORAGE_UNAVAILABLE`。下载错误仍用 RFC 7807，不返回部分 HTML 错误页。

## 8. WebSocket 契约

### 8.1 握手、公共 JSON 外壳与心跳

产品流固定为 `WS /ws/telemetry`、`WS /ws/events`、`WS /ws/camera`，必须协商子协议 `substation.v1`。Gateway 只接受同源 Host/Origin；握手前依赖不可用时返回对应 RFC 7807 HTTP 错误。每次连接生成 UUIDv4 `connection_id`；Gateway 每次进程启动生成 UUIDv4 `stream_epoch`。每个 endpoint 在该 epoch 内维护一个全局 sequence，逻辑消息分配序号后再向所有连接 fan-out，因此所有客户端看到相同数据序号。连接私有的 `stream.open` 使用 sequence=0，不进入连续性/replay 判断；其后每个数据消息和全局心跳占用一个 sequence。达到 JSON 最大安全整数 `9007199254740991` 前 Gateway 必须滚动到新 stream_epoch 并从 1 重新开始。

三个流的所有服务器文本消息均使用：

```json
{
  "schema_version": "1.0",
  "stream": "telemetry",
  "stream_epoch": "f72b21de-d178-4cf9-8819-29f07c824adb",
  "connection_id": "57d8cf69-ff22-4c0e-bc47-24d1b9eaf539",
  "run_id": "f93bf1d5-8bf6-4ad7-8f13-f6e3e148728f",
  "sequence": 8124,
  "snapshot_revision": 1842,
  "sent_at": "2026-07-22T14:03:05.123456Z",
  "type": "robot.state",
  "payload": {}
}
```

`stream` 为 `telemetry|events|camera`，`run_id` 为当前 run UUID、未进入 run 时为 null，sequence 是 JSON 安全整数范围内的非负整数。连接建立后的第一条消息 type=`stream.open`，payload 为 `{"heartbeat_interval_s":1.0,"connection_timeout_s":5.0,"replay_available":bool}`。仅 events replay 消息可增加可选顶层字段 `replayed:true`，正常消息省略该字段。服务器每 1 s 为每个 endpoint 生成一条全局 type=`heartbeat` 并 fan-out，payload 为：

```json
{
  "server_time":"2026-07-22T14:03:05.123456Z",
  "latest_data_sequence":8123,
  "ready":true
}
```

Gateway 另外每 2 s 发送 WebSocket protocol Ping，浏览器自动 Pong。浏览器超过 5 s 未收到任何合法应用消息必须进入“连接中断”、立即发送/选择零手动速度、禁用除紧急停止外的普通控制并开始重连；服务器超过 10 s 未收到 Pong 关闭连接，close code 1001。畸形 JSON/未知主版本关闭 1003；消息过大关闭 1009；服务重启关闭 1012。紧急停止 HTTP 按钮不得依赖 WebSocket 可用。

### 8.2 `WS /ws/telemetry`

这是可丢弃的最新状态流，不是历史日志。类型、payload 和最大发送率：

| type | payload | 最大率 |
|---|---|---:|
| `robot.state` | 与 `GET /robot/state` 的 `data` 相同 | 10 Hz |
| `navigation.paths` | `{"frame_id":"map","global":[{"x_m":1.0,"y_m":2.0}],"local":[{"x_m":1.1,"y_m":2.1}],"goal":{"x_m":3.0,"y_m":4.0,"yaw_rad":0.0}}`；无 goal 时为 null | 5 Hz |
| `environment.state` | `{"assets":[{"asset_id":"transformer-01","temperature_celsius":72.4,"smoke_0_1":0.05,"gas_ppm":8.0,"observed_at":"2026-07-22T14:03:04.900000Z","stale":false}]}`；可空测量为 null，按 asset_id 排序 | 5 Hz |
| `risk.assets` | `{"risk_revision":42,"assets":[{"asset_id":"transformer-01","score_0_100":72.0,"level":"alert","visual_0_1":0.4,"temperature_0_1":0.9,"smoke_0_1":0.2,"gas_0_1":0.1,"context_0_1":0.5}]}`；按 score 降序、asset_id 升序 | 5 Hz |
| `mission.state` | 与 `GET /missions/current` 的 `data` 相同 | 10 Hz |
| `system.health` | `GET /system/status` 中 overall/components/websocket 子集 | 1 Hz |

Gateway 在积压时只保留每个 type 最新一条，绝不延迟堆积旧遥测。客户端检测到同一 epoch 中 `sequence` 不连续、run_id 改变或 snapshot_revision 倒退时，标记 UI stale，关闭当前连接，依次 GET system/robot/assets/current mission 快照，再建立新连接。telemetry 不提供 replay，不能用 `after_sequence` 猜补差量。

### 8.3 `WS /ws/events`

事件类型固定为：

| type | payload 必需字段 |
|---|---|
| `risk.alert` | `alert_id`、`run_id`、`asset_id`、`event`（`opened`、`level_changed`、`cleared`）、`previous_level`、`current_level`、`score_0_100`、`evidence_ids` |
| `command.status` | 第 6.3 节命令对象完整字段；每次状态转换一条 |
| `mission.changed` | `mission_id`、`state`、`queue_revision`、`active_task_id`、`reason_code` |
| `system.event` | `severity`（`info`、`warning`、`error`、`critical`）、`code`、`message`、`component`、`evidence_id`（可空） |
| `resync.required` | `code="WS_RESYNC_REQUIRED"`、`oldest_available_sequence`、`latest_sequence`、`snapshot_revision` |

Gateway 将事件先持久化再发送，并保留至少最近 10,000 条事件流消息（包括其间心跳）且不少于 10 分钟的内存 replay 窗口。客户端在首次/完整 REST 恢复后不带 query 连接并从 `stream.open` 后的实时消息开始；需要补缺口时使用 `/ws/events?stream_epoch=<uuid>&after_sequence=<uint64>`。两个 query 必须同时出现，epoch 为 UUID、sequence 为 1～9007199254740991；否则握手返回 422 `VALIDATION_FAILED`：

- epoch 相同且 `after_sequence` 仍在窗口内：先按原 sequence 重放之后事件，再发实时事件；重放外壳增加 `replayed:true`。
- 带 query 时 epoch 不同或 sequence 超出窗口：服务器在 `stream.open` 后发 `resync.required`，再以 private close code 4009 关闭；客户端读取四个 REST 快照，并不带 query 重连。
- 客户端在实时流发现缺口时先以最后连续 sequence 重连一次；若收到 `resync.required`，执行 REST 恢复。不得跳过 command/alert 事件后继续把 UI 当作一致。

### 8.4 `WS /ws/camera` 二进制 framing

相机连接发送两类 WebSocket message：第 8.1 节 JSON 文本 `stream.open`/`heartbeat`/`resync.required`，以及一条完整 JPEG 对应的一条二进制 message。目标帧率 15 FPS；拥塞时只保留最新帧并降低帧率，绝不让视频积压影响事件、紧急停止或基础任务控制。

每个二进制 message 为固定 64-byte header、UTF-8 metadata JSON、JPEG 三段连续拼接。多字节整数使用 network byte order（big-endian）：

| Offset | 长度 | 字段 | 约束 |
|---:|---:|---|---|
| 0 | 4 | magic | ASCII `SSCF` (`0x53 0x53 0x43 0x46`) |
| 4 | 1 | framing_version | `1` |
| 5 | 1 | flags | bit 0=`annotated`; bits 1～7 必须为 0 |
| 6 | 2 | header_length | uint16，固定 64 |
| 8 | 8 | sequence | uint64，与 camera 流 JSON 消息共享序号空间 |
| 16 | 8 | snapshot_revision | uint64 |
| 24 | 4 | metadata_length | uint32，1～16384 |
| 28 | 4 | jpeg_length | uint32，1～2097152 |
| 32 | 4 | width | uint32，必须与 JPEG SOF 一致 |
| 36 | 4 | height | uint32，必须与 JPEG SOF 一致 |
| 40 | 16 | stream_epoch | UUID 的 16 个 raw bytes，等于文本外壳 UUID |
| 56 | 8 | reserved | 全 0；schema 1 客户端拒绝非 0 |

metadata 是以下 schema，未知字段按同主版本可忽略：

```json
{
  "schema_version":"1.0",
  "connection_id":"57d8cf69-ff22-4c0e-bc47-24d1b9eaf539",
  "run_id":"f93bf1d5-8bf6-4ad7-8f13-f6e3e148728f",
  "captured_at":"2026-07-22T14:03:05.100000Z",
  "source_ros_time":{"sec":123,"nanosec":400000000},
  "ros_frame_id":"camera_optical_frame",
  "encoding":"jpeg",
  "annotated":true,
  "detections_sequence":7712,
  "evidence_id":null
}
```

JPEG 必须以 SOI `FFD8` 开始、EOI `FFD9` 结束，且二进制 message 总长度严格等于 `64 + metadata_length + jpeg_length`。`captured_at` 是 canonical RFC 3339 UTC；header 不使用非 RFC 3339 业务时间。`detections_sequence` 是 Gateway 在当前 stream_epoch 内为其消费的 `/perception/detections` 样本分配的单调序号，必须对应生成该 annotated frame 的检测样本。冻结并持久化该帧后 `evidence_id` 为 UUID，否则为 null。

相机是易失流：检测到 sequence 缺口时丢弃不完整帧并显示 dropped-frame 计数，继续等待下一完整帧；重连或 stream_epoch 变化后从新帧恢复，不 replay 视频。若客户端还需要一致状态，按 telemetry 规则读取 REST 快照。metadata/JPEG 不合法时丢弃该帧；连续 3 帧不合法则关闭 1003 并产生 `CAMERA_FRAME_INVALID` system event。

## 9. 命令状态机与安全语义

### 9.1 通用状态机

```text
HTTP 同步校验失败 ───────────────────────────────> rejected

accepted ──ROS 调用开始──> executing ──完成──────> succeeded
    │                         ├─确定失败──────────> failed
    │                         ├─到 endpoint 时限──> timed_out
    │                         └─紧停/stop/替代────> cancelled
    ├─紧停/stop 在执行前─────────────────────────> cancelled
    └─到 endpoint 时限───────────────────────────> timed_out
```

terminal 状态为 succeeded/failed/timed_out/cancelled/rejected，不能再转换。每次转换必须在 SQLite 命令记录提交后，才发送 `command.status`；WebSocket 发送失败不回滚命令。`result` 是 endpoint 特定 JSON，例如 mission_id/task_id/latch_revision/scenario_revision；失败对象固定为 `{"code":str,"message":str,"retryable":bool}`。

Gateway 接受请求不等于 ROS 操作成功。任务/Action/Service 返回后才可 succeeded；到时限后 timed_out，即使底层随后成功也不改 terminal 状态，而是记录 `LATE_RESULT_IGNORED` system event 并通过新快照反映真实状态。客户端不得仅凭 202 改变业务真值。

### 9.2 任务与导航冲突

- 同一时刻只允许一个活动 mission 和一个 Nav2 goal。新的风险重排仅改变后续任务；若风险达到紧急等级，任务模块取消当前普通 Nav2 goal、把安全观察任务置于队首并重新调用 Nav2。
- `pause`、`stop`、`return-home` 和紧停可取消 Nav2；取消原因写入旧命令/任务。普通 navigation goal 不得抢占紧急任务，返回 `COMMAND_CONFLICT`。
- 手动模式只消费 `/cmd_vel_manual`；autonomous 模式只消费 `/cmd_vel_nav`；estop 模式只输出零。模式选择在任务安全仲裁器内完成，不允许浏览器或 Nav2 直接控制最终 `/cmd_vel`。
- 手动速度的 HTTP command succeeded 表示该有时限速度样本被安全仲裁器接受，不表示机器人已移动。duration 到期不创建新 command，而是安全仲裁器自动归零。

### 9.3 紧急停止锁存与复位

紧急停止拥有最高优先级，并且即使数字孪生、风险、Nav2、SQLite、视频或 WebSocket 故障也必须尝试执行。锁存转换的顺序固定为：

1. 原子设置 `emergency_stop_latched=true` 并增加 `latch_revision`；
2. 安全仲裁器选择零速度，立即发布 `/cmd_vel` 零值；
3. 拒绝新普通任务/目标/速度并取消所有可见 Nav2 goal；
4. 取消受影响命令，错误码为 `EMERGENCY_STOP_ACTIVATED`；
5. 持久化可用时记录证据，向 REST/ROS/WS 暴露锁存状态。

复位是单独 endpoint 和 ROS Service，不能由 mission resume、场景 reset、Gateway 重启或重复 start 隐式完成。它使用 compare-and-set 的 `observed_latch_revision` 防止操作者依据旧页面复位。复位成功后不恢复先前速度、goal 或任务，机器人保持零速度和 manual 模式；操作者必须重新明确选择后续动作。

## 10. 稳定错误代码

HTTP status 是协议分类，`code` 是客户端逻辑依据。下表代码在 schema 1 中不得改义；ROS 自定义响应的 `error_code` 使用同一集合，成功时为空字符串。

| HTTP | code | 含义 / 典型恢复 |
|---:|---|---|
| 400 | `BAD_REQUEST` | JSON 语法或请求结构无法读取。 |
| 400 | `INVALID_CURSOR` | 列表 cursor 无效/过期；从第一页重取。 |
| 400 | `INVALID_ACTION` | path action 不在固定集合。 |
| 400 | `IDEMPOTENCY_KEY_REQUIRED` | 控制请求缺少 header。 |
| 400 | `INVALID_IDEMPOTENCY_KEY` | header 不是规范 UUID。 |
| 403 | `SIMULATION_MODE_REQUIRED` | 真实模式禁止场景控制。 |
| 404 | `COMMAND_NOT_FOUND` | command_id 不存在或不再保留。 |
| 404 | `MISSION_NOT_FOUND` | mission UUID 不存在/不是当前 mission。 |
| 404 | `ROUTE_NOT_FOUND` | route_id 未配置。 |
| 404 | `SCENARIO_NOT_FOUND` | scenario_id 未配置。 |
| 404 | `REPORT_NOT_FOUND` | report_id 不存在。 |
| 404 | `REPORT_FORMAT_NOT_FOUND` | 该报告没有指定格式。 |
| 409 | `IDEMPOTENCY_KEY_REUSED` | 同 key 对应不同请求体。 |
| 409 | `INVALID_STATE_TRANSITION` | 当前 mission/command 状态不允许该动作。 |
| 409 | `COMMAND_CONFLICT` | 与活动紧急/导航/任务命令冲突。 |
| 409 | `MANUAL_MODE_ACTIVE` | 自动目标在 manual 模式被拒绝。 |
| 409 | `MANUAL_MODE_REQUIRED` | 手动速度在非 manual 模式被拒绝。 |
| 409 | `EMERGENCY_STOP_LATCHED` | 锁存期间拒绝普通控制。 |
| 409 | `EMERGENCY_STOP_NOT_LATCHED` | 无锁存可复位。 |
| 409 | `LATCH_REVISION_MISMATCH` | 页面观察 revision 已旧；刷新状态。 |
| 409 | `EMERGENCY_STOP_RESET_UNSAFE` | 速度、Nav2、仲裁器或审计前置条件不安全。 |
| 409 | `SCENARIO_CONFLICT` | 场景状态不允许该切换。 |
| 409 | `REPORT_NOT_READY` | 报告仍生成或已失败。 |
| 413 | `REQUEST_TOO_LARGE` | 请求体超过 64 KiB。 |
| 415 | `UNSUPPORTED_MEDIA_TYPE` | JSON 请求不是 UTF-8 `application/json`。 |
| 416 | `RANGE_NOT_SATISFIABLE` | 下载 Range 不合法。 |
| 422 | `VALIDATION_FAILED` | 通用字段/范围/未知字段错误。 |
| 422 | `INVALID_ORIENTATION` | yaw/quaternion 不合法。 |
| 422 | `GOAL_OUTSIDE_MAP` | 目标超出地图。 |
| 422 | `GOAL_OCCUPIED` | 目标栅格不可通行。 |
| 422 | `GOAL_IN_ASSET_COLLISION` | 目标落入膨胀资产碰撞体。 |
| 422 | `GOAL_IN_HAZARD_ZONE` | 目标落入危险区。 |
| 422 | `VELOCITY_LIMIT_EXCEEDED` | 手动速度超限。 |
| 422 | `DEADMAN_REQUIRED` | 非零手动速度缺少 deadman。 |
| 422 | `RESET_CONFIRMATION_REQUIRED` | 紧停复位未显式 confirm。 |
| 422 | `SCENARIO_ACTION_INVALID` | 场景 action 非法。 |
| 422 | `SCENARIO_PARAMETER_INVALID` | 参数不在 allowlist/范围。 |
| 426 | `WEBSOCKET_SUBPROTOCOL_REQUIRED` | 未协商 `substation.v1`。 |
| 429 | `MANUAL_COMMAND_RATE_EXCEEDED` | 超过 10 请求/s。 |
| 500 | `INTERNAL_ERROR` | 未分类服务器错误；用 trace_id 排查。 |
| 500 | `INTERFACE_VERSION_UNSUPPORTED` | 收到不支持的 ROS/Web 主 schema。 |
| 500 | `CAMERA_FRAME_INVALID` | camera framing/JPEG 连续不合法。 |
| 503 | `NOT_READY` | `/readyz` 强制依赖未就绪。 |
| 503 | `DEPENDENCY_UNAVAILABLE` | 非专用依赖故障。 |
| 503 | `ROBOT_STATE_UNAVAILABLE` | 无合法 robot pose/odom。 |
| 503 | `MISSION_STATE_UNAVAILABLE` | 无一致任务快照。 |
| 503 | `NAVIGATION_UNAVAILABLE` | Nav2/map/TF 安全校验不可用。 |
| 503 | `GAZEBO_UNAVAILABLE` | 场景管理不可用。 |
| 503 | `AUDIT_STORAGE_UNAVAILABLE` | 需要审计的操作无法持久化。 |
| 503 | `REPORT_INDEX_UNAVAILABLE` | 报告索引不可读。 |
| 503 | `REPORT_STORAGE_UNAVAILABLE` | 报告文件不可读。 |
| 503 | `EMERGENCY_STOP_PATH_UNAVAILABLE` | Gateway 到安全 Service 的优先路径不可用；UI 按危险状态处理。 |
| WS/4009 | `WS_RESYNC_REQUIRED` | replay 不可能；REST 快照后重连。 |
| 命令终态 | `TIMEOUT` | endpoint 时限到达。 |
| 命令终态 | `EMERGENCY_STOP_ACTIVATED` | 命令被紧停取消。 |
| 系统事件 | `LATE_RESULT_IGNORED` | terminal 后到达的底层结果，仅审计。 |

## 11. 只读诊断例外

服务器 Foxglove Bridge 可订阅本文件 ROS Topic、TF、地图和图像，供开发者在 Foxglove Web 中只读排障；它不是 `REST /api/v1` 或 `WS /ws/*` 的一部分，不承诺产品 schema、频率、replay、命令状态或浏览器兼容性。部署必须关闭 Bridge 的发布、Service 调用和 Action goal 能力，浏览器只连接服务器 Bridge 而不直连 DDS。Foxglove 不可用不得影响产品 Web、任务、风险或证据链；Gateway/Nginx 不可用时也不得把 Foxglove 改造成控制替代路径。
