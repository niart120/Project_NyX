from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class FrameTransformConfig:
    aspect_box_enabled: bool = False
    background_bgr: tuple[int, int, int] = (0, 0, 0)

    def __post_init__(self) -> None:
        if len(self.background_bgr) != 3:
            raise ValueError("background_bgr must contain 3 channels")
        if any(channel < 0 or channel > 255 for channel in self.background_bgr):
            raise ValueError("background_bgr channels must be between 0 and 255")


class FrameTransformer:
    def transform(
        self,
        frame: cv2.typing.MatLike,
        config: FrameTransformConfig,
    ) -> cv2.typing.MatLike:
        if frame is None:
            raise ValueError("frame must not be None")
        height, width = frame.shape[:2]
        if width <= 0 or height <= 0:
            raise ValueError("frame size must be positive")
        if not config.aspect_box_enabled:
            return frame
        if width * 9 == height * 16:
            return frame

        if width * 9 < height * 16:
            target_width = (height * 16 + 8) // 9
            target_height = height
        else:
            target_width = width
            target_height = (width * 9 + 15) // 16

        result = np.full(
            (target_height, target_width, frame.shape[2]),
            config.background_bgr,
            dtype=frame.dtype,
        )
        x = (target_width - width) // 2
        y = (target_height - height) // 2
        result[y : y + height, x : x + width] = frame
        return result
