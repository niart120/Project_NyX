"""
TID 画像認識モジュール

トレーナーカード画面のキャプチャから TID (0–65535) を OCR で読み取る。
"""

from __future__ import annotations

import re

import cv2

from nyxpy.framework.core.imgproc import ImageProcessor


def recognize_tid(
    image: cv2.typing.MatLike,
    roi: tuple[int, int, int, int],
) -> int | None:
    """キャプチャ画像から TID を OCR で認識する。

    :param image: 1280×720 のキャプチャ画像
    :param roi: TID 表示領域 (x, y, w, h)
    :return: 認識成功時は TID (0–65535)、失敗時は ``None``
    """
    x, y, w, h = roi
    cropped = image[y : y + h, x : x + w]

    processor = ImageProcessor(cropped)
    raw_text = processor.get_text(language="en", preprocess=True)

    # 数字のみを抽出
    digits = re.sub(r"\D", "", raw_text)
    if not digits:
        return None

    value = int(digits)
    if value < 0 or value > 65535:
        return None

    return value
