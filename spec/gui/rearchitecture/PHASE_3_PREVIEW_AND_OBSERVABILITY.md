# GUI 再設計 Phase 3: Preview device 切り替えと可観測性

> **文書種別**: Phase 仕様。capture device 切り替え時の preview 状態管理と GUI ログ表示を扱う。
> **対象モジュール**: `src\nyxpy\gui\panes\preview_pane.py`, `src\nyxpy\gui\panes\log_pane.py`, `src\nyxpy\gui\log_sink.py`, `src\nyxpy\gui\main_window.py`
> **親仕様**: `IMPLEMENTATION_PLAN.md`
> **先行条件**: Phase 2 完了。GUI 実行状態が `RunHandle` ベースで管理されている。

## 1. 目的

GUI 設定変更で capture device を切り替えるときに、preview が古い device 参照で更新を続けないようにする。あわせて、GUI ログ表示を `UserEvent` 経由に固定し、core 層へ Qt 依存を持ち込まない状態を維持する。

## 2. Preview device 切り替え

Runtime 実行中という理由だけでは `PreviewPane` の timer を停止しない。停止が必要なのは、GUI 設定変更で active capture device を切り替える間である。

```text
capture device setting changed
  -> PreviewPane.pause_for_device_switch()
  -> capture_manager.set_active(...)
  -> PreviewPane.set_capture_device(capture_manager.get_active_device())
  -> PreviewPane.resume_after_device_switch()
```

Runtime と preview の同時 capture 利用に排他が必要な場合は、`FrameSourcePort` / capture adapter 側の lock 方針として別仕様で定義する。GUI は「Runtime 実行中だから preview を止める」という暗黙の ownership ルールを持たない。

## 3. 実装仕様

### 3.1 `PreviewPane`

追加 API:

```python
def pause_for_device_switch(self) -> None: ...
def resume_after_device_switch(self) -> None: ...
```

要件:

- `pause_for_device_switch()` は timer を停止する。
- `set_capture_device()` は古い device 参照を新しい active device に置き換える。
- `resume_after_device_switch()` は widget が表示中で、かつ capture device が設定済みの場合だけ `apply_fps()` 相当で timer を再開する。
- `hideEvent()` で停止された場合に、device 切り替え完了で勝手に preview を再開しないよう表示状態を考慮する。
- Runtime 実行状態と snapshot 可否はこの API の責務に含めない。

### 3.2 `MainWindow` 連携

`apply_app_settings()` または `GuiAppServices.apply_settings()` は、capture device の変更がある場合に限り `pause_for_device_switch()` を呼ぶ。device 反映に成功した場合は `set_capture_device()` で参照を更新し、最後に `resume_after_device_switch()` を呼ぶ。

device 切り替えに失敗した場合も、preview の停止状態を固定しない。古い device を使い続けるか、device なし状態に落とすかを明示し、その状態に応じて preview を再開または停止維持する。失敗詳細は `LoggerPort.technical()` へ記録し、UI には短い文言だけを出す。

### 3.3 `LogPane` / `GuiLogSink`

`GuiLogSink` は `LogSink` adapter として `UserEvent` を Qt Signal へ変換するだけにする。widget 更新は `LogPane` の slot が担当する。

`LogPane` 要件:

- dispatcher へ sink を登録する。
- close 時に sink を解除し、`GuiLogSink.stop()` を呼ぶ。
- `dispose()` のような冪等 method で sink 解除を明示実行できるようにする。`MainWindow.closeEvent()` は logging close より前にこの method を呼ぶ。
- debug checkbox は `dispatcher.set_level()` だけを呼ぶ。
- close 後の `UserEvent` は widget に反映されない。

## 4. テスト方針

| テスト名 | 検証内容 |
|----------|----------|
| `test_preview_pauses_during_capture_device_switch` | capture device 切り替え中に timer が止まる |
| `test_preview_resumes_after_capture_device_switch_when_visible` | 表示中なら device 差し替え後に再開する |
| `test_preview_resume_does_not_restart_hidden_widget` | 非表示状態では勝手に preview を再開しない |
| `test_preview_keeps_previous_device_when_switch_fails` | device 切り替え失敗時の扱いが明示される |
| `test_gui_log_pane_displays_user_event_from_sink` | `UserEvent` が表示される |
| `test_gui_log_sink_removed_on_close` | close 後の event が反映されない |
| `test_main_window_disposes_log_sink_before_logging_close` | logging close 前に GUI sink が解除される |
| `test_gui_log_debug_checkbox_updates_sink_level` | debug checkbox が sink level を更新する |

## 5. 完了ゲート

| ゲート | 判定 |
|--------|------|
| Capture switch gate | capture device 切り替え中に preview timer が停止する |
| Resume gate | device 切り替え成功、失敗、非表示のいずれでも preview の扱いが一貫する |
| Qt boundary gate | framework 層が `nyxpy.gui` / Qt を import しない |
| Sink lifecycle gate | `LogPane` close 後に sink が解除される |
