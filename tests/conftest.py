from pathlib import Path

import pandas as pd
import pytest

import skin_tone

CSV_PATH = Path(__file__).resolve().parents[1] / "colors.csv"


@pytest.fixture(scope="session")
def tones():
    """The real tone table shipped with the app."""
    return skin_tone.load_tones(CSV_PATH)


@pytest.fixture
def make_tones():
    """Build a small tone table from (name, (r, g, b)) pairs."""

    def build(rows, recommendation="Peach (#FFDAB9), Navy Blue (#000080)"):
        return pd.DataFrame(
            [
                {
                    "Skin Tone Name": name,
                    "HEX Code": "#{:02X}{:02X}{:02X}".format(*rgb),
                    "Red": rgb[0],
                    "Green": rgb[1],
                    "Blue": rgb[2],
                    **{skin_tone.category_column(c): recommendation for c in skin_tone.CATEGORIES},
                }
                for name, rgb in rows
            ]
        )

    return build
