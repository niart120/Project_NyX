# 画像処理

NyX の画像処理 API は、OpenCV 画像に対するテンプレートマッチング、OCR、前処理の薄い入口です。OpenCV や PaddleOCR の一般的な使い方、モデル学習、NyX API を通らない画像処理手順は扱いません。

## 主な import

```python
from nyxpy.framework.core.imgproc import (
    ImagePreprocessor,
    ImageProcessor,
    OCRProcessor,
    contains_template,
    find_template,
)
```

## テンプレートマッチング

```python
result = find_template(frame, template, threshold=0.8)
cmd.log(f"match={result.confidence:.3f}", level="INFO")
```

`find_template()` は最良の一致を `MatchResult` として返します。画像が無効な場合は `InvalidImageError`、閾値に届かない場合は `ThresholdNotMetError`、OpenCV 側の失敗は `TemplateMatchingError` です。

単に含まれるかだけを見たい場合は `contains_template()` を使います。閾値未達は `False` として扱われます。無効画像や OpenCV 側の失敗は例外として送出されます。

## ImageProcessor

```python
processor = ImageProcessor(frame)
if processor.contains_template(template, threshold=0.85, preprocess=True):
    ...
```

`ImageProcessor` は 1 枚の画像を保持し、テンプレートマッチング、OCR、前処理込みの処理を呼び出すための入口です。コンストラクタには `None` や空画像を渡せません。

## OCR

```python
ocr = OCRProcessor.get_instance("ja")
text = ocr.get_best_text(frame)
digits = ocr.extract_digits(frame)
```

`OCRProcessor.get_instance(language)` は言語ごとに OCR エンジンをキャッシュします。PaddleOCR は初期化と初回推論に時間がかかるため、同じ言語では `get_instance()` を使います。`None` や空画像は `InvalidImageError`、PaddleOCR が利用できない場合は `OCREngineNotFoundError`、認識処理中の失敗は `OCRProcessingError` です。

## 前処理

`ImagePreprocessor` は次の処理を提供します。

| API | 用途 |
|-----|------|
| `enhance_contrast()` | CLAHE によるコントラスト強調 |
| `denoise()` | ノイズ除去 |
| `sharpen()` | アンシャープマスク |
| `binarize()` | 固定閾値または適応的閾値による二値化 |
| `enhance_for_template_matching()` | テンプレートマッチング向け前処理 |
| `enhance_for_ocr()` | OCR 向け前処理 |

前処理はゲーム画面の認識を補助するためのものです。認識精度は入力画像、テンプレート、閾値に依存するため、ロジック部分を関数化してテストできる形にします。
