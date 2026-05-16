from pathlib import Path

import cv2
import numpy as np
import pytest

from macros.nsmb_sort_or_splode.config import NsmbSortOrSplodeConfig, TouchRect
from macros.nsmb_sort_or_splode.macro import NsmbSortOrSplodeMacro
from macros.nsmb_sort_or_splode.recognizer import (
    BombColor,
    DetectedBomb,
    build_drag_path,
    classify_bombs,
    find_bombs,
    measure_color_features,
    paint_ignored_rects,
    touch_rect_to_cropped_hd_rect,
)
from nyxpy.framework.core.constants import THREEDS_HD_BOTTOM_SCREEN, TouchPoint

ROOT = Path(__file__).resolve().parents[3]


class FakeCommand:
    def __init__(
        self,
        frame: np.ndarray | list[np.ndarray],
        images: dict[str, np.ndarray],
    ) -> None:
        self.frames = [frame] if isinstance(frame, np.ndarray) else frame
        self.images = images
        self.events: list[tuple[str, object]] = []
        self.saved_images: dict[str, np.ndarray] = {}
        self.capture_index = 0

    def load_img(self, filename, grayscale: bool = False):
        image = self.images[str(filename).replace("\\", "/")].copy()
        if grayscale and image.ndim == 3:
            return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        return image

    def capture(self, crop_region=None, grayscale: bool = False):
        frame = self.frames[min(self.capture_index, len(self.frames) - 1)].copy()
        self.capture_index += 1
        if crop_region is not None:
            x, y, w, h = crop_region
            frame = frame[y : y + h, x : x + w]
        if grayscale:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return frame

    def touch_down(self, x: int, y: int) -> None:
        self.events.append(("touch_down", (x, y)))

    def touch_up(self) -> None:
        self.events.append(("touch_up", None))

    def wait(self, seconds: float) -> None:
        self.events.append(("wait", seconds))

    def notify(self, text: str, img=None) -> None:
        self.events.append(("notify", text))

    def save_img(self, filename, image) -> None:
        self.saved_images[str(filename)] = image.copy()

    def log(self, *values, sep: str = " ", end: str = "\n", level: str = "DEBUG") -> None:
        message = sep.join(map(str, values)) + end.rstrip("\n")
        self.events.append(("log", (level, message)))


def _load_template(name: str) -> np.ndarray:
    path = ROOT / "resources" / "nsmb_sort_or_splode" / "assets" / "templates" / name
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    assert image is not None
    return image


def _template_images() -> dict[str, np.ndarray]:
    return {
        "templates/red_bob_omb.png": _load_template("red_bob_omb.png"),
        "templates/black_bob_omb.png": _load_template("black_bob_omb.png"),
    }


def test_config_accepts_default_settings() -> None:
    cfg = NsmbSortOrSplodeConfig.from_args({})

    assert cfg.red_goal_touch == TouchPoint(24, 122)
    assert cfg.black_goal_touch == TouchPoint(296, 122)
    assert cfg.mask_fill_bgr == (0, 255, 0)
    assert cfg.notify_on_finish is False
    assert cfg.template_score_margin == 0.08
    assert cfg.red_min_ratio == 0.20
    assert cfg.black_min_dark_ratio == 0.35
    assert cfg.black_max_red_ratio == 0.10
    assert cfg.verify_before_goal is True
    assert cfg.red_staging_touch == TouchPoint(64, 200)
    assert cfg.black_staging_touch == TouchPoint(256, 200)
    assert cfg.staging_wait_seconds == 0.05
    assert cfg.staging_verification_radius == 24


def test_config_rejects_invalid_touch_goal() -> None:
    with pytest.raises(ValueError, match="Touch X"):
        NsmbSortOrSplodeConfig.from_args({"red_goal_touch": [320, 0]})


def test_config_rejects_invalid_ignore_rect_extent() -> None:
    with pytest.raises(ValueError, match="width"):
        NsmbSortOrSplodeConfig.from_args({"ignore_touch_rects": [[300, 0, 30, 10]]})


def test_config_rejects_staging_point_inside_ignored_rect() -> None:
    with pytest.raises(ValueError, match="red_staging_touch"):
        NsmbSortOrSplodeConfig.from_args({"red_staging_touch": [20, 80]})


def test_touch_rect_to_cropped_hd_rect_uses_3ds_scale() -> None:
    rect = touch_rect_to_cropped_hd_rect(TouchRect(10, 20, 40, 30))

    assert rect.x == 15
    assert rect.y == 30
    assert rect.width == 60
    assert rect.height == 45


def test_paint_ignored_rects_uses_green_bgr() -> None:
    frame = np.zeros(
        (THREEDS_HD_BOTTOM_SCREEN.height, THREEDS_HD_BOTTOM_SCREEN.width, 3), dtype=np.uint8
    )

    masked = paint_ignored_rects(frame, (TouchRect(10, 20, 40, 30),), fill_bgr=(0, 255, 0))

    assert tuple(masked[30, 15]) == (0, 255, 0)
    assert tuple(masked[0, 0]) == (0, 0, 0)


def test_find_bombs_returns_best_match() -> None:
    template = _load_template("black_bob_omb.png")
    frame = np.zeros((120, 120, 3), dtype=np.uint8)
    frame[40 : 40 + template.shape[0], 30 : 30 + template.shape[1]] = template

    bombs = find_bombs(
        frame,
        template,
        color=BombColor.BLACK,
        threshold=0.95,
        duplicate_suppression_radius=18,
    )

    assert bombs
    assert bombs[0].color is BombColor.BLACK
    assert bombs[0].score >= 0.99


def test_find_bombs_rejects_low_score() -> None:
    template = _load_template("black_bob_omb.png")
    frame = np.zeros((120, 120, 3), dtype=np.uint8)

    bombs = find_bombs(
        frame,
        template,
        color=BombColor.BLACK,
        threshold=0.95,
        duplicate_suppression_radius=18,
    )

    assert bombs == []


def test_build_drag_path_includes_start_and_goal() -> None:
    path = build_drag_path(TouchPoint(10, 20), TouchPoint(20, 40), steps=2)

    assert path == (TouchPoint(10, 20), TouchPoint(15, 30), TouchPoint(20, 40))


def test_measure_color_features_separates_red_and_black_templates() -> None:
    red_template = _load_template("red_bob_omb.png")
    black_template = _load_template("black_bob_omb.png")

    red_features = measure_color_features(red_template, 17, 21, 28)
    black_features = measure_color_features(black_template, 16, 20, 28)

    assert red_features.red_ratio >= 0.20
    assert black_features.dark_ratio >= 0.35
    assert black_features.red_ratio <= 0.10


def test_classify_bombs_uses_hsv_gate_for_same_position_candidates() -> None:
    black_template = _load_template("black_bob_omb.png")
    frame = np.zeros((120, 120, 3), dtype=np.uint8)
    frame[40 : 40 + black_template.shape[0], 30 : 30 + black_template.shape[1]] = black_template
    center_x, center_y = _template_center(30, 40, black_template)
    red_false_positive = _detected_bomb(
        BombColor.RED,
        score=0.90,
        cropped_x=center_x,
        cropped_y=center_y,
    )
    black_candidate = _detected_bomb(
        BombColor.BLACK,
        score=0.86,
        cropped_x=center_x,
        cropped_y=center_y,
    )

    classified = classify_bombs(
        frame,
        [red_false_positive],
        [black_candidate],
        red_threshold=0.83,
        black_threshold=0.83,
        duplicate_suppression_radius=18,
        template_score_margin=0.08,
        color_sample_size=28,
        red_min_ratio=0.20,
        black_min_dark_ratio=0.35,
        black_max_red_ratio=0.10,
    )

    assert [bomb.color for bomb in classified] == [BombColor.BLACK]
    assert classified[0].red_score == 0.90
    assert classified[0].black_score == 0.86


def test_classify_bombs_keeps_nearby_opposite_colors_outside_radius() -> None:
    red_template = _load_template("red_bob_omb.png")
    black_template = _load_template("black_bob_omb.png")
    frame = np.zeros((160, 180, 3), dtype=np.uint8)
    frame[40 : 40 + red_template.shape[0], 30 : 30 + red_template.shape[1]] = red_template
    frame[40 : 40 + black_template.shape[0], 90 : 90 + black_template.shape[1]] = black_template
    red_x, red_y = _template_center(30, 40, red_template)
    black_x, black_y = _template_center(90, 40, black_template)
    red_candidate = _detected_bomb(BombColor.RED, score=0.95, cropped_x=red_x, cropped_y=red_y)
    black_candidate = _detected_bomb(
        BombColor.BLACK,
        score=0.95,
        cropped_x=black_x,
        cropped_y=black_y,
    )

    classified = classify_bombs(
        frame,
        [red_candidate],
        [black_candidate],
        red_threshold=0.83,
        black_threshold=0.83,
        duplicate_suppression_radius=18,
        template_score_margin=0.08,
        color_sample_size=28,
        red_min_ratio=0.20,
        black_min_dark_ratio=0.35,
        black_max_red_ratio=0.10,
    )

    assert {bomb.color for bomb in classified} == {BombColor.RED, BombColor.BLACK}


def test_macro_sends_touch_drag_for_detected_bomb() -> None:
    images = _template_images()
    cfg = NsmbSortOrSplodeConfig.from_args({"staging_wait_seconds": 0})
    initial_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    verification_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    template = images["templates/red_bob_omb.png"]
    _place_template_at_touch(initial_frame, template, TouchPoint(60, 40))
    _place_template_at_touch(verification_frame, template, cfg.red_staging_touch)
    cmd = FakeCommand([initial_frame, verification_frame], images)
    macro = NsmbSortOrSplodeMacro()
    macro.initialize(
        cmd,
        {
            "scan_interval_seconds": 0,
            "post_drop_wait_seconds": 0,
            "staging_wait_seconds": 0,
            "max_sorted_count": 1,
            "red_match_threshold": 0.95,
            "notify_on_finish": True,
        },
    )

    bomb = macro.run_iteration(cmd)

    assert bomb is not None
    assert bomb.color is BombColor.RED
    touch_down_points = _touch_down_points(cmd.events)
    assert (cfg.red_staging_touch.x, cfg.red_staging_touch.y) in touch_down_points
    assert (cfg.red_goal_touch.x, cfg.red_goal_touch.y) in touch_down_points
    assert ("touch_up", None) in cmd.events
    assert any(event[0] == "notify" for event in cmd.events)


def test_macro_uses_verified_color_after_staging() -> None:
    images = _template_images()
    cfg = NsmbSortOrSplodeConfig.from_args({"staging_wait_seconds": 0})
    initial_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    verification_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    verified_touch = TouchPoint(252, 198)
    _place_template_at_touch(
        initial_frame,
        images["templates/black_bob_omb.png"],
        TouchPoint(220, 40),
    )
    _place_template_at_touch(
        verification_frame,
        images["templates/red_bob_omb.png"],
        verified_touch,
    )
    cmd = FakeCommand([initial_frame, verification_frame], images)
    macro = NsmbSortOrSplodeMacro()
    macro.initialize(
        cmd,
        {
            "scan_interval_seconds": 0,
            "post_drop_wait_seconds": 0,
            "staging_wait_seconds": 0,
        },
    )

    bomb = macro.run_iteration(cmd)

    touch_down_points = _touch_down_points(cmd.events)
    assert bomb is not None
    assert bomb.color is BombColor.RED
    assert touch_down_points[4] == (cfg.black_staging_touch.x, cfg.black_staging_touch.y)
    assert touch_down_points[5] == (verified_touch.x, verified_touch.y)
    assert touch_down_points[-1] == (cfg.red_goal_touch.x, cfg.red_goal_touch.y)


def test_macro_skips_goal_when_staging_verification_is_ambiguous() -> None:
    images = _template_images()
    cfg = NsmbSortOrSplodeConfig.from_args({"staging_wait_seconds": 0})
    initial_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    verification_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    _place_template_at_touch(
        initial_frame,
        images["templates/red_bob_omb.png"],
        TouchPoint(60, 40),
    )
    _place_template_at_touch(
        verification_frame,
        images["templates/red_bob_omb.png"],
        TouchPoint(44, 200),
    )
    _place_template_at_touch(
        verification_frame,
        images["templates/black_bob_omb.png"],
        TouchPoint(84, 200),
    )
    cmd = FakeCommand([initial_frame, verification_frame], images)
    macro = NsmbSortOrSplodeMacro()
    macro.initialize(
        cmd,
        {
            "scan_interval_seconds": 0,
            "post_drop_wait_seconds": 0,
            "staging_wait_seconds": 0,
        },
    )

    bomb = macro.run_iteration(cmd)

    touch_down_points = _touch_down_points(cmd.events)
    assert bomb is None
    assert touch_down_points[-1] == (cfg.red_staging_touch.x, cfg.red_staging_touch.y)
    assert (cfg.red_goal_touch.x, cfg.red_goal_touch.y) not in touch_down_points
    assert any(event[0] == "log" and event[1][0] == "WARNING" for event in cmd.events)


def test_macro_detects_red_and_black_on_same_frame() -> None:
    images = _template_images()
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    bottom = THREEDS_HD_BOTTOM_SCREEN
    red_template = images["templates/red_bob_omb.png"]
    black_template = images["templates/black_bob_omb.png"]
    frame[
        bottom.y + 40 : bottom.y + 40 + red_template.shape[0],
        bottom.x + 30 : bottom.x + 30 + red_template.shape[1],
    ] = red_template
    frame[
        bottom.y + 120 : bottom.y + 120 + black_template.shape[0],
        bottom.x + 140 : bottom.x + 140 + black_template.shape[1],
    ] = black_template
    cmd = FakeCommand(frame, images)
    macro = NsmbSortOrSplodeMacro()
    macro.initialize(cmd, {"scan_interval_seconds": 0, "verify_before_goal": False})

    bomb = macro.run_iteration(cmd)

    assert bomb is not None
    assert bomb.color in {BombColor.RED, BombColor.BLACK}


def _detected_bomb(
    color: BombColor,
    *,
    score: float,
    cropped_x: int,
    cropped_y: int,
) -> DetectedBomb:
    return DetectedBomb(
        color=color,
        score=score,
        hd_center_x=THREEDS_HD_BOTTOM_SCREEN.x + cropped_x,
        hd_center_y=THREEDS_HD_BOTTOM_SCREEN.y + cropped_y,
        touch_x=round(cropped_x * 320 / THREEDS_HD_BOTTOM_SCREEN.width),
        touch_y=round(cropped_y * 240 / THREEDS_HD_BOTTOM_SCREEN.height),
        width=32,
        height=42,
    )


def _place_template_at_touch(
    frame: np.ndarray,
    template: np.ndarray,
    touch: TouchPoint,
) -> None:
    bottom = THREEDS_HD_BOTTOM_SCREEN
    center_x = bottom.x + round(touch.x * bottom.width / 320)
    center_y = bottom.y + round(touch.y * bottom.height / 240)
    x0 = center_x - template.shape[1] // 2
    y0 = center_y - template.shape[0] // 2
    frame[y0 : y0 + template.shape[0], x0 : x0 + template.shape[1]] = template


def _touch_down_points(events: list[tuple[str, object]]) -> list[tuple[int, int]]:
    return [payload for name, payload in events if name == "touch_down"]


def _template_center(x: int, y: int, template: np.ndarray) -> tuple[int, int]:
    return x + template.shape[1] // 2, y + template.shape[0] // 2
