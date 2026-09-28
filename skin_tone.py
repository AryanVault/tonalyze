"""Skin tone matching: sample a photo, find the nearest reference tone, read its color picks."""
import re
from dataclasses import dataclass

import cv2
import numpy as np
import pandas as pd

CATEGORIES = ("Warm", "Bright", "Dark", "Pastel", "Metallic")
RGB_COLUMNS = ["Red", "Green", "Blue"]
NAME_COLUMN = "Skin Tone Name"

CLOSE_MATCH_DELTA_E = 5.0  # CIE76; ~2.3 is the smallest difference most people notice
APPROXIMATE_MATCH_DELTA_E = 12.0

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
PAD_RGB = (128, 128, 128)  # neutral grey past the photo's edge in the loupe
MARKER_MIN_HALF = 6
MARKER_GAP = 2
MARKER_TICK = 8
MARKER_WEIGHT_STEP = 340  # px of the display's short side per unit of marker weight
LOUPE_CONTEXT = 4  # the loupe shows this many sample-widths around the sample
LOUPE_MIN_SIDE = 15
GREY_MAX_SPREAD = 6  # a pixel whose channels differ by at most this much counts as grey
GREY_SHARE = 0.99  # a photo this grey overall has no skin color to read

_ENTRY = re.compile(r"(?P<name>[^()]+?)\s*\((?P<hex>#[0-9A-Fa-f]{6})\)")


@dataclass(frozen=True)
class Swatch:
    name: str
    hex: str

    @property
    def rgb(self) -> tuple[int, int, int]:
        return tuple(int(self.hex[i:i + 2], 16) for i in (1, 3, 5))


def category_column(category: str) -> str:
    return f"Recommended Colors ({category})"


def parse_color_list(cell) -> list[Swatch]:
    """Parse 'Peach (#FFDAB9), Coral (#FF7F50)' into swatches.

    Raises ValueError on anything that isn't 'Name (#RRGGBB)', so a typo in the
    CSV fails loudly instead of silently dropping a swatch.
    """
    if not isinstance(cell, str) or not cell.strip():
        raise ValueError("no colors listed")
    swatches = []
    for entry in cell.split(","):
        match = _ENTRY.fullmatch(entry.strip())
        if match is None:
            raise ValueError(f"bad color entry {entry.strip()!r}, expected 'Name (#RRGGBB)'")
        swatches.append(Swatch(match["name"], match["hex"].upper()))
    return swatches


def load_tones(csv_path) -> pd.DataFrame:
    """Load the tone table, checking the columns, RGB values and every color entry."""
    tones = pd.read_csv(csv_path)
    required = [NAME_COLUMN, *RGB_COLUMNS, *(category_column(c) for c in CATEGORIES)]
    missing = [c for c in required if c not in tones.columns]
    if missing:
        raise ValueError(f"{csv_path} is missing columns: {', '.join(missing)}")

    rgb = tones[RGB_COLUMNS].apply(pd.to_numeric, errors="coerce")
    if rgb.isna().any().any() or ((rgb < 0) | (rgb > 255)).any().any():
        raise ValueError(f"{csv_path}: Red, Green and Blue must be whole numbers 0-255")
    tones[RGB_COLUMNS] = rgb.astype(int)

    for _, row in tones.iterrows():
        for category in CATEGORIES:
            try:
                parse_color_list(row[category_column(category)])
            except ValueError as err:
                raise ValueError(f"{row[NAME_COLUMN]} / {category}: {err}") from err
    return tones


def to_hex(rgb) -> str:
    return "#{:02X}{:02X}{:02X}".format(*(int(c) for c in rgb))


def rgb_to_lab(rgb) -> np.ndarray:
    """sRGB (0-255) to CIELAB (D65), as an (N, 3) array. Accepts one color or many."""
    pixels = np.asarray(rgb, dtype=np.float32).reshape(-1, 1, 3) / 255
    return cv2.cvtColor(pixels, cv2.COLOR_RGB2LAB).reshape(-1, 3)


def is_grayscale(image: np.ndarray) -> bool:
    """True for a black-and-white photo, even one saved as RGB with a little color noise."""
    pixels = image[::4, ::4].reshape(-1, 3).astype(np.int16)  # every 16th pixel is plenty
    spread = pixels.max(axis=1) - pixels.min(axis=1)
    return float((spread <= GREY_MAX_SPREAD).mean()) >= GREY_SHARE


def patch_size(shape, fraction: float, minimum: int = 3) -> int:
    """Odd side length of a sample covering `fraction` of the image's short side."""
    return max(minimum, round(min(shape[:2]) * fraction)) | 1


def sample_color(image: np.ndarray, x: int, y: int, size: int) -> np.ndarray:
    """Median RGB of the size x size square centred on (x, y), clipped to the image.

    The median shrugs off the highlight, shadow or stray hair that makes a single
    pixel unreliable.
    """
    height, width = image.shape[:2]
    if not (0 <= x < width and 0 <= y < height):
        raise ValueError(f"point ({x}, {y}) is outside the {width}x{height} image")
    if size < 1:
        raise ValueError(f"sample size must be at least 1, got {size}")
    half = size // 2
    patch = image[max(y - half, 0):y + half + 1, max(x - half, 0):x + half + 1]
    return np.median(patch.reshape(-1, 3), axis=0).round().astype(np.uint8)


def closest_tone(rgb, tones: pd.DataFrame) -> tuple[pd.Series, float]:
    """Nearest tone by CIE76 delta E (straight-line distance in CIELAB)."""
    distances = np.linalg.norm(rgb_to_lab(tones[RGB_COLUMNS].to_numpy()) - rgb_to_lab(rgb), axis=1)
    best = int(np.argmin(distances))
    return tones.iloc[best], float(distances[best])


def match_quality(delta_e: float) -> str:
    if delta_e <= CLOSE_MATCH_DELTA_E:
        return "close"
    if delta_e <= APPROXIMATE_MATCH_DELTA_E:
        return "approximate"
    return "poor"


def sort_by_lightness(tones: pd.DataFrame) -> pd.DataFrame:
    """Tones from lightest to deepest by CIELAB L*."""
    lightness = rgb_to_lab(tones[RGB_COLUMNS].to_numpy())[:, 0]
    return tones.iloc[np.argsort(-lightness, kind="stable")]


def recommendations(tone: pd.Series) -> dict[str, list[Swatch]]:
    return {c: parse_color_list(tone[category_column(c)]) for c in CATEGORIES}


def downscale(image: np.ndarray, max_width: int, max_height: int) -> tuple[np.ndarray, float]:
    """Shrink to fit max_width x max_height; returns the image and the scale applied."""
    height, width = image.shape[:2]
    scale = min(1.0, max_width / width, max_height / height)
    if scale == 1.0:
        return image, 1.0
    size = (max(1, round(width * scale)), max(1, round(height * scale)))
    return cv2.resize(image, size, interpolation=cv2.INTER_AREA), scale


def _outline(image: np.ndarray, top_left, bottom_right, ticks=(), weight: int = 1) -> None:
    """Black-under-white strokes, legible on light and deep skin alike. Draws in place."""
    for color, thickness in ((BLACK, 3 * weight), (WHITE, weight)):
        cv2.rectangle(image, top_left, bottom_right, color, thickness)
        for start, end in ticks:
            cv2.line(image, start, end, color, thickness)


def marker_weight(shape) -> int:
    """Stroke multiplier so the reticle survives being shrunk onto a phone screen."""
    return max(1, round(min(shape[:2]) / MARKER_WEIGHT_STEP))


def draw_marker(image: np.ndarray, x: int, y: int, size: int, weight: int = 1) -> np.ndarray:
    """Copy of image with a reticle around the size x size sample at (x, y).

    The outline sits outside the sampled pixels so they stay visible.
    """
    marked = image.copy()
    r = max(size // 2, MARKER_MIN_HALF * weight) + MARKER_GAP * weight
    tick = MARKER_TICK * weight
    ticks = (
        ((x - r - tick, y), (x - r, y)),
        ((x + r, y), (x + r + tick, y)),
        ((x, y - r - tick), (x, y - r)),
        ((x, y + r), (x, y + r + tick)),
    )
    _outline(marked, (x - r, y - r), (x + r, y + r), ticks, weight)
    return marked


def loupe(image: np.ndarray, x: int, y: int, size: int, out_px: int) -> np.ndarray:
    """Magnified square around (x, y) with the sampled area outlined; grey past the edges."""
    side = max(size * LOUPE_CONTEXT, LOUPE_MIN_SIDE) | 1
    half = side // 2
    height, width = image.shape[:2]
    x0, y0 = x - half, y - half
    x1, y1 = x0 + side, y0 + side
    crop = image[max(y0, 0):min(y1, height), max(x0, 0):min(x1, width)]
    crop = cv2.copyMakeBorder(
        np.ascontiguousarray(crop),
        max(-y0, 0), max(y1 - height, 0), max(-x0, 0), max(x1 - width, 0),
        cv2.BORDER_CONSTANT, value=PAD_RGB,
    )
    zoomed = cv2.resize(crop, (out_px, out_px), interpolation=cv2.INTER_NEAREST)
    k = out_px / side
    start = round((half - size // 2) * k)
    end = round((half + size // 2 + 1) * k) - 1
    _outline(zoomed, (start, start), (end, end))
    return zoomed
