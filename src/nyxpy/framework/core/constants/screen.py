"""3DS screen coordinate constants and conversion helpers."""

from dataclasses import dataclass
from enum import StrEnum
from math import floor


@dataclass(frozen=True, slots=True)
class ScreenSize:
    width: int
    height: int

    def __post_init__(self) -> None:
        if self.width < 1 or self.height < 1:
            raise ValueError("ScreenSize width and height must be greater than 0")


@dataclass(frozen=True, slots=True)
class ScreenPoint:
    x: int
    y: int


@dataclass(frozen=True, slots=True)
class ScreenRect:
    x: int
    y: int
    width: int
    height: int

    def __post_init__(self) -> None:
        if self.width < 1 or self.height < 1:
            raise ValueError("ScreenRect width and height must be greater than 0")

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height

    @property
    def tuple(self) -> tuple[int, int, int, int]:
        return self.x, self.y, self.width, self.height

    def contains(self, point: ScreenPoint) -> bool:
        return self.x <= point.x < self.right and self.y <= point.y < self.bottom


@dataclass(frozen=True, slots=True)
class TouchPoint:
    x: int
    y: int


class ScaleRounding(StrEnum):
    FLOOR = "floor"
    ROUND = "round"


THREEDS_CAPTURE_SIZE = ScreenSize(400, 480)
THREEDS_TOP_SCREEN = ScreenRect(0, 0, 400, 240)
THREEDS_BOTTOM_SCREEN = ScreenRect(40, 240, 320, 240)
THREEDS_BOTTOM_PILLARBOXED_AREA = ScreenRect(0, 240, 400, 240)
THREEDS_FULL_SCREEN = ScreenRect(0, 0, 400, 480)

THREEDS_HD_CAPTURE_SIZE = ScreenSize(1280, 720)
THREEDS_HD_CANVAS = ScreenRect(0, 0, 1280, 720)
THREEDS_HD_CONTENT = ScreenRect(340, 0, 600, 720)
THREEDS_HD_TOP_SCREEN = ScreenRect(340, 0, 600, 360)
THREEDS_HD_BOTTOM_SCREEN = ScreenRect(400, 360, 480, 360)
THREEDS_HD_BOTTOM_PILLARBOXED_AREA = ScreenRect(340, 360, 600, 360)
THREEDS_HD_FULL_SCREEN = THREEDS_HD_CONTENT

THREEDS_TOUCH_SIZE = ScreenSize(320, 240)


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


def _quantize_point(point: ScreenPoint, rect: ScreenRect, target_size: ScreenSize) -> ScreenPoint:
    if not rect.contains(point):
        raise ValueError("Point is outside target rectangle")
    x = floor((point.x - rect.x + 0.5) * target_size.width / rect.width)
    y = floor((point.y - rect.y + 0.5) * target_size.height / rect.height)
    return ScreenPoint(
        _clamp(x, 0, target_size.width - 1),
        _clamp(y, 0, target_size.height - 1),
    )


def validate_3ds_touch_point(point: TouchPoint) -> TouchPoint:
    if not 0 <= point.x < THREEDS_TOUCH_SIZE.width:
        raise ValueError("Touch X must be in range 0..319")
    if not 0 <= point.y < THREEDS_TOUCH_SIZE.height:
        raise ValueError("Touch Y must be in range 0..239")
    return point


def normalized_point_to_3ds_touch(point: ScreenPoint) -> TouchPoint:
    quantized = _quantize_point(point, THREEDS_BOTTOM_SCREEN, THREEDS_TOUCH_SIZE)
    return TouchPoint(quantized.x, quantized.y)


def try_normalized_point_to_3ds_touch(point: ScreenPoint) -> TouchPoint | None:
    try:
        return normalized_point_to_3ds_touch(point)
    except ValueError:
        return None


def touch_point_to_3ds_normalized(point: TouchPoint) -> ScreenPoint:
    point = validate_3ds_touch_point(point)
    return ScreenPoint(THREEDS_BOTTOM_SCREEN.x + point.x, THREEDS_BOTTOM_SCREEN.y + point.y)


def normalized_point_to_hd_capture(point: ScreenPoint) -> ScreenPoint:
    if not THREEDS_FULL_SCREEN.contains(point):
        raise ValueError("Point is outside 3DS normalized screen")
    return ScreenPoint(
        THREEDS_HD_CONTENT.x
        + floor(point.x * THREEDS_HD_CONTENT.width / THREEDS_CAPTURE_SIZE.width),
        THREEDS_HD_CONTENT.y
        + floor(point.y * THREEDS_HD_CONTENT.height / THREEDS_CAPTURE_SIZE.height),
    )


def hd_capture_point_to_normalized(point: ScreenPoint) -> ScreenPoint:
    return _quantize_point(point, THREEDS_HD_CONTENT, THREEDS_CAPTURE_SIZE)


def hd_capture_point_to_3ds_touch(point: ScreenPoint) -> TouchPoint:
    quantized = _quantize_point(point, THREEDS_HD_BOTTOM_SCREEN, THREEDS_TOUCH_SIZE)
    return TouchPoint(quantized.x, quantized.y)


def try_hd_capture_point_to_3ds_touch(point: ScreenPoint) -> TouchPoint | None:
    try:
        return hd_capture_point_to_3ds_touch(point)
    except ValueError:
        return None


def touch_point_to_3ds_hd_capture(point: TouchPoint) -> ScreenPoint:
    point = validate_3ds_touch_point(point)
    return ScreenPoint(
        THREEDS_HD_BOTTOM_SCREEN.x + floor(point.x * THREEDS_HD_BOTTOM_SCREEN.width / 320),
        THREEDS_HD_BOTTOM_SCREEN.y + floor(point.y * THREEDS_HD_BOTTOM_SCREEN.height / 240),
    )


def cropped_normalized_point_to_normalized(
    point: ScreenPoint,
    crop_region: ScreenRect,
) -> ScreenPoint:
    return ScreenPoint(point.x + crop_region.x, point.y + crop_region.y)


def normalized_point_to_cropped(point: ScreenPoint, crop_region: ScreenRect) -> ScreenPoint:
    if not crop_region.contains(point):
        raise ValueError("Point is outside crop region")
    return ScreenPoint(point.x - crop_region.x, point.y - crop_region.y)


def cropped_normalized_point_to_3ds_touch(
    point: ScreenPoint,
    crop_region: ScreenRect,
) -> TouchPoint:
    return normalized_point_to_3ds_touch(cropped_normalized_point_to_normalized(point, crop_region))


def try_cropped_normalized_point_to_3ds_touch(
    point: ScreenPoint,
    crop_region: ScreenRect,
) -> TouchPoint | None:
    try:
        return cropped_normalized_point_to_3ds_touch(point, crop_region)
    except ValueError:
        return None


def cropped_hd_point_to_3ds_touch(point: ScreenPoint, crop_region: ScreenRect) -> TouchPoint:
    hd_point = ScreenPoint(point.x + crop_region.x, point.y + crop_region.y)
    return hd_capture_point_to_3ds_touch(hd_point)


def try_cropped_hd_point_to_3ds_touch(
    point: ScreenPoint,
    crop_region: ScreenRect,
) -> TouchPoint | None:
    try:
        return cropped_hd_point_to_3ds_touch(point, crop_region)
    except ValueError:
        return None


def scale_point(
    point: ScreenPoint,
    *,
    source_size: ScreenSize,
    target_size: ScreenSize = THREEDS_CAPTURE_SIZE,
    rounding: ScaleRounding = ScaleRounding.FLOOR,
) -> ScreenPoint:
    x_float = (point.x + 0.5) * target_size.width / source_size.width
    y_float = (point.y + 0.5) * target_size.height / source_size.height
    if rounding is ScaleRounding.ROUND:
        x = round(x_float)
        y = round(y_float)
    else:
        x = floor(x_float)
        y = floor(y_float)
    return ScreenPoint(_clamp(x, 0, target_size.width - 1), _clamp(y, 0, target_size.height - 1))


def scaled_source_point_to_3ds_touch(
    point: ScreenPoint,
    *,
    source_size: ScreenSize,
) -> TouchPoint:
    return normalized_point_to_3ds_touch(
        scale_point(point, source_size=source_size, target_size=THREEDS_CAPTURE_SIZE)
    )


def try_scaled_source_point_to_3ds_touch(
    point: ScreenPoint,
    *,
    source_size: ScreenSize,
) -> TouchPoint | None:
    try:
        return scaled_source_point_to_3ds_touch(point, source_size=source_size)
    except ValueError:
        return None


def aspect_fit_rect(source_size: ScreenSize, target_size: ScreenSize) -> ScreenRect:
    scale = min(target_size.width / source_size.width, target_size.height / source_size.height)
    width = max(1, round(source_size.width * scale))
    height = max(1, round(source_size.height * scale))
    return ScreenRect(
        (target_size.width - width) // 2, (target_size.height - height) // 2, width, height
    )


def project_hd_rect_to_preview(rect: ScreenRect, *, preview_size: ScreenSize) -> ScreenRect:
    display = aspect_fit_rect(THREEDS_HD_CAPTURE_SIZE, preview_size)
    scale_x = display.width / THREEDS_HD_CAPTURE_SIZE.width
    scale_y = display.height / THREEDS_HD_CAPTURE_SIZE.height
    return ScreenRect(
        display.x + round(rect.x * scale_x),
        display.y + round(rect.y * scale_y),
        max(1, round(rect.width * scale_x)),
        max(1, round(rect.height * scale_y)),
    )


def preview_touch_rect(preview_size: ScreenSize) -> ScreenRect:
    return project_hd_rect_to_preview(THREEDS_HD_BOTTOM_SCREEN, preview_size=preview_size)


def preview_point_to_hd_capture(
    point: ScreenPoint,
    *,
    preview_size: ScreenSize,
    hd_capture_size: ScreenSize = THREEDS_HD_CAPTURE_SIZE,
) -> ScreenPoint:
    display = aspect_fit_rect(hd_capture_size, preview_size)
    if not display.contains(point):
        raise ValueError("Point is outside preview display rectangle")
    x = floor((point.x - display.x) * hd_capture_size.width / display.width)
    y = floor((point.y - display.y) * hd_capture_size.height / display.height)
    return ScreenPoint(
        _clamp(x, 0, hd_capture_size.width - 1), _clamp(y, 0, hd_capture_size.height - 1)
    )


def try_preview_point_to_hd_capture(
    point: ScreenPoint,
    *,
    preview_size: ScreenSize,
    hd_capture_size: ScreenSize = THREEDS_HD_CAPTURE_SIZE,
) -> ScreenPoint | None:
    try:
        return preview_point_to_hd_capture(
            point,
            preview_size=preview_size,
            hd_capture_size=hd_capture_size,
        )
    except ValueError:
        return None


def preview_point_to_3ds_touch(
    point: ScreenPoint,
    *,
    preview_size: ScreenSize,
) -> TouchPoint:
    rect = preview_touch_rect(preview_size)
    quantized = _quantize_point(point, rect, THREEDS_TOUCH_SIZE)
    return TouchPoint(quantized.x, quantized.y)


def try_preview_point_to_3ds_touch(
    point: ScreenPoint,
    *,
    preview_size: ScreenSize,
) -> TouchPoint | None:
    try:
        return preview_point_to_3ds_touch(point, preview_size=preview_size)
    except ValueError:
        return None
