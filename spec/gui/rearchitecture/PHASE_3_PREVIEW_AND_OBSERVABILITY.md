# GUI 再設計 Phase 3: Preview 所有権と可観測性

> **文書種別**: Phase 仕様。Runtime 実行中の capture 所有権と GUI ログ表示を扱う。  
> **対象モジュール**: `src\nyxpy\gui\panes\preview_pane.py`, `src\nyxpy\gui\panes\log_pane.py`, `src\nyxpy\gui\log_sink.py`, `src\nyxpy\gui\main_window.py`  
> **親仕様**: `IMPLEMENTATION_PLAN.md`  
> **先行条件**: Phase 2 完了。GUI 実行状態が `RunHandle` ベースで管理されている。

## 1. 目的

Runtime 実行中に preview と macro execution が同じ capture device を同時利用して競合することを防ぐ。あわせて、GUI ログ表示を `UserEvent` 経由に固定し、core 層へ Qt 依存を持ち込まない状態を維持する。

## 2. Preview 所有権

初期実装では、Runtime 実行中に `PreviewPane` の timer を停止する。完了後に同じ `preview_fps` で再開する。

```text
run requested
  -> PreviewPane.pause_for_runtime()
  -> Runtime start
  -> RunResult received
  -> PreviewPane.resume_after_runtime()
```

この方針は capture device の thread safety を仮定しない。将来 shared frame source を導入する場合は、`FrameSourcePort` 側の lock 方針と GUI preview の読み取り契約を別仕様で定義する。

## 3. 実装仕様

### 3.1 `PreviewPane`

追加 API:

```python
def pause_for_runtime(self) -> None: ...
def resume_after_runtime(self) -> None: ...
```

要件:

- `pause_for_runtime()` は timer を停止する。
- 実行中 snapshot は無効化するか、last frame 保存に限定する。
- `resume_after_runtime()` は `apply_fps()` 相当で timer を再開する。
- `hideEvent()` で停止された場合に、実行完了で勝手に再開しないよう表示状態を考慮する。

### 3.2 `MainWindow` 連携

`_start_macro()` は Runtime start 前に `pause_for_runtime()` を呼ぶ。`_poll_run_handle()` は成功、失敗、中断、result 取得例外のいずれでも `resume_after_runtime()` を呼ぶ。

### 3.3 `LogPane` / `GuiLogSink`

`GuiLogSink` は `LogSink` adapter として `UserEvent` を Qt Signal へ変換するだけにする。widget 更新は `LogPane` の slot が担当する。

`LogPane` 要件:

- dispatcher へ sink を登録する。
- close 時に sink を解除し、`GuiLogSink.stop()` を呼ぶ。
- debug checkbox は `dispatcher.set_level()` だけを呼ぶ。
- close 後の `UserEvent` は widget に反映されない。

## 4. テスト方針

| テスト名 | 検証内容 |
|----------|----------|
| `test_preview_pauses_during_runtime_and_resumes_after_result` | 実行中に timer が止まり、結果後に再開する |
| `test_preview_resume_does_not_restart_hidden_widget` | 非表示状態では勝手に preview を再開しない |
| `test_snapshot_disabled_during_runtime` | 実行中 snapshot の扱いが明示される |
| `test_gui_log_pane_displays_user_event_from_sink` | `UserEvent` が表示される |
| `test_gui_log_sink_removed_on_close` | close 後の event が反映されない |
| `test_gui_log_debug_checkbox_updates_sink_level` | debug checkbox が sink level を更新する |

## 5. 完了ゲート

| ゲート | 判定 |
|--------|------|
| Capture ownership gate | Runtime 実行中に preview timer が停止する |
| Resume gate | 成功、失敗、中断、result 例外のいずれでも preview の扱いが一貫する |
| Qt boundary gate | framework 層が `nyxpy.gui` / Qt を import しない |
| Sink lifecycle gate | `LogPane` close 後に sink が解除される |

