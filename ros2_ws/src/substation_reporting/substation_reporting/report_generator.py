from __future__ import annotations

from dataclasses import dataclass
import hashlib
import html
import io
import json
from typing import Any
import zipfile


@dataclass(frozen=True)
class ReportArtifacts:
    html: bytes
    pdf: bytes
    evidence_zip: bytes


class ReportGenerator:
    REQUIRED_FIELDS = (
        "run_id", "generated_at", "git_commit", "model_versions",
        "dataset_versions", "assets", "alerts", "tasks", "trajectory",
        "mission", "model_manifest_yaml", "rosbag_metadata_yaml",
        "evidence_ids",
    )

    def generate(self, snapshot: dict[str, Any]) -> ReportArtifacts:
        if any(field not in snapshot for field in self.REQUIRED_FIELDS):
            raise ValueError("REPORT_INPUT_INVALID")
        if (
            not isinstance(snapshot["run_id"], str)
            or len(snapshot["git_commit"]) != 40
            or not isinstance(snapshot["mission"], dict)
            or not isinstance(snapshot["model_manifest_yaml"], str)
            or "schema_version:" not in snapshot["model_manifest_yaml"]
            or not isinstance(snapshot["rosbag_metadata_yaml"], str)
            or "rosbag2_bagfile_information:" not in snapshot["rosbag_metadata_yaml"]
        ):
            raise ValueError("REPORT_INPUT_INVALID")
        document = self._render_html(snapshot)
        html_bytes = document.encode("utf-8")
        pdf_bytes = self._render_pdf(snapshot)
        bundle_entries = [
            "report.html",
            "report.pdf",
            "rosbag2/metadata.yaml",
            "snapshots/alerts.json",
            "snapshots/mission.json",
            "snapshots/model-manifest.yaml",
            "snapshots/trajectory.json",
        ]
        manifest = {
            "schema_version": "1.0",
            "run_id": snapshot["run_id"],
            "git_commit": snapshot["git_commit"],
            "model_versions": snapshot["model_versions"],
            "dataset_versions": snapshot["dataset_versions"],
            "evidence_ids": snapshot["evidence_ids"],
            "bundle_entries": bundle_entries,
        }
        files = {
            "manifest.json": json.dumps(manifest, ensure_ascii=True, indent=2).encode(),
            "report.html": html_bytes,
            "report.pdf": pdf_bytes,
            "rosbag2/metadata.yaml": snapshot["rosbag_metadata_yaml"].encode("utf-8"),
            "snapshots/alerts.json": self._json_bytes(snapshot["alerts"]),
            "snapshots/mission.json": self._json_bytes(snapshot["mission"]),
            "snapshots/model-manifest.yaml": snapshot["model_manifest_yaml"].encode("utf-8"),
            "snapshots/trajectory.json": self._json_bytes(snapshot["trajectory"]),
        }
        files["SHA256SUMS"] = "".join(
            f"{hashlib.sha256(files[name]).hexdigest()}  {name}\n"
            for name in sorted(files)
        ).encode("ascii")
        evidence_zip = self._zip(files)
        return ReportArtifacts(html_bytes, pdf_bytes, evidence_zip)

    @staticmethod
    def _json_bytes(value: Any) -> bytes:
        return json.dumps(
            value,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        ).encode("utf-8")

    @staticmethod
    def _render_html(snapshot: dict[str, Any]) -> str:
        def text(value: Any) -> str:
            return html.escape(str(value))

        assets = "".join(
            f"<tr><td>{text(item.get('asset_id'))}</td><td>{text(item.get('risk'))}</td>"
            f"<td>{text(item.get('level'))}</td></tr>"
            for item in snapshot["assets"]
        )
        alerts = "".join(
            f"<li>{text(item.get('asset_id'))}: {text(item.get('code'))}</li>"
            for item in snapshot["alerts"]
        )
        tasks = "".join(
            f"<li>{text(item.get('asset_id'))}: {text(item.get('reason'))}, "
            f"priority {text(item.get('priority'))}</li>"
            for item in snapshot["tasks"]
        )
        return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Substation inspection report</title>
<style>body{{font:14px system-ui;background:#0b1220;color:#e8eef7;padding:32px}}table{{border-collapse:collapse}}td,th{{padding:8px 14px;border:1px solid #334155}}section{{margin:24px 0}}</style>
</head><body><h1>Substation inspection report</h1>
<p>Run {text(snapshot['run_id'])} at {text(snapshot['generated_at'])}</p>
<p>Implementation {text(snapshot['git_commit'])}</p>
<section><h2>Model and dataset versions</h2><pre>{text(json.dumps({'models': snapshot['model_versions'], 'datasets': snapshot['dataset_versions'], 'evidence_ids': snapshot['evidence_ids']}, indent=2))}</pre></section>
<section><h2>Asset risk</h2><table><tr><th>Asset</th><th>Score</th><th>Level</th></tr>{assets}</table></section>
<section><h2>Alerts</h2><ul>{alerts or '<li>None</li>'}</ul></section>
<section><h2>Risk-driven task changes</h2><ul>{tasks or '<li>None</li>'}</ul></section>
<section><h2>Trajectory samples</h2><pre>{text(json.dumps(snapshot['trajectory'], indent=2))}</pre></section>
</body></html>"""

    @staticmethod
    def _render_pdf(snapshot: dict[str, Any]) -> bytes:
        lines = [
            "Substation inspection report",
            f"Run: {snapshot['run_id']}",
            f"Generated: {snapshot['generated_at']}",
            f"Implementation: {snapshot['git_commit']}",
            f"Assets: {len(snapshot['assets'])}; Alerts: {len(snapshot['alerts'])}; Tasks: {len(snapshot['tasks'])}",
        ]
        content = "BT /F1 12 Tf 50 760 Td " + " ".join(
            f"({line.replace('(', '[').replace(')', ']')}) Tj 0 -18 Td" for line in lines
        ) + " ET"
        objects = [
            b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
            b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n",
            b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj\n",
            b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
            f"5 0 obj << /Length {len(content.encode())} >> stream\n{content}\nendstream endobj\n".encode(),
        ]
        output = bytearray(b"%PDF-1.4\n")
        offsets = []
        for obj in objects:
            offsets.append(len(output))
            output.extend(obj)
        xref = len(output)
        output.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
        output.extend("".join(f"{offset:010d} 00000 n \n" for offset in offsets).encode())
        output.extend(f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
        return bytes(output)

    @staticmethod
    def _zip(files: dict[str, bytes]) -> bytes:
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in sorted(files.items()):
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, data)
        return stream.getvalue()
