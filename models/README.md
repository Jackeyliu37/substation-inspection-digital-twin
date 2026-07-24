# Phase 4 模型交付

用户训练结果**已经上传到 Git**：

```text
artifacts/phase4/substation_yolo_runs.zip
```

归档 SHA-256 为 `fae3721cbe65b9fa09f24972ab36a5c45df54d0a9f97fa7e9d5cb87e619235ce`，大小 `83,036,921` 字节。导入报告、数据/模型校验和加载 smoke 位于同一目录；规范 manifest 为 [`models/manifest.yaml`](manifest.yaml)。

归档内包含四个训练 run 的 `best.pt`、`last.pt`、训练参数、`results.csv` 和图表。经校验后，服务器将按内容地址复制到：

```text
/var/lib/substation/models/production/<sha256>/
```

Git 中保存的是交付归档和可追溯元数据，服务器运行时使用的是经过 SHA-256 校验的生产副本，不在工作树中散落可变权重。

| 逻辑模型 | 指标 | 当前结论 |
|---|---:|---|
| `yolo11n_safety` | mAP50 `0.69297` | 低于 `0.75`，按 operator-approved waiver 接纳 |
| `yolo11n_equipment` | mAP50 `0.84187` | 达到门槛 |
| `yolo11n_fault` | accuracy top-1 `0.99673` | 计划未规定数值下限，保留追溯结果 |
| `meter_locator` | mAP50 `0.99500` | OpenCV 读数仍需完整运行验收 |

这份 ZIP 是用户本地 handoff，不是不可变 GitHub Release。若要撤销 waiver 或做严格生产发布，应重新训练并以不可变 release/commit 交付，再运行完整四模块 ROS 管线、15 FPS/300 秒和仪表读数验收。
