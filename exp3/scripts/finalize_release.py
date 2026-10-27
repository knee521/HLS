"""Validate existing evidence and package user-operated bitstreams with hashes."""

import argparse
import csv
import json
import re
import shutil
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from common.project import ROOT, sha256, write_json


def validate_evidence() -> None:
    """Fail closed when required software validation evidence is absent or failed."""
    for name in [
        "python-tests",
        "ruff-check",
        "ruff-format-check",
        "gui-smoke",
        "tb_uart",
        "tb_bringup",
        "tb_parser",
        "tb_response",
        "tb_display",
        "tb_diagnostic",
        "tb_system",
        "tb_watchdog",
        "implement-bringup",
        "implement-baseline",
        "implement-medium",
        "implement-fast",
    ]:
        result = json.loads((ROOT / "evidence/runs" / name / "result.json").read_text())
        if result["exit_code"] != 0:
            raise ValueError(f"Validation failed: {name}")
    quant = json.loads((ROOT / "model/quant_config.json").read_text())
    if quant["weights_sha256"] != sha256("hls/weights.h"):
        raise ValueError("HLS weights differ from the evaluated export")
    for variant in ["baseline", "serialized"]:
        for stage, expected in [("csim", 10000), ("cosim", 24)]:
            path = ROOT / f"evidence/simulation/{stage}_{variant}.csv"
            with path.open(newline="") as stream:
                rows = list(csv.DictReader(stream))
            if len(rows) != expected or any(
                r["c_prediction"] != r["reference_prediction"]
                or (stage == "csim" and int(r["score_mismatches"]) != 0)
                for r in rows
            ):
                raise ValueError(f"Incomplete or failing {stage} evidence for {variant}")
        repack = json.loads((ROOT / f"evidence/environment/ip_repack_{variant}.json").read_text())
        if repack["archive_sha256"] != sha256(repack["archive"]):
            raise ValueError(f"IP archive changed: {variant}")


def hls_metrics(variant: str) -> dict:
    folder = ROOT / f"build/hls_{variant}/solution1"
    root = ET.parse(folder / "syn/report/nn_infer_csynth.xml").getroot()

    def integer(path: str) -> int:
        value = root.findtext(path)
        if value is None:
            raise ValueError(f"Missing HLS metric {path}")
        return int(value)

    return {
        "latency_cycles": integer("PerformanceEstimates/SummaryOfOverallLatency/Best-caseLatency"),
        "interval_cycles": integer("PerformanceEstimates/SummaryOfOverallLatency/Interval-min"),
        "dsp": integer("AreaEstimates/Resources/DSP48E"),
        "bram18": integer("AreaEstimates/Resources/BRAM_18K"),
        "lut": integer("AreaEstimates/Resources/LUT"),
        "ff": integer("AreaEstimates/Resources/FF"),
        "measurement_type": "HLS synthesis estimate verified by RTL cosimulation",
    }


def implementation_metrics(configuration: str) -> dict:
    folder = ROOT / "evidence/implementation" / configuration
    metrics = json.loads((folder / "build_summary.json").read_text(encoding="utf-8"))
    report = (folder / "utilization.rpt").read_text(encoding="utf-8")
    for label, key in [
        ("Slice LUTs", "lut"),
        ("Slice Registers", "ff"),
        ("Block RAM Tile", "bram36"),
    ]:
        match = re.search(r"\|\s*" + label + r"\s*\|\s*([\d.]+)\s*\|", report)
        if not match:
            raise ValueError(f"Missing implemented metric {label}")
        metrics[key] = float(match.group(1))
    if metrics["wns_ns"] < 0 or metrics["hold_slack_ns"] < 0 or metrics["dsp"] > 60:
        raise ValueError("Timing/resource gate failed")
    if metrics["bram36"] > 30 or metrics["lut"] > 12000 or metrics["ff"] > 20000:
        raise ValueError("Implementation exceeded the declared engineering budget")
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    validate_evidence()
    evaluation = json.loads(
        (ROOT / "evidence/training/evaluation.json").read_text(encoding="utf-8")
    )
    if not evaluation["passed"] or evaluation["model_sha256"] != sha256("model/best.pt"):
        raise ValueError("Release has no passing frozen-model evaluation")
    source_hashes = {}
    for folder in [
        "common",
        "train",
        "host",
        "scripts",
        "rtl",
        "sim",
        "hls",
        "constraints",
        "configs",
        "tests",
    ]:
        for path in sorted((ROOT / folder).rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                source_hashes[path.relative_to(ROOT).as_posix()] = sha256(path)
    for name in ["pyproject.toml", "requirements-lock.txt"]:
        source_hashes[name] = sha256(name)
    write_json("evidence/source_hashes.json", source_hashes)
    implementations = {}
    for configuration in ["bringup", "baseline", "medium", "fast"]:
        metrics = implementation_metrics(configuration)
        implementations[configuration] = metrics
        release = ROOT / "release" / configuration
        release.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / f"build/vivado_{configuration}/exp3.bit", release / "exp3.bit")
        manifest = {
            "created_utc": datetime.now(timezone.utc).isoformat(),
            **metrics,
            "part": "xc7a35tfgg484-2",
            "clock_hz": 50_000_000,
            "model_sha256": sha256("model/best.pt"),
            "weights_sha256": sha256("hls/weights.h"),
            "bit_sha256": sha256(release / "exp3.bit"),
            "source_manifest_sha256": sha256("evidence/source_hashes.json"),
            "rightmost_index_verified_on_board": False,
            "status": "awaiting_user_hardware_validation",
        }
        write_json(release / "manifest.json", manifest)
    # The default candidate is the conservative baseline, not an unmeasured 'fastest' build.
    final = ROOT / "release/final"
    final.mkdir(parents=True, exist_ok=True)
    for name in ["exp3.bit", "manifest.json"]:
        shutil.copy2(ROOT / "release/baseline" / name, final / name)
    optimized, original = hls_metrics("baseline"), hls_metrics("serialized")
    write_json(
        "evidence/summary.json",
        {
            "model": evaluation,
            "hls_baseline": optimized,
            "hls_serialized": original,
            "hls_latency_reduction_fraction": 1
            - optimized["latency_cycles"] / original["latency_cycles"],
            "implementations": implementations,
            "hardware_performed_by_agent": False,
            "hardware_end_to_end_optimization_measured": False,
            "pending": [
                "board wiring",
                "program bitstreams",
                "echo test",
                "physical display mapping",
                "100-image board comparison",
                "handwriting",
                "fault recovery on board",
                "300-frame timing comparison",
                "1000-frame stability",
                "teacher acceptance",
                "personal report details and signature",
            ],
        },
    )
    print("Release candidates packaged; hardware acceptance remains pending.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
