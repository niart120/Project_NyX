# CLI 再設計 追加修正仕様書

> **文書種別**: 追加修正仕様。CLI 再設計追従後に見つかった legacy helper、manager singleton、secret 入力元、cleanup 表現の不整合を修正する。
> **対象モジュール**: `src\nyxpy\cli\`, `tests\unit\cli\`, `tests\integration\test_cli_runtime_adapter.py`
> **親仕様**: `IMPLEMENTATION_PLAN.md`
> **関連ドキュメント**: `spec\framework\rearchitecture\RUNTIME_AND_IO_PORTS.md`, `spec\framework\rearchitecture\DEPRECATION_AND_MIGRATION.md`, `spec\framework\rearchitecture\OBSERVABILITY_AND_GUI_CLI.md`
> **破壊的変更**: CLI オプション互換は維持する。CLI 内部 helper、manager 直接利用、cleanup 経路は互換対象に含めない。

## 1. 概要

### 1.1 目的

CLI adapter を `MacroRuntimeBuilder.run(RuntimeBuildRequest)` の呼び出しに固定し、旧 Runtime builder 補助関数、manager singleton の active device 取得、manager release、`SecretsSettings` 直参照に戻らない状態を追加修正の完了条件として定義する。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| CLI adapter | 引数解析、Runtime request 生成、表示、終了コード変換だけを担当する上位 adapter |
| Runtime builder | `MacroRuntimeBuilder`。settings / secrets snapshot、device discovery、Port factory、logger から実行 context と Runtime を組み立てる |
| Legacy helper | `legacy` 名を含む Runtime builder 補助関数。CLI の最終実装には残さない |
| Secrets snapshot | `SecretsStore` 由来の secret 値 snapshot。CLI 引数、通常 settings、`exec_args` へ複製しない |
| Cleanup | `MacroRuntimeBuilder.shutdown()` と logging close。失敗しても主結果の終了コードを上書きしない |

### 1.3 背景・問題

CLI 再設計計画では Runtime 入口化が進んでいたが、文書上に旧 builder helper、manager release、`SecretsSettings` 直参照を許すように読める記述が残っていた。これらは既存マクロ互換契約ではなく CLI 内部実装なので、追加修正で削除条件を明示する。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| CLI の実行入口 | Runtime builder 経由だが legacy helper 名が残り得る | `MacroRuntimeBuilder.run(request)` だけを実行入口にする |
| manager singleton 直接利用 | active device 取得と release が戻る余地がある | CLI から `serial_manager` / `capture_manager` / settings singleton を直接参照しない |
| secret 入力元 | `SecretsSettings` 直参照に読める箇所がある | `SecretsStore` 由来の secrets snapshot だけを builder へ渡す |
| cleanup 失敗 | `pass` や manager release 表現が残り得る | builder shutdown / logging close 失敗を技術ログまたは stderr へ残す |

### 1.5 着手条件

- `IMPLEMENTATION_PLAN.md` の CLI adapter 方針が `RuntimeBuildRequest(entrypoint="cli")` と `MacroRuntimeBuilder.run()` へ更新済みである。
- `RUNTIME_AND_IO_PORTS.md` の builder API に `shutdown()` が定義済みである。
- `DEPRECATION_AND_MIGRATION.md` で manager singleton は新 Runtime 経路から直接参照しない方針が確定している。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `spec\cli\rearchitecture\FOLLOWUP_FIXES.md` | 新規 | 本仕様書 |
| `spec\cli\rearchitecture\IMPLEMENTATION_PLAN.md` | 変更 | 本仕様への参照と追加ゲートを反映 |
| `src\nyxpy\cli\run_cli.py` | 変更 | legacy helper 依存、manager release、`SecretsSettings` 直参照を削除 |
| `tests\unit\cli\test_cli_presenter.py` | 新規 | 表示・終了コードを検証 |
| `tests\unit\cli\test_run_cli_parser.py` | 新規 | parser と secret 引数不在を検証 |
| `tests\integration\test_cli_runtime_adapter.py` | 変更 | Runtime request、builder shutdown、secret source、削除対象 import を検証 |

## 3. 設計方針

### 3.1 Runtime entry

CLI 実行は次の流れに固定する。

```text
run_cli.main()
  -> parse args
  -> load SettingsStore / SecretsStore snapshots
  -> create MacroRuntimeBuilder(...)
  -> RuntimeBuildRequest(macro_id=..., entrypoint="cli", exec_args=...)
  -> builder.run(request)
  -> CliPresenter.exit_code(result)
  -> builder.shutdown()
  -> logging close
```

CLI は `DefaultCommand`、`MacroExecutor`、`MacroRuntime.run()` を直接呼ばない。

### 3.2 manager singleton の扱い

`serial_manager`、`capture_manager`、`global_settings`、`secrets_settings` は移行期間の互換 shim であり、新 CLI 経路から直接参照しない。デバイス検出、dummy 許可、frame readiness は `DeviceDiscoveryService`、Port factory、`MacroRuntimeBuilder` の責務にする。

### 3.3 secret 境界

CLI parser は通知 secret 引数を持たない。通知 secret は `SecretsStore` 由来の secrets snapshot から builder が `NotificationPort` を構築する時だけ参照する。`RuntimeBuildRequest`、`exec_args`、通常 settings、技術ログ extra へ secret 平文を渡さない。

### 3.4 cleanup

`finally` では `MacroRuntimeBuilder.shutdown()` と logging close を行う。cleanup 失敗は主結果の終了コードを上書きしないが、`LoggerPort.technical("WARNING", ..., event="resource.cleanup_failed")` または stderr fallback に短文を残す。

## 4. 実装仕様

### 4.1 `create_runtime_builder()`

```python
def create_runtime_builder(
    *,
    project_root: Path,
    settings_snapshot: SettingsSnapshot,
    secrets_snapshot: SecretsSnapshot,
    logger: LoggerPort,
    device_discovery: DeviceDiscoveryService,
    controller_output_factory: ControllerOutputPortFactory,
    frame_source_factory: FrameSourcePortFactory,
) -> MacroRuntimeBuilder: ...
```

`create_runtime_builder()` は CLI 内部 helper であり、外部互換 API として保証しない。`legacy` 名の helper へ委譲しない。

### 4.2 `execute_macro()`

```python
def execute_macro(
    runtime_builder: MacroRuntimeBuilder,
    *,
    macro_id: str,
    exec_args: Mapping[str, RuntimeValue],
) -> RunResult: ...
```

`RuntimeBuildRequest.entrypoint` は `"cli"` 固定である。`macro_name` という CLI 引数名は parser 互換として残してよいが、Runtime へ渡す値は `macro_id` として扱う。

### 4.3 cleanup sequence

```text
try:
    result = execute_macro(...)
    exit_code = presenter.exit_code(result)
finally:
    try builder.shutdown()
    except Exception as exc: log cleanup warning or stderr fallback
    try logging.close()
    except Exception as exc: stderr fallback
```

cleanup 例外を `pass` で握りつぶしてはならない。cleanup 失敗だけで `exit_code` を変更しない。

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| ユニット | `test_cli_parser_keeps_existing_options` | 既存 CLI オプションを維持する |
| ユニット | `test_cli_does_not_accept_notification_secret_args` | 通知 secret 引数が parser にない |
| ユニット | `test_cli_presenter_exit_codes` | 成功 `0`、失敗 `2`、中断 `130` を返す |
| 結合 | `test_cli_uses_runtime_builder_run` | `MacroRuntimeBuilder.run(RuntimeBuildRequest(entrypoint="cli"))` を呼ぶ |
| 結合 | `test_cli_uses_secrets_store_snapshot` | 通知 secret が `SecretsStore` 由来 snapshot だけから渡る |
| 結合 | `test_cli_shutdown_failure_is_logged` | `builder.shutdown()` 失敗を沈黙させない |
| 静的 | `test_cli_does_not_import_removed_runtime_apis` | `MacroExecutor`、`DefaultCommand`、`LogManager`、`log_manager` を import しない |
| 静的 | `test_cli_does_not_call_manager_singletons` | `serial_manager` / `capture_manager` / settings singleton を直接呼ばない |

## 6. 実装チェックリスト

- [x] `legacy` 名の Runtime builder 補助関数依存を削除する。
- [x] CLI の secret 入力元を `SecretsStore` snapshot に統一する。
- [x] manager singleton の active device 取得と release を CLI から削除する。
- [x] `MacroRuntimeBuilder.shutdown()` の cleanup 失敗を技術ログまたは stderr へ残す。
- [x] CLI parser に通知 secret 引数がないことを固定する。
- [x] 静的 import / call graph テストで旧 API への逆戻りを防ぐ。
