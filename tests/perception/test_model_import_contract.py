from __future__ import annotations

import csv
import importlib.util
from pathlib import Path
import sys
import zipfile

import pytest


SCRIPT = Path(__file__).parents[2] / "scripts/import_phase4_models.py"
SPEC = importlib.util.spec_from_file_location("import_phase4_models", SCRIPT)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


def _archive(tmp_path: Path, *, safety_map50: float = 0.69) -> Path:
    root = tmp_path / "payload"
    specs = {
        "yolo11n_safety": ("detect", ["person", "no_hardhat", "hardhat", "fire", "smoke"], "metrics/mAP50(B)", safety_map50),
        "yolo11n_equipment": ("detect", [
            "open_blade_disconnect_switch", "closed_blade_disconnect_switch",
            "open_tandem_disconnect_switch", "closed_tandem_disconnect_switch",
            "breaker", "fuse_disconnect_switch", "glass_disc_insulator",
            "porcelain_pin_insulator", "muffle", "lightning_arrester",
            "recloser", "power_transformer", "current_transformer",
            "potential_transformer", "tripolar_disconnect_switch",
        ], "metrics/mAP50(B)", 0.84),
        "yolo11n_fault": ("classify", ["0_normal", "1_corrosion", "2_broken_component", "3_bird_nest"], "metrics/accuracy_top1", 0.99),
        "yolo11n_meter_locator": ("detect", ["meter"], "metrics/mAP50(B)", 0.99),
    }
    for name, (task, _names, metric, value) in specs.items():
        run = root / "substation_yolo_runs" / "runs" / name
        (run / "weights").mkdir(parents=True)
        (run / "weights/best.pt").write_bytes(f"{name}-weights".encode())
        (run / "args.yaml").write_text(f"task: {task}\n", encoding="utf-8")
        (run / "results.csv").write_text(
            f"epoch,{metric}\n1,{value}\n", encoding="utf-8"
        )
    archive = tmp_path / "models.zip"
    with zipfile.ZipFile(archive, "w") as output:
        for path in root.rglob("*"):
            if path.is_file():
                output.write(path, path.relative_to(root).as_posix())
    return archive


class _FakeModel:
    def __init__(self, path: str):
        name = Path(path).parents[1].name
        self.task = "classify" if name == "yolo11n_fault" else "detect"
        self.names = {
            "yolo11n_safety": {0: "person", 1: "no_hardhat", 2: "hardhat", 3: "fire", 4: "smoke"},
            "yolo11n_equipment": {i: name for i, name in enumerate([
                "open_blade_disconnect_switch", "closed_blade_disconnect_switch",
                "open_tandem_disconnect_switch", "closed_tandem_disconnect_switch",
                "breaker", "fuse_disconnect_switch", "glass_disc_insulator",
                "porcelain_pin_insulator", "muffle", "lightning_arrester",
                "recloser", "power_transformer", "current_transformer",
                "potential_transformer", "tripolar_disconnect_switch",
            ])},
            "yolo11n_fault": {0: "0_normal", 1: "1_corrosion", 2: "2_broken_component", 3: "3_bird_nest"},
            "yolo11n_meter_locator": {0: "meter"},
        }[name]


def test_inspection_rejects_safety_below_map50_and_keeps_all_hashes(tmp_path: Path) -> None:
    archive = _archive(tmp_path, safety_map50=0.69)
    result = module.inspect_archive(archive, model_loader=_FakeModel)

    assert result["production_ready"] is False
    assert result["artifacts"]["yolo11n_safety"]["acceptance_status"] == "rejected"
    assert result["artifacts"]["yolo11n_equipment"]["acceptance_status"] == "passed"
    assert len(result["artifacts"]["yolo11n_safety"]["sha256"]) == 64


def test_inspection_rejects_unsafe_archive_path(tmp_path: Path) -> None:
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("../escape.txt", "bad")

    with pytest.raises(module.ImportError, match="ARCHIVE_PATH_INVALID"):
        module.inspect_archive(archive, model_loader=_FakeModel)
