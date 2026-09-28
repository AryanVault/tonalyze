"""HTML fragments for the page. Names from the CSV are escaped; hex codes are pre-validated."""
from html import escape

import pandas as pd

import skin_tone
from skin_tone import Swatch

QUALITY_TEXT = {
    "close": "Close match",
    "approximate": "Approximate match",
    "poor": "Poor match. This spot may be in shadow, shiny, or not skin.",
}
DELTA_E_HINT = "Color difference in CIELAB (delta E). Below about 2 is hard to see."


def header() -> str:
    return (
        '<header class="sk-header">'
        '<h1 class="sk-title">Skin tone color match</h1>'
        '<p class="sk-lede">Upload a photo, then click an evenly lit patch of skin, such as a cheek '
        "or the forehead. Shadows, shine and makeup throw the reading off.</p>"
        "</header>"
    )


def label(text: str) -> str:
    return f'<div class="sk-label">{escape(text)}</div>'


def strip(category: str, swatches: list[Swatch], skin_hex: str) -> str:
    """One paint-sample strip; each color carries a dot of the sampled skin to judge the pairing."""
    items = "".join(
        '<li class="sk-strip-item">'
        f'<span class="sk-swatch" style="background:{s.hex}">'
        f'<span class="sk-swatch-skin" style="background:{skin_hex}"></span></span>'
        f'<span class="sk-strip-text"><span class="sk-swatch-name">{escape(s.name)}</span>'
        f'<span class="sk-swatch-hex">{s.hex}</span></span>'
        "</li>"
        for s in swatches
    )
    return f'<section class="sk-strip">{label(category)}<ol class="sk-strip-list">{items}</ol></section>'


def palette(recs: dict[str, list[Swatch]], skin_hex: str) -> str:
    strips = "".join(strip(category, swatches, skin_hex) for category, swatches in recs.items())
    return (
        '<div class="sk-palette"><h2 class="sk-section">Colors to wear</h2>'
        f'<div class="sk-strips">{strips}</div></div>'
    )


def tone_ruler(tones: pd.DataFrame, match_name: str | None = None) -> str:
    """Every reference tone, lightest to deepest, with the match marked."""
    cells = "".join(
        f'<span class="sk-ruler-cell{" is-match" if row[skin_tone.NAME_COLUMN] == match_name else ""}" '
        f'style="background:{skin_tone.to_hex(row[skin_tone.RGB_COLUMNS])}" '
        f'title="{escape(row[skin_tone.NAME_COLUMN])}"></span>'
        for _, row in skin_tone.sort_by_lightness(tones).iterrows()
    )
    caption = f"{len(tones)} reference tones"
    return (
        f'<div class="sk-ruler" role="img" aria-label="{caption}, lightest to deepest">'
        f'<div class="sk-ruler-track">{cells}</div>'
        f'<div class="sk-ruler-ends"><span>Lightest</span><span>{caption}</span><span>Deepest</span></div>'
        "</div>"
    )


def readout(sample_rgb, tone: pd.Series, delta_e: float) -> str:
    """Closest tone, how close it is, and the sample and tone side by side."""
    quality = skin_tone.match_quality(delta_e)
    sample_hex = skin_tone.to_hex(sample_rgb)
    tone_hex = skin_tone.to_hex(tone[skin_tone.RGB_COLUMNS])
    name = escape(tone[skin_tone.NAME_COLUMN])
    return (
        '<div class="sk-readout">'
        f'{label("Closest tone")}'
        f'<div class="sk-tone-name">{name}</div>'
        f'<div class="sk-quality is-{quality}">'
        f'<span class="sk-mono" title="{DELTA_E_HINT}">ΔE {delta_e:.1f}</span>'
        f"<span>{QUALITY_TEXT[quality]}</span></div>"
        '<div class="sk-compare">'
        f'<span style="background:{sample_hex}"></span><span style="background:{tone_hex}"></span></div>'
        '<div class="sk-compare-legend">'
        f'<span>Your sample<span class="sk-mono">{sample_hex}</span></span>'
        f'<span>{name}<span class="sk-mono">{tone_hex}</span></span></div>'
        "</div>"
    )
