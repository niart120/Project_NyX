"""画像認識ラッパー

ステータスの OCR 認識を担当する。
NyX フレームワークの ImageProcessor / OCRProcessor を使用する。
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import cv2

from macros.shared.image_utils import crop_and_pad as _shared_crop_and_pad
from nyxpy.framework.core.imgproc import ImageProcessor

if TYPE_CHECKING:
    import numpy as np


# ============================================================
# ROI 定義 (Switch / JPN / 720p)
# ============================================================

# ステータス ROI: (x, y, w, h) — HP, Atk, Def, SpA, SpD, Spe の順
ROI_STATS: tuple[tuple[int, int, int, int], ...] = (
    (1015, 90, 155, 60),   # HP
    (1005, 170, 170, 60),  # こうげき
    (1005, 225, 170, 60),  # ぼうぎょ
    (1005, 280, 170, 60),  # とくこう
    (1005, 335, 170, 60),  # とくぼう
    (1005, 390, 170, 60),  # すばやさ
)

_STAT_KEYS = ("HP", "Atk", "Def", "SpA", "SpD", "Spe")

_PADDING = 80  # 白パディング (px)


def calc_stat_valid_ranges(
    base_stats: tuple[int, int, int, int, int, int],
    level: int,
) -> dict[str, tuple[int, int]]:
    """種族値・レベルから各ステータスの有効範囲 (EV=0, IV=0〜31, 性格補正考慮) を返す。

    HP 以外は性格補正 0.9〜1.1 を考慮した広い範囲を返す。
    """
    b_hp, b_atk, b_def, b_spa, b_spd, b_spe = base_stats

    def _hp_range(base: int) -> tuple[int, int]:
        lo = ((2 * base) * level) // 100 + level + 10
        hi = ((2 * base + 31) * level) // 100 + level + 10
        return lo, hi

    def _stat_range(base: int) -> tuple[int, int]:
        lo = int(((2 * base) * level // 100 + 5) * 0.9)
        hi = int(((2 * base + 31) * level // 100 + 5) * 1.1)
        return lo, hi

    return {
        "HP":  _hp_range(b_hp),
        "Atk": _stat_range(b_atk),
        "Def": _stat_range(b_def),
        "SpA": _stat_range(b_spa),
        "SpD": _stat_range(b_spd),
        "Spe": _stat_range(b_spe),
    }

# ============================================================
# 認識関数
# ============================================================


def crop_and_pad(
    image: np.ndarray, roi: tuple[int, int, int, int]
) -> np.ndarray:
    """ROI クロップ → 白パディング付与。"""
    return _shared_crop_and_pad(image, roi, pad=_PADDING)


def get_stat_digits(
    image: np.ndarray,
) -> tuple[str | None, str | None, str | None, str | None, str | None, str | None]:
    """ステータス 6 項目の OCR 生文字列を取得する。"""
    raw: list[str | None] = []
    for roi in ROI_STATS:
        padded = crop_and_pad(image, roi)
        digits = ImageProcessor(padded).get_digits(language="en")
        raw.append(digits if digits else None)

    return (raw[0], raw[1], raw[2], raw[3], raw[4], raw[5])


def recognize_stats(
    image: np.ndarray,
    base_stats: tuple[int, int, int, int, int, int],
    level: int,
) -> tuple[int, int, int, int, int, int] | None:
    """キャプチャ画像から6ステータスの実数値を OCR 認識する。

    Args:
        image: キャプチャ画像 (BGR)
        base_stats: 対象ポケモンの種族値 (HP, Atk, Def, SpA, SpD, Spe)
        level: 対象ポケモンのレベル

    Returns:
        (HP, Atk, Def, SpA, SpD, Spe) のタプル、または認識失敗時は None
    """
    valid_ranges = calc_stat_valid_ranges(base_stats, level)
    values: list[int] = []
    raw_digits = get_stat_digits(image)

    for i, digits in enumerate(raw_digits):
        if not digits:
            return None

        try:
            value = int(digits)
        except ValueError:
            return None

        # 有効範囲チェック (種族値・レベルから導出)
        key = _STAT_KEYS[i]
        lo, hi = valid_ranges[key]
        if not (lo <= value <= hi):
            return None

        values.append(value)

    return (values[0], values[1], values[2], values[3], values[4], values[5])


# ============================================================
# 画像保存ヘルパー
# ============================================================


def save_roi_image(
    image: np.ndarray,
    roi: tuple[int, int, int, int],
    path: Path,
) -> None:
    """ROI をクロップし白パディングを付与して保存する（毎回上書き）。"""
    padded = crop_and_pad(image, roi)
    cv2.imwrite(str(path), padded)
