from pathlib import Path

import cv2
import numpy as np
import pytest

from macros.nsmb_sort_or_splode.config import NsmbSortOrSplodeConfig, TouchRect
from macros.nsmb_sort_or_splode.macro import NsmbSortOrSplodeMacro
from macros.nsmb_sort_or_splode.recognizer import (
    BombColor,
    build_drag_path,
    find_bombs,
    paint_ignored_rects,
    touch_rect_to_cropped_hd_rect,
)
from nyxpy.framework.core.constants import THREEDS_HD_BOTTOM_SCREEN, TouchPoint

ROOT = Path(__file__).resolve().parents[3]


class FakeCommand:
    def __init__(self, frame: np.ndarray, images: dict[str, np.ndarray]) -> None:
        self.frame = frame
        self.images = images
        self.events: list[tuple[str, object]] = []
        self.saved_images: dict[str, np.ndarray] = {}

    def load_img(self, filename, grayscale: bool = False):
        image = self.images[str(filename).replace("\\", "/")].copy()
        if grayscale and image.ndim == 3:
            return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        return image

    def capture(self, crop_region=None, grayscale: bool = False):
        frame = self.frame.copy()
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

    assert cfg.red_goal_touch == TouchPoint(50, 122)
    assert cfg.black_goal_touch == TouchPoint(270, 122)
    assert cfg.mask_fill_bgr == (0, 255, 0)


def test_config_rejects_invalid_touch_goal() -> None:
    with pytest.raises(ValueError, match="Touch X"):
        NsmbSortOrSplodeConfig.from_args({"red_goal_touch": [320, 0]})


def test_config_rejects_invalid_ignore_rect_extent() -> None:
    with pytest.raises(ValueError, match="width"):
        NsmbSortOrSplodeConfig.from_args({"ignore_touch_rects": [[300, 0, 30, 10]]})


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
        min_score_margin=0.0,
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
        min_score_margin=0.0,
        duplicate_suppression_radius=18,
    )

    assert bombs == []


def test_build_drag_path_includes_start_and_goal() -> None:
    path = build_drag_path(TouchPoint(10, 20), TouchPoint(20, 40), steps=2)

    assert path == (TouchPoint(10, 20), TouchPoint(15, 30), TouchPoint(20, 40))


def test_macro_sends_touch_drag_for_detected_bomb() -> None:
    frame = cv2.imread(str(ROOT / "snapshots" / "20260516_200318.png"), cv2.IMREAD_COLOR)
    assert frame is not None
    cmd = FakeCommand(frame, _template_images())
    macro = NsmbSortOrSplodeMacro()
    macro.initialize(
        cmd,
        {
            "scan_interval_seconds": 0,
            "post_drop_wait_seconds": 0,
            "max_sorted_count": 1,
            "min_score_margin": 0,
            "red_match_threshold": 0.95,
        },
    )

    bomb = macro.run_iteration(cmd)

    assert bomb is not None
    assert bomb.color is BombColor.RED
    assert any(event[0] == "touch_down" for event in cmd.events)
    assert ("touch_up", None) in cmd.events
    assert any(event[0] == "notify" for event in cmd.events)


def test_macro_alternates_red_and_black_detection() -> None:
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    cmd = FakeCommand(frame, _template_images())
    macro = NsmbSortOrSplodeMacro()
    macro.initialize(cmd, {"scan_interval_seconds": 0, "min_score_margin": 0})

    macro.run_iteration(cmd)
    macro.run_iteration(cmd)

    assert macro._next_color is BombColor.RED
