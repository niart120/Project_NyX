# GUI 再設計 Phase 4: Cleanup と回帰防止

> **文書種別**: Phase 仕様。GUI close 時の後始末、削除対象 API の回帰防止、最終テストを扱う。  
> **対象モジュール**: `src\nyxpy\gui\main_window.py`, `src\nyxpy\gui\app_services.py`, `tests\gui\`  
> **親仕様**: `IMPLEMENTATION_PLAN.md`  
> **先行条件**: Phase 1-3 完了。

## 1. 目的

GUI close 時の cancel、wait、preview 停止、manager release、logging close の順序を固定し、失敗を沈黙させない。あわせて `MacroExecutor`、`DefaultCommand`、`LogManager` など削除対象 API への逆戻りをテストで防ぐ。

## 2. Close sequence

`MainWindow.closeEvent()` は次の順序で処理する。

1. 実行中 `RunHandle` があれば `cancel()` を呼ぶ。
2. 設定値 timeout で `wait(timeout)` する。
3. timeout した場合は `LoggerPort.technical("WARNING", ..., event="macro.cancel_timeout")` を記録する。
4. preview timer を停止する。
5. `GuiAppServices.close()` で manager release と logging close を行う。
6. `super().closeEvent(event)` を呼ぶ。

timeout は固定値ではなく、`runtime.release_timeout_sec` または GUI 設定値から読む。設定がない場合の既定値は `5` 秒とする。

## 3. Cleanup failure

cleanup 失敗は主結果や close 処理を不必要に壊さない。ただし、`pass` で握りつぶしてはならない。

| 失敗箇所 | UI 表示 | 技術ログ |
|----------|---------|----------|
| `RunHandle.wait()` timeout | 原則表示しない | `macro.cancel_timeout` |
| capture release | 原則表示しない | `resource.cleanup_failed` |
| serial close | 原則表示しない | `resource.cleanup_failed` |
| logging close | `stderr` fallback を許可 | `resource.cleanup_failed` または fallback |

`LoggerPort` が既に閉じられている場合は、stderr fallback へ短文を出す。traceback や secret 値を GUI dialog に出さない。

## 4. 削除対象 API の回帰防止

`src\nyxpy\gui\` から次を import してはならない。

- `nyxpy.framework.core.macro.executor.MacroExecutor`
- `nyxpy.framework.core.macro.command.DefaultCommand`
- `nyxpy.framework.core.logger.log_manager.LogManager`
- `nyxpy.framework.core.logger.log_manager.log_manager`

許可される Runtime 入口は `MacroRuntimeBuilder`、`RuntimeBuildRequest`、`RunHandle`、`RunResult` である。

## 5. テスト方針

| テスト名 | 検証内容 |
|----------|----------|
| `test_main_window_close_cancels_and_waits_with_configured_timeout` | close 時に cancel と wait を行う |
| `test_main_window_close_logs_cancel_timeout` | wait timeout が技術ログに残る |
| `test_main_window_close_logs_cleanup_failures` | release 例外を沈黙させない |
| `test_gui_does_not_import_removed_runtime_apis` | 削除対象 API を import していない |
| `test_gui_runtime_flow_smoke` | Phase 1-3 の最小実行フローが通る |

## 6. 完了ゲート

| ゲート | 判定 |
|--------|------|
| Close order gate | cancel -> wait -> preview stop -> service close の順序が固定される |
| Cleanup visibility gate | cleanup 失敗が技術ログまたは fallback に残る |
| Removal gate | GUI から削除対象 API への import がない |
| Final regression gate | `uv run pytest tests\gui\` が通る |

