# Command Artifact Output API 仕様書

> **文書種別**: WIP 仕様書。`Command` API から生成ファイルを保存・読み戻す公開 API と、`resources` 配下への集約方針を扱う。
> **対象モジュール**: `src\nyxpy\framework\core\macro\`, `src\nyxpy\framework\core\io\`, `src\nyxpy\framework\core\runtime\`
> **目的**: マクロ実行中に生成した画像・blob を、実行中および実行後に再利用しやすい形で保存する。
> **関連ドキュメント**: `spec\framework\rearchitecture\RESOURCE_FILE_IO.md`, `spec\framework\rearchitecture\RUNTIME_AND_IO_PORTS.md`, `docs\macro-development\*.md`
> **既存ソース**: `src\nyxpy\framework\core\macro\command.py`, `src\nyxpy\framework\core\io\resources.py`, `src\nyxpy\framework\core\runtime\builder.py`, `src\nyxpy\framework\core\runtime\result.py`
> **破壊的変更**: あり。`cmd.artifacts` と `runs\<run_id>\outputs` 前提の実装・テスト・ドキュメントを新 API と `resources\<macro_id>\artifacts` 配置へ更新する。

## 1. 概要

### 1.1 目的

マクロが生成する成果物を `resources\<macro_id>` 配下へ集約し、マクロ開発者が用途に応じて保存先を制御できるようにする。framework は path guard、型別保存 API、読み戻し API、実行ごとのディレクトリ名 helper、`RunResult` への保存済み参照記録を提供する。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| Command | マクロがコントローラー操作、待機、キャプチャ、ログ、通知、画像入出力を行うための高レベル API |
| Asset | `resources\<macro_id>\assets` 配下に置く読み取り用資材。`cmd.load_img()` / `cmd.load_blob()` の対象 |
| Artifact | マクロ実行中に生成・更新するファイル。`resources\<macro_id>\artifacts` 配下に保存する |
| Artifact root | `resources\<macro_id>\artifacts`。実行中に書き込み可能な標準 root |
| Run-scoped artifact | 既定の保存先。`resources\<macro_id>\artifacts\<artifact_dir_name>` 配下に保存する |
| Stable artifact | 実行回に依存せず再利用したい artifact。`resources\<macro_id>\artifacts\stable` 配下に保存する |
| Blob | 任意のバイナリデータ。テキストや JSON も encoding 済み bytes として扱える |
| ArtifactScope | artifact の保存・読み戻し基準。既定は `RUN`、固定再利用用に `STABLE` を持つ |
| Artifact readback | 保存済み artifact を `cmd.load_artifact_*()` で読み戻す操作 |
| artifact_dir_name | 実行ごとの保存先切り替えに使う helper 値。例: `20260526T221417_a1b2` |
| ResourceRef | 保存・解決済みファイルの参照。kind、source、path、relative_path、macro_id、run_id を持つ |
| RunResult.artifacts | `cmd.save_artifact_*()` 経由で保存された `ResourceRef` 一覧 |
| RunResult.artifacts_overflow_count | `RunResult.artifacts` の上限を超えて記録しなかった artifact 件数 |

### 1.3 背景・問題

現行実装は `cmd.save_img()` と `cmd.artifacts.open_output()` を `runs\<run_id>\outputs` へ保存する。実行ごとの衝突回避には有効だが、マクロ実行中や実行後に生成物を入力資材として再利用するには、`runs` から `resources` へ移す追加操作が必要になる。

今回の方針では、生成ファイルも `resources\<macro_id>` 配下へ集約する。ただし `assets` を直接 writable にすると読み取り用資材と生成物の境界が崩れるため、書き込み先は `artifacts` に分ける。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| 生成物の再利用 | `runs` から `resources` への移動が必要 | `resources\<macro_id>\artifacts` に保存し、同じ相対パスで読み戻せる |
| Command API | `cmd.artifacts.open_output()` が低レイヤー store を露出する | `cmd.load_img()` / `cmd.load_blob()` と `cmd.save_artifact_*()` / `cmd.load_artifact_*()` を主導線にする |
| assets と artifacts の境界 | `cmd.load_img()` と生成物の関係が未整理 | `cmd.load_img()` / `cmd.load_blob()` は assets、`cmd.load_artifact_*()` は artifacts と分ける |
| 実行ごとの出力切り替え | framework が `runs\<run_id>` を強制する | 既定では `artifacts\<artifact_dir_name>` 配下へ保存し、固定化したい場合だけ scope を明示する |
| RunResult の成果物参照 | 保存先 root だけでは成果物単位の参照が弱い | `cmd.save_artifact_*()` が返した `ResourceRef` 一覧を `RunResult.artifacts` に保持する |

### 1.5 着手条件

- `resources\<macro_id>\assets` は読み取り用資材として扱い、実行中の直接書き込み先にしない。
- `resources\<macro_id>\artifacts` は writable artifacts の標準 root とする。
- `cmd.load_img()` の探索範囲を artifacts へ広げず、assets 専用 API として維持する。
- `cmd.load_blob()` は assets 専用の bytes 読み込み API として追加する。
- `cmd.save_img(filename, image)` は完全削除し、`cmd.save_artifact_img(filename, image)` へ置き換える。
- 既存実装済みマクロ（`macros\` / `examples\macros\`）と `docs\` 配下の利用例を同じ変更で新 API へ更新する。
- 既存の `runs\<run_id>\outputs` 前提のテストとドキュメントを同じ変更で更新する。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `src\nyxpy\framework\core\macro\command.py` | 変更 | `load_blob()`、`save_artifact_*()`、`load_artifact_*()`、artifact scope、`artifact_dir_name` helper を追加し、`cmd.save_img()` / `cmd.artifacts` を削除する |
| `src\nyxpy\framework\core\io\resources.py` | 変更 | artifact root を `resources\<macro_id>\artifacts` へ変更し、保存済み `ResourceRef` の記録を実装する |
| `src\nyxpy\framework\core\runtime\builder.py` | 変更 | 実行ごとの `artifact_dir_name` と artifact store を構築する |
| `src\nyxpy\framework\core\runtime\context.py` | 変更 | `artifact_dir_name` と artifact store を `ExecutionContext` から参照できるようにする |
| `src\nyxpy\framework\core\runtime\result.py` | 変更 | `RunResult.artifacts: tuple[ResourceRef, ...]` と `RunResult.artifacts_overflow_count: int` を追加する |
| `docs\**\*.md` | 変更 | `cmd.save_img()` / `cmd.artifacts` 前提の説明と例を新 API・新配置へ更新する。設計経緯や WIP 仕様への言及は含めない |
| `spec\framework\rearchitecture\RESOURCE_FILE_IO.md` | 変更 | `runs` 標準保存先から `resources\<macro_id>\artifacts` へ正本を更新する |
| `macros\**\*.py` | 変更 | 実装済みローカルマクロの `cmd.save_img()` / `cmd.artifacts` 呼び出しを新 API へ更新する |
| `examples\macros\**\*.py` | 変更 | サンプルマクロの `cmd.save_img()` / `cmd.artifacts` 呼び出しを新 API へ更新する |
| `tests\unit\framework\io\test_resource_file_io.py` | 変更 | artifact root、path guard、保存済み参照記録を検証する |
| `tests\integration\test_resource_file_io_migration.py` | 変更 | Runtime 経由の保存先と `RunResult.artifacts` を検証する |
| `tests\unit\framework\runtime\test_runtime_builder.py` | 変更 | `artifact_dir_name` 生成と artifact store 構築を検証する |

## 3. 設計方針

### アーキテクチャ上の位置づけ

成果物出力は `Command` の高レベル API と、framework 内部の artifact store の境界に置く。マクロ作者は store 実体を直接操作せず、型別の保存・読み戻し API を使う。

```text
macro code
  -> Command.load_img(...) / load_blob(...)
  -> Command.save_artifact_img(...) / save_artifact_blob(...)
  -> Command.load_artifact_img(...) / load_artifact_blob(...)
  -> DefaultCommand
  -> ArtifactStore
  -> resources\<macro_id>\artifacts\<artifact_dir_name>\<relative_path>  # default
```

`MacroRuntimeBuilder` は実行ごとに `artifact_dir_name` を生成する。保存 API は既定で `artifacts\<artifact_dir_name>` 配下を基準にする。実行回に依存しない固定 artifact を保存したい場合だけ、マクロ開発者が `scope=ArtifactScope.STABLE` を明示する。

### 公開 API 方針

| 案 | API | 判定 | 理由 |
|----|-----|------|------|
| 低レイヤー store 露出 | `cmd.artifacts.open_output(...)` | 不採用 | `Command` が高レベル API である方針に反し、file mode や close をマクロ作者へ露出する |
| `open_output()` 追加 | `cmd.open_output(...)` | 不採用 | 任意ファイルには対応できるが、高レベル API としては低すぎる |
| 型別保存 API | `cmd.save_text(...)`, `cmd.save_json(...)` | 初期実装では不採用 | `save_artifact_blob()` に集約できる。encoding や JSON 整形の方針を Command API に固定するには判断材料が足りない |
| asset 読み込み API | `cmd.load_img(...)`, `cmd.load_blob(...)` | 採用 | `asset` 接頭辞なしでも保存 API と衝突せず、assets 専用 API として短く保てる |
| artifact 保存 API | `cmd.save_artifact_img(...)`, `cmd.save_artifact_blob(...)` | 採用 | 生成物を書き込む意図と保存先を名前で明示する |
| artifact 読み戻し API | `cmd.load_artifact_img(...)`, `cmd.load_artifact_blob(...)` | 採用 | まだ生成されていない artifact を読もうとしたのか、静的 asset の配置漏れなのかを区別する |
| source フラグ方式 | `cmd.load_img(..., source=...)` | 不採用 | `load_img()` の探索範囲が広がり、失敗原因の切り分けが弱くなる |

### 配置方針

採用配置は次の通りである。

```text
resources
  sample_macro
    assets
      marker.png
    artifacts
      20260526T221417_a1b2
        debug
          frame.png
      stable
        marker.png
```

`artifacts\<artifact_dir_name>` は既定の保存先である。`artifacts\stable` は実行後も安定して参照したい成果物の固定保存先とする。

`cmd.load_img()` / `cmd.load_blob()` は `assets` だけを読む。`artifacts` 配下は `cmd.load_artifact_img()` / `cmd.load_artifact_blob()` で読む。分離の主目的は、まだ生成されていない artifact を読もうとした失敗と、静的 asset として配置されているべき資材の欠落を区別できるようにすることである。

artifact scope の初期案は次の通りである。

| Scope | 解決先 | 用途 |
|-------|--------|------|
| `ArtifactScope.RUN` | `resources\<macro_id>\artifacts\<artifact_dir_name>\<name>` | 既定。実行ごとのデバッグ画像、結果ファイル |
| `ArtifactScope.STABLE` | `resources\<macro_id>\artifacts\stable\<name>` | 実行をまたいで再利用したい生成物 |

`short_id` は directory 名が長くなる欠点があるが、同一秒の多重起動や同一マクロの並列実行を考えると残す。`artifact_dir_name` は人間が読む時刻と衝突回避用 short ID の組み合わせにする。

### 初回議論案と不採用理由

| 案 | 配置 | 不採用理由 |
|----|------|------------|
| 現行維持 | `runs\<run_id>\outputs` | 実行 ID だけでは人間が判別しにくく、生成物を resources 側で再利用する導線が弱い |
| runs + macro_id | `runs\<macro_id>\<timestamp>_<short_id>\files` | 実行ごとの管理はしやすいが、結局 resources へ移すまたは promote する手順が必要になる |
| run directory 直下に成果物 | `runs\<macro_id>\<timestamp>_<short_id>\debug\frame.png` | `run.json` など framework metadata とユーザー成果物が混ざる |
| `outputs` 階層維持 | `runs\<macro_id>\<timestamp>_<short_id>\outputs` | `outputs` は内部用語寄りで、資材として再利用するファイル群という意味が弱い |
| `run slug` 概念 | `20260526T221417_a1b2` を公開用語化 | directory segment として足り、API 名や metadata key として独立させる意味が薄い |

### RunResult 方針

resources 集約案では、単一の標準成果物 root を `RunResult` に載せても情報が弱い。`cmd.save_artifact_*()` が返した `ResourceRef` を store が記録し、`RunResult.artifacts` に含める方式を採用する。`ArtifactScope.RUN` と `ArtifactScope.STABLE` のどちらで保存した artifact も記録対象にする。

| 案 | 内容 | 判定 |
|----|------|------|
| 成果物 root なし | `RunResult` は実行状態だけを返す | 不採用。GUI / CLI から成果物へ案内しにくい |
| 保存済み `ResourceRef` 一覧 | `cmd.save_artifact_*()` 経由の保存を `RunResult.artifacts` に含める | 採用 |
| 明示登録方式 | `track=True` や `cmd.register_artifact()` だけを載せる | 初期実装では不採用。大量ファイル生成時の拡張候補 |

`RunResult.artifacts` は上限を設ける。同一 absolute path への保存は最後の 1 件だけを記録し、同じ path の既存 `ResourceRef` を置き換えて末尾へ移動する。新規 path の追加で上限を超えた場合は古いものから削除し、削除した件数を `RunResult.artifacts_overflow_count` に加算する。上限超過はマクロ実行失敗にしない。

### 後方互換性

Project NyX のフレームワーク本体はアルファ版であるため、`cmd.save_img()`、`cmd.artifacts`、`runs\<run_id>\outputs` の破壊的変更を許容する。互換 shim、alias、段階的な `DeprecationWarning` は追加しない。呼び出し元、実装済みマクロ、テスト、ドキュメントを同じ変更で正 API へ更新する。

### レイヤー構成

| レイヤー | 責務 | 依存してよい先 |
|----------|------|----------------|
| macro | `Command` API を呼び、保存先相対パスを選ぶ | `nyxpy.framework.*`, `macros.shared` |
| `Command` | マクロ作者向けの保存・読み戻し API を提供する | runtime context, artifact store interface |
| artifact store | artifact root 配下の path guard、atomic write、読み戻し、保存済み参照記録を扱う | 標準ライブラリ、OpenCV、framework 例外 |
| `MacroRuntimeBuilder` | `artifact_dir_name` と artifact store を実行ごとに生成する | registry, settings, resource file io |
| GUI / CLI | `RunResult.artifacts` を表示・案内する | framework runtime API |

### 性能要件

| 指標 | 目標値 |
|------|--------|
| `artifact_dir_name` 生成 | 1 実行あたり 5 ms 未満 |
| `cmd.save_artifact_blob()` の追加オーバーヘッド | ファイル保存時に 5 ms 未満 |
| `cmd.load_artifact_img()` の追加オーバーヘッド | OpenCV 読み込み時間を除き 5 ms 未満 |
| `RunResult.artifacts` 記録 | 1 保存あたり 1 ms 未満 |

### 並行性・スレッド安全性

実行ごとのディレクトリ分離は既定で framework が行う。マクロ開発者が固定保存を選ぶ場合は `scope=ArtifactScope.STABLE` を明示する。同じ相対パスへ複数スレッドから保存する場合は、artifact store の overwrite policy と atomic write に従う。

## 4. 実装仕様

### 公開インターフェース

```python
class Command(ABC):
    @abstractmethod
    def load_img(
        self,
        filename: str | pathlib.Path,
        *,
        grayscale: bool = False,
    ) -> cv2.typing.MatLike:
        """resources/<macro_id>/assets 配下の静的画像 asset を読み込む。"""
        ...

    @abstractmethod
    def load_blob(
        self,
        filename: str | pathlib.Path,
    ) -> bytes:
        """resources/<macro_id>/assets 配下の静的 blob asset を読み込む。"""
        ...

    @abstractmethod
    def save_artifact_img(
        self,
        filename: str | pathlib.Path,
        image: cv2.typing.MatLike,
        *,
        scope: ArtifactScope = ArtifactScope.RUN,
        overwrite: OverwritePolicy | None = None,
        atomic: bool | None = None,
    ) -> ResourceRef:
        """resources/<macro_id>/artifacts 配下へ画像 artifact を保存する。"""
        ...

    @abstractmethod
    def save_artifact_blob(
        self,
        filename: str | pathlib.Path,
        data: bytes,
        *,
        scope: ArtifactScope = ArtifactScope.RUN,
        overwrite: OverwritePolicy | None = None,
        atomic: bool | None = None,
    ) -> ResourceRef: ...

    @abstractmethod
    def load_artifact_blob(
        self,
        artifact: ResourceRef | str | pathlib.Path,
        *,
        scope: ArtifactScope = ArtifactScope.RUN,
    ) -> bytes: ...

    @abstractmethod
    def load_artifact_img(
        self,
        artifact: ResourceRef | str | pathlib.Path,
        *,
        scope: ArtifactScope = ArtifactScope.RUN,
        grayscale: bool = False,
    ) -> cv2.typing.MatLike:
        """resources/<macro_id>/artifacts 配下の画像 artifact を読み戻す。"""
        ...

    @property
    @abstractmethod
    def artifact_dir_name(self) -> str:
        """実行ごとの保存先切り替えに使える directory segment。"""
        ...
```

利用例:

```python
frame = cmd.capture()
marker = cmd.load_img("marker.png")
ref = cmd.save_artifact_img("debug/frame.png", frame)
same_frame = cmd.load_artifact_img(ref)
cmd.save_artifact_blob("debug/result.json", b'{"matched": true}')
cmd.save_artifact_img("marker.png", frame, scope=ArtifactScope.STABLE)
```

`save_img()` は、保存先が artifact であることを名前に含めるため公開 API から削除する。`load_img()` は assets 専用 API として維持し、artifact 読み戻しは `load_artifact_img()` で明示する。任意 bytes は `load_blob()` / `save_artifact_blob()` / `load_artifact_blob()` に統一する。`save_artifact()` のような型接尾辞なしの API は、画像エンコードと bytes 書き込みの境界が曖昧になるため初期実装では採用しない。

| 案 | API | 評価 |
|----|-----|------|
| 読み込み短縮 | `load_img()` / `load_blob()` | 採用。保存側に `save_img()` / `save_blob()` が存在しないため、assets 読み込みとして読める |
| artifact 明示 | `save_artifact_img()` / `save_artifact_blob()` / `load_artifact_img()` / `load_artifact_blob()` | 採用。生成物の保存・読み戻しを名前で区別できる |
| asset 明示 | `load_asset_img()` / `load_asset_blob()` | 不採用。明示的だが、assets しか読まない `load_*()` を長くするほどの利点が薄い |
| 型なし artifact | `save_artifact()` / `load_artifact()` | 不採用。画像として decode するのか bytes のまま扱うのかがシグネチャから分かりにくい |
| source 指定 | `load_img(..., source=...)` | 不採用。API 数は増えないが、探索範囲が広がり失敗原因の切り分けが弱くなる |
| namespace façade | `cmd.assets.load_img()` / `cmd.artifacts.save_img()` | 保留。名前は短いが、`cmd.artifacts` を低レイヤー store と誤解されやすい |

`save_text()` / `save_json()` は初期実装では追加しない。必要な場合は、呼び出し側で encoding または JSON serialize を行い `save_artifact_blob()` に渡す。

`cmd.load_blob()` は静的資材として同梱または配置された任意 bytes を読む。artifact の読み戻しは `cmd.load_artifact_blob()` に限定し、asset と artifact の探索範囲を混ぜない。

`load_artifact_*()` に `ResourceRef` を渡した場合は、`ResourceRef.path` を正とし、`scope` は解決に使わない。`str` または `Path` を渡した場合だけ、`scope` に基づいて現在実行中の `artifacts\<artifact_dir_name>` または `artifacts\stable` から解決する。過去実行の run-scoped artifact を読み戻す場合は、保存時に得た `ResourceRef` を渡す。

`ResourceRef.run_id` は、その artifact を保存した実行の ID とする。`ArtifactScope.STABLE` で保存した場合も provenance として保存時の `run_id` を保持するが、パス解決には使わない。

`save_artifact_*()` の `overwrite=None` と `atomic=None` は artifact store の既定値を使う。標準設定では `resource.overwrite_policy=REPLACE`、`resource.atomic_write=True` とし、同一 path の artifact を更新できるようにする。呼び出し単位で `OverwritePolicy.ERROR` や `atomic=False` などを明示した場合は、その指定を優先する。

### artifact_dir_name

| 項目 | 規則 |
|------|------|
| `run_id` | 完全な一意 ID。既定は `uuid4().hex` |
| `short_id` | `run_id[:4]` |
| `timestamp` | 開始時刻を local time で `YYYYMMDDTHHMMSS` 形式にする |
| `artifact_dir_name` | `{timestamp}_{short_id}` |

`ArtifactScope.RUN` では `artifact_dir_name` が自動的に基準ディレクトリになるため、マクロ開発者は `debug/frame.png` だけを渡せば `artifacts\<artifact_dir_name>\debug\frame.png` に保存される。固定パスとして扱いたい場合は `scope=ArtifactScope.STABLE` を明示し、`artifacts\stable\<name>` に保存する。

### 設定パラメータ

| パラメータ | 型 | デフォルト | 説明 |
|------------|-----|-----------|------|
| `resource.artifacts_root` | `Path` | `project_root\resources\<macro_id>\artifacts` | artifact 保存 root |
| `resource.artifact_dir_name_format` | `str` | `{timestamp}_{short_id}` | helper が返す directory segment の形式 |
| `resource.artifact_timestamp_format` | `str` | `%Y%m%dT%H%M%S` | helper に使う開始時刻の形式 |
| `resource.short_id_length` | `int` | `4` | helper に含める短縮 ID の長さ |
| `resource.tracked_artifact_limit` | `int` | `65535` | `RunResult.artifacts` に保持する最大件数 |
| `resource.overwrite_policy` | `OverwritePolicy` | `REPLACE` | `save_artifact_*()` で `overwrite=None` の場合に使う同名 artifact 処理 |
| `resource.atomic_write` | `bool` | `True` | artifact 保存に atomic write を使うか |

### エラーハンドリング

| 例外クラス | 発生条件 |
|------------|----------|
| `ResourcePathError` | `filename` が artifact root 外、不正名、絶対パス、`..` を指す |
| `ResourceWriteError` | artifact の書き込みに失敗した |
| `ResourceReadError` | artifact の読み込みに失敗した |
| `ResourceAlreadyExistsError` | `OverwritePolicy.ERROR` で同名 artifact が存在する |
| `ResourceConfigurationError` | artifacts root、helper format、short ID 長などの設定が不正 |

### シングルトン管理

新規グローバル singleton は追加しない。artifact store と `artifact_dir_name` は `MacroRuntimeBuilder` またはテスト fixture が実行ごとに生成する。

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| ユニット | `test_command_load_img_reads_assets` | `DefaultCommand.load_img()` が assets から画像を読む |
| ユニット | `test_command_load_blob_reads_assets` | `DefaultCommand.load_blob()` が assets から bytes を読む |
| ユニット | `test_command_save_artifact_blob_delegates_to_artifact_store` | `DefaultCommand.save_artifact_blob()` が artifact store へ委譲する |
| ユニット | `test_command_load_artifact_blob_reads_saved_blob` | `cmd.save_artifact_blob()` が返した `ResourceRef` を `cmd.load_artifact_blob()` で読み戻せる |
| ユニット | `test_command_load_artifact_img_reads_saved_image` | `cmd.save_artifact_img()` が返した `ResourceRef` を `cmd.load_artifact_img()` で読み戻せる |
| ユニット | `test_load_artifact_ref_ignores_scope` | `ResourceRef` で読み戻す場合は `scope` ではなく `ResourceRef.path` を使う |
| ユニット | `test_command_load_artifact_does_not_use_assets` | `load_artifact_blob()` と `load_artifact_img()` が `assets` を探索しない |
| ユニット | `test_command_does_not_expose_artifacts_property` | `cmd.artifacts` が公開 API から消えている |
| ユニット | `test_artifact_dir_name_uses_timestamp_and_short_id` | helper が `{timestamp}_{short_id}` を返す |
| ユニット | `test_artifact_scope_defaults_to_run_directory` | scope 未指定時は `artifacts\<artifact_dir_name>` 配下へ保存する |
| ユニット | `test_artifact_scope_stable_uses_fixed_directory` | `scope=ArtifactScope.STABLE` で `artifacts\stable` 配下へ保存する |
| ユニット | `test_artifact_scope_stable_is_recorded_in_run_result` | `ArtifactScope.STABLE` の保存も `RunResult.artifacts` に含める |
| ユニット | `test_artifact_store_records_saved_refs` | `save_artifact_*()` 経由の `ResourceRef` が記録される |
| ユニット | `test_artifact_tracking_dedupes_same_path` | 同一 absolute path の保存は最後の `ResourceRef` だけを記録する |
| ユニット | `test_artifact_tracking_keeps_latest_refs_on_overflow` | 上限超過時は最新の `ResourceRef` を保持し、削除件数を `RunResult.artifacts_overflow_count` に記録する |
| 結合 | `test_runtime_result_includes_saved_artifacts` | Runtime 経由で `RunResult.artifacts` に保存済み `ResourceRef` が入る |
| 結合 | `test_runtime_saves_artifacts_under_resources` | `cmd.save_artifact_img()` が `resources\<macro_id>\artifacts` 配下に保存する |
| ハードウェア | `test_realdevice_artifact_save_image` | `@pytest.mark.realdevice`。実キャプチャ画像を artifact として保存できる |
| パフォーマンス | `test_artifact_tracking_limit_perf` | 上限件数までの `ResourceRef` 記録が目標値内である |

## 6. 実装チェックリスト

- [x] resources 集約案を採用
- [x] 命名は assets 読み込みを `load_img()` / `load_blob()`、artifact 操作を `save_artifact_*()` / `load_artifact_*()` に統一する
- [x] `RunResult` は保存済み `ResourceRef` 一覧を持つ案を採用
- [x] `artifacts/stable` は `scope=ArtifactScope.STABLE` で明示する
- [x] `cmd.artifacts` を削除
- [x] `cmd.load_blob()` / `cmd.save_artifact_blob()` / `cmd.load_artifact_blob()` を実装
- [x] `cmd.save_artifact_img()` / `cmd.load_artifact_img()` を実装
- [x] `cmd.save_img()` を完全削除し、`macros\` / `examples\macros\` の呼び出し元を更新
- [x] `cmd.artifact_dir_name` helper を実装
- [x] `RunResult.artifacts` と `artifacts_overflow_count` を実装
- [x] 既存 tests / docs / specs を新 API と新配置へ更新
- [x] `uv run ruff check .` がパス
- [x] 関連 pytest がパス
