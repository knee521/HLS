"""Reproducible non-hardware build entry point. Never programs a device."""

import argparse
import json
import os
import sys

from common.project import ROOT, read_config, sha256, write_json
from scripts.run_logged import run_logged

VIVADO = "D:/HLS/software/Xilinx/Vivado/2018.3/bin/vivado.bat"
HLS = "D:/HLS/software/Xilinx/Vivado/2018.3/bin/vivado_hls.bat"


def checked(name: str, command: list[str], timeout: int = 3600) -> None:
    if run_logged(name, command, timeout=timeout):
        raise RuntimeError(f"Stage failed: {name}; inspect evidence/runs/{name}/output.log")


def build_hls(variant: str) -> None:
    evaluation = json.loads(
        (ROOT / "evidence/training/evaluation.json").read_text(encoding="utf-8")
    )
    if not evaluation["passed"] or evaluation["model_sha256"] != sha256("model/best.pt"):
        raise ValueError("Frozen model lacks a passing evaluation")
    quant = json.loads((ROOT / "model/quant_config.json").read_text(encoding="utf-8"))
    if quant["weights_sha256"] != sha256("hls/weights.h"):
        raise ValueError("Generated HLS weights changed after quantization")
    os.environ["EXP3_HLS_VARIANT"] = variant
    os.environ["EXP3_HLS_MODE"] = "all"
    name = f"hls-{variant}"
    code = run_logged(name, [HLS, "-f", "hls/run_hls.tcl"])
    if code:
        log = (ROOT / "evidence/runs" / name / "output.log").read_text(encoding="utf-8")
        errors = [line for line in log.splitlines() if line.startswith("ERROR:")]
        # Recover only the observed date-overflow export failure, never a C/RTL failure.
        if (
            "bad lexical cast" not in log
            or "core_revision" not in log
            or "*** C/RTL co-simulation finished: PASS ***" not in log
            or "prediction_mismatches=0 score_mismatches=0" not in log
            or errors != ["ERROR: [IMPL 213-28] Failed to generate IP."]
        ):
            raise RuntimeError(f"HLS {variant} failed outside the supported packaging workaround")
        checked(
            f"repack-{variant}",
            [sys.executable, "-m", "scripts.repack_hls_ip", "--variant", variant],
        )
    write_json(
        f"evidence/simulation/hls_{variant}_status.json",
        {
            "variant": variant,
            "csim": "passed",
            "cosim": "passed",
            "synthesis": "passed",
            "ip_packaging": "passed_with_project_local_revision_fix" if code else "passed",
            "source_sha256": sha256("hls/nn_infer.cpp"),
            "weights_sha256": sha256("hls/weights.h"),
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stage", choices=["checks", "train", "hls", "rtl", "implement", "all"], default="checks"
    )
    parser.add_argument("--variant", choices=["baseline", "serialized"], default="baseline")
    parser.add_argument(
        "--configuration", choices=["baseline", "medium", "fast", "bringup", "all"], default="all"
    )
    parser.add_argument("--rightmost-index", type=int, choices=range(6), default=0)
    args = parser.parse_args()
    read_config()
    if args.stage in ("checks", "all"):
        checked("python-tests", [sys.executable, "-m", "pytest", "-q"])
        checked("ruff-check", [sys.executable, "-m", "ruff", "check", "."])
        checked("ruff-format-check", [sys.executable, "-m", "ruff", "format", "--check", "."])
        checked("gui-smoke", [sys.executable, "-m", "host.gui", "--smoke-test"])
    if args.stage in ("train", "all"):
        for module in ["train.train_mlp", "train.export_quant", "train.evaluate"]:
            checked(module.replace(".", "-"), [sys.executable, "-m", module])
    if args.stage in ("hls", "all"):
        build_hls(args.variant)
    if args.stage in ("rtl", "all"):
        for test in [
            "tb_uart",
            "tb_bringup",
            "tb_parser",
            "tb_response",
            "tb_display",
            "tb_diagnostic",
            "tb_system",
            "tb_watchdog",
        ]:
            checked(
                test,
                [
                    VIVADO,
                    "-mode",
                    "batch",
                    "-source",
                    "scripts/run_rtl_tests.tcl",
                    "-tclargs",
                    test,
                ],
            )
    if args.stage in ("implement", "all"):
        configurations = (
            ["bringup", "baseline", "medium", "fast"]
            if args.configuration == "all"
            else [args.configuration]
        )
        for configuration in configurations:
            checked(
                f"implement-{configuration}",
                [
                    VIVADO,
                    "-mode",
                    "batch",
                    "-source",
                    "scripts/create_vivado.tcl",
                    "-tclargs",
                    configuration,
                    str(args.rightmost_index),
                ],
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
