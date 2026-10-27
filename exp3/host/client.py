"""Single-in-flight serial transactions and monotonic end-to-end measurements."""

import threading
import time
from dataclasses import asdict, dataclass
from typing import Protocol

import serial

from common.protocol import RESULT_TYPE, FrameDecoder, Recognition, image_frame


class Transport(Protocol):
    @property
    def in_waiting(self) -> int: ...
    def write(self, data: bytes) -> int: ...
    def read(self, size: int = 1) -> bytes: ...
    def close(self) -> None: ...


@dataclass(frozen=True)
class Measurement:
    seq: int
    status: str
    prediction: int | None
    inference_cycles: int | None
    total_ms: float
    crc_ok: bool
    matched_seq: bool
    invalid_frames: int
    stale_responses: int
    error_reason: str

    def as_dict(self) -> dict:
        return asdict(self)


class SerialClient:
    def __init__(
        self, transport: Transport, timeout_s: float = 0.5, clock_ns=time.perf_counter_ns
    ) -> None:
        if timeout_s <= 0:
            raise ValueError("Transaction timeout must be positive")
        self.transport = transport
        self.timeout_s = timeout_s
        self.clock_ns = clock_ns
        self.sequence = 0
        self.decoder = FrameDecoder()
        self._lock = threading.Lock()

    @classmethod
    def connect(cls, port: str, baud: int, timeout_s: float = 0.5) -> "SerialClient":
        transport = serial.Serial(
            port=port,
            baudrate=baud,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.002,
            write_timeout=timeout_s,
            xonxoff=False,
            rtscts=False,
            dsrdtr=False,
        )
        transport.reset_input_buffer()  # once at connection, never after sending a frame
        return cls(transport, timeout_s)

    def close(self) -> None:
        self.transport.close()

    def request(self, pixels: bytes) -> Measurement:
        if not self._lock.acquire(blocking=False):
            raise RuntimeError("A recognition transaction is already in progress")
        try:
            seq = self.sequence
            wire = image_frame(pixels, seq)  # validate and build before starting the timer
            self.sequence = (self.sequence + 1) & 0xFFFF
            self.decoder.reset()
            invalid_before = self.decoder.invalid_frames
            stale = 0
            t0 = self.clock_ns()
            deadline = t0 + int(self.timeout_s * 1e9)
            try:
                offset = 0
                while offset < len(wire):
                    if self.clock_ns() >= deadline:
                        raise TimeoutError("Request write deadline exceeded")
                    written = self.transport.write(wire[offset:])
                    if written <= 0:
                        raise OSError("Serial write made no progress")
                    offset += written
                while self.clock_ns() < deadline:
                    data = self.transport.read(max(1, min(self.transport.in_waiting, 4096)))
                    for frame in self.decoder.feed(data):
                        if frame.kind != RESULT_TYPE or frame.sequence != seq:
                            stale += 1
                            continue
                        result = Recognition.from_frame(frame)
                        t1 = self.clock_ns()
                        if t1 >= deadline:
                            raise TimeoutError("Response arrived after transaction deadline")
                        return Measurement(
                            seq,
                            "ok" if result.status == 0 else "core_timeout",
                            result.digit if result.status == 0 else None,
                            result.cycles,
                            (t1 - t0) / 1e6,
                            True,
                            True,
                            self.decoder.invalid_frames - invalid_before,
                            stale,
                            "" if result.status == 0 else "FPGA core watchdog",
                        )
                raise TimeoutError("No matching valid response before deadline")
            except (OSError, serial.SerialException, ValueError, TimeoutError) as exc:
                return Measurement(
                    seq,
                    "failed",
                    None,
                    None,
                    (self.clock_ns() - t0) / 1e6,
                    False,
                    False,
                    self.decoder.invalid_frames - invalid_before,
                    stale,
                    f"{type(exc).__name__}: {exc}",
                )
        finally:
            self._lock.release()
