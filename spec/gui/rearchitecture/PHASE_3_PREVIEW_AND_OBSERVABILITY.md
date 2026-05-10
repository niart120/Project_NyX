# GUI 再設計 Phase 3: Preview frame source 参照更新と可観測性

> **文書種別**: Phase 仕様。preview 用 `FrameSourcePort` 参照更新と GUI ログ表示を扱う。
> **対象モジュール**: `src\nyxpy\gui\panes\preview_pane.py`, `src\nyxpy\gui\panes\log_pane.py`, `src\nyxpy\gui\log_sink.py`, `src\nyxpy\gui\main_window.py`
> **親仕様**: `IMPLEMENTATION_PLAN.md`
> **先行条件**: Phase 2 完了。GUI 実行状態が `RunHandle` ベースで管理されている。

## 1. 目的

GUI 設定変更で capture device が変わったときに、preview が古い `FrameSourcePort` 参照で更新を続けないようにする。あわせて、GUI ログ表示を `UserEvent` 経由に固定し、core 層へ Qt 依存を持ち込まない状態を維持する。

## 2. Preview frame source 参照更新

Runtime 実行中という理由だけでは `PreviewPane` の timer を停止しない。GUI 設定変更で active capture device が実際に変わる場合だけ、`PreviewPane.pause()` で更新を止め、`set_frame_source()` で GUI lifetime の `FrameSourcePort` 参照を差し替え、`resume()` で通常の preview 更新へ戻す。設定画面を開いただけでは preview 状態を変更しない。

```text
capture device setting changed
  -> if active device differs:
      -> PreviewPane.pause()
      -> GuiAppServices.apply_settings(...)
      -> PreviewPane.set_frame_source(runtime_builder.frame_source_for_preview())
      -> PreviewPane.resume()
  -> else: no preview state change
```

Runtime と preview の同時 capture 利用は `FrameSourcePort` / capture adapter 側の lock 方針で扱う。GUI は「Runtime 実行中だから preview を止める」という暗黙の ownership ルールを持たない。preview tick は `try_latest_frame()` で非ブロッキング取得し、source が busy の場合は描画を skip して直近 pixmap を維持する。

## 3. 実装仕様

### 3.1 `PreviewPane`

追加する API:

```python
def pause(self) -> None: ...
def resume(self) -> None: ...
def set_frame_source(self, frame_source: FrameSourcePort | None) -> None: ...
```

要件:

- `pause()` は preview timer を停止する。
- `resume()` は widget が表示中で、かつ frame source が設定済みの場合だけ `apply_fps()` 相当で timer を再開する。
- `set_frame_source()` は古い `FrameSourcePort` 参照を新しい preview 用 `FrameSourcePort` に置き換える。
- 表示中であれば通常の `update_preview()` 経路で次フレームを反映する。
- `pause()` / `resume()` は汎用の preview timer 制御であり、device 切り替え専用名にはしない。
- Runtime 実行状態と snapshot 可否はこの API の責務に含めない。
- `update_preview()` は UI thread から `FrameSourcePort.latest_frame()` を呼ばない。`FrameSourcePort.try_latest_frame()` が `None` を返した場合はその tick を終了する。

### 3.2 `MainWindow` 連携

`apply_app_settings()` または `GuiAppServices.apply_settings()` は、active capture device が実際に変わる場合だけ `pause()` を呼ぶ。device 反映に成功した場合は Runtime builder から GUI lifetime の preview 用 `FrameSourcePort` を取得し、`set_frame_source()` で参照を更新してから `resume()` を呼ぶ。設定画面を開いただけ、または保存内容が同一 device の場合は pause / resume しない。

device 切り替えに失敗した場合も、preview の停止状態を固定しない。古い `FrameSourcePort` を使い続けるか、frame source なし状態に落とすかを明示し、その状態に応じて `resume()` するか停止を維持する。失敗詳細は `LoggerPort.technical()` へ記録し、UI には短い文言だけを出す。

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
| `test_preview_pauses_only_during_active_device_change` | 設定画面を開いただけでは停止せず、active device 実変更時だけ停止する |
| `test_preview_resumes_after_frame_source_update` | `FrameSourcePort` 参照差し替え後、表示中なら preview を再開する |
| `test_preview_resume_does_not_restart_hidden_widget` | 非表示状態では勝手に preview を再開しない |
| `test_preview_keeps_previous_device_when_switch_fails` | device 切り替え失敗時の扱いが明示される |
| `test_preview_skips_frame_when_source_busy` | `try_latest_frame()` が `None` の tick は直近 pixmap を維持する |
| `test_preview_runtime_frame_source_contention_perf` | Runtime capture と preview tick が同時に走っても preview tick 超過率が 1% 未満 |
| `test_gui_log_pane_displays_user_event_from_sink` | `UserEvent` が表示される |
| `test_gui_log_sink_removed_on_close` | close 後の event が反映されない |
| `test_main_window_disposes_log_sink_before_logging_close` | logging close 前に GUI sink が解除される |
| `test_gui_log_debug_checkbox_updates_sink_level` | debug checkbox が sink level を更新する |

## 5. 完了ゲート

| ゲート | 判定 |
|--------|------|
| Capture switch gate | active device 実変更時だけ preview timer を停止し、参照差し替え後に再開する |
| No dialog pause gate | 設定画面を開いただけ、または同一 device 保存では preview を停止しない |
| Nonblocking preview gate | preview は `try_latest_frame()` を使い、UI thread で frame lock の blocking wait をしない |
| Qt boundary gate | framework 層が `nyxpy.gui` / Qt を import しない |
| Sink lifecycle gate | `LogPane` close 後に sink が解除される |
