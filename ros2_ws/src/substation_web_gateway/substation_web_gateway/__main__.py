from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Substation Web Gateway.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8000, type=int)
    args = parser.parse_args()

    import uvicorn

    from .app import GatewayState, create_app
    from .ros_adapter import RosGatewayAdapter

    state = GatewayState()
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
