# 项目状态

## 当前结论

- 当前阶段：Phase 0 文档与契约已完成；Phase 1 环境基线是下一执行阶段。
- Phase 1 执行状态：尚未执行。未安装系统依赖，未创建 ROS 2 功能包，未下载数据或模型，未启动 Gazebo、Nav2、Gateway、前端、Foxglove Bridge 或产品 Nginx 服务，也未修改服务器配置。
- Phase 0 契约快照提交：`d0fb12dbe794221f88abb777f31760bdee655783`（`docs: complete phase zero contracts`）。
- Phase 0 状态记录提交：运行 `git log -1 --format=%H -- README.md docs/PROJECT_STATUS.md docs/HANDOFF.md` 获取。该提交只记录阶段事实和恢复入口；本文不嵌入自身提交哈希。
- 当前阻塞项：无。下一步是否进入 Phase 1 只取决于用户是否要求继续，以及 Phase 1 Task 1/Task 2 的只读 gate 结果。

## Phase 0 已固定的契约范围

- 项目计划、README、仓库执行规则、架构、部署和四份 Accepted ADR。
- ROS topic/service/action、TF、REST、WebSocket、错误码、时间/revision/`uint64` 编码、命令终态和证据归属契约。
- 数据、许可、模型、manifest、版本矩阵、PyTorch CUDA wheel 内容身份和依赖锁定规则。
- Phase 0 静态 gate、Phase 1 环境验收合同，以及 `docs/plans/PHASE-01-ENVIRONMENT.md` 的可执行任务顺序。
- Phase 1 入口边界：先提交只读验证器，再初始化唯一 acceptance run；之后每个任务都单独提交实现和状态/交接记录。

上述完成项仅代表 Phase 0 文档合同冻结，不代表任何 Phase 1 或产品功能已经实现。

## 只读主机事实

以下事实采集于 `2026-07-23T03:17:19Z`，只作为 Phase 1 入口背景；Phase 1 仍必须按计划重新审计并保存证据。

- 物理内存：`16654860288` bytes，约 `15.51 GiB`，满足 Phase 1 文档中的 `15 GiB` 下限。
- 当前仓库挂载点可用空间：`87260987392` bytes，约 `81.27 GiB`。Phase 1 仍必须在每次小资源操作前证明操作后保留至少 `20 GiB`；后续大数据集下载必须另跑 `expected-size + 20 GiB` gate。
- GPU：`NVIDIA GeForce RTX 3060 Ti`。
- NVIDIA 驱动：`595.71.05`。Phase 1 可以审计并保留合格驱动；若实际审计不合格，计划要求停在 `DRIVER_TRANSACTION_REQUIRED`，不得自动运行驱动安装器。

## 验证权威

- 完整 Phase 0 gate：`docs/TEST_ACCEPTANCE.md` 第 4.4 节的唯一 Bash block。
- 辅助聚焦检查：`docs/TEST_ACCEPTANCE.md` 第 4.1 与 4.2 节。
- 提交后最终输出归档：`.superpowers/sdd/final-phase0-fix-report.md`，该目录被忽略，避免为了记录 post-commit 输出而改变已验证的 Git 快照。
- 状态文档不复制 gate 代码；Phase 1 Task 1 的 `scripts/verify_documentation_gate.sh` 必须继续从 `docs/TEST_ACCEPTANCE.md` 第 4.4 节提取并执行权威 block，防止出现第二份漂移副本。

## 下一步入口

等用户要求进入 Phase 1 时，从 `docs/plans/PHASE-01-ENVIRONMENT.md` 的 Task 1 开始：先创建预期失败的 documentation-gate 测试，再实现只读验证器和 acceptance-run 初始化。不得跳过失败测试，不得先安装、下载、启动服务或修改主机。
