"""画像認識ヘルパー

OCR によるポケモン名・アイテム名認識と、
輝度判定によるメッセージウィンドウ検出を提供する。
仕様: spec/macro/frlg_gorgeous_resort/spec.md §4
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import cv2
import numpy as np

from nyxpy.framework.core.imgproc import ImageProcessor

if TYPE_CHECKING:
    from nyxpy.framework.core.macro.command import Command

# ============================================================
# ROI 定義 (Switch / JPN / 720p)
# ============================================================

# ポケモン名表示領域 (Switch / JPN / 720p)
ROI_POKEMON_NAME: tuple[int, int, int, int] = (200, 590, 335, 70)

# アイテム取得テキスト表示領域 — 実機計測で確定すること (TBD)
ROI_ITEM_NAME: tuple[int, int, int, int] = (200, 480, 500, 50)

# メッセージウィンドウ検出用 ROI
ROI_MESSAGE: tuple[int, int, int, int] = (1056, 474, 89, 223)

# ============================================================
# 定数
# ============================================================

_PADDING: int = 40  # 白パディング (px)

_MESSAGE_BRIGHTNESS_THRESHOLD: float = 240.0

_FUZZY_THRESHOLD: int = 1  # 編集距離の許容閾値

ITEM_NAMES: list[str] = [
    "ゴージャスボール",
    "おおきなしんじゅ",
    "しんじゅ",
    "ほしのすな",
    "ほしのかけら",
    "きんのたま",
    "ふしぎなアメ",
]

BAG_FULL_KEYWORD: str = "おかばん"


# ============================================================
# 共通 OCR ヘルパー
# ============================================================


def _crop_and_pad(
    image: np.ndarray,
    roi: tuple[int, int, int, int],
    pad: int = _PADDING,
) -> np.ndarray:
    """ROI クロップ → 白パディング付与。"""
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


def save_roi_image(
    image: np.ndarray,
    roi: tuple[int, int, int, int],
    path: Path,
) -> None:
    """ROI をクロップし白パディングを付与して保存する（毎回上書き）。"""
    padded = _crop_and_pad(image, roi)
    cv2.imwrite(str(path), padded)


def ocr_roi(
    cmd: "Command",
    roi: tuple[int, int, int, int],
    pad: int = _PADDING,
    *,
    img_path: Path | None = None,
) -> str | None:
    """指定 ROI をクロップし、OCR でテキストを返す。"""
    image = cmd.capture()
    padded = _crop_and_pad(image, roi, pad)
    if img_path is not None:
        cv2.imwrite(str(img_path), padded)
    text = ImageProcessor(padded).get_text(language="ja")
    return text.strip() if text else None


# ============================================================
# ポケモン名認識
# ============================================================


def recognize_requested_pokemon(
    cmd: "Command", *, img_dir: Path | None = None
) -> str | None:
    """アキホのダイアログからポケモン名を OCR で読み取る。"""
    return ocr_roi(cmd, ROI_POKEMON_NAME, img_path=img_dir and img_dir / "pokemon_name.png")


def _edit_distance(s1: str, s2: str) -> int:
    """2 つの文字列間のレーベンシュタイン距離を返す。"""
    if len(s1) < len(s2):
        return _edit_distance(s2, s1)

    prev = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr = [i + 1]
        for j, c2 in enumerate(s2):
            cost = 0 if c1 == c2 else 1
            curr.append(min(prev[j + 1] + 1, curr[j] + 1, prev[j] + cost))
        prev = curr

    return prev[len(s2)]


def matches_any_target(recognized: str, target_pokemon: list[str]) -> bool:
    """OCR 認識結果が target_pokemon リスト内のいずれかと一致するか判定する。"""
    for target in target_pokemon:
        if recognized == target:
            return True
        if _edit_distance(recognized, target) <= _FUZZY_THRESHOLD:
            return True
    return False


# ============================================================
# アイテム認識
# ============================================================


def recognize_item(cmd: "Command", *, img_dir: Path | None = None) -> str | None:
    """アイテム取得テキストを OCR で読み取り、アイテム名を返す。

    Returns:
        アイテム名、"BAG_FULL"、または認識失敗時は None
    """
    text = ocr_roi(cmd, ROI_ITEM_NAME, img_path=img_dir and img_dir / "item_name.png")
    if text is None:
        return None
    return match_item(text)


def match_item(ocr_text: str) -> str | None:
    """OCR テキストからアイテム名を突合する。"""
    if BAG_FULL_KEYWORD in ocr_text:
        return "BAG_FULL"

    # 長い名前から順に照合（部分一致）
    for name in sorted(ITEM_NAMES, key=len, reverse=True):
        if name in ocr_text:
            return name

    return None


# ============================================================
# メッセージウィンドウ検出（輝度判定）
# ============================================================


def is_message_window_visible(cmd: "Command") -> bool:
    """メッセージウィンドウの有無を ROI 内平均輝度で検出する。"""
    image = cmd.capture()
    x, y, w, h = ROI_MESSAGE
    cropped = image[y : y + h, x : x + w]
    gray = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
    mean_brightness = float(np.mean(gray))
    return mean_brightness > _MESSAGE_BRIGHTNESS_THRESHOLD
