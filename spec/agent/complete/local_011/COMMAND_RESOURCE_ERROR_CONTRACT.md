# Command resource error contract 統一仕様書

> **対象モジュール**: `src/nyxpy/framework/core/macro/`, `src/nyxpy/framework/core/io/`
> **目的**: `Command.load_img` / `Command.save_img` と resource store の例外契約を統一する
> **関連ドキュメント**: `docs/macro-development/command-api.md`, `docs/macro-development/settings-and-resources.md`, `docs/api/framework.md`
> **既存ソース**: `src/nyxpy/framework/core/macro/command.py`, `src/nyxpy/framework/core/io/resources.py`
> **破壊的変更**: あり

## 1. 概要

### 1.1 目的

画像資材の読み込みと実行成果物の保存で送出される例外を、`ResourceError` 系のフレームワーク例外へ統一する。`Command` の docstring、Markdown docs、実装、テストを同じ例外契約へ揃える。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| Command | マクロがハードウェア操作や画像入出力を行うための高レベル API。 |
| ResourceStorePort | マクロ資材を読み込む読み取り専用 store。 |
| RunArtifactStore | 実行ごとの出力成果物を書き込む store。 |
| ResourceError | マクロ資材・成果物の path、読み込み、書き込みに関する基底例外。 |
| ResourcePathError | 資材 path が空、絶対 path、root 外、Windows 予約名などの場合の例外。 |
| ResourceNotFoundError | 指定資材が探索 root に存在しない場合の例外。 |
| ResourceReadError | 資材ファイルを OpenCV 画像として読み込めない場合の例外。 |
| ResourceWriteError | 実行成果物を書き込めない場合の例外。 |

### 1.3 背景・問題

`Command.load_img` の docstring は `FileNotFoundError` と `ValueError` を送出すると説明している。一方で実装は `DefaultCommand.load_img()` から `context.resources.load_image()` へ委譲し、`ResourceNotFoundError`, `ResourceReadError`, `ResourcePathError` を送出する。`Command.save_img` も `context.artifacts.save_image()` へ委譲し、`ResourceWriteError` 系を送出する。現状は docstring と実装の乖離により、マクロ実装者が捕捉すべき例外を判断しにくい。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| `Command.load_img` の例外契約 | docstring は組み込み例外、実装は `ResourceError` 系 | docstring と実装が `ResourceError` 系で一致 |
| 画像入出力の捕捉対象 | API ごとに不明確 | `ResourceError` を基点に判断できる |
| API reference の説明 | 実装と矛盾 | 実装と一致 |

### 1.5 着手条件

- `ResourceError` 系を公開 API として扱う方針を採用する。
- `docs/api/framework.md` に `nyxpy.framework.core.io.resources` と `nyxpy.framework.core.macro.exceptions` が含まれていることを維持する。
- 既存の `LocalResourceStore` / `LocalRunArtifactStore` の例外階層を確認する。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `src/nyxpy/framework/core/macro/command.py` | 変更 | `load_img`, `save_img`, `artifacts` の docstring を `ResourceError` 系へ統一する。 |
| `src/nyxpy/framework/core/io/resources.py` | 変更 | 必要に応じて例外 docstring と `details` を補足する。 |
| `docs/macro-development/command-api.md` | 変更 | 画像入出力 API の例外契約を記載する。 |
| `docs/macro-development/settings-and-resources.md` | 変更 | settings と resources の例外説明を `ResourceError` 系へ揃える。 |
| `tests/unit/framework/runtime/test_default_command_ports.py` | 変更 | `Command.load_img` / `save_img` が resource store の例外をそのまま伝えることを確認する。 |
| `tests/unit/framework/io/test_resource_file_io.py` | 変更 | `ResourcePathError`, `ResourceNotFoundError`, `ResourceReadError`, `ResourceWriteError` の発生条件を確認する。 |

## 3. 設計方針

### アーキテクチャ上の位置づけ

`Command` はマクロ実装者向けの高レベル API であり、画像入出力の実処理は `ResourceStorePort` と `RunArtifactStore` が担う。`Command` は例外を組み込み例外へ変換せず、resource 層のフレームワーク例外を公開契約として伝播する。

### 公開 API 方針

`Command.load_img()` / `Command.save_img()` の利用者は、個別条件を細かく扱う場合に `ResourcePathError`, `ResourceNotFoundError`, `ResourceReadError`, `ResourceWriteError` を捕捉できる。通常は `ResourceError` を基底例外として扱う。`FileNotFoundError` と `ValueError` は公開契約から外し、resource 層内部で必要な場合だけ cause として保持する。

### 後方互換性

破壊的変更あり。docstring に書かれていた `FileNotFoundError` / `ValueError` 捕捉を前提にしたマクロは、`ResourceError` 系へ変更する必要がある。NyX はアルファ版であり、互換 shim や組み込み例外へのラップは追加しない。

### レイヤー構成

`Command` は `ResourceError` 系を import して docstring の参照対象にできるが、実装では既存どおり resource store へ委譲する。resource store は `Command` に依存しない。

### 性能要件

| 指標 | 目標値 |
|------|--------|
| `load_img` / `save_img` の追加 I/O | 0 |
| 例外変換による追加処理 | 0 |

### 並行性・スレッド安全性

例外契約の統一であり、並行性には影響しない。`RunArtifactStore` の atomic write と overwrite policy は現行どおり維持する。

## 4. 実装仕様

### 公開インターフェース

```python
class Command(ABC):
    @abstractmethod
    def load_img(self, filename: str | Path, grayscale: bool = False) -> cv2.typing.MatLike:
        """画像資材を読み込みます。

        Raises:
            ResourcePathError: filename が不正な path の場合。
            ResourceNotFoundError: 探索 root に画像資材が存在しない場合。
            ResourceReadError: OpenCV 画像として読み込めない場合。
        """

    @abstractmethod
    def save_img(self, filename: str | Path, image: cv2.typing.MatLike) -> None:
        """画像を実行ごとの出力先へ保存します。

        Raises:
            ResourcePathError: filename が不正な path の場合。
            ResourceWriteError: 画像を書き込めない場合。
        """
```

### 設定パラメータ

| パラメータ | 型 | デフォルト | 説明 |
|------------|-----|-----------|------|
| `filename` | `str | Path` | なし | 資材 root または run output root からの相対 path。絶対 path、root 外、空 path は不正。 |
| `grayscale` | `bool` | `False` | `load_img` でグレースケール読み込みするか。 |

### エラーハンドリング

| 例外クラス | 発生条件 |
|------------|----------|
| `ResourcePathError` | path が空、絶対 path、drive 指定、`..`、Windows 予約名、root 外を指す場合。 |
| `ResourceNotFoundError` | `load_img` の探索候補に画像が存在しない場合。 |
| `ResourceReadError` | `cv2.imread()` が `None` を返す場合。 |
| `ResourceAlreadyExistsError` | `OverwritePolicy.ERROR` で出力先が既に存在する場合。 |
| `ResourceWriteError` | `cv2.imwrite()` や atomic rename が失敗した場合。 |

### シングルトン管理

該当なし。resource store は `ExecutionContext` が所有する。

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| ユニット | `test_load_img_propagates_resource_not_found` | `Command.load_img()` が `ResourceNotFoundError` を組み込み例外へ変換しない。 |
| ユニット | `test_load_img_rejects_unsafe_path` | 空 path、絶対 path、`..` が `ResourcePathError` になる。 |
| ユニット | `test_save_img_propagates_write_error` | `Command.save_img()` が `ResourceWriteError` 系を伝播する。 |
| ユニット | `test_resource_errors_include_details` | 例外に `code`, `component`, `details` が含まれる。 |
| ドキュメント | `uv run --no-sync mkdocs build --strict` | API reference と Markdown docs が `ResourceError` 系を表示する。 |

## 6. 実装チェックリスト

- [x] `ResourceError` 系を `Command` 画像入出力の公開契約にする判断を確定する。
- [x] `Command.load_img` / `save_img` の docstring を Google style で更新する。
- [x] `command-api.md` と `settings-and-resources.md` の例外説明を更新する。
- [x] resource store の例外 `details` がマクロ実装者の診断に足りるか確認する。
- [x] ユニットテストを追加・更新する。
- [x] `uv run ruff check src\nyxpy\framework\core\macro\command.py src\nyxpy\framework\core\io\resources.py tests\unit\framework` を実行する。
- [x] `uv run --no-sync mkdocs build --strict` を実行する。
