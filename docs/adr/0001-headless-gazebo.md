# ADR-0001：Gazebo 使用 OGRE2/EGL 纯无头渲染

- 状态：Accepted
- 日期：2026-07-22

## 背景

系统在 Ubuntu 24.04 服务器上运行 Gazebo Harmonic `gz-sim 8.x`（精确锁定见 `docs/VERSION_MATRIX.md`），用相机、深度/激光和物理仿真驱动变电站巡检闭环。服务器没有本地桌面，普通操作员在 Windows 浏览器中使用 Web 平台；Gazebo GUI 不是日常可视化通道。仍须在没有 `DISPLAY` 的环境中产生可验收的渲染传感器数据。

## 已考虑的方案

1. **OGRE2/EGL 无头渲染（选择）。** 使用 Gazebo Harmonic `gz-sim 8.x` 的服务器渲染路径，例如 `gz sim -s -r --headless-rendering substation_world.sdf`，项目 launch 提供等价的 `headless:=true`。
2. **安装 Ubuntu Desktop 或使用 Gazebo GUI。** 需要服务器图形桌面和显示会话，与无桌面服务器及浏览器日常入口冲突。
3. **Xorg、Xvfb、VirtualGL 或 NoMachine 形成虚拟/远程显示栈。** 这些组件只是规避无头初始化问题的替代路径，均被项目约束禁止。

## 决定

Gazebo 固定采用 Harmonic 的 OGRE2/EGL 纯无头模式。服务器不安装 Ubuntu Desktop、Xorg、NoMachine、Xvfb 或 VirtualGL；无论开发还是验收，都以无 `DISPLAY` 的 Gazebo 传感器、日志、Topic 统计、rosbag2 和浏览器截图验证。Three.js Web 数字孪生和 Foxglove Web 分别承担日常展示和开发诊断，均不传输远程桌面画面。

## 后果

- 减少服务器 GUI、远程桌面和显示栈的依赖，保持单一服务器/浏览器运行模型。
- EGL 初始化、NVIDIA 驱动和 OGRE2 可用性成为启动前和恢复时的显式检查项；失败时暂停仿真并保存日志。
- 相机/渲染验证必须证明无头模式下确有数据，不能以“进程存在”作为证据。
- 不得通过安装被禁止的桌面或虚拟显示替代方案修复故障。

## 可以被取代的条件

只有在以下条件全部满足时，才可新建一个 Superseding ADR 取代本决定：项目计划和 AGENTS 约束已先行更新；目标 Gazebo/硬件组合不再支持经官方验证的 OGRE2/EGL 无头渲染，或项目范围明确要求受控的本地物理显示；替代方案在无头传感器、性能、安全边界和验收证据上经过完整验证；版本矩阵、部署手册、锁文件和测试基线同步修改。单次 EGL 故障、开发便利或远程查看需求不足以构成取代条件。
