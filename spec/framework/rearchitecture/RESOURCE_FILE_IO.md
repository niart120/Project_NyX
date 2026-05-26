# Resource File I/O 再設計仕様書

> **対象モジュール**: `src\nyxpy\framework\core\io\`, `src\nyxpy\framework\core\macro\`, `src\nyxpy\framework\core\runtime\`
> **目的**: 読み取り用 assets と実行中に生成する artifacts を分離し、Command API から安全に読み書きできる境界を定義する。
> **関連ドキュメント**: `CONFIGURATION_AND_RESOURCES.md`, `RUNTIME_AND_IO_PORTS.md`, `IMPLEMENTATION_PLAN.md`

## 1. 概要

### 1.1 目的

Resource File I/O は、マクロが読む固定資材と、実行中に保存・読み戻す生成物を明確に分けるためのフレームワーク境界である。`Command` は assets 読み込み API と artifacts 保存・読み戻し API を提供し、store 実装は path guard、atomic write、overwrite policy、保存済み参照の記録を担当する。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| Command | マクロがハードウェア操作、キャプチャ、資材入出力、通知、ログを行うための高レベル API |
| Asset | `resources\<macro_id>\assets` またはマクロパッケージ内 `assets` に置く読み取り用資材 |
| Artifact | マクロ実行中に生成・更新するファイル。`resources\<macro_id>\artifacts` 配下に保存する |
| ArtifactScope.RUN | 実行ごとの既定保存先。`artifacts\<artifact_dir_name>` 配下を基準にする |
| ArtifactScope.STABLE | 実行回に依存しない固定保存先。`artifacts\stable` 配下を基準にする |
| ResourceStorePort | assets の path guard、探索、画像・bytes 読み込みを担当する Port |
| RunArtifactStore | artifacts の path guard、保存、読み戻し、保存済み `ResourceRef` 記録を担当する Port |
| ResourceRef | 解決済みファイル参照。kind、source、path、relative_path、macro_id、run_id を持つ |
| RunResult.artifacts | `cmd.save_artifact_*()` 経由で保存された `ResourceRef` 一覧 |

### 1.3 背景・問題

旧配置では生成物を `runs` 配下へ集約していたため、実行中または実行後に生成物をマクロ資材として再利用するには追加の移動操作が必要だった。現行仕様では生成物も `resources\<macro_id>` 配下へ集約する。ただし読み取り用の `assets` を直接 writable にすると固定資材と生成物の境界が崩れるため、書き込み先は `artifacts` に分ける。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| 生成物の再利用 | 実行出力から resources への移動が必要 | `resources\<macro_id>\artifacts` から同じ API で読み戻せる |
| API の責務 | 低レイヤー store 露出と高レベル API が混在 | `load_*` は assets、`save_artifact_*` / `load_artifact_*` は artifacts に分離 |
| 失敗原因の切り分け | 静的資材欠落と未生成 artifact が同じ読み込み経路になりやすい | assets と artifacts の API を分けて例外文脈を明確化 |
| 結果参照 | 保存先 root だけでは成果物単位の追跡が弱い | `RunResult.artifacts` に保存済み `ResourceRef` を保持 |

### 1.5 着手条件

- `resources\<macro_id>\assets` は読み取り専用資材として扱う。
- `resources\<macro_id>\artifacts` は writable artifacts の標準 root とする。
- 互換 shim や旧名 alias は追加しない。
- settings TOML の探索は `MacroSettingsResolver` が担当し、Resource Store へ戻さない。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `src\nyxpy\framework\core\io\resources.py` | 変更 | `ArtifactScope`、`ResourceStorePort`、`RunArtifactStore`、path guard、artifact tracking を実装 |
| `src\nyxpy\framework\core\macro\command.py` | 変更 | assets 読み込み API と artifacts 保存・読み戻し API を公開 |
| `src\nyxpy\framework\core\runtime\context.py` | 変更 | `artifact_dir_name` と artifact store を `ExecutionContext` へ保持 |
| `src\nyxpy\framework\core\runtime\result.py` | 変更 | `RunResult.artifacts` と `artifacts_overflow_count` を追加 |
| `src\nyxpy\framework\core\runtime\builder.py` | 変更 | `artifact_dir_name` と artifacts root を構築 |
| `tests\unit\framework\io\test_resource_file_io.py` | 変更 | path guard、scope、保存・読み戻し、tracking を検証 |
| `tests\integration\test_resource_file_io_migration.py` | 変更 | Runtime 経由で artifacts 配下へ保存されることを検証 |

## 3. 設計方針

### 3.1 配置モデル

```text
resources
  <macro_id>
    assets
      marker.png
    artifacts
      20260526T235245_a1b2
        debug
          frame.png
      stable
        marker.png
```

`ArtifactScope.RUN` は既定値であり、`artifact_dir_name` 配下に保存する。`ArtifactScope.STABLE` は明示した場合だけ使い、実行回に依存しない artifact を `stable` 配下に保存する。

### 3.2 公開 API 方針

| API | 用途 |
|-----|------|
| `cmd.load_img(name, grayscale=False)` | assets から画像を読む |
| `cmd.load_blob(name)` | assets から bytes を読む |
| `cmd.save_artifact_img(name, image, ...)` | artifacts へ画像を保存する |
| `cmd.save_artifact_blob(name, data, ...)` | artifacts へ bytes を保存する |
| `cmd.load_artifact_img(ref_or_name, ...)` | artifacts から画像を読み戻す |
| `cmd.load_artifact_blob(ref_or_name, ...)` | artifacts から bytes を読み戻す |
| `cmd.artifact_dir_name` | 実行ごとの保存先切り替えに使う directory segment を取得する |

`load_img()` / `load_blob()` は assets だけを読む。artifacts は `load_artifact_img()` / `load_artifact_blob()` だけで読む。`ResourceRef` を渡した読み戻しでは `ResourceRef.path` を正とし、`scope` は解決に使わない。

### 3.3 RunResult 方針

`RunArtifactStore` は `cmd.save_artifact_*()` 経由の保存を記録し、`RunResult.artifacts` に snapshot を渡す。同一 absolute path への保存は最後の 1 件だけを記録し、既存 `ResourceRef` を置き換えて末尾へ移動する。上限超過時は古いものから削除し、削除件数を `artifacts_overflow_count` に加算する。上限超過は実行失敗にしない。

### 3.4 後方互換性

Project NyX のフレームワーク本体はアルファ版として扱うため、旧画像保存 API と低レイヤー store 露出は削除する。互換 shim、alias、段階廃止 warning は追加しない。呼び出し元、テスト、ドキュメントは同じ変更で正 API へ更新する。

## 4. 実装仕様

### 4.1 公開インターフェース

```python
class Command(ABC):
    def load_img(self, filename: str | Path, *, grayscale: bool = False) -> cv2.typing.MatLike: ...
    def load_blob(self, filename: str | Path) -> bytes: ...
    def save_artifact_img(
        self,
        filename: str | Path,
        image: cv2.typing.MatLike,
        *,
        scope: ArtifactScope = ArtifactScope.RUN,
        overwrite: OverwritePolicy | None = None,
        atomic: bool | None = None,
    ) -> ResourceRef: ...
    def save_artifact_blob(
        self,
        filename: str | Path,
        data: bytes,
        *,
        scope: ArtifactScope = ArtifactScope.RUN,
        overwrite: OverwritePolicy | None = None,
        atomic: bool | None = None,
    ) -> ResourceRef: ...
    def load_artifact_img(
        self,
        artifact: ResourceRef | str | Path,
        *,
        scope: ArtifactScope = ArtifactScope.RUN,
        grayscale: bool = False,
    ) -> cv2.typing.MatLike: ...
    def load_artifact_blob(
        self,
        artifact: ResourceRef | str | Path,
        *,
        scope: ArtifactScope = ArtifactScope.RUN,
    ) -> bytes: ...
    @property
    def artifact_dir_name(self) -> str: ...
```

### 4.2 artifact_dir_name

| 項目 | 規則 |
|------|------|
| `run_id` | 既定は `uuid4().hex` |
| `short_id` | `run_id[:4]` |
| `timestamp` | 開始時刻を `%Y%m%dT%H%M%S` 形式にする |
| `artifact_dir_name` | `{timestamp}_{short_id}` |

### 4.3 設定パラメータ

| パラメータ | 型 | デフォルト | 説明 |
|------------|-----|-----------|------|
| `resource.artifacts_root` | `Path` | `resources\<macro_id>\artifacts` | artifact 保存 root |
| `resource.artifact_dir_name_format` | `str` | `{timestamp}_{short_id}` | helper が返す directory segment の形式 |
| `resource.artifact_timestamp_format` | `str` | `%Y%m%dT%H%M%S` | helper に使う開始時刻の形式 |
| `resource.short_id_length` | `int` | `4` | helper に含める短縮 ID の長さ |
| `resource.tracked_artifact_limit` | `int` | `65535` | `RunResult.artifacts` に保持する最大件数 |
| `resource.overwrite_policy` | `OverwritePolicy` | `REPLACE` | `overwrite=None` の場合に使う同名 artifact 処理 |
| `resource.atomic_write` | `bool` | `True` | artifact 保存に atomic write を使うか |

### 4.4 エラーハンドリング

| 例外クラス | 発生条件 |
|------------|----------|
| `ResourcePathError` | `filename` が root 外、不正名、絶対パス、`..` を指す |
| `ResourceNotFoundError` | assets または artifact が存在しない |
| `ResourceReadError` | 画像または bytes の読み込みに失敗した |
| `ResourceWriteError` | artifact の書き込みに失敗した |
| `ResourceAlreadyExistsError` | `OverwritePolicy.ERROR` で同名 artifact が存在する |
| `ResourceConfigurationError` | artifacts root、helper format、short ID 長などの設定が不正 |

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| ユニット | `test_local_resource_store_load_blob_reads_assets` | bytes asset を読み込める |
| ユニット | `test_local_run_artifact_store_saves_run_artifacts_without_stripping_macro_prefix` | run scope の保存先と relative path |
| ユニット | `test_local_run_artifact_store_save_and_load_blob` | blob artifact の保存・読み戻し |
| ユニット | `test_local_run_artifact_store_stable_scope_and_ref_readback` | stable scope と ResourceRef 読み戻し |
| ユニット | `test_local_run_artifact_store_tracks_dedupe_and_overflow` | dedupe と overflow count |
| ユニット | `test_default_command_resources_and_artifacts_delegate_to_ports` | Command が assets / artifacts store へ委譲する |
| 結合 | `test_runtime_saves_command_images_to_resource_artifacts` | Runtime 経由の artifact 保存先と RunResult |

## 6. 実装チェックリスト

- [x] assets 読み込み API を `load_img()` / `load_blob()` に統一
- [x] artifacts 操作 API を `save_artifact_*()` / `load_artifact_*()` に統一
- [x] artifact root を `resources\<macro_id>\artifacts` に変更
- [x] `artifact_dir_name` helper を実装
- [x] `RunResult.artifacts` と `artifacts_overflow_count` を実装
- [x] 既存マクロ、サンプル、docs を新 API へ更新
- [x] 関連単体テスト・結合テストを更新
