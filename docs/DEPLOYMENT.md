# 部署与运行

## 1. 目标拓扑与身份

单台 Ubuntu 24.04 服务器集中运行 ROS 2 Jazzy、Gazebo Harmonic（release series `gz-sim 8.x`，实际 Debian revisions 由环境清单内容锁定）、GPU 推理、三份 SQLite、FastAPI、Next.js、Nginx 和维护诊断所需的 Foxglove Bridge。普通 Windows 操作员只访问 `http://ros-server/`，不安装 ROS、Gazebo、Node.js 或项目源码。

开发检出可以位于授权操作员账户，例如当前 `/home/jackeyliu37/substation-inspection-digital-twin`；开发账户不等于运行服务账户。部署只从干净、已验证的 Git commit 构建不可变 release 到 `/opt/substation/releases/<git-commit>`，`/opt/substation/current` 原子指向当前 release，systemd 服务统一以无登录运行账户 `substation` 执行。可变数据不得写入开发检出或 release。

Gazebo 使用 OGRE2/EGL 纯无头渲染，标准命令等价于：

```bash
env -u DISPLAY ROS_LOCALHOST_ONLY=1 gz sim -s -r --headless-rendering substation_world.sdf
```

禁止桌面元包、显示管理器、远程桌面、NoMachine、Xvfb、VirtualGL、活动 Xorg/Wayland 图形会话或配置 X Server。Ubuntu 官方 NVIDIA 驱动必需但未激活的 X 包依赖按 [ADR-0004](adr/0004-nvidia-headless-packaging.md) 验收。

## 2. 目录、数据库与文件所有权

| 路径 | 内容 | 可变性与唯一写入者 |
|---|---|---|
| 授权操作员的开发检出 | Git 源码、受控脚本、配置、manifest 和锁文件 | 操作员维护；不作为 systemd 运行树 |
| `/opt/substation/releases/<git-commit>` | 已验证 ROS/Gateway/前端产物及 `release-manifest.json` | root 部署、不可原地修改；服务只读 |
| `/opt/substation/current` | 指向当前 release 的符号链接 | 部署程序以同目录 no-replace/原子 rename 切换 |
| `/opt/substation/config` | systemd 环境、site network 值、Nginx include 和非密配置 | root 维护；敏感值不提交 Git |
| `/var/lib/substation/sqlite/mission.sqlite3` | RunContext、mission、task、mode、latch revisions | `substation_mission` 唯一写入 |
| `/var/lib/substation/sqlite/gateway.sqlite3` | command、幂等键、Web outbox、Gateway Web revisions | `substation_web_gateway` 唯一写入 |
| `/var/lib/substation/sqlite/evidence.sqlite3` | 时间映射、证据、报告/诊断索引与 artifact manifest | `substation_reporting/evidence_store` 唯一写入 |
| `/var/lib/substation/evidence/objects` | 内容寻址证据与校验值 | evidence store 唯一最终写入 |
| `/var/lib/substation/reports` | 已发布 HTML/PDF/evidence ZIP | report_generator 只写 `.work`；evidence store 最终发布 |
| `/var/lib/substation/diagnostics` | 已发布诊断包和 manifest | evidence store 最终发布 |
| `/var/lib/substation/rosbag2` | run-scoped rosbag2 | evidence store 管理的 recorder |
| `/var/lib/substation/models` | 基础/生产权重、manifest 与 SHA-256 | manifest 管理；备份必须包含权重本体 |
| `/var/log/substation` | 服务日志和轮转日志 | 对应服务写入，logrotate 管理 |

Gateway 不得打开 `mission.sqlite3` 或 `evidence.sqlite3` 的写连接；report_generator 不得直接写最终报告目录或 `evidence.sqlite3`。跨进程持久化只经 `docs/INTERFACES.md` 的 ROS Service。

## 3. 网络、名称解析与 Foxglove

所有 ROS/systemd 单元固定环境 `ROS_LOCALHOST_ONLY=1`。产品监听关系为：

```text
Windows browser -> ros-server:80 (Nginx)
                         ├─ /               -> 127.0.0.1:3000 Next.js
                         ├─ /api/、/ws/      -> 127.0.0.1:8000 Gateway
                         └─ /foxglove/       -> 127.0.0.1:8765 Bridge（维护时）
```

| 服务 | 绑定 / 暴露 | 强制边界 |
|---|---|---|
| ROS/Gazebo/Nav2/reporting | localhost DDS | LAN 浏览器不可发现或加入 DDS |
| Gateway | `127.0.0.1:8000` | 不能绑定 `0.0.0.0` 或 LAN 地址 |
| Next.js | `127.0.0.1:3000` | 不能绑定 `0.0.0.0` 或 LAN 地址 |
| Nginx | LAN TCP/80，Host `ros-server` | 唯一产品监听者；代理 `/`、`/api/`、`/ws/` |
| Foxglove Bridge | `127.0.0.1:8765` | systemd 默认 disabled/inactive；不能从 LAN 直连 |

站点必须在 `/opt/substation/config/network.env` 写入唯一、真实的静态/保留 IPv4 键 `ROS_SERVER_IPV4`；值必须匹配严格 IPv4 语法且不能是 loopback、link-local 或 `0.0.0.0`。该地址由静态 Netplan 或 DHCP reservation 保持不变。LAN DNS 应把 `ros-server` 解析到该值；没有 DNS 时，Windows `C:\Windows\System32\drivers\etc\hosts` 必须用同一实际值登记 `ros-server`。验收至少执行：

```bash
set -euo pipefail
set -a
source /opt/substation/config/network.env
set +a
python3 -c 'import ipaddress,os; value=ipaddress.ip_address(os.environ["ROS_SERVER_IPV4"]); assert value.version == 4 and not value.is_loopback and not value.is_link_local and not value.is_unspecified'
test "$(getent ahostsv4 ros-server | awk 'NR==1{print $1}')" = "$ROS_SERVER_IPV4"
curl --fail --silent --show-error --resolve "ros-server:80:$ROS_SERVER_IPV4" http://ros-server/healthz
```

Windows 验收保存 `Resolve-DnsName ros-server`、`Test-NetConnection ros-server -Port 80` 和浏览器网络记录；解析地址必须逐字等于 `network.env` 中的值。

Foxglove 的 systemd 配置固定 `address=127.0.0.1`、`port=8765`。只读 topic allowlist 为 `/tf`、`/tf_static`、`/map`、`/map_updates`、`/plan`、`/local_plan`、`/camera/image_raw`、`/perception/annotated_image`、`/diagnostics`、`/system/run_context`、`/mission/inspection_tasks`、`/risk/assets` 和 `/risk/alerts`；client topic publish、Service、Action goal 和参数写 allowlist 均为空/拒绝全部。维护者显式启用 Bridge 与 Nginx `/foxglove/` include，完成后立即禁用。单操作员受信 LAN 本期使用 HTTP、无应用认证/TLS；禁止公网路由。公网、多操作员或不可信网络必须先有新 ADR、认证、TLS、授权和审计。

负向验收必须证明：LAN 直连 `8765` 失败；Foxglove 发布 Topic、调用 Service、发送 Action goal 和改参数均失败；Bridge inactive 时产品八页、Gateway、任务和证据链仍可用。

## 4. 启动、就绪和安全停止

启动顺序：

1. 验证 release manifest、目录权限、三个 SQLite schema、NVIDIA/EGL、`ROS_LOCALHOST_ONLY=1` 和 `network.env`。
2. 启动 `substation-gazebo.service`；确认无 `DISPLAY` 且相机/LiDAR/`/clock` 就绪。
3. 启动 `substation-core.service`；其内部 lifecycle 顺序为 reporting/evidence store、数字孪生、风险、感知、Nav2、任务管理器；全部 readiness 通过后才接受 mission。
4. 启动 `substation-web-gateway.service`，确认 `127.0.0.1:8000/readyz` 和三个数据库的领域 Service 可用。
5. 启动 `substation-web-frontend.service`，确认只在 `127.0.0.1:3000` 响应。
6. 启动/reload `nginx.service`，从 LAN 验证 `http://ros-server/`、`/api/` 和 `/ws/`。
7. 仅维护时临时启动 `substation-foxglove-bridge.service` 和只读 Nginx include。

停止、升级、回滚或维护时，不能先关掉 Gateway。必须从已验证 release 执行唯一安全停止入口：

```bash
set -euo pipefail
maintenance_id="$(date -u +%Y%m%dT%H%M%SZ)"
maintenance_evidence="/var/lib/substation/evidence/maintenance/$maintenance_id"
sudo install -d -m 0750 -o substation -g substation "$maintenance_evidence"
sudo -u substation env -u DISPLAY ROS_LOCALHOST_ONLY=1 \
  /opt/substation/current/bin/substation-safe-stop \
  --reason upgrade --timeout-s 10 --evidence-dir "$maintenance_evidence"
jq -e '.emergency_stop_latched == true and .nav2_active_goals == 0 and .cmd_vel_zero == true' \
  "$maintenance_evidence/safe-stop-result.json"
sudo systemctl stop substation-core.service substation-gazebo.service
sudo systemctl stop substation-web-gateway.service substation-web-frontend.service nginx.service
```

`substation-safe-stop` 必须先锁存急停，再取消所有 Nav2 goal，等待任务管理器清除 goal handle，确认最终 `/cmd_vel` 连续 0.5 s 为零并把逐步证据 fsync 后才成功。失败时不得继续普通升级；保持 Gateway/Nginx 可用并按危险状态处理。`substation-core.service` 的 stop hook 必须依次停 mission/Nav2、simulation bridge/perception、digital twin/risk/reporting；紧急停止状态保留在 `mission.sqlite3`，重启不能隐式解除。

## 5. 备份、升级与回滚

### 5.1 一致性备份命令

安全停止通过后执行：

```bash
set -euo pipefail
backup_id="$(date -u +%Y%m%dT%H%M%SZ)"
backup_root="/var/backups/substation/$backup_id"
sudo install -d -m 0700 "$backup_root/sqlite" "$backup_root/files"
for database in mission gateway evidence; do
  sudo sqlite3 "/var/lib/substation/sqlite/$database.sqlite3" \
    ".backup '$backup_root/sqlite/$database.sqlite3'"
  sudo sqlite3 "$backup_root/sqlite/$database.sqlite3" 'PRAGMA integrity_check;' \
    | grep -Fx ok
done
sudo rsync -aHAX --numeric-ids /var/lib/substation/evidence/ "$backup_root/files/evidence/"
sudo rsync -aHAX --numeric-ids /var/lib/substation/reports/ "$backup_root/files/reports/"
sudo rsync -aHAX --numeric-ids /var/lib/substation/diagnostics/ "$backup_root/files/diagnostics/"
sudo rsync -aHAX --numeric-ids /var/lib/substation/rosbag2/ "$backup_root/files/rosbag2/"
sudo rsync -aHAX --numeric-ids /var/lib/substation/models/ "$backup_root/files/models/"
sudo rsync -aHAX --numeric-ids /opt/substation/config/ "$backup_root/files/config/"
readlink -f /opt/substation/current | sudo tee "$backup_root/current-release.txt" >/dev/null
sudo cp -a /opt/substation/current/release-manifest.json "$backup_root/release-manifest.json"
sudo find "$backup_root" -type f ! -name SHA256SUMS -printf '%P\0' \
  | sudo sort -z \
  | while IFS= read -r -d '' path; do
      (cd "$backup_root" && sudo sha256sum -- "$path")
    done | sudo tee "$backup_root/SHA256SUMS" >/dev/null
(cd "$backup_root" && sudo sha256sum -c SHA256SUMS)
```

备份必须包含模型权重本体、models manifest、三个 SQLite、证据/报告/诊断/rosbag2、配置、当前 release 指针和 release manifest；只备份校验值不够。

### 5.2 候选构建与原子切换

```bash
set -euo pipefail
target_commit="$(git rev-parse --verify HEAD^{commit})"
candidate="/opt/substation/releases/$target_commit"
test -d "$candidate"
test "$(jq -r .git_commit "$candidate/release-manifest.json")" = "$target_commit"
(cd "$candidate" && sha256sum -c release-SHA256SUMS)
current_new="/opt/substation/.current-$target_commit"
test ! -e "$current_new"
sudo ln -s "$candidate" "$current_new"
sudo mv -T "$current_new" /opt/substation/current
```

候选在切换前完成构建、schema dry-run、配置检查和 release-SHA256SUMS。切换后按第 4 节启动并运行恢复检查；任何失败立即执行 5.3。只有恢复检查通过后才可标记部署成功，且必须保留上一 release 与同批备份。

### 5.3 精确回滚

```bash
set -euo pipefail
backup_root="$(find /var/backups/substation -mindepth 1 -maxdepth 1 -type d -printf '%p\n' | LC_ALL=C sort | tail -n1)"
test -n "$backup_root"
(cd "$backup_root" && sudo sha256sum -c SHA256SUMS)
previous_release="$(sudo sed -n '1p' "$backup_root/current-release.txt")"
case "$previous_release" in /opt/substation/releases/[0-9a-f][0-9a-f]*) ;; *) exit 1 ;; esac
test -d "$previous_release"
rollback_link="/opt/substation/.current-rollback-$(basename "$previous_release")"
test ! -e "$rollback_link"
sudo ln -s "$previous_release" "$rollback_link"
sudo mv -T "$rollback_link" /opt/substation/current
for database in mission gateway evidence; do
  sudo install -m 0640 -o substation -g substation \
    "$backup_root/sqlite/$database.sqlite3" \
    "/var/lib/substation/sqlite/$database.sqlite3"
done
for tree in evidence reports diagnostics rosbag2 models; do
  sudo rsync -aHAX --numeric-ids --delete "$backup_root/files/$tree/" "/var/lib/substation/$tree/"
done
sudo rsync -aHAX --numeric-ids --delete "$backup_root/files/config/" /opt/substation/config/
```

只有当候选 schema 与旧 release 不兼容或候选已写入状态时才恢复同批 SQLite/文件；不得混用不同备份批次。回滚后机器人仍保持锁存急停和零速度，按第 4 节启动，再执行第 6 节检查；任何检查失败时保持 Nginx 不对外宣告 ready。

## 6. 恢复与边界验收

至少保存以下逐字输出：

```bash
set -euo pipefail
systemctl is-active substation-gazebo.service substation-core.service \
  substation-web-gateway.service substation-web-frontend.service nginx.service
test "$(systemctl is-enabled substation-foxglove-bridge.service 2>/dev/null || true)" = disabled
ss -H -ltnp
test -z "$(ss -H -ltn 'sport = :8000' | awk '$4 !~ /^127\.0\.0\.1:8000$/')"
test -z "$(ss -H -ltn 'sport = :3000' | awk '$4 !~ /^127\.0\.0\.1:3000$/')"
test -z "$(ss -H -ltn 'sport = :8765')"
curl --fail http://127.0.0.1:8000/readyz
curl --fail http://ros-server/healthz
env -u DISPLAY ROS_LOCALHOST_ONLY=1 /opt/substation/current/bin/verify-headless-sensors
/opt/substation/current/bin/verify-persistence-ownership
/opt/substation/current/bin/verify-network-boundaries --host ros-server
```

检查必须确认：Gazebo 相机/LiDAR 有数据；ROS、reporting、Gateway readiness 一致；三份数据库只有各自进程持有写锁；`ros-server` 解析正确；Gateway/前端回环、Nginx 唯一 LAN 产品监听；Foxglove 默认关闭；浏览器从 REST 快照续接 WebSocket；紧停锁存、命令确认、报告/证据下载与 SHA-256 正常。

EGL 失败时保留当前工作驱动并检查 NVIDIA/EGL/OGRE2 日志；不得自动运行 `ubuntu-drivers install` 或启用图形栈。相关决定见 [ADR-0001](adr/0001-headless-gazebo.md)、[ADR-0002](adr/0002-server-web-deployment.md)、[ADR-0003](adr/0003-multimodel-perception.md) 和 [ADR-0004](adr/0004-nvidia-headless-packaging.md)。
