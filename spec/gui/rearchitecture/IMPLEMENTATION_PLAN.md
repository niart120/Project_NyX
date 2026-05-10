# GUI 再設計追従 実装修正仕様書

> **文書種別**: 実装修正仕様。フレームワーク再設計後に GUI adapter が満たすべき責務、残修正、検証ゲートを定義する。
> **対象モジュール**: `src\nyxpy\gui\`, `tests\gui\`
> **目的**: GUI の実行制御を `RunHandle` / `RunResult` / `UserEvent` ベースへ固定し、旧 `Command.stop()`、`MacroExecutor`、GUI スレッドからの Runtime 詳細操作、capture 所有権競合を排除する。
> **関連ドキュメント**: `spec\framework\rearchitecture\IMPLEMENTATION_PLAN.md`, `spec\framework\rearchitecture\RUNTIME_AND_IO_PORTS.md`, `spec\framework\rearchitecture\LOGGING_FRAMEWORK.md`, `spec\framework\rearchitecture\OBSERVABILITY_AND_GUI_CLI.md`, `spec\framework\rearchitecture\DEPRECATION_AND_MIGRATION.md`, `PHASE_1_APP_SERVICES_AND_CATALOG.md`, `PHASE_2_RUNTIME_CONTROL.md`, `PHASE_3_PREVIEW_AND_OBSERVABILITY.md`, `PHASE_4_CLEANUP_AND_REGRESSION.md`
> **破壊的変更**: マクロ実行、停止、設定、ログ表示の GUI 操作は維持する。マクロ一覧の内部識別子は class name から stable `macro_id` へ移行するが、表示名は維持する。

## 1. 概要

### 1.1 目的

GUI は Runtime の上位 adapter であり、Qt イベント、画面状態、ユーザー操作、`UserEvent` 表示、application lifetime の resource 管理を担当する。マクロ lifecycle、settings 解決、Resource I/O、device port、通知、構造化ログ生成は Runtime / Builder / Ports へ委譲する。

### 1.2 現状確認

現行 `src\nyxpy\gui\main_window.py` は `RuntimeBuildRequest`、`RunHandle`、`RunResult`、`QTimer` polling に移行済みである。`LogPane` は `LogSinkDispatcher` と `GuiLogSink` で `UserEvent` を表示している。

残修正は次の通り。

| 項目 | 現状 | 修正方針 |
|------|------|----------|
| Builder 生成 | 実行ごとに `create_legacy_runtime_builder()` を呼ぶ | GUI application lifetime の service に集約し、設定変更時だけ再構成する |
| Macro identity | `MacroCatalog.macros` が `definition.class_name` を key にしている | stable `definition.id` を実行 ID にし、表示名と分離する |
| capture 所有権 | PreviewPane と Runtime が同じ active capture device を参照し得る | 実行中の preview pause または thread-safe shared frame source を明示する |
| cancel UI | cancel 直後に `control_pane.set_running(False)` する | `CANCELLING` 状態を持ち、`RunResult` 確定まで再実行を許可しない |
| poll 例外 | `run_handle.result()` 例外を status 文字列にする | `LoggerPort.technical()` に記録し、UI には短い表示だけを出す |
| close timeout | `wait(5)` が固定値 | `runtime.release_timeout_sec` または GUI 設定値へ寄せる |
| singleton 直接操作 | `MainWindow` が manager 設定、release、settings 差分を直接扱う | `GuiAppServices` 相当の composition object へ寄せ、MainWindow は UI orchestration に絞る |

### 1.3 完了状態

GUI の最終状態は次の呼び出し列で表せる。

```text
MainWindow
  -> GuiAppServices(runtime_builder, registry, logging, device services)
  -> MacroCatalog uses MacroDefinition.id
  -> Run button creates RuntimeBuildRequest(entrypoint="gui")
  -> MacroRuntimeBuilder.start(request)
  -> RunHandle stored in MainWindow
  -> QTimer polls RunHandle.done()
  -> RunResult updates status, controls, log, retry affordance
  -> Cancel button calls RunHandle.cancel()
```

`nyxpy.framework.*` は `nyxpy.gui.*` を import しない。GUI 層だけが Qt に依存する。

### 1.4 分割方針

GUI は変更範囲が広く、composition root、macro identity、実行状態、preview 所有権、log sink、close cleanup が互いに絡む。本書は全体計画と完了ゲートの正本にし、実装詳細は次の phase 仕様へ分ける。

| フェーズ | 仕様書 | 実装の狙い | 先行条件 |
|----------|--------|------------|----------|
| Phase 1 | `PHASE_1_APP_SERVICES_AND_CATALOG.md` | `GuiAppServices` と stable macro ID を導入する | Runtime / Registry API が利用可能 |
| Phase 2 | `PHASE_2_RUNTIME_CONTROL.md` | `RunHandle` と GUI 状態遷移を整理する | Phase 1 |
| Phase 3 | `PHASE_3_PREVIEW_AND_OBSERVABILITY.md` | preview 所有権と `UserEvent` 表示を整理する | Phase 2 |
| Phase 4 | `PHASE_4_CLEANUP_AND_REGRESSION.md` | close cleanup、削除対象 API の回帰防止、最終テストを固定する | Phase 1-3 |

各 phase 仕様は、その phase で変更するファイル、テスト、完了ゲートを持つ。実装時は phase ごとにテストを追加し、次 phase に進む前に対象 GUI テストを通す。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `spec\gui\rearchitecture\IMPLEMENTATION_PLAN.md` | 新規 | 本仕様書 |
| `spec\gui\rearchitecture\PHASE_1_APP_SERVICES_AND_CATALOG.md` | 新規 | GUI composition root と macro identity の詳細 |
| `spec\gui\rearchitecture\PHASE_2_RUNTIME_CONTROL.md` | 新規 | 実行開始、cancel、polling、UI 状態の詳細 |
| `spec\gui\rearchitecture\PHASE_3_PREVIEW_AND_OBSERVABILITY.md` | 新規 | preview 所有権、`GuiLogSink`、`LogPane` の詳細 |
| `spec\gui\rearchitecture\PHASE_4_CLEANUP_AND_REGRESSION.md` | 新規 | close cleanup、削除対象 API、最終回帰テストの詳細 |
| `src\nyxpy\gui\main_window.py` | 変更 | 実行状態、builder lifetime、cleanup、error logging、preview pause を整理 |
| `src\nyxpy\gui\app_services.py` | 新規 | GUI composition root。logging、registry、builder、device service を保持 |
| `src\nyxpy\gui\macro_catalog.py` | 変更 | `MacroDefinition.id` と display name を分離して扱う |
| `src\nyxpy\gui\panes\macro_browser.py` | 変更 | stable macro ID を選択値として保持する |
| `src\nyxpy\gui\panes\control_pane.py` | 変更 | `IDLE` / `RUNNING` / `CANCELLING` に応じたボタン状態を表示 |
| `src\nyxpy\gui\panes\preview_pane.py` | 変更 | Runtime 実行中の capture 所有権方針を実装 |
| `src\nyxpy\gui\panes\log_pane.py` | 変更 | sink 登録解除、debug level 変更、close 後配信を検証済みにする |
| `src\nyxpy\gui\log_sink.py` | 変更 | Qt Signal adapter として core 依存を持たない状態を維持 |
| `tests\gui\test_main_window.py` | 変更 | `RunHandle`、状態遷移、error logging、close timeout を検証 |
| `tests\gui\test_macro_catalog.py` | 新規 | stable macro ID と表示名の分離を検証 |
| `tests\gui\test_preview_runtime_ownership.py` | 新規 | 実行中 preview pause または shared frame source 方針を検証 |

## 3. 設計方針

### 3.1 GUI adapter の責務

| 責務 | GUI が行うこと | GUI が行わないこと |
|------|---------------|-------------------|
| 操作受付 | 実行、パラメータ入力、中断、設定変更を受け取る | マクロ lifecycle を直接呼ぶ |
| 実行制御 | `RunHandle` を保持し、polling で状態反映する | `Command.stop()` や thread 例外注入で止める |
| 表示 | `RunResult` と `UserEvent` を Qt widget へ変換する | traceback、secret、内部 path を status や dialog に出す |
| 設定反映 | GUI 設定変更を service へ通知する | Runtime context を手作業で組み立てる |
| cleanup | close 時に cancel、wait、sink 解除、preview 停止、logging close を順序立てる | cleanup 失敗を沈黙させる |

### 3.2 Composition root

`MainWindow` の肥大化を避けるため、GUI 起動時の依存生成は `GuiAppServices` に集約する。

```python
class GuiAppServices:
    logging: LoggingComponents
    registry: MacroRegistry
    macro_catalog: MacroCatalog

    def create_runtime_builder(self) -> MacroRuntimeBuilder: ...
    def apply_settings(self, global_settings, secrets_settings) -> None: ...
    def close(self) -> None: ...
```

`GuiAppServices` は singleton ではない。`MainWindow` の lifetime に 1 個作成され、テストでは fake service に差し替えられる。実装初期段階でファイルを分けない場合も、同等の責務境界を private method ではなく小さな collaborator として抽出する。

### 3.3 Macro identity

マクロ実行に使う ID は `MacroDefinition.id` を正とする。class name は表示名または旧表示互換として扱う。

| 値 | 用途 |
|----|------|
| `definition.id` | `RuntimeBuildRequest.macro_id`、ログ相関、Resource scope |
| `definition.display_name` | GUI 表示、dialog title |
| `definition.class_name` | 旧表示互換、診断情報 |

`MacroBrowserPane` は選択行に stable macro ID を保持する。`MainWindow` は table の 0 列 text から実行 ID を復元しない。

### 3.4 実行状態

GUI は次の状態を持つ。

| 状態 | Run button | Cancel button | Snapshot | Status |
|------|------------|---------------|----------|--------|
| `IDLE` | 選択ありで有効 | 無効 | 有効 | `準備完了` |
| `RUNNING` | 無効 | 有効 | 方針により無効または last frame 保存 | `実行中` |
| `CANCELLING` | 無効 | 無効 | 無効 | `中断要求中` |
| `FINISHED` | 選択ありで有効 | 無効 | 有効 | `完了` / `中断` / `エラー: ...` |

Cancel button は `RunHandle.cancel()` だけを呼ぶ。`RunResult` が確定するまで `RUNNING` 相当の排他を維持し、二重実行を防ぐ。

### 3.5 Preview と Runtime の capture 所有権

最初の実装では、マクロ実行中に `PreviewPane` の timer を停止する。Runtime が capture frame source を使い終わった後、`RunResult` 反映と同じタイミングで preview を再開する。

この方針は capture device の thread safety を仮定しないための安全側の既定である。将来 `FrameSourcePort` が read-only shared access と lock 方針を提供し、テストで競合がないことを検証できた場合だけ、実行中 preview 継続へ変更してよい。

### 3.6 ロギングと GUI 表示

GUI は `LogSinkDispatcher` に `GuiLogSink` を登録し、`UserEvent` を Qt Signal で `LogPane` へ渡す。core 層は Qt を import しない。

`RunHandle.result()` や close cleanup で例外が起きた場合、GUI は `LoggerPort.technical()` に詳細を記録し、status / dialog には短い文言だけを出す。`QMessageBox` へ traceback、絶対 path、secret 値を表示してはならない。

## 4. 実装仕様

### 4.1 `MainWindow`

`MainWindow` は UI orchestration に集中する。

必須要件:

- 実行開始時に選択中の stable macro ID を取得する。
- `RuntimeBuildRequest(macro_id=..., entrypoint="gui", exec_args=...)` を作成する。
- `MacroRuntimeBuilder.start()` の戻り値を `self.run_handle` に保持する。
- 実行中は preview timer を停止する。
- `QTimer` で `RunHandle.done()` を監視する。
- 完了時に `RunHandle.result()` から `RunResult` を取得し、status と button state を更新する。
- 中断要求時は `RunHandle.cancel()` を呼び、状態を `CANCELLING` にする。
- close 時は実行中 handle に cancel を要求し、設定値 timeout で wait する。

`MainWindow` は `DefaultCommand`、`MacroExecutor`、`LogManager` を import しない。

### 4.2 `GuiAppServices`

`GuiAppServices` は次を担当する。

- `create_default_logging(..., console_enabled=False)` の生成と close。
- `MacroRegistry(project_root)` の生成と reload。
- `MacroCatalog` の生成。
- global settings / secrets settings から runtime builder を構成する。
- serial / capture / protocol / notification の変更反映。
- application close 時の manager release と logging close。

release 例外は `LoggerPort.technical("WARNING", ..., event="resource.cleanup_failed")` へ記録する。`pass` で握りつぶさない。

### 4.3 `MacroCatalog` / `MacroBrowserPane`

`MacroCatalog` は `MacroDefinition` を stable ID で保持する。

```python
class MacroCatalog:
    definitions_by_id: dict[str, MacroDefinition]

    def reload_macros(self) -> None: ...
    def get(self, macro_id: str) -> MacroDefinition: ...
```

`MacroBrowserPane` は表示列に `display_name` または class name を出してよいが、選択値として `macro_id` を保持する。`MainWindow` は table cell text ではなく `MacroBrowserPane.selected_macro_id()` から実行対象を取得する。

### 4.4 `ControlPane`

`ControlPane.set_running(bool)` だけでは `CANCELLING` を表現できないため、状態 enum または専用 method を追加する。

```python
class RunUiState(Enum):
    IDLE = "idle"
    RUNNING = "running"
    CANCELLING = "cancelling"
    FINISHED = "finished"
```

最小実装では `set_run_state(state: RunUiState)` を追加し、既存 `set_running(bool)` は内部互換 wrapper としてだけ残す。

### 4.5 `PreviewPane`

`PreviewPane` は次の API を提供する。

```python
def pause_for_runtime(self) -> None: ...
def resume_after_runtime(self) -> None: ...
```

`pause_for_runtime()` は timer を停止し、実行中 snapshot を無効化するか last frame 保存に限定する。`resume_after_runtime()` は現在の `preview_fps` で timer を再開する。

### 4.6 `LogPane` / `GuiLogSink`

`LogPane` は close 時に dispatcher から sink を解除する。debug checkbox の level 変更は `LogSinkDispatcher.set_level()` 経由に限定する。

`GuiLogSink` は widget を直接更新しない。Qt Signal emit だけを行い、`LogSink` 例外隔離は dispatcher 側に委譲する。

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| GUI | `test_main_window_uses_run_handle` | 実行開始で `MacroRuntimeBuilder.start()` と `RuntimeBuildRequest(entrypoint="gui")` を使う |
| GUI | `test_main_window_uses_selected_macro_id` | table 表示名ではなく stable macro ID を request に渡す |
| GUI | `test_main_window_cancel_enters_cancelling_state` | cancel 後、`RunResult` 確定まで再実行できない |
| GUI | `test_main_window_poll_updates_status_from_run_result` | `RunResult` から status、button state、`last_run_result` を更新する |
| GUI | `test_main_window_poll_logs_result_exception` | `RunHandle.result()` 例外を技術ログへ記録する |
| GUI | `test_main_window_close_cancels_and_waits_with_configured_timeout` | close 時に cancel と wait を行う |
| GUI | `test_main_window_close_logs_cleanup_failures` | manager release 失敗を沈黙させない |
| GUI | `test_preview_pauses_during_runtime_and_resumes_after_result` | 実行中 preview timer を停止し、完了後に再開する |
| GUI | `test_macro_catalog_keys_by_definition_id` | `MacroCatalog` が `definition.id` で定義を保持する |
| GUI | `test_gui_log_pane_displays_user_event_from_sink` | `UserEvent` がログペインに表示される |
| GUI | `test_gui_log_sink_removed_on_close` | close 後の event が widget に届かない |
| 静的 | `test_gui_does_not_import_removed_runtime_apis` | `MacroExecutor`、`DefaultCommand`、`LogManager` を import しない |

## 6. 実装チェックリスト

- [ ] `GuiAppServices` 相当の composition root を導入する。
- [ ] `MacroCatalog` を stable `MacroDefinition.id` key に変更する。
- [ ] `MacroBrowserPane` に `selected_macro_id()` を追加する。
- [ ] `MainWindow._start_macro()` が table text ではなく stable macro ID を使う。
- [ ] 実行中 preview pause / 完了後 resume を入れる。
- [ ] cancel 後に `CANCELLING` 状態を維持し、`RunResult` 確定まで再実行を禁止する。
- [ ] `RunHandle.result()` 例外と close cleanup 例外を `LoggerPort.technical()` へ記録する。
- [ ] close wait timeout を設定値から読む。
- [ ] `ControlPane` の状態 API を `IDLE` / `RUNNING` / `CANCELLING` 対応に拡張する。
- [ ] `src\nyxpy\gui\` から削除対象 API の import がないことをテストで固定する。
- [ ] `uv run pytest tests\gui\test_main_window.py tests\gui\test_log_pane_user_event.py` を通す。

## 7. 完了ゲート

GUI 移行は次をすべて満たした時点で完了とする。

| ゲート | 判定 |
|--------|------|
| Runtime entry gate | GUI 実行は `RuntimeBuildRequest(entrypoint="gui")` と `MacroRuntimeBuilder.start()` を使う |
| Stable identity gate | 実行 ID、ログ相関、Resource scope に `MacroDefinition.id` を使う |
| Cancellation gate | GUI cancel は `RunHandle.cancel()` だけを呼び、`Command.stop()` を直接呼ばない |
| UI state gate | `RUNNING` と `CANCELLING` を区別し、二重実行を防ぐ |
| Capture ownership gate | Runtime 実行中の preview / capture 競合をテストで防ぐ |
| Log sink gate | `GuiLogSink` は Qt adapter に留まり、close 時に dispatcher から解除される |
| Cleanup visibility gate | close / release / wait 失敗を沈黙させない |
| Removal gate | `MacroExecutor`、`DefaultCommand`、`LogManager` 参照が GUI にない |
