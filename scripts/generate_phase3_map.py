#!/usr/bin/env python3
"""Render the Phase 2 fixed collision geometry into the committed Nav2 map."""

from __future__ import annotations

import argparse
import math
from pathlib import Path
import xml.etree.ElementTree as ET


RESOLUTION = 0.05
ORIGIN_X = -8.0
ORIGIN_Y = -6.0
WIDTH = 320
HEIGHT = 240
FREE = 254
OCCUPIED = 0


def world_to_pixel(x: float, y: float) -> tuple[int, int]:
    return int((x - ORIGIN_X) / RESOLUTION), int((6.0 - y) / RESOLUTION)


def fill_box(data: bytearray, x: float, y: float, width: float, height: float) -> None:
    left, top = world_to_pixel(x - width / 2.0, y + height / 2.0)
    right, bottom = world_to_pixel(x + width / 2.0, y - height / 2.0)
    for row in range(max(0, top), min(HEIGHT, bottom + 1)):
        for column in range(max(0, left), min(WIDTH, right + 1)):
            data[row * WIDTH + column] = OCCUPIED


def fill_circle(data: bytearray, x: float, y: float, radius: float) -> None:
    center_x, center_y = world_to_pixel(x, y)
    pixel_radius = math.ceil(radius / RESOLUTION)
    for row in range(max(0, center_y - pixel_radius), min(HEIGHT, center_y + pixel_radius + 1)):
        for column in range(max(0, center_x - pixel_radius), min(WIDTH, center_x + pixel_radius + 1)):
            cell_x = ORIGIN_X + (column + 0.5) * RESOLUTION
            cell_y = 6.0 - (row + 0.5) * RESOLUTION
            if math.hypot(cell_x - x, cell_y - y) <= radius:
                data[row * WIDTH + column] = OCCUPIED


def pose_xyz(element: ET.Element | None) -> tuple[float, float, float]:
    if element is None or not element.text:
        return 0.0, 0.0, 0.0
    values = [float(value) for value in element.text.split()]
    return values[0], values[1], values[2]


def render(world_path: Path) -> bytes:
    data = bytearray([FREE]) * (WIDTH * HEIGHT)
    root = ET.parse(world_path).getroot()
    for model in root.findall(".//world/model"):
        if model.attrib["name"].startswith("scenario_"):
            continue
        if model.findtext("static") != "true":
            continue
        model_x, model_y, model_z = pose_xyz(model.find("pose"))
        for collision in model.findall(".//collision"):
            collision_x, collision_y, collision_z = pose_xyz(collision.find("pose"))
            x, y, z = model_x + collision_x, model_y + collision_y, model_z + collision_z
            box = collision.find("geometry/box/size")
            cylinder = collision.find("geometry/cylinder/radius")
            if box is not None and box.text:
                size = [float(value) for value in box.text.split()]
                if z + size[2] / 2.0 < 0.1:
                    continue
                fill_box(data, x, y, size[0], size[1])
            elif cylinder is not None and cylinder.text:
                fill_circle(data, x, y, float(cylinder.text))
    return bytes(data)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--world", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = render(args.world)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(f"P5\n{WIDTH} {HEIGHT}\n255\n".encode() + payload)


if __name__ == "__main__":
    main()
