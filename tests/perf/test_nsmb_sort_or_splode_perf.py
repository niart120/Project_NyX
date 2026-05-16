import time
from pathlib import Path

import cv2

from macros.nsmb_sort_or_splode.config import NsmbSortOrSplodeConfig
from macros.nsmb_sort_or_splode.recognizer import BombColor, find_bombs, paint_ignored_rects
from nyxpy.framework.core.constants import THREEDS_HD_BOTTOM_SCREEN

ROOT = Path(__file__).resolve().parents[2]
SINGLE_COLOR_THRESHOLD_S = 0.03


def _load_image(path: Path):
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    assert image is not None
    return image


def test_nsmb_sort_or_splode_single_color_detection_perf() -> None:
    cfg = NsmbSortOrSplodeConfig.from_args({})
    template = _load_image(
        ROOT / "resources" / "nsmb_sort_or_splode" / "assets" / "templates" / "black_bob_omb.png"
    )
    frame = _load_image(ROOT / "spec" / "macro" / "nsmb_sort_or_splode" / "masked_preview.png")
    bottom = THREEDS_HD_BOTTOM_SCREEN
    cropped = frame[bottom.y : bottom.y + bottom.height, bottom.x : bottom.x + bottom.width]

    iterations = 100
    started = time.perf_counter()
    for _ in range(iterations):
        masked = paint_ignored_rects(cropped, cfg.ignore_touch_rects, fill_bgr=cfg.mask_fill_bgr)
        find_bombs(
            masked,
            template,
            color=BombColor.BLACK,
            threshold=cfg.black_match_threshold,
            min_score_margin=cfg.min_score_margin,
            duplicate_suppression_radius=cfg.duplicate_suppression_radius,
        )
    elapsed = (time.perf_counter() - started) / iterations

    assert elapsed < SINGLE_COLOR_THRESHOLD_S
