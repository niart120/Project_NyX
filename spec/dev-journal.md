# Dev Journal

実装中の設計上の気づき・疑問・バックログ送りタスクの記録。

## 2026-05-13: PaddlePaddle を含む依存ライブラリ更新

### 現状

`pyproject.toml` は `paddlepaddle>=3.0.0,<3.3.0` と `paddleocr>=3.0.0` を指定し、`uv.lock` は `paddlepaddle 3.2.2` / `paddleocr 3.4.0` を解決している。

### 観察

`tests\unit\imgproc\test_ocr_processor.py::TestOCRProcessorInit::test_init_en_succeeds` で PaddlePaddle の `No ccache found` warning が出ており、PaddlePaddle 側では PR `PaddlePaddle/Paddle#77116` で通常 import 時の ccache 探索を遅延化している。

### 方針

PaddlePaddle / PaddleOCR を含む依存更新を別タスクで検討し、過去に `paddlepaddle` の上限を `<3.3.0` にした理由を確認したうえで OCR 初期化テストと CI warning の扱いを見直す。
