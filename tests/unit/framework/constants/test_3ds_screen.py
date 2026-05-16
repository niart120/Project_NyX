import pytest

from nyxpy.framework.core.constants import (
    THREEDS_BOTTOM_SCREEN,
    THREEDS_CAPTURE_SIZE,
    THREEDS_FULL_SCREEN,
    THREEDS_HD_BOTTOM_SCREEN,
    THREEDS_HD_CAPTURE_SIZE,
    THREEDS_HD_CONTENT,
    THREEDS_HD_TOP_SCREEN,
    THREEDS_TOP_SCREEN,
    ScreenPoint,
    ScreenRect,
    ScreenSize,
    TouchPoint,
    aspect_fit_rect,
    cropped_hd_point_to_3ds_touch,
    hd_capture_point_to_3ds_touch,
    normalized_point_to_3ds_touch,
    preview_point_to_3ds_touch,
    preview_touch_rect,
    touch_point_to_3ds_hd_capture,
    try_hd_capture_point_to_3ds_touch,
    validate_3ds_touch_point,
)


def test_3ds_screen_constants_define_normalized_rects() -> None:
    assert THREEDS_CAPTURE_SIZE == ScreenSize(400, 480)
    assert THREEDS_TOP_SCREEN == ScreenRect(0, 0, 400, 240)
    assert THREEDS_BOTTOM_SCREEN == ScreenRect(40, 240, 320, 240)
    assert THREEDS_FULL_SCREEN == ScreenRect(0, 0, 400, 480)


def test_3ds_screen_constants_define_hd_capture_rects() -> None:
    assert THREEDS_HD_CAPTURE_SIZE == ScreenSize(1280, 720)
    assert THREEDS_HD_CONTENT == ScreenRect(340, 0, 600, 720)
    assert THREEDS_HD_TOP_SCREEN == ScreenRect(340, 0, 600, 360)
    assert THREEDS_HD_BOTTOM_SCREEN == ScreenRect(400, 360, 480, 360)


def test_normalized_point_to_3ds_touch_offsets_lower_screen() -> None:
    assert normalized_point_to_3ds_touch(ScreenPoint(40, 240)) == TouchPoint(0, 0)
    assert normalized_point_to_3ds_touch(ScreenPoint(359, 479)) == TouchPoint(319, 239)


def test_hd_capture_point_to_3ds_touch_offsets_aspect_box() -> None:
    assert hd_capture_point_to_3ds_touch(ScreenPoint(400, 360)) == TouchPoint(0, 0)
    assert hd_capture_point_to_3ds_touch(ScreenPoint(879, 719)) == TouchPoint(319, 239)
    assert hd_capture_point_to_3ds_touch(
        touch_point_to_3ds_hd_capture(TouchPoint(319, 239))
    ) == TouchPoint(319, 239)


def test_hd_capture_point_to_3ds_touch_rejects_outer_and_inner_pillarbox() -> None:
    for point in [
        ScreenPoint(339, 360),
        ScreenPoint(399, 360),
        ScreenPoint(880, 360),
        ScreenPoint(940, 360),
    ]:
        with pytest.raises(ValueError):
            hd_capture_point_to_3ds_touch(point)
        assert try_hd_capture_point_to_3ds_touch(point) is None


def test_cropped_hd_point_to_3ds_touch_uses_crop_origin() -> None:
    crop = ScreenRect(400, 360, 480, 360)

    assert cropped_hd_point_to_3ds_touch(ScreenPoint(0, 0), crop) == TouchPoint(0, 0)
    assert cropped_hd_point_to_3ds_touch(ScreenPoint(479, 359), crop) == TouchPoint(319, 239)


def test_aspect_fit_rect_places_3ds_screen_in_hd_box() -> None:
    assert aspect_fit_rect(ScreenSize(400, 480), ScreenSize(1280, 720)) == ScreenRect(
        340, 0, 600, 720
    )


@pytest.mark.parametrize(
    ("preview_size", "expected"),
    [
        (ScreenSize(640, 360), ScreenRect(200, 180, 240, 180)),
        (ScreenSize(1280, 720), ScreenRect(400, 360, 480, 360)),
        (ScreenSize(1600, 900), ScreenRect(500, 450, 600, 450)),
        (ScreenSize(2560, 1440), ScreenRect(800, 720, 960, 720)),
    ],
)
def test_preview_touch_rect_scales_by_window_size_preset(
    preview_size: ScreenSize,
    expected: ScreenRect,
) -> None:
    assert preview_touch_rect(preview_size) == expected


@pytest.mark.parametrize(
    ("preview_size", "left_top", "right_bottom"),
    [
        (ScreenSize(640, 360), ScreenPoint(200, 180), ScreenPoint(439, 359)),
        (ScreenSize(1280, 720), ScreenPoint(400, 360), ScreenPoint(879, 719)),
        (ScreenSize(1600, 900), ScreenPoint(500, 450), ScreenPoint(1099, 899)),
        (ScreenSize(2560, 1440), ScreenPoint(800, 720), ScreenPoint(1759, 1439)),
    ],
)
def test_preview_point_to_3ds_touch_preserves_edges(
    preview_size: ScreenSize,
    left_top: ScreenPoint,
    right_bottom: ScreenPoint,
) -> None:
    assert preview_point_to_3ds_touch(left_top, preview_size=preview_size) == TouchPoint(0, 0)
    assert preview_point_to_3ds_touch(right_bottom, preview_size=preview_size) == TouchPoint(
        319, 239
    )


def test_touch_point_validation_rejects_pixel_index_out_of_range() -> None:
    with pytest.raises(ValueError, match="0..319"):
        validate_3ds_touch_point(TouchPoint(320, 0))
    with pytest.raises(ValueError, match="0..239"):
        validate_3ds_touch_point(TouchPoint(0, 240))
