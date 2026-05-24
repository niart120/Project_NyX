# ty 型検査厳格化仕様

## 1. 目的

`py.typed` 追加後に利用者へ公開される型ヒントの妥当性を高める。`ty` を段階的に適用し、最終的に `src\nyxpy` の型検査を CI gate にできる状態へ進める。

## 2. 現状

| 項目 | 状態 |
|------|------|
| 型検査器 | `ty>=0.0.39` を dev dependency に追加済み |
| PEP 561 marker | `src\nyxpy\py.typed` を追加済み |
| 全体 baseline | `uv run ty check src\nyxpy --output-format concise --no-progress` で 0 diagnostics |
| 公開 API 周辺 baseline | macro / constants / imgproc / resources 対象で 0 diagnostics |
| CI gate | 未適用 |

公開 API 周辺 baseline の取得コマンド:

```powershell
uv run ty check src\nyxpy\framework\core\macro src\nyxpy\framework\core\constants src\nyxpy\framework\core\imgproc src\nyxpy\framework\core\io\resources.py --output-format concise --no-progress
```

## 3. 設計方針

### 3.1 公開 API から直す

`py.typed` により、利用者は `nyxpy.framework.*` の型ヒントを見る。GUI や内部 runtime より先に、マクロ実装者が直接 import する API を通す。

### 3.2 suppression より型の修正を優先する

`ty: ignore` は使わない方針を既定にする。外部ライブラリ stub の誤差や、ty 側の未成熟な診断であることを確認した場合だけ、対象範囲を限定して保留する。

### 3.3 動的属性を公開 API にしない

`LStick.UP` のような実行時代入は補完・型検査に弱い。公開定数として使わせる値は class body 内の `ClassVar`、module-level constant、または明示的な factory に寄せる。

### 3.4 CI gate は小さい範囲から始める

最初から `src\nyxpy` 全体を gate にしない。0 diagnostics になった範囲だけ CI に追加し、範囲を広げる。

## 4. 段階計画

| Phase | 対象 | 目的 | 完了条件 |
|-------|------|------|----------|
| 0 | baseline 文書化 | 現状の診断数と分類を固定する | 本仕様書を追加し、baseline コマンドを明記する |
| 1 | `constants` | マクロで最初に参照される Button / stick / keyboard の型を安定させる | `uv run ty check src\nyxpy\framework\core\constants --output-format concise --no-progress` が 0 diagnostics |
| 2 | `macro` | `MacroBase`, `Command`, registry, settings resolver の型を通す | `uv run ty check src\nyxpy\framework\core\macro --output-format concise --no-progress` が 0 diagnostics |
| 3 | `imgproc` | `ImageProcessor`, OCR, template matching の `None` / OpenCV 型を整理する | `uv run ty check src\nyxpy\framework\core\imgproc --output-format concise --no-progress` が 0 diagnostics |
| 4 | `resources` | resources / outputs の context manager と `BinaryIO` 型を整理する | `uv run ty check src\nyxpy\framework\core\io\resources.py --output-format concise --no-progress` が 0 diagnostics |
| 5 | 公開 API bundle | マクロ利用者が直接使う面をまとめて gate 化する | 公開 API 周辺 baseline コマンドが 0 diagnostics |
| 6 | `src\nyxpy\framework\core` | runtime / hardware / logger / settings を含めて framework core を通す | `uv run ty check src\nyxpy\framework\core --output-format concise --no-progress` が 0 diagnostics |
| 7 | `src\nyxpy` | CLI / GUI を含む package 全体を通す | `uv run ty check src\nyxpy --output-format concise --no-progress` が 0 diagnostics |
| 8 | CI gate | 0 diagnostics の範囲を CI に追加する | `.github\workflows\test.yml` または専用 workflow で `ty check` が必須になる |

## 5. 診断分類と対応方針

| 分類 | 代表例 | 対応方針 |
|------|--------|----------|
| `None` 非許容の型注釈 | `Command.capture(crop_region=None)`, `Command.notify(img=None)` | `None` が既定値や添付なしを表す場合は `T | None` にする。失敗を表す `None` は例外に寄せ、マクロ作者向け API へ optional を広げない |
| 動的 class 属性 | `LStick.UP`, `RStick.CENTER` | `ClassVar` 宣言または module-level constant に移す。公開 API と docs を同時に更新する |
| 外部ライブラリ optional state | `OCRProcessor.ocr` が `None | PaddleOCR` | 初期化後に `None` でないことを guard し、局所変数へ束縛してから使う |
| OpenCV / NumPy shape 型 | `max_loc` が `Sequence[int]` | 必要なら `tuple[int, int]` へ明示変換する |
| context manager / IO 型 | `_AtomicOutputFile` と `BinaryIO` | Protocol または戻り値型を実際の context manager に合わせる |
| exception kwargs | `FrameworkError.__init__` へ渡す `object` | `TypedDict`、明示引数、型付き helper のいずれかに寄せる |
| union dict access | `SettingsSchema` の nested dict access | `TypedDict` または runtime guard で型を絞る |
| PySide6 enum stub | `QLineEdit.Password`, `Qt.LeftButton` | GUI phase でまとめて扱う。公開 macro API の gate には混ぜない |

## 6. 実装順

1. `constants` を直す。`LStick` / `RStick` の公開定数と `KeyCode` の `None` 型を整理する。
2. `macro.command` を直す。`capture()` は strict API とし、`None` を既定値にする引数を docstring と揃える。
3. `macro.exceptions` / `registry` を直す。`**kwargs` と `list` name shadowing を解消する。
4. `imgproc` を直す。OCR 初期化 guard、OpenCV 戻り値の型変換、前処理値の型を整理する。
5. `io.resources` を直す。読み書き context manager の型を実装に合わせる。
6. 公開 API bundle を 0 diagnostics にして、専用 command を仕様書と README に追加する。
7. `framework\core` 全体へ対象を広げる。
8. GUI / CLI を含む `src\nyxpy` 全体へ対象を広げる。

## 7. 検証コマンド

```powershell
uv run ty check src\nyxpy\framework\core\constants --output-format concise --no-progress
uv run ty check src\nyxpy\framework\core\macro --output-format concise --no-progress
uv run ty check src\nyxpy\framework\core\imgproc --output-format concise --no-progress
uv run ty check src\nyxpy\framework\core\io\resources.py --output-format concise --no-progress
uv run ty check src\nyxpy\framework\core\macro src\nyxpy\framework\core\constants src\nyxpy\framework\core\imgproc src\nyxpy\framework\core\io\resources.py --output-format concise --no-progress
uv run ty check src\nyxpy --output-format concise --no-progress
```

各修正単位では、対象の `ty check` に加えて次を実行する。

```powershell
uv run ruff check .
uv run ty check src\nyxpy --output-format concise --no-progress
uv run pytest tests/unit tests/integration
```

## 8. 完了チェックリスト

- [x] 型検査厳格化仕様を追加する
- [x] `constants` の型診断を 0 にする
- [x] `macro` の型診断を 0 にする
- [x] `imgproc` の型診断を 0 にする
- [x] `io.resources` の型診断を 0 にする
- [x] 公開 API bundle の型診断を 0 にする
- [x] `src\nyxpy\framework\core` の型診断を 0 にする
- [x] `src\nyxpy` の型診断を 0 にする
- [x] CI gate として `ty check` を追加する
