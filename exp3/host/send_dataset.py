"""Measure a fixed set of images on a physically connected FPGA (user-operated)."""

import argparse
import time
from datetime import datetime

import numpy as np

from common.project import ROOT, project_path, read_config, write_json
from host.client import SerialClient
from host.measurements import append_csv, make_row, release_metadata, summarize


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/baseline.json")
    parser.add_argument("--port", required=True)
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--warmup", type=int, default=10)
    parser.add_argument("--release", type=project_path)
    parser.add_argument("--output", type=project_path)
    args = parser.parse_args()
    if not 1 <= args.count <= 10000 or args.repeats < 1 or args.warmup < 0:
        parser.error("count=1..10000, repeats>=1 and warmup>=0 are required")
    config = read_config(args.config)
    run_id = datetime.now().strftime("board_%Y%m%d_%H%M%S_%f")
    output = args.output or ROOT / "evidence/timing" / run_id
    metadata = release_metadata(args.release, args.baud)
    if (output / "transactions.csv").exists():
        raise FileExistsError(f"Use a new output directory to avoid mixing runs: {output}")
    pixels = np.fromfile(ROOT / "data/vectors/test_images.bin", dtype="u1").reshape(-1, 784)
    labels = np.fromfile(ROOT / "data/vectors/test_labels.bin", dtype="u1")
    reference = (
        np.fromfile(ROOT / "data/vectors/test_scores.bin", dtype="<i4").reshape(-1, 10).argmax(1)
    )
    rows = []
    client = SerialClient.connect(args.port, args.baud, config["request_timeout_s"])
    try:
        for i in range(args.warmup):
            data = pixels[i % args.count].tobytes()
            measured = client.request(data)
            append_csv(
                output / "warmup.csv",
                make_row(
                    measured,
                    pixels=data,
                    run_id=run_id,
                    config_id=config["config_id"],
                    baud=args.baud,
                    sample_id=i % args.count,
                    source="warmup",
                    metadata=metadata,
                ),
            )
            if measured.status != "ok":
                time.sleep(config["recovery_wait_s"])
        for repeat in range(args.repeats):
            for index in range(args.count):
                data = pixels[index].tobytes()
                measured = client.request(data)
                row = make_row(
                    measured,
                    pixels=data,
                    run_id=run_id,
                    config_id=config["config_id"],
                    baud=args.baud,
                    sample_id=index,
                    source=f"mnist-repeat-{repeat}",
                    metadata=metadata,
                    label=int(labels[index]),
                    reference=int(reference[index]),
                )
                rows.append(row)
                append_csv(output / "transactions.csv", row)
                if measured.status != "ok":
                    time.sleep(config["recovery_wait_s"])
    finally:
        client.close()
    summary = summarize(rows)
    write_json(output / "summary.json", summary)
    print(summary)
    return 0 if summary["failures"] == 0 and summary["reference_mismatches"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
