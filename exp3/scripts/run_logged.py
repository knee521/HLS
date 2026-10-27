"""Execute a subprocess without shell interpolation and retain complete evidence."""

import argparse
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from common.project import ROOT, project_path, write_json


def run_logged(
    name: str, command: list[str], cwd: Path | None = None, timeout: float = 3600
) -> int:
    folder = ROOT / "evidence" / "runs" / name
    folder.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    record = {
        "command": command,
        "cwd": str(cwd or ROOT),
        "started_utc": datetime.now(timezone.utc).isoformat(),
    }
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    with (folder / "output.log").open("w", encoding="utf-8") as log:
        try:
            result = subprocess.run(
                command,
                cwd=cwd or ROOT,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=timeout,
                check=False,
            )
            code = result.returncode
        except subprocess.TimeoutExpired:
            log.write("\nRUNNER TIMEOUT\n")
            code = 124
    record["native_exit_code"] = code
    if Path(command[0]).name.lower() == "vivado_hls.bat":
        # The 2018.3 Windows launcher pipes through tee and can mask a Tcl failure.
        contents = (folder / "output.log").read_text(encoding="utf-8", errors="replace")
        if "ERROR:" in contents or "EXP3_HLS_PASS" not in contents:
            code = code or 1
    record.update(exit_code=code, elapsed_s=time.perf_counter() - start)
    write_json(folder / "result.json", record)
    print(json.dumps(record, ensure_ascii=False), flush=True)
    return code


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--cwd", type=project_path, default=ROOT)
    parser.add_argument("--timeout", type=float, default=3600)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("A subprocess command is required after --")
    return run_logged(args.name, command, args.cwd, args.timeout)


if __name__ == "__main__":
    raise SystemExit(main())
