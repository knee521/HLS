"""Run only with the bringup bitstream: verify 2560 UART echo bytes."""

import argparse
import time
from datetime import datetime

import serial

from common.project import ROOT, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True)
    parser.add_argument("--baud", type=int, default=115200)
    args = parser.parse_args()
    expected = bytes(range(256)) * 10
    received = bytearray()
    output = ROOT / "evidence/board" / datetime.now().strftime("echo_%Y%m%d_%H%M%S_%f")
    with serial.Serial(
        args.port,
        args.baud,
        timeout=0.002,
        write_timeout=1,
        xonxoff=False,
        rtscts=False,
        dsrdtr=False,
    ) as port:
        port.reset_input_buffer()
        started = time.perf_counter()
        offset = 0
        while offset < len(expected):
            count = port.write(expected[offset:])
            if count <= 0:
                raise OSError("Serial write made no progress")
            offset += count
        deadline = started + 2
        while len(received) < len(expected) and time.perf_counter() < deadline:
            received.extend(port.read(max(1, port.in_waiting)))
        result = {
            "port": args.port,
            "baud": args.baud,
            "bytes_sent": len(expected),
            "bytes_received": len(received),
            "passed": received == expected,
            "elapsed_ms": (time.perf_counter() - started) * 1000,
            "evidence_dir": str(output.relative_to(ROOT)),
            "first_mismatch_index": next(
                (i for i, (a, b) in enumerate(zip(expected, received, strict=False)) if a != b),
                min(len(expected), len(received)) if received != expected else None,
            ),
        }
    output.mkdir(parents=True, exist_ok=False)
    (output / "sent.bin").write_bytes(expected)
    (output / "received.bin").write_bytes(received)
    write_json(output / "result.json", result)
    write_json("evidence/board/echo_result.json", result)
    print(result)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
