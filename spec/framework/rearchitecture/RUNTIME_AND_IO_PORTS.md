# Runtime と I/O Ports 再設計仕様書

> **対象モジュール**: `src\nyxpy\framework\core\runtime\`, `src\nyxpy\framework\core\io\`, `src\nyxpy\framework\core\macro\`, `src\nyxpy\framework\core\hardware\`
> **目的**: マクロ実行組み立てとデバイス入出力を Runtime と Port に分離し、既存マクロの import 互換を維持したまま GUI/CLI の重複構築と I/O 境界の不具合を解消する。
> **関連ドキュメント**: `.github\skills\framework-spec-writing\template.md`
> **既存ソース**: `src\nyxpy\framework\core\macro\command.py`, `src\nyxpy\framework\core\hardware\serial_comm.py`, `src\nyxpy\framework\core\hardware\capture.py`, `src\nyxpy\framework\core\hardware\resource.py`, `src\nyxpy\framework\core\api\notification_handler.py`, `src\nyxpy\cli\run_cli.py`, `src\nyxpy\gui\main_window.py`
> **破壊的変更**: なし。既存マクロが参照する import path と `Command` API は維持する。

## 1. 概要

### 1.1 目的

`MacroRuntime` をマクロ実行の唯一の組み立て点とし、シリアル送信・フレーム取得・静的リソース・通知・ログを Port インターフェースで隔離する。既存マクロ資産が利用する `nyxpy.framework.core.macro.command.Command` / `DefaultCommand` の import path とメソッド互換を維持し、GUI/CLI は Runtime を呼び出す薄い入口へ移行する。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| Command | マクロがコントローラー操作、待機、キャプチャ、画像入出力、通知、ログを行うための高レベル API |
| DefaultCommand | 既存 import path を維持する `Command` 実装。移行後は `CommandFacade` の互換ラッパーとして Ports を利用する |
| CommandFacade | `Command` API を Ports へ委譲する実装。プロトコル変換やデバイス具象実装を直接持たない |
| MacroBase | ユーザ定義マクロの抽象基底クラス。`initialize` / `run` / `finalize` ライフサイクルを持つ |
| MacroExecutor | 旧 GUI/CLI/テスト入口で使われる既存クラス。残す場合は `reload_macros()` / `set_active_macro()` / `execute()` から `MacroRuntime` へ委譲するだけの一時 adapter とし、既存ユーザーマクロが直接依存していない限り公開互換契約から外す |
| MacroRuntime | 実行要求、`ExecutionContext` 構築、`Command` 生成、`MacroRegistry` / `MacroFactory` / `MacroRunner` 呼び出し、`RunResult` 確定、リソース解放を統括するフレームワーク層の実行基盤 |
| MacroRegistry | 利用可能マクロを発見し、安定 ID とメタデータを保持するレジストリ。実行インスタンスは保持しない |
| MacroFactory | `MacroRegistry` の定義情報から実行ごとに新しい `MacroBase` インスタンスを生成するファクトリ |
| MacroRunner | `initialize -> run -> finalize` のライフサイクルを実行し、例外・中断・結果を `RunResult` に変換するコンポーネント |
| ExecutionContext | 1 回のマクロ実行に必要な引数、CancellationToken、Ports、設定値、実行 ID を束ねる不変データ |
| RunHandle | 非同期実行中のマクロに対するキャンセル、完了待ち、結果取得のハンドル |
| RunResult | マクロ実行の終了状態、`datetime` の開始・終了時刻、`ErrorInfo | None`、`cleanup_warnings` を表す値オブジェクト |
| ControllerOutputPort | ボタン、スティック、キーボード入力をコントローラー出力へ送る基本 Port。touch と sleep は optional capability に分離する |
| FrameSourcePort | キャプチャデバイスまたはテスト用フレームソースから最新フレームを取得する Port |
| ResourceStorePort | static 配下の画像保存・読み込みを行い、パス検証と書き込み結果検証を担当する Port。settings TOML 解決は担当しない |
| MacroSettingsResolver | `static/<macro_name>/settings.toml` 互換と manifest settings path を解決する専用コンポーネント |
| NotificationPort | Discord / Bluesky などの外部通知へ発行する Port |
| LoggerPort | loguru ベースの `LogManager` またはテスト用ロガーへログを出力する Port |
| Ports/Adapters | Port は Runtime 中核から見た I/O 抽象、Adapter は現行 Serial/Capture/Resource/Notification/Logger 実装へ接続する実装 |
| Legacy Compatibility Layer | 既存ユーザーマクロが import する `MacroBase` / `Command` / `DefaultCommand` / constants / `MacroStopException` と settings lookup を維持する互換層。`MacroExecutor` は必要な場合だけ旧入口から新 Runtime / Port へ委譲する |
| CancellationToken | スレッドセーフなマクロ中断メカニズム |
| dummy fallback | 実デバイス未選択時に暗黙でダミーデバイスを有効化する現行挙動 |
| frame readiness | `AsyncCaptureDevice` 初期化後、最初の有効フレームが取得可能になった状態 |

### 1.3 背景・問題

現行実装では `DefaultCommand` が `SerialCommInterface`、`CaptureDeviceInterface`、`StaticResourceIO`、`NotificationHandler`、`SerialProtocolInterface` を直接保持し、GUI と CLI が個別に同じ依存組み立てを行っている。そのため実行前提、エラー分類、リソース解放のルールが入口ごとに分散している。

解消対象の現行問題は次の通りである。

| 項目 | 現状 | 問題 |
|------|------|------|
| dummy fallback | `SerialManager.get_active_device()` と `CaptureManager.get_active_device()` が未選択時にダミーデバイスを自動選択する | 設定誤りや実機未接続を成功扱いし、CLI/GUI 上で失敗原因が見えない |
| async detection race | `auto_register_devices()` がバックグラウンド検出を開始し、CLI は直後に `list_devices()` を参照する | 検出完了前に「デバイスなし」と判定する競合が起きる |
| frame readiness | `AsyncCaptureDevice.initialize()` はスレッド開始直後に戻り、`get_frame()` は初回フレーム未取得時に例外を投げる | 実行直後の `cmd.capture()` がデバイス初期化成功後でも失敗する |
| resource path escape | `StaticResourceIO.save_image()` / `load_image()` は `root / filename` 後の解決済みパス検証を行わない | `..` や絶対パスで static root 外へアクセスできる余地がある |
| `cv2.imwrite` return | `StaticResourceIO.save_image()` が `cv2.imwrite()` の戻り値を検証しない | 書き込み失敗が成功扱いになり、後続の load で原因が遅れて表面化する |
| GUI/CLI 重複構築 | `run_cli.py` と `main_window.py` が個別に `DefaultCommand` を構築する | 設定反映、通知、キャンセル、リソース解放の仕様が二重管理になる |
| cancellation latency | `DefaultCommand.wait()` が `time.sleep()` を直接呼ぶ | 長い待機中にキャンセル要求へ即応できない |
| logging boundary | `DefaultCommand.log()` がグローバル `log_manager` に直接依存する | テスト時のログ検証と GUI/CLI ごとのログ出力差し替えが難しい |
| CLI notification settings | CLI と GUI で通知設定の参照経路が分かれ得る | Discord / Bluesky の有効化と secret 値を `SecretsSettings` に統一しないと、Runtime 移行後に通知挙動が入口でずれる |

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| GUI/CLI の Command 構築箇所 | `run_cli.py` と `main_window.py` の 2 箇所 | `MacroRuntime` 経由の 1 箇所 |
| 暗黙 dummy fallback | 未選択時に自動有効化 | 本番実行では禁止。`allow_dummy=True` の明示時のみ使用 |
| デバイス検出完了待ち | 呼び出し側で保証なし | `detect(timeout_sec)` が完了、タイムアウト、失敗を明示的に返す |
| 初回 frame readiness | `get_frame()` 呼び出し時に偶発的に判明 | Runtime 起動前に `FrameSourcePort.await_ready()` で検証 |
| static root 外アクセス | 保存・読み込み先の最終パス検証なし | `resolve_resource_path()` で root 配下のみ許可 |
| 画像書き込み失敗検出 | `cv2.imwrite()` 失敗を無視 | `ResourceWriteError` を即時送出 |
| 既存マクロ import 互換 | `Command` / `DefaultCommand` を直接 import 可能 | 同じ import path を維持 |
| キャンセル応答 | `wait()` 指定秒数まで遅延 | 50 ms 以下の周期で `CancellationToken` を確認 |

### 1.5 着手条件

- 現行 `Command` 抽象メソッドのメソッド名、引数、戻り値互換を維持する。
- `nyxpy.framework.core.macro.command.DefaultCommand` の import path を維持する。
- 既存の `MacroBase` ライフサイクル、`Command` / `DefaultCommand`、constants、`MacroStopException`、settings lookup を維持する。
- GUI/CLI の実行組み立ては変更してよいが、GUI/CLI がマクロへ渡す `cmd` は `Command` として振る舞う。
- 既存テスト (`uv run pytest tests/unit/`) が移行前後でパスすること。
- 実機依存テストは `@pytest.mark.realdevice` を付け、通常の単体テストから分離する。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `spec\framework\rearchitecture\RUNTIME_AND_IO_PORTS.md` | 新規 | 本仕様書 |
| `src\nyxpy\framework\core\runtime\__init__.py` | 新規 | Runtime 公開 API の再 export |
| `src\nyxpy\framework\core\runtime\context.py` | 新規 | `ExecutionContext`, `RuntimeOptions` を定義 |
| `src\nyxpy\framework\core\runtime\result.py` | 新規 | `RunStatus`, `RunResult` を定義 |
| `src\nyxpy\framework\core\runtime\handle.py` | 新規 | `RunHandle` とスレッド実装を定義 |
| `src\nyxpy\framework\core\runtime\runtime.py` | 新規 | `MacroRuntime` の同期・非同期実行を実装 |
| `src\nyxpy\framework\core\runtime\builder.py` | 新規 | GUI/CLI 設定から Runtime と Ports を組み立てる。通知設定は `SecretsSettings` から読む |
| `src\nyxpy\framework\core\io\__init__.py` | 新規 | Port インターフェースと標準実装の再 export |
| `src\nyxpy\framework\core\io\ports.py` | 新規 | `ControllerOutputPort`, `FrameSourcePort`, `ResourceStorePort`, `NotificationPort`, `LoggerPort` を定義 |
| `src\nyxpy\framework\core\io\controller.py` | 新規 | `SerialControllerOutputPort`, `DummyControllerOutputPort` を実装 |
| `src\nyxpy\framework\core\io\frame_source.py` | 新規 | `CaptureFrameSourcePort`, `DummyFrameSourcePort`, frame readiness を実装 |
| `src\nyxpy\framework\core\io\resource_store.py` | 新規 | 安全な static root 解決と画像 I/O を実装。settings TOML 解決は扱わない |
| `src\nyxpy\framework\core\macro\settings_resolver.py` | 新規 | `MacroSettingsResolver` を実装し、manifest / legacy settings TOML を解決 |
| `src\nyxpy\framework\core\io\notification.py` | 新規 | `NotificationHandler` の Port adapter を実装 |
| `src\nyxpy\framework\core\io\logger.py` | 新規 | `LogManager` の Port adapter を実装 |
| `src\nyxpy\framework\core\macro\command.py` | 変更 | `CommandFacade` を追加し、`DefaultCommand` を互換ラッパーとして Ports 利用へ移行 |
| `src\nyxpy\framework\core\hardware\serial_comm.py` | 変更 | 既存 API は維持し、Runtime 経路では暗黙 dummy fallback を使わない。明示的な検出完了待ち API を追加 |
| `src\nyxpy\framework\core\hardware\capture.py` | 変更 | 既存 API は維持し、Runtime 経路で使う検出完了待ち、frame readiness、release join timeout を追加 |
| `src\nyxpy\framework\core\hardware\resource.py` | 変更 | `StaticResourceIO` を `ResourceStorePort` adapter へ移行、パス検証と `cv2.imwrite` 戻り値検証を追加 |
| `src\nyxpy\framework\core\api\notification_handler.py` | 変更 | `NotificationPort` adapter から使える失敗ログ方針を整理 |
| `src\nyxpy\framework\core\singletons.py` | 変更 | Runtime/Port 関連シングルトンが必要な場合のみ登録し、`reset_for_testing()` で初期化 |
| `src\nyxpy\cli\run_cli.py` | 変更 | CLI 固有の組み立てを `MacroRuntimeBuilder` 呼び出しへ置換 |
| `src\nyxpy\gui\main_window.py` | 変更 | `DefaultCommand` 直接構築と `WorkerThread` の実行責務を Runtime 利用へ移行 |
| `src\nyxpy\gui\models\virtual_controller_model.py` | 変更 | 直接 `SerialCommInterface` 送信から `ControllerOutputPort` 利用へ移行 |
| `tests\unit\framework\runtime\test_runtime.py` | 新規 | Runtime ライフサイクル、RunResult、キャンセルを検証 |
| `tests\unit\framework\io\test_ports.py` | 新規 | 各 Port の正常系・異常系を検証 |
| `tests\integration\test_runtime_cli.py` | 新規 | CLI が Runtime 経由で実行されることを検証 |
| `tests\gui\test_runtime_main_window.py` | 新規 | GUI の開始、キャンセル、終了表示を検証 |
| `tests\hardware\test_runtime_devices.py` | 新規 | 実 serial/capture device の検出と入出力を `@pytest.mark.realdevice` で検証 |

## 3. 設計方針

### アーキテクチャ上の位置づけ

Runtime は `MacroRegistry`、`MacroFactory`、`MacroRunner` と I/O Ports の組み立て点に置く。`MacroRegistry` の正配置は `src\nyxpy\framework\core\macro\registry.py` である。GUI/CLI は Runtime へ実行要求を渡し、Runtime は `CommandFacade(context)` を作成して `MacroRunner` にライフサイクル実行を委譲する。旧 `MacroExecutor` は必要な場合だけ同じ Runtime を呼ぶ一時 adapter として残し、不要なら GUI/CLI を Runtime へ直接移行して廃止する。

```text
nyxpy.gui / nyxpy.cli
    ↓
MacroRuntimeBuilder
    ↓
MacroRuntime ── RunHandle / RunResult
    ↓
MacroRegistry / MacroFactory / MacroRunner
    ↓
CommandFacade implements Command
    ↓
ControllerOutputPort / FrameSourcePort / ResourceStorePort / NotificationPort / LoggerPort
    ↓
SerialComm / AsyncCaptureDevice / static resources / NotificationHandler / LogManager
```

依存方向は次の制約を守る。

- `nyxpy.framework.core.runtime` は `nyxpy.gui` と `nyxpy.cli` に依存しない。
- `nyxpy.framework.core.io` は GUI イベントや Qt 型に依存しない。
- `nyxpy.framework.core.macro.command` は Port インターフェースに依存してよいが、Port 具象実装への依存は互換コンストラクタ内の adapter 生成に限定する。
- `macros\` 配下は引き続き `nyxpy.framework.*` にだけ依存する。

### 公開 API 方針

新規公開 API は `nyxpy.framework.core.runtime` と `nyxpy.framework.core.io` に集約する。既存 `Command` API は維持し、`DefaultCommand` の import path と主要コンストラクタ引数も移行期間中は維持する。

`CommandFacade` は新規実装の正とする。`DefaultCommand` は次のどちらの形式でも生成できる。

1. 新形式: `DefaultCommand(context=execution_context)`
2. 旧形式: `DefaultCommand(serial_device=..., capture_device=..., resource_io=..., protocol=..., ct=..., notification_handler=...)`

旧形式は内部で標準 Port adapter を生成する。旧形式を即時廃止せず、移行後 1 minor 以上の期間は `DeprecationWarning` なしで維持する。GUI/CLI の内部利用だけを先に新形式へ移す。

### 後方互換性

破壊的変更は行わない。次の互換条件を受け入れ基準とする。

| 互換対象 | 方針 |
|----------|------|
| `from nyxpy.framework.core.macro.command import Command` | 維持 |
| `from nyxpy.framework.core.macro.command import DefaultCommand` | 維持 |
| `Command.press`, `hold`, `release`, `wait`, `stop`, `log`, `capture`, `save_img`, `load_img`, `keyboard`, `type`, `notify`, `touch`, `touch_down`, `touch_up`, `disable_sleep` | メソッド名、引数名、既定値を維持 |
| 既存マクロの `initialize(cmd, args)`, `run(cmd)`, `finalize(cmd)` | 維持 |
| `MacroExecutor.execute(cmd, exec_args)` | 既存ユーザーマクロが直接依存していない限り公開互換契約から外す。既存 GUI/CLI/テスト移行のために残す場合は一時 adapter とし、例外再送出、`None` 戻り値互換だけを担い、内部実装は Runtime / Runner へ委譲 |
| Dummy 実装 | テスト・明示指定用途として維持。本番 Runtime の暗黙 fallback は廃止 |

### レイヤー構成

| レイヤー | モジュール | 責務 |
|----------|------------|------|
| Entry | `src\nyxpy\cli`, `src\nyxpy\gui` | ユーザー入力、表示、設定編集、Runtime 呼び出し |
| Runtime | `src\nyxpy\framework\core\runtime` | 実行単位の生成、同期・非同期実行、キャンセル、結果、リソース解放 |
| Command | `src\nyxpy\framework\core\macro\command.py` | 既存 Command API を提供し Ports へ委譲 |
| Port | `src\nyxpy\framework\core\io` | I/O 境界の抽象化、テスト差し替え点 |
| Adapter | `src\nyxpy\framework\core\io\*.py` | 現行 Serial/Capture/Resource/Notification/Logger 実装との接続 |
| Device | `src\nyxpy\framework\core\hardware`, `src\nyxpy\framework\core\api`, `src\nyxpy\framework\core\logger` | 具象 I/O |

### 性能要件

| 指標 | 目標値 |
|------|--------|
| `CommandFacade.press()` の Port 委譲オーバーヘッド | 既存 `DefaultCommand.press()` 比 +1 ms 未満 |
| `FrameSourcePort.latest_frame()` のロック保持時間 | 1280x720 BGR frame copy を含め 10 ms 未満 |
| `FrameSourcePort.await_ready()` 既定タイムアウト | 3 秒 |
| デバイス検出の CLI 既定タイムアウト | 5 秒 |
| GUI 起動時の同期ブロック | 200 ms 未満。長い検出はバックグラウンド化し、完了イベントで UI 更新 |
| `CommandFacade.wait()` キャンセル確認周期 | 50 ms 以下 |
| `RunHandle.cancel()` から `RunResult.cancelled` までの目標 | マクロが `Command` API 内にいる場合 100 ms 以下 |
| `release()` / `close()` の join timeout | 2 秒以下。超過時は警告ログを出し、結果に cleanup warning を残す |

### 並行性・スレッド安全性

- `RunHandle` は `threading.Thread` と `threading.Event` を使う。Qt 依存の worker は GUI 層の薄い adapter とし、Runtime 本体に置かない。
- `ExecutionContext` は実行中に差し替えない。不変データとして扱い、Port の内部状態だけが同期対象になる。
- `ControllerOutputPort` は `threading.Lock` で送信順序を直列化する。GUI の仮想コントローラーとマクロが同一 serial device を共有する場合も bytes の interleave を防ぐ。
- `FrameSourcePort` は最新フレームの参照更新とコピーを lock で保護する。返却値は呼び出し側が破壊しても内部キャッシュに影響しない copy とする。
- `ResourceStorePort` はパス解決を stateless に行う。保存時のディレクトリ作成と書き込みは同一 root 内に限定し、同一ファイルへの同時書き込みは呼び出し側の責務ではなく Port の per-path lock で保護する。
- `NotificationPort` は通知先ごとの例外を握りつぶさず `LoggerPort` に警告として記録する。Runtime の成功・失敗判定は通知失敗で変更しない。
- `LoggerPort` は `LogManager` の thread-safe 性に委譲する。テスト用実装は list への追記を lock で保護する。

## 4. 実装仕様

### 公開インターフェース

```python
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from threading import Event
from typing import Any, Protocol

import cv2

from nyxpy.framework.core.constants import KeyCode, KeyType, SpecialKeyCode
from nyxpy.framework.core.macro.base import MacroBase
from nyxpy.framework.core.macro.command import Command
from nyxpy.framework.core.utils.cancellation import CancellationToken


class RunStatus(StrEnum):
    SUCCESS = "success"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass(frozen=True)
class RuntimeOptions:
    allow_dummy: bool = False
    device_detection_timeout_sec: float = 5.0
    frame_ready_timeout_sec: float = 3.0
    release_timeout_sec: float = 2.0
    wait_poll_interval_sec: float = 0.05


@dataclass(frozen=True)
class ExecutionContext:
    run_id: str
    macro_name: str
    exec_args: Mapping[str, Any]
    metadata: Mapping[str, Any]
    cancellation_token: CancellationToken
    controller: ControllerOutputPort
    frame_source: FrameSourcePort
    resources: ResourceStorePort
    notifications: NotificationPort
    logger: LoggerPort
    options: RuntimeOptions = field(default_factory=RuntimeOptions)


@dataclass(frozen=True)
class RunContext:
    run_id: str
    macro_name: str
    started_at: datetime
    cancellation_token: CancellationToken
    logger: LoggerPort


@dataclass(frozen=True)
class ErrorInfo:
    kind: str
    code: str
    message: str
    component: str
    exception_type: str
    recoverable: bool = False
    details: Mapping[str, Any] = field(default_factory=dict)
    traceback: str | None = None


@dataclass(frozen=True)
class RunResult:
    run_id: str
    macro_name: str
    status: RunStatus
    started_at: datetime
    finished_at: datetime
    error: ErrorInfo | None = None
    cleanup_warnings: tuple[str, ...] = ()

    @property
    def duration_sec(self) -> float: ...


class RunHandle(ABC):
    @property
    @abstractmethod
    def run_id(self) -> str: ...

    @property
    @abstractmethod
    def cancellation_token(self) -> CancellationToken: ...

    @abstractmethod
    def cancel(self) -> None: ...

    @abstractmethod
    def done(self) -> bool: ...

    @abstractmethod
    def wait(self, timeout: float | None = None) -> bool: ...

    @abstractmethod
    def result(self) -> RunResult: ...


class MacroRuntime:
    def __init__(
        self,
        registry: MacroRegistry | None = None,
        factory: MacroFactory | None = None,
        runner: MacroRunner | None = None,
    ) -> None: ...

    def create_context(
        self,
        *,
        macro_name: str,
        exec_args: Mapping[str, Any] | None,
        controller: ControllerOutputPort,
        frame_source: FrameSourcePort,
        resources: ResourceStorePort,
        notifications: NotificationPort,
        logger: LoggerPort,
        options: RuntimeOptions | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> ExecutionContext: ...

    def run(self, context: ExecutionContext) -> RunResult: ...

    def start(self, context: ExecutionContext) -> RunHandle: ...

    def shutdown(self) -> None: ...


class MacroRunner(ABC):
    @abstractmethod
    def run(
        self,
        macro: MacroBase,
        cmd: Command,
        exec_args: Mapping[str, Any],
        run_context: RunContext,
    ) -> RunResult: ...
```

```python
class ControllerOutputPort(ABC):
    @abstractmethod
    def press(self, keys: tuple[KeyType, ...]) -> None: ...

    @abstractmethod
    def hold(self, keys: tuple[KeyType, ...]) -> None: ...

    @abstractmethod
    def release(self, keys: tuple[KeyType, ...] = ()) -> None: ...

    @abstractmethod
    def keyboard(self, text: str) -> None: ...

    @abstractmethod
    def type_key(self, key: str | KeyCode | SpecialKeyCode) -> None: ...

    @abstractmethod
    def close(self) -> None: ...


class TouchInputCapability(ABC):
    @abstractmethod
    def touch_down(self, x: int, y: int) -> None: ...

    @abstractmethod
    def touch_up(self) -> None: ...


class SleepControlCapability(ABC):
    @abstractmethod
    def disable_sleep(self, enabled: bool = True) -> None: ...


class FrameSourcePort(ABC):
    @abstractmethod
    def initialize(self) -> None: ...

    @abstractmethod
    def await_ready(self, timeout: float | None = None) -> bool: ...

    @abstractmethod
    def latest_frame(self) -> cv2.typing.MatLike: ...

    @abstractmethod
    def close(self) -> None: ...


class ResourceStorePort(ABC):
    @abstractmethod
    def resolve_resource_path(self, filename: str | Path) -> Path: ...

    @abstractmethod
    def save_image(self, filename: str | Path, image: cv2.typing.MatLike) -> None: ...

    @abstractmethod
    def load_image(self, filename: str | Path, grayscale: bool = False) -> cv2.typing.MatLike: ...

    def close(self) -> None: ...


class NotificationPort(ABC):
    @abstractmethod
    def publish(self, text: str, img: cv2.typing.MatLike | None = None) -> None: ...


class LoggerPort(ABC):
    @abstractmethod
    def log(self, level: str, message: str, component: str | None = None) -> None: ...
```

```python
class CommandFacade(Command):
    def __init__(self, context: ExecutionContext) -> None: ...

    def press(self, *keys: KeyType, dur: float = 0.1, wait: float = 0.1) -> None: ...
    def hold(self, *keys: KeyType) -> None: ...
    def release(self, *keys: KeyType) -> None: ...
    def wait(self, wait: float) -> None: ...
    def stop(self) -> None: ...
    def log(self, *values, sep: str = " ", end: str = "\n", level: str = "INFO") -> None: ...
    def capture(
        self,
        crop_region: tuple[int, int, int, int] | None = None,
        grayscale: bool = False,
    ) -> cv2.typing.MatLike: ...
    def save_img(self, filename: str | Path, image: cv2.typing.MatLike) -> None: ...
    def load_img(self, filename: str | Path, grayscale: bool = False) -> cv2.typing.MatLike: ...
    def keyboard(self, text: str) -> None: ...
    def type(self, key: str | KeyCode | SpecialKeyCode) -> None: ...
    def notify(self, text: str, img: cv2.typing.MatLike | None = None) -> None: ...
    def touch(self, x: int, y: int, dur: float = 0.1, wait: float = 0.1) -> None: ...
    def touch_down(self, x: int, y: int) -> None: ...
    def touch_up(self) -> None: ...
    def disable_sleep(self, enabled: bool = True) -> None: ...


class DefaultCommand(CommandFacade):
    def __init__(
        self,
        *,
        context: ExecutionContext | None = None,
        serial_device: SerialCommInterface | None = None,
        capture_device: CaptureDeviceInterface | None = None,
        resource_io: StaticResourceIO | ResourceStorePort | None = None,
        protocol: SerialProtocolInterface | None = None,
        ct: CancellationToken | None = None,
        notification_handler: NotificationHandler | NotificationPort | None = None,
        logger: LoggerPort | None = None,
    ) -> None: ...
```

### 内部設計

#### MacroRuntime 同期実行シーケンス

```text
MacroRuntime.run(context)
  ├─ context.logger.log(INFO, "macro starting")
  ├─ context.frame_source.initialize()
  ├─ context.frame_source.await_ready(context.options.frame_ready_timeout_sec)
  │    └─ False の場合 FrameNotReadyError
  ├─ descriptor = registry.resolve(context.macro_name)
  ├─ macro = factory.create(descriptor)
  ├─ cmd = CommandFacade(context)
  ├─ result = runner.run(macro, cmd, context.exec_args, run_context)
  │    ├─ macro.initialize(cmd, args)
  │    ├─ macro.run(cmd)
  │    ├─ macro.finalize(cmd)
  │    └─ RunResult を生成
  └─ controller.close(), frame_source.close(), resources.close() を finally で試行
       └─ close 失敗だけ RunResult.cleanup_warnings に追記
```

`MacroRuntime` は registry 解決、factory 呼び出し、Ports 準備、`CommandFacade(context)` 生成、Port close だけを担当する。`MacroRunner` は現行実行順序を引き継ぎ、`finalize()` を `finally` で呼び、outcome 判定、`MacroStopException` の `RunStatus.CANCELLED` 正規化、`RunResult` 生成を担当する。旧 `MacroExecutor.execute()` を残す場合は一時 adapter として Runtime を呼ぶだけで、Runner と同じ処理を再実装しない。

`ExecutionContext` は `Command` を保持しない。`MacroRuntime.create_context()` は `exec_args` と `metadata` を `dict(...)` で shallow copy し、実行中は `Mapping[str, Any]` として扱う。

#### RunHandle 非同期実行シーケンス

```text
MacroRuntime.start(context)
  ├─ ThreadedRunHandle を作成
  ├─ worker thread で MacroRuntime.run(context)
  ├─ cancel() は context.cancellation_token.request_stop()
  ├─ wait(timeout) は thread.join(timeout) 後、完了済みなら True、timeout なら False
  ├─ done() は完了状態を bool で返す
  └─ result() は完了済みなら RunResult、完了前なら RuntimeError
```

GUI は `RunHandle` を保持する。Qt signal が必要な場合は GUI 層で `QTimer` polling または `QThread` adapter を使い、Runtime 本体へ Qt 依存を入れない。

#### CommandFacade の委譲規則

| Command API | 委譲先 | 補足 |
|-------------|--------|------|
| `press(*keys, dur, wait)` | `controller.press(keys)`, `wait(dur)`, `controller.release(keys)`, `wait(wait)` | 既存の press/release sequence を維持 |
| `hold(*keys)` | `controller.hold(keys)` | 送信 lock は Port 側 |
| `release(*keys)` | `controller.release(keys)` | 空 tuple は全解放 |
| `wait(wait)` | `CancellationToken` aware wait | 50 ms 以下で停止確認 |
| `stop()` | `cancellation_token.request_stop()` | `MacroStopException` を送出 |
| `capture(crop_region, grayscale)` | `frame_source.latest_frame()` | 1280x720 resize、crop、grayscale は CommandFacade で互換維持 |
| `save_img()` | `resources.save_image()` | 失敗時は例外 |
| `load_img()` | `resources.load_image()` | `None` 読み込みは例外 |
| `keyboard()` / `type()` | `controller.keyboard()` / `controller.type_key()` | `type(key: str | KeyCode | SpecialKeyCode)` を受け、テキスト検証は互換維持 |
| `notify()` | `notifications.publish()` | 通知失敗はログ化し、マクロ失敗にしない |
| `log()` | `logger.log()` | component は既存同様 caller class 名を既定にする |
| `touch*()` / `disable_sleep()` | `controller` | 未対応 protocol は `NotImplementedError` |

#### ControllerOutputPort

`ControllerOutputPort` の基本契約は `press`、`hold`、`release`、`keyboard`、`type_key`、`close` に限定する。touch 操作は `TouchInputCapability`、スリープ制御は `SleepControlCapability` を実装した Port だけが提供する。`CommandFacade.touch*()` と `disable_sleep()` は capability の有無を検査し、未対応なら既存どおり `NotImplementedError` を送出する。

`SerialControllerOutputPort` は `SerialCommInterface` と `SerialProtocolInterface` を受け取り、既存 `DefaultCommand` 内の protocol build 処理を移管する。`VirtualControllerModel` も同じ Port を使うことで、マクロ実行と手動操作の送信経路を統一する。

本番では serial device 未選択時に `DummySerialComm` へ自動 fallback しない。`RuntimeOptions.allow_dummy=True` のときだけ `DummyControllerOutputPort` を構築できる。

#### FrameSourcePort

`CaptureFrameSourcePort` は現行 `AsyncCaptureDevice` または `CaptureDeviceInterface` を包む。`initialize()` 後に capture loop が最初の frame を取得した時点で internal `Event` を set し、`await_ready()` はこの Event を待つ。`latest_frame()` は readiness 未達なら `FrameNotReadyError` を送出する。

`DummyFrameSourcePort` はテストと明示 dummy 実行用であり、黒画面または指定 frame を即時 ready とする。

#### ResourceStorePort

`StaticResourceStorePort` は画像保存・読み込みだけを担当する。`static/<macro_name>/settings.toml` 互換と manifest settings path は `MacroSettingsResolver` が担当し、設定解決と画像リソース保存先を混同しない。

`MacroSettingsResolver` は manifest `settings` を次のように解決する。`static/...` のような通常パスは `project_root` 相対、`./settings.toml` のように `./` で始まるパスは manifest を置いた macro root 相対である。絶対パスと `..` による root 外参照は拒否する。legacy fallback は `project_root/static/<macro_name>/settings.toml` を優先し、`cwd` fallback は非推奨警告付きで残す。

`StaticResourceStorePort` は root を `Path.cwd() / "static"` またはマクロ固有 static root として受け取る。`resolve_resource_path()` は次を満たす場合だけパスを返す。

1. `filename` が空でない。
2. `filename` が `str | Path` である。
3. `filename` が絶対パスでない。
4. `(root / filename).resolve()` が `root.resolve()` 配下である。
5. 保存時、親ディレクトリ作成後も解決済み親ディレクトリが root 配下である。

`cv2.imwrite(str(path), image)` が `False` を返した場合は `ResourceWriteError` を送出する。

#### NotificationPort

`NotificationHandlerPort` は現行 `NotificationHandler` を adapter として包む。`NotificationHandler` が `None` の場合は `NoopNotificationPort` を使う。個別 notifier の失敗は `LoggerPort` に `WARNING` で記録し、マクロ本体の `RunResult` は変更しない。

#### LoggerPort

`LogManagerPort` は `log_manager.log(level, message, component)` に委譲する。`CommandFacade.log()` は既存互換のため `sep` と `end` を反映し、component 未指定時は `get_caller_class_name()` 相当を使う。

### GUI/CLI 移行後シーケンス

#### CLI

```text
main()
  ├─ argparse で引数解析
  ├─ configure_logging()
  ├─ builder = MacroRuntimeBuilder.from_cli_args(args)
  ├─ detection = builder.detect_devices(timeout=5.0)
  │    ├─ serial/capture が未検出なら exit code 1
  │    └─ timeout なら検出途中の候補と timeout を表示して exit code 1
  ├─ context = builder.create_context(macro_name=args.macro_name, exec_args=parse_define_args(args.define))
  ├─ result = builder.runtime.run(context)
  ├─ result.status == SUCCESS なら exit code 0
  ├─ result.status == CANCELLED なら exit code 130
  └─ result.status == FAILED なら exit code 2
```

CLI から `serial_manager.get_active_device()` と `capture_manager.get_active_device()` を直接呼ばない。検出完了待ちと dummy 許可は `MacroRuntimeBuilder` に集約する。Discord / Bluesky 通知設定は `SecretsSettings` を唯一の入力元とし、CLI 独自の通知設定解釈を持たない。

#### GUI

```text
MainWindow.__init__()
  ├─ builder = MacroRuntimeBuilder.from_settings(global_settings, secrets_settings)
  ├─ builder.start_device_detection(background=True)
  ├─ PreviewPane は builder.frame_source_for_preview() を購読
  └─ VirtualControllerModel は builder.controller_output_for_manual_input() を保持

Run button
  ├─ context = builder.create_context(macro_name, exec_args)
  ├─ handle = runtime.start(context)
  ├─ control_pane.set_running(True)
  └─ QTimer で handle.done() を監視し、完了時 result を UI に反映

Cancel button
  ├─ handle.cancel()
  └─ UI は "中断要求中" を表示し、完了結果は handle.result() で確定

Window close
  ├─ 実行中 handle.cancel()
  ├─ handle.wait(timeout=5.0)
  ├─ builder.shutdown()
  └─ preview/controller ports を close
```

GUI から `DefaultCommand` を直接構築しない。既存 `WorkerThread` は Runtime 非同期実行へ置き換えるか、Qt signal adapter のみに縮小する。

### 設定パラメータ

| パラメータ | 型 | デフォルト | 説明 |
|------------|-----|-----------|------|
| `runtime.allow_dummy` | `bool` | `False` | 本番実行で dummy port を許可するか。テストと明示 dry-run 用 |
| `runtime.device_detection_timeout_sec` | `float` | `5.0` | CLI/Runtime builder が serial/capture 検出完了を待つ最大秒数 |
| `runtime.frame_ready_timeout_sec` | `float` | `3.0` | `FrameSourcePort.await_ready()` の最大秒数 |
| `runtime.release_timeout_sec` | `float` | `2.0` | frame source や controller close の待機秒数 |
| `runtime.wait_poll_interval_sec` | `float` | `0.05` | `CommandFacade.wait()` がキャンセル状態を確認する周期 |
| `serial_device` | `str` | `""` | GUI/CLI で選択する serial device 名 |
| `serial_protocol` | `str` | `"CH552"` | `ProtocolFactory` で解決する serial protocol 名 |
| `serial_baud` | `int | None` | `None` | 明示 baudrate。`None` は protocol 既定値 |
| `capture_device` | `str` | `""` | GUI/CLI で選択する capture device 名 |
| `static_root` | `Path | None` | `Path.cwd() / "static"` | `ResourceStorePort` の root |
| `notification.discord.enabled` | `bool` | `False` | `SecretsSettings` の値。CLI/GUI/Runtime builder の唯一の通知設定ソース |
| `notification.bluesky.enabled` | `bool` | `False` | `SecretsSettings` の値。CLI/GUI/Runtime builder の唯一の通知設定ソース |

### エラーハンドリング

| 例外クラス | 発生条件 |
|------------|----------|
| `RuntimeConfigurationError` | Runtime builder に必要な設定が不足、または protocol/baudrate が不正 |
| `DeviceDetectionTimeoutError` | serial/capture 検出が timeout 内に完了しない |
| `DeviceNotFoundError` | 指定された serial/capture device が検出結果に存在しない |
| `DummyDeviceNotAllowedError` | `allow_dummy=False` で dummy device を選択しようとした |
| `FrameNotReadyError` | `FrameSourcePort.await_ready()` が timeout、または ready 前に `latest_frame()` が呼ばれた |
| `FrameReadError` | capture device が `None` frame または空 frame を返した |
| `ResourcePathError` | static root 外、絶対パス、空 filename、不正型の resource path が指定された |
| `ResourceWriteError` | `cv2.imwrite()` が `False` を返す、または保存後にファイルが存在しない |
| `ResourceReadError` | `cv2.imread()` が `None` を返す |
| `ControllerOutputError` | serial send に失敗した |
| `MacroStopException` | `CommandFacade.stop()` またはキャンセル検知時に送出され、Runtime では `RunStatus.CANCELLED` に変換 |

`MacroRunner` は `MacroStopException` を `FAILED` ではなく `CANCELLED` に変換する。その他の例外は `RunStatus.FAILED` とし、`RunResult.error` に `ErrorInfo` として保持する。Runtime は Port close 失敗だけを `RunResult.cleanup_warnings` に追記する。

### シングルトン管理

Runtime 自体は原則としてシングルトンにしない。GUI と CLI が必要な lifetime で `MacroRuntimeBuilder` と `MacroRuntime` を生成する。

`singletons.py` は当面、既存 `serial_manager`, `capture_manager`, `global_settings`, `secrets_settings` を維持する。追加が必要な場合は `device_discovery_service` のみに限定し、`reset_for_testing()` で Runtime/Port 関連状態を含めて初期化する。

### 現行問題への対応詳細

| 現行問題 | 対応 |
|----------|------|
| dummy fallback | `get_active_device()` の暗黙 dummy 選択を Runtime builder から使わない。互換 API として残す場合も warning を出し、新 Runtime 経路では `allow_dummy` を必須判定にする |
| async detection race | `SerialManager.detect(timeout)` / `CaptureManager.detect(timeout)` または builder 内の `DeviceDiscoveryResult` により完了を待つ。CLI は完了前の `list_devices()` を見ない |
| frame readiness | `FrameSourcePort.initialize()` 後、`await_ready()` が成功するまで Runtime 実行を開始しない。GUI preview は ready 前に placeholder を表示する |
| resource path escape | `ResourceStorePort.resolve_resource_path()` が root と最終 path の `resolve()` 結果を比較する。絶対 filename と root 外 symlink を拒否する |
| `cv2.imwrite` return | `False` の場合に `ResourceWriteError`。保存後に `path.exists()` が false の場合も同じ例外 |
| GUI/CLI 重複構築 | `MacroRuntimeBuilder` に protocol、serial、capture、resource、notification、logger の組み立てを集約する |
| CLI notification settings | Runtime builder が `SecretsSettings` から `NotificationPort` を構築する。CLI 独自設定や `GlobalSettings` 由来の secret 値は持たない |

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| ユニット | `test_command_facade_press_delegates_to_controller_port` | `press()` が press、待機、release の順で `ControllerOutputPort` を呼ぶ |
| ユニット | `test_command_facade_wait_observes_cancellation_token` | 長い wait 中に cancellation が要求されたら 50 ms 周期で `MacroStopException` へ進む |
| ユニット | `test_command_facade_capture_resizes_crops_and_grayscales` | 既存 `DefaultCommand.capture()` と同じ 1280x720 resize、crop 範囲検証、grayscale 変換を行う |
| ユニット | `test_default_command_legacy_constructor_builds_ports` | 旧形式の `DefaultCommand(serial_device=..., ...)` が import path と挙動互換を保つ |
| ユニット | `test_runtime_success_calls_finalize_and_closes_ports` | 正常終了時に `finalize()` と各 Port の close が一度だけ呼ばれ `RunStatus.SUCCESS` になる |
| ユニット | `test_runtime_failed_preserves_error_info` | マクロ例外が `RunResult.error` に `ErrorInfo` として保持され `RunStatus.FAILED` になる |
| ユニット | `test_runtime_cancelled_result` | `RunHandle.cancel()` 後、`RunStatus.CANCELLED` になる |
| ユニット | `test_run_handle_wait_timeout_returns_false` | timeout 内に終了しない場合 `wait()` が `False` を返し、完了時は `True` を返す |
| ユニット | `test_controller_output_port_serializes_send_operations` | 複数スレッド送信で serial bytes が interleave しない |
| ユニット | `test_frame_source_await_ready_success_after_first_frame` | 初回 frame 取得後に readiness が true になる |
| ユニット | `test_frame_source_await_ready_timeout` | frame 未取得なら `FrameNotReadyError` または false を返す |
| ユニット | `test_resource_store_rejects_path_escape` | `..\outside.png`、絶対パス、root 外 symlink を拒否する |
| ユニット | `test_macro_settings_resolver_is_separate_from_resource_store` | settings TOML 解決が `ResourceStorePort` に依存しないことを検証する |
| ユニット | `test_resource_store_raises_when_imwrite_returns_false` | `cv2.imwrite` false を `ResourceWriteError` に変換する |
| ユニット | `test_notification_port_logs_notifier_failure` | notifier 失敗が warning log になり、例外がマクロへ伝播しない |
| 結合 | `test_cli_uses_macro_runtime_builder` | CLI が `DefaultCommand` を直接構築せず Runtime 経由で実行する |
| 結合 | `test_cli_notification_settings_come_from_secrets_settings` | CLI の Discord / Bluesky 通知設定が `SecretsSettings` だけから構築されることを検証する |
| 結合 | `test_cli_device_detection_waits_until_complete` | 非同期検出が遅れても timeout 内なら成功し、race で失敗しない |
| GUI | `test_main_window_starts_runtime_and_updates_status` | Run button が Runtime `start()` を呼び、完了時に status を更新する |
| GUI | `test_main_window_cancel_requests_run_handle_cancel` | Cancel button が `RunHandle.cancel()` を呼ぶ |
| GUI | `test_virtual_controller_uses_controller_output_port` | 仮想コントローラー操作が Port 経由で送信される |
| ハードウェア | `test_serial_controller_output_port_realdevice` | `@pytest.mark.realdevice`。実 serial device へ CH552 press/release bytes を送信できる |
| ハードウェア | `test_capture_frame_source_realdevice_ready` | `@pytest.mark.realdevice`。実 capture device が timeout 内に ready になる |
| パフォーマンス | `test_command_facade_press_overhead_perf` | fake Port で `press()` の追加 overhead が 1 ms 未満 |
| パフォーマンス | `test_frame_source_latest_frame_copy_perf` | 1280x720 frame copy が 10 ms 未満 |

テストでは Port fake を標準化する。実 serial/capture device を使わない単体テストは `DummySerialComm` や `DummyCaptureDevice` ではなく fake Port を優先し、Runtime の責務だけを検証する。

## 6. 実装チェックリスト

- [ ] `ControllerOutputPort`, `FrameSourcePort`, `ResourceStorePort`, `NotificationPort`, `LoggerPort` のシグネチャ確定
- [ ] `ExecutionContext`, `RunHandle`, `RunResult`, `RuntimeOptions` のシグネチャ確定
- [ ] `MacroRuntime` の同期実行 `run()` 実装
- [ ] `MacroRuntime` の非同期実行 `start()` と `RunHandle` 実装
- [ ] `CommandFacade` 実装
- [ ] `DefaultCommand` の import path 維持と旧コンストラクタ互換
- [ ] `SerialControllerOutputPort` 実装
- [ ] `CaptureFrameSourcePort` と frame readiness 実装
- [ ] `StaticResourceStorePort` の path escape 防止
- [ ] `StaticResourceStorePort` の `cv2.imwrite()` 戻り値検証
- [ ] `NotificationHandlerPort` と `NoopNotificationPort` 実装
- [ ] `LogManagerPort` 実装
- [ ] serial/capture detection race を避ける検出完了待ち API 実装
- [ ] 本番 Runtime 経路で暗黙 dummy fallback を禁止
- [ ] GUI の `DefaultCommand` 直接構築を Runtime 利用へ移行
- [ ] CLI の `DefaultCommand` 直接構築を Runtime 利用へ移行
- [ ] `VirtualControllerModel` を `ControllerOutputPort` 利用へ移行
- [ ] `singletons.py` の `reset_for_testing()` が Runtime/Port 関連状態を初期化
- [ ] ユニットテスト作成・パス
- [ ] 結合テスト作成・パス
- [ ] GUI テスト作成・パス
- [ ] 実機テストに `@pytest.mark.realdevice` を付与
- [ ] パフォーマンステスト作成・目標値達成
- [ ] `uv run ruff check .` がパス
- [ ] `uv run pytest tests/unit/` がパス
