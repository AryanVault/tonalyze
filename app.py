"""Streamlit UI: click a patch of skin in a photo, get the nearest tone and colors to wear."""
import io
from pathlib import Path

import numpy as np
import streamlit as st
from PIL import Image, ImageOps, UnidentifiedImageError
from streamlit_image_coordinates import streamlit_image_coordinates

import components
import skin_tone

HERE = Path(__file__).parent
CSV_PATH = HERE / "colors.csv"
STYLE_PATH = HERE / "style.css"

DISPLAY_MAX_WIDTH = 1100
DISPLAY_MAX_HEIGHT = 680
LOUPE_PX = 160
SAMPLE_AREAS = {"Fine": 0.01, "Medium": 0.025, "Wide": 0.05}  # share of the photo's short side
DEFAULT_SAMPLE_AREA = "Medium"
UPLOAD_TYPES = ["jpg", "jpeg", "png", "webp"]
FAVICON_BANDS = ((243, 231, 219), (160, 126, 86), (58, 49, 42))  # Monk scale 2, 6 and 9
SAMPLE_PATH = HERE / "samples" / "sample.jpg"  # synthetic; regenerate with samples/make_sample.py
PRIVACY_NOTE = "Photos are processed in memory and never saved to disk."
SAMPLE_NOTE = "Showing a sample photo: three skin tones under side light. Upload your own above."


@st.cache_data(show_spinner=False)
def load_tones():
    return skin_tone.load_tones(CSV_PATH)


GREYSCALE_MODES = {"1", "L", "LA", "La", "I", "I;16", "I;16B", "I;16L", "I;16N", "F"}


class NotAColorPhoto(ValueError):
    """The photo has no color to read a skin tone from."""


def read_photo(data: bytes) -> np.ndarray:
    """Decode an upload to upright 8-bit RGB.

    Black-and-white photos are refused rather than guessed at (16-bit grey would
    otherwise clip to white), and transparent areas become neutral grey so colors
    hidden under them can't be sampled.
    """
    with Image.open(io.BytesIO(data)) as img:
        if img.mode in GREYSCALE_MODES:
            raise NotAColorPhoto(img.mode)
        upright = ImageOps.exif_transpose(img)
        if upright.has_transparency_data:
            backdrop = Image.new("RGBA", upright.size, (*skin_tone.PAD_RGB, 255))
            upright = Image.alpha_composite(backdrop, upright.convert("RGBA"))
        photo = np.array(upright.convert("RGB"))
    if skin_tone.is_grayscale(photo):
        raise NotAColorPhoto("grey RGB")
    return photo


@st.cache_resource(max_entries=2, show_spinner=False)
def decode_photo(data: bytes) -> tuple[np.ndarray, np.ndarray, float]:
    """Full-resolution RGB, a display copy, and the scale between them.

    Both arrays are read-only: the cache hands the same objects to every rerun.
    """
    full = read_photo(data)
    display, scale = skin_tone.downscale(full, DISPLAY_MAX_WIDTH, DISPLAY_MAX_HEIGHT)
    full.setflags(write=False)
    display.setflags(write=False)
    return full, display, scale


def point_from_click(click, shape) -> tuple[int, int]:
    """Map a click on the displayed photo to full-resolution pixels; the centre before any click."""
    height, width = shape[:2]
    if not click or not click.get("width") or not click.get("height"):
        return width // 2, height // 2
    x = int(click["x"] * width / click["width"])
    y = int(click["y"] * height / click["height"])
    return min(max(x, 0), width - 1), min(max(y, 0), height - 1)


def photo_width_share(shape) -> float:
    """Share of the photo column to fill, so a portrait photo ends up no taller than it is wide."""
    height, width = shape[:2]
    return min(1.0, width / height)


def show_photo(display: np.ndarray, key: str, marked: np.ndarray) -> None:
    # The component's own "auto" width never shrinks a wide photo, so fill the column instead
    # and narrow the column for portrait photos.
    share = photo_width_share(display.shape)
    target = st.columns([share, 1 - share])[0] if share < 1 else st.container()
    with target:
        streamlit_image_coordinates(
            marked, key=key, use_column_width="always", image_format="JPEG", jpeg_quality=90, cursor="crosshair"
        )


def show_analysis(full: np.ndarray, display: np.ndarray, scale: float, tones, key: str) -> None:
    photo_col, result_col = st.columns([7, 5], gap="large")

    with photo_col:
        area = st.segmented_control(
            "Sample area", list(SAMPLE_AREAS), default=DEFAULT_SAMPLE_AREA, key="sample_area"
        ) or DEFAULT_SAMPLE_AREA
        size = skin_tone.patch_size(full.shape, SAMPLE_AREAS[area])
        # The click lands in session state before this rerun, so the marker is drawn where it is.
        x, y = point_from_click(st.session_state.get(key), full.shape)
        marked = skin_tone.draw_marker(
            display, round(x * scale), round(y * scale), max(1, round(size * scale)),
            weight=skin_tone.marker_weight(display.shape),
        )
        show_photo(display, key, marked)
        st.caption("Click the photo to move the sample.")

    sample = skin_tone.sample_color(full, x, y, size)
    tone, delta_e = skin_tone.closest_tone(sample, tones)

    with result_col:
        loupe_col, readout_col = st.columns([2, 3], gap="medium")
        with loupe_col:
            st.html(components.label("Sample"))
            st.image(skin_tone.loupe(full, x, y, size, LOUPE_PX * 2), width=LOUPE_PX)
        with readout_col:
            st.html(components.readout(sample, tone, delta_e))
        st.html(components.tone_ruler(tones, tone[skin_tone.NAME_COLUMN]))

    st.html(components.palette(skin_tone.recommendations(tone), skin_tone.to_hex(sample)))


def use_sample() -> None:
    st.session_state["show_sample"] = True


def favicon() -> Image.Image:
    """Three bands, light to deep, for the browser tab."""
    band = 16
    icon = Image.new("RGB", (band * 3, band * 3))
    for i, rgb in enumerate(FAVICON_BANDS):
        icon.paste(rgb, (0, i * band, band * 3, (i + 1) * band))
    return icon


def main() -> None:
    st.set_page_config(page_title="Skin Tone Color Match", page_icon=favicon(), layout="wide")
    st.markdown(f"<style>{STYLE_PATH.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)
    st.html(components.header())

    try:
        tones = load_tones()
    except (OSError, ValueError) as err:
        st.error(f"Couldn't load the skin tone data: {err}")
        return

    photo = st.file_uploader("Photo", type=UPLOAD_TYPES, label_visibility="collapsed")
    st.caption(PRIVACY_NOTE)
    # An upload always wins; the sample is for visitors who won't upload a photo of themselves.
    if photo is not None:
        data, key = photo.getvalue(), f"photo-{photo.file_id}"
    elif st.session_state.get("show_sample"):
        st.caption(SAMPLE_NOTE)
        data, key = SAMPLE_PATH.read_bytes(), "photo-sample"
    else:
        st.button("Try a sample photo", key="use_sample", on_click=use_sample)
        st.html(components.tone_ruler(tones))
        return

    try:
        full, display, scale = decode_photo(data)
    except NotAColorPhoto:
        st.error("This looks like a black-and-white photo. Skin tone needs a color photo.")
        return
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        st.error("That file couldn't be opened as an image. Try a JPG, PNG or WebP.")
        return
    show_analysis(full, display, scale, tones, key=key)


if __name__ == "__main__":
    main()
