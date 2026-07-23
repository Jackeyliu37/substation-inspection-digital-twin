# 数据与模型治理

## 1. 范围与不可变边界

本文规定公开数据、Gazebo 合成数据、标注转换、训练、评估、模型发布和追溯规则。仓库只保存 manifest、脚本、许可/引用说明和校验值；原始公开数据、转换数据、训练产物、模型权重、日志与 rosbag2 均不得直接提交 Git。

四个感知模块必须保持独立：

1. `safety_detector`：安全风险检测；
2. `equipment_detector`：变电站设备检测；
3. `defect_classifier`：设备裁剪图的缺陷分类；
4. `meter_reader`：独立 `meter_locator` YOLO11n 表盘定位，加 OpenCV 透视/刻度/指针后处理的仪表读数。

不得把它们合并为未经评估的单一大模型。温度、烟雾、气体和设备上下文通过 ROS 测量接口进入风险融合，不得伪装成视觉类别。Gazebo 场景真值只用于自动标签、场景验收和证据，绝不作为运行时感知输入。仪表训练和评估数据只允许使用 Gazebo 合成数据，不得加入外部仪表数据集。

## 2. 数据目录、所有权与生命周期

源码检出中的受控入口固定为：

```text
datasets/
├── manifest.yaml
└── README.md
models/
├── manifest.yaml
└── README.md
scripts/
├── download_datasets.py
└── convert_annotations.py
```

服务器数据根目录由后续阶段在受控存储中建立，推荐布局如下；这些目录不进入 Git：

```text
/var/lib/substation/datasets/
├── raw/<dataset_id>/<revision>/
├── derived/<dataset_id>/<conversion_id>/
├── synthetic/<generator_id>/<generation_id>/
└── manifests/<manifest_sha256>.yaml
/var/lib/substation/models/
├── base/<artifact_sha256>/
├── training/<training_run_id>/
├── released/<artifact_sha256>/
└── manifests/<manifest_sha256>.yaml
```

- `raw` 下载完成并校验后改为只读；任何清洗、重命名、转换、裁剪、增强或 split 文件都写入新的 `derived`/`synthetic` 目录。
- 路径身份只用于定位，内容身份始终是 SHA-256。不得覆盖已有 revision、conversion、generation 或 model artifact。
- 训练临时目录和缓存可按保留策略清理，但发布权重、评估报告、manifest、训练配置、日志摘要和校验值必须保留到关联运行/报告的证据保留期结束。
- 每次转换和训练都记录执行脚本的 Git commit；dirty working tree 产物不得晋升为发布模型。

## 3. 数据源登记

| `dataset_id` | 用途 | 固定来源与 revision | 数量基线 | 许可与允许用途 | 接纳规则 |
|---|---|---|---:|---|---|
| `substation-equipment-15` | 设备检测主数据 | [15-class Substation Equipment](https://huggingface.co/datasets/AndrzejDD/15-class-Substation-Equipment)，revision `c63ed3c7f5ea33ac8e9024c467a70a62b849b2ad` | train 5,023；val 601；test 1,452；总计 7,076 | Apache-2.0；按许可用于本项目训练、评估和可复现研究 | 必须保持原始 split；数量、revision、YOLO 标注和全部文件 SHA-256 同时匹配 |
| `hard-hat-workers-v10` | 人员/PPE 安全检测 | [Hard Hat Workers v10](https://public.roboflow.com/object-detection/hard-hat-workers/10)，版本 10 | 7,041 张 | CC0；可用于安全检测训练/评估 | 下载时固定导出格式为 YOLO，记录实际导出 URL、导出时间、archive 和逐文件 SHA-256；缺少这些字段不得接纳 |
| `d-fire` | 火焰/烟雾安全检测和负样本 | [D-Fire](https://github.com/gaia-solutions-on-demand/DFireDataset)，commit `4bf9c31b18fadcd44d5f0b6d66f82bc56fa5e328` | 超过 21,000 张；fire 框 14,692；smoke 框 11,865；无烟火负样本 9,838 | CC0 1.0；可用于安全检测训练/评估 | checkout 必须精确等于固定 commit；记录仓库内容清单 SHA-256，保留负样本，不得只下载正样本 |
| `insplad` | 设备检测补充与独立缺陷分类 | [InsPLAD](https://github.com/andreluizbvs/InsPLAD)：10,607 张 Full-HD 图、28,933 个实例、17 类资产；`InsPLAD-fault` 含 5 类资产、6 种状态 | 以接纳 manifest 的精确统计为准 | **CC BY-NC 3.0**；仅限非商业教学研究，派生模型和演示必须保留署名、许可与非商业限制 | 根项目计划未固定 commit；下载脚本必须先解析完整 40 位 commit，连同 archive/逐文件 SHA-256 写入 manifest。未完成时状态必须为 `blocked`，不得跟随默认分支训练 |
| `gazebo-meter` | 表盘定位、透视校正和读数 | 项目 Gazebo 生成器、场景配置、资产配置、版本和 seed 组合锁定 | 至少 **2,000** 张仪表图 | 项目自有；仅由 Gazebo 自动标签 | 是仪表模块唯一允许的数据来源；必须覆盖表盘、指针读数、光照、视角、模糊和遮挡，并按场景组 split |
| `gazebo-anomalies` | 域适配及缺陷/异常补充 | 项目 Gazebo 生成器、场景配置、资产配置、版本和 seed 组合锁定 | 每类异常不少于 **500** 张 | 项目自有；仅由 Gazebo 自动标签 | 至少覆盖设备热点、烟雾源和绝缘子外观变化；实际场景配置中每个启用异常类都必须分别达到 500，不能用总数替代每类计数 |

不得直接重新发布来源数据。任何来源的许可文件、引用文本、主页 URL、revision 和用途限制都必须随 manifest 保存；许可未知、冲突或无法验证时停止该来源的转换与训练。

## 4. 规范类别与映射

### 4.1 安全检测

安全模型输出前缀固定为 `safety/`，训练标签映射如下：

| 来源 | 原始标签 | 规范标签 |
|---|---|---|
| Hard Hat Workers v10 | `person` | `person` |
| Hard Hat Workers v10 | `helmet` | `hardhat` |
| Hard Hat Workers v10 | `head` | `no_hardhat` |
| D-Fire | `fire` | `fire` |
| D-Fire | `smoke` | `smoke` |

模型 artifact 逻辑名固定为 `yolo11n_safety.pt`，类别顺序固定为 `person=0`、`no_hardhat=1`、`hardhat=2`、`fire=3`、`smoke=4`。任何同图中 `head`/`helmet` 的语义冲突必须由转换报告列出，不能静默改标签。运行时 `vision_msgs/Detection2D` 的 `class_id` 使用 `safety/<class>`。

### 4.2 设备检测

设备模型输出前缀固定为 `equipment/`。15-class 主数据集按下表建立项目唯一整数 ID，不沿用其他数据源的原始 ID：

| ID | 原始类名 | 规范类名 |
|---:|---|---|
| 0 | `Open blade disconnect switch` | `open_blade_disconnect_switch` |
| 1 | `Closed blade disconnect switch` | `closed_blade_disconnect_switch` |
| 2 | `Open tandem disconnect switch` | `open_tandem_disconnect_switch` |
| 3 | `Closed tandem disconnect switch` | `closed_tandem_disconnect_switch` |
| 4 | `Breaker` | `breaker` |
| 5 | `Fuse disconnect switch` | `fuse_disconnect_switch` |
| 6 | `Glass disc insulator` | `glass_disc_insulator` |
| 7 | `Porcelain pin insulator` | `porcelain_pin_insulator` |
| 8 | `Muffle` | `muffle` |
| 9 | `Lightning arrester` | `lightning_arrester` |
| 10 | `Recloser` | `recloser` |
| 11 | `Power transformer` | `power_transformer` |
| 12 | `Current transformer` | `current_transformer` |
| 13 | `Potential transformer` | `potential_transformer` |
| 14 | `Tripolar disconnect switch` | `tripolar_disconnect_switch` |

InsPLAD-det 只允许补充可由人工审查表逐字、一对一映射到上述 15 个规范类的实例。映射表必须列出每个 InsPLAD 原始类的 `mapped_to` 或 `excluded_reason`；禁止按近似词自动合并，也禁止为接入 InsPLAD 擅自扩展产品设备类别。模型 artifact 逻辑名固定为 `yolo11n_equipment.pt`，运行时类名为 `equipment/<canonical_class>`。

### 4.3 缺陷分类

缺陷模块是设备裁剪图分类，不得把状态标签并入设备检测输出头。模型基于 `yolo11n-cls`，artifact 逻辑名固定为 `yolo11n_fault.pt`，运行时类名前缀为 `defect/`。

项目计划授权的最小报告语义为 `normal`、`corrosion`、`broken_component` 和 `bird_nest`。InsPLAD-fault 实际 6 种状态必须在接纳 manifest 中逐项映射：能无歧义对应这四类的进入训练；其余源标签必须记录 `excluded_reason`，不得并入含义最接近的类。新增规范缺陷类会改变产品语义，必须先更新根项目计划和接口/验收规范；本文不以“等”字虚构额外类别。

Gazebo 缺陷裁剪图只能补充同一规范类别，并记录自动标签来源、资产 ID、场景 ID 和 seed。设备裁剪必须按原始图像/场景组保持 split，禁止同一源图的不同裁剪跨 train/val/test。

### 4.4 仪表读数

仪表模块由两个保持边界的阶段组成：独立 `meter_locator` YOLO11n 模型只定位表盘，逻辑部署权重固定为 `yolo11n_meter.pt`；其下游 OpenCV 再完成透视校正、圆盘/刻度/指针分析。OpenCV 读数不是第四个合并模型，也不得把其他三个模块的输出头并入 `meter_locator`。最终输出不是自由文本类别，而是 `reading`、资产配置提供的 `unit`、`confidence_0_1`、`valid` 和 `evidence_id`，经 `/perception/meters/readings` 发布。

生成标签必须包含：`asset_id`、`sensor_id`、表盘框、四角/姿态参数、量程、单位、真实读数、指针角、光照、模糊、遮挡、场景 ID、seed 和生成器 Git commit。单位与量程只来自版本控制的资产配置；模型不得自由生成单位。

## 5. Split、去重与转换规则

1. 公开数据保留来源的 train/validation/test 边界。若来源没有官方 split，下载接纳阶段按不可变样本组、seed 42 生成一次并记录排序算法与 split 文件 SHA-256；后续不得重新随机划分以改善指标。
2. 同一来源图像、视频相邻帧、同一原图裁剪、同一 Gazebo 场景族或由相同基础样本增强得到的图必须属于同一 split。
3. Gazebo 数据按场景组划分。测试 split 的设备布局、光照组合和相机角度组合不得出现在训练 split；seed 不得作为绕过场景隔离的唯一差异。
4. 转换前计算 byte SHA-256，另计算图像像素摘要用于检测重编码重复。发现跨 split 重复即失败并生成人工处理清单，不自动移动或删除原始数据。
5. COCO、VOC 或其他检测格式统一转换为 YOLO `class x_center y_center width height`，坐标归一化到 `[0,1]`；无效框、越界框、零面积框、未知类或缺图标签均使转换失败。
6. 分类数据保持独立目录；检测框与设备裁剪分类标签不得共享同一 data YAML 或输出头。
7. 所有转换输出按稳定路径排序；相同输入、脚本 commit、配置和 seed 必须生成相同 split、标签内容、split manifest SHA-256 和 content manifest SHA-256。登记文件的生成时间不得参与数据内容或 split 决策。
8. 数据增强参数属于训练配置而非原始数据。增强后样本不得回写 `raw`，也不得被当作独立原始样本提高计数。

## 6. `datasets/manifest.yaml` 合同

manifest 使用 UTF-8 YAML，顶层 key 固定并按字典序序列化后计算文件 SHA-256。schema 1 至少包含：

```yaml
schema_version: 1
generated_at: RFC3339-UTC
generator_git_commit: 40-char-git-sha
sources:
  - dataset_id: stable-kebab-case
    purpose: safety-detection
    source_url: canonical-url
    license_spdx: CC0-1.0
    license_url: canonical-license-url
    permitted_use: explicit-human-readable-rule
    revision_type: git-commit
    revision: immutable-revision
    status: accepted|blocked|rejected
    block_reason: empty-string-or-nonempty-block-explanation
    archive_sha256: 64-lowercase-hex
    file_manifest_sha256: 64-lowercase-hex
    file_manifest_path: relative-path-under-data-root
    original_splits:
      train: integer
      val: integer
      test: integer
    class_mapping:
      source-label: canonical-label-or-null
    excluded_labels:
      source-label: explicit-reason
derived_datasets:
  - dataset_id: stable-kebab-case
    module: safety
    source_dataset_ids: [stable-kebab-case]
    conversion_git_commit: 40-char-git-sha
    conversion_config_sha256: 64-lowercase-hex
    split_manifest_sha256: 64-lowercase-hex
    content_manifest_sha256: 64-lowercase-hex
    sample_counts:
      train: integer
      val: integer
      test: integer
```

示例值只说明字段类型，不是已取得资源的事实。`status` 只能为 `accepted`、`blocked` 或 `rejected`；`accepted` 才允许进入转换、训练、推理或验收，`blocked` 和 `rejected` 都必须被工具拒绝。blocked 时 `block_reason` 必须是非空、可审计的明确原因；accepted/rejected 时它必须是空字符串，不能以未解释 null、pending 或自然语言猜测替代。实际 manifest 不得含示例 URL、伪造摘要、空 revision、浮动版本、默认分支名、未填写占位标记或未解释的 null。Roboflow 没有 Git commit 时使用 `revision_type: provider-version` 和 revision `10`；Gazebo 使用 `revision_type: generated`，revision 由生成器 commit、配置摘要、Gazebo 版本和 seed 清单的 SHA-256 组成。

每个 `file_manifest_sha256` 必须与 `file_manifest_path` 指向的同一份按相对路径字节序排序的 TSV 内容摘要清单相匹配，路径以 data root 为基准、使用 `/`、不得为绝对路径、不得含 `..`、空段或反斜杠，推荐为 `raw/<dataset_id>/<revision>/file-manifest.tsv`。TSV 行格式为 `sha256<TAB>size_bytes<TAB>relative_path`。校验器必须读取 path 中的文件、重算它的 SHA-256 并逐项验证，不能只信任摘要字符串。绝对路径、用户名和下载 token 不得进入受控 manifest。

`insplad` 在精确 40 位 commit、archive SHA-256、file manifest path 与逐文件 SHA-256 全部取得前，唯一合法条目是 `status: blocked` 和非空 `block_reason: "exact upstream commit and file hashes have not been accepted"`；禁止使用默认分支、临时 tag 或“以后补充”来绕过这一门槛。其他来源在缺少相同接纳字段时也必须是 blocked/rejected，而非假定 accepted。

## 7. 训练基线与可复现性

安全检测、设备检测、缺陷分类和独立仪表定位四个 YOLO11n artifact 共用以下不可变起点：

```yaml
model: yolo11n.pt
imgsz: 640
epochs: 100
batch: 8
device: 0
workers: 6
seed: 42
patience: 20
```

- 安全检测与设备检测分别训练，使用各自 data YAML、指标和权重；禁止拼成一个检测模型。
- 缺陷分类使用相同 seed 和独立分类配置；检测超参数中不适用于分类的字段必须由训练配置明确标为不适用，不能被静默解释。
- `meter_locator` 只使用 `gazebo-meter` 数据的表盘框训练，逻辑部署名为 `yolo11n_meter.pt`；它的定位指标与 OpenCV 读数误差分别评估，不能用其中一项代替另一项。
- RTX 3060 Ti 首先使用 `batch=8`。只有出现有日志证据的显存不足时允许改为 4；该变更写入训练 manifest。不得通过降低 `imgsz=640` 掩盖显存问题。
- 每次训练记录命令、环境 lock SHA-256、GPU/驱动、基础权重 SHA-256、数据 manifest SHA-256、完整配置、seed、开始/结束时间、Git commit、stdout/stderr、最佳/最终 epoch 和退出码。
- 训练和全速 Gazebo 仿真分时运行。资源降级不得关闭风险确认、审计或紧急停止链路。

## 8. 评估、发布门槛与允许用途

| 模块 | 固定评估输入 | 必须产出的指标 | 发布/失败判据 |
|---|---|---|---|
| 安全检测 | safety manifest 中冻结的公开 test split，640×640 | 总体 `mAP50`、每类 AP、precision、recall、混淆矩阵、完整 ROS 图像管线 FPS | 总体 `mAP50 >= 0.75` 且完整 ROS 管线 `>= 15 FPS`；任一必需指标/每类 AP 缺失、测试集变化或追溯字段缺失即失败 |
| 设备检测 | equipment manifest 中冻结的公开 test split，640×640 | 总体 `mAP50`、15 类逐类 AP、precision、recall、混淆矩阵、完整 ROS 图像管线 FPS | 总体 `mAP50 >= 0.75` 且完整 ROS 管线 `>= 15 FPS`；不能用总体 mAP 隐藏未报告的小类 |
| 缺陷分类 | fault manifest 中冻结的独立 test split | Balanced Accuracy、逐类 recall、混淆矩阵、推理速度 | 根项目计划没有授权数值下限，因此这是强制报告和追溯门槛，不虚构通过阈值；指标缺失、非有限数、split 泄漏或类别映射不一致即失败 |
| 仪表读数 | 仅 Gazebo meter 冻结 test 场景；独立 `meter_locator` artifact 加 OpenCV 下游 | `yolo11n_meter.pt` 定位 AP、定位推理速度、OpenCV 有效读数率、绝对误差分布、按表型/光照/视角/模糊/遮挡分组结果 | 根项目计划没有授权数值下限；meter locator 权重/摘要缺失、外部仪表数据、真值泄漏、单位不来自配置、分组结果缺失或样本少于 2,000 即失败 |

单帧安全误检不得直接触发紧急任务；运行验收还必须验证连续帧确认、滑动平均与滞回。每个检测/读数都必须追溯到源图像、ROS 时间戳、`evidence_id`、模型 artifact SHA-256、数据 manifest SHA-256 和 Git commit。

InsPLAD 参与训练的模型继承 CC BY-NC 3.0 非商业限制。manifest 和报告必须明确标记 `noncommercial-only`；不得把该权重错误标为可商业使用。其他数据的许可也不因转换、混合或蒸馏而消失。

## 9. 模型 artifact 与 `models/manifest.yaml`

不可变权重文件名固定为：

```text
<logical_model>--<training_run_id>--sha256-<first16>.pt
```

其中 `logical_model` 只能为 `yolo11n_safety`、`yolo11n_equipment`、`yolo11n_fault` 或 `meter_locator`；`training_run_id` 是 UUIDv4；`first16` 是文件完整 SHA-256 的前 16 个小写十六进制字符。逻辑部署名 `yolo11n_safety.pt`、`yolo11n_equipment.pt`、`yolo11n_fault.pt`、`yolo11n_meter.pt` 只能通过 manifest 的 `production_artifact_sha256` 指向一个已通过门槛的不可变文件，不能覆盖旧文件。OpenCV 参数/标定是单独有 SHA-256 的配置 artifact，不得冒充 `meter_locator` 权重。

`models/manifest.yaml` schema 1 每个 artifact 至少记录：

```yaml
schema_version: 1
required_logical_models:
  - yolo11n_safety
  - yolo11n_equipment
  - yolo11n_fault
  - meter_locator
base_weights:
  yolo11n:
    source_url: https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo11n.pt
    filename: yolo11n.pt
    sha256: 64-lowercase-hex
artifacts:
  - logical_model: yolo11n_safety
    module: safety
    training_run_id: uuid-v4
    filename: immutable-artifact-name
    sha256: 64-lowercase-hex
    size_bytes: integer
    git_commit: 40-char-git-sha
    environment_lock_sha256: 64-lowercase-hex
    dataset_manifest_sha256: 64-lowercase-hex
    training_config_sha256: 64-lowercase-hex
    class_names: [ordered-canonical-classes]
    metrics_file: relative-json-path
    metrics_sha256: 64-lowercase-hex
    permitted_use: explicit-license-conclusion
    acceptance_status: passed-or-rejected
production_artifact_sha256:
  yolo11n_safety: 64-lowercase-hex
  yolo11n_equipment: 64-lowercase-hex
  yolo11n_fault: 64-lowercase-hex
  meter_locator: 64-lowercase-hex
deployment_filenames:
  yolo11n_safety: yolo11n_safety.pt
  yolo11n_equipment: yolo11n_equipment.pt
  yolo11n_fault: yolo11n_fault.pt
  meter_locator: yolo11n_meter.pt
meter_reader:
  locator_logical_model: meter_locator
  opencv_config_file: relative-yaml-path
  opencv_config_sha256: 64-lowercase-hex
```

示例只定义结构。实际 manifest 中 `acceptance_status` 只允许 `passed` 或 `rejected`；不存在 `pending` 发布状态。尚未完成评估的训练产物留在 training 目录且不得出现在 production 映射。四个 `required_logical_models` 都必须各有一个独立、已通过的 production SHA-256；`meter_locator` 还必须精确映射到 `yolo11n_meter.pt`，并引用独立 OpenCV 配置摘要。任一缺失都使 manifest 校验失败，且不能改变“仪表只使用 Gazebo 数据”的限制。

## 10. 校验、晋升与回滚

后续阶段必须提供并执行以下唯一校验入口：

```bash
.venv/bin/python scripts/verify_data_and_models.py \
  --dataset-manifest datasets/manifest.yaml \
  --model-manifest models/manifest.yaml \
  --data-root /var/lib/substation/datasets \
  --model-root /var/lib/substation/models \
  --report /var/lib/substation/evidence/data-model-verification.json
```

该脚本在创建前不是 Phase 0 可运行命令。实现必须以非零退出码拒绝以下任一情况：schema/必填字段不符、source `status` 非 accepted、blocked/rejected 的 `block_reason` 语义不符、file_manifest_path 缺失/越界/不存在/摘要不匹配、许可或 revision 缺失、SHA-256 不匹配、原始数据被修改、跨 split 重复、未知/未映射类别、仪表外部数据、合成样本不足、训练环境不可追溯、指标缺失、阈值未达、生产映射指向未通过 artifact 或文件名/摘要不一致。

模型晋升必须是 manifest 原子更新，不复制覆盖旧权重；服务加载时再次计算 SHA-256。回滚只把 production 映射指回历史上已通过且其数据/环境仍可取得的 artifact。任何数据 revision、类别语义、基础权重、训练版本或发布阈值变化，先新增 ADR，并同步根项目计划、[VERSION_MATRIX](VERSION_MATRIX.md)、本文件和 [TEST_ACCEPTANCE](TEST_ACCEPTANCE.md)。
