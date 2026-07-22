# 版本与资源锁定矩阵

## 1. 适用范围与锁定规则

本文是操作系统、ROS/Gazebo、GPU、Python/AI、Web、后端、数据库、反向代理、公开数据和模型权重的唯一版本基线。基线日期为 2026-07-22。项目只使用 Ubuntu 24.04、ROS 2 Jazzy 和 Gazebo Harmonic；不得引入 ROS 1、Gazebo Classic 或其他 ROS 发行版，也不得用桌面或虚拟显示栈替代 OGRE2/EGL 纯无头渲染。

锁定级别含义如下：

- **发行版锁定**：固定发行版和官方仓库；安装时解析出的全部 Debian 包精确版本必须写入 `artifacts/environment/dpkg-packages.tsv`，之后按该清单重建。
- **系列锁定**：固定 LTS/主系列，同时把实际安装的完整版本写入环境清单；超出系列或改变已记录完整版本均属于升级。
- **精确锁定**：锁文件必须使用完整版本且禁止范围运算符、浮动标签和未固定 Git 分支。
- **内容锁定**：外部数据、权重和生成物以不可变 revision 加 SHA-256 锁定；没有摘要的文件不得进入训练、推理或验收。

Phase 0 只建立合同，不安装依赖、下载数据/权重或启动服务。下列环境和资源命令在相应文件由后续阶段创建后才可执行；当前是否可运行以 [TEST_ACCEPTANCE](TEST_ACCEPTANCE.md) 的阶段状态为准。

## 2. 主机、ROS、Gazebo 与导航

| 组件 | 锁定基线 | 锁定级别 | 官方获取源 | 后续验证命令 |
|---|---|---|---|---|
| Ubuntu | Ubuntu 24.04 LTS，Noble 官方更新 | 发行版锁定 | <https://releases.ubuntu.com/noble/> | `source /etc/os-release && test "$ID" = ubuntu && test "$VERSION_ID" = 24.04 && printf '%s\n' "$PRETTY_NAME"` |
| Linux 与基础 Debian 包 | Ubuntu 24.04 当前已批准环境清单中的精确解析版本 | 内容锁定 | Ubuntu Noble `main`、`universe`、`restricted`、`multiverse`；不得混入其他 Ubuntu 发行版 | `dpkg-query -W -f='${Package}\t${Version}\n' \| LC_ALL=C sort > artifacts/environment/dpkg-packages.tsv`，再由 `sha256sum -c artifacts/environment/SHA256SUMS` 校验 |
| NVIDIA 驱动 | Ubuntu 推荐驱动；验收版本不得低于 `560.35.05` | 最低版本加内容锁定 | `ubuntu-drivers install`；NVIDIA 官方兼容说明 <https://docs.nvidia.com/deploy/cuda-compatibility/minor-version-compatibility.html> | `nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader`；`dpkg --compare-versions "$(nvidia-smi --query-gpu=driver_version --format=csv,noheader \| head -n1)" ge 560.35.05` |
| ROS | ROS 2 Jazzy Jalisco LTS；`ros-jazzy-ros-base`，不安装桌面元包 | 发行版锁定 | ROS 2 Jazzy Ubuntu Debian 仓库：<https://docs.ros.org/en/jazzy/Installation/Ubuntu-Install-Debs.html> | `source /opt/ros/jazzy/setup.bash && test "$ROS_DISTRO" = jazzy`；`dpkg-query -W 'ros-jazzy-*'` |
| Gazebo | Gazebo Harmonic LTS，`gz-sim 8.x`，OGRE2/EGL headless | 系列锁定 | ROS/Gazebo 官方配对源：<https://gazebosim.org/docs/harmonic/ros_installation/>；headless：<https://gazebosim.org/api/sim/8/headless_rendering.html> | `gz sim --versions`；`dpkg-query -W 'gz-sim8*' 'libgz-sim8*'`；运行验收必须使用 `env -u DISPLAY gz sim -s -r --headless-rendering substation_world.sdf` 或项目等价 launch |
| ROS–Gazebo | `ros_gz 1.0.23-1` | 精确锁定 | ROS Jazzy 软件源中的 `ros-jazzy-ros-gz` | `dpkg-query -W -f='${Package}\t${Version}\n' ros-jazzy-ros-gz \| grep -E $'^ros-jazzy-ros-gz\\t1\\.0\\.23-1([^0-9].*)?$'`；完整 Ubuntu 包 revision 还必须逐字匹配批准的环境清单 |
| Navigation2 | `1.3.12-1` | 精确锁定 | `ros-jazzy-navigation2`、`ros-jazzy-nav2-bringup` | `dpkg-query -W -f='${Package}\t${Version}\n' ros-jazzy-navigation2 ros-jazzy-nav2-bringup`，版本必须与批准的 Debian 环境清单一致且上游版本为 `1.3.12-1` |
| SLAM Toolbox | `2.8.5-1` | 精确锁定 | ROS Jazzy 软件源中的 `ros-jazzy-slam-toolbox` | `dpkg-query -W -f='${Version}\n' ros-jazzy-slam-toolbox`，上游版本必须为 `2.8.5-1` |
| TurtleBot3 | 核心 `2.3.6-1`；仿真 `2.3.7-1` | 精确锁定 | ROBOTIS TurtleBot3 Jazzy 文档：<https://emanual.robotis.com/docs/en/platform/turtlebot3/quick-start/> 和 ROS Jazzy 软件源 | `dpkg-query -W -f='${Package}\t${Version}\n' 'ros-jazzy-turtlebot3*'`，核心与仿真上游版本分别匹配 `2.3.6-1`、`2.3.7-1` |
| Python | Python `3.12`，Ubuntu 24.04 系统 Python | 次版本锁定加内容锁定 | Ubuntu Noble 软件源 | `python3 -c 'import sys; assert sys.version_info[:2] == (3, 12); print(sys.version)'`；精确 patch 版本进入 Debian 环境清单 |

Debian 包显示的完整版本可能包含 Ubuntu 构建后缀。项目计划固定的是表中上游版本；唯一可复现依据仍是审核并提交校验值的 `dpkg-packages.tsv`。任何重新解析出的不同完整版本不得静默替换旧清单。

## 3. Python、AI 与 Gateway

训练/推理环境固定为仓库根目录 `.venv`，使用 `python3 -m venv --system-site-packages .venv`；Gateway 固定为独立 `.venv-web`，同样通过 `--system-site-packages` 读取 ROS 2 的 `rclpy`。禁止全局 `sudo pip`、Conda CUDA、Ubuntu `nvidia-cuda-toolkit` 与 pip CUDA 混装。

| 组件 | 精确版本 / 资源 | 获取源 | 锁文件与后续验证 |
|---|---|---|---|
| PyTorch | `torch==2.12.1`，CUDA 12.6 wheel | `https://download.pytorch.org/whl/cu126`；PyTorch 官方历史版本页 <https://pytorch.org/get-started/previous-versions/> | `requirements.lock`；`.venv/bin/python -c 'import torch; assert torch.__version__.split("+")[0] == "2.12.1"; assert torch.cuda.is_available(); print(torch.__version__, torch.version.cuda)'` |
| TorchVision | `torchvision==0.27.1` | PyTorch CUDA 12.6 wheel 源 | `requirements.lock`；`.venv/bin/python -c 'import torchvision; assert torchvision.__version__.split("+")[0] == "0.27.1"; print(torchvision.__version__)'` |
| Ultralytics | `ultralytics==8.4.104` | PyPI：<https://pypi.org/project/ultralytics/> | `requirements.lock`；`.venv/bin/python -c 'import ultralytics; assert ultralytics.__version__ == "8.4.104"'` |
| NumPy | `numpy==1.26.4` | PyPI | `requirements.lock`；`.venv/bin/python -c 'import numpy; assert numpy.__version__ == "1.26.4"'` |
| OpenCV | `opencv-python==4.11.0.86` | PyPI | `requirements.lock`；`.venv/bin/python -c 'import cv2; assert cv2.__version__ == "4.11.0"'` |
| FastAPI | `fastapi==0.139.2` | PyPI：<https://fastapi.tiangolo.com/> | `requirements-web.lock`；`.venv-web/bin/python -c 'import fastapi; assert fastapi.__version__ == "0.139.2"'` |
| Uvicorn | `uvicorn==0.51.0` | PyPI | `requirements-web.lock`；`.venv-web/bin/python -c 'import uvicorn; assert uvicorn.__version__ == "0.51.0"'` |
| Pydantic | `pydantic==2.13.4` | PyPI | `requirements-web.lock`；`.venv-web/bin/python -c 'import pydantic; assert pydantic.__version__ == "2.13.4"'` |
| WebSockets | `websockets==16.1.1` | PyPI | `requirements-web.lock`；`.venv-web/bin/python -c 'import websockets; assert websockets.__version__ == "16.1.1"'` |

两个 lock 文件必须由带 SHA-256 的完全解析依赖组成；直接依赖和传递依赖都不得使用 `>=`、`~=`、通配符、Git 分支或未带 digest 的本地 wheel。环境验证保存 `.venv/bin/python -m pip freeze --all`、`.venv-web/bin/python -m pip freeze --all` 和对应 SHA-256。

## 4. Node.js 与前端

| 组件 | 精确版本 | 获取源 | 锁文件与后续验证 |
|---|---:|---|---|
| Node.js | `24.18.0` LTS（Krypton） | <https://nodejs.org/en/download/> | `node --version \| grep -Fx v24.18.0`；安装包摘要进入环境清单 |
| npm | 精确版本由 `web/frontend/package.json` 顶层 `packageManager` 字段唯一拥有，值必须匹配 `^npm@[0-9]+\.[0-9]+\.[0-9]+$`，不允许 `latest`、范围或前缀 `v` | Node.js 官方发行包自带 npm；Phase 1 把实际版本写入该字段后形成内容锁定 | `npm_spec="$(node -p 'require("./web/frontend/package.json").packageManager')" && [[ "$npm_spec" =~ ^npm@[0-9]+\.[0-9]+\.[0-9]+$ ]] && test "$(npm --prefix web/frontend --version)" = "${npm_spec#npm@}"`；`package-lock.json` 不拥有 package manager 版本 |
| Next.js | `16.2.11` | npm registry；<https://nextjs.org/docs> | `web/frontend/package-lock.json`；`npm --prefix web/frontend ls next --depth=0` |
| React / React DOM | `19.2.8` / `19.2.8` | npm registry；<https://react.dev/> | `package-lock.json`；`npm --prefix web/frontend ls react react-dom --depth=0` |
| TypeScript | `6.0.3` | npm registry；<https://www.typescriptlang.org/docs/> | `package-lock.json`；`npm --prefix web/frontend ls typescript --depth=0` |
| Tailwind CSS | `4.3.3` | npm registry；<https://tailwindcss.com/docs> | `package-lock.json`；`npm --prefix web/frontend ls tailwindcss --depth=0` |
| Three.js | `0.185.1` | npm registry；<https://threejs.org/docs/> | `package-lock.json`；`npm --prefix web/frontend ls three --depth=0` |
| React Three Fiber | `9.6.1` | npm registry；<https://r3f.docs.pmnd.rs/> | `package-lock.json`；`npm --prefix web/frontend ls @react-three/fiber --depth=0` |
| Apache ECharts | `6.1.0` | npm registry；<https://echarts.apache.org/en/index.html> | `package-lock.json`；`npm --prefix web/frontend ls echarts --depth=0` |
| Playwright | `@playwright/test@1.61.1` | npm registry；<https://playwright.dev/docs/intro> | `package-lock.json`；`npm --prefix web/frontend exec playwright -- --version \| grep -Fx 'Version 1.61.1'` |

前端只允许在 Ubuntu 服务器从仓库根目录执行 `npm --prefix web/frontend ci` 和 `npm --prefix web/frontend run build`。`web/frontend/package.json` 中上述直接依赖必须写精确版本，`web/frontend/package-lock.json` 使用 lockfile v3 并提交 Git；Windows 操作员端不安装 Node.js 或依赖。

## 5. 数据库、代理与运行服务

| 组件 | 基线 | 锁定级别与来源 | 后续验证命令 |
|---|---|---|---|
| SQLite | SQLite 3，Ubuntu 24.04 软件源解析的精确版本 | 发行版锁定加 Debian 环境清单；不引入独立数据库服务 | `sqlite3 --version`；`dpkg-query -W -f='${Version}\n' sqlite3 libsqlite3-0` |
| Nginx | Ubuntu 24.04 软件源解析的精确版本 | 发行版锁定加 Debian 环境清单；只由 Nginx 对 LAN 暴露 `http://ros-server/` | `nginx -v`；`dpkg-query -W -f='${Version}\n' nginx`；`nginx -t` |
| FastAPI Gateway | 上表 Python 栈；Uvicorn 只绑定 `127.0.0.1:8000` | `requirements-web.lock` 和 Git commit | `ss -ltnp` 与 Gateway 合同测试共同验证，不接受 LAN 直绑 |
| Next.js 服务 | 上表 Node 栈；只绑定 `127.0.0.1:3000` | `package-lock.json` 和 Git commit | `ss -ltnp` 与 Web 验收共同验证，不接受 LAN 直绑 |
| Foxglove Bridge | ROS Jazzy 软件源中与批准 Debian 清单一致的版本 | 发行版锁定；独立只读开发诊断路径 | `dpkg-query -W 'ros-jazzy-foxglove-bridge'`；运行测试必须证明浏览器不直连 DDS，Bridge 不能发布 Topic、调用 Service 或发送 Action goal |

## 6. 数据集与模型资源

外部资源的详细治理见 [DATA_AND_MODELS](DATA_AND_MODELS.md)。本表只定义版本身份和获取源；实际文件必须由 manifest 记录 SHA-256，且大文件不提交 Git。

| 资源 | 固定身份 | 获取源 | 锁定与验证 |
|---|---|---|---|
| 15-class Substation Equipment | revision `c63ed3c7f5ea33ac8e9024c467a70a62b849b2ad` | <https://huggingface.co/datasets/AndrzejDD/15-class-Substation-Equipment> | 内容锁定；`datasets/manifest.yaml` 同时记录 revision、每文件 SHA-256、7,076 张总数和原始 split |
| Hard Hat Workers | Roboflow public dataset version `10` | <https://public.roboflow.com/object-detection/hard-hat-workers/10> | 版本锁定；记录实际 YOLO 导出 URL、导出时间、archive SHA-256 和每文件 SHA-256 |
| D-Fire | commit `4bf9c31b18fadcd44d5f0b6d66f82bc56fa5e328` | <https://github.com/gaia-solutions-on-demand/DFireDataset> | 内容锁定；Git checkout 必须处于该 commit，文件清单摘要进入 dataset manifest |
| InsPLAD | 使用时解析并固定一个完整 40 位 commit；许可固定为 CC BY-NC 3.0 | <https://github.com/andreluizbvs/InsPLAD> | 项目计划未指定 commit，因此未在 manifest 写入 commit 和文件 SHA-256 前状态为“禁止训练/验收”，不得跟随默认分支 |
| Gazebo 合成数据 | 生成脚本 Git commit、场景配置 SHA-256、Gazebo/模型版本和 seed 的组合身份 | 项目自有 `substation_gazebo` 生成链 | 内容锁定；原图、标签与 split 文件逐项哈希，仪表数据只能来自该来源 |
| YOLO11n COCO 基础权重 | Ultralytics YOLO11n，文件名 `yolo11n.pt`，release `v8.4.0` | `https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo11n.pt` | 下载后把实际 SHA-256 写入 `models/manifest.yaml`；摘要缺失或不匹配即拒绝加载，不使用 `yolov11n.pt` |
| 项目模型 | `yolo11n_safety.pt`、`yolo11n_equipment.pt`、`yolo11n_fault.pt`、独立仪表定位权重 `yolo11n_meter.pt`，以及其下游 OpenCV 仪表读数配置/产物 | 仅由已批准 manifest 数据和固定训练配置生成 | 四个模型 artifact 分别记录内容 SHA-256、训练 Git commit、数据 manifest SHA-256、指标和用途；`yolo11n_meter.pt` 只定位表盘，OpenCV 独立完成透视/刻度/指针读数；生产别名只能指向 manifest 中已通过验收的 artifact |

## 7. 升级、回滚与失败规则

1. 任何表中基线、已解析 Debian/Python/npm 版本、数据 revision、模型基础权重或内容 SHA-256 的变化，都必须先新增 ADR；不得覆盖历史 ADR。
2. 同一变更必须同步更新根项目计划、本文件、`requirements.lock`、`requirements-web.lock`、`package-lock.json`、数据/模型 manifest、环境清单和 [TEST_ACCEPTANCE](TEST_ACCEPTANCE.md) 中受影响基线。
3. 候选版本必须在独立 release 中完成环境、构建、单元、集成、场景、模型、Gateway、Web、性能和最终验收；任何失败都禁止替换 `/opt/substation/current`。
4. 回滚必须使用已验证 Git commit、对应锁文件、`artifacts/environment` 清单、`/opt/substation/releases` 运行树以及相同批次的 `/var/lib/substation` 备份，不得从浏览器缓存、未记录 wheel、浮动 Git 分支或临时训练目录恢复。
5. 版本命令无法执行、输出版本不匹配、来源不在表内、清单缺失或 SHA-256 不一致，均为硬失败；不得以“兼容版本”或本机可运行作为放行理由。
