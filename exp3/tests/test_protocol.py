"""Wire-format golden vectors and adversarial stream behavior."""

import random

import pytest

from common.protocol import Frame, FrameDecoder, Recognition, crc16, image_frame


def test_golden_crc_and_frames():
    assert crc16(b"123456789") == 0x29B1
    request = image_frame(bytes(784), 0x1234)
    assert len(request) == 794
    assert request[:8].hex() == "a55a010134121003"
    assert request[-2:].hex() == "1d88"
    response = bytes.fromhex("A5 5A 01 81 34 12 07 00 00 07 00 40 63 00 00 EA F5")
    frames = FrameDecoder().feed(response)
    assert frames[0].sequence == 0x1234
    assert Recognition.from_frame(frames[0]) == Recognition(0, 7, 25408)


@pytest.mark.parametrize("chunk", [1, 2, 3, 7, 16, 793, 794])
def test_fragmented_payload_sync_and_resynchronization(chunk):
    payload = b"\xa5\x5a\x00\xff" * 196
    valid = image_frame(payload, 65535)
    corrupted = bytearray(valid)
    corrupted[-1] ^= 1
    stream = b"noise\xa5" + bytes(corrupted) + valid + image_frame(bytes(784), 0)
    decoder = FrameDecoder()
    frames = []
    for offset in range(0, len(stream), chunk):
        frames.extend(decoder.feed(stream[offset : offset + chunk]))
    assert frames == [Frame(1, 65535, payload), Frame(1, 0, bytes(784))]


def test_garbage_is_bounded_and_invalid_length_recovers():
    decoder = FrameDecoder()
    decoder.feed(random.Random(2026).randbytes(100_000))
    assert len(decoder.buffer) <= 794
    decoder.reset()  # host transaction deadline discards a truncated candidate
    invalid = bytes.fromhex("a55a01010000ffff")
    assert decoder.feed(invalid + image_frame(bytes(784), 12))[0].sequence == 12


def test_invalid_result_and_request_rejected():
    with pytest.raises(ValueError):
        image_frame(bytes(783), 0)
    with pytest.raises(ValueError):
        image_frame(bytes(784), 65536)
    with pytest.raises(ValueError):
        Recognition.from_frame(Frame(0x81, 0, bytes([0, 10, 0, 0, 0, 0, 0])))
