import components
from skin_tone import Swatch


def test_strip_escapes_names_and_carries_the_skin_dot():
    html = components.strip("Warm", [Swatch("<b>Peach</b>", "#FFDAB9")], "#B4826A")
    assert "&lt;b&gt;Peach&lt;/b&gt;" in html
    assert "<b>" not in html
    assert "background:#FFDAB9" in html
    assert "background:#B4826A" in html


def test_strip_keeps_the_recommended_order():
    html = components.strip("Dark", [Swatch("Navy Blue", "#000080"), Swatch("Burgundy", "#800020")], "#B4826A")
    assert html.index("Navy Blue") < html.index("Burgundy")
    assert html.count('class="sk-swatch"') == 2


def test_palette_has_one_labelled_strip_per_category_in_order():
    html = components.palette({"Warm": [Swatch("Peach", "#FFDAB9")], "Dark": [Swatch("Navy Blue", "#000080")]}, "#B4826A")
    assert html.count('class="sk-strip"') == 2
    assert html.index(">Warm<") < html.index(">Dark<")


def test_tone_ruler_marks_only_the_match_and_runs_light_to_deep(make_tones):
    tones = make_tones([("Deep", (60, 40, 30)), ("Light", (240, 220, 200)), ("Mid", (160, 110, 80))])
    html = components.tone_ruler(tones, "Mid")
    assert html.count("is-match") == 1
    assert html.index('title="Light"') < html.index('title="Mid"') < html.index('title="Deep"')


def test_tone_ruler_without_a_match_marks_nothing(make_tones):
    html = components.tone_ruler(make_tones([("Light", (240, 220, 200))]))
    assert "is-match" not in html


def test_readout_shows_both_colors_and_the_delta_e(make_tones):
    tone = make_tones([("Tan", (216, 165, 126))]).iloc[0]
    html = components.readout((210, 160, 120), tone, 3.04)
    assert "Tan" in html
    assert "#D2A078" in html and "#D8A57E" in html
    assert "ΔE 3.0" in html
    assert "is-close" in html


def test_readout_flags_a_poor_match(make_tones):
    tone = make_tones([("Tan", (216, 165, 126))]).iloc[0]
    assert "is-poor" in components.readout((20, 60, 200), tone, 31.4)
