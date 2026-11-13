"""Decoding real uploads: every accepted format should reach the matcher as honest RGB."""
import io

import numpy as np
import pytest
from PIL import Image, UnidentifiedImageError

import app
import skin_tone

SKIN = (180, 130, 100)


def encode(img: Image.Image, fmt: str, **options) -> bytes:
    buf = io.BytesIO()
    img.save(buf, fmt, **options)
    return buf.getvalue()


def test_reads_a_color_jpeg():
    photo = app.read_photo(encode(Image.new("RGB", (40, 30), SKIN), "JPEG", quality=95))
    assert photo.shape == (30, 40, 3)
    assert np.abs(photo[15, 20].astype(int) - SKIN).max() <= 3


def test_turns_a_phone_photo_upright_from_its_exif_orientation():
    exif = Image.Exif()
    exif[0x0112] = 6  # rotated 90 degrees, as phones save portrait shots
    photo = app.read_photo(encode(Image.new("RGB", (40, 30), SKIN), "JPEG", exif=exif))
    assert photo.shape == (40, 30, 3)


@pytest.mark.parametrize("mode, fmt", [("CMYK", "JPEG"), ("P", "PNG"), ("RGB", "WEBP")])
def test_reads_other_color_formats(mode, fmt):
    img = Image.new("RGB", (20, 20), SKIN).convert(mode)
    assert app.read_photo(encode(img, fmt)).shape == (20, 20, 3)


def test_flattens_transparency_onto_neutral_grey_instead_of_leaking_hidden_color():
    img = Image.new("RGBA", (20, 20), (*SKIN, 255))
    img.putpixel((0, 0), (255, 0, 0, 0))  # invisible red
    photo = app.read_photo(encode(img, "PNG"))
    assert photo[0, 0].tolist() == list(skin_tone.PAD_RGB)
    assert photo[10, 10].tolist() == list(SKIN)


@pytest.mark.parametrize(
    "img",
    [
        Image.new("L", (20, 20), 128),
        Image.fromarray(np.full((20, 20), 40000, np.uint16)),  # Pillow infers I;16
        Image.new("RGB", (20, 20), (128, 128, 128)),  # black-and-white saved as RGB
    ],
    ids=["8-bit grey", "16-bit grey", "grey RGB"],
)
def test_refuses_black_and_white_photos(img):
    with pytest.raises(app.NotAColorPhoto):
        app.read_photo(encode(img, "PNG"))


def test_rejects_bytes_that_are_not_an_image():
    with pytest.raises(UnidentifiedImageError):
        app.read_photo(b"not an image")


def test_is_grayscale_ignores_a_little_color_noise():
    rng = np.random.default_rng(3)
    grey = np.clip(128 + rng.normal(0, 1, (40, 40, 3)), 0, 255).astype(np.uint8)
    assert skin_tone.is_grayscale(grey)
    assert not skin_tone.is_grayscale(np.full((40, 40, 3), SKIN, np.uint8))
