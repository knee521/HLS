import numpy as np
import pytest
from PIL import Image, ImageDraw

from common.preprocess import image_bytes, preprocess


def test_blank_is_rejected():
    with pytest.raises(ValueError):
        preprocess(Image.new("L", (28, 28)))


@pytest.mark.parametrize("offset", [(0, 0), (8, 7), (17, 2)])
def test_digit_is_centered_without_wraparound(offset):
    image = Image.new("L", (28, 28))
    x, y = offset
    ImageDraw.Draw(image).rectangle((x, y, x + 2, y + 12), fill=255)
    result = preprocess(image)
    array = np.asarray(result, dtype=np.float64)
    yy, xx = np.indices(array.shape)
    assert abs((xx * array).sum() / array.sum() - 13.5) <= 0.5
    assert abs((yy * array).sum() / array.sum() - 13.5) <= 0.5
    assert array[0].sum() == array[-1].sum() == 0
    assert len(image_bytes(result)) == 784
