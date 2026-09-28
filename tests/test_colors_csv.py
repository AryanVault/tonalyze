"""Data contract for colors.csv, so the cleanup can't quietly regress."""
from collections import defaultdict

import skin_tone

DARK_MAX_LIGHTNESS = 60  # CIELAB L*; "Dark" picks above this read as light


def all_lists(tones):
    for _, row in tones.iterrows():
        for category, swatches in skin_tone.recommendations(row).items():
            yield row["Skin Tone Name"], category, swatches


def test_tone_names_are_unique(tones):
    assert not tones["Skin Tone Name"].duplicated().any()


def test_hex_column_matches_the_rgb_columns(tones):
    for _, row in tones.iterrows():
        assert row["HEX Code"].upper() == skin_tone.to_hex(row[skin_tone.RGB_COLUMNS]), row["Skin Tone Name"]


def test_every_category_lists_five_distinct_colors(tones):
    for name, category, swatches in all_lists(tones):
        hexes = [s.hex for s in swatches]
        assert len(set(hexes)) == len(hexes) == 5, (name, category, hexes)


def test_each_color_has_one_name_and_each_name_one_color(tones):
    names_by_hex, hexes_by_name = defaultdict(set), defaultdict(set)
    for _, _, swatches in all_lists(tones):
        for s in swatches:
            names_by_hex[s.hex].add(s.name)
            hexes_by_name[s.name].add(s.hex)
    assert {h: n for h, n in names_by_hex.items() if len(n) > 1} == {}
    assert {n: h for n, h in hexes_by_name.items() if len(h) > 1} == {}


def test_dark_recommendations_are_actually_dark(tones):
    too_light = {
        (s.name, s.hex)
        for _, category, swatches in all_lists(tones)
        if category == "Dark"
        for s in swatches
        if skin_tone.rgb_to_lab(s.rgb)[0, 0] > DARK_MAX_LIGHTNESS
    }
    assert too_light == set()


def test_tones_span_very_fair_to_very_deep_skin(tones):
    lightness = skin_tone.rgb_to_lab(tones[skin_tone.RGB_COLUMNS].to_numpy())[:, 0]
    assert lightness.max() >= 90
    assert lightness.min() <= 20
