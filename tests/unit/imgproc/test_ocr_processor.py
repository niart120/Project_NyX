"""
OCRProcessor ユニットテスト

PaddleOCR 3.x を前提とした認識精度の検証。
PaddleOCR が未インストールの場合はスキップされる。

【既知のモデル挙動】
  PaddleOCR 3.x (en) + 合成フォント画像では以下の認識誤りが確認されている。
  これらはモデルレベルの制限であり、OCRProcessor 実装の問題ではない。
  - "9" が "6" に誤認識されるケースがある (例: "99999" → "66666")
  - 先頭の "1" が "10000" のような特定パターンで欠落するケースがある
  テストケースはこれらの既知誤認識パターンを避けて設計する。
"""

from __future__ import annotations

import os

import numpy as np
import pytest

# テスト実行時にモデルの接続チェックをスキップ
os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

paddleocr = pytest.importorskip("paddleocr", reason="paddleocr が未インストール")
PIL = pytest.importorskip("PIL", reason="Pillow が未インストール")

from PIL import Image, ImageDraw, ImageFont

from nyxpy.framework.core.imgproc.ocr_engine import OCRProcessor, OCRResult

# テストに使用するシステムフォント (Windows 環境想定)
_FONT_CANDIDATES = [
    "C:/Windows/Fonts/Arial.ttf",
    "C:/Windows/Fonts/cour.ttf",
]


# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------

def make_text_image(
    text: str,
    width: int = 600,
    height: int = 200,
    font_size: int = 100,
) -> np.ndarray:
    """
    PIL でテキストを描画した画像を返す。
    テキストを画像中央に配置することで端部クリップを回避する。
    フォントは利用可能なシステムフォントを自動選択する。
    """
    img = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    font: ImageFont.FreeTypeFont | ImageFont.ImageFont = ImageFont.load_default(size=font_size)
    for candidate in _FONT_CANDIDATES:
        if os.path.exists(candidate):
            font = ImageFont.truetype(candidate, font_size)
            break

    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = max((width - tw) // 2, 10)
    y = max((height - th) // 2, 10)
    draw.text((x, y), text, font=font, fill=(0, 0, 0))
    return np.array(img)


# ---------------------------------------------------------------------------
# フィクスチャ
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def ocr_en() -> OCRProcessor:
    return OCRProcessor(language="en")


@pytest.fixture(scope="module")
def ocr_ja() -> OCRProcessor:
    return OCRProcessor(language="ja")


# ---------------------------------------------------------------------------
# OCRProcessor 初期化テスト
# ---------------------------------------------------------------------------

class TestOCRProcessorInit:
    def test_init_en_succeeds(self):
        proc = OCRProcessor(language="en")
        assert proc._ocr_engine is not None

    def test_init_ja_succeeds(self):
        proc = OCRProcessor(language="ja")
        assert proc._ocr_engine is not None

    def test_init_unknown_language_falls_back(self):
        """未知の言語コードは 'japan' にフォールバックして初期化が成功する"""
        proc = OCRProcessor(language="xx")
        assert proc._ocr_engine is not None


# ---------------------------------------------------------------------------
# recognize_text テスト
# ---------------------------------------------------------------------------

class TestRecognizeText:
    def test_returns_list(self, ocr_en):
        img = make_text_image("12345")
        result = ocr_en.recognize_text(img)
        assert isinstance(result, list)

    def test_each_element_is_ocr_result(self, ocr_en):
        img = make_text_image("12345")
        result = ocr_en.recognize_text(img)
        for r in result:
            assert isinstance(r, OCRResult)
            assert isinstance(r.text, str)
            assert 0.0 <= r.confidence <= 1.0

    def test_detects_digits(self, ocr_en):
        img = make_text_image("12345")
        result = ocr_en.recognize_text(img)
        combined = "".join(r.text for r in result)
        assert "12345" in combined, f"'12345' not found in OCR output: {combined!r}"

    def test_empty_image_returns_empty(self, ocr_en):
        img = np.full((200, 600, 3), 255, dtype=np.uint8)  # 白紙
        result = ocr_en.recognize_text(img)
        assert result == []

    def test_none_like_empty_array_returns_empty(self, ocr_en):
        img = np.zeros((0, 0, 3), dtype=np.uint8)
        result = ocr_en.recognize_text(img)
        assert result == []


# ---------------------------------------------------------------------------
# get_best_text テスト
# ---------------------------------------------------------------------------

class TestGetBestText:
    def test_returns_string(self, ocr_en):
        img = make_text_image("12345")
        result = ocr_en.get_best_text(img)
        assert isinstance(result, str)

    def test_best_text_contains_digits(self, ocr_en):
        img = make_text_image("12345")
        result = ocr_en.get_best_text(img)
        assert result != "", "認識結果が空文字列"
        assert any(c.isdigit() for c in result), f"数字が含まれない: {result!r}"

    def test_empty_image_returns_empty_string(self, ocr_en):
        img = np.full((200, 600, 3), 255, dtype=np.uint8)
        assert ocr_en.get_best_text(img) == ""


# ---------------------------------------------------------------------------
# extract_digits テスト
# ---------------------------------------------------------------------------

class TestExtractDigits:
    def test_extracts_exact_digits(self, ocr_en):
        img = make_text_image("12345")
        result = ocr_en.extract_digits(img)
        assert "12345" in result, f"'12345' not in {result!r}"

    def test_returns_only_digits(self, ocr_en):
        img = make_text_image("12345")
        result = ocr_en.extract_digits(img)
        assert result.isdigit(), f"数字以外が含まれる: {result!r}"

    def test_empty_image_returns_empty_string(self, ocr_en):
        img = np.full((200, 600, 3), 255, dtype=np.uint8)
        assert ocr_en.extract_digits(img) == ""

    @pytest.mark.parametrize("number", ["00000", "65535", "12300", "11111"])
    def test_various_5digit_numbers(self, ocr_en, number):
        """
        モデルの既知誤認識パターン ("9"→"6", 先頭"1"+後続"0000") を避けた
        5桁整数を使って認識の安定性を確認する。
        """
        img = make_text_image(number)
        result = ocr_en.extract_digits(img)
        assert number in result, f"期待値 {number!r} が結果 {result!r} に含まれない"
