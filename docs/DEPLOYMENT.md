# 部署与运行

## 1. 目标拓扑

目标是单台 Ubuntu 24.04 服务器集中运行 ROS 2 Jazzy、Gazebo Harmonic（`gz-sim 8.x`；精确锁定见 `docs/VERSION_MATRIX.md`）、GPU 推理、SQLite、FastAPI、Next.js、Nginx 和开发诊断所需的 Foxglove Bridge。普通 Windows 操作员只访问 `http://ros-server/`。不在 Windows 安装项目运行时、ROS、Node.js 或项目源码。

服务器保持无桌面：Gazebo 使用 OGRE2/EGL 纯无头渲染，标准命令等价于 `gz sim -s -r --headless-rendering substation_world.sdf`。不得安装或以 Ubuntu Desktop、Xorg、NoMachine、Xvfb 或 VirtualGL 作为图形或故障规避方案。

## 2. 目录与文件所有权

部署以服务器操作员账户 `substation` 为准；该账户的源代码检出目录固定为 `/home/substation/substation-inspection-digital-twin`。不要把运行时可变数据写入源码目录。

| 路径 | 内容 | 可变性与所有者 |
|---|---|---|
| `/home/substation/substation-inspection-digital-twin` | Git 源码检出、受版本控制的 launch、配置、脚本、manifest 和锁文件 | `substation` 操作员维护；不是服务的持久状态目录 |
| `/opt/substation/current` | 当前已验证部署版本的只读运行树（由源码构建/安装的 ROS、Gateway 与前端产物） | 部署程序原子切换；服务只读使用 |
| `/opt/substation/releases/<git-commit>` | 可回滚的、按 Git commit 标识的已验证运行树 | 不在原地修改；保留上一个可用版本作为回滚源 |
| `/opt/substation/config` | systemd 环境文件、Nginx 站点链接和部署固定配置 | 运维受控；敏感值不提交 Git |
| `/var/lib/substation/sqlite` | SQLite 历史、命令、报告索引和 schema 迁移记录 | 证据存储拥有；每日备份输入 |
| `/var/lib/substation/evidence` | JPEG/证据清单与校验值 | 证据存储拥有；不提交 Git |
| `/var/lib/substation/reports` | 生成的 HTML/PDF 与证据包 | 报告组件通过证据存储写入；不提交 Git |
| `/var/lib/substation/rosbag2` | 运行与验收 rosbag2 | 证据存储拥有；不提交 Git |
| `/var/lib/substation/models` | 已下载模型权重与 SHA-256 记录 | 由 manifest 管理；权重本体不提交 Git |
| `/var/log/substation` | `gazebo.log`、`core.log`、`gateway.log`、`frontend.log`、`deployment.log` 与轮转后的日志 | 服务写入，使用 logrotate；日志不提交 Git |

`/var/lib/substation`、`/var/log/substation` 和 `/opt/substation` 由受权限控制的部署步骤创建；源代码始终由 `substation` 用户通过 Git 恢复。数据集原始文件与训练产物不属于 Git 部署物，只有下载/转换脚本、manifest 和校验值进入仓库。

## 3. 网络和服务边界

| 服务 | systemd 单元 | 绑定 / 暴露 | 依赖与职责 |
|---|---|---|---|
| Gazebo 仿真 | `substation-gazebo.service` | 无 LAN 监听；ROS DDS 在服务器内 | 启动 Harmonic `gz-sim 8.x`、OGRE2/EGL 无头世界与传感器 |
| ROS 核心 | `substation-core.service` | 无 LAN 监听；ROS DDS 在服务器内 | 描述、SLAM/Nav2、感知、数字孪生、风险、任务和报告 |
| FastAPI Gateway | `substation-web-gateway.service` | 仅 `127.0.0.1:8000` | `rclpy`、REST、WebSocket、JPEG、SQLite 历史/报告索引与命令边界 |
| Next.js 前端 | `substation-web-frontend.service` | 仅 `127.0.0.1:3000` | 生产 Web 应用；只调用 Nginx/Gateway 定义的 Web 接口 |
| Nginx | `nginx.service` | LAN TCP/80，主机名 `ros-server` | 唯一普通操作员入口；代理 `/`、`/api/`、`/ws/` 到回环服务 |
| Foxglove Bridge | `substation-foxglove-bridge.service` | 仅在开发诊断时按运维访问控制启用；浏览器连接 Bridge 而非 DDS | 服务器侧读取 ROS 数据的独立只读诊断路径；不是普通操作员入口或产品控制平面，不能发布命令或 Topic，未启用不阻塞系统 |

端口号、TLS 和鉴权等接口细节由 `docs/INTERFACES.md` 与 Nginx 配置冻结；本文件固定的安全边界是不变的：产品 Gateway 和前端只能回环绑定，Nginx 才能对局域网提供产品 Web UI。产品 UI 的全部状态与控制都经 Gateway；Foxglove Web 是经服务器 Bridge 的独立只读开发诊断路径，浏览器不直连 DDS，也没有命令或 Topic 发布能力。Nginx 代理失败时，不允许用浏览器直连 Gateway 或 ROS DDS 作为替代。

## 4. 启动、停止与就绪顺序

`substation-gazebo.service` 和 `substation-core.service` 使用 `/opt/substation/current`，并以 `substation` 用户运行。Gateway 在核心就绪后启动；前端在 Gateway 回环健康检查可用后启动；Nginx 最后暴露入口。推荐顺序如下：

1. 验证挂载、目录权限、GPU 驱动、EGL 和 `/opt/substation/current` 指向一个完整 release。
2. 启动 `substation-gazebo.service`；确认无 `DISPLAY` 依赖且相机、LiDAR 和仿真时钟就绪。
3. 启动 `substation-core.service`；确认描述/TF、感知、数字孪生、风险、任务和 Nav2 健康。
4. 启动 `substation-web-gateway.service`；确认回环健康/就绪检查、ROS 连接和 SQLite 可写。
5. 启动 `substation-web-frontend.service`；确认其仅在回环地址响应。
6. 启动或 reload `nginx.service`；从 LAN 访问 `http://ros-server/`，确认 `/api/` 与 `/ws/` 由 Nginx 代理。
7. 需要排错时再启动 Foxglove Bridge；确认它只从服务器侧读取 ROS 数据、Foxglove Web 只读连接 Bridge 且不能发布命令或 Topic。它不是前六步的前置条件。

按相反顺序停止外部入口、前端、Gateway、核心和 Gazebo。发生异常时，先保留 `/var/log/substation` 和 `/var/lib/substation` 证据，再停止会改变现场状态的服务。紧急停止不能等待前端、Nginx 或 Foxglove 恢复。

## 5. 备份、升级与回滚

### 5.1 备份输入

每次升级前、每日以及重大场景验收后备份以下内容，并记录 backup manifest、Git commit、时间和 SHA-256：

- `/var/lib/substation/sqlite`；
- `/var/lib/substation/evidence`、`reports` 和需要保留的 `rosbag2`；
- `/var/lib/substation/models` 的 manifest 与权重校验值；
- `/opt/substation/config`；
- `/var/log/substation` 中与该运行/升级相关的日志；
- 源码检出的 Git commit、锁文件、Nginx 配置版本和当前 release 指针。

备份不改变原始公开数据；大数据、模型、日志和 rosbag2 只按保留策略存放在服务器或备份介质，不能直接提交 Git。

### 5.2 升级顺序

1. 在 `/home/substation/substation-inspection-digital-twin` 获取并审阅目标 Git commit，确认 ADR、版本矩阵、锁文件和验收基线一致。
2. 在不修改 `/opt/substation/current` 的情况下构建候选运行树到 `/opt/substation/releases/<git-commit>`，执行该版本的部署前检查。
3. 备份第 5.1 节输入；若有 SQLite schema 迁移，先验证可恢复备份和迁移兼容性。
4. 停止 Nginx 外部入口、前端和 Gateway；在安全状态下停止或保持核心服务，绝不绕过锁存紧急停止。
5. 原子切换 `/opt/substation/current` 到候选 release，按第 4 节顺序启动并执行恢复检查。
6. 只有全部恢复检查通过后才把候选标记为当前部署；保留前一 release 和备份。

任何版本变更先需新增 ADR，并同步项目计划、锁文件和测试基线；不得在服务器上临时升级单个包来替代该流程。

### 5.3 回滚来源与恢复

回滚源是 `/opt/substation/releases/<previous-verified-git-commit>`、升级前 `/var/lib/substation` 备份以及该 commit 的 `/home/substation/substation-inspection-digital-twin` Git 历史。停止外部入口后将 `current` 指回前一已验证 release；如迁移导致数据不兼容，从同一升级批次的 SQLite/证据备份恢复，再按第 4 节启动。不得用未验证的工作树、训练输出或浏览器本地文件作为回滚来源。

## 6. 恢复检查与明确降级

恢复后至少确认：

1. `systemctl` 显示 Gazebo、核心、Gateway、前端和 Nginx 均处于预期状态；Foxglove 可处于未启动状态。
2. Gazebo 在没有 `DISPLAY` 的情况下以 OGRE2/EGL headless 运行，且相机/激光传感器有数据。
3. 核心健康检查确认数字孪生、风险、任务和 Nav2 已连接；Gateway 回环健康检查确认 SQLite 可读写。
4. Gateway 和前端只监听 `127.0.0.1`，Nginx 以 `http://ros-server/` 提供页面、`/api/` 和 `/ws/`。
5. 浏览器以 REST 快照后接收 WebSocket 心跳；断线超过 5 秒必须禁用普通控制。验证紧急停止、命令确认和恢复流程仍可用。
6. 检查最新日志、证据清单和备份 manifest；不以“服务已启动”替代传感器、持久化和 Web 路径验证。

EGL 失败时检查 NVIDIA 驱动、OGRE2、EGL 和无头传感器日志；不要安装桌面或虚拟显示软件。WebSocket 积压时按 Gateway 主题限频、只保留最新遥测，前端从 REST 快照恢复。资源不足时将训练与仿真分时运行，并降低非关键传感器或视频刷新率；不可通过关闭风险确认、审计或紧急停止保证表面可用。

相关架构决定见 [ADR-0001](adr/0001-headless-gazebo.md)、[ADR-0002](adr/0002-server-web-deployment.md) 和 [ADR-0003](adr/0003-multimodel-perception.md)。
