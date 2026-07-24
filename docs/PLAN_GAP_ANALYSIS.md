# 项目计划差异清单

本文按根目录项目计划第 14、15、18、19 节逐项核对当前仓库。它不是新的需求文档；它把“代码/契约已经存在”和“真实系统证据还没有”分开，方便人工验收前确认剩余范围。

## 总结

- Phase 0～3：已有文档、环境、Gazebo 世界、合成仪表数据和导航的可复核 evidence。
- Phase 4：四模型训练结果已上传并导入；production ROS 感知管线、仪表 OpenCV 读数和冻结集评估已实现。安全模型 `0.69297` waiver 已按操作员决定接受，不重新训练。
- Phase 5～7：核心节点、持久化、报告服务、Gateway、rosbag2/完整快照和冷启动/急停 barrier 已实现并有契约/集成测试；正式 300 秒、15 FPS live evidence 仍待 release 安装后执行。
- Phase 8～9：前端构建和部署静态契约已通过；按操作员选择改为人工浏览器验收，不再把 Playwright 作为本项目验收前置条件。

## 分阶段核对

| 阶段 | 计划完成定义 | 当前事实 | 状态 |
|---|---|---|---|
| 0 文档门槛 | AGENTS、架构、接口、版本、测试、ADR、状态、交接和阶段计划 | 文档门禁通过，入口齐全 | 已完成 |
| 1 环境基线 | Ubuntu/ROS/Gazebo/GPU/Python/Node 锁定并可验证 | 主机审计、GPU/EGL、依赖和 immutable environment evidence 已通过 | 已完成 |
| 2 变电站世界 | 设备、语义 ID、通道、传感器和无头 Gazebo topic | Phase 2 live acceptance 通过；合成仪表数据生成已完成 | 已完成 |
| 3 SLAM 与导航 | 地图、定位、固定巡检点、动态避障和闭环 | Phase 3 live acceptance 通过，静态/动态目标和局部代价地图已验证 | 已完成 |
| 4 数据与 YOLO | 四模块模型、指标、推理模块和验收报告 | ZIP 已上传；四权重、类别、指标、训练摘要和 SHA-256 已导入。操作员已接受安全模型 `0.69297 < 0.75` 的 waiver，不重新训练 | 实现完成；15 FPS/300 秒 live evidence 待执行 |
| 5 数字孪生与风险 | 设备状态、时间序列、多模态融合、告警和证据 | 风险评分、确认/滞回、孪生、reporting/evidence Service、rosbag2 capture、完整快照和报告 bundle 已实现并测试 | 实现完成；随 Phase 9 live run 封存 |
| 6 风险驱动任务 | 队列、优先级、Nav2 重规划、失败恢复、急停 | 风险重排、SQLite 恢复、任务终态、Nav2 Action、速度仲裁、IDLE→START 和 0.5 秒 motion barrier 已实现并测试 | 实现完成；随 Phase 9 live run 封存 |
| 7 Web Gateway | ROS 聚合、REST、WebSocket、图像流、SQLite、命令确认 | 权威状态、真实 Gateway JPEG、命令终态、report/diagnostic 索引下载和边界契约已验证 | 实现完成；真实 release 联调待执行 |
| 8 Web 前端 | 八页面、三维孪生、地图、视频、风险、场景、报告和控制 | 八工作区、REST/WS-only、构建和前端契约通过 | 待人工验收：真实 Gateway/ROS/Nginx 联调、Windows 浏览器流程 |
| 9 集成与交付 | Nginx、systemd、端到端、Foxglove、报告、演示和文档 | immutable release 构建、五服务依赖、loopback 边界、报告封存和人工 Web 验收口径已实现；installer 现会授予 `substation` 的 `render/video` 设备组 | 待 root 安装后执行 live release、300 秒/15 FPS 和人工 Web 验收 |

## 已上传模型交付核对

| 项目计划要求 | 当前事实 |
|---|---|
| 四个独立 artifact | 已有 `yolo11n_safety`、`yolo11n_equipment`、`yolo11n_fault`、`meter_locator` |
| 权重、指标、训练摘要、类别映射 | ZIP 和 `models/manifest.yaml` 已上传；导入报告记录 SHA-256、大小和指标 |
| 固定来源与完整生产门槛 | 当前来源是用户本地 handoff，不是 GitHub release；已按 operator waiver 接纳，后续严格发布仍建议不可变 release/commit |
| 安全 mAP50 ≥ 0.75 | 未达到：`0.69297`。不应在人工验收中标为严格通过 |
| 仪表 OpenCV 下游 | 已完成独立 OpenCV 读数、DiagnosticArray/evidence_id 和 200 张冻结集评估；报告位于 `/var/lib/substation/evidence/acceptance/35900da2-0e41-4d98-802b-b7e36675e988/04-meter-reader-evaluation.staging/meter-evaluation.json` |
| 15 FPS、300 秒完整 ROS 管线 | 生产节点已恢复真实相机/模块/聚合输出；当前开发用户无 `render/video` 组且 release 尚未安装，正式 300 秒门槛不能提前宣称通过。installer 已修复组权限，root 安装后重新执行。 |

## 请操作员确认的剩余项

以下是基于计划仍需要你确认或亲自执行的事项，按“阻塞最终交付”的优先级排列：

1. **人工 Web 验收**：从 Windows 访问 `http://ros-server/`，确认八个工作区、启动/暂停/继续/停止、地图设点、场景触发、急停/复位、报告下载和断线恢复。记录浏览器截图或验收结论即可；本项目不再要求 Playwright。
2. **真实集成服务**：按 `docs/DEPLOYMENT.md` 安装 immutable release；installer 会将 `substation` 加入 `render`/`video` 组，随后启动 Gazebo → core → Gateway → frontend → Nginx，验证 loopback/LAN 边界和 readiness。
3. **Phase 4/9 生产验收**：safety waiver 已接受且不重新训练；root 安装后执行四模块 ROS 管线 15 FPS/300 秒正式 run。
4. **证据与报告**：capture/verify 工具和报告 bundle 已完成；正式 run 需封存 rosbag2、告警/轨迹/模型快照、HTML/PDF/evidence ZIP。
5. **安全与任务边界**：冷启动 IDLE→START、急停复位 barrier 已有测试和短 smoke；正式 release run 需再次封存现场证据。
6. **交付材料**：操作员亲自进行人工浏览器验收；不要求 Playwright、截图包或 3～5 分钟演示视频。

## 不应误判为缺陷的项目选择

- Windows 端不需要安装 ROS、Gazebo、Python 或 Node.js。
- Playwright 依赖仍在版本矩阵中，但按操作员决定不作为本轮人工验收前置条件。
- 公开训练数据不上传仓库；仓库仅保存来源、许可、manifest、校验值和用户交付的训练结果 ZIP。
- 当前本机没有启动产品服务，这不是代码“漏启动”，而是避免把未完成的 release/LAN 验收伪装成已部署。
