# 可観測性と GUI/CLI 入口再設計 仕様書

> **対象モジュール**: `src\nyxpy\framework\core\runtime\`, `src\nyxpy\framework\core\logger\`, `src\nyxpy\framework\core\settings\`, `src\nyxpy\cli\`, `src\nyxpy\gui\`
> **目的**: GUI/CLI の実行入口を `MacroRuntime` へ寄せ、構造化ログ、GUI 表示イベント、ユーザー表示、技術ログ、通知設定ソースを一貫させる。
> **関連ドキュメント**: `spec\framework\rearchitecture\RUNTIME_AND_IO_PORTS.md`, `spec\framework\rearchitecture\ERROR_CANCELLATION_LOGGING.md`, `spec\framework\rearchitecture\CONFIGURATION_AND_RESOURCES.md`
> **破壊的変更**: なし。既存 GUI/CLI の操作概念と既存マクロの `Command.log()` 呼び出しを維持する。

## 1. 概要

### 1.1 目的

GUI と CLI が個別に `DefaultCommand`、通知、ログ、中断を組み立てる状態を解消し、`MacroRuntime` を実行入口として統一する。保存用の構造化ログと GUI 表示イベントを分離し、`run_id` / `macro_id` による追跡、秘密値保護、handler 例外隔離をフレームワーク側で保証する。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| MacroRuntime | GUI/CLI/Legacy 入口から呼ばれるマクロ実行中核。同期実行、非同期実行、キャンセル、結果取得を提供する |
| MacroRuntimeBuilder | `GlobalSettings`、`SecretsSettings`、デバイス検出結果から `MacroRuntime` と `ExecutionContext` を組み立てる adapter |
| RunHandle | GUI から非同期実行を監視し、中断要求、完了待ち、結果取得を行うハンドル |
| RunResult | CLI の終了コード、GUI の実行完了表示、構造化ログに使う実行結果 |
| run_id | 1 回の実行を識別する UUID 文字列。ログ、GUI 表示イベント、`RunResult` を関連付ける |
| macro_id | 実行対象マクロを識別する安定 ID。構造化ログと GUI/CLI 表示の軸になる |
| 構造化ログ | `run_id`, `macro_id`, `component`, `level`, `event`, `message`, `extra` を持つ保存・解析用ログ |
| GUI 表示イベント | GUI のログペイン、ステータスバー、通知バナーへ渡す短い表示用イベント |
| ユーザー表示 | GUI/CLI に出す短い文言。secret 値、traceback、内部 path の詳細を含めない |
| 技術ログ | 開発者が調査に使う保存ログ。traceback、例外型、component、詳細辞書を含められるが secret 値は含めない |
| LogManager | loguru ベースの統合ログ管理。構造化ログと GUI 表示イベント配信を担当する |
| SecretsSettings | 通知 secret の唯一の設定ソース。CLI 独自構造や `GlobalSettings` へ secret 値を複製しない |

### 1.3 背景・問題

既存仕様では Runtime と I/O Ports の分離、異常系、構造化ログの方向性が定義されている。ただし、GUI/CLI をどの段階で `MacroRuntime` 入口へ寄せるか、CLI 通知設定ソースを `SecretsSettings` に統一する問題、ユーザー表示と技術ログの境界、GUI log handler の例外・ロック方針は独立した観点として明文化が不足していた。

現行 GUI/CLI がそれぞれ `DefaultCommand` を組み立てると、通知設定、キャンセル、ログ handler、デバイス検出完了待ちが入口ごとにずれる。再設計では既存マクロを変更せず、入口側の組み立てを `MacroRuntimeBuilder` へ集約する。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| GUI/CLI の実行組み立て | 入口ごとに `DefaultCommand` を構築 | `MacroRuntimeBuilder` 経由の 1 系統 |
| 通知 secret の参照元 | CLI/GUI で分岐し得る | `SecretsSettings` のみ |
| ログ相関 | 文字列ログ中心 | 全実行ログに `run_id` / `macro_id` を付与 |
| GUI 表示と保存ログ | 同一 handler に依存しやすい | `GuiLogEvent` と構造化ログを別経路にする |
| handler 例外 | 方針未定義 | handler 例外は記録して握り、他 handler とマクロ実行を継続 |
| ユーザー表示 | traceback や内部詳細が混入し得る | 短い表示文言と技術ログを分離 |
| 既存マクロ変更数 | 変更不可 | 0 件 |

### 1.5 着手条件

- `MacroRuntime.run()` / `MacroRuntime.start()` / `RunHandle` / `RunResult` の基本仕様が確定している。
- `GlobalSettings` と `SecretsSettings` の schema 化方針が確定している。
- GUI 層は Qt 依存を保持してよいが、Runtime 本体へ Qt 依存を入れない。
- CLI は `RunResult.status` に基づく終了コードを返す。
- 既存マクロの `Command.log()` 呼び出しと `notify()` 呼び出しを変更不要にする。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `spec\framework\rearchitecture\OBSERVABILITY_AND_GUI_CLI.md` | 新規 | 本仕様書 |
| `src\nyxpy\framework\core\runtime\builder.py` | 新規 | GUI/CLI/Legacy 入口から Runtime と Ports を組み立てる |
| `src\nyxpy\framework\core\runtime\result.py` | 新規 | `RunResult`, `RunStatus`, `ErrorInfo` を GUI/CLI 表示へ利用可能にする |
| `src\nyxpy\framework\core\logger\log_manager.py` | 変更 | 構造化ログ、`GuiLogEvent`、handler 登録、handler 例外隔離を実装 |
| `src\nyxpy\framework\core\logger\events.py` | 新規 | `GuiLogEvent`, `UserMessage`, event 名定数を定義 |
| `src\nyxpy\framework\core\settings\secrets_settings.py` | 変更 | CLI/GUI 共通の通知設定ソースとして schema を提供 |
| `src\nyxpy\cli\run_cli.py` | 変更 | `MacroRuntimeBuilder.from_cli_args()` を使い、終了コードを `RunResult` から決定 |
| `src\nyxpy\gui\main_window.py` | 変更 | `MacroRuntime.start()` と `RunHandle` を使う実行制御へ移行 |
| `src\nyxpy\gui\log_pane.py` | 変更 | `GuiLogEvent` を表示し、保存ログ handler へ直接依存しない |
| `tests\unit\logger\test_log_manager_events.py` | 新規 | 構造化ログ、GUI handler、例外隔離、ロック方針を検証 |
| `tests\integration\test_cli_runtime_entry.py` | 新規 | CLI が Runtime 入口と `SecretsSettings` を使うことを検証 |
| `tests\gui\test_runtime_entry.py` | 新規 | GUI が `RunHandle` と GUI 表示イベントで実行状態を反映することを検証 |

## 3. 設計方針

### アーキテクチャ上の位置づけ

GUI/CLI はフレームワークの上位 adapter であり、マクロ実行中核ではない。実行要求、デバイス検出、通知設定、ログ相関、キャンセル、結果取得は `MacroRuntimeBuilder` と `MacroRuntime` に寄せる。

```text
nyxpy.cli.run_cli
  -> MacroRuntimeBuilder.from_cli_args()
  -> MacroRuntime.run()
  -> RunResult

nyxpy.gui.main_window
  -> MacroRuntimeBuilder.from_settings()
  -> MacroRuntime.start()
  -> RunHandle
  -> GuiLogEvent
```

Runtime 本体は Qt、argparse、標準出力表示へ依存しない。GUI/CLI は `RunResult` と表示イベントを、自身の UI または標準出力へ変換する。

### 公開 API 方針

`LogManager.log()` は既存の文字列ログ呼び出しを維持しつつ、キーワード専用引数で `run_id`、`macro_id`、`event`、`extra` を受け取る。`Command.log(*values, sep, end, level)` は既存シグネチャを維持し、内部で `event="macro.message"` の構造化ログと GUI 表示イベントへ変換する。

GUI handler は `add_gui_handler()` / `remove_gui_handler()` で登録する。handler は `GuiLogEvent` を受け取り、戻り値を持たない。handler 例外は `LogManager` が捕捉し、他 handler へ配信を継続する。

### 後方互換性

既存 CLI オプションと GUI 操作は段階移行で維持する。CLI の出力文言は短いユーザー表示へ変更してよいが、成功時 0、失敗時 非 0、中断時 130 の終了コードを明示する。GUI の `WorkerThread` は Runtime adapter へ縮小または置換してよいが、マクロ本体のスレッド実行と GUI スレッド更新の分離は維持する。

`Command.notify()` は既存呼び出しを維持する。通知先の有効化、webhook URL、Bluesky credentials は `SecretsSettings` からのみ読み、CLI 引数や `GlobalSettings` に secret 値を複製しない。

### レイヤー構成

| レイヤー | 責務 | 禁止事項 |
|----------|------|----------|
| Runtime | 実行、結果、キャンセル、構造化ログ context 付与 | Qt、argparse、標準出力への直接依存 |
| Logger | 保存ログ、GUI 表示イベント配信、handler 隔離 | secret 平文出力、handler 例外の再送出 |
| CLI adapter | 引数解析、Runtime 呼び出し、終了コード、ユーザー表示 | secret 値の独自保存、`DefaultCommand` 直接構築 |
| GUI adapter | 操作イベント、`RunHandle` 監視、画面表示、Qt signal 変換 | Runtime 本体への Qt 依存混入 |
| Notification adapter | `SecretsSettings` から通知先を構築 | `GlobalSettings` から secret 値を読む |

### 性能要件

| 指標 | 目標値 |
|------|--------|
| `LogManager.log()` の handler なし通常呼び出し | 1 件 2 ms 未満 |
| GUI handler 10 件への配信 | 1 件 10 ms 未満 |
| handler 例外発生時の他 handler 継続 | 100% |
| CLI 起動時の Runtime builder 追加コスト | デバイス検出を除き 100 ms 未満 |
| GUI cancel ボタンから中断要求発火 | 100 ms 未満 |

### 並行性・スレッド安全性

GUI handler の登録、削除、配信対象 snapshot 作成は `RLock` で保護する。handler 呼び出しは lock 外で行い、handler 内から `remove_gui_handler()` や GUI signal emit が呼ばれても deadlock しないようにする。

`run_id` と `macro_id` は `ExecutionContext` 作成時に確定し、実行中は immutable とする。`RunHandle.cancel()` は GUI スレッドから呼べる中断要求 API であり、例外を送出しない。

## 4. 実装仕様

### 公開インターフェース

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Mapping


@dataclass(frozen=True)
class GuiLogEvent:
    run_id: str | None
    macro_id: str | None
    level: str
    component: str
    event: str
    message: str
    timestamp: datetime
    user_visible: bool = True
    extra: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class UserMessage:
    level: str
    text: str
    code: str | None = None


class LogManager:
    def log(
        self,
        level: str,
        message: str,
        component: str = "",
        *,
        run_id: str | None = None,
        macro_id: str | None = None,
        event: str = "log.message",
        extra: Mapping[str, Any] | None = None,
        user_message: str | None = None,
    ) -> None: ...

    def add_gui_handler(
        self,
        handler: Callable[[GuiLogEvent], None],
        *,
        level: str = "INFO",
    ) -> None: ...

    def remove_gui_handler(self, handler: Callable[[GuiLogEvent], None]) -> None: ...
    def emit_gui_event(self, event: GuiLogEvent) -> None: ...


class MacroRuntimeBuilder:
    @classmethod
    def from_cli_args(cls, args: object) -> "MacroRuntimeBuilder": ...

    @classmethod
    def from_settings(
        cls,
        global_settings: GlobalSettings,
        secrets_settings: SecretsSettings,
    ) -> "MacroRuntimeBuilder": ...

    def create_context(
        self,
        *,
        macro_id: str,
        exec_args: Mapping[str, Any] | None = None,
    ) -> ExecutionContext: ...

    def create_notification_port(self) -> NotificationPort: ...


class CliPresenter:
    def render_result(self, result: RunResult) -> UserMessage: ...
    def exit_code(self, result: RunResult) -> int: ...
```

### 設定パラメータ

| パラメータ | 型 | デフォルト | 説明 |
|------------|-----|-----------|------|
| `logging.file_level` | `str` | `"DEBUG"` | 技術ログの最低レベル |
| `logging.console_level` | `str` | `"INFO"` | CLI 標準出力へ出す最低レベル |
| `logging.gui_level` | `str` | `"INFO"` | GUI 表示イベントの最低レベル |
| `logging.include_traceback` | `bool` | `True` | 技術ログへ traceback を保存するか |
| `notification.discord.enabled` | `bool` | `False` | `SecretsSettings` 内の通知有効化 |
| `notification.discord.webhook_url` | `str` | `""` | `SecretsSettings` 内の secret。表示時はマスク |
| `notification.bluesky.enabled` | `bool` | `False` | `SecretsSettings` 内の通知有効化 |
| `notification.bluesky.identifier` | `str` | `""` | `SecretsSettings` 内の secret 扱い値 |
| `notification.bluesky.password` | `str` | `""` | `SecretsSettings` 内の secret |
| `runtime.gui_poll_interval_ms` | `int` | `100` | GUI が `RunHandle.done()` を監視する周期 |

### 内部設計

#### GUI/CLI を MacroRuntime 入口へ寄せる

CLI は `MacroRuntimeBuilder.from_cli_args()` で設定 snapshot、`SecretsSettings`、デバイス検出、通知 Port、LoggerPort を組み立てる。CLI は `DefaultCommand` を直接生成しない。

```text
run_cli.main()
  -> args parse
  -> builder = MacroRuntimeBuilder.from_cli_args(args)
  -> context = builder.create_context(macro_id=args.macro, exec_args=args.define)
  -> result = builder.runtime.run(context)
  -> CliPresenter.exit_code(result)
```

GUI は `MacroRuntimeBuilder.from_settings(global_settings, secrets_settings)` を作成し、実行ボタンで `runtime.start(context)` を呼ぶ。GUI cancel は `RunHandle.cancel()` のみを呼び、`Command.stop()` を GUI スレッドから直接呼ばない。

#### CLI 通知設定ソース

通知 secret は `SecretsSettings` が唯一の入力元である。CLI 引数で通知先を直接受け取る場合でも、その値を一時的な `SecretsSettings` snapshot として扱い、`GlobalSettings` やログ context へ平文を渡さない。Runtime builder が `SecretsSettings` 以外から secret 値を受け取った場合は `ConfigurationError` とする。

#### 構造化ログと GUI 表示イベント

`LogManager.log()` は保存ログを先に出し、`user_message` が指定された場合、または `event` が GUI 表示対象の場合に `GuiLogEvent` を生成する。保存ログの `extra` には `run_id`, `macro_id`, `component`, `event`, `error_code` を含める。GUI 表示イベントには短い `message` と表示に必要な最小限の `extra` だけを含める。

| event | 技術ログ | ユーザー表示 |
|-------|----------|--------------|
| `macro.started` | `run_id`, `macro_id`, `args_keys` | `マクロを開始しました` |
| `macro.message` | `Command.log()` の値、component | マクロ作者が出した文言 |
| `macro.cancel_requested` | `source`, `reason` | `中断を要求しました` |
| `macro.cancelled` | `RunResult`, `cancelled_reason` | `マクロを中断しました` |
| `macro.failed` | `ErrorInfo`, traceback | `マクロ実行中にエラーが発生しました` |
| `notification.failed` | 通知種別、マスク済み詳細 | 必要時だけ警告表示 |
| `log.gui_handler_failed` | handler 名、例外型、traceback | 表示しない |

#### Log handler 例外・ロック方針

```text
emit_gui_event(event)
  -> RLock を取得
  -> 現在の handler と level filter の snapshot を作成
  -> RLock を解放
  -> handler を順番に呼ぶ
  -> handler 例外は捕捉し、技術ログへ `log.gui_handler_failed` を出す
  -> 他 handler と呼び出し元の `LogManager.log()` は継続
```

handler 例外の記録では再帰を防ぐため、GUI event を再発行しない内部ログ経路を使う。

#### ユーザー表示と技術ログの分離

`ErrorInfo.message` はユーザー表示可能な短文に限定する。traceback、内部絶対パス、secret 値、通知 payload は技術ログの DEBUG 詳細へ分離する。CLI は `CliPresenter.render_result()` で `RunResult` を `UserMessage` に変換し、GUI は同じ `UserMessage` 相当を status 表示へ渡す。

### エラーハンドリング

| 例外クラス | 発生条件 |
|------------|----------|
| `ConfigurationError` | 通知 secret を `SecretsSettings` 以外から受け取った、ログレベル不正、CLI 引数不正 |
| `GuiHandlerError` | handler 例外の内部表現。外部へ再送出せず `log.gui_handler_failed` に変換 |
| `LoggingConfigurationError` | loguru sink 作成失敗、ログファイル path 不正 |
| `MacroRuntimeError` | マクロ実行中の未分類例外。`RunResult.error` と技術ログへ記録 |

ユーザー表示では例外クラス名を必要以上に出さない。技術ログでは `exception_type` と traceback を保存するが、secret 値は mask 済み辞書だけを記録する。

### シングルトン管理

既存 `log_manager` シングルトンは維持する。GUI handler は GUI の lifetime に合わせて登録・解除し、`reset_for_testing()` で handler 配列、level filter、内部 lock 状態を初期化する。`MacroRuntimeBuilder`、`RunHandle`、`RunResult` は実行単位のオブジェクトであり、シングルトンにしない。

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| ユニット | `test_log_manager_adds_run_and_macro_id` | 構造化ログに `run_id` と `macro_id` が入る |
| ユニット | `test_command_log_emits_macro_message_event` | 既存 `Command.log()` が `macro.message` として記録される |
| ユニット | `test_gui_event_is_separate_from_file_log` | GUI 表示イベントと保存ログが別 handler で受け取れる |
| ユニット | `test_gui_handler_exception_is_logged_and_ignored` | handler 例外が他 handler と `LogManager.log()` を失敗させない |
| ユニット | `test_gui_handler_snapshot_avoids_deadlock` | handler 呼び出し中の登録解除で deadlock しない |
| ユニット | `test_user_message_excludes_traceback` | ユーザー表示に traceback が含まれない |
| ユニット | `test_technical_log_masks_secrets` | 技術ログでも secret 値が平文で出ない |
| ユニット | `test_cli_presenter_exit_codes` | 成功 0、失敗 2、中断 130 の終了コードを返す |
| ユニット | `test_runtime_builder_rejects_cli_secret_outside_secrets_settings` | CLI 通知 secret の入力元違反を `ConfigurationError` にする |
| 結合 | `test_cli_uses_macro_runtime_entry` | CLI が `DefaultCommand` 直接構築ではなく Runtime builder を使う |
| 結合 | `test_cli_notification_settings_source_is_secrets_settings` | CLI 通知設定が `SecretsSettings` に統一される |
| GUI | `test_main_window_uses_run_handle` | GUI 実行開始で `MacroRuntime.start()` の `RunHandle` を保持する |
| GUI | `test_main_window_cancel_calls_handle_cancel` | GUI cancel が `Command.stop()` ではなく `RunHandle.cancel()` を呼ぶ |
| GUI | `test_log_pane_receives_gui_log_event` | `LogPane` が `GuiLogEvent` を表示する |
| ハードウェア | `test_realdevice_cli_runtime_logging` | `@pytest.mark.realdevice`。実機 CLI 実行で run_id 付きログが残る |
| パフォーマンス | `test_gui_log_event_dispatch_perf` | handler 10 件で 1 event 10 ms 未満 |
| パフォーマンス | `test_cancel_button_to_token_latency_perf` | GUI cancel から token 発火まで 100 ms 未満 |

## 6. 実装チェックリスト

- [ ] GUI/CLI の `DefaultCommand` 直接構築箇所を Runtime builder へ寄せる
- [ ] CLI 通知設定ソースを `SecretsSettings` に統一
- [ ] 構造化ログに `run_id` / `macro_id` / `component` / `event` を付与
- [ ] GUI 表示イベントを保存ログから分離
- [ ] Log handler の `RLock` と snapshot 配信を実装
- [ ] handler 例外を技術ログへ記録し、他 handler とマクロ実行を継続
- [ ] ユーザー表示から traceback、secret、内部詳細を除外
- [ ] CLI 終了コードを `RunResult` から決定
- [ ] GUI cancel を `RunHandle.cancel()` へ移行
- [ ] ユニットテスト作成・パス
- [ ] GUI/CLI integration テスト作成・パス
