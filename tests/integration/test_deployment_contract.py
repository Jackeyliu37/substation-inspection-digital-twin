from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    target = ROOT / path
    assert target.is_file(), f"missing deployment artifact: {target}"
    return target.read_text(encoding="utf-8")


def test_product_services_bind_only_to_loopback_and_keep_ros_local() -> None:
    gateway = read("deploy/systemd/substation-web-gateway.service")
    frontend = read("deploy/systemd/substation-web-frontend.service")

    for unit in (gateway, frontend):
        assert "ROS_LOCALHOST_ONLY=1" in unit
        assert "127.0.0.1" in unit
        assert "DISPLAY" not in unit
    assert "--host 127.0.0.1" in gateway
    assert "--hostname 127.0.0.1" in frontend


def test_gateway_sandbox_allows_rclpy_log_directory() -> None:
    gateway = read("deploy/systemd/substation-web-gateway.service")

    assert "ProtectSystem=strict" in gateway
    assert "/var/lib/substation/.ros" in gateway


def test_gateway_module_entrypoint_matches_the_systemd_command() -> None:
    unit = read("deploy/systemd/substation-web-gateway.service")
    entrypoint = ROOT / "ros2_ws/src/substation_web_gateway/substation_web_gateway/__main__.py"
    wrapper = read("scripts/deployment/substation-web-gateway")

    assert "scripts/deployment/substation-web-gateway" in unit
    assert entrypoint.is_file()
    source = entrypoint.read_text(encoding="utf-8")
    assert "--host" in source
    assert "--port" in source
    assert "source /opt/ros/jazzy/setup.bash" in wrapper
    assert "source /opt/substation/current/install/setup.bash" in wrapper
    assert ".venv-web/bin/python" in wrapper
    assert "-m substation_web_gateway" in wrapper


def test_nginx_is_the_only_product_lan_entry_and_proxies_ws() -> None:
    config = read("deploy/nginx/substation.conf")

    assert "listen 80" in config
    assert "proxy_pass http://127.0.0.1:8000" in config
    assert "proxy_pass http://127.0.0.1:3000" in config
    assert "proxy_http_version 1.1" in config
    assert "Upgrade" in config
    assert "8765" not in config


def test_foxglove_is_disabled_and_loopback_only() -> None:
    unit = read("deploy/systemd/substation-foxglove-bridge.service")
    allowlist = read("deploy/foxglove/read-only-allowlist.txt")

    assert "127.0.0.1" in unit
    assert "8765" in unit
    assert "WantedBy" not in unit
    assert "/tf" in allowlist
    assert "/diagnostics" in allowlist
    assert "/cmd_vel" not in allowlist


def test_safe_stop_entrypoint_has_required_barriers() -> None:
    script = read("scripts/deployment/substation-safe-stop")

    assert "emergency_stop" in script
    assert "nav2_active_goals" in script
    assert "cmd_vel_zero" in script
    assert "SHA256SUMS" in script


def test_release_builder_requires_clean_commit_and_writes_sha_inventory() -> None:
    script = read("scripts/deployment/build_release.sh")

    assert "git status --porcelain" in script
    assert "git archive" in script
    assert "release-manifest.json" in script
    assert "release-SHA256SUMS" in script
    assert "colcon --log-base" in script
    assert " build " in script
    assert "run build" in script
    assert ".venv" in script
    assert ".venv-web" in script


def test_root_installer_verifies_then_atomically_switches_current() -> None:
    script = read("scripts/deployment/install_release.sh")

    assert "EUID" in script
    assert "sha256sum -c release-SHA256SUMS" in script
    assert "/opt/substation/releases" in script
    assert "useradd" in script
    assert "systemctl daemon-reload" in script
    assert "nginx -t" in script
    assert "mv -T" in script
    assert "/opt/substation/current" in script


def test_root_installer_grants_headless_render_device_groups() -> None:
    script = read("scripts/deployment/install_release.sh")

    assert 'usermod -aG "render" substation' in script
    assert 'usermod -aG "video" substation' in script


def test_root_installer_prepares_service_home_and_runtime_caches() -> None:
    script = read("scripts/deployment/install_release.sh")

    assert "chgrp substation /var/lib/substation" in script
    assert "chmod 0750 /var/lib/substation" in script
    for path in (
        "/var/lib/substation/.ros",
        "/var/lib/substation/.gz/rendering",
        "/var/lib/substation/.gz/sim/log",
        "/var/lib/substation/.cache",
        "/var/lib/substation/.config",
    ):
        assert path in script


def test_release_activator_performs_safe_ordered_health_checked_deployment() -> None:
    script = read("scripts/deployment/activate_release.sh")

    assert "EUID" in script
    assert "--candidate" in script
    assert "--run-id" in script
    assert "/api/v1/robot/emergency-stop" in script
    assert "scripts/deployment/install_release.sh" in script
    assert "substation-web-frontend.service" in script
    assert "substation-core.service" in script
    assert "substation-gazebo.service" in script
    assert "substation-web-gateway.service" in script
    assert script.index("stop substation-web-frontend.service") < script.index(
        "stop substation-core.service substation-gazebo.service"
    )
    assert script.index("stop substation-core.service substation-gazebo.service") < script.index(
        "stop substation-web-gateway.service"
    )
    assert script.index("start substation-gazebo.service") < script.index(
        "start substation-core.service substation-web-gateway.service substation-web-frontend.service"
    )
    assert "systemctl reload nginx.service" in script
    assert "http://127.0.0.1:8000/healthz" in script
    assert "http://127.0.0.1:8000/readyz" in script
    assert "health_timeout_s=120" in script
    assert "/opt/substation/current" in script
    assert "journalctl" in script


def test_release_activation_repairs_the_controlled_start_time_mapping_race() -> None:
    activator = read("scripts/deployment/activate_release.sh")
    repair = read("scripts/deployment/repair_current_readiness.sh")
    helper = read("scripts/deployment/ensure_time_mapping.py")

    assert "repair_current_readiness.sh" in activator
    assert "EUID" in repair
    assert "/opt/substation/config/runtime.env" in repair
    assert "runuser -u substation" in repair
    assert "source /opt/ros/jazzy/setup.bash" in repair
    assert "source /opt/substation/current/install/setup.bash" in repair
    assert "ensure_time_mapping.py" in repair
    assert "http://127.0.0.1:8000/readyz" in repair
    assert "RunContext" in helper
    assert "QueryRunTimeMapping" in helper
    assert "RecordRunTimeMapping" in helper
    assert "DurabilityPolicy.TRANSIENT_LOCAL" in helper
    assert "context_revision" in helper
    assert "self.run_context" in helper
    assert "self.context:" not in helper


def test_latest_release_entrypoint_selects_candidate_and_generates_run_id() -> None:
    script = read("scripts/deployment/activate_latest_release.sh")

    assert "EUID" in script
    assert "/var/lib/substation/releases-staging" in script
    assert "release-manifest.json" in script
    assert "/proc/sys/kernel/random/uuid" in script
    assert "activate_release.sh" in script
    assert "--candidate" in script
    assert "--run-id" in script


def test_five_service_units_form_a_loopback_only_dependency_chain() -> None:
    units = {
        name: read(f"deploy/systemd/{name}.service")
        for name in (
            "substation-gazebo",
            "substation-core",
            "substation-web-gateway",
            "substation-web-frontend",
            "substation-foxglove-bridge",
        )
    }

    for source in units.values():
        assert "ROS_LOCALHOST_ONLY=1" in source
        assert "User=substation" in source
    assert "DISPLAY" not in units["substation-gazebo"]
    assert "substation-gazebo.service" in units["substation-core"]
    assert "substation-core.service" in units["substation-web-gateway"]
    assert "substation-web-gateway.service" in units["substation-web-frontend"]


def test_service_wrappers_launch_production_graph_from_current_release() -> None:
    gazebo = read("scripts/deployment/substation-gazebo")
    core = read("scripts/deployment/substation-core")

    for source in (gazebo, core):
        assert "source /opt/ros/jazzy/setup.bash" in source
        assert "source /opt/substation/current/install/setup.bash" in source
        assert "ROS_LOCALHOST_ONLY=1" in source
    assert "substation_navigation.launch.py" in gazebo
    assert "production_core.launch.py" in core
    assert "ros2 topic type /clock" in core
    assert "ros2 topic type /camera/image_raw" in core
    production_launch = read(
        "ros2_ws/src/substation_mission/launch/production_core.launch.py"
    )
    for launch_name in (
        "reporting.launch.py",
        "substation_core.launch.py",
        "inspection_executor.launch.py",
        "production_perception.launch.py",
    ):
        assert launch_name in production_launch
    setup = read("ros2_ws/src/substation_mission/setup.py")
    assert '"launch/production_core.launch.py"' in setup
