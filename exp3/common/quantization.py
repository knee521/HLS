"""Bit-exact integer reference; int64 intermediates prove 32-bit safety separately."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


def round_symmetric(values: NDArray) -> NDArray[np.int64]:
    return (np.sign(values) * np.floor(np.abs(values) + 0.5)).astype(np.int64)


@dataclass(frozen=True)
class QuantizedMLP:
    w1: NDArray
    b1: NDArray
    w2: NDArray
    b2: NDArray
    fw1: int
    fw2: int
    fh: int

    @property
    def shift(self) -> int:
        return 8 + self.fw1 - self.fh

    def verify(self) -> dict:
        for name, values, shape in [
            ("w1", self.w1, (32, 784)),
            ("b1", self.b1, (32,)),
            ("w2", self.w2, (10, 32)),
            ("b2", self.b2, (10,)),
        ]:
            if values.shape != shape or not np.issubdtype(values.dtype, np.integer):
                raise ValueError(f"Invalid {name} shape/type")
        for weights in (self.w1, self.w2):
            if np.any(weights < -127) or np.any(weights > 127):
                raise ValueError("Weight outside symmetric int8 range")
        if not 0 <= self.shift <= 30:
            raise ValueError("Unsupported requantization shift")
        bounds = []
        for weights, bias in [(self.w1, self.b1), (self.w2, self.b2)]:
            bound = np.abs(bias.astype(np.int64)) + 255 * np.abs(weights.astype(np.int64)).sum(1)
            if np.any(bound > np.iinfo(np.int32).max):
                raise ValueError("32-bit accumulation bound exceeded")
            bounds.append(bound.tolist())
        return {
            "layer1_bounds": bounds[0],
            "layer2_bounds": bounds[1],
            "int32_max": int(np.iinfo(np.int32).max),
            "safe_for_all_uint8_inputs": True,
        }

    def infer(self, pixels: NDArray) -> tuple[NDArray, NDArray, NDArray, int]:
        pixels = np.asarray(pixels)
        if pixels.ndim != 2 or pixels.shape[1] != 784:
            raise ValueError("Expected N x 784 pixels")
        if np.any(pixels < 0) or np.any(pixels > 255):
            raise ValueError("Pixel outside uint8 range")
        a1 = pixels.astype(np.int64) @ self.w1.astype(np.int64).T + self.b1
        positive = np.maximum(a1, 0)
        if self.shift:
            positive = (positive + (1 << (self.shift - 1))) >> self.shift
        saturated = int((positive > 255).sum())
        hidden = np.clip(positive, 0, 255).astype(np.int64)
        scores = hidden @ self.w2.astype(np.int64).T + self.b2
        return scores.argmax(1), scores, hidden, saturated
