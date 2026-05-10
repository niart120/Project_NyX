# CLI 再設計追従 実装修正仕様書

> **文書種別**: 実装修正仕様。フレームワーク再設計後に CLI adapter が満たすべき責務、残修正、検証ゲートを定義する。
> **対象モジュール**: `src\nyxpy\cli\`, `tests\integration\test_cli_runtime_adapter.py`, `tests\unit\cli\`
> **目的**: CLI を `MacroRuntimeBuilder` / `RuntimeBuildRequest` / `RunResult` ベースの薄い adapter に固定し、旧 `DefaultCommand` 直接構築、通知 secret の独自入力、実行後 cleanup の沈黙失敗を排除する。
> **関連ドキュメント**: `spec\framework\rearchitecture\IMPLEMENTATION_PLAN.md`, `spec\framework\rearchitecture\RUNTIME_AND_IO_PORTS.md`, `spec\framework\rearchitecture\LOGGING_FRAMEWORK.md`, `spec\framework\rearchitecture\OBSERVABILITY_AND_GUI_CLI.md`, `spec\framework\rearchitecture\DEPRECATION_AND_MIGRATION.md`
> **破壊的変更**: CLI オプション互換は維持する。終了コードは成功 `0`、設定不正 `1`、実行失敗 `2`、中断 `130` を正とする。通知 secret を CLI 引数で受け取る機能は追加しない。

## 1. 概要

### 1.1 目的

CLI はフレームワーク再設計後の composition root であり、マクロ実行中核ではない。引数解析、実行要求の生成、ユーザー表示、終了コード変換、起動時依存の組み立てだけを担当し、マクロ発見、settings 解決、Resource I/O、device port、通知、実行 lifecycle は Runtime / Builder / Ports へ委譲する。

### 1.2 現状確認

現行 `src\nyxpy\cli\run_cli.py` は `CliPresenter`、`RuntimeBuildRequest`、`MacroRuntimeBuilder.run()`、`RunResult` へ移行済みである。一方で、次の点は CLI adapter 仕様として明文化し、実装修正の完了ゲートに入れる。

| 項目 | 現状 | 修正方針 |
|------|------|----------|
| Builder 生成 | `create_legacy_runtime_builder()` を CLI から呼ぶ | CLI は `MacroRuntimeBuilder` interface だけに依存する。互換 helper 名は移行中の内部詳細として扱う |
| helper docstring | `create_runtime_builder()` が Command 生成と説明している | Runtime builder 生成の説明へ修正する |
| cleanup | `finally` で manager release 例外を `pass` している | 例外は `LoggerPort.technical()` へ記録し、終了コードの主結果は上書きしない |
| device 選択 | CLI は manager の active device を直接取得しない | 検出、dummy 許可、未選択エラーは builder の責務に固定する |
| 通知 secret | `SecretsSettings` から通知 handler を生成している | CLI 引数、`exec_args`、通常 settings へ secret を渡さないことをテストで固定する |
| 終了コード | `RunResult.status` から変換済み | 設定不正 `1` と実行失敗 `2` の境界を presenter / error mapper で固定する |

### 1.3 完了状態

CLI の最終状態は次の呼び出し列で表せる。

```text
run_cli.main()
  -> build_parser().parse_args()
  -> configure_logging()
  -> create_runtime_builder(...)
  -> RuntimeBuildRequest(macro_id, entrypoint="cli", exec_args)
  -> MacroRuntimeBuilder.run(request)
  -> CliPresenter.render_result(result)
  -> CliPresenter.exit_code(result)
  -> close logging and release composition-root resources
```

`src\nyxpy\cli\` から `MacroExecutor`、`DefaultCommand`、`LogManager`、`log_manager`、GUI module を import してはならない。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `spec\cli\rearchitecture\IMPLEMENTATION_PLAN.md` | 新規 | 本仕様書 |
| `src\nyxpy\cli\run_cli.py` | 変更 | Runtime adapter、presenter、cleanup、docstring、設定不正 mapping を整理 |
| `src\nyxpy\cli\__init__.py` | 変更なし | CLI 公開面を増やさない |
| `tests\integration\test_cli_runtime_adapter.py` | 変更 | Runtime request、通知 secret、終了コード、cleanup logging を検証 |
| `tests\unit\cli\test_run_cli_parser.py` | 新規 | CLI 引数互換、通知 secret 引数不在、`--define` 解析を検証 |
| `tests\unit\cli\test_cli_presenter.py` | 新規 | `RunResult` から表示文言と終了コードへの変換を検証 |

## 3. 設計方針

### 3.1 CLI adapter の責務

| 責務 | CLI が行うこと | CLI が行わないこと |
|------|---------------|-------------------|
| 引数解析 | macro ID、device 名、protocol、baud、`--define`、verbosity を受け取る | 通知 secret、resource path override、settings file path の暗黙 fallback を受け取る |
| 依存生成 | logger、protocol、registry、builder を組み立てる | `DefaultCommand` を構築する |
| 実行 | `RuntimeBuildRequest(entrypoint="cli")` を渡す | lifecycle を直接呼ぶ |
| 表示 | `RunResult` を短いユーザー文言へ変換する | traceback、絶対 path、secret 値を標準出力へ出す |
| 終了 | logging close と composition-root resource release を行う | cleanup 失敗を沈黙させる |

### 3.2 CLI オプション互換

次のオプションは維持する。

| オプション | 維持理由 | Runtime へ渡す先 |
|------------|----------|------------------|
| `macro_name` | 既存 CLI の実行対象指定 | `RuntimeBuildRequest.macro_id` |
| `--serial` | 使用デバイス指定 | builder の device selection |
| `--capture` | 使用デバイス指定 | builder の device selection |
| `--protocol` | controller protocol 指定 | protocol factory |
| `--baud` | serial baudrate 指定 | builder の serial selection |
| `--silence` | console verbosity | logging composition |
| `--verbose` | console verbosity | logging composition |
| `--define key=value` | 実行引数 | `RuntimeBuildRequest.exec_args` |

通知 secret を受け取る `--discord-webhook-url`、`--bluesky-password` などの CLI 引数は追加しない。通知設定は `SecretsSettings` 由来の snapshot だけを入力元とする。

### 3.3 エラーと終了コード

| 条件 | 返す終了コード | 表示 | 技術ログ |
|------|----------------|------|----------|
| `RunStatus.SUCCESS` | `0` | 原則なし。verbose 時だけ成功表示を許可 | `macro.finished` |
| `RunStatus.CANCELLED` | `130` | `Macro execution was interrupted` | `macro.cancelled` |
| `RunStatus.FAILED` | `2` | `ErrorInfo.message` または短い失敗文言 | `macro.failed` |
| CLI 引数不正 | argparse の標準終了 | argparse に従う | 原則なし |
| protocol / device / settings 構成不正 | `1` | `エラー: ...` | `configuration.invalid` |
| 未捕捉例外 | `2` | `Unexpected error. See logs for details.` | `macro.failed` または `cli.unhandled` |
| cleanup 失敗 | 主結果を維持 | 主結果の表示を維持 | `resource.cleanup_failed` |

cleanup 失敗は本体の終了コードを上書きしない。ただし、cleanup 失敗を `pass` で握りつぶしてはならない。

### 3.4 ロギング

CLI は `create_default_logging(base_dir=Path.cwd() / "logs")` で作成した `LoggerPort` を Runtime builder へ渡す。`--silence` と `--verbose` は console sink の出力レベルだけを変更し、file backend の技術ログ保存を無効化しない。

`CliPresenter.render_result()` が返す `UserMessage` は標準出力向けの短文である。traceback、内部絶対 path、通知 payload、secret 値は含めない。詳細は `LoggerPort.technical()` へ送る。

未捕捉例外の標準出力も固定文言にする。`str(exc)` は絶対 path、通知 payload、secret 値を含み得るため、表示へ連結しない。

### 3.5 Builder 生成と device 検出

CLI は builder に device 名、baudrate、protocol、logger、notification handler を渡す。実デバイスの登録待ち、dummy device の許可判定、未選択エラー、frame readiness は builder / Port adapter の責務である。

CLI から `serial_manager.get_active_device()`、`capture_manager.get_active_device()`、`DefaultCommand(...)` を呼ばない。manager への release は composition root の後始末としてだけ許可する。

## 4. 実装仕様

### 4.1 `CliPresenter`

`CliPresenter` は `RunResult` からユーザー表示と終了コードを決める唯一の CLI 表示 adapter とする。

```python
class CliPresenter:
    def render_result(self, result: RunResult) -> UserMessage: ...
    def exit_code(self, result: RunResult) -> int: ...
```

`render_result()` は `RunResult.error.message` を表示に使ってよいが、`ErrorInfo.details`、traceback、exception repr は表示しない。技術詳細は `LoggerPort.technical()` の入力であり、presenter の責務ではない。

### 4.2 `create_runtime_builder()`

`create_runtime_builder()` は CLI 内部 helper として扱う。既存テストから import されてもよいが、外部互換 API として保証しない。

必須要件:

- docstring は Runtime builder 生成を説明する。
- `SecretsSettings()` を読み、通知 handler へ渡す。
- CLI 引数由来の secret 値を受け取らない。
- `MacroRegistry(project_root)` を生成し、`registry.reload()` を呼ぶ。
- `MacroRuntimeBuilder` interface を返す。
- `resources_dir` は移行中の project root override としてだけ扱う。Resource I/O の個別 fallback を CLI に実装しない。

### 4.3 `execute_macro()`

`execute_macro()` は `RuntimeBuildRequest` を作成して `runtime_builder.run()` を呼ぶ。例外変換は Runtime 側が `RunResult` へ正規化するため、CLI は戻り値をログと presenter へ渡す。

必須要件:

- `entrypoint` は `"cli"` 固定。
- `macro_name` は `RuntimeBuildRequest.macro_id` へ渡す。
- `exec_args` は `parse_define_args()` の結果を渡す。
- `RunStatus.CANCELLED` は失敗ではなく中断として扱う。
- `RunStatus.FAILED` では `logger.user("ERROR", ...)` を出す。

### 4.4 `cli_main()`

`cli_main()` は構成不正と実行失敗を分ける。

| 入力 | 処理 |
|------|------|
| argparse 済み `Namespace` | protocol、logging、builder、exec args を生成する |
| `ValueError` / `ConfigurationError` | `configuration.invalid` としてログし、終了コード `1` |
| `RunResult` | presenter で表示と終了コードへ変換 |
| 未捕捉例外 | `LoggerPort.technical()` へ記録し、固定文言を表示して終了コード `2` |

`finally` では logging と manager release を行う。release 例外は logger が生きている場合に `technical("WARNING", ..., event="resource.cleanup_failed")` へ記録する。logger が生成されていない段階の cleanup 失敗は `stderr` へ短文を出す。

未捕捉例外時の表示文言は `Unexpected error. See logs for details.` に固定する。例外 message、repr、traceback は標準出力へ出さず、`LoggerPort.technical(..., exc=e)` のみに渡す。

### 4.5 Parser

Parser は通知 secret 引数を持たないことをテストで固定する。`--define` は複数回指定を許可し、`parse_define_args()` の仕様に従って `dict[str, FrameworkValue]` へ変換する。

`--serial` と `--capture` の required 方針は現行互換を維持する。将来 GUI と同じ設定 store からの省略実行を追加する場合は、本仕様を更新してから実装する。

## 5. テスト方針

### 5.1 フェーズ分割

CLI は修正範囲が小さいため、分割仕様書は作らず本書内のフェーズで実装順を固定する。各フェーズは単独でテスト可能な単位にし、GUI 側の大きな再設計と同じ粒度にはしない。

| フェーズ | 目的 | 主な変更 | 完了条件 |
|----------|------|----------|----------|
| Phase 1: Presenter / parser 固定 | CLI の入出力契約を先に固定する | `CliPresenter` の unit test、既存 parser option、通知 secret 引数なし、`--define` 伝播 | 終了コードと表示文言が `RunResult` から一意に決まる |
| Phase 2: Runtime entry 整理 | CLI 実行入口を Runtime builder へ閉じる | `execute_macro()`、`RuntimeBuildRequest(entrypoint="cli")`、`create_runtime_builder()` docstring | CLI が `DefaultCommand` / `MacroExecutor` を参照しない |
| Phase 3: error mapping / cleanup 可視化 | 構成不正と cleanup 失敗を沈黙させない | `ConfigurationError` の終了コード `1` 化、release / close 失敗 logging | cleanup 失敗が `resource.cleanup_failed` として残る |
| Phase 4: regression gate | 削除対象 API への逆戻りを防ぐ | 静的 import テスト、integration test の整理 | `MacroExecutor`、`DefaultCommand`、`LogManager` 参照が CLI にない |

Phase 1 は実装前に赤いテストを置いてよい。Phase 2 以降は既存 `tests\integration\test_cli_runtime_adapter.py` を拡張し、必要な parser / presenter のみ `tests\unit\cli\` へ分ける。

### 5.2 テスト一覧

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| ユニット | `test_cli_presenter_exit_codes` | 成功 `0`、失敗 `2`、中断 `130` を返す |
| ユニット | `test_cli_presenter_excludes_traceback` | 表示文言に traceback、絶対 path、secret 値が含まれない |
| ユニット | `test_cli_unhandled_exception_uses_fixed_user_message` | 未捕捉例外の標準出力に例外 message を含めない |
| ユニット | `test_cli_parser_keeps_existing_options` | 既存オプションを受け取れる |
| ユニット | `test_cli_does_not_accept_notification_secret_args` | 通知 secret 引数が parser に存在しない |
| ユニット | `test_cli_define_args_are_passed_to_request` | `--define` が `RuntimeBuildRequest.exec_args` へ渡る |
| 結合 | `test_cli_uses_runtime_and_run_result` | `execute_macro()` が `MacroRuntimeBuilder.run()` を呼び、`RunResult` を返す |
| 結合 | `test_cli_notification_settings_source_is_secrets_store` | 通知 handler の入力が `SecretsSettings` である |
| 結合 | `test_cli_cleanup_failures_are_logged` | release 例外を沈黙させない |
| 結合 | `test_cli_configuration_error_returns_1` | 構成不正は終了コード `1` |
| 結合 | `test_cli_runtime_failure_returns_2` | 実行失敗は終了コード `2` |
| 静的 | `test_cli_does_not_import_removed_runtime_apis` | `MacroExecutor`、`DefaultCommand`、`LogManager` を import しない |

## 6. 実装チェックリスト

- [ ] `create_runtime_builder()` の docstring を Runtime builder 生成へ修正する。
- [ ] `cli_main()` の cleanup 例外を `LoggerPort.technical()` または `stderr` へ記録する。
- [ ] `ConfigurationError` を `ValueError` と同じ構成不正系に分類する。
- [ ] `CliPresenter` の終了コードと表示文言を unit test へ分離する。
- [ ] Parser に通知 secret 引数がないことを unit test で固定する。
- [ ] `src\nyxpy\cli\` から削除対象 API の import がないことをテストで固定する。
- [ ] `create_legacy_runtime_builder()` への依存が残る場合は CLI 内部 helper に閉じ込め、CLI の公開互換 API として扱わない。
- [ ] `uv run pytest tests\unit\cli\ tests\integration\test_cli_runtime_adapter.py` を通す。

## 7. 完了ゲート

CLI 移行は次をすべて満たした時点で完了とする。

| ゲート | 判定 |
|--------|------|
| Runtime entry gate | CLI 実行は `RuntimeBuildRequest(entrypoint="cli")` と `MacroRuntimeBuilder.run()` を使う |
| No direct command gate | CLI から `DefaultCommand` を直接構築しない |
| Secret source gate | 通知 secret は `SecretsSettings` 由来の snapshot だけから生成する |
| Exit code gate | `RunResult` と構成不正から終了コードを一意に決める |
| Cleanup visibility gate | release / close 失敗を沈黙させない |
| Removal gate | `MacroExecutor`、`LogManager`、`log_manager` 参照が CLI にない |
