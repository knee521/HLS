"""Version-1 binary protocol; no GUI or serial-port dependencies.

Integers and CRC are little endian. CRC excludes the two sync bytes.
The decoder is bounded and accepts arbitrarily fragmented byte streams.
"""

import struct
from dataclasses import dataclass

SYNC = b"\xa5\x5a"
VERSION = 1
IMAGE_TYPE = 0x01
RESULT_TYPE = 0x81
IMAGE_BYTES = 784
RESULT_BYTES = 7
HEADER = struct.Struct("<BBHH")
RESULT = struct.Struct("<BBBI")
MAX_FRAME_BYTES = 794


def crc16(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ (0x1021 if crc & 0x8000 else 0)) & 0xFFFF
    return crc


@dataclass(frozen=True)
class Frame:
    kind: int
    sequence: int
    payload: bytes

    def encode(self) -> bytes:
        expected = {IMAGE_TYPE: IMAGE_BYTES, RESULT_TYPE: RESULT_BYTES}.get(self.kind)
        if expected is None or len(self.payload) != expected:
            raise ValueError("Unsupported type or incorrect payload length")
        if not 0 <= self.sequence <= 0xFFFF:
            raise ValueError("Sequence must fit uint16")
        body = HEADER.pack(VERSION, self.kind, self.sequence, len(self.payload)) + self.payload
        return SYNC + body + struct.pack("<H", crc16(body))


@dataclass(frozen=True)
class Recognition:
    status: int
    digit: int
    cycles: int

    @classmethod
    def from_frame(cls, frame: Frame) -> "Recognition":
        if frame.kind != RESULT_TYPE or len(frame.payload) != RESULT_BYTES:
            raise ValueError("Not a recognition response")
        status, digit, flags, cycles = RESULT.unpack(frame.payload)
        if flags != 0 or status not in (0, 1):
            raise ValueError("Unknown response status/flags")
        if (status == 0 and not 0 <= digit <= 9) or (status != 0 and digit != 255):
            raise ValueError("Invalid result digit")
        return cls(status, digit, cycles)


class FrameDecoder:
    """Resynchronize invalid frames and retain at most one incomplete frame."""

    def __init__(self) -> None:
        self.buffer = bytearray()
        self.invalid_frames = 0

    def reset(self) -> None:
        self.buffer.clear()

    def feed(self, data: bytes) -> list[Frame]:
        frames: list[Frame] = []
        # Incremental processing keeps memory bounded even for a large garbage chunk.
        for byte in data:
            self.buffer.append(byte)
            while len(self.buffer) >= 2:
                if self.buffer[:2] != SYNC:
                    del self.buffer[0]
                    continue
                if len(self.buffer) < 8:
                    break
                version, kind, sequence, length = HEADER.unpack(self.buffer[2:8])
                expected = {IMAGE_TYPE: IMAGE_BYTES, RESULT_TYPE: RESULT_BYTES}.get(kind)
                if version != VERSION or length != expected:
                    self.invalid_frames += 1
                    del self.buffer[0]
                    continue
                total = length + 10
                if len(self.buffer) < total:
                    break
                body = bytes(self.buffer[2 : total - 2])
                received_crc = int.from_bytes(self.buffer[total - 2 : total], "little")
                if crc16(body) != received_crc:
                    self.invalid_frames += 1
                    del self.buffer[0]
                    continue
                frames.append(Frame(kind, sequence, bytes(self.buffer[8 : total - 2])))
                del self.buffer[:total]
        return frames


def image_frame(pixels: bytes, sequence: int) -> bytes:
    return Frame(IMAGE_TYPE, sequence, pixels).encode()
