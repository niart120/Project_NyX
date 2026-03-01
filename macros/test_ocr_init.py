"""
PaddleOCR 初期化テストマクロ

PaddleOCR のモデルダウンロードと初期化が正常に行えるか確認する。
キャプチャ画像に対して OCR を実行し、結果をログに出力する。
"""

import numpy as np

from nyxpy.framework.core.macro.base import MacroBase
from nyxpy.framework.core.macro.command import Command


class TestOcrInitMacro(MacroBase):
    description = "PaddleOCR の初期化・モデルダウンロードを確認するテストマクロ"
    tags = ["test", "ocr", "debug"]

    def initialize(self, cmd: Command, args: dict) -> None:
        self.lang = str(args.get("lang", "en"))
        cmd.log(f"OCR テスト開始: lang={self.lang}")

    def run(self, cmd: Command) -> None:
        # --- Step 1: PaddleOCR の初期化（モデルダウンロードが走る） ---
        cmd.log("Step 1: PaddleOCR を初期化します...")
        try:
            from nyxpy.framework.core.imgproc import OCRProcessor
            ocr = OCRProcessor(language=self.lang)
            cmd.log("PaddleOCR の初期化に成功しました")
        except Exception as e:
            cmd.log(f"PaddleOCR の初期化に失敗しました: {e}")
            return

        # --- Step 2: ダミー画像で OCR を実行 ---
        cmd.log("Step 2: ダミー画像で OCR を実行します...")
        dummy = np.zeros((100, 300, 3), dtype=np.uint8)
        # 白背景に黒テキスト風のダミー
        dummy[:] = (255, 255, 255)
        try:
            results = ocr.recognize_text(dummy)
            cmd.log(f"  ダミー画像 OCR 結果: {len(results)} 件")
        except Exception as e:
            cmd.log(f"  ダミー画像 OCR でエラー: {e}")

        # --- Step 3: キャプチャ画像で OCR を実行 ---
        cmd.log("Step 3: キャプチャ画像で OCR を実行します...")
        frame = cmd.capture()
        if frame is not None:
            try:
                from nyxpy.framework.core.imgproc import ImageProcessor
                processor = ImageProcessor(frame)
                text = processor.get_text(language=self.lang, preprocess=True)
                cmd.log(f"  キャプチャ OCR 結果: '{text}'")
            except Exception as e:
                cmd.log(f"  キャプチャ OCR でエラー: {e}")
        else:
            cmd.log("  キャプチャ取得不可（デバイス未接続）")

        cmd.log("OCR テスト完了")

    def finalize(self, cmd: Command) -> None:
        cmd.release()
        cmd.log("TestOcrInitMacro finalized")
