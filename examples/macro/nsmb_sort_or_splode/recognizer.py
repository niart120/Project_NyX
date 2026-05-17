from dataclasses import dataclass
from enum import StrEnum
from math import ceil, floor

import cv2
import numpy as np

from nyxpy.framework.core.constants import (
    THREEDS_HD_BOTTOM_SCREEN,
    ScreenPoint,
    ScreenRect,
    TouchPoint,
    cropped_hd_point_to_3ds_touch,
    touch_point_to_3ds_hd_capture,
)

from .config import TouchRect


class BombColor(StrEnum):
    RED = "red"
    BLACK = "black"


@dataclass(frozen=True, slots=True)
class DetectedBomb:
    color: BombColor
    score: float
    hd_center_x: int
    hd_center_y: int
    touch_x: int
    touch_y: int
    width: int
    height: int
    red_score: float = 0.0
    black_score: float = 0.0
    color_features: "ColorFeatures | None" = None

    @property
    def touch_point(self) -> TouchPoint:
        return TouchPoint(self.touch_x, self.touch_y)


@dataclass(frozen=True, slots=True)
class ColorFeatures:
    red_ratio: float
    dark_ratio: float


def touch_rect_to_cropped_hd_rect(rect: TouchRect) -> ScreenRect:
    start = touch_point_to_3ds_hd_capture(TouchPoint(rect.x, rect.y))
    end_x = THREEDS_HD_BOTTOM_SCREEN.x + ceil((rect.x + rect.width) * 480 / 320)
    end_y = THREEDS_HD_BOTTOM_SCREEN.y + ceil((rect.y + rect.height) * 360 / 240)
    return ScreenRect(
        start.x - THREEDS_HD_BOTTOM_SCREEN.x,
        start.y - THREEDS_HD_BOTTOM_SCREEN.y,
        max(1, end_x - start.x),
        max(1, end_y - start.y),
    )


def paint_ignored_rects(
    frame_bgr: np.ndarray,
    ignore_touch_rects: tuple[TouchRect, ...],
    *,
    fill_bgr: tuple[int, int, int] = (0, 255, 0),
) -> np.ndarray:
    masked = frame_bgr.copy()
    for touch_rect in ignore_touch_rects:
        rect = touch_rect_to_cropped_hd_rect(touch_rect)
        right = min(masked.shape[1], rect.right)
        bottom = min(masked.shape[0], rect.bottom)
        cv2.rectangle(
            masked,
            (rect.x, rect.y),
            (right - 1, bottom - 1),
            fill_bgr,
            thickness=-1,
        )
    return masked


def find_bombs(
    frame_bgr: np.ndarray,
    template_bgr: np.ndarray,
    *,
    color: BombColor,
    threshold: float,
    duplicate_suppression_radius: int,
) -> list[DetectedBomb]:
    if frame_bgr.ndim != 3 or template_bgr.ndim != 3:
        raise ValueError("frame_bgr and template_bgr must be color images")
    if frame_bgr.shape[0] < template_bgr.shape[0] or frame_bgr.shape[1] < template_bgr.shape[1]:
        return []

    result = cv2.matchTemplate(frame_bgr, template_bgr, cv2.TM_CCOEFF_NORMED)
    ys, xs = _local_maxima(result, threshold)
    candidates = [
        _candidate_from_match(
            color,
            float(result[y, x]),
            x,
            y,
            template_bgr.shape[1],
            template_bgr.shape[0],
        )
        for y, x in zip(ys, xs)
    ]
    candidates.sort(key=lambda item: item.score, reverse=True)
    selected = _suppress_duplicates(candidates, duplicate_suppression_radius)
    return selected


def classify_bombs(
    frame_bgr: np.ndarray,
    red_candidates: list[DetectedBomb],
    black_candidates: list[DetectedBomb],
    *,
    red_threshold: float,
    black_threshold: float,
    duplicate_suppression_radius: int,
    template_score_margin: float,
    color_sample_size: int,
    red_min_ratio: float,
    black_min_dark_ratio: float,
    black_max_red_ratio: float,
) -> list[DetectedBomb]:
    classified: list[DetectedBomb] = []
    candidates = sorted(
        [*red_candidates, *black_candidates],
        key=lambda item: item.score,
        reverse=True,
    )
    consumed = [False] * len(candidates)
    duplicate_suppression_radius_sq = duplicate_suppression_radius * duplicate_suppression_radius
    for index, anchor in enumerate(candidates):
        if consumed[index]:
            continue
        group_indices = [
            group_index
            for group_index, candidate in enumerate(candidates)
            if not consumed[group_index]
            and _touch_distance_sq(anchor, candidate) <= duplicate_suppression_radius_sq
        ]
        for group_index in group_indices:
            consumed[group_index] = True
        group = [candidates[group_index] for group_index in group_indices]
        red = _best_color_candidate(group, BombColor.RED)
        black = _best_color_candidate(group, BombColor.BLACK)
        red_score = red.score if red is not None else 0.0
        black_score = black.score if black is not None else 0.0
        features = measure_color_features(
            frame_bgr,
            anchor.hd_center_x - THREEDS_HD_BOTTOM_SCREEN.x,
            anchor.hd_center_y - THREEDS_HD_BOTTOM_SCREEN.y,
            color_sample_size,
        )
        red_gate = features.red_ratio >= red_min_ratio
        black_gate = (
            features.dark_ratio >= black_min_dark_ratio
            and features.red_ratio <= black_max_red_ratio
        )

        selected: DetectedBomb | None = None
        selected_color: BombColor | None = None
        if (
            red is not None
            and red.score >= red_threshold
            and red.score >= black_score + template_score_margin
            and red_gate
        ):
            selected = red
            selected_color = BombColor.RED
        elif (
            black is not None
            and black.score >= black_threshold
            and black.score >= red_score + template_score_margin
            and black_gate
        ):
            selected = black
            selected_color = BombColor.BLACK
        elif red_gate != black_gate:
            if red_gate and red is not None and red.score >= red_threshold:
                selected = red
                selected_color = BombColor.RED
            elif black_gate and black is not None and black.score >= black_threshold:
                selected = black
                selected_color = BombColor.BLACK

        if selected is not None and selected_color is not None:
            classified.append(
                DetectedBomb(
                    color=selected_color,
                    score=selected.score,
                    hd_center_x=selected.hd_center_x,
                    hd_center_y=selected.hd_center_y,
                    touch_x=selected.touch_x,
                    touch_y=selected.touch_y,
                    width=selected.width,
                    height=selected.height,
                    red_score=red_score,
                    black_score=black_score,
                    color_features=features,
                )
            )
    classified.sort(key=lambda item: item.score, reverse=True)
    return classified


def measure_color_features(
    frame_bgr: np.ndarray,
    cropped_center_x: int,
    cropped_center_y: int,
    sample_size: int,
) -> ColorFeatures:
    if sample_size < 1:
        raise ValueError("sample_size must be greater than 0")
    half = sample_size // 2
    x0 = max(0, cropped_center_x - half)
    y0 = max(0, cropped_center_y - half)
    x1 = min(frame_bgr.shape[1], x0 + sample_size)
    y1 = min(frame_bgr.shape[0], y0 + sample_size)
    roi = frame_bgr[y0:y1, x0:x1]
    if roi.size == 0:
        return ColorFeatures(red_ratio=0.0, dark_ratio=0.0)
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    hue = hsv[:, :, 0]
    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]
    red = ((hue <= 10) | (hue >= 165)) & (saturation >= 70) & (value >= 80)
    dark = (value <= 95) & (saturation <= 140)
    total = hue.size
    return ColorFeatures(
        red_ratio=float(red.sum() / total),
        dark_ratio=float(dark.sum() / total),
    )


def build_drag_path(
    start: TouchPoint,
    goal: TouchPoint,
    *,
    steps: int,
) -> tuple[TouchPoint, ...]:
    if steps < 1:
        raise ValueError("steps must be greater than 0")
    return tuple(
        TouchPoint(
            round(start.x + (goal.x - start.x) * i / steps),
            round(start.y + (goal.y - start.y) * i / steps),
        )
        for i in range(steps + 1)
    )


def _candidate_from_match(
    color: BombColor,
    score: float,
    x: int,
    y: int,
    width: int,
    height: int,
) -> DetectedBomb:
    center_x = x + floor(width / 2)
    center_y = y + floor(height / 2)
    touch = cropped_hd_point_to_3ds_touch(
        ScreenPoint(center_x, center_y),
        THREEDS_HD_BOTTOM_SCREEN,
    )
    return DetectedBomb(
        color=color,
        score=score,
        hd_center_x=THREEDS_HD_BOTTOM_SCREEN.x + center_x,
        hd_center_y=THREEDS_HD_BOTTOM_SCREEN.y + center_y,
        touch_x=touch.x,
        touch_y=touch.y,
        width=width,
        height=height,
        red_score=score if color is BombColor.RED else 0.0,
        black_score=score if color is BombColor.BLACK else 0.0,
    )


def _suppress_duplicates(
    candidates: list[DetectedBomb],
    duplicate_suppression_radius: int,
) -> list[DetectedBomb]:
    min_distance_sq = duplicate_suppression_radius * duplicate_suppression_radius
    selected: list[DetectedBomb] = []
    for candidate in candidates:
        if all(_touch_distance_sq(candidate, item) > min_distance_sq for item in selected):
            selected.append(candidate)
    return selected


def _best_color_candidate(candidates: list[DetectedBomb], color: BombColor) -> DetectedBomb | None:
    same_color = [candidate for candidate in candidates if candidate.color is color]
    if not same_color:
        return None
    return max(same_color, key=lambda item: item.score)


def _touch_distance_sq(first: DetectedBomb, second: DetectedBomb) -> int:
    dx = first.touch_x - second.touch_x
    dy = first.touch_y - second.touch_y
    return dx * dx + dy * dy


def _local_maxima(result: np.ndarray, threshold: float) -> tuple[np.ndarray, np.ndarray]:
    above_threshold = result >= threshold
    if not bool(above_threshold.any()):
        return np.array([], dtype=np.int64), np.array([], dtype=np.int64)
    dilated = cv2.dilate(result, np.ones((3, 3), dtype=np.uint8))
    return np.where(above_threshold & (result == dilated))
