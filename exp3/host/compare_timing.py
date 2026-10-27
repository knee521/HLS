"""Compare two real board CSVs without mixing estimated and measured timings."""

import argparse
import csv

from common.project import project_path, write_json
from host.measurements import summarize


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=project_path)
    parser.add_argument("after", type=project_path)
    parser.add_argument(
        "--output", type=project_path, default=project_path("evidence/timing/comparison.json")
    )
    args = parser.parse_args()
    runs = []
    for path in [args.before, args.after]:
        with path.open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        if not rows:
            raise ValueError("A measurement CSV is empty")
        runs.append(rows)
    for key in ["image_sha256", "sample_id", "model_sha256"]:
        if [row[key] for row in runs[0]] != [row[key] for row in runs[1]]:
            raise ValueError(f"Uncontrolled comparison: {key} differs")
    before, after = [summarize(rows) for rows in runs]
    if not before["mean_ms"] or not after["mean_ms"]:
        raise ValueError("Both runs need successful measurements")
    result = {
        "before": before,
        "after": after,
        "mean_reduction_fraction": 1 - after["mean_ms"] / before["mean_ms"],
        "mean_speedup": before["mean_ms"] / after["mean_ms"],
        "p95_speedup": before["p95_ms"] / after["p95_ms"],
        "source": "user-operated hardware measurements",
    }
    write_json(args.output, result)
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
