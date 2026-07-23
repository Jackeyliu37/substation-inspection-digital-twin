# 项目状态

## 当前结论

- 当前阶段：Phase 1 环境基线 fast-track 正在进行；documentation gate、acceptance run、轻量主机预检、Phase 1 早期资源下载，以及模型/数据职责边界同步已完成。
- Phase 1 执行状态：已下载并锁定 Node.js 24.18.0 tarball 与官方 YOLO11n 占位/base weight。公开训练数据下载和模型微调由用户在仓库外完成；本仓库后续只接收用户发布的不可变 GitHub 模型资产。尚未安装系统依赖，未创建 ROS 2 功能包，未创建虚拟环境，未构建前端，未启动 Gazebo、Nav2、Gateway、前端、Foxglove Bridge 或产品 Nginx 服务。
- Phase 0 契约快照提交：`d0fb12dbe794221f88abb777f31760bdee655783`（`docs: complete phase zero contracts`）。
- Phase 0 状态记录提交：运行 `git log -1 --format=%H -- README.md docs/PROJECT_STATUS.md docs/HANDOFF.md` 获取。该提交只记录阶段事实和恢复入口；本文不嵌入自身提交哈希。
- 当前阻塞项：无。下一步进入 Phase 1 环境安装/工具链准备检查点；继续保留“个人项目 fast-track”：安全审查从简，但不放宽 ROS/Gazebo/headless/哈希/证据边界。

## Phase 1 fast-track 当前状态

- Documentation gate implementation commit：`d049f62bd39b910c2e5fe41ace80b778f14da509`（`feat: add phase one documentation gate`）。
- Acceptance run identity commit：`99a2709f5a0f4d51eb7af99d3c440b06f5e28ad9`（包含 Task 1 实现及当时的阻塞状态记录；后续状态提交不替换该 evidence identity）。
- Fast-track simplification commit：`2f5b2e16c623e32746b42b7fc01626784aabf316`（`docs: simplify phase one fast track`）。
- Lightweight host preflight commit：`9edb7a2ccbe745e9a7123a5385b514c22f10715d`（`feat: add lightweight phase one host preflight`）。
- Resource download implementation commit：`6e79e70274817710ddbd3b347c38bad648886549`（`feat: download phase one base resources`）。
- Model/data responsibility contract commit：`21ea620c656030ec12c902de3cbd9d547b509a39`（`docs: externalize model training inputs`）。
- 验证时间：`2026-07-23T04:13:36Z` 起，至资源下载验证完成。
- Acceptance run id：`a9ab99ee-a85e-4c6f-a9bd-65b421efc8ca`。
- Evidence staging：`/var/lib/substation/evidence/acceptance/a9ab99ee-a85e-4c6f-a9bd-65b421efc8ca/01-environment.staging`。
- 已通过命令：
  - `bash tests/environment/test_documentation_gate.sh`，输出 `documentation-gate: PASS`。
  - `bash scripts/verify_documentation_gate.sh | tee "$gate_log"`，最终行 `documentation-gate: PASS`。
  - `bash tests/environment/test_audit_host.sh`，输出 `audit-host-light-test: PASS`。
  - `source .phase1-run.env && bash scripts/audit_host.sh --evidence-dir "$PHASE1_EVIDENCE_ROOT"`，生成 `host-audit.json` 且 `status` 为 `passed`。
  - `source .phase1-run.env && bash scripts/download_phase1_resources.sh --resource all --evidence-dir "$PHASE1_EVIDENCE_ROOT"`，输出 `phase1-resources: PASS: all`。
  - `source .phase1-run.env && bash scripts/verify_phase1_resources.sh --evidence-dir "$PHASE1_EVIDENCE_ROOT"`，输出 `verify-phase1-resources: PASS`。
  - `bash tests/environment/test_phase1_resources.sh`，输出 `phase1-resource-static-test: PASS`。
  - `bash tests/environment/test_documentation_gate.sh`，新增模型训练职责断言输出 `model-training-boundary: PASS`。
  - `git diff --check`，无输出。
- 初始化命令：
  - 用户在交互式终端运行 `bash scripts/init_phase1_run.sh --gate-log "$gate_log"`。
  - 本会话随后运行 `source .phase1-run.env`、校验 `acceptance_run_id.txt`、`git_commit.txt`、`documentation-gate.log`、`storage-paths-before.tsv`、确认 final target 不存在，并执行 `bash tests/environment/test_documentation_gate.sh | tee "$PHASE1_EVIDENCE_ROOT/test-documentation-gate.log"`。
- 轻量主机预检结论：Ubuntu `24.04.4 LTS`、`x86_64`、物理内存 `16654860288` bytes、仓库和 `/var/lib/substation`、`/opt/substation` 均保留超过 `20 GiB` free；GPU 为 `NVIDIA GeForce RTX 3060 Ti`，driver `595.71.05`；forbidden packages、active project services、active graphics processes 均为空。
- Phase 1 资源 manifest：`artifacts/environment/resource-downloads.tsv`。
- Phase 1 evidence：`documentation-gate.log`、`storage-paths-before.tsv`、`test-documentation-gate.log`、`host-audit.json`、`download-phase1-resources.log`、`resource-downloads.tsv` 已在 staging 目录中。
- 下载资源：
  - `node-linux-x64`：revision `24.18.0`，size `31511588`，SHA-256 `55aa7153f9d88f28d765fcdad5ae6945b5c0f98a36881703817e4c450fa76742`，路径 `/var/lib/substation/downloads/node/24.18.0/node-v24.18.0-linux-x64.tar.xz`。
  - `yolo11n-base`：revision `v8.4.0`，size `5613764`，SHA-256 `0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1`，路径 `/var/lib/substation/models/base/0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1/yolo11n.pt`。
- 下一步：进入 Phase 1 环境安装/工具链准备检查点。不得启动 Gazebo/Nav2/Web/Nginx 服务；不得下载公开训练数据或搜索第三方生产模型。

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
- 当前仓库挂载点可用空间：`87260987392` bytes，约 `81.27 GiB`。Phase 1 仍必须在每次资源操作前证明操作后保留至少 `20 GiB`；后续 Gazebo 合成数据或用户模型资产导入必须另跑 `expected-size + 20 GiB` gate。
- GPU：`NVIDIA GeForce RTX 3060 Ti`。
- NVIDIA 驱动：`595.71.05`。Phase 1 可以审计并保留合格驱动；若实际审计不合格，计划要求停在 `DRIVER_TRANSACTION_REQUIRED`，不得自动运行驱动安装器。

## 验证权威

- 完整 Phase 0 gate：`docs/TEST_ACCEPTANCE.md` 第 4.4 节的唯一 Bash block。
- 辅助聚焦检查：`docs/TEST_ACCEPTANCE.md` 第 4.1 与 4.2 节。
- 提交后最终输出归档：`.superpowers/sdd/final-phase0-fix-report.md`，该目录被忽略，避免为了记录 post-commit 输出而改变已验证的 Git 快照。
- 状态文档不复制 gate 代码；Phase 1 Task 1 的 `scripts/verify_documentation_gate.sh` 必须继续从 `docs/TEST_ACCEPTANCE.md` 第 4.4 节提取并执行权威 block，防止出现第二份漂移副本。

## 下一步入口

Phase 1 下一步是环境安装/工具链准备检查点。继续使用 fast-track：只做计划内依赖、锁文件、空 ROS workspace、AI/Gateway venv、前端 baseline 和 EGL smoke 所需步骤；不得启动产品服务、下载公开训练数据或搜索第三方生产模型。
