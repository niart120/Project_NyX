# 可観測性と GUI/CLI 入口再設計 仕様書

> **対象モジュール**: `src\nyxpy\framework\core\runtime\`, `src\nyxpy\framework\core\logger\`, `src\nyxpy\framework\core\settings\`, `src\nyxpy\cli\`, `src\nyxpy\gui\`  
> **目的**: GUI/CLI の実行入口を `MacroRuntime` へ寄せ、表示、終了コード、通知設定ソースを一貫させる。ロギング基盤の詳細は `LOGGING_FRAMEWORK.md` を正とする。  
> **関連ドキュメント**: `RUNTIME_AND_IO_PORTS.md`, `ERROR_CANCELLATION_LOGGING.md`, `CONFIGURATION_AND_RESOURCES.md`, `LOGGING_FRAMEWORK.md`  
> **破壊的変更**: 既存マクロの `Command.log()` 呼び出しと import / lifecycle 互換は維持する。GUI/CLI 内部入口、Worker / command 組み立て、singleton 直接利用、暗黙 fallback、`DefaultCommand` 旧コンストラクタは互換維持対象に含めず、新 API へ置換または削除する。

## 1. 概要

### 1.1 目的

GUI と CLI が個別に `DefaultCommand`、通知、ログ、中断を組み立てる状態を解消し、`MacroRuntime` を実行入口として統一する。ログの保存形式、GUI 表示イベント、`run_id` / `macro_id` 追跡、秘密値保護、sink 例外隔離は `LOGGING_FRAMEWORK.md` の仕様を参照する。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| MacroRuntime | GUI/CLI/Legacy 入口から呼ばれるマクロ実行中核。同期実行、非同期実行、キャンセル、結果取得を提供する |
| MacroRuntimeBuilder | `GlobalSettings`、`SecretsSettings`、デバイス検出結果から `MacroRuntime` と `ExecutionContext` を組み立てる adapter |
| RunHandle | GUI から非同期実行を監視し、中断要求、完了待ち、結果取得を行うハンドル |
| RunResult | CLI の終了コード、GUI の実行完了表示、構造化ログに使う実行結果 |
| run_id | 1 回の実行を識別する UUID 文字列。ログ、GUI 表示イベント、`RunResult` を関連付ける |
| macro_id | 実行対象マクロを識別する安定 ID。構造化ログと GUI/CLI 表示の軸になる |
| 構造化ログ | `LOGGING_FRAMEWORK.md` の `TechnicalLog`。保存・解析に使う |
| GUI 表示イベント | `LOGGING_FRAMEWORK.md` の `UserEvent`。GUI のログペイン、ステータスバー、通知バナーへ渡す |
| ユーザー表示 | GUI/CLI に出す短い文言。secret 値、traceback、内部 path の詳細を含めない |
| 技術ログ | 開発者が調査に使う保存ログ。詳細な仕様は `LOGGING_FRAMEWORK.md` を正とする |
| LoggerPort | Runtime / GUI / CLI adapter が使うロギング抽象。詳細は `LOGGING_FRAMEWORK.md` を正とする |
| GuiLogSink | `src\nyxpy\gui\` 配下に置く GUI 層 adapter。core 層の `LogSink` を実装し、`UserEvent` を Qt Signal へ変換する |
| SecretsSettings | 通知 secret の唯一の設定ソース。CLI 独自構造や `GlobalSettings` へ secret 値を複製しない |

### 1.3 背景・問題

既存仕様では Runtime と I/O Ports の分離、異常系、構造化ログの方向性が定義されている。ただし、GUI/CLI をどの段階で `MacroRuntime` 入口へ寄せるか、CLI 通知設定ソースを `SecretsSettings` に統一する問題、ユーザー表示と技術ログの境界は独立した観点として明文化が不足していた。sink 例外・ロック方針は `LOGGING_FRAMEWORK.md` を正とする。

現行 GUI/CLI がそれぞれ `DefaultCommand` を組み立てると、通知設定、キャンセル、logger 注入、デバイス検出完了待ちが入口ごとにずれる。再設計ではマクロ実行契約を維持し、入口側の組み立てを `MacroRuntimeBuilder` へ集約する。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| GUI/CLI の実行組み立て | 入口ごとに `DefaultCommand` を構築 | `MacroRuntimeBuilder` 経由の 1 系統 |
| 通知 secret の参照元 | CLI/GUI で分岐し得る | `SecretsSettings` のみ |
| ログ相関 | 文字列ログ中心 | `LOGGING_FRAMEWORK.md` の `RunLogContext` を GUI/CLI 実行へ接続 |
| GUI 表示と保存ログ | 同一 handler に依存しやすい | `LOGGING_FRAMEWORK.md` の `UserEvent` と `TechnicalLog` を利用 |
| sink 例外 | 方針未定義 | `LOGGING_FRAMEWORK.md` の sink 例外隔離に従う |
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
| `src\nyxpy\framework\core\logger\log_manager.py` | 変更 | `LOGGING_FRAMEWORK.md` の `LoggerPort` / sink 基盤を Runtime builder から利用 |
| `src\nyxpy\framework\core\logger\events.py` | 新規 | `LOGGING_FRAMEWORK.md` の `UserEvent` / `TechnicalLog` 定義を利用 |
| `src\nyxpy\framework\core\settings\secrets_settings.py` | 変更 | CLI/GUI 共通の通知設定ソースとして schema を提供 |
| `src\nyxpy\cli\run_cli.py` | 変更 | `RuntimeBuildRequest` と `MacroRuntimeBuilder.run()` を使い、終了コードを `RunResult` から決定 |
| `src\nyxpy\gui\main_window.py` | 変更 | `MacroRuntime.start()` と `RunHandle` を使う実行制御へ移行 |
| `src\nyxpy\gui\panes\log_pane.py` | 変更 | `UserEvent` を表示し、保存ログ sink へ直接依存しない |
| `tests\unit\framework\logger\test_logging_framework.py` | 新規 | ロギング基盤の詳細テストは `LOGGING_FRAMEWORK.md` に従う |
| `tests\integration\test_cli_runtime_entry.py` | 新規 | CLI が Runtime 入口と `SecretsSettings` を使うことを検証 |
| `tests\gui\test_runtime_entry.py` | 新規 | GUI が `RunHandle` と GUI 表示イベントで実行状態を反映することを検証 |

## 3. 設計方針

### アーキテクチャ上の位置づけ

GUI/CLI はフレームワークの上位 adapter であり、マクロ実行中核ではない。実行要求、デバイス検出、通知設定、ログ相関、キャンセル、結果取得は `MacroRuntimeBuilder` と `MacroRuntime` に寄せる。`MacroRuntimeBuilder` の API と build 順序は `RUNTIME_AND_IO_PORTS.md` を正とし、本書では GUI/CLI がそれをどう呼び出すかだけを定義する。

```text
nyxpy.cli.run_cli
  -> RuntimeBuildRequest(...)
  -> MacroRuntimeBuilder.run(request)
  -> RunResult

nyxpy.gui.main_window
  -> RuntimeBuildRequest(...)
  -> MacroRuntimeBuilder.start(request)
  -> RunHandle
  -> UserEvent
```

Runtime 本体は Qt、argparse、標準出力表示へ依存しない。GUI/CLI は `RunResult` と表示イベントを、自身の UI または標準出力へ変換する。

### 公開 API 方針

ロギングの公開 API は `LOGGING_FRAMEWORK.md` の `LoggerPort`、`UserEvent`、`TechnicalLog`、`LogSink` を正とする。本書では GUI/CLI が Runtime builder から `LoggerPort` を受け取り、`UserEvent` を表示へ変換することだけを定める。

### 後方互換性

既存 CLI オプションと GUI 操作は段階移行で維持する。CLI の出力文言は短いユーザー表示へ変更してよいが、成功時 0、失敗時 非 0、中断時 130 の終了コードを明示する。GUI の `WorkerThread` は Runtime adapter へ縮小または置換してよいが、マクロ本体のスレッド実行と GUI スレッド更新の分離は維持する。

`Command.notify()` は既存呼び出しを維持する。通知先の有効化、webhook URL、Bluesky credentials は `SecretsSettings` からのみ読み、CLI 引数や `GlobalSettings` に secret 値を複製しない。

### レイヤー構成

| レイヤー | 責務 | 禁止事項 |
|----------|------|----------|
| Runtime | 実行、結果、キャンセル、構造化ログ context 付与 | Qt、argparse、標準出力への直接依存 |
| Logger | `LOGGING_FRAMEWORK.md` の `LoggerPort` と sink を提供 | secret 平文出力、sink 例外の再送出 |
| CLI adapter | 引数解析、Runtime 呼び出し、終了コード、ユーザー表示 | secret 値の独自保存、`DefaultCommand` 直接構築 |
| GUI adapter | 操作イベント、`RunHandle` 監視、画面表示、Qt signal 変換 | Runtime 本体への Qt 依存混入 |
| Notification adapter | `SecretsSettings` から通知先を構築 | `GlobalSettings` から secret 値を読む |

### 性能要件

| 指標 | 目標値 |
|------|--------|
| `LoggerPort` 注入の追加コスト | Runtime context 作成 1 回 1 ms 未満 |
| GUI `UserEvent` 受信から Qt Signal emit | 1 event 10 ms 未満 |
| sink 例外発生時の GUI/CLI 継続 | `LOGGING_FRAMEWORK.md` の隔離方針に従い 100% |
| CLI 起動時の Runtime builder 追加コスト | デバイス検出を除き 100 ms 未満 |
| GUI cancel ボタンから中断要求発火 | 100 ms 未満 |

### 並行性・スレッド安全性

sink 登録、削除、配信対象 snapshot 作成は `LOGGING_FRAMEWORK.md` に従う。GUI adapter は `UserEvent` を受け取ったら Qt Signal で GUI スレッドへ転送し、core 層へ Qt 依存を持ち込まない。

`run_id` と `macro_id` は `ExecutionContext` 作成時に確定し、実行中は immutable とする。`RunHandle.cancel()` は GUI スレッドから呼べる中断要求 API であり、例外を送出しない。

## 4. 実装仕様

### 公開インターフェース

`UserEvent`、`TechnicalLog`、`LoggerPort`、`LogSink` の公開インターフェースは `LOGGING_FRAMEWORK.md` を正とする。`MacroRuntimeBuilder`、`RuntimeBuildRequest`、`ExecutionContext`、`RunHandle`、`RunResult` は `RUNTIME_AND_IO_PORTS.md` を正とする。GUI/CLI 入口側で本書が追加定義する公開面は次である。

```python
class UserMessage:
    level: str
    text: str
    code: str | None = None


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

CLI は `RuntimeBuildRequest` を作成して `MacroRuntimeBuilder.run(request)` を呼ぶ。設定 snapshot、`SecretsSettings`、デバイス検出、通知 Port、LoggerPort、Resource scope の組み立て順序は `RUNTIME_AND_IO_PORTS.md` に従う。CLI は settings / resource を個別解決せず、`DefaultCommand` も直接生成しない。

```text
run_cli.main()
  -> args parse
  -> request = RuntimeBuildRequest(macro_id=args.macro, entrypoint="cli", exec_args=args.define)
  -> result = builder.run(request)
  -> CliPresenter.exit_code(result)
```

GUI は起動時に `MacroRuntimeBuilder` を構成し、実行ボタンで `RuntimeBuildRequest(entrypoint="gui", ...)` を作成して `builder.start(request)` を呼ぶ。GUI cancel は `RunHandle.cancel()` のみを呼び、`Command.stop()` を GUI スレッドから直接呼ばない。

#### CLI 通知設定ソース

通知 secret は `SecretsSettings` が唯一の入力元である。CLI 引数で通知先を直接受け取る場合でも、その値を一時的な `SecretsSettings` snapshot として扱い、`GlobalSettings` やログ context へ平文を渡さない。Runtime builder が `SecretsSettings` 以外から secret 値を受け取った場合は `ConfigurationError` とする。

#### ロギング基盤との接続

構造化ログ、GUI 表示イベント、sink 配信、`run_id` / `macro_id` の保持、secret mask は `LOGGING_FRAMEWORK.md` を正とする。CLI は `LoggerPort` を Runtime builder から受け取り、GUI は `src\nyxpy\gui\log_sink.py` の `GuiLogSink` で `UserEvent` を Qt Signal へ変換する adapter に留める。core 層は `GuiLogSink` を import せず、`LogSink` Protocol / ABC だけを知る。

#### sink 例外・ロック方針

sink 登録解除、snapshot 配信、例外隔離、再帰防止は `LOGGING_FRAMEWORK.md` に従う。本書では GUI が `UserEvent` を受け取った後、Qt Signal で GUI スレッドへ渡すことだけを定める。

```text
Runtime worker thread
  -> LoggerPort.user()
  -> LogManager dispatches UserEvent to LogSink
  -> GuiLogSink.emit_user(UserEvent)
  -> Qt Signal emit
  -> LogPane slot on GUI thread
```

`GuiLogSink` は widget を直接更新しない。Qt Signal emit 以降の queued connection、表示整形、LogPane 更新は GUI 層の責務である。`GuiLogSink` 例外は `LOGGING_FRAMEWORK.md` の sink 例外隔離に従い、GUI 操作とマクロ実行へ再送出しない。

#### ユーザー表示と技術ログの分離

`ErrorInfo.message` はユーザー表示可能な短文に限定する。traceback、内部絶対パス、secret 値、通知 payload は `LOGGING_FRAMEWORK.md` の `TechnicalLog` へ分離する。CLI は `CliPresenter.render_result()` で `RunResult` を `UserMessage` に変換し、GUI は同じ `UserMessage` 相当を status 表示へ渡す。

### エラーハンドリング

| 例外クラス | 発生条件 |
|------------|----------|
| `ConfigurationError` | 通知 secret を `SecretsSettings` 以外から受け取った、ログレベル不正、CLI 引数不正 |
| `GuiSinkError` | GUI sink 例外の内部表現。外部へ再送出せず `LOGGING_FRAMEWORK.md` の sink 例外隔離へ渡す |
| `LoggingConfigurationError` | loguru sink 作成失敗、ログファイル path 不正 |
| `MacroRuntimeError` | マクロ実行中の未分類例外。`RunResult.error` と技術ログへ記録 |

ユーザー表示では例外クラス名を必要以上に出さない。技術ログでは `exception_type` と traceback を保存するが、secret 値は mask 済み辞書だけを記録する。

### シングルトン管理

既存 `log_manager` シングルトンは維持する。GUI sink は GUI の lifetime に合わせて登録・解除し、詳細な reset 方針は `LOGGING_FRAMEWORK.md` に従う。`MacroRuntimeBuilder`、`RunHandle`、`RunResult` は実行単位のオブジェクトであり、シングルトンにしない。

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| ユニット | `test_user_message_excludes_traceback` | GUI/CLI の `UserMessage` に traceback が含まれない |
| ユニット | `test_runtime_builder_passes_logger_port` | Runtime builder が `LOGGING_FRAMEWORK.md` の `LoggerPort` を実行 context へ渡す |
| ユニット | `test_cli_presenter_exit_codes` | 成功 0、失敗 2、中断 130 の終了コードを返す |
| ユニット | `test_runtime_builder_rejects_cli_secret_outside_secrets_settings` | CLI 通知 secret の入力元違反を `ConfigurationError` にする |
| 結合 | `test_cli_uses_macro_runtime_entry` | CLI が `DefaultCommand` 直接構築ではなく Runtime builder を使う |
| 結合 | `test_cli_notification_settings_source_is_secrets_settings` | CLI 通知設定が `SecretsSettings` に統一される |
| GUI | `test_main_window_uses_run_handle` | GUI 実行開始で `MacroRuntime.start()` の `RunHandle` を保持する |
| GUI | `test_main_window_cancel_calls_handle_cancel` | GUI cancel が `Command.stop()` ではなく `RunHandle.cancel()` を呼ぶ |
| GUI | `test_log_pane_receives_user_event` | `LogPane` が `UserEvent` を表示する |
| GUI | `test_gui_log_sink_emits_qt_signal` | `GuiLogSink` が `UserEvent` を Qt Signal へ変換し、LogPane slot が GUI thread で受け取る |
| ハードウェア | `test_realdevice_cli_runtime_logging` | `@pytest.mark.realdevice`。実機 CLI 実行で run_id 付きログが残る |
| 性能 | `test_gui_user_event_dispatch_perf` | GUI `UserEvent` 受信から Qt Signal emit まで 10 ms 未満 |
| 性能 | `test_cancel_button_to_token_latency_perf` | GUI cancel から token 発火まで 100 ms 未満 |

## 6. 実装チェックリスト

- [ ] GUI/CLI の `DefaultCommand` 直接構築箇所を Runtime builder へ寄せる
- [ ] `GuiLogSink` を GUI 層 adapter として実装し、core 層の Qt 依存を禁止
- [ ] CLI 通知設定ソースを `SecretsSettings` に統一
- [ ] `LOGGING_FRAMEWORK.md` の `LoggerPort` / `UserEvent` を GUI/CLI 入口へ接続
- [ ] ユーザー表示から traceback、secret、内部詳細を除外
- [ ] CLI 終了コードを `RunResult` から決定
- [ ] GUI cancel を `RunHandle.cancel()` へ移行
- [ ] ユニットテスト作成・パス
- [ ] GUI/CLI integration テスト作成・パス
