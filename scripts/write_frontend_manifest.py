#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--npm-version", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", args.npm_version):
        raise SystemExit("npm version must be an exact semantic version")
    document = {
        "name": "substation-inspection-frontend",
        "version": "0.1.0",
        "private": True,
        "packageManager": f"npm@{args.npm_version}",
        "scripts": {"build": "next build", "dev": "next dev --hostname 127.0.0.1 --port 3000", "start": "next start --hostname 127.0.0.1 --port 3000"},
        "dependencies": {"@react-three/fiber": "9.6.1", "echarts": "6.1.0", "next": "16.2.11", "react": "19.2.8", "react-dom": "19.2.8", "three": "0.185.1"},
        "devDependencies": {"@playwright/test": "1.61.1", "tailwindcss": "4.3.3", "typescript": "6.0.3"},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    work = args.output.with_suffix(args.output.suffix + ".new")
    work.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.output.exists():
        if json.loads(args.output.read_text(encoding="utf-8")) != document:
            work.unlink()
            raise SystemExit(f"refusing to overwrite changed frontend manifest: {args.output}")
        work.unlink()
    else:
        work.replace(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
