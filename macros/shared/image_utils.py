"""画像処理ユーティリティ。

ROI クロップ・パディングなど、複数マクロで共通する画像前処理を提供する。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import cv2

if TYPE_CHECKING:
    import numpy as np

_DEFAULT_PADDING: int = 40


def crop_and_pad(
    image: "np.ndarray",
    roi: tuple[int, int, int, int],
    pad: int = _DEFAULT_PADDING,
) -> "np.ndarray":
    """ROI をクロップし白パディングを付与して返す。

    :param image: 入力画像 (H×W×C)
    :param roi: (x, y, w, h) の切り出し矩形
    :param pad: 付与する白パディング幅 (px)
    :return: パディング済み画像
    """
    x, y, w, h = roi
    cropped = image[y : y + h, x : x + w]
    return cv2.copyMakeBorder(
        cropped,
        pad,
        pad,
        pad,
        pad,
        borderType=cv2.BORDER_CONSTANT,
        value=(255, 255, 255),
    )
