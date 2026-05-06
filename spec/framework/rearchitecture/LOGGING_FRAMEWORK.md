# ロギングフレームワーク再設計 仕様書

> **対象モジュール**: `src\nyxpy\framework\core\logger\`, `src\nyxpy\framework\core\io\`, `src\nyxpy\gui\panes\`  
> **目的**: 現行 `LogManager` singleton を廃止し、実行単位コンテキスト、ユーザー表示イベント、技術ログ、差し替え可能な sink を持つロギング基盤へ再設計する。
> **関連ドキュメント**: `ERROR_CANCELLATION_LOGGING.md`, `OBSERVABILITY_AND_GUI_CLI.md`, `IMPLEMENTATION_PLAN.md`, `..\archive\logging_design.md`  
> **既存ソース**: `src\nyxpy\framework\core\logger\log_manager.py`, `src\nyxpy\gui\panes\log_pane.py`  
> **破壊的変更**: 旧 `LogManager` / `log_manager` / `log_manager.log(level, message, component="")` / handler API は内部 API とみなし、互換 shim を作らず完全削除する。削除条件と呼び出し元置換ゲートは `DEPRECATION_AND_MIGRATION.md` を正とする。

## 1. 概要

### 1.1 目的

ロギング基盤を、loguru のグローバル logger に直接依存する実装から、`LoggerPort` と `LogSink` を境界にした差し替え可能な設計へ移行する。保存用の `TechnicalLog` と GUI/CLI 向けの `UserEvent` を分離し、すべての実行ログを `run_id` / `macro_id` で追跡できるようにする。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| LoggerPort | Runtime、Command、通知、設定処理から見えるロギング抽象。backend や GUI 実装へ直接依存しない |
| LogSinkDispatcher | sink 登録、解除、snapshot 配信、sink 例外隔離を担当するコンポーネント。`LogManager` の後継であり singleton ではない |
| LogBackend | 技術ログの永続化や console 出力を担う backend。loguru を使う場合も backend 実装の内側へ閉じ込める |
| LogSanitizer | secret mask と JSON 化不能値の縮退を担当するコンポーネント |
| LogEvent | ログ発生時の共通封筒。時刻、level、component、event、message、`run_id`、`macro_id`、`extra`、例外情報を持つ |
| TechnicalLog | ファイル保存、障害調査、集計に使う技術ログ。traceback、例外型、詳細辞書を持てるが secret 値は含めない |
| UserEvent | GUI/CLI へ表示する短いイベント。traceback、secret 値、内部絶対パス、通知 payload を含めない |
| LogSink | `LogEvent`、`TechnicalLog`、`UserEvent` のいずれかを受け取る出力先。core 層では Protocol / ABC だけを定義し、Qt 型へ依存しない |
| RunLogContext | 1 回の実行に紐づく `run_id`、`macro_id`、`macro_name`、入口種別、開始時刻を保持する immutable な値。型定義は本書、所有場所は `RUNTIME_AND_IO_PORTS.md` の `ExecutionContext.run_log_context` を正とする |
| backend | 実際のログ出力を担う実装。候補は loguru、Python logging、structlog、独自 JSON writer である |
| Structured Log | JSON Lines など機械処理しやすい形式の技術ログ。検索、集計、障害解析の入力にする |
| GuiLogSink | `src\nyxpy\gui\` 配下に置く GUI 層 adapter。`LogSink` を実装し、受け取った `UserEvent` を Qt Signal へ変換する。core 層はこの具象クラスを import しない |
| TestLogSink | テストでログをメモリに保持し、イベント名、context、secret マスク、配信順序を検証する sink |

### 1.3 背景・問題

現行 `log_manager.py` は module import 時に `log_manager = LogManager()` を生成し、`LogManager.__init__()` で `logger.remove()` を呼んで loguru のグローバル handler を全削除する。その後、標準出力 handler と `logs/logfile.log` handler を固定設定で追加するため、import だけでファイル出力、handler 変更、ログパス作成が発生し得る。

`LogPane` は `log_manager.add_handler(self._emit_append, level=...)` で loguru の文字列 handler を直接購読する。GUI 表示は保存ログと同じ整形済み文字列を受け取り、`set_custom_handler_level()` 失敗を広い `except Exception` で握るため、handler 状態の破損や解除漏れを診断しにくい。

現行 API は `component` 文字列以外の相関情報を持たない。複数マクロ実行、GUI/CLI の同時操作、通知失敗、キャンセル、終了処理失敗を `run_id` / `macro_id` で追跡できず、ユーザー向け短文と開発者向け traceback も同じログ経路に混在する。

handler 管理は `custom_handlers` の dict と loguru の handler ID に依存し、`RLock`、snapshot 配信、handler 例外隔離、再帰防止方針がない。`set_level()` は dict 反復中に handler ID を差し替えるため、将来の並行登録や GUI close と衝突しやすい。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| import 時副作用 | `log_manager` import で global handler 削除と handler 追加が走る | composition root による backend 明示生成まで handler を変更しない |
| ログ相関 | `component` 文字列のみ | Runtime 経由の全技術ログに `run_id` / `macro_id` / `event` を付与 |
| GUI 表示 | loguru の整形済み文字列を直接表示 | `UserEvent` を GUI adapter が表示文言へ変換 |
| 技術ログ | `logs/logfile.log` に人間向け format で保存 | JSON Lines と人間向け tail を分離し、検索可能な構造を保持 |
| backend 依存 | core が loguru の global logger に密結合 | `LoggerPort` と `LogSink` により backend を差し替え可能 |
| handler 例外 | 方針未定義 | sink 例外は技術ログへ記録し、他 sink とマクロ実行を継続 |
| テスト容易性 | loguru handler ID と実ファイルに依存 | `TestLogSink` で実ファイルなしに検証可能 |
| secret 保護 | 呼び出し側の注意に依存 | `LogEvent` 正規化時に mask 済み `extra` だけを sink へ渡す |

### 1.5 着手条件

- `RUNTIME_AND_IO_PORTS.md` の `RunResult` と、`ERROR_CANCELLATION_LOGGING.md` の `ErrorInfo` / `MacroCancelled` 方針が確定している。
- `ERROR_CANCELLATION_LOGGING.md` の `FrameworkValue` を metadata / error details / log extra の共通値型として使う。
- `RUNTIME_AND_IO_PORTS.md` で `ExecutionContext.run_log_context` が `RunLogContext` の保持場所として確定している。
- 既存 `log_manager.log(level, message, component="")` 呼び出し元は `LoggerPort.technical()` または `LoggerPort.user()` へ置換する。
- core 層から `nyxpy.gui`、Qt 型、CLI 表示実装へ依存しない。
- 実装前に `uv run pytest tests\unit\` のベースラインを確認する。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `spec/framework/rearchitecture/LOGGING_FRAMEWORK.md` | 新規 | 本仕様書 |
| `src\nyxpy\framework\core\logger\events.py` | 新規 | `LogEvent`、`TechnicalLog`、`UserEvent`、`RunLogContext`、event 名を定義 |
| `src\nyxpy\framework\core\logger\ports.py` | 新規 | `LoggerPort`、`LogSink`、`LogBackend` の抽象を定義 |
| `src\nyxpy\framework\core\logger\dispatcher.py` | 新規 | `LogSinkDispatcher` を定義し、sink snapshot 配信と例外隔離を実装 |
| `src\nyxpy\framework\core\logger\backend.py` | 新規 | `LogBackend` と標準 backend factory を定義。loguru 依存はここへ閉じ込める |
| `src\nyxpy\framework\core\logger\sanitizer.py` | 新規 | secret mask と JSON 化不能値の縮退を実装 |
| `src\nyxpy\framework\core\logger\log_manager.py` | 削除 | `LogManager` singleton と旧 `log_manager.log()` 互換 adapter を削除 |
| `src\nyxpy\framework\core\logger\sinks.py` | 新規 | file、console、test sink の標準実装を定義。GUI sink は置かない |
| `src\nyxpy\framework\core\io\ports.py` | 変更 | Logger は `core\logger\ports.py` を正とし、io port 群へ再定義しない |
| `src\nyxpy\framework\core\runtime\context.py` | 変更 | `RunLogContext` を `ExecutionContext.run_log_context` に含める |
| `src\nyxpy\framework\core\runtime\builder.py` | 変更 | composition root から受け取った `LoggerPort` を `ExecutionContext` へ注入する。CLI/GUI 用 logger 構成は担当しない |
| `src\nyxpy\framework\core\macro\command.py` | 変更 | 既存 `Command.log()` を `LoggerPort.user()` / `technical()` へ接続 |
| `src\nyxpy\framework\core\api\notification_handler.py` | 変更 | 通知失敗を secret mask 済み `TechnicalLog` として記録 |
| `src\nyxpy\gui\log_sink.py` | 新規 | `GuiLogSink` を定義し、`UserEvent` を Qt Signal へ変換する GUI 層 adapter |
| `src\nyxpy\gui\panes\log_pane.py` | 変更 | loguru 文字列 handler ではなく `GuiLogSink` 由来の Qt Signal を購読 |
| `tests\unit\framework\logger\test_logging_framework.py` | 新規 | logger port、sink 配信、secret mask、context、handler 例外隔離を検証 |
| `tests\gui\test_log_pane_user_event.py` | 新規 | `LogPane` が `UserEvent` を Qt Signal 経由で表示することを検証 |
| `tests\perf\test_logging_framework_perf.py` | 新規 | sink 配信と構造化ログの性能を検証 |

## 3. 設計方針

### アーキテクチャ上の位置づけ

ロギングは Runtime と GUI/CLI の間にある横断的な port である。Runtime、Command、通知、設定は `LoggerPort` にだけ依存し、backend、ファイル形式、GUI 表示方法を知らない。

```text
MacroRuntime / Command / NotificationHandler
  -> LoggerPort
  -> DefaultLogger
  -> LogSinkDispatcher
  -> LogSink[] / LogBackend
       -> TechnicalFileSink
       -> ConsoleSink
       -> TestLogSink
       -> GUI layer: GuiLogSink
```

core 層は Qt 型へ依存しない。GUI 層は `GuiLogSink` を作成して `LogSinkDispatcher.add_sink()` に `LogSink` として登録し、受け取った `UserEvent` を Qt Signal で GUI スレッドへ渡す。

### 公開 API 方針

旧 `log_manager.log()` と旧 handler API は残さない。Runtime、Command、通知、設定、GUI/CLI adapter は `LoggerPort`、`LogSink`、`UserEvent`、`TechnicalLog` を直接使う。

### 後方互換性

旧 `LogManager` クラス、`log_manager` グローバル、`LogManager.log()`、`set_level()`、`set_console_level()`、`set_file_level()`、`add_handler()`、`set_custom_handler_level()`、`remove_handler()` は内部 API とみなし、互換維持対象に含めない。呼び出し元を新 API へ置換した後に完全削除し、`LegacyStringSink` や互換 adapter は作らない。

`logs/logfile.log` は読み取り対象として残す必要はないが、移行後 1 リリースは同名ファイルへの人間向けログ出力を任意で有効化できる設定を用意する。

### レイヤー構成

| レイヤー | 責務 | 禁止事項 |
|----------|------|----------|
| Runtime / Command | `RunLogContext` を付与し、event 名と message を決める | backend、ファイル path、Qt Signal を扱う |
| LoggerPort | 技術ログとユーザー表示イベントの抽象 API を提供 | loguru の global logger を公開する |
| DefaultLogger | `LoggerPort` 実装、event 生成、context bind、sanitizer と dispatcher/backend の呼び出し | GUI widget、loguru global logger へ直接依存する |
| LogSinkDispatcher | sink 管理、level filter、sink 例外隔離 | backend 初期化、secret mask、GUI widget へ直接依存する |
| LogSink | 出力先ごとの書き込み、flush、close | 他 sink の失敗を制御する |
| GUI adapter | `UserEvent` を GUI スレッドへ転送して表示する | traceback や secret を表示する |

### ロギングフレームワーク選定

| 候補 | 利点 | 懸念 | 採用判断 |
|------|------|------|----------|
| loguru 継続 | 現行依存を維持でき、rotation と sink 追加が簡単 | global logger 前提が強く、`logger.remove()` の影響範囲を制御しにくい | 短期 backend として採用可。ただし `LoggerPort` の裏側へ閉じ込める |
| Python logging への回帰 | 標準ライブラリで長期保守しやすく、ライブラリとの相性がよい | 構造化ログと context bind は自前実装が増える | 依存削減を優先する場合の候補。設計は回帰可能にする |
| structlog 等の構造化ログ導入 | context、processor、JSON 出力が強い | 新規依存と学習コストが増え、GUI sink との境界設計は別途必要 | JSON Lines と context 要件が増えた段階で採用を再判断 |
| 自前薄ラッパ + backend 差し替え | Project NyX 固有の `UserEvent` / `TechnicalLog` を安定 API にできる | ラッパ設計を誤ると標準機能を再実装し過ぎる | 採用方針。backend は実装詳細として loguru から開始する |

採用判断基準は次の順で評価する。

| 基準 | 判定内容 |
|------|----------|
| 移行性 | 既存 `log_manager` 呼び出し元を `LoggerPort` / `LogSink` へ段階置換できる |
| 構造化 | `run_id`、`macro_id`、`event`、`component`、`extra` を欠落なく保存できる |
| 表示分離 | `UserEvent` と `TechnicalLog` を別 sink へ送れる |
| 副作用制御 | import 時に global handler を変更せず、明示初期化できる |
| テスト容易性 | `TestLogSink` でファイル、標準出力、GUI なしに検証できる |
| スレッド安全性 | sink 登録解除と配信が snapshot 方式で deadlock しない |
| 運用 | rotation、保持期間、flush、close、障害時 fallback を設定できる |

本仕様の結論は「自前薄ラッパ + backend 差し替え」を採用し、初期 backend は loguru adapter とする。Python logging または structlog への移行は、`LogBackend` 実装の差し替えで行う。

### 性能要件

| 指標 | 目標値 |
|------|--------|
| handler なし `LoggerPort.technical()` | 1 件 2 ms 未満 |
| sink 3 件への配信 | 1 件 5 ms 未満 |
| GUI sink 10 件への `UserEvent` 配信 | 1 件 10 ms 未満 |
| `RunLogContext` bind | 1 回 1 ms 未満 |
| 1 実行あたり structured JSONL flush | 1 秒以内または終了時確実に flush |
| sink 例外時の他 sink 継続 | 100% |

### 並行性・スレッド安全性

sink 登録、解除、level 変更、close は `threading.RLock` で保護する。配信時は lock 内で sink と level filter の snapshot を作り、lock 外で sink を呼ぶ。sink が `LoggerPort` を再利用しても deadlock しないよう、例外記録には GUI sink を通さない内部技術ログ経路を使う。

`RunLogContext` は immutable とし、`LoggerPort.bind_context(context)` は context を持つ軽量 logger を返す。非同期実行では contextvars を補助的に使ってよいが、Runtime は `ExecutionContext` から明示的に `LoggerPort` を渡すことを正とする。

## 4. 実装仕様

### 公開インターフェース

```python
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from nyxpy.framework.core.errors import FrameworkValue

type LogExtraValue = FrameworkValue


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class RunLogContext:
    run_id: str
    macro_id: str
    macro_name: str = ""
    entrypoint: str = "runtime"
    started_at: datetime | None = None


@dataclass(frozen=True)
class LogEvent:
    timestamp: datetime
    level: LogLevel
    component: str
    event: str
    message: str
    run_id: str | None = None
    macro_id: str | None = None
    extra: Mapping[str, LogExtraValue] = field(default_factory=dict)
    exception_type: str | None = None
    traceback: str | None = None


@dataclass(frozen=True)
class TechnicalLog:
    event: LogEvent
    include_traceback: bool = True


@dataclass(frozen=True)
class UserEvent:
    timestamp: datetime
    level: LogLevel
    component: str
    event: str
    message: str
    run_id: str | None = None
    macro_id: str | None = None
    code: str | None = None
    extra: Mapping[str, LogExtraValue] = field(default_factory=dict)


class LoggerPort(Protocol):
    def bind_context(self, context: RunLogContext) -> "LoggerPort": ...

    def technical(
        self,
        level: str,
        message: str,
        *,
        component: str,
        event: str = "log.message",
        extra: Mapping[str, LogExtraValue] | None = None,
        exc: BaseException | None = None,
    ) -> None: ...

    def user(
        self,
        level: str,
        message: str,
        *,
        component: str,
        event: str,
        code: str | None = None,
        extra: Mapping[str, LogExtraValue] | None = None,
    ) -> None: ...


class LogSink(ABC):
    @abstractmethod
    def emit_technical(self, event: TechnicalLog) -> None: ...

    def emit_user(self, event: UserEvent) -> None: ...
    def flush(self) -> None: ...
    def close(self) -> None: ...


class LogSinkDispatcher:
    def add_sink(self, sink: LogSink, *, level: str = "INFO") -> str: ...
    def remove_sink(self, sink_id: str) -> None: ...


class DefaultLogger(LoggerPort):
    def __init__(
        self,
        dispatcher: LogSinkDispatcher,
        sanitizer: "LogSanitizer",
        backend: LogBackend,
    ) -> None: ...
```

`LoggerPort.bind_context()` は `RunLogContext` を保持した context 付き `LoggerPort` を返す self-like interface である。`RunLogContext` の所有者は `ExecutionContext` であり、`LoggerPort` は出力時に参照する束縛ビューだけを返す。戻り値を close する責務はなく、sink と backend の close は GUI / CLI composition root または Runtime の Port close で扱う。

### 内部設計

#### 初期化

GUI / CLI composition root は `LogBackend`、`LogSinkDispatcher`、`LogSanitizer`、`DefaultLogger` を明示生成する。module import 時に backend handler、ファイル、標準出力を作成しない。未設定状態で `LoggerPort.user()` / `technical()` が呼ばれた場合は `LoggingConfigurationError` とし、成功扱いの fallback は作らない。

#### 配信手順

```text
LoggerPort.technical() / user()
  -> LogEvent 正規化
  -> secret mask と JSON 化可能性を検査
  -> RLock 内で sink snapshot を作成
  -> lock 外で sink.emit_* を呼ぶ
  -> sink 例外を内部技術ログへ記録
  -> 他 sink と呼び出し元処理を継続
```

`LoggerPort.user()` は `UserEvent` と、対応する要約 `TechnicalLog` の両方を生成する。ユーザーに見せた文言も調査時に追跡できるようにするためである。`LoggerPort.technical()` は `user_visible=False` 相当であり、GUI/CLI へは出さない。

#### sink lock policy

`LogSinkDispatcher` の sink 登録、解除、level 更新、配信先 snapshot 作成は `sink_lock` で保護する。lock 内では sink の一覧と level 判定に必要な immutable snapshot だけを作り、`emit_*()`、`flush()`、`close()`、Qt Signal emit、ファイル I/O は lock 外で実行する。

| lock 名 | 種別 | 保護対象 | 取得順 | timeout | timeout 時の扱い | 保持してはいけない処理 | テスト名 |
|---------|------|----------|--------|---------|------------------|------------------------|----------|
| `sink_lock` | `threading.RLock` | sink registry、level、配信先 snapshot | 全体 5 番目。`frame_lock` より後、他 lock 取得中の logging 呼び出しでは取得しない | 1 秒 | `LogSinkError(code="logging.sink_lock_timeout")` を fallback stderr へ出し、呼び出し元へ再送出しない | sink `emit_*()`、backend write、Qt Signal emit、retention cleanup | `test_log_sink_dispatcher_snapshot_lock_order` |

fallback stderr は通常 sink 経路が使えない場合の最後の通知先であるため、出力内容を固定文言、event code、component、例外型、mask 済み要約に限定する。元例外の message を出す場合も `LogSanitizer.mask_text()` 相当を必ず通し、secret、通知 payload、内部 token、絶対 path を平文で出力しない。

他コンポーネントが `registry_reload_lock`、`run_start_lock`、`run_handle_lock`、`frame_lock` を保持したまま `LoggerPort` を呼ぶ設計は禁止する。ログを残す必要がある場合は、保護対象の値を局所変数へ退避し、lock を解放してから `LoggerPort` を呼ぶ。

#### GUI sink の境界

`GuiLogSink` は core 層の sink 実装ではなく、GUI 層 adapter である。core 層は `LogSink` Protocol / ABC と `UserEvent` だけを知り、Qt 型、Qt Signal、GUI widget へ依存しない。

```text
LoggerPort.user()
  -> DefaultLogger が UserEvent を生成
  -> LogSinkDispatcher が RLock 内で sink snapshot を作成
  -> lock 外で LogSink.emit_user(UserEvent) を呼ぶ
  -> src\nyxpy\gui\log_sink.py の GuiLogSink.emit_user()
  -> Qt Signal emit
  -> GUI thread の LogPane slot が表示を更新
```

`GuiLogSink.emit_user()` が呼ばれるスレッドは、ログを発行した Runtime worker thread または GUI thread のどちらでもあり得る。`GuiLogSink` は widget を直接更新せず、Qt Signal だけを emit する。Qt Signal から LogPane の slot への queued connection と UI 更新は GUI 層の責務である。`GuiLogSink` が例外を送出した場合、`LogSinkDispatcher` は `sink.emit_failed` の TechnicalLog を記録し、後続 sink とマクロ実行を継続する。

#### UserEvent と TechnicalLog の分離

| 項目 | UserEvent | TechnicalLog |
|------|-----------|--------------|
| 主用途 | GUI log pane、CLI 表示、status 表示 | 障害調査、検索、集計、サポート情報 |
| message | 1 行の短文 | 詳細でもよいが secret mask 済み |
| traceback | 含めない | DEBUG 詳細として保持可 |
| 内部 path | 原則含めない | 相対 path または mask 済みで保持可 |
| secret 値 | 含めない | `LogSanitizer` を通した mask 済み要約のみ |
| 通知 payload | 含めない | secret と本文を mask した要約のみ |
| sink | GUI 層の `GuiLogSink`、CLI presenter | JSONL file、人間向け file、console debug |

#### 実行単位コンテキスト

Runtime builder は `RunLogContext(run_id, macro_id, macro_name, entrypoint)` を作成して `ExecutionContext.run_log_context` に保持する。`ExecutionContext.logger` は `LoggerPort.bind_context(run_log_context)` の戻り値であり、`Command`、`NotificationPort`、`MacroRunner` に渡す。実行終了時は `macro.finished`、中断時は `macro.cancelled`、失敗時は `macro.failed` を同じ context で記録する。

#### Event catalog

ログ event 名、UserEvent の表示方針、TechnicalLog の保持項目は本表を正とする。他仕様は event catalog ID の発行タイミングだけを定義し、event 名を追加・変更する場合は本表を先に更新する。`RUNTIME_AND_IO_PORTS.md`、`ERROR_CANCELLATION_LOGGING.md`、`OBSERVABILITY_AND_GUI_CLI.md` は本表の ID を参照し、独自の event 名正本を持たない。

| event | 発生元 | TechnicalLog | UserEvent |
|-------|--------|--------------|-----------|
| `macro.started` | `MacroRuntime` | `run_id`, `macro_id`, entrypoint | `マクロを開始しました` |
| `macro.finished` | `MacroRunner` | `RunResult`, duration | `マクロが完了しました` |
| `macro.cancel_requested` | `RunHandle.cancel()` / `Command.stop()` | `source`, `reason`, `run_id`, `macro_id` | `中断を要求しました` |
| `macro.cancelled` | `MacroRunner` | `RunResult`, cancelled_reason | `マクロを中断しました` |
| `macro.failed` | `MacroRunner` | `ErrorInfo`, exception_type, traceback | `マクロ実行中にエラーが発生しました` |
| `macro.finalize_failed` | `MacroRunner` | finalize 例外詳細、元 outcome | `終了処理でエラーが発生しました` |
| `configuration.invalid` | settings / args 検証 | key 名、期待型、mask 済み詳細、error code | `設定に誤りがあります` |
| `notification.failed` | `NotificationPort` | 通知先種別、mask 済み詳細 | 原則表示しない。必要時のみ warning 表示 |
| `log.retention_cleanup_failed` | `LogBackend` | 対象 path、例外型、message | 原則表示しない |
| `sink.emit_failed` | `LogSinkDispatcher` | sink_id、event、例外型、message | 原則表示しない |

#### 旧 handler API の削除

旧 `LogManager.add_handler()` / `remove_handler()` / `set_custom_handler_level()` は実装しない。GUI は `GuiLogSink`、テストは `TestLogSink`、CLI は console sink を使う。旧 callable handler を包む `LegacyStringSink` は作らず、呼び出し元を `LogSink` へ移行する。`src\nyxpy\gui\main_window.py`、`src\nyxpy\cli\run_cli.py`、`src\nyxpy\framework\core\hardware\capture.py`、通知実装、既存 logger テストの旧 API 参照がなくなったことを削除ゲートにする。

#### テスト用 sink

`TestLogSink` は `TechnicalLog` と `UserEvent` をそれぞれ list に保持する。テストは次を直接検証できる。

- event 名と level
- `run_id` / `macro_id` の付与
- traceback が `UserEvent` に含まれないこと
- secret 値が `extra` に残らないこと
- sink 例外時に後続 sink が呼ばれること
- close / flush が実行終了時に呼ばれること

#### ログファイル配置、ローテーション、保持ポリシー

| 種別 | 既定 path | 形式 | rotation | retention | 用途 |
|------|-----------|------|----------|-----------|------|
| 人間向け技術ログ | `logs\nyxpy.log` | text | 10 MB | 14 日 | 開発中の tail と簡易確認 |
| 実行単位構造化ログ | `logs\runs\{yyyyMMdd}\{run_id}.jsonl` | JSON Lines | 実行ごと | 30 日 | マクロ実行の調査、GUI/CLI の相関 |
| framework 構造化ログ | `logs\framework.jsonl` | JSON Lines | 10 MB | 30 日 | 起動、設定、デバイス検出、通知失敗 |

保持期間を過ぎたファイルは composition root が backend を明示生成する時点で削除対象としてよい。削除失敗は `log.retention_cleanup_failed` の技術ログに残し、アプリ起動は継続する。ファイル書き込みに失敗した場合、該当 sink を無効化して console sink へ警告を出す。

### 設定パラメータ

| パラメータ | 型 | デフォルト | 説明 |
|------------|-----|-----------|------|
| `logging.backend` | `str` | `"loguru"` | `loguru`、`logging`、`structlog`、`json_writer` のいずれか |
| `logging.base_dir` | `str` | `"logs"` | ログ出力の基準ディレクトリ |
| `logging.file_level` | `str` | `"DEBUG"` | 技術ログファイルの最低 level |
| `logging.console_level` | `str` | `"INFO"` | CLI/コンソール向け最低 level |
| `logging.gui_level` | `str` | `"INFO"` | GUI `UserEvent` の最低 level |
| `logging.structured_enabled` | `bool` | `True` | JSON Lines の構造化ログを出すか |
| `logging.human_log_enabled` | `bool` | `True` | 人間向け text ログを出すか |
| `logging.rotation_size_mb` | `int` | `10` | 人間向けログと framework JSONL の rotation サイズ |
| `logging.run_retention_days` | `int` | `30` | 実行単位構造化ログの保持日数 |
| `logging.framework_retention_days` | `int` | `30` | framework 構造化ログの保持日数 |
| `logging.human_retention_days` | `int` | `14` | 人間向け text ログの保持日数 |
| `logging.include_traceback` | `bool` | `True` | 技術ログへ traceback を保存するか |
| `logging.mask_secret_keys` | `list[str]` | `[]` | 追加で mask する key 名。既定 secret key 群に加える |

### エラーハンドリング

| 例外クラス | 発生条件 |
|------------|----------|
| `LoggingConfigurationError` | 不正な level、backend 名、ログ path、rotation 設定を受け取った |
| `LogSinkError` | sink が emit、flush、close に失敗した、または `sink_lock` の取得が 1 秒以内に完了しない。外部へは再送出せず内部技術ログまたは fallback stderr へ変換する |
| `LogSerializationError` | `extra` が JSON 化できない。`repr()` に縮退し技術ログへ記録する |
| `SecretMaskingError` | mask 処理に失敗した。元値を出さず key 名だけ記録する |

sink 例外はマクロ実行結果を失敗にしない。ただし技術ログ sink がすべて失敗した場合は、`LoggerHealth` が degraded を返し、GUI/CLI が「ログ保存に失敗しています」を表示できるようにする。

### シングルトン管理

`log_manager` グローバルインスタンスは互換のため維持しない。アプリ起動時に必要な lifetime で `LogBackend`、`LogSinkDispatcher`、`LogSanitizer`、`DefaultLogger` を生成し、`MacroRuntimeBuilder` へ `LoggerPort` として渡す。`singletons.py` の `reset_for_testing()` が存在する場合も、logging のグローバル状態ではなく、テストごとの `TestLogSink` と logging components を初期化する。

`RunLogContext`、`LoggerPort.bind_context()` の戻り値、`TestLogSink` は実行またはテストごとのオブジェクトであり、`singletons.py` へ登録しない。

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| ユニット | `test_logger_import_has_no_backend_side_effect` | import だけで loguru global handler 削除とファイル sink 追加が行われない |
| ユニット | `test_legacy_log_api_removed` | `log_manager.log(level, message, component)` 互換 API が残っていない |
| ユニット | `test_logger_port_binds_run_context` | `bind_context()` 後のログに `run_id` / `macro_id` が入る |
| ユニット | `test_user_event_does_not_include_traceback_or_secret` | `UserEvent` が traceback、secret、内部詳細を含まない |
| ユニット | `test_technical_log_masks_secret_values` | `TechnicalLog.extra` の secret 値が mask される |
| ユニット | `test_sink_exception_is_logged_and_ignored` | 失敗 sink があっても後続 sink と呼び出し元処理が継続する |
| ユニット | `test_log_sink_dispatcher_exception_isolation` | GUI sink 相当の sink が例外を送出しても後続 sink が呼ばれる |
| ユニット | `test_fallback_stderr_masks_secret_values` | `sink_lock` timeout 時の fallback stderr に secret、通知 payload、絶対 path が平文で出ない |
| ユニット | `test_sink_snapshot_allows_remove_during_emit` | sink 呼び出し中に登録解除しても deadlock しない |
| ユニット | `test_test_log_sink_records_user_and_technical_events` | `TestLogSink` で user / technical を個別検証できる |
| ユニット | `test_logging_config_rejects_invalid_level` | 不正 level を `LoggingConfigurationError` にする |
| ユニット | `test_log_serialization_falls_back_to_repr` | JSON 化不能な `extra` を安全に縮退する |
| 結合 | `test_command_log_emits_macro_message_with_context` | 既存 `Command.log()` が `macro.message` と実行 context を付与する |
| 結合 | `test_notification_failure_is_technical_log_only` | 通知失敗は secret mask 済み技術ログに残り、原則 GUI 表示しない |
| GUI | `test_gui_log_pane_displays_user_event_from_sink` | `LogPane` が `UserEvent` を Qt Signal で表示する |
| GUI | `test_gui_log_sink_emits_qt_signal_without_core_qt_dependency` | `GuiLogSink` が GUI 層で `UserEvent` を Qt Signal へ変換し、core 層が Qt 型を import しない |
| GUI | `test_log_pane_level_filter_uses_gui_sink` | DEBUG 表示切替が GUI sink の level に反映される |
| 性能 | `test_log_handler_dispatch_thread_safety` | sink 登録解除と配信で deadlock しない |
| 性能 | `test_gui_user_event_dispatch_perf` | GUI sink 10 件への配信が 1 件 10 ms 未満 |

## 6. 実装チェックリスト

### 6.1 仕様確定

- [ ] `LogEvent`、`TechnicalLog`、`UserEvent`、`RunLogContext` のシグネチャ確定
- [ ] `LoggerPort`、`LogSink`、`LogBackend` の抽象定義

### 6.2 実装

- [ ] `LogManager` singleton と module-level `log_manager` を削除
- [ ] `DefaultLogger`、`LogSinkDispatcher`、`LogBackend`、`LogSanitizer` を実装
- [ ] 旧 `LogManager.log()` と handler API の呼び出し元を新 API へ置換
- [ ] `UserEvent` と `TechnicalLog` の分離配信を実装
- [ ] `RunLogContext` を `ExecutionContext` と `Command.log()` へ接続
- [ ] secret mask と JSON 化不能値の縮退処理を実装
- [ ] sink 登録解除の `RLock`、snapshot 配信、handler 例外隔離を実装
- [ ] `TestLogSink` を実装
- [ ] ログファイル配置、rotation、保持期間、cleanup を実装
- [ ] `LogPane` を `UserEvent` 購読へ移行
- [ ] 通知失敗と Runtime 失敗を技術ログへ記録

### 6.3 検証

- [ ] ユニットテスト作成・パス
- [ ] GUI テスト作成・パス
- [ ] パフォーマンステスト作成・パス
- [ ] `uv run ruff check .` がパス
- [ ] `uv run pytest tests\unit\` がパス
