from dataclasses import dataclass
from enum import StrEnum
from math import ceil, floor, hypot

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

    @property
    def touch_point(self) -> TouchPoint:
        return TouchPoint(self.touch_x, self.touch_y)


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
    min_score_margin: float,
    duplicate_suppression_radius: int,
) -> list[DetectedBomb]:
    if frame_bgr.ndim != 3 or template_bgr.ndim != 3:
        raise ValueError("frame_bgr and template_bgr must be color images")
    if frame_bgr.shape[0] < template_bgr.shape[0] or frame_bgr.shape[1] < template_bgr.shape[1]:
        return []

    result = cv2.matchTemplate(frame_bgr, template_bgr, cv2.TM_CCOEFF_NORMED)
    ys, xs = np.where(result >= threshold)
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
    if selected and selected[0].score < threshold + min_score_margin:
        return []
    return selected


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
    )


def _suppress_duplicates(
    candidates: list[DetectedBomb],
    duplicate_suppression_radius: int,
) -> list[DetectedBomb]:
    selected: list[DetectedBomb] = []
    for candidate in candidates:
        if all(
            hypot(candidate.touch_x - item.touch_x, candidate.touch_y - item.touch_y)
            > duplicate_suppression_radius
            for item in selected
        ):
            selected.append(candidate)
    return selected
