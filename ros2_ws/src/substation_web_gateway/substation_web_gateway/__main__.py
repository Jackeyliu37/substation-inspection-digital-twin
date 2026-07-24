from __future__ import annotations

import argparse
from pathlib import Path


def build_runtime_state(
    manifest_path: str | Path = "/opt/substation/current/models/manifest.yaml",
    production_root: str | Path = "/var/lib/substation/models/production",
):
    from .app import GatewayState, load_production_models

    manifest = Path(manifest_path)
    return GatewayState(
        models=load_production_models(manifest, production_root)
        if manifest.is_file()
        else []
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Substation Web Gateway.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8000, type=int)
    args = parser.parse_args()

    import uvicorn

    from .app import create_app
    from .ros_adapter import RosGatewayAdapter

    state = build_runtime_state()
    uvicorn.run(
        create_app(
            state=state,
            db_path="/var/lib/substation/sqlite/gateway.sqlite3",
            adapter=RosGatewayAdapter(state),
        ),
        host=args.host,
        port=args.port,
    )


if __name__ == "__main__":
    main()
