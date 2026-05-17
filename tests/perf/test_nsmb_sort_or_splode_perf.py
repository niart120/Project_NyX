import time
from pathlib import Path

import cv2
from macro.nsmb_sort_or_splode.config import NsmbSortOrSplodeConfig
from macro.nsmb_sort_or_splode.recognizer import (
    BombColor,
    classify_bombs,
    find_bombs,
    paint_ignored_rects,
)

from nyxpy.framework.core.constants import THREEDS_HD_BOTTOM_SCREEN

ROOT = Path(__file__).resolve().parents[2]
CLASSIFIED_DETECTION_THRESHOLD_S = 0.04


def _load_image(path: Path):
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    assert image is not None
    return image


def test_nsmb_sort_or_splode_classified_detection_perf() -> None:
    cfg = NsmbSortOrSplodeConfig.from_args({})
    red_template = _load_image(
        ROOT
        / "examples"
        / "resources"
        / "nsmb_sort_or_splode"
        / "assets"
        / "templates"
        / "red_bob_omb.png"
    )
    black_template = _load_image(
        ROOT
        / "examples"
        / "resources"
        / "nsmb_sort_or_splode"
        / "assets"
        / "templates"
        / "black_bob_omb.png"
    )
    frame = _load_image(ROOT / "spec" / "macro" / "nsmb_sort_or_splode" / "masked_preview.png")
    bottom = THREEDS_HD_BOTTOM_SCREEN
    cropped = frame[bottom.y : bottom.y + bottom.height, bottom.x : bottom.x + bottom.width]

    iterations = 100
    started = time.perf_counter()
    for _ in range(iterations):
        masked = paint_ignored_rects(cropped, cfg.ignore_touch_rects, fill_bgr=cfg.mask_fill_bgr)
        red_candidates = find_bombs(
            masked,
            red_template,
            color=BombColor.RED,
            threshold=cfg.red_match_threshold,
            duplicate_suppression_radius=cfg.duplicate_suppression_radius,
        )
        black_candidates = find_bombs(
            masked,
            black_template,
            color=BombColor.BLACK,
            threshold=cfg.black_match_threshold,
            duplicate_suppression_radius=cfg.duplicate_suppression_radius,
        )
        classify_bombs(
            cropped,
            red_candidates,
            black_candidates,
            red_threshold=cfg.red_match_threshold,
            black_threshold=cfg.black_match_threshold,
            duplicate_suppression_radius=cfg.duplicate_suppression_radius,
            template_score_margin=cfg.template_score_margin,
            color_sample_size=cfg.color_sample_size,
            red_min_ratio=cfg.red_min_ratio,
            black_min_dark_ratio=cfg.black_min_dark_ratio,
            black_max_red_ratio=cfg.black_max_red_ratio,
        )
    elapsed = (time.perf_counter() - started) / iterations

    assert elapsed < CLASSIFIED_DETECTION_THRESHOLD_S
