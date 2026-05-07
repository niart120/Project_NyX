# マクロ移行ガイド 仕様書

> **文書種別**: 移行ガイド仕様。再設計でマクロ作者に要求する変更の正本である。
> **対象モジュール**: `macros\`, `resources\`, `static\`, `macro.toml`, `src\nyxpy\framework\core\macro\`
> **目的**: Resource I/O、settings lookup、entrypoint、`DefaultCommand` 直接生成の破壊的変更に対して、マクロ側で必要な修正手順を定義する。
> **関連ドキュメント**: `MACRO_COMPATIBILITY_AND_REGISTRY.md`, `RESOURCE_FILE_IO.md`, `CONFIGURATION_AND_RESOURCES.md`, `RUNTIME_AND_IO_PORTS.md`, `DEPRECATION_AND_MIGRATION.md`, `TEST_STRATEGY.md`
> **破壊的変更**: 破壊的変更と削除条件は `DEPRECATION_AND_MIGRATION.md` を正とする。本ガイドはマクロ作者、テスト作者、adapter 実装者が必要な移行手順を説明する。

## 1. 概要

### 1.1 目的

フレームワーク再設計に伴い、マクロ側で必要になる移行作業を一か所に集約する。互換 shim を長期維持しない項目を明示し、マクロ作者が任意の `macro.toml`、class metadata、settings、画像リソース、出力先を新仕様へ移せる状態にする。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| macro_id | manifest、class metadata、または convention default で決まる安定 ID。リソース配置、settings、実行ログの相関に使う |
| manifest | 任意のマクロ定義ファイル `macro.toml`。複数 entrypoint、import 前 metadata、args schema、配布用 metadata を明示したい場合に使う |
| class metadata | `MacroBase` 派生クラスに置く `macro_id`、`display_name`、`settings_path` などの任意属性 |
| convention discovery | manifest がない軽量マクロを、ファイル名またはディレクトリ名と 1 件の `MacroBase` 派生クラスから発見する規約 |
| entrypoint | `module:ClassName` 形式のマクロクラス参照。manifest を使う場合に明示する |
| standard assets | `resources\<macro_id>\assets` 配下の read-only 画像リソース |
| macro package assets | `macros\<macro_id>\assets` 配下の read-only 画像リソース |
| run outputs | `runs\<run_id>\outputs` 配下の実行ごとの出力先 |
| explicit settings source | `macro.toml [macro].settings` または class metadata `settings_path` で明示する settings TOML の場所 |

### 1.3 背景・問題

旧仕様では `static\<macro_name>` が settings、画像リソース、出力の境界を兼ねていた。`Path.cwd()` を前提にした暗黙探索、ファイル名 prefix 除去、旧 single-file auto discovery も混在し、GUI/CLI、テスト、マクロ作者が同じパス規則を共有しづらい状態だった。

再設計では、read-only assets、writable outputs、settings、entrypoint を分離する。互換モードを残すと実装とテストが二重化するため、マクロ側移行を要求する。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| settings 探索 | `static\<macro_name>` と `cwd` fallback が混在 | manifest または class metadata の明示 settings source |
| 画像リソース | 読み込み元と保存先が `static` に混在 | assets と outputs を分離 |
| マクロ発見 | 旧 auto discovery と manifest が混在 | manifest / class metadata / convention discovery |
| 出力追跡 | 実行単位の出力先が曖昧 | `run_id` ごとの outputs へ保存 |

### 1.5 着手条件

- `MACRO_COMPATIBILITY_AND_REGISTRY.md` の manifest 任意採用、class metadata、convention discovery 仕様が確定している。
- `RESOURCE_FILE_IO.md` の `ResourceRef`、`ResourceKind`、`ResourceSource`、`RunArtifactStore` 仕様が確定している。
- `CONFIGURATION_AND_RESOURCES.md` の `MacroSettingsResolver` 仕様が確定している。
- 移行対象マクロの現行 settings と画像リソースの配置を確認済みである。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `spec/framework/rearchitecture/MACRO_MIGRATION_GUIDE.md` | 新規 | マクロ側移行手順を定義 |
| `macros\<macro_id>\macro.toml` | 新規 | 高度機能が必要な場合だけ manifest entrypoint と settings path を定義 |
| `macros\<macro_id>\macro.py` | 変更 | 必要に応じて resource path と `DefaultCommand` 直接生成を修正 |
| `macros\<macro_id>\assets\**` | 新規 | マクロ同梱 assets の移動先 |
| `resources\<macro_id>\assets\**` | 新規 | プロジェクト標準 assets の移動先 |
| `resources\<macro_id>\settings.toml` | 新規 | 明示 settings source の推奨配置 |
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
| entrypoint | package / single-file の実行 | 曖昧な旧 auto discovery。軽量マクロは convention discovery へ移行 |

### 3.2 移行単位

移行はマクロごとに完結させる。1 つのマクロで発見方式、settings、assets、outputs の期待値を揃えてからテストを通す。旧配置と新配置を同時に標準探索させる中間状態は作らない。

### 3.3 single-file macro の扱い

single-file macro は許容する。`macros\<macro_id>.py` に `MacroBase` 派生クラスが 1 件だけなら manifest は不要である。複数クラスや import 前 metadata が必要な場合は manifest entrypoint で明示する。

```toml
[macro]
id = "sample_single_file"
name = "Sample Single File"
entrypoint = "sample_single_file:SampleSingleFileMacro"
settings = "project:resources/sample_single_file/settings.toml"
```

### 3.4 パス方針

`cmd.load_img()` は assets を読み込む API、`cmd.save_img()` は run outputs へ書き込む API として扱う。settings は `MacroSettingsResolver` が解決し、Resource Store は settings TOML を探索しない。

Markdown の説明文では Windows 配置例として `\` を使う。`macro.toml` の `entrypoint` と `settings` など、ファイル内に永続化する path 文字列は portable path として `/` を使う。

## 4. 実装仕様

### 4.1 公開インターフェース

本ガイドは呼び出し側の移行手順を示す。`MacroRuntime`、`DefaultCommand`、Resource File I/O、settings lookup の公開 API 正本は、それぞれ `RUNTIME_AND_IO_PORTS.md`、`RESOURCE_FILE_IO.md`、`CONFIGURATION_AND_RESOURCES.md` を参照する。

移行後のマクロ側で使う公開面は次の範囲である。

```python
from nyxpy.framework.core.macro.base import MacroBase
from nyxpy.framework.core.macro.command import Command, DefaultCommand


class FrlgIdRngMacro(MacroBase):
    macro_id = "frlg_id_rng"
    display_name = "FRLG ID RNG"
    settings_path = "project:resources/frlg_id_rng/settings.toml"

    def initialize(self, cmd: Command, args: dict) -> None: ...
    def run(self, cmd: Command) -> None: ...
    def finalize(self, cmd: Command) -> None: ...


cmd = DefaultCommand(context=context)
```

`DefaultCommand(context=...)` はテストや adapter 実装で必要な場合だけ使う。通常のマクロは GUI/CLI 経路から渡された `cmd` を受け取り、`DefaultCommand` を直接生成しない。

### 4.2 manifest の追加

`macro.toml` は必須ではない。次の条件に該当するマクロだけ `macros\<macro_id>\macro.toml` を追加する。

| 条件 | manifest 要否 |
|------|---------------|
| 単一 `MacroBase` クラスだけの軽量マクロ | 不要 |
| class metadata で `settings_path` を示せる | 不要 |
| 1 パッケージに複数 entrypoint がある | 必須 |
| GUI/CLI 一覧に import 前 metadata や args schema を出したい | 必須 |
| 配布・共有用に ID、説明、tags、resource roots を固定したい | 推奨 |

```toml
[macro]
id = "frlg_id_rng"
name = "FRLG ID RNG"
entrypoint = "macros.frlg_id_rng.macro:FrlgIdRngMacro"
settings = "project:resources/frlg_id_rng/settings.toml"
```

`entrypoint` は `module:ClassName` 形式とする。`id` はディレクトリ名や表示名ではなく、リソース配置とログ相関に使う安定 ID とする。manifest がない場合はファイル名またはディレクトリ名を ID とし、必要に応じて class metadata `macro_id` で上書きする。

manifest なしで settings を使う場合は class metadata を使う。

```python
class FrlgIdRngMacro(MacroBase):
    macro_id = "frlg_id_rng"
    display_name = "FRLG ID RNG"
    settings_path = "project:resources/frlg_id_rng/settings.toml"
```

### 4.3 settings の移行

旧配置（Windows 表記例）:

```text
static\frlg_id_rng\settings.toml
```

新配置（Windows 表記例）:

```text
resources\frlg_id_rng\settings.toml
```

manifest を使う場合:

```toml
[macro]
settings = "project:resources/frlg_id_rng/settings.toml"
```

class metadata を使う場合:

```python
class FrlgIdRngMacro(MacroBase):
    settings_path = "project:resources/frlg_id_rng/settings.toml"
```

相対パスを使う場合は macro root 相対とする。`project:` prefix を付けた場合は `project_root` 相対とする。`Path.cwd()` からの探索は行わない。

### 4.4 assets の移行

旧配置（Windows 表記例）:

```text
static\frlg_id_rng\button_a.png
static\frlg_id_rng\templates\title.png
```

新配置の例（Windows 表記例）:

```text
resources\frlg_id_rng\assets\button_a.png
resources\frlg_id_rng\assets\templates\title.png
```

マクロ同梱にしたい assets は次へ置ける。

```text
macros\frlg_id_rng\assets\templates\title.png
```

`cmd.load_img("templates/title.png")` は assets root からの相対パスとして解決される。`static\frlg_id_rng` や絶対パスを直接渡す前提は移行対象である。

```python
# 移行前: static 配置を呼び出し側に含めている
template = cmd.load_img("frlg_id_rng/templates/title.png")
```

```python
# 移行後: assets root からの相対パスだけを渡す
template = cmd.load_img("templates/title.png")
```

### 4.5 outputs の移行

`cmd.save_img("result.png", image)` の保存先は次に固定する。

```text
runs\<run_id>\outputs\result.png
```

旧 `static\<macro_name>` への保存、`legacy_static_write=True`、`resource.write_mode = "legacy_static"` は定義しない。ファイル名先頭の macro ID prefix は除去しない。

```python
# 移行前: static 配下へ直接保存する
output_path = Path("static/frlg_initial_seed/result.csv")
output_path.write_text(csv_text, encoding="utf-8")
```

```python
# 移行後: run outputs へ成果物として保存する
from nyxpy.framework.core.io.resources import OverwritePolicy


with cmd.artifacts.open_output(
    "result.csv",
    mode="wb",
    overwrite=OverwritePolicy.REPLACE,
) as fp:
    fp.write(csv_text.encode("utf-8"))
```

`RunArtifactStore.open_output()` は binary mode のみを受け付ける。テキストを保存する場合は呼び出し側で `bytes` へ変換する。

### 4.6 `DefaultCommand` 直接生成の修正

マクロは GUI/CLI 経路から渡された `cmd` を使う。次の直接生成は削除する。

```python
# 移行前: 不可
cmd = DefaultCommand(serial_device=serial, capture_device=capture)
```

テストで Command が必要な場合は、`tests\support\fake_execution_context.py` の fake `ExecutionContext` fixture または `MacroRuntimeBuilder` から `ExecutionContext` を作成して `DefaultCommand(context=...)` を使う。adapter 実装者は builder から渡された context を利用し、旧具象引数を再導入しない。マクロ固有ロジックは可能な範囲で `Command` 不要の純粋関数に分離する。

```python
# 移行後: テスト用に context を明示する
context = fake_execution_context()
cmd = DefaultCommand(context=context)
```

```python
# 移行後: Command 不要なロジックは純粋関数としてテストする
def decide_next_button(state: dict[str, int]) -> Button:
    return Button.A if state["ready"] else Button.B
```

### 4.7 `Command.stop()` の移行

現行 `DefaultCommand.stop()` は停止要求後に即時 `MacroStopException` を送出していた。再設計後の `Command.stop()` は協調キャンセル専用とし、停止要求だけを登録する。即時例外送出の互換引数は提供しないため、長い処理から脱出したい箇所は `cmd.wait()`、`@check_interrupt`、`CancellationToken.throw_if_requested()` などの safe point に寄せる。

```python
# 移行前: stop() 呼び出し直後の例外送出に依存
cmd.stop()
```

```python
# 移行後: 停止要求後は次の safe point で脱出する
cmd.stop()
cmd.wait(0)
```

### 4.8 設定パラメータ

| パラメータ | 型 | デフォルト | 説明 |
|------------|-----|------------|------|
| `[macro].id` | `str` | convention default | manifest を使う場合のマクロ安定 ID |
| `[macro].entrypoint` | `str` | convention discovery | `module:ClassName` 形式。複数候補など曖昧な場合は必須 |
| `[macro].settings` | `str | None` | `None` | settings TOML の path。未指定なら class metadata を見る |
| `MacroBase.settings_path` | `str | None` | `None` | manifest なし、または manifest に settings がない場合の settings TOML path |
| `project:` prefix | `str` | なし | `project_root` 相対 path を表す |

### 4.9 エラーハンドリング

| エラー | 発生条件 |
|--------|----------|
| `MacroLoadError` | module import に失敗、class が `MacroBase` でない、convention discovery が曖昧、manifest entrypoint が不正 |
| `ConfigurationError` | settings path が root 外参照、絶対パス、空 path、存在しない必須 file |
| `ResourcePathError` | assets / outputs の root 外参照、未許可拡張子、ディレクトリ指定 |
| `ResourceWriteError` | `cmd.save_img()` の書き込みまたは atomic replace に失敗 |

### 4.10 移行対象代表マクロ

代表マクロは、全マクロを一度に修正する前に移行手順とテストゲートを固定するための対象である。代表マクロの追加・削除は本表を更新し、`DEPRECATION_AND_MIGRATION.md` と `TEST_STRATEGY.md` では本表を参照する。

| macro_id | 採用理由 | 必要な移行項目 | 必須テスト |
|----------|----------|----------------|------------|
| `frlg_id_rng` | settings、画像リソース、output 保存を含む代表例 | 明示 settings source、assets root 相対 path、run outputs 保存 | `test_sample_turbo_macro_saves_capture_to_run_outputs_without_prefix_stripping`, `test_file_settings_and_exec_args_are_merged_with_exec_args_precedence` |
| `sample_turbo_a_macro` | single-file convention discovery の最小例 | manifest なし discovery、公開 import 契約 | `test_registry_loads_convention_single_file_macro` |
| `frlg_initial_seed` | package 型 macro の代表例 | package entrypoint、class metadata、settings 未指定時の `{}` | `test_repository_representative_macros_keep_lifecycle_contract` |

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| ユニット | `test_registry_loads_convention_single_file_macro` | manifest なしの single-file macro を convention discovery でロードする |
| ユニット | `test_registry_loads_manifest_single_file_macro` | single-file macro を manifest entrypoint からロードできる |
| ユニット | `test_registry_requires_manifest_when_convention_is_ambiguous` | 複数候補など曖昧な場合だけ manifest entrypoint を要求する |
| ユニット | `test_macro_settings_resolver_loads_explicit_settings` | manifest または class metadata settings path から settings を読む |
| ユニット | `test_macro_settings_resolver_does_not_read_legacy_static_settings` | 旧 `static` settings を暗黙探索しない |
| ユニット | `test_command_load_img_uses_resource_store` | `cmd.load_img()` が assets root から読む |
| ユニット | `test_command_save_img_uses_run_artifact_store` | `cmd.save_img()` が run outputs へ保存する |
| ユニット | `test_default_command_rejects_legacy_constructor_args` | 旧具象引数コンストラクタを受け付けない |
| 結合 | `test_convention_package_and_single_file_macros_load_without_manifest` | 移行後代表マクロが manifest なしでもロードされる |
| 結合 | `test_optional_manifest_file_does_not_break_package_macro_load` | manifest ありの package macro をロードできる |
| 結合 | `test_file_settings_and_exec_args_are_merged_with_exec_args_precedence` | settings と実行引数が Runtime builder で merge され、実行引数が優先される |
| 結合 | `test_repository_representative_macros_keep_lifecycle_contract` | リポジトリ代表マクロが lifecycle signature を維持する |

## 6. 実装チェックリスト

- [x] 高度機能が必要なマクロだけ `macro.toml` を追加し、`id` / `entrypoint` / `settings` を定義
- [x] `static\<macro_name>\settings.toml` を manifest または class metadata settings path へ移動
- [x] 読み込み専用画像を `resources\<macro_id>\assets` または `macros\<macro_id>\assets` へ移動
- [x] `cmd.load_img()` に渡す path を assets root 相対へ修正
- [x] `cmd.save_img()` の保存先が `runs\<run_id>\outputs` になる前提へ修正
- [x] ファイル名先頭の macro ID prefix 除去に依存する処理を削除
- [x] `DefaultCommand(serial_device=..., capture_device=..., ...)` の直接生成を削除
- [x] single-file macro は convention discovery で一意にロードできることを確認し、曖昧な場合だけ manifest entrypoint を追加
- [x] 代表マクロの移行後結合テストを追加
- [x] 旧 `static` / `cwd` fallback に依存するテストを削除または新仕様へ更新
