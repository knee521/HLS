import numpy as np
import pytest

from common.quantization import QuantizedMLP, round_symmetric


def model(bias1=0, bias2=0, shift=1):
    return QuantizedMLP(
        np.zeros((32, 784), dtype=np.int64),
        np.full(32, bias1, dtype=np.int64),
        np.zeros((10, 32), dtype=np.int64),
        np.full(10, bias2, dtype=np.int64),
        0,
        0,
        8 - shift,
    )


def test_rounding_relu_saturation_and_all_negative_argmax():
    assert round_symmetric(np.array([-1.5, -0.5, 0.5, 1.5])).tolist() == [-2, -1, 1, 2]
    q = model(bias1=511, bias2=-20)
    pred, scores, hidden, saturated = q.infer(np.zeros((1, 784), dtype=np.uint8))
    assert pred.tolist() == [0] and np.all(scores == -20)
    assert np.all(hidden == 255) and saturated == 32
    assert np.all(model(bias1=-1).infer(np.zeros((1, 784)))[2] == 0)


def test_worst_case_accumulator_overflow_is_rejected():
    q = model(bias1=np.iinfo(np.int32).max)
    q.w1[0, 0] = 1
    with pytest.raises(ValueError, match="accumulation"):
        q.verify()


def test_unsigned_white_is_not_negative():
    q = model(shift=0)
    q.w1[0, 0] = 1
    q.w2[1, 0] = 1
    pixels = np.zeros((1, 784), dtype=np.uint8)
    pixels[0, 0] = 255
    assert q.infer(pixels)[0].tolist() == [1]
