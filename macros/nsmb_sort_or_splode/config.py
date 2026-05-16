from dataclasses import dataclass
from pathlib import Path
from typing import Self

from nyxpy.framework.core.constants import THREEDS_TOUCH_SIZE, TouchPoint, validate_3ds_touch_point


@dataclass(frozen=True, slots=True)
class TouchRect:
    x: int
    y: int
    width: int
    height: int

    def __post_init__(self) -> None:
        if self.x < 0 or self.y < 0:
            raise ValueError("TouchRect x and y must be greater than or equal to 0")
        if self.width < 1 or self.height < 1:
            raise ValueError("TouchRect width and height must be greater than 0")
        if self.x + self.width > THREEDS_TOUCH_SIZE.width:
            raise ValueError("TouchRect exceeds 3DS touch width")
        if self.y + self.height > THREEDS_TOUCH_SIZE.height:
            raise ValueError("TouchRect exceeds 3DS touch height")


@dataclass(frozen=True, slots=True)
class NsmbSortOrSplodeConfig:
    scan_interval_seconds: float = 0.10
    post_drop_wait_seconds: float = 0.02
    max_sorted_count: int = 0
    red_template_path: Path = Path("templates/red_bob_omb.png")
    black_template_path: Path = Path("templates/black_bob_omb.png")
    mask_fill_bgr: tuple[int, int, int] = (0, 255, 0)
    match_method: str = "TM_CCOEFF_NORMED"
    red_match_threshold: float = 0.82
    black_match_threshold: float = 0.82
    min_score_margin: float = 0.05
    duplicate_suppression_radius: int = 18
    drag_steps: int = 8
    drag_duration_seconds: float = 0.18
    red_goal_touch: TouchPoint = TouchPoint(50, 122)
    black_goal_touch: TouchPoint = TouchPoint(270, 122)
    ignore_touch_rects: tuple[TouchRect, ...] = (
        TouchRect(9, 70, 82, 100),
        TouchRect(230, 72, 82, 98),
    )
    save_debug_frames: bool = False
    notify_on_finish: bool = True

    @classmethod
    def from_args(cls, args: dict) -> Self:
        defaults = cls()
        cfg = cls(
            scan_interval_seconds=_get_float(
                args, "scan_interval_seconds", defaults.scan_interval_seconds
            ),
            post_drop_wait_seconds=_get_float(
                args,
                "post_drop_wait_seconds",
                defaults.post_drop_wait_seconds,
            ),
            max_sorted_count=_get_int(args, "max_sorted_count", defaults.max_sorted_count),
            red_template_path=Path(str(args.get("red_template_path", defaults.red_template_path))),
            black_template_path=Path(
                str(args.get("black_template_path", defaults.black_template_path))
            ),
            mask_fill_bgr=_parse_bgr(args.get("mask_fill_bgr", defaults.mask_fill_bgr)),
            match_method=str(args.get("match_method", defaults.match_method)),
            red_match_threshold=_get_float(
                args,
                "red_match_threshold",
                defaults.red_match_threshold,
            ),
            black_match_threshold=_get_float(
                args,
                "black_match_threshold",
                defaults.black_match_threshold,
            ),
            min_score_margin=_get_float(args, "min_score_margin", defaults.min_score_margin),
            duplicate_suppression_radius=_get_int(
                args,
                "duplicate_suppression_radius",
                defaults.duplicate_suppression_radius,
            ),
            drag_steps=_get_int(args, "drag_steps", defaults.drag_steps),
            drag_duration_seconds=_get_float(
                args,
                "drag_duration_seconds",
                defaults.drag_duration_seconds,
            ),
            red_goal_touch=_parse_touch_point(args.get("red_goal_touch", defaults.red_goal_touch)),
            black_goal_touch=_parse_touch_point(
                args.get("black_goal_touch", defaults.black_goal_touch)
            ),
            ignore_touch_rects=_parse_touch_rects(
                args.get("ignore_touch_rects", defaults.ignore_touch_rects)
            ),
            save_debug_frames=bool(args.get("save_debug_frames", defaults.save_debug_frames)),
            notify_on_finish=bool(args.get("notify_on_finish", defaults.notify_on_finish)),
        )
        cfg.validate()
        return cfg

    def validate(self) -> None:
        if self.scan_interval_seconds < 0:
            raise ValueError("scan_interval_seconds must be greater than or equal to 0")
        if self.post_drop_wait_seconds < 0:
            raise ValueError("post_drop_wait_seconds must be greater than or equal to 0")
        if self.max_sorted_count < 0:
            raise ValueError("max_sorted_count must be greater than or equal to 0")
        if self.match_method != "TM_CCOEFF_NORMED":
            raise ValueError("Only TM_CCOEFF_NORMED is supported")
        _validate_threshold("red_match_threshold", self.red_match_threshold)
        _validate_threshold("black_match_threshold", self.black_match_threshold)
        if self.min_score_margin < 0:
            raise ValueError("min_score_margin must be greater than or equal to 0")
        if self.duplicate_suppression_radius < 0:
            raise ValueError("duplicate_suppression_radius must be greater than or equal to 0")
        if self.drag_steps < 1:
            raise ValueError("drag_steps must be greater than 0")
        if self.drag_duration_seconds < 0:
            raise ValueError("drag_duration_seconds must be greater than or equal to 0")
        validate_3ds_touch_point(self.red_goal_touch)
        validate_3ds_touch_point(self.black_goal_touch)


def _get_float(args: dict, name: str, default: float) -> float:
    return float(args.get(name, default))


def _get_int(args: dict, name: str, default: int) -> int:
    return int(args.get(name, default))


def _validate_threshold(name: str, value: float) -> None:
    if not 0 <= value <= 1:
        raise ValueError(f"{name} must be in range 0..1")


def _parse_bgr(value: object) -> tuple[int, int, int]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError("mask_fill_bgr must be a 3-item list")
    parsed = tuple(int(v) for v in value)
    if any(v < 0 or v > 255 for v in parsed):
        raise ValueError("mask_fill_bgr values must be in range 0..255")
    return parsed


def _parse_touch_point(value: object) -> TouchPoint:
    if isinstance(value, TouchPoint):
        return validate_3ds_touch_point(value)
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError("touch point must be a 2-item list")
    return validate_3ds_touch_point(TouchPoint(int(value[0]), int(value[1])))


def _parse_touch_rects(value: object) -> tuple[TouchRect, ...]:
    if isinstance(value, tuple) and all(isinstance(item, TouchRect) for item in value):
        return value
    if not isinstance(value, (list, tuple)):
        raise ValueError("ignore_touch_rects must be a list")
    rects: list[TouchRect] = []
    for item in value:
        if isinstance(item, TouchRect):
            rects.append(item)
            continue
        if not isinstance(item, (list, tuple)) or len(item) != 4:
            raise ValueError("ignore_touch_rects entries must be 4-item lists")
        rects.append(TouchRect(*(int(v) for v in item)))
    return tuple(rects)
