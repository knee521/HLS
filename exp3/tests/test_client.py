import pytest

from common.protocol import RESULT, Frame, FrameDecoder
from host.client import SerialClient
from host.measurements import summarize


class FakeSerial:
    def __init__(self, mode="normal"):
        self.mode = mode
        self.now = 0
        self.pending = bytearray()
        self.requests = FrameDecoder()
        self.closed = False

    @property
    def in_waiting(self):
        return min(3, len(self.pending))  # enforce fragmented replies

    def write(self, data):
        self.now += 100_000
        count = min(100, len(data))  # enforce partial writes
        for request in self.requests.feed(data[:count]):
            response = Frame(0x81, request.sequence, RESULT.pack(0, 7, 0, 26365)).encode()
            if self.mode == "normal":
                stale = Frame(
                    0x81, (request.sequence - 1) & 65535, RESULT.pack(0, 2, 0, 9)
                ).encode()
                corrupt = response[:-1] + bytes([response[-1] ^ 1])
                self.pending.extend(stale + corrupt + response)
        return count

    def read(self, size=1):
        self.now += 100_000
        data = bytes(self.pending[:size])
        del self.pending[:size]
        return data

    def close(self):
        self.closed = True


def test_timing_includes_write_and_accepts_only_valid_matching_reply():
    transport = FakeSerial()
    client = SerialClient(transport, clock_ns=lambda: transport.now)
    result = client.request(bytes(784))
    assert result.status == "ok" and result.prediction == 7
    assert result.total_ms >= 0.8  # all eight partial write calls are inside t0..t1
    assert result.stale_responses == 1 and result.invalid_frames >= 1
    assert result.crc_ok and result.matched_seq


def test_timeout_is_bounded_and_busy_request_rejected():
    transport = FakeSerial("silent")
    client = SerialClient(transport, timeout_s=0.002, clock_ns=lambda: transport.now)
    assert client.request(bytes(784)).status == "failed"
    client._lock.acquire()
    try:
        with pytest.raises(RuntimeError):
            client.request(bytes(784))
    finally:
        client._lock.release()


def test_statistics_keep_failed_requests_in_denominator():
    rows = [
        {"status": "ok", "total_ms": 10, "label": 7, "prediction": 7, "reference_prediction": 7},
        {
            "status": "failed",
            "total_ms": 500,
            "label": 7,
            "prediction": None,
            "reference_prediction": 7,
        },
    ]
    stats = summarize(rows)
    assert stats["requests"] == 2 and stats["failures"] == 1
    assert stats["success_fraction"] == 0.5 and stats["p95_ms"] == 10
