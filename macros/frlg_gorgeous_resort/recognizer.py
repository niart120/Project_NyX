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

from macros.shared.image_utils import crop_and_pad

if TYPE_CHECKING:
    from nyxpy.framework.core.macro.command import Command

# ============================================================
# ROI 定義 (Switch / JPN / 720p)
# ============================================================

# ポケモン名表示領域 (Switch / JPN / 720p)
# 文字数により表示幅が変わるため、複数の横幅で OCR を試行する
ROI_POKEMON_NAME_BASE: tuple[int, int, int] = (200, 590, 70)  # (x, y, h)
ROI_POKEMON_NAME_WIDTHS: tuple[int, ...] = (120, 190, 260, 330)

# アイテム取得テキスト表示領域 — 実機計測で確定する
ROI_ITEM_NAME: tuple[int, int, int, int] = (200, 520, 640, 70)

# メッセージウィンドウ検出用 ROI
ROI_MESSAGE: tuple[int, int, int, int] = (1056, 474, 89, 223)

# ============================================================
# 定数
# ============================================================

_PADDING: int = 40  # 白パディング (px)

_MESSAGE_BRIGHTNESS_THRESHOLD: float = 240.0

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
# OCR ヘルパー
# ============================================================


def save_roi_image(
    image: np.ndarray,
    roi: tuple[int, int, int, int],
    path: Path,
) -> None:
    """ROI をクロップし白パディングを付与して保存する（毎回上書き）。"""
    padded = crop_and_pad(image, roi, pad=_PADDING)
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
    padded = crop_and_pad(image, roi, pad)
    if img_path is not None:
        cv2.imwrite(str(img_path), padded)
    text = ImageProcessor(padded).get_text(language="ja")
    return text.strip() if text else None


# ============================================================
# ポケモン名認識
# ============================================================


def recognize_requested_pokemon(
    cmd: "Command",
    target_pokemon: list[str],
    *,
    img_dir: Path | None = None,
) -> str | None:
    """アキホのダイアログからポケモン名を OCR で読み取る。

    ROI の横幅を 4 段階で切り替えながら OCR を試行し、
    target_pokemon との部分文字列マッチに成功した時点で結果を返す。
    いずれの幅でもマッチしない場合は最後の試行結果を返す。
    """
    x, y, h = ROI_POKEMON_NAME_BASE
    image = cmd.capture()
    last_text: str | None = None

    for w in ROI_POKEMON_NAME_WIDTHS:
        roi = (x, y, w, h)
        padded = crop_and_pad(image, roi, pad=_PADDING)
        if img_dir is not None:
            cv2.imwrite(str(img_dir / f"pokemon_name_w{w}.png"), padded)
        text = ImageProcessor(padded).get_text(language="ja")
        text = text.strip() if text else None
        matched = text is not None and matches_any_target(text, target_pokemon)
        cmd.log(f"OCR w={w}: '{text}' matched={matched}", level="DEBUG")
        if text is not None:
            last_text = text
            if matched:
                return text

    return last_text


def matches_any_target(recognized: str, target_pokemon: list[str]) -> bool:
    """OCR 認識結果が target_pokemon リスト内のいずれかを含むか判定する。

    recognized の部分文字列として target が出現するかを検証する。
    """
    for target in target_pokemon:
        if target in recognized:
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
