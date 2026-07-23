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


def test_gateway_module_entrypoint_matches_the_systemd_command() -> None:
    unit = read("deploy/systemd/substation-web-gateway.service")
    entrypoint = ROOT / "ros2_ws/src/substation_web_gateway/substation_web_gateway/__main__.py"

    assert "-m substation_web_gateway" in unit
    assert entrypoint.is_file()
    source = entrypoint.read_text(encoding="utf-8")
    assert "--host" in source
    assert "--port" in source


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
