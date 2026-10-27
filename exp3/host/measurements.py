"""Stable CSV schema and timing statistics; failures remain in the denominator."""

import csv
import hashlib
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path

from common.project import ROOT, sha256
from host.client import Measurement

FIELDS = [
    "timestamp",
    "run_id",
    "config_id",
    "model_sha256",
    "bit_sha256",
    "bit_identity_source",
    "baud",
    "seq",
    "sample_id",
    "image_sha256",
    "source",
    "label",
    "prediction",
    "reference_prediction",
    "status",
    "crc_ok",
    "matched_seq",
    "inference_cycles",
    "total_ms",
    "attempt",
    "invalid_frames",
    "stale_responses",
    "error_reason",
]


def release_metadata(release: Path | None, baud: int | None = None) -> dict:
    manifest_path = release / "manifest.json" if release else None
    if manifest_path and manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if sha256(release / "exp3.bit") != manifest["bit_sha256"]:
            raise ValueError("Release bitstream hash mismatch")
        if manifest["top"] != "exp3_top" or (baud is not None and manifest["baud"] != baud):
            raise ValueError("Selected release is not an inference bitstream at the requested baud")
        if manifest["model_sha256"] != sha256("model/best.pt"):
            raise ValueError("Selected release uses a different model")
        return {
            "model_sha256": manifest["model_sha256"],
            "bit_sha256": manifest["bit_sha256"],
            "bit_identity_source": "user_selected_release_not_read_from_device",
        }
    if release is not None:
        raise FileNotFoundError(f"Release manifest missing: {manifest_path}")
    return {
        "model_sha256": sha256(ROOT / "model/best.pt"),
        "bit_sha256": "unknown",
        "bit_identity_source": "not_verified",
    }


def make_row(
    measurement: Measurement,
    *,
    pixels: bytes,
    run_id: str,
    config_id: str,
    baud: int,
    sample_id: str | int,
    source: str,
    metadata: dict,
    label: int | str = "",
    reference: int | str = "",
) -> dict:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "config_id": config_id,
        **metadata,
        "baud": baud,
        "sample_id": sample_id,
        "image_sha256": hashlib.sha256(pixels).hexdigest(),
        "source": source,
        "label": label,
        "reference_prediction": reference,
        "attempt": 1,
        **measurement.as_dict(),
    }


def append_csv(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists() or path.stat().st_size == 0
    with path.open("a", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        if new:
            writer.writeheader()
        writer.writerow(row)


def summarize(rows: list[dict]) -> dict:
    successful = [row for row in rows if row["status"] == "ok"]
    times = sorted(float(row["total_ms"]) for row in successful)
    labeled = [row for row in successful if row["label"] != ""]
    mismatches = [
        row
        for row in successful
        if row["reference_prediction"] != ""
        and int(row["prediction"]) != int(row["reference_prediction"])
    ]
    return {
        "requests": len(rows),
        "successes": len(successful),
        "failures": len(rows) - len(successful),
        "success_fraction": len(successful) / len(rows) if rows else None,
        "accuracy_successful_labeled": (
            sum(int(r["prediction"]) == int(r["label"]) for r in labeled) / len(labeled)
            if labeled
            else None
        ),
        "reference_mismatches": len(mismatches),
        "mean_ms": statistics.mean(times) if times else None,
        "median_ms": statistics.median(times) if times else None,
        "p95_ms": times[math.ceil(0.95 * len(times)) - 1] if times else None,
        "min_ms": min(times) if times else None,
        "max_ms": max(times) if times else None,
        "latency_population": "successful transactions only; failures counted separately",
    }
