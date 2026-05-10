# GUI 再設計 Phase 2: Runtime 実行制御

> **文書種別**: Phase 仕様。GUI の実行開始、cancel、polling、UI 状態を扱う。
> **対象モジュール**: `src\nyxpy\gui\main_window.py`, `src\nyxpy\gui\panes\control_pane.py`, `tests\gui\test_main_window.py`
> **親仕様**: `IMPLEMENTATION_PLAN.md`
> **先行条件**: Phase 1 完了。GUI が stable `macro_id` と service 経由の Runtime builder を使える。

## 1. 目的

GUI の実行制御を `RunHandle` / `RunResult` に寄せ、GUI スレッドから `Command.stop()` や旧 executor へ触れない状態にする。Cancel 後も `RunResult` が確定するまで二重実行を防ぐ。

## 2. 実行状態

| 状態 | 意味 | Run button | Cancel button | 状態遷移 |
|------|------|------------|---------------|----------|
| `IDLE` | 実行していない | 選択ありで有効 | 無効 | run -> `RUNNING` |
| `RUNNING` | Runtime thread が実行中 | 無効 | 有効 | cancel -> `CANCELLING`, done -> `FINISHED` |
| `CANCELLING` | 中断要求済み、結果待ち | 無効 | 無効 | done -> `FINISHED` |
| `FINISHED` | 結果反映済み | 選択ありで有効 | 無効 | run -> `RUNNING` |

`ControlPane.set_running(bool)` は `RUNNING` と `CANCELLING` を区別できないため、`set_run_state(state)` を追加する。既存 method は呼び出し元置換中の一時 wrapper に限り許可し、Phase 2 の実装差分内で全呼び出しを `set_run_state()` へ移す。Phase 4 完了までに公開 API から削除する。

## 3. 実装仕様

### 3.1 実行開始

`MainWindow._start_macro(exec_args)` は次を行う。

1. `MacroBrowserPane.selected_macro_id()` から stable ID を取得する。
2. `RuntimeBuildRequest(macro_id=macro_id, entrypoint="gui", exec_args=exec_args)` を作る。
3. `GuiAppServices.create_runtime_builder().start(request)` を呼ぶ。
4. 戻り値の `RunHandle` を保持する。
5. UI 状態を `RUNNING` にする。
6. poll timer を開始する。

実行対象未選択、builder 構成不正、`start()` 例外は `LoggerPort.technical()` へ記録し、UI には短い失敗文言だけを出す。

### 3.2 中断

`cancel_macro()` は `RunHandle.cancel()` だけを呼ぶ。`control_pane.set_running(False)` で即座に再実行可能にしてはならない。

```text
RUNNING
  -> cancel button
  -> handle.cancel()
  -> CANCELLING
  -> poll detects done
  -> RunResult(CANCELLED)
  -> FINISHED
```

`RunHandle.cancel()` が例外を出した場合は技術ログへ記録し、状態は `RUNNING` に戻すか `FINISHED` へ落とす。例外を握りつぶして `CANCELLING` に固定しない。

### 3.3 polling

`_poll_run_handle()` は `RunHandle.done()` が true になった時だけ `result()` を呼ぶ。`result()` 例外は `LoggerPort.technical()` に記録し、ユーザー表示は `エラー: 実行結果を取得できません` のような短文にする。

`RunResult` 取得後は次を行う。

- `last_run_result` を更新する。
- status label を `完了` / `中断` / `エラー: ...` へ更新する。
- UI 状態を `FINISHED` にする。
- `run_handle` を `None` にする。
- poll timer を止める。

## 4. テスト方針

| テスト名 | 検証内容 |
|----------|----------|
| `test_main_window_uses_run_handle` | `start()` の戻り値を保持する |
| `test_main_window_uses_selected_macro_id` | stable ID を request に渡す |
| `test_main_window_cancel_enters_cancelling_state` | cancel 後に再実行できない |
| `test_main_window_cancel_calls_handle_cancel_only` | `Command.stop()` 相当を呼ばない |
| `test_control_pane_exposes_run_state_api_only` | 最終公開 API が `set_run_state()` で、`set_running(bool)` を残していない |
| `test_main_window_poll_updates_status_from_run_result` | `RunResult` から UI を更新する |
| `test_main_window_poll_logs_result_exception` | result 取得例外を技術ログへ出す |

## 5. 完了ゲート

| ゲート | 判定 |
|--------|------|
| Runtime handle gate | GUI は `RunHandle` だけで実行中状態を管理する |
| Cancellation gate | cancel は `RunHandle.cancel()` のみ |
| Double-run prevention gate | `CANCELLING` 中に run button が有効にならない |
| No boolean state gate | `ControlPane.set_running(bool)` へ依存する GUI 呼び出しが残っていない |
| User display gate | traceback や内部 path を status / dialog に出さない |
