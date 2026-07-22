# ADR-0002：服务器集中部署与统一 Web 入口

- 状态：Accepted
- 日期：2026-07-22

## 背景

ROS 2、Gazebo、GPU 推理、SQLite、FastAPI、Next.js、报告和全部证据必须共享同一 Ubuntu 服务器环境。普通 Windows 用户要通过一个地址完成日常巡检；浏览器不能直接连接 ROS DDS 或发布 Topic。单操作员、局域网是本期范围。

## 已考虑的方案

1. **服务器集中运行、Nginx 统一入口（选择）。** ROS 与 GPU 服务留在 Ubuntu；FastAPI Gateway 和 Next.js 仅监听回环地址，Nginx 向 LAN 暴露 `http://ros-server/`。
2. **Windows 客户端运行 ROS、Gazebo、Node.js 或本地项目副本。** 会复制 DDS、CUDA、Python 和 Node 环境，破坏单一运行证据并提高版本漂移风险。
3. **浏览器直接连接 ROS DDS，或直接暴露 FastAPI 给 LAN。** 前者违反唯一 Web Gateway 边界；后者绕过 Nginx 的统一入口和代理策略。

## 决定

所有项目服务、源码、数据、模型、SQLite 与运行证据集中在 Ubuntu 服务器。源代码在 `/home/substation/substation-inspection-digital-twin`；部署 release 位于 `/opt/substation`，可变状态位于 `/var/lib/substation`，日志位于 `/var/log/substation`。FastAPI 与 Next.js 只绑定 `127.0.0.1`，Nginx 才能向局域网公开 TCP/80 的 `http://ros-server/`、`/api/` 与 `/ws/`。Gateway 是浏览器到 ROS 的唯一命令和状态边界；SQLite 不提供网络数据库服务。

## 后果

- 普通操作员只需浏览器；Windows 无需安装项目依赖，所有可追溯证据保留在服务器。
- Nginx、Gateway、前端和 ROS 形成可独立检查的进程边界，Gateway 负责命令校验、限频和断线降级。
- Gateway 或 Nginx 故障不会让浏览器改连 DDS；自治 ROS 服务可保持其已接受任务，浏览器普通控制在心跳丢失后被禁用。
- 单服务器、单操作员限制了横向扩展能力；备份、原子 release 切换和回滚是运行保障的必要部分。

## 可以被取代的条件

只有在项目计划先明确改为多站点、多操作员、互联网访问或高可用部署，并且完成威胁建模、身份认证、TLS、授权、审计、故障切换和性能验收时，才可新建一个 Superseding ADR。该 ADR 还必须更新部署路径、接口契约、Nginx/服务配置、版本锁定和恢复测试。仅因希望从 Windows 直接运行组件或临时打开端口，不足以取代本决定。
