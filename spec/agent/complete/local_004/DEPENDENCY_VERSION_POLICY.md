# 依存ライブラリ更新方針仕様書

> **対象モジュール**: `pyproject.toml`, `uv.lock`
> **目的**: 依存ライブラリの下限・上限・脆弱性制約を、検証済みロックファイルと整合させる。
> **関連ドキュメント**: `spec/dev-journal.md`
> **既存ソース**: `pyproject.toml`, `uv.lock`, `tests/unit/imgproc/test_ocr_processor.py`
> **破壊的変更**: なし

## 1. 概要

### 1.1 目的

`uv.lock` で検証した依存ライブラリの版を `pyproject.toml` の制約に反映し、再解決時に未検証の古い版へ戻らないようにする。OCR 系依存は PaddlePaddle の既知回帰を避けつつ PaddleOCR 3.5 系へ更新する。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| 直接依存 | `pyproject.toml` の `[project].dependencies` または `[dependency-groups]` に明記する依存 |
| 推移依存 | 直接依存が要求する依存。`urllib3` は `requests` などから解決される |
| 検証済み下限 | `uv.lock` で解決し、テストを通した版を下限として採用する制約 |
| OCR 系依存 | `paddlepaddle`, `paddleocr`, `paddlex`, `numpy` を中心とした OCR 実行スタック |
| 脆弱性制約 | `tool.uv.constraint-dependencies` で、推移依存を修正版以上に固定する制約 |

### 1.3 背景・問題

`uv.lock` は `paddleocr 3.5.0` などを解決していても、`pyproject.toml` の下限が古いままだと環境再構築時に未検証の古い版を許容する。PaddlePaddle 3.3.0/3.3.1 には oneDNN/PIR 回帰があり、`urllib3` には 2.7.0 未満を避けるべき脆弱性がある。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| OCR 系下限 | `paddleocr>=3.0.0`, `paddlepaddle>=3.0.0` | 検証済みの `paddleocr>=3.5.0,<3.6.0`, `paddlepaddle>=3.2.2,<3.3.0` |
| `numpy` 解決範囲 | `>=2.0.0` | PaddleX 3.5.2 要件に合わせ `>=2.3.5,<2.4.0` |
| `urllib3` 脆弱性制約 | なし | `urllib3>=2.7.0` を推移依存制約として保持 |
| 直接依存下限 | ロック済み版より古い下限が混在 | 検証済みロック版を下限に採用 |
| 開発依存下限 | `pytest-cov>=6.1.1`, `pytest-qt>=4.4.0`, `ruff>=0.11.7` | 検証済みの `pytest-cov>=7.1.0`, `pytest-qt>=4.5.0`, `ruff>=0.15.12` |

### 1.5 着手条件

- `uv lock --upgrade` で最新解決候補を確認すること。
- `paddlepaddle<3.3.0` の理由として `0e99613` の oneDNN 回帰メモを確認すること。
- `urllib3 2.7.0` が OSV で既知脆弱性なしであることを確認すること。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `pyproject.toml` | 変更 | 直接依存・開発依存の下限、OCR 系上限、`urllib3` 脆弱性制約を更新する |
| `uv.lock` | 変更 | 依存解決結果を最新化する |
| `spec/agent/complete/local_004/DEPENDENCY_VERSION_POLICY.md` | 新規 | 依存更新判断を仕様化する |
| `spec/dev-journal.md` | 変更 | 仕様化済みの一時メモを削除する |

## 3. 設計方針

### アーキテクチャ上の位置づけ

依存管理はフレームワーク実行基盤の前提条件であり、GUI / CLI / マクロからは直接参照しない。制約は `pyproject.toml` に集約し、`uv.lock` は検証済み環境の記録として扱う。

### 公開 API 方針

公開 Python API の変更は行わない。依存制約だけを変更し、`OCRProcessor` の呼び出し API は維持する。

### 後方互換性

破壊的変更はない。PaddlePaddle 3.3 系は既知回帰を避けるため許容しないが、これは既存上限 `<3.3.0` の維持である。

### レイヤー構成

依存制約は `pyproject.toml` に限定する。推移依存の脆弱性対策は直接依存に昇格せず、`tool.uv.constraint-dependencies` で制御する。

### 性能要件

| 指標 | 目標値 |
|------|--------|
| OCR 初期化・推論 | 既存テスト `test_ocr_processor.py` が成功すること |
| 依存解決 | `uv lock` が追加操作なしで成功すること |

### 並行性・スレッド安全性

該当なし。依存制約の変更であり、実行時のスレッドモデルは変更しない。

## 4. 実装仕様

### 公開インターフェース

公開 API の追加・削除はない。依存制約は次の TOML 断片で管理する。

```toml
dependencies = [
    "paddlepaddle>=3.2.2,<3.3.0",
    "paddleocr>=3.5.0,<3.6.0",
    "numpy>=2.3.5,<2.4.0",
]

[tool.uv]
constraint-dependencies = [
    "urllib3>=2.7.0",
    "ujson>=5.12.0",
]
```

### 設定パラメータ

| パラメータ | 型 | デフォルト | 説明 |
|------------|-----|-----------|------|
| `paddlepaddle` | version specifier | `>=3.2.2,<3.3.0` | oneDNN/PIR 回帰を含む 3.3.0/3.3.1 を避ける |
| `paddleocr` | version specifier | `>=3.5.0,<3.6.0` | PaddleOCR 3.5 系を検証対象にする |
| `numpy` | version specifier | `>=2.3.5,<2.4.0` | PaddleX 3.5.2 の `numpy<2.4` 要件に合わせる |
| `requests` | version specifier | `>=2.34.0,<3.0.0` | `urllib3 2.7.0` と合わせて HTTP 系依存を更新する |
| `pyside6` | version specifier | `>=6.11.0,<7.0.0` | GUI 基盤をロック済み 6.11 系に合わせる |
| `opencv-python` | version specifier | `>=4.13.0.92,<5.0.0.0` | 画像処理基盤をロック済み 4.13 系に合わせる |
| `cv2-enumerate-cameras` | version specifier | `>=1.3.3,<2.0.0.0` | キャプチャデバイス列挙依存をロック済み版に合わせる |
| `tomlkit` | version specifier | `>=0.13.3,<0.14.0` | 設定ファイル編集依存をロック済み版に合わせる |
| `setuptools` | version specifier | `>=82.0.1` | PaddlePaddle の実行時依存をロック済み版に合わせる |
| `chardet` | version specifier | `>=5.2.0,<6.0.0` | 文字コード判定依存をロック済み版に合わせる |
| `pytest-cov` | version specifier | `>=7.1.0` | 開発依存をロック済み版に合わせる |
| `pytest-qt` | version specifier | `>=4.5.0` | GUI テスト依存をロック済み版に合わせる |
| `ruff` | version specifier | `>=0.15.12` | 静的検査をロック済み版に合わせる |
| `urllib3` | constraint specifier | `>=2.7.0` | CVE-2026-21441 / CVE-2026-44432 対策として推移依存を制約する |

### エラーハンドリング

| 例外クラス | 発生条件 |
|------------|----------|
| 該当なし | 実装コードの例外処理は変更しない |

### シングルトン管理

該当なし。新規 singleton は追加しない。

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| ユニット | `tests/unit/imgproc/test_ocr_processor.py::TestOCRProcessorInit::test_init_en_succeeds` | OCR エンジン初期化が成功すること |
| ユニット | `tests/unit/imgproc/test_ocr_processor.py::TestRecognizeText::test_detects_digits` | PaddleOCR 3.5 系で推論が成功すること |
| ユニット | `tests/unit/` | 依存更新後に既存単体テストが破壊されないこと |
| 静的検査 | `uv run ruff check .` | ruff 0.15.12 で既存コードが通ること |
| 脆弱性確認 | OSV query for `urllib3==2.7.0` | `urllib3 2.7.0` に既知脆弱性が返らないこと |
| 脆弱性確認 | `uvx pip-audit -r <uv export output>` | `uv.lock` 由来の requirements に既知脆弱性がないこと |

## 6. 実装チェックリスト

- [x] 直接依存の下限を検証済みロック版に整理
- [x] OCR 系依存の上限・下限を整理
- [x] `urllib3>=2.7.0` の推移依存制約を追加
- [x] `uv.lock` を再解決
- [x] `uv.lock` 由来の requirements を `pip-audit` で監査
- [x] OCR 初期化・推論テスト作成済みテストで確認
- [x] 既存単体テストが破壊されないことの確認
- [x] ruff による静的検査
