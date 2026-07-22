# 仓库执行规则

## 目标、范围与权威来源

唯一目标是实现[项目计划](./基于数字孪生与多模态风险感知的变电站智能巡检系统_项目计划.md)定义的变电站智能巡检系统；不得增加与验收无关的功能。

信息冲突时必须按以下顺序处理：

1. 用户当前明确指令；执行后同步更新项目计划和受影响规范。
2. [项目计划](./基于数字孪生与多模态风险感知的变电站智能巡检系统_项目计划.md)：项目范围、最终架构和交付目标的唯一事实来源。
3. [ADR](./docs/adr/)：已批准的具体架构选择；改变决定时新建 ADR，不覆盖历史 ADR。
4. 专项规范：[ARCHITECTURE](./docs/ARCHITECTURE.md)、[DEPLOYMENT](./docs/DEPLOYMENT.md)、[INTERFACES](./docs/INTERFACES.md)、[TEST_ACCEPTANCE](./docs/TEST_ACCEPTANCE.md)、[VERSION_MATRIX](./docs/VERSION_MATRIX.md) 与 [DATA_AND_MODELS](./docs/DATA_AND_MODELS.md)。其中 ARCHITECTURE、INTERFACES、TEST_ACCEPTANCE 和 VERSION_MATRIX 分别约束设计、接口、验证和版本。
5. 阶段计划：[PHASE-01-ENVIRONMENT](./docs/plans/PHASE-01-ENVIRONMENT.md)；只规定当前阶段的实现方式，不得扩大范围或修改架构。
6. 当前事实与恢复入口：[PROJECT_STATUS](./docs/PROJECT_STATUS.md) 和 [HANDOFF](./docs/HANDOFF.md)；不得用它们改变需求或技术决策。

发现权威文档冲突时，停止受影响实现，明确报告冲突，先修正权威文档；不得自行选择一种解释继续开发。

## 不可变约束

1. 唯一目标是实现项目计划定义的变电站智能巡检系统；不得增加与验收无关的功能。
2. 固定使用 Ubuntu 24.04、ROS 2 Jazzy 和 Gazebo Harmonic；禁止引入 ROS 1、Gazebo Classic 或其他 ROS 发行版。
3. Gazebo 固定使用 OGRE2/EGL 纯无头模式；禁止安装 Ubuntu 桌面、Xorg、NoMachine、Xvfb 和 VirtualGL。
4. Windows 普通使用者只访问 `http://ros-server/`；全部项目服务、源码、数据和运行证据位于 Ubuntu 服务器。
5. 浏览器不得直连 ROS DDS 或发布 Topic；所有状态和命令必须经过 FastAPI ROS Web Gateway。
6. 仪表数据只使用 Gazebo 合成数据；不得重新加入外部仪表数据集。
7. 安全检测、设备检测、缺陷分类和仪表读数必须保持独立模块；不得合并为未经评估的大模型。
8. 不得自行升级 [VERSION_MATRIX](./docs/VERSION_MATRIX.md) 中的版本；版本变化必须先新增 ADR，并同步项目计划、锁文件和测试基线。
9. 每个功能必须先有测试和验收条件；没有实际命令输出、日志或产物证据时不得标记完成。
10. 每次任务结束必须更新 [PROJECT_STATUS](./docs/PROJECT_STATUS.md) 和 [HANDOFF](./docs/HANDOFF.md)，记录 commit、验证命令、结果和下一步。
11. 不修改原始公开数据；转换数据、训练产物、日志和 rosbag2 不直接提交 Git，仓库只保存 manifest、脚本和校验值。
12. 发现规范冲突时停止相关实现，明确指出冲突并先更新权威文档；不得自行选择一种解释继续开发。

## 允许与禁止的操作

- 允许：在项目计划、ADR、专项规范和当前阶段计划的边界内创建源代码、配置、测试、文档、manifest、脚本和校验值；在 Ubuntu 服务器上执行经计划定义的构建、测试和无头验证。
- 禁止：创建验收范围外的功能；将浏览器接入 DDS；使用远程桌面或虚拟显示栈；修改原始公开数据；提交大型转换数据、训练产物、日志或 rosbag2；以状态/交接文档替代权威决策。
- Phase 0 文档门槛通过前，不安装系统依赖、不创建 ROS 2 功能包、不下载数据或模型、不启动 Gazebo/Nav2/Web 服务，也不修改服务器配置。

## 构建、验证与完成

使用阶段计划和 [TEST_ACCEPTANCE](./docs/TEST_ACCEPTANCE.md) 中与当前任务相符的命令类别：环境检查与锁定清单、ROS `colcon build`/节点测试、Python 单元与集成测试、Gazebo 无头传感器验证、Gateway API/WebSocket 测试、Web `npm ci`/生产构建、Playwright 端到端测试，以及证据归档检查。不得把未运行的命令、无日志的观察或静态推测当作完成证据。

项目仅在满足[项目计划第 19 节](./基于数字孪生与多模态风险感知的变电站智能巡检系统_项目计划.md#19-项目完成定义)时完成：文档门槛和新服务器重建均有记录；Gazebo、ROS 2、YOLO11n、风险融合和 Nav2 构成实际闭环；高风险会改变任务优先级与路径；Windows 浏览器通过一个 Web 地址完成日常使用；结果可追溯到版本、时间戳、rosbag2 与报告证据；Web、Foxglove 和无头 Gazebo 均经验证；所有交付物均已完整填写，链接、命令、版本和路径已复核。
