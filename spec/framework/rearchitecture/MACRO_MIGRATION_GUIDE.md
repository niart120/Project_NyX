# マクロ移行ガイド 仕様書

> **文書種別**: 移行ガイド仕様。再設計でマクロ作者に要求する変更の正本である。
> **対象モジュール**: `macros\`, `resources\`, `static\`, `macro.toml`, `src\nyxpy\framework\core\macro\`
> **目的**: Resource I/O、settings lookup、entrypoint、`DefaultCommand` 直接生成の破壊的変更に対して、マクロ側で必要な修正手順を定義する。
> **関連ドキュメント**: `MACRO_COMPATIBILITY_AND_REGISTRY.md`, `RESOURCE_FILE_IO.md`, `CONFIGURATION_AND_RESOURCES.md`, `RUNTIME_AND_IO_PORTS.md`, `DEPRECATION_AND_MIGRATION.md`, `TEST_STRATEGY.md`
> **破壊的変更**: `MacroBase` / `Command` / `DefaultCommand` / constants / `MacroStopException` の import と lifecycle は維持する。旧 `static` リソース配置、旧 settings fallback、legacy auto discovery、`DefaultCommand` 旧コンストラクタは維持しない。

## 1. 概要

### 1.1 目的

フレームワーク再設計に伴い、マクロ側で必要になる移行作業を一か所に集約する。互換 shim を長期維持しない項目を明示し、マクロ作者が `macro.toml`、settings、画像リソース、出力先を新仕様へ移せる状態にする。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| macro_id | manifest で定義する安定 ID。リソース配置、settings、実行ログの相関に使う |
| manifest | マクロ定義ファイル `macro.toml`。`[macro].id`、`[macro].entrypoint`、`[macro].settings` を持つ |
| entrypoint | `module:ClassName` 形式のマクロクラス参照。package 形式と single-file 形式の両方で必須 |
| standard assets | `resources\<macro_id>\assets` 配下の read-only 画像リソース |
| macro package assets | `macros\<macro_id>\assets` 配下の read-only 画像リソース |
| run outputs | `runs\<run_id>\outputs` 配下の実行ごとの出力先 |
| manifest settings path | `macro.toml` の `[macro].settings` で明示する settings TOML の場所 |

### 1.3 背景・問題

旧仕様では `static\<macro_name>` が settings、画像リソース、出力の境界を兼ねていた。`Path.cwd()` を前提にした暗黙探索、ファイル名 prefix 除去、旧 single-file auto discovery も混在し、GUI/CLI、テスト、マクロ作者が同じパス規則を共有しづらい状態だった。

再設計では、read-only assets、writable outputs、settings、entrypoint を分離する。互換モードを残すと実装とテストが二重化するため、マクロ側移行を要求する。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| settings 探索 | `static\<macro_name>` と `cwd` fallback が混在 | manifest settings path の 1 系統 |
| 画像リソース | 読み込み元と保存先が `static` に混在 | assets と outputs を分離 |
| マクロ発見 | legacy auto discovery と manifest が混在 | manifest entrypoint の 1 系統 |
| 出力追跡 | 実行単位の出力先が曖昧 | `run_id` ごとの outputs へ保存 |

### 1.5 着手条件

- `MACRO_COMPATIBILITY_AND_REGISTRY.md` の manifest entrypoint 仕様が確定している。
- `RESOURCE_FILE_IO.md` の `ResourceRef`、`ResourceKind`、`ResourceSource`、`RunArtifactStore` 仕様が確定している。
- `CONFIGURATION_AND_RESOURCES.md` の `MacroSettingsResolver` 仕様が確定している。
- 移行対象マクロの現行 settings と画像リソースの配置を確認済みである。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `spec\framework\rearchitecture\MACRO_MIGRATION_GUIDE.md` | 新規 | マクロ側移行手順を定義 |
| `macros\<macro_id>\macro.toml` | 新規 | manifest entrypoint と settings path を定義 |
| `macros\<macro_id>\macro.py` | 変更 | 必要に応じて resource path と `DefaultCommand` 直接生成を修正 |
| `macros\<macro_id>\assets\**` | 新規 | マクロ同梱 assets の移動先 |
| `resources\<macro_id>\assets\**` | 新規 | プロジェクト標準 assets の移動先 |
| `resources\<macro_id>\settings.toml` | 新規 | manifest settings path の推奨配置 |
| `static\<macro_name>\**` | 削除 | 旧 settings / assets / outputs 配置。移行後は標準探索しない |

## 3. 設計方針

### 3.1 後方互換性

維持するものは import と lifecycle に限定する。

| 区分 | 維持するもの | 移行が必要なもの |
|------|--------------|------------------|
| import | `MacroBase`, `Command`, `DefaultCommand`, constants, `MacroStopException` | `MacroExecutor` 直接 import |
| lifecycle | `initialize(cmd, args)`, `run(cmd)`, `finalize(cmd)` | 発見時インスタンス保持に依存する処理 |
| Command API | `cmd.load_img()`, `cmd.save_img()` などのメソッド名 | 旧 `static` 前提の path、ファイル名 prefix 除去前提 |
| settings | `exec_args` による上書き | `static\<macro_name>\settings.toml` と `Path.cwd()` fallback |
| entrypoint | package / single-file の実行 | legacy auto discovery |

### 3.2 移行単位

移行はマクロごとに完結させる。1 つのマクロで manifest、settings、assets、outputs の期待値を揃えてからテストを通す。旧配置と新配置を同時に標準探索させる中間状態は作らない。

### 3.3 single-file macro の扱い

single-file macro は許容する。ただし、legacy auto discovery ではなく manifest entrypoint で明示する。

```toml
[macro]
id = "sample_single_file"
name = "Sample Single File"
entrypoint = "sample_single_file:SampleSingleFileMacro"
settings = "project:resources/sample_single_file/settings.toml"
```

### 3.4 パス方針

`cmd.load_img()` は assets を読み込む API、`cmd.save_img()` は run outputs へ書き込む API として扱う。settings は `MacroSettingsResolver` が解決し、Resource Store は settings TOML を探索しない。

## 4. 実装仕様

### 4.1 manifest の追加

package 形式のマクロは `macros\<macro_id>\macro.toml` を追加する。

```toml
[macro]
id = "frlg_id_rng"
name = "FRLG ID RNG"
entrypoint = "macros.frlg_id_rng.macro:FrlgIdRngMacro"
settings = "project:resources/frlg_id_rng/settings.toml"
```

`entrypoint` は `module:ClassName` 形式とする。`id` はディレクトリ名や表示名ではなく、リソース配置とログ相関に使う安定 ID とする。

### 4.2 settings の移行

旧配置:

```text
static\frlg_id_rng\settings.toml
```

新配置:

```text
resources\frlg_id_rng\settings.toml
```

manifest:

```toml
[macro]
settings = "project:resources/frlg_id_rng/settings.toml"
```

相対パスを使う場合は manifest のある macro root 相対とする。`project:` prefix を付けた場合は `project_root` 相対とする。`Path.cwd()` からの探索は行わない。

### 4.3 assets の移行

旧配置:

```text
static\frlg_id_rng\button_a.png
static\frlg_id_rng\templates\title.png
```

新配置の例:

```text
resources\frlg_id_rng\assets\button_a.png
resources\frlg_id_rng\assets\templates\title.png
```

マクロ同梱にしたい assets は次へ置ける。

```text
macros\frlg_id_rng\assets\templates\title.png
```

`cmd.load_img("templates/title.png")` は assets root からの相対パスとして解決される。`static\frlg_id_rng` や絶対パスを直接渡す前提は移行対象である。

### 4.4 outputs の移行

`cmd.save_img("result.png", image)` の保存先は次に固定する。

```text
runs\<run_id>\outputs\result.png
```

旧 `static\<macro_name>` への保存、`legacy_static_write=True`、`resource.write_mode = "legacy_static"` は定義しない。ファイル名先頭の macro ID prefix は除去しない。

### 4.5 `DefaultCommand` 直接生成の修正

マクロは GUI/CLI 経路から渡された `cmd` を使う。次の直接生成は削除する。

```python
# 移行前: 不可
cmd = DefaultCommand(serial_device=serial, capture_device=capture)
```

テストで Command が必要な場合は、`MacroRuntimeBuilder` から `ExecutionContext` を作成して `DefaultCommand(context=...)` を使うか、対象ロジックを `Command` 不要の純粋関数に分離する。

```python
# 移行後: テスト用に context を明示する
cmd = DefaultCommand(context=context)
```

### 4.6 設定パラメータ

| パラメータ | 型 | デフォルト | 説明 |
|------------|-----|------------|------|
| `[macro].id` | `str` | なし | マクロの安定 ID。必須 |
| `[macro].entrypoint` | `str` | なし | `module:ClassName` 形式。必須 |
| `[macro].settings` | `str | None` | `None` | settings TOML の path。未指定なら `{}` |
| `project:` prefix | `str` | なし | `project_root` 相対 path を表す |

### 4.7 エラーハンドリング

| エラー | 発生条件 |
|--------|----------|
| `MacroLoadError` | manifest entrypoint がない、module import に失敗、class が `MacroBase` でない |
| `ConfigurationError` | settings path が root 外参照、絶対パス、空 path、存在しない必須 file |
| `ResourcePathError` | assets / outputs の root 外参照、未許可拡張子、ディレクトリ指定 |
| `ResourceWriteError` | `cmd.save_img()` の書き込みまたは atomic replace に失敗 |

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| ユニット | `test_manifest_entrypoint_required` | manifest entrypoint がないマクロをロードしない |
| ユニット | `test_registry_loads_manifest_single_file_macro` | single-file macro を manifest entrypoint からロードできる |
| ユニット | `test_macro_settings_resolver_loads_manifest_settings` | manifest settings path から settings を読む |
| ユニット | `test_macro_settings_resolver_does_not_read_legacy_static_settings` | 旧 `static` settings を暗黙探索しない |
| ユニット | `test_command_load_img_uses_resource_store` | `cmd.load_img()` が assets root から読む |
| ユニット | `test_command_save_img_uses_run_artifact_store` | `cmd.save_img()` が run outputs へ保存する |
| ユニット | `test_default_command_rejects_legacy_constructor_args` | 旧具象引数コンストラクタを受け付けない |
| 結合 | `test_migrated_repository_macros_load_from_manifest` | 移行後代表マクロが manifest entrypoint からロードされる |
| 結合 | `test_migrated_macro_settings_load_from_manifest` | 移行後代表マクロの settings が manifest から読み込まれる |

## 6. 実装チェックリスト

- [ ] 各マクロに `macro.toml` を追加し、`id` / `entrypoint` / `settings` を定義
- [ ] `static\<macro_name>\settings.toml` を manifest settings path へ移動
- [ ] 読み込み専用画像を `resources\<macro_id>\assets` または `macros\<macro_id>\assets` へ移動
- [ ] `cmd.load_img()` に渡す path を assets root 相対へ修正
- [ ] `cmd.save_img()` の保存先が `runs\<run_id>\outputs` になる前提へ修正
- [ ] ファイル名先頭の macro ID prefix 除去に依存する処理を削除
- [ ] `DefaultCommand(serial_device=..., capture_device=..., ...)` の直接生成を削除
- [ ] single-file macro は manifest entrypoint を追加
- [ ] 代表マクロの移行後結合テストを追加
- [ ] 旧 `static` / `cwd` fallback に依存するテストを削除または新仕様へ更新
