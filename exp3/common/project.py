"""Project-relative paths and deterministic evidence serialization."""

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def project_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def read_config(path: str | Path = "configs/baseline.json") -> dict[str, Any]:
    with project_path(path).open(encoding="utf-8") as stream:
        config = json.load(stream)
    if config["network"] != [784, 32, 10] or config["part"] != "xc7a35tfgg484-2":
        raise ValueError("Network/device differ from the approved execution plan")
    if config["clock_hz"] != 50_000_000 or config["input_fraction_bits"] != 8:
        raise ValueError("Clock and input scaling must match the RTL/quantization contract")
    return config


def write_json(path: str | Path, value: Any) -> None:
    target = project_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(target)


def sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with project_path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
