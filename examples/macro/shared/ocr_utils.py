"""OCR ユーティリティ。

OCR エンジンのウォームアップなど、マクロの initialize フェーズで使う
共通処理を提供する。
"""

from __future__ import annotations

import numpy as np

from nyxpy.framework.core.imgproc import OCRProcessor
from nyxpy.framework.core.macro.command import Command


def warmup_ocr(cmd: Command, language: str = "en") -> None:
    """OCR エンジンを事前に起動し、初回認識のレイテンシを解消する。

    :param cmd: コマンドインターフェース（log のみ使用）
    :param language: ウォームアップ対象の言語コード
    """
    cmd.log(f"OCR ウォームアップ開始 (lang={language})", level="INFO")
    ocr = OCRProcessor.get_instance(language)
    try:
        ocr.get_best_text(np.zeros((64, 200, 3), dtype=np.uint8))
    except Exception:
        pass
    cmd.log("OCR ウォームアップ完了", level="INFO")
