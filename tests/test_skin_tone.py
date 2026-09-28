import numpy as np
import pytest

import skin_tone
from skin_tone import Swatch


def solid(rgb, height=40, width=40):
    return np.full((height, width, 3), rgb, np.uint8)


# parse_color_list

def test_parse_color_list_reads_names_and_hex_codes():
    assert skin_tone.parse_color_list("Peach (#FFDAB9), Navy Blue (#000080)") == [
        Swatch("Peach", "#FFDAB9"),
        Swatch("Navy Blue", "#000080"),
    ]


def test_parse_color_list_tolerates_stray_tabs_and_lowercase_hex():
    assert skin_tone.parse_color_list(" Warm Sand (#e4c49a)\t") == [Swatch("Warm Sand", "#E4C49A")]


@pytest.mark.parametrize("cell", ["Soft Copper (#D3A683", "Lemon (#FFFFACD)", "Peach", "(#FFDAB9)"])
def test_parse_color_list_rejects_malformed_entries(cell):
    with pytest.raises(ValueError, match=r"Name \(#RRGGBB\)"):
        skin_tone.parse_color_list(cell)


@pytest.mark.parametrize("cell", ["", "   ", float("nan"), None])
def test_parse_color_list_rejects_empty_cells(cell):
    with pytest.raises(ValueError, match="no colors"):
        skin_tone.parse_color_list(cell)


def test_swatch_exposes_its_rgb():
    assert Swatch("Peach", "#FFDAB9").rgb == (255, 218, 185)


# load_tones

def write_csv(tmp_path, frame):
    path = tmp_path / "tones.csv"
    frame.to_csv(path, index=False)
    return path


def test_load_tones_reads_a_valid_file(tmp_path, make_tones):
    tones = skin_tone.load_tones(write_csv(tmp_path, make_tones([("Tan", (216, 165, 126))])))
    assert list(tones["Skin Tone Name"]) == ["Tan"]


def test_load_tones_rejects_missing_columns(tmp_path, make_tones):
    frame = make_tones([("Tan", (216, 165, 126))]).drop(columns=["Blue"])
    with pytest.raises(ValueError, match="Blue"):
        skin_tone.load_tones(write_csv(tmp_path, frame))


def test_load_tones_names_the_tone_and_category_of_a_bad_color(tmp_path, make_tones):
    frame = make_tones([("Tan", (216, 165, 126))])
    frame.loc[0, skin_tone.category_column("Metallic")] = "Soft Copper (#D3A683"
    with pytest.raises(ValueError, match="Tan.*Metallic"):
        skin_tone.load_tones(write_csv(tmp_path, frame))


def test_load_tones_rejects_rgb_outside_0_to_255(tmp_path, make_tones):
    frame = make_tones([("Tan", (216, 165, 126))])
    frame.loc[0, "Blue"] = 300
    with pytest.raises(ValueError, match="0-255"):
        skin_tone.load_tones(write_csv(tmp_path, frame))


# rgb_to_lab

@pytest.mark.parametrize(
    "rgb, lab",
    [
        ((255, 0, 0), (53.24, 80.09, 67.20)),
        ((255, 255, 255), (100, 0, 0)),
        ((0, 0, 0), (0, 0, 0)),
        ((122, 122, 122), (51.2, 0, 0)),
    ],
)
def test_rgb_to_lab_matches_reference_values(rgb, lab):
    np.testing.assert_allclose(skin_tone.rgb_to_lab(rgb)[0], lab, atol=0.5)


def test_rgb_to_lab_converts_many_colors_at_once():
    assert skin_tone.rgb_to_lab([(0, 0, 0), (255, 255, 255), (255, 0, 0)]).shape == (3, 3)


# sample_color

def test_sample_color_of_size_one_is_that_pixel():
    image = np.arange(5 * 5 * 3, dtype=np.uint8).reshape(5, 5, 3)
    assert skin_tone.sample_color(image, 2, 3, 1).tolist() == image[3, 2].tolist()


def test_sample_color_ignores_highlights_and_stray_hairs():
    image = solid((180, 130, 100))
    image[18:21, 18:21] = 255  # specular highlight
    image[22, 10:30] = 20  # a hair across the patch
    assert skin_tone.sample_color(image, 20, 20, 15).tolist() == [180, 130, 100]


def test_sample_color_clips_the_patch_at_the_image_edge():
    assert skin_tone.sample_color(solid((10, 20, 30)), 0, 0, 15).tolist() == [10, 20, 30]


@pytest.mark.parametrize("x, y", [(-1, 0), (0, 40), (40, 0)])
def test_sample_color_rejects_points_outside_the_image(x, y):
    with pytest.raises(ValueError, match="outside"):
        skin_tone.sample_color(solid((1, 2, 3)), x, y, 5)


def test_sample_color_rejects_a_non_positive_size():
    with pytest.raises(ValueError, match="size"):
        skin_tone.sample_color(solid((1, 2, 3)), 5, 5, 0)


def test_patch_size_is_odd_and_scales_with_the_short_side():
    assert skin_tone.patch_size((3000, 4000, 3), 0.025) == 75
    assert skin_tone.patch_size((400, 600, 3), 0.025) == 11
    assert skin_tone.patch_size((50, 50, 3), 0.01) == 3


# closest_tone

def test_closest_tone_finds_an_exact_tone(make_tones):
    tones = make_tones([("Light", (241, 216, 177)), ("Deep", (75, 45, 45))])
    tone, delta_e = skin_tone.closest_tone((75, 45, 45), tones)
    assert tone["Skin Tone Name"] == "Deep"
    assert delta_e == pytest.approx(0, abs=1e-3)


def test_closest_tone_compares_colors_the_way_eyes_do(make_tones):
    # Grey 122 is nearer black in raw RGB, but it looks nearer white (L* 51 of 100).
    tones = make_tones([("Black", (0, 0, 0)), ("White", (255, 255, 255))])
    tone, _ = skin_tone.closest_tone((122, 122, 122), tones)
    assert tone["Skin Tone Name"] == "White"


JUST_NOTICEABLE_DELTA_E = 2.3


def noisy_photos(rgb, count=25, sigma=8, seed=7):
    """Flat skin patches with camera-like per-pixel noise."""
    rng = np.random.default_rng(seed)
    for _ in range(count):
        yield np.clip(rng.normal(rgb, sigma, (60, 60, 3)), 0, 255).astype(np.uint8)


def spread(samples):
    """Largest delta E of any sample from their mean."""
    lab = skin_tone.rgb_to_lab(np.array(samples))
    return float(np.linalg.norm(lab - lab.mean(axis=0), axis=1).max())


def test_patch_sample_holds_steady_where_a_single_pixel_wanders():
    photos = list(noisy_photos((180, 130, 100)))
    assert spread([skin_tone.sample_color(p, 30, 30, 15) for p in photos]) < JUST_NOTICEABLE_DELTA_E
    assert spread([p[30, 30] for p in photos]) > 10


@pytest.mark.parametrize("name", ["Caramel", "Honey Brown", "Porcelain", "Deep Ebony"])
def test_skin_near_a_reference_tone_always_matches_it(tones, name):
    rgb = tones.loc[tones[skin_tone.NAME_COLUMN] == name, skin_tone.RGB_COLUMNS].iloc[0].tolist()
    matches = {
        skin_tone.closest_tone(skin_tone.sample_color(p, 30, 30, 15), tones)[0][skin_tone.NAME_COLUMN]
        for p in noisy_photos(rgb)
    }
    assert matches == {name}


@pytest.mark.parametrize(
    "delta_e, quality",
    [(0, "close"), (5, "close"), (5.1, "approximate"), (12, "approximate"), (12.1, "poor")],
)
def test_match_quality_bands(delta_e, quality):
    assert skin_tone.match_quality(delta_e) == quality


def test_sort_by_lightness_runs_light_to_deep(make_tones):
    tones = make_tones([("Mid", (160, 110, 80)), ("Deep", (60, 40, 30)), ("Light", (240, 220, 200))])
    assert list(skin_tone.sort_by_lightness(tones)["Skin Tone Name"]) == ["Light", "Mid", "Deep"]


# recommendations / to_hex

def test_recommendations_cover_every_category_in_order(make_tones):
    tone = make_tones([("Tan", (216, 165, 126))]).iloc[0]
    recs = skin_tone.recommendations(tone)
    assert list(recs) == list(skin_tone.CATEGORIES)
    assert recs["Warm"] == [Swatch("Peach", "#FFDAB9"), Swatch("Navy Blue", "#000080")]


def test_to_hex_accepts_tuples_and_arrays():
    assert skin_tone.to_hex((255, 128, 0)) == "#FF8000"
    assert skin_tone.to_hex(np.array([1, 2, 3], np.uint8)) == "#010203"


# downscale / draw_marker / loupe

def test_downscale_fits_the_box_and_reports_the_scale():
    small, scale = skin_tone.downscale(np.zeros((1000, 2000, 3), np.uint8), 800, 1000)
    assert small.shape == (400, 800, 3)
    assert scale == pytest.approx(0.4)


def test_downscale_is_limited_by_height_for_portrait_photos():
    small, scale = skin_tone.downscale(np.zeros((4000, 3000, 3), np.uint8), 1100, 680)
    assert small.shape == (680, 510, 3)
    assert scale == pytest.approx(0.17)


def test_downscale_leaves_small_images_alone():
    image = np.zeros((100, 200, 3), np.uint8)
    small, scale = skin_tone.downscale(image, 800, 600)
    assert small is image and scale == 1.0


def test_draw_marker_returns_a_copy():
    image = solid((180, 130, 100))
    before = image.copy()
    skin_tone.draw_marker(image, 20, 20, 9)
    assert np.array_equal(image, before)


def test_draw_marker_outlines_the_sample_without_covering_it():
    marked = skin_tone.draw_marker(solid((180, 130, 100), 80, 80), 40, 40, 11)
    assert marked[35:46, 35:46].reshape(-1, 3).tolist() == [[180, 130, 100]] * 121
    colors = {tuple(p) for p in marked.reshape(-1, 3).tolist()}
    assert {(0, 0, 0), (255, 255, 255)} <= colors


def test_draw_marker_weight_thickens_the_strokes_for_large_photos():
    image = solid((180, 130, 100), 200, 200)

    def ink(marked):
        return int((marked != image).any(axis=2).sum())

    assert ink(skin_tone.draw_marker(image, 100, 100, 11, weight=2)) > 2 * ink(skin_tone.draw_marker(image, 100, 100, 11))


def test_marker_weight_grows_with_the_display_size():
    assert skin_tone.marker_weight((300, 400, 3)) == 1
    assert skin_tone.marker_weight((680, 907, 3)) == 2


def test_loupe_magnifies_around_the_point():
    image = np.zeros((50, 50, 3), np.uint8)
    image[25, 25] = (200, 100, 50)
    zoomed = skin_tone.loupe(image, 25, 25, 5, 120)
    assert zoomed.shape == (120, 120, 3)
    assert zoomed[60, 60].tolist() == [200, 100, 50]


def test_loupe_pads_past_the_image_edge():
    zoomed = skin_tone.loupe(solid((180, 130, 100), 30, 30), 0, 0, 5, 100)
    assert zoomed.shape == (100, 100, 3)
    assert zoomed[2, 2].tolist() == list(skin_tone.PAD_RGB)
