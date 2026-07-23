# ADR-0004：无头 NVIDIA 驱动与图形包依赖边界

- 状态：Accepted
- 日期：2026-07-23
- 细化：ADR-0001 中“禁止 Xorg”的包级解释；不改变 OGRE2/EGL 纯无头决定

## 背景

目标服务器的 NVIDIA RTX 3060 Ti 正由 Ubuntu 官方驱动 `595.71.05` 正常驱动，`nvidia-smi` 成功。该驱动的 Debian 依赖闭包包含 `xserver-xorg-core`、`xserver-xorg-video-nvidia-595` 和 `x11-common`；系统没有启用/活动显示管理器，没有 Xorg/Wayland 图形会话，也没有运行 Xorg 进程。移除 `xserver-xorg-core` 会同时移除工作正常的 NVIDIA 驱动。

原先把“Xorg 包存在”与“活动图形栈存在”等同，会错误拒绝当前合格主机并破坏驱动。项目真正需要禁止的是桌面、远程/虚拟显示和活动 X Server，而不是官方驱动不可避免的 inert 包依赖。

## 已考虑的方案

1. **分离包依赖与运行态（选择）。** 保留工作正常的 Ubuntu 官方驱动及其 inert 依赖，同时以包、服务、进程、会话和配置五类证据证明没有活动图形栈。
2. **强制删除所有 X 包。** 会卸载当前工作驱动，且不能改善 OGRE2/EGL 无头安全边界。
3. **自动运行 `ubuntu-drivers install`。** 会在无需变更时改写已验证环境，并把驱动事务混入 Phase 1 自动安装，难以审查和回滚。

## 决定

1. 若 Ubuntu 官方 NVIDIA 驱动满足全部条件，则原样保留，不运行 `ubuntu-drivers install`，不修改 NVIDIA 包：
   - `nvidia-smi` 成功；
   - 驱动版本 `>= 560.35.05`；
   - 无 `DISPLAY` 的 DRM/EGL 和 Gazebo OGRE2 探针成功。
2. 允许仅因上述官方驱动依赖而安装、且没有启动图形会话的 `xserver-xorg-core`、相同驱动分支的 `xserver-xorg-video-nvidia-*`、`x11-common` 及其必要库。清单必须记录精确包版本和反向依赖。
3. 以下仍为硬禁止：Ubuntu/衍生桌面元包、GNOME/KDE 桌面会话、显示管理器、NoMachine、其他远程桌面、Xvfb、VirtualGL、活动 `Xorg`/`Xwayland`/Wayland compositor、启用的图形 target，以及项目创建或修改的 X Server 配置。
4. 若驱动缺失、低于最低版本、来源不是批准的 Ubuntu 官方包或 EGL 探针失败，Phase 1 以 `DRIVER_TRANSACTION_REQUIRED` 停止。驱动变更必须作为单独、显式、可回滚且再次审查的 headless 事务；环境计划不得自动安装/升级驱动。
5. 禁止把安装桌面、启动显示管理器、设置 `DISPLAY`、Xvfb 或 VirtualGL 作为 EGL 故障修复路径。

## 验收证据

- `nvidia-smi` 的 GPU、驱动和显存输出；
- NVIDIA 包的 `dpkg-query` 精确版本及 `apt-cache rdepends`；
- display manager、`graphical.target`、登录会话和 `Xorg|Xwayland|weston|gnome-shell|kwin_wayland` 进程检查；
- 项目未新增 Xorg 配置的 before/after 清单；
- `env -u DISPLAY eglinfo --display drm` 与 Gazebo 64×48 RGB payload 探针。

任一禁止服务/进程/会话/配置存在，或 inert 包无法证明由工作驱动需要，均失败。

## 后果

- 当前 `595.71.05` 驱动可以在保持纯无头运行边界的同时继续使用。
- 禁止项扫描必须检查“活动能力”，不能仅用宽泛包名正则拒绝 NVIDIA 依赖。
- 驱动升级不再是自动环境安装的一部分；缺失/不合格时明确阻塞并单独评审。

## 可以被取代的条件

只有目标硬件、Ubuntu 官方打包、最低 CUDA 兼容要求或无头渲染路径发生变化，并且新的 ADR 同步项目计划、环境计划、版本矩阵、部署和验收后，才可取代本决定。为了清理包列表而破坏工作驱动，或为了调试启用图形会话，均不足以取代。
