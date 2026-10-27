"""28x28 grayscale preprocessing with zero-filled, mass-centered translation."""

import math

import numpy as np
from PIL import Image

SIZE = 28
PREPROCESS_VERSION = "crop16-fit20-center13.5-v1"


def _round_away(value: float) -> int:
    return int(math.copysign(math.floor(abs(value) + 0.5), value))


def preprocess(image: Image.Image) -> Image.Image:
    pixels = np.asarray(image.convert("L"), dtype=np.uint8)
    ys, xs = np.nonzero(pixels >= 16)
    if len(xs) == 0:
        raise ValueError("Empty canvas: write a digit before sending")
    crop = Image.fromarray(pixels).crop(
        (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
    )
    scale = 20 / max(crop.size)
    size = tuple(max(1, _round_away(side * scale)) for side in crop.size)
    resized = crop.resize(size, Image.Resampling.BILINEAR)
    canvas = Image.new("L", (SIZE, SIZE))
    canvas.paste(resized, ((SIZE - size[0]) // 2, (SIZE - size[1]) // 2))
    values = np.asarray(canvas, dtype=np.float64)
    y_grid, x_grid = np.indices(values.shape)
    mass = values.sum()
    dx = _round_away(13.5 - float((values * x_grid).sum() / mass))
    dy = _round_away(13.5 - float((values * y_grid).sum() / mass))
    ys, xs = np.nonzero(values)
    dx = int(np.clip(dx, -int(xs.min()), SIZE - 1 - int(xs.max())))
    dy = int(np.clip(dy, -int(ys.min()), SIZE - 1 - int(ys.max())))
    shifted = Image.new("L", (SIZE, SIZE))
    shifted.paste(canvas, (dx, dy))
    return shifted


def image_bytes(image: Image.Image) -> bytes:
    if image.mode != "L" or image.size != (SIZE, SIZE):
        raise ValueError("Wire image must be grayscale 28x28")
    return image.tobytes()
