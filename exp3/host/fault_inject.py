"""Inject bounded malformed requests, then verify recovery on connected hardware."""

import argparse
import random
import time
from datetime import datetime

import numpy as np

from common.project import ROOT, project_path, read_config, write_json
from common.protocol import FrameDecoder, image_frame
from host.client import SerialClient


def faults(valid: bytes) -> dict[str, bytes]:
    bad_crc = bytearray(valid)
    bad_crc[-1] ^= 1
    bad_length = bytearray(valid)
    bad_length[6:8] = b"\xff\xff"
    bad_version = bytearray(valid)
    bad_version[2] = 2
    bad_type = bytearray(valid)
    bad_type[3] = 0x7F
    return {
        "crc": bytes(bad_crc),
        "length_ffff": bytes(bad_length),
        "version": bytes(bad_version),
        "type": bytes(bad_type),
        "truncated_header": valid[:5],
        "truncated_payload": valid[:100],
        "truncated_crc": valid[:-1],
        "random_noise": random.Random(2026).randbytes(2000),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True)
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--config", default="configs/baseline.json")
    parser.add_argument("--output", type=project_path)
    args = parser.parse_args()
    config = read_config(args.config)
    output = args.output or ROOT / "evidence/board" / datetime.now().strftime(
        "faults_%Y%m%d_%H%M%S_%f"
    )
    output.mkdir(parents=True, exist_ok=True)
    pixels = (ROOT / "data/vectors/test_images.bin").read_bytes()[:784]
    scores = np.fromfile(ROOT / "data/vectors/test_scores.bin", dtype="<i4", count=10)
    reference = int(scores.argmax())
    client = SerialClient.connect(args.port, args.baud, config["request_timeout_s"])
    results = []
    try:
        for name, data in faults(image_frame(pixels, 65535)).items():
            (output / f"{name}.bin").write_bytes(data)
            offset = 0
            while offset < len(data):
                count = client.transport.write(data[offset:])
                if count <= 0:
                    raise OSError("Fault injection write made no progress")
                offset += count
            # write() may return before the last UART stop bit reaches the device.
            # Include a conservative full wire time before the specified recovery wait.
            time.sleep(len(data) * 10 / args.baud + config["recovery_wait_s"])
            unexpected = bytearray()
            while client.transport.in_waiting:
                unexpected.extend(client.transport.read(client.transport.in_waiting))
            (output / f"{name}_unexpected_rx.bin").write_bytes(unexpected)
            unsolicited = FrameDecoder().feed(bytes(unexpected))
            recovered = client.request(pixels)
            passed = (
                not unsolicited and recovered.status == "ok" and recovered.prediction == reference
            )
            results.append(
                {
                    "case": name,
                    "passed": passed,
                    "unsolicited_frames": len(unsolicited),
                    "recovery": recovered.as_dict(),
                }
            )
            write_json(output / "results.json", results)
            print(name, passed)
    finally:
        client.close()
    return 0 if all(row["passed"] for row in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
