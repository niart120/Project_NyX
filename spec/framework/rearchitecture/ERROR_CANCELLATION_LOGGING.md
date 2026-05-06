# 異常系・中断・ログ再設計 仕様書

> **文書種別**: 仕様書。例外分類、キャンセル正規化、`RunResult.error` への失敗情報変換、error code catalog の正本である。`RunResult` 本体の正本は `RUNTIME_AND_IO_PORTS.md` とする。
> **対象モジュール**: `src/nyxpy/framework/core/macro/`, `src/nyxpy/framework/core/utils/`, `src/nyxpy/framework/core/logger/`, `src/nyxpy/framework/core/settings/`  
> **目的**: マクロ実行基盤の異常系、入力検証、協調キャンセル、実行結果を再設計し、ログ出力は `LOGGING_FRAMEWORK.md` の基盤へ接続する。  
> **関連ドキュメント**: `LOGGING_FRAMEWORK.md`, `spec/framework/archive/logging_design.md`  
> **既存ソース**: `decorators.py`, `exceptions.py`, `cancellation.py`, `executor.py`, `command.py`, `log_manager.py`, `global_settings.py`, `secrets_settings.py`, `notification_handler.py`, `log_pane.py`  
> **破壊的変更**: `MacroBase` / `Command` / `DefaultCommand` / constants / `MacroStopException` の import と lifecycle は維持する。Resource I/O、settings lookup、`DefaultCommand` 旧コンストラクタ、legacy loader、`Command.stop()` の即時例外送出依存はマクロ側移行を前提に破壊的変更を許容する。

## 1. 概要

### 1.1 目的

マクロ実行基盤で発生する入力不備、設定不備、デバイス不具合、リソース不備、処理中断を `FrameworkError` 階層と `RunResult` に正規化する。既存マクロ資産の import 互換を維持しつつ、GUI/CLI が例外文字列ではなく構造化された実行結果と表示イベントを扱える状態にする。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| Command | マクロがハードウェア操作、待機、キャプチャ、ログ、通知を行うための高レベル API |
| MacroBase | ユーザ定義マクロの抽象基底クラス。`initialize` / `run` / `finalize` ライフサイクルを持つ |
| MacroExecutor | 旧 GUI/CLI/テスト入口で使われる既存クラス。再設計後の公開 API、既存マクロ互換契約、移行 adapter のいずれにも含めず削除する |
| MacroRuntime | 新方式の実行中核。例外正規化、キャンセル、`RunResult` 生成は Runtime / Runner 側で扱う |
| MacroRegistry | 利用可能マクロを発見し、安定 ID とメタデータを保持するレジストリ |
| MacroFactory | `MacroDefinition` が所有する生成責務。実行ごとに新しい `MacroBase` インスタンスを返す |
| MacroRunner | `initialize -> run -> finalize` を実行し、例外・中断を `RunResult` に変換するコンポーネント |
| RunHandle | 非同期実行中のマクロに対する中断要求、完了待ち、結果取得を提供するハンドル |
| ExecutionContext | 1 回のマクロ実行に必要な `run_id`、`macro_id`、`RunLogContext`、Ports、中断トークン、options、`exec_args`、`metadata` を束ねる値オブジェクト。`Command` は保持しない。完全なフィールド一覧は `RUNTIME_AND_IO_PORTS.md` を正とする |
| Ports/Adapters | Runtime 中核がハードウェア・通知・ログ・GUI/CLI に直接依存しないための抽象境界と接続実装 |
| Legacy Compatibility Layer | 既存マクロと既存 GUI/CLI import を壊さない互換層。旧パス・旧クラス名・旧メソッドシグネチャを維持する |
| CancellationToken | `threading.Event` ベースのスレッドセーフな協調キャンセル機構 |
| MacroCancelled | マクロ実行スレッド内で中断を表す新しい例外。既存 `MacroStopException` との互換を持つ |
| MacroStopException | 既存マクロ・GUI・CLI が import している中断例外名。削除せず adapter として維持する |
| FrameworkError | フレームワークが利用者へ返す異常を表す基底例外。分類、コード、コンポーネント、詳細を保持する |
| DeviceError | シリアルデバイス、キャプチャデバイス、プロトコル操作の失敗を表す `FrameworkError` |
| ResourceError | 画像、設定ファイル、マクロリソース、ログファイルなどの読み書き失敗を表す `FrameworkError` |
| ConfigurationError | CLI/GUI 入力、マクロ引数、`GlobalSettings`、`SecretsSettings` の検証失敗を表す `FrameworkError` |
| RunResult | 1 回のマクロ実行の開始、終了、成功、失敗、中断、失敗情報、`run_id` を保持する値オブジェクト |
| run_id | 1 回のマクロ実行を識別する UUID 文字列。構造化ログ、GUI 表示イベント、`RunResult` を関連付ける |
| macro_id | 実行対象マクロを識別する文字列。原則としてパッケージ名または単一ファイル名を使う |
| component | ログまたは例外の発生元を示す安定した名前。例: `MacroRuntime`, `DefaultCommand`, `GlobalSettings` |
| 構造化ログ | `LOGGING_FRAMEWORK.md` で定義する `TechnicalLog`。異常・中断の詳細を検索・解析できる形で保存する |
| GUI 表示イベント | `LOGGING_FRAMEWORK.md` で定義する `UserEvent`。GUI のログペインやステータス表示に渡す短い表示用イベント |

### 1.3 背景・問題

現行コードでは中断例外が `MacroStopException` だけであり、入力不備、デバイス不具合、リソース不備、設定不備が `ValueError` や任意の例外として混在している。`DefaultCommand.wait()` は `time.sleep()` 中に `CancellationToken` を確認しないため、長い待機中の GUI cancel が即時に反映されない。

`MainWindow.cancel_macro()` と `closeEvent()` は GUI スレッドから `cmd.stop()` を呼び出しており、`cmd.stop()` が `MacroStopException` を送出するため GUI 操作側で例外が発生し得る。旧 `MacroExecutor.execute()` は失敗情報を返さず、`finalize(cmd)` へ成功・失敗・中断の outcome を渡せない。新設計では GUI/CLI が `MacroExecutor` を経由せず `RunResult` を扱い、outcome は `MacroBase.finalize(cmd)` の抽象契約には含めず、受け取り可能なマクロだけの opt-in 拡張にする。

`LogManager` は文字列メッセージと `component` のみを扱うため、同時実行や GUI 表示で `run_id` / `macro_id` とログを関連付けられない。ロギング基盤そのものの問題、backend 選定、sink 設計、GUI sink の例外処理と lock 方針は `LOGGING_FRAMEWORK.md` を正とする。`parse_define_args()` は `list[str]` 前提だが GUI 側から文字列が渡される経路があり、`GlobalSettings` / `SecretsSettings` は TOML 読み込み後の schema 検証を持たない。CLI 通知設定の入力元が `SecretsSettings` に統一されていない場合、GUI/CLI で Discord / Bluesky の挙動がずれる。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| 既存 `MacroStopException` import | `exceptions.py` に単独定義 | import パスと `except MacroStopException` の捕捉互換を維持 |
| マクロ実行結果 | `execute()` は `None`、失敗情報はログ文字列のみ | `RunResult` に `status`, `error`, `cancelled_reason`, `run_id`, `macro_id` を保持 |
| GUI cancel の例外 | GUI スレッドから `cmd.stop()` を呼ぶと例外が出る | GUI は中断要求のみを行い、例外送出はマクロ実行スレッドに限定 |
| `Command.wait()` 中断反映 | 待機秒数が終わるまで反映されない | `CancellationToken` 発火後 100 ms 未満で `MacroCancelled` を送出 |
| ログ相関 | `component` 文字列のみ | 構造化ログに `run_id`, `macro_id`, `component` を常時付与 |
| GUI 表示 | loguru の文字列を直接表示 | 永続ログと GUI 表示イベントを分離し、表示用文言を短く保つ |
| 設定・引数検証 | TOML パース後の型検証なし | schema に基づき実行前に `ConfigurationError` として検出 |

### 1.5 着手条件

- 現行コードを正とし、`spec/framework/archive/logging_design.md` は背景情報としてのみ扱う。
- 既存マクロの `from nyxpy.framework.core.macro.exceptions import MacroStopException` を変更不要にする。
- 既存マクロの `finalize(self, cmd)` を変更不要にする。
- `Command.log(*values, sep=" ", end="\n", level="...")` の既存呼び出しを変更不要にする。
- `Command.stop()` は協調キャンセル専用へ変更し、即時例外送出の互換引数は提供しない。
- GUI からの cancel は例外を直接送出せず、マクロ実行スレッド側の協調キャンセルで処理する。
- 実装前に `uv run pytest tests/unit/` のベースラインを確認する。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `spec/framework/rearchitecture/ERROR_CANCELLATION_LOGGING.md` | 新規 | 本仕様書 |
| `src/nyxpy/framework/core/macro/exceptions.py` | 変更 | `FrameworkError` 階層、`MacroCancelled`、`MacroStopException` adapter、失敗情報モデルを定義 |
| `src/nyxpy/framework/core/utils/cancellation.py` | 変更 | `CancellationToken` に理由、要求元、時刻、`throw_if_requested()`、即時待機 API を追加 |
| `src/nyxpy/framework/core/macro/decorators.py` | 変更 | `@check_interrupt` が `MacroCancelled` を送出し、既存 `MacroStopException` 捕捉互換を保つ |
| `src/nyxpy/framework/core/macro/command.py` | 変更 | `Command.wait()` の即時キャンセル対応、GUI 用中断要求 API、構造化ログ対応、デバイス/リソース例外の正規化 |
| `src/nyxpy/framework/core/macro/executor.py` | 削除 | GUI/CLI/テストの参照を Runtime へ移行した後に削除。戻り値 `None`、例外再送出、import 互換 shim は保証しない |
| `src/nyxpy/framework/core/macro/base.py` | 変更 | `finalize(cmd)` 抽象シグネチャを維持し、outcome 受け取りは opt-in 拡張として説明する |
| `src/nyxpy/framework/core/logger/log_manager.py` | 変更 | `LOGGING_FRAMEWORK.md` の `LoggerPort` / sink 基盤へ接続し、異常・中断イベントに `run_id` / `macro_id` / `component` を付与 |
| `src/nyxpy/framework/core/settings/global_settings.py` | 変更 | `GlobalSettings` schema、既定値、型検証、設定読み込み失敗時の `ConfigurationError` を実装 |
| `src/nyxpy/framework/core/settings/secrets_settings.py` | 変更 | `SecretsSettings` schema、秘匿値のログマスク、型検証、読み込み失敗時の `ConfigurationError` を実装 |
| `src/nyxpy/framework/core/utils/helper.py` | 変更 | `parse_define_args()` を `str` / `Iterable[str]` 対応にし、パース失敗を `ConfigurationError` に正規化 |
| `src/nyxpy/framework/core/api/notification_handler.py` | 変更 | 通知失敗を飲み込むだけでなく、秘匿情報を除いた `ResourceError` 相当の構造化ログに記録 |
| `src/nyxpy/gui/main_window.py` | 変更 | GUI cancel が例外を送出しない経路へ変更し、`RunResult` に基づき完了/中断/失敗を表示 |
| `src/nyxpy/gui/panes/log_pane.py` | 変更 | loguru 文字列 handler ではなく `LOGGING_FRAMEWORK.md` の `UserEvent` を購読 |
| `src/nyxpy/cli/run_cli.py` | 変更 | `RunResult` に基づく終了コード、エラーメッセージ、キャンセル表示へ変更。通知設定は `SecretsSettings` から取得 |
| `tests/unit/` | 新規/変更 | 例外階層、キャンセル、入力検証、構造化ログ、executor outcome の単体テスト |
| `tests/integration/` | 新規/変更 | GUI/CLI を含まないマクロ実行結果と `finalize` 互換の結合テスト |

## 3. 設計方針

### アーキテクチャ上の位置づけ

異常系と中断は `core/macro/` と `core/utils/` に集約し、GUI/CLI は `RunResult` と GUI 表示イベントを消費する上位レイヤーに留める。フレームワーク層から `nyxpy.gui` へ依存しない。

ログ管理の詳細は `LOGGING_FRAMEWORK.md` が担う。本書では異常・中断・設定検証がどの event を出すかだけを定義する。`NotificationHandler` は外部サービス失敗をユーザー操作の失敗にしないが、失敗情報を `TechnicalLog` に残す。

### 公開 API 方針

既存ユーザーマクロが import する `MacroBase` / `Command` / `DefaultCommand` / constants / `MacroStopException` と主要メソッド名は維持する。settings lookup は新方式へ移行し、旧 `static` / `cwd` fallback は維持しない。`MacroExecutor.execute()` は公開互換契約から外し、戻り値 `None` と失敗時の例外再送出は保証しない。`RunResult` は `MacroRuntime` / `MacroRunner` の新方式 API が返す。既存 `Command.log()` は呼び出し形式を維持し、`LOGGING_FRAMEWORK.md` の `LoggerPort` へ接続する。

`Command.stop()` はマクロ内から呼ばれる既存用途を考慮し、既定では中断要求の登録だけを行う。GUI/CLI の外部操作は `RunHandle.cancel()` のみを呼び、`Command` の cancel API や `CancellationToken` を直接操作しない。

### 後方互換性

例外・中断契約に対する破壊的変更は行わない。`MacroStopException` は削除せず、`MacroCancelled` との adapter 関係を定義する。推奨 API は `MacroCancelled` だが、既存の `except MacroStopException` は `MacroCancelled` を捕捉できる。

`MacroBase.finalize(self, cmd)` の抽象シグネチャは変更しない。これは唯一の抽象契約である。新方式で outcome を受け取りたいマクロだけが `SupportsFinalizeOutcome` Protocol 相当の opt-in 拡張として `finalize(self, cmd, outcome)` または `finalize(self, cmd, **kwargs)` を実装できる。Runner が `inspect.signature()` で `outcome` 引数または `**kwargs` の有無を判定し、受け取れるマクロにだけ `outcome` を渡す。

### レイヤー構成

| レイヤー | 対象 | 責務 | 禁止事項 |
|----------|------|------|----------|
| ユーティリティ | `CancellationToken` | スレッドセーフな中断状態、待機、理由保持 | GUI 型への依存 |
| マクロ実行 | `MacroRuntime`, `MacroRunner`, `Command`, `decorators` | 実行制御、例外正規化、キャンセル送出、outcome 生成 | GUI/CLI 固有表示 |
| ログ | `LoggerPort` / `LogManager` | 異常・中断 event を `LOGGING_FRAMEWORK.md` の sink 基盤へ渡す | 秘密情報の平文出力、sink 詳細の再定義 |
| 設定 | `GlobalSettings`, `SecretsSettings`, `parse_define_args` | schema 検証、入力正規化、`ConfigurationError` 生成 | マクロ固有ロジックへの依存 |
| 上位 UI | GUI, CLI | ユーザー入力、cancel 要求、`RunResult` 表示 | フレームワーク内部例外への過剰依存 |

### 性能要件

| 指標 | 目標値 |
|------|--------|
| `CancellationToken` 発火から `Command.wait()` 解除までの遅延 | 100 ms 以下 |
| `@check_interrupt` の通常時オーバーヘッド | 1 回あたり 100 µs 以下 |
| 異常・中断 event 発行 | 1 回あたり 1 ms 以下 |
| `RunResult` 生成 | 1 実行あたり 1 回、追加スレッドなし |
| GUI 表示イベント配信 | 詳細性能は `LOGGING_FRAMEWORK.md` の sink 性能要件に従う |

### 並行性・スレッド安全性

`CancellationToken` は `threading.Event` と `threading.Lock` を使い、中断要求の理由、要求元、時刻を一貫して読めるようにする。複数回 `request_cancel()` が呼ばれた場合、最初の理由を保持し、後続呼び出しは冪等に扱う。

ロギング sink の追加・削除・配信ロックは `LOGGING_FRAMEWORK.md` に従う。GUI 表示イベントはフレームワーク層ではただの callback として扱い、GUI 実装側が Qt Signal で GUI スレッドへ転送する。

`Command.wait()` は `CancellationToken.wait(timeout)` を使い、`time.sleep()` による単純待機を廃止する。デバイス I/O 中の強制割り込みは行わず、I/O 呼び出し前後の safe point でキャンセルを確認する。

## 4. 実装仕様

### 公開インターフェース

```python
from abc import ABC
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Mapping, Protocol

from nyxpy.framework.core.runtime import RunResult, RunStatus
from nyxpy.framework.core.macro.base import MacroBase
from nyxpy.framework.core.macro.command import Command


type FrameworkValue = str | int | float | bool | list[FrameworkValue] | dict[str, FrameworkValue] | None
type ErrorDetailValue = FrameworkValue
type MacroArgValue = FrameworkValue
type LogExtraValue = FrameworkValue


class ErrorKind(StrEnum):
    CANCELLED = "cancelled"
    DEVICE = "device"
    RESOURCE = "resource"
    CONFIGURATION = "configuration"
    VALIDATION = "validation"
    MACRO = "macro"
    INTERNAL = "internal"


class FrameworkError(Exception):
    def __init__(
        self,
        message: str,
        *,
        kind: ErrorKind,
        code: str,
        component: str,
        recoverable: bool = False,
        details: Mapping[str, ErrorDetailValue] | None = None,
        cause: BaseException | None = None,
    ) -> None: ...


class MacroStopException(FrameworkError):
    """既存 import 互換のため維持する中断例外 adapter。"""

    def __init__(self, *args: object, **kwargs: object) -> None: ...


class MacroCancelled(MacroStopException):
    """協調キャンセルによりマクロ実行スレッドで送出される例外。"""


class DeviceError(FrameworkError): ...
class ResourceError(FrameworkError): ...
class ConfigurationError(FrameworkError): ...
class MacroRuntimeError(FrameworkError): ...


@dataclass(frozen=True)
class ErrorInfo:
    kind: ErrorKind
    code: str
    message: str
    component: str
    exception_type: str
    recoverable: bool
    details: dict[str, ErrorDetailValue] = field(default_factory=dict)
    traceback: str | None = None

# RunStatus / RunResult の型定義は RUNTIME_AND_IO_PORTS.md を正とする。
```

```python
class CancellationToken:
    def stop_requested(self) -> bool: ...
    def request_stop(self) -> None: ...
    def request_cancel(self, reason: str = "", source: str = "") -> None: ...
    def clear(self) -> None: ...
    def reason(self) -> str | None: ...
    def source(self) -> str | None: ...
    def requested_at(self) -> datetime | None: ...
    def wait(self, timeout: float) -> bool: ...
    def throw_if_requested(self) -> None: ...
```

```python
class Command(ABC):
    def wait(self, wait: float) -> None: ...
    def stop(self) -> None: ...
    def log(
        self,
        *values: object,
        sep: str = " ",
        end: str = "\n",
        level: str = "INFO",
    ) -> None: ...


class CancellableCommand(Command):
    def log_event(
        self,
        *values: object,
        sep: str = " ",
        end: str = "\n",
        level: str = "INFO",
        event: str = "macro.message",
        extra: Mapping[str, LogExtraValue] | None = None,
        gui: bool = True,
    ) -> None: ...
```

```python
class RunContext: ...
class ExecutionContext: ...


class SupportsFinalizeOutcome(Protocol):
    def finalize(self, cmd: Command, outcome: RunResult) -> None: ...


class MacroRunner:
    def run(
        self,
        macro: MacroBase,
        cmd: Command,
        exec_args: Mapping[str, MacroArgValue],
        run_context: RunContext,
    ) -> RunResult: ...

class MacroRuntime:
    def run(self, context: ExecutionContext) -> RunResult: ...
```

ロギング公開インターフェースは `LOGGING_FRAMEWORK.md` の `LoggerPort`、`LogEvent`、`TechnicalLog`、`UserEvent`、`LogSink` を正とする。本書の Runtime / Runner は、失敗・中断・終了処理失敗を `LoggerPort` へ渡す event 名だけを保証する。

### 例外階層

| 例外クラス | 親 | `kind` | 発生条件 |
|------------|----|--------|----------|
| `FrameworkError` | `Exception` | 個別指定 | フレームワークが正規化して扱う全異常の基底 |
| `MacroStopException` | `FrameworkError` | `cancelled` | 既存互換用。既存コードが直接送出した場合も中断として扱う |
| `MacroCancelled` | `MacroStopException` | `cancelled` | `CancellationToken` 発火後の safe point、`@check_interrupt`、`Command.wait()` で送出 |
| `DeviceError` | `FrameworkError` | `device` | シリアル送信、キャプチャ取得、プロトコル変換、デバイス未接続の失敗 |
| `ResourceError` | `FrameworkError` | `resource` | 画像読み書き、マクロリソース、設定ファイル、ログファイル、通知先 I/O の失敗 |
| `ConfigurationError` | `FrameworkError` | `configuration` | CLI/GUI 入力、マクロ引数、`GlobalSettings`、`SecretsSettings` の schema 検証失敗 |
| `MacroRuntimeError` | `FrameworkError` | `macro` | マクロ実装由来の未分類例外を executor が正規化したもの |

`MacroStopException` は削除しない。`MacroStopException()` と `MacroStopException("stop")` は破壊しない。constructor は `__init__(*args, **kwargs)` で旧呼び出しを受け、`args[0]` がある場合は message として扱う。`kind` 未指定時は `ErrorKind.CANCELLED`、`code` 未指定時は `NYX_MACRO_CANCELLED`、`component` 未指定時は `MacroStopException`、`recoverable` 未指定時は `False` を既定値にする。kwargs に同名キーが渡された場合は kwargs を優先する。新規コードは `MacroCancelled` を送出するが、`MacroCancelled` が `MacroStopException` を継承するため、既存の `except MacroStopException` は中断を捕捉できる。既存マクロが `MacroStopException` を直接送出した場合、`MacroRunner` は `MacroCancelled` 相当の `RunResult(status=RunStatus.CANCELLED)` に正規化する。

### RunResult と失敗情報

`RunResult` は `MacroRunner` が生成し、`MacroRuntime.run()` が返す。本書は発生条件と `RunResult` への正規化を定義し、`ExecutionContext` のフィールドと Port close 失敗時の `cleanup_warnings` 追記規則は `RUNTIME_AND_IO_PORTS.md` を正とする。成功時は `RunStatus.SUCCESS`、協調キャンセル時は `RunStatus.CANCELLED`、それ以外の失敗は `RunStatus.FAILED` とする。`MacroExecutor.execute()` の戻り値 `None` と例外再送出は保証しない。

失敗時の `ErrorInfo` は以下を保持する。

| フィールド | 内容 |
|------------|------|
| `kind` | `ErrorKind`。GUI/CLI の表示分類と終了コード判定に使う |
| `code` | 安定したエラーコード。例: `NYX_DEVICE_CAPTURE_FAILED` |
| `message` | ユーザーへ表示可能な短いメッセージ。秘密情報を含めない |
| `component` | 発生元。例: `DefaultCommand.capture` |
| `exception_type` | 元例外のクラス名 |
| `recoverable` | リトライ可能性の目安 |
| `details` | JSON 化できる詳細情報。パスやキー名はよいが secret 値は入れない |
| `traceback` | DEBUG ログ用。GUI 表示には出さない |

#### Error code catalog

error code の体系と発生元は本表を正とする。設定仕様、Runtime 仕様、GUI/CLI 仕様は本表の code を参照し、別名を定義しない。

| code | kind | 発生元 | 発生条件 |
|------|------|--------|----------|
| `NYX_MACRO_CANCELLED` | `cancelled` | `CancellationToken`, `MacroRunner` | ユーザー操作またはマクロ内部操作で中断要求が確定した |
| `NYX_INVALID_WAIT_SECONDS` | `configuration` | `Command.wait` | `seconds < 0` が指定された |
| `NYX_DEFINE_PARSE_FAILED` | `configuration` | `parse_define_args` | CLI/GUI の define 入力を TOML として解釈できない |
| `NYX_DEFINE_INVALID` | `configuration` | `parse_define_args` | 空 key、key のみ、重複による型衝突など define 入力が不正 |
| `NYX_MACRO_ARGS_INVALID` | `configuration` | `MacroRunner` / args schema | マクロ引数が schema に一致しない |
| `NYX_SETTINGS_PARSE_FAILED` | `configuration` | `GlobalSettings`, `SecretsSettings`, `MacroSettingsResolver` | TOML 破損または読み込み不能 |
| `NYX_SETTINGS_SCHEMA_INVALID` | `configuration` | `GlobalSettings`, `SecretsSettings` | 設定値が schema に一致しない |
| `NYX_SETTINGS_PATH_INVALID` | `configuration` | `MacroSettingsResolver` | 明示 settings path が空、絶対パス、root 外参照、root 外シンボリックリンクである |
| `NYX_DEVICE_SERIAL_FAILED` | `device` | `ControllerOutputPort` | シリアル送信、接続、プロトコル変換に失敗した |
| `NYX_DEVICE_CAPTURE_FAILED` | `device` | `FrameSourcePort` | フレーム取得、初期化、切断検出に失敗した |
| `NYX_FRAME_NOT_READY` | `device` | `FrameSourcePort.await_ready` | timeout 内に有効フレームが取得できない |
| `NYX_DEVICE_DETECTION_TIMEOUT` | `device` | `MacroRuntimeBuilder` | serial/capture 検出が timeout 内に完了しない |
| `NYX_DEVICE_NOT_FOUND` | `device` | `MacroRuntimeBuilder` | 指定された serial/capture device が検出結果に存在しない |
| `NYX_DUMMY_DEVICE_NOT_ALLOWED` | `configuration` | `MacroRuntimeBuilder` | `allow_dummy=False` で dummy device を選択しようとした |
| `NYX_RUNTIME_BUSY` | `configuration` | `MacroRuntime`, `RunHandle` | 同一 Runtime の二重実行、または実行状態 lock の timeout |
| `NYX_RESOURCE_PATH_INVALID` | `resource` | `ResourceStorePort`, `RunArtifactStore` | path guard で root 外参照または不正 path を検出した |
| `NYX_RESOURCE_READ_FAILED` | `resource` | `ResourceStorePort` | assets 読み込みに失敗した |
| `NYX_RESOURCE_WRITE_FAILED` | `resource` | `RunArtifactStore` | outputs 書き込みまたは atomic replace に失敗した |
| `NYX_NOTIFICATION_FAILED` | `resource` | `NotificationPort` | Discord / Bluesky 等の通知送信に失敗した |
| `NYX_MACRO_FAILED` | `macro` | `MacroRunner` | マクロの `initialize` / `run` / `finalize` が未分類例外を送出した |

### CancellationToken と協調キャンセル

`CancellationToken.request_cancel()` は GUI/CLI/内部処理から安全に呼べる中断要求 API であり、例外を送出しない。`request_stop()` は既存互換の別名として残し、内部では `request_cancel(reason="stop requested", source="legacy")` を呼ぶ。

`CancellationToken.throw_if_requested()` はマクロ実行スレッドの safe point で呼び、発火済みなら `MacroCancelled` を送出する。`@check_interrupt` は `self.ct.throw_if_requested()` を使う。

`Command.wait(seconds)` は以下の手順で動作する。

1. `seconds < 0` は `ConfigurationError(code="NYX_INVALID_WAIT_SECONDS")` とする。
2. 待機前に `ct.throw_if_requested()` を呼ぶ。
3. `ct.wait(seconds)` を呼び、中断要求が来たら 100 ms 未満で `MacroCancelled` を送出する。
4. 待機後に再度 `ct.throw_if_requested()` を呼ぶ。

キャンセル API は 3 層に分ける。

| 層 | 呼び出し元 | API | 例外送出 |
|----|------------|-----|----------|
| 外部操作 | GUI / CLI | `RunHandle.cancel()` | 送出しない |
| Runtime 内部 | `RunHandle` / Runtime | `CancellationToken.request_cancel(reason, source)` | 送出しない |
| マクロ内部 | マクロコード | `Command.stop()` | 送出しない |

`Command.stop()` はマクロ内部から停止要求を登録する API とし、`cancellation_token.request_cancel(reason="stop requested", source="macro")` のみを行う。実際の脱出は `Command.wait()`、`@check_interrupt`、`CancellationToken.throw_if_requested()` などの safe point で `MacroCancelled` を送出して行う。現行 `DefaultCommand.stop()` の即時例外送出とは意味論が変わるが、即時例外送出の互換引数や escape hatch は提供しない。

### finalize への outcome 伝達

`MacroBase.finalize(cmd)` を唯一の抽象契約として維持する。outcome 伝達は `SupportsFinalizeOutcome` Protocol または signature inspection による opt-in 拡張であり、既存マクロへ `finalize(cmd, outcome)` 実装を要求しない。

`MacroRunner` は `initialize`、`run`、例外正規化、暫定 `RunResult` 生成の後に必ず `finalize` を呼ぶ。`finalize` の呼び出しは以下の互換ルールに従う。

| マクロ側シグネチャ | Runner の呼び出し |
|--------------------|------------------|
| `finalize(self, cmd)` | `finalize(cmd)` |
| `finalize(self, cmd, outcome)` | `finalize(cmd, outcome)` |
| `finalize(self, cmd, *, outcome=None)` | `finalize(cmd, outcome=result)` |
| `finalize(self, cmd, **kwargs)` | `finalize(cmd, outcome=result)` |

`finalize` の signature inspection は Registry reload または `MacroDefinition` 生成時に 1 回だけ行い、`MacroDefinition.finalize_accepts_outcome: bool` として保持する。`MacroRunner` は実行ごとに `inspect.signature()` を呼ばず、保持済みフラグに従って呼び出し形式を選ぶ。

`finalize` 自体が例外を送出した場合、元の `run` 失敗情報を失わせない。実行本体が成功していた場合は `finalize` 失敗を `RunStatus.FAILED` とする。実行本体がすでに失敗または中断していた場合は、`RunResult.error.details["finalize_error"]` に要約を追加し、構造化ログへ `event="macro.finalize_failed"` を出す。

この処理は Runtime / Runner で実装し、GUI/CLI は `RunResult` を参照する。

### 入力検証

#### macro args schema

マクロは任意で `args_schema` を定義できる。未定義マクロは既存互換のため schema 検証をスキップする。schema 定義時も未知キー拒否は opt-in とし、既存 `settings.toml` や `-D` 引数を壊さない。

```python
@dataclass(frozen=True)
class ArgSpec:
    type: type | tuple[type, ...]
    required: bool = False
    default: MacroArgValue = None
    choices: tuple[MacroArgValue, ...] | None = None
    description: str = ""


@dataclass(frozen=True)
class MacroArgsSchema:
    fields: dict[str, ArgSpec]
    strict: bool = False
```

検証順序は manifest または class metadata settings path から読み込んだ settings と、CLI/GUI `exec_args` のマージ後とする。`exec_args` が優先される現行仕様は維持する。旧 `static/<macro_id>/settings.toml` は探索しない。検証失敗は `ConfigurationError(code="NYX_MACRO_ARGS_INVALID", component="MacroRuntime")` に正規化する。

#### GlobalSettings / SecretsSettings schema

`GlobalSettings` は既定値と型を schema として定義する。現行の `capture_device`, `serial_device`, `serial_baud`, `serial_protocol` は維持する。

| パラメータ | 型 | デフォルト | 説明 |
|------------|-----|-----------|------|
| `capture_device` | `str` | `""` | 利用するキャプチャデバイス名 |
| `serial_device` | `str` | `""` | 利用するシリアルデバイス名 |
| `serial_baud` | `int` | `9600` | シリアル通信速度 |
| `serial_protocol` | `str` | `"CH552"` | 利用するシリアルプロトコル |
| `logging.file_level` | `str` | `"DEBUG"` | ファイルログの最低レベル |
| `logging.console_level` | `str` | `"INFO"` | コンソールログの最低レベル |
| `logging.gui_level` | `str` | `"INFO"` | GUI 表示イベントの最低レベル |

`SecretsSettings` は通知設定を schema として定義する。CLI/GUI/Runtime builder は Discord / Bluesky 通知設定を `SecretsSettings` からのみ読み、`GlobalSettings` や CLI 独自構造に secret 値を複製しない。secret 値は `LogManager` に渡す前にマスクする。

| パラメータ | 型 | デフォルト | 説明 |
|------------|-----|-----------|------|
| `notification.discord.enabled` | `bool` | `False` | Discord 通知の有効化 |
| `notification.discord.webhook_url` | `str` | `""` | Discord webhook URL。ログではマスクする |
| `notification.bluesky.enabled` | `bool` | `False` | Bluesky 通知の有効化 |
| `notification.bluesky.identifier` | `str` | `""` | Bluesky identifier。ログでは一部マスクする |
| `notification.bluesky.password` | `str` | `""` | Bluesky password。ログでは全体をマスクする |

既存ファイルに schema 外キーがある場合は保持する。型不一致は `ConfigurationError` とし、自動変換は `int` など安全な範囲に限る。TOML 破損時は元ファイルを上書きせず、エラーを返す。

#### parse_define_args

`parse_define_args()` は既存 import パスと関数名を維持し、入力型を広げる。

| 入力 | 扱い |
|------|------|
| `None` | `{}` |
| `list[str]` / `tuple[str, ...]` | 各要素を TOML 行として結合 |
| `str` | GUI 入力として受け取り、改行または空白区切りの `key=value` 群を TOML へ変換 |
| TOML パース失敗 | `ConfigurationError(code="NYX_DEFINE_PARSE_FAILED")` |
| `key` のみ、空 key、重複で型衝突 | `ConfigurationError(code="NYX_DEFINE_INVALID")` |

値の型は TOML に従う。文字列を渡す場合は `"name=\"abc\" count=3"` のような表現を許容するが、曖昧なクォートや秘密値はログへ出さない。

### ロギング連携

ロギングフレームワーク選定、event catalog、`LoggerPort`、`LogEvent`、`LogSink`、`UserEvent` と `TechnicalLog` の分離、実行単位コンテキスト、テスト用 sink、ログファイル配置、rotation、保持期間は `LOGGING_FRAMEWORK.md` を正とする。本書は異常系・中断系から event を発行するタイミングだけを定義する。

| タイミング | 発行 event |
|------------|------------|
| `RunHandle.cancel()` または `Command.stop()` が中断要求を登録した | `macro.cancel_requested` |
| `MacroRunner` が `RunStatus.CANCELLED` を確定した | `macro.cancelled` |
| `MacroRunner` が `RunStatus.FAILED` を確定した | `macro.failed` |
| `finalize` が例外を送出した | `macro.finalize_failed` |
| settings / args schema 検証で `ConfigurationError` を生成した | `configuration.invalid` |
| 通知送信が失敗した | `notification.failed` |

### エラーハンドリング

| 発生箇所 | 正規化先 | 備考 |
|----------|----------|------|
| `serial_device.send()` | `DeviceError` | 送信データ本体はログに出さない |
| `capture_device.get_frame()` が `None` | `DeviceError` | 現行の `None` 返却を失敗として扱う |
| `StaticResourceIO` の読み書き | `ResourceError` | パスは相対化して記録 |
| `load_macro_settings()` の TOML 破損 | `ConfigurationError` | ファイルを上書きしない |
| `parse_define_args()` の TOML 破損 | `ConfigurationError` | 入力全文は INFO 以上のログに出さない |
| `GlobalSettings` / `SecretsSettings` 型不一致 | `ConfigurationError` | secret 値はマスク |
| マクロ `initialize` / `run` の任意例外 | `MacroRuntimeError` | 元例外名と traceback を DEBUG ログに保存 |
| `NotificationHandler.publish()` の通知失敗 | `ResourceError` 相当の構造化ログ | マクロ実行は継続 |
| GUI log sink の例外 | `LOGGING_FRAMEWORK.md` の sink 例外隔離 | 他 sink への配信とマクロ実行は継続 |
| CLI 通知設定ソース不一致 | `ConfigurationError` | Runtime builder が `SecretsSettings` 以外から secret 値を受け取った場合 |

### シングルトン管理

`LogManager` は現行どおり `log_manager` グローバルインスタンスを維持する。sink と GUI 表示イベントの reset 方針は `LOGGING_FRAMEWORK.md` を正とする。新しい `RunResult` や `CancellationToken` は実行ごとのオブジェクトであり、`singletons.py` への登録は不要である。

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| ユニット | `test_macro_cancelled_is_macro_stop_exception_compatible` | `MacroCancelled` が既存 `except MacroStopException` で捕捉できる |
| ユニット | `test_macro_stop_exception_constructor_keeps_legacy_calls` | `MacroStopException()` と `MacroStopException("stop")` が成功し、既定 `kind` / `code` / `component` を持つ |
| ユニット | `test_framework_error_contains_kind_code_component` | `FrameworkError` 階層が `kind`, `code`, `component`, `details` を保持する |
| ユニット | `test_cancellation_token_request_cancel_is_idempotent` | 複数回 cancel しても最初の理由と要求元を保持する |
| ユニット | `test_command_wait_returns_immediately_on_cancel` | 長い `wait()` 中に token 発火後 100 ms 以内で `MacroCancelled` になる |
| ユニット | `test_run_handle_cancel_does_not_raise` | 外部操作 API の `RunHandle.cancel()` が呼び出し元スレッドで例外を送出しない |
| ユニット | `test_command_stop_requests_cancel_without_raising` | マクロ内部の `Command.stop()` は停止要求だけを登録し、即時例外を送出しない |
| ユニット | `test_command_stop_rejects_raise_immediately_argument` | `Command.stop(raise_immediately=True)` を互換引数として受け付けない |
| ユニット | `test_runtime_returns_run_result_on_success` | 成功時 `RunResult(status="success", error=None)` を返す |
| ユニット | `test_macro_executor_removed` | `MacroExecutor.execute()` の `None` 戻り値や例外再送出を互換契約として保証しない |
| ユニット | `test_runtime_returns_run_result_on_framework_error` | `ConfigurationError` 等を `RunResult.error` に格納する |
| ユニット | `test_runtime_returns_cancelled_for_legacy_macro_stop_exception` | 既存 `MacroStopException` 送出を `status="cancelled"` に正規化する |
| ユニット | `test_finalize_receives_outcome_when_supported` | `finalize(cmd, outcome)` 形式のマクロへ `RunResult` を渡す |
| ユニット | `test_finalize_cmd_only_remains_supported` | 既存 `finalize(cmd)` 形式が変更なしで呼ばれる |
| ユニット | `test_parse_define_args_accepts_list_and_string` | CLI list 入力と GUI string 入力の両方を辞書へ変換する |
| ユニット | `test_parse_define_args_raises_configuration_error` | 不正 TOML と不正 key を `ConfigurationError` にする |
| ユニット | `test_global_settings_schema_validation` | `GlobalSettings` の型不一致と既定値を検証する |
| ユニット | `test_secrets_settings_masks_secret_values_in_logs` | secret 値が構造化ログに平文で出ない |
| ユニット | `test_error_events_use_logger_port` | 異常・中断 event が `LOGGING_FRAMEWORK.md` の `LoggerPort` へ渡る |
| ユニット | `test_cli_notification_settings_source_is_secrets_settings` | CLI 通知設定が `SecretsSettings` に統一されていることを検証する |
| 結合 | `test_executor_cancel_flow_with_dummy_macro` | Dummy マクロ実行中に token を発火し、`finalize` と `RunResult(cancelled)` を確認する |
| 結合 | `test_cli_uses_run_result_exit_code` | CLI が `RunResult` に基づき成功 0、失敗 非 0、中断 130 を返す |
| GUI | `test_main_window_cancel_does_not_raise_in_gui_thread` | `cancel_macro()` が例外を送出せず、worker が中断結果を通知する |
| ハードウェア | `test_device_error_on_serial_disconnect` | `@pytest.mark.realdevice`。シリアル切断時に `DeviceError` へ正規化する |
| ハードウェア | `test_device_error_on_capture_disconnect` | `@pytest.mark.realdevice`。キャプチャ取得失敗時に `DeviceError` へ正規化する |
| 性能 | `test_command_wait_cancel_latency_perf` | cancel latency が 100 ms 以下である |
| 性能 | `test_structured_logging_overhead_perf` | 構造化ログ追加後の 1 件あたりオーバーヘッドが 1 ms 以下である |

## 6. 実装チェックリスト

- [ ] `FrameworkError` 階層、`ErrorKind`、`ErrorInfo` のシグネチャ確定
- [ ] `MacroStopException` import 互換、constructor 互換、`MacroCancelled` adapter 方針の実装
- [ ] `CancellationToken` の理由・要求元・時刻・即時 wait・`throw_if_requested()` 実装
- [ ] `@check_interrupt` の `MacroCancelled` 送出対応
- [ ] `Command.wait()` の即時キャンセル対応
- [ ] GUI/CLI cancel が例外を送出しない中断要求 API へ移行
- [ ] `MacroExecutor` を削除対象とし、Runtime / Runner での `RunResult` 生成・例外正規化・`finalize` outcome 伝達を固定
- [ ] 既存 `finalize(cmd)` マクロの互換テスト作成
- [ ] `macro args schema` と検証処理の実装
- [ ] `GlobalSettings` / `SecretsSettings` schema 検証と secret マスク実装
- [ ] `parse_define_args()` の `str` / `Iterable[str]` 対応と `ConfigurationError` 正規化
- [ ] 異常・中断イベントを `LOGGING_FRAMEWORK.md` の `LoggerPort` へ接続
- [ ] `LogPane` への表示経路は `LOGGING_FRAMEWORK.md` の `UserEvent` 購読へ委譲
- [ ] `NotificationHandler` の通知失敗ログを構造化
- [ ] CLI 通知設定ソースを `SecretsSettings` に統一
- [ ] ユニットテスト作成・パス
- [ ] 結合テスト作成・パス
- [ ] GUI テスト作成・パス
- [ ] ハードウェアテストに `@pytest.mark.realdevice` を指定
- [ ] パフォーマンステスト作成・パス
- [ ] `uv run ruff check .` がパス
- [ ] `uv run pytest tests/unit/` がパス
- [ ] 公開 API のドキュメントコメント更新
