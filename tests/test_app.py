from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import app

APP_PATH = str(Path(__file__).resolve().parents[1] / "app.py")
APP_TIMEOUT_S = 30  # the first run imports OpenCV and pandas from cold


def html_blocks(at):
    return "".join(el.proto.body for el in at.get("html"))


def test_app_starts_on_the_upload_screen_with_the_reference_tones():
    at = AppTest.from_file(APP_PATH, default_timeout=APP_TIMEOUT_S).run()
    assert not at.exception
    page = html_blocks(at)
    assert "Skin tone color match" in page
    assert "sk-ruler" in page
    assert "is-match" not in page


def test_upload_screen_says_photos_are_not_saved():
    at = AppTest.from_file(APP_PATH, default_timeout=APP_TIMEOUT_S).run()
    assert app.PRIVACY_NOTE in [c.value for c in at.caption]


def test_the_sample_photo_ships_with_the_app_and_is_in_color():
    assert app.read_photo(app.SAMPLE_PATH.read_bytes()).shape == (1200, 1600, 3)


def test_sample_button_shows_results_without_an_upload():
    at = AppTest.from_file(APP_PATH, default_timeout=APP_TIMEOUT_S).run()
    at.button(key="use_sample").click().run()
    assert not at.exception
    assert "Closest tone" in html_blocks(at)
    assert any("sample photo" in c.value.lower() for c in at.caption)


def test_results_render_for_a_photo():
    def script():
        import numpy as np

        import app
        import skin_tone

        full = np.full((300, 400, 3), (180, 130, 100), np.uint8)
        full.setflags(write=False)
        display, scale = skin_tone.downscale(full, app.DISPLAY_MAX_WIDTH, app.DISPLAY_MAX_HEIGHT)
        app.show_analysis(full, display, scale, app.load_tones(), key="photo-test")

    at = AppTest.from_function(script, default_timeout=APP_TIMEOUT_S).run()
    assert not at.exception
    page = html_blocks(at)
    assert "Closest tone" in page
    assert page.count('class="sk-swatch"') == 25
    assert "is-match" in page


@pytest.mark.parametrize(
    "shape, share",
    [((1200, 1600, 3), 1.0), ((1000, 1000, 3), 1.0), ((4000, 3000, 3), 0.75), ((1920, 1080, 3), 0.5625)],
)
def test_portrait_photos_get_a_narrower_column_so_they_are_no_taller_than_wide(shape, share):
    assert app.photo_width_share(shape) == pytest.approx(share)


@pytest.mark.parametrize(
    "click, point",
    [
        (None, (200, 150)),
        ({"x": 0, "y": 0, "width": 200, "height": 150}, (0, 0)),
        ({"x": 100, "y": 75, "width": 200, "height": 150}, (200, 150)),
        ({"x": 200, "y": 150, "width": 200, "height": 150}, (399, 299)),
        ({"x": 5, "y": 5, "width": 0, "height": 0}, (200, 150)),
    ],
)
def test_point_from_click_maps_display_pixels_to_the_full_photo(click, point):
    assert app.point_from_click(click, (300, 400, 3)) == point
