# Runtime と I/O Ports 再設計仕様書

> **文書種別**: 仕様書。`MacroRuntime`、`MacroRuntimeBuilder`、Ports、`ExecutionContext`、`RunResult`、`RunHandle` の正本である。
> **対象モジュール**: `src\nyxpy\framework\core\runtime\`, `src\nyxpy\framework\core\io\`, `src\nyxpy\framework\core\macro\`, `src\nyxpy\framework\core\hardware\`  
> **目的**: マクロ実行組み立てとデバイス入出力を Runtime と Port に分離し、既存マクロの import 互換を維持したまま GUI/CLI の重複構築と I/O 境界の不具合を解消する。  
> **関連ドキュメント**: `.github\skills\framework-spec-writing\template.md`, `CONFIGURATION_AND_RESOURCES.md`, `RESOURCE_FILE_IO.md`
> **既存ソース**: `src\nyxpy\framework\core\macro\command.py`, `src\nyxpy\framework\core\hardware\serial_comm.py`, `src\nyxpy\framework\core\hardware\capture.py`, `src\nyxpy\framework\core\hardware\resource.py`, `src\nyxpy\framework\core\api\notification_handler.py`, `src\nyxpy\cli\run_cli.py`, `src\nyxpy\gui\main_window.py`  
> **破壊的変更**: `MacroBase` / `Command` / `DefaultCommand` / constants / `MacroStopException` の import と lifecycle は維持する。Resource I/O、settings lookup、旧 auto discovery、`DefaultCommand` 旧コンストラクタ、`MacroExecutor`、GUI/CLI 内部入口、singleton 直接利用、暗黙 fallback は互換維持対象に含めず、新 API へ置換または削除する。

## 1. 概要

### 1.1 目的

`MacroRuntime` をマクロ実行の唯一の組み立て点とし、シリアル送信・フレーム取得・静的リソース・通知・ログを Port インターフェースで隔離する。既存マクロ資産が利用する `nyxpy.framework.core.macro.command.Command` / `DefaultCommand` の import path とメソッド互換を維持し、GUI/CLI は Runtime を呼び出す薄い入口へ移行する。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| Command | マクロがコントローラー操作、待機、キャプチャ、画像入出力、通知、ログを行うための高レベル API |
| DefaultCommand | 既存 import path を維持する `Command` 実装。移行後は `ExecutionContext` を受け取り、Ports へ委譲する。旧コンストラクタ引数は受け付けない |
| MacroBase | ユーザ定義マクロの抽象基底クラス。`initialize` / `run` / `finalize` ライフサイクルを持つ |
| MacroExecutor | 旧 GUI/CLI/テスト入口で使われる既存クラス。再設計後の公開 API、既存マクロ互換契約、移行 adapter のいずれにも含めず削除する |
| MacroRuntime | 完成済み `ExecutionContext` を受け取り、`Command` 生成、`MacroFactory` / `MacroRunner` 呼び出し、`RunResult` 確定、リソース解放を統括するフレームワーク層の実行基盤 |
| MacroRuntimeBuilder | GUI/CLI 入口から受け取った実行要求を、`MacroDefinition`、settings、`MacroResourceScope`、Ports、`ExecutionContext` へ組み立てる adapter。本書が API と責務の正本である |
| MacroRegistry | 利用可能マクロを発見し、安定 ID とメタデータを保持するレジストリ。実行インスタンスは保持しない |
| MacroFactory | `MacroDefinition` が所有する生成責務。実行ごとに新しい `MacroBase` インスタンスを返す |
| MacroRunner | `initialize -> run -> finalize` のライフサイクルを実行し、例外・中断・結果を `RunResult` に変換するコンポーネント |
| ExecutionContext | 1 回のマクロ実行に必要な `macro_id`、`macro_name`、引数、CancellationToken、Ports、設定値、実行 ID を束ねる不変データ |
| RunLogContext | 1 回の実行に紐づくログ相関情報。型定義は `LOGGING_FRAMEWORK.md` を正とし、所有は `ExecutionContext.run_log_context` とする |
| RunHandle | 非同期実行中のマクロに対するキャンセル、完了待ち、結果取得のハンドル |
| RunResult | `macro_id`、`macro_name`、マクロ実行の終了状態、`datetime` の開始・終了時刻、`ErrorInfo | None`、`cleanup_warnings` を表す値オブジェクト |
| ControllerOutputPort | ボタン、スティック、キーボード入力をコントローラー出力へ送る基本 Port。touch と sleep は optional capability に分離する |
| FrameSourcePort | キャプチャデバイスまたはテスト用フレームソースから最新フレームを取得する Port |
| ResourceStorePort | Resource File I/O の assets 読み込みを行う Port。詳細は `RESOURCE_FILE_IO.md` を正とし、settings TOML 解決は担当しない |
| RunArtifactStore | Resource File I/O の writable outputs 保存を行う Port。実行 ID ごとの成果物 root、atomic write、overwrite policy を担当する |
| MacroResourceScope | 1 つのマクロ ID に紐づく assets root と macro root を表す値 |
| MacroSettingsResolver | manifest または class metadata の settings source と project root 明示設定を解決する専用コンポーネント |
| NotificationPort | Discord / Bluesky などの外部通知へ発行する Port |
| LoggerPort | loguru ベースの `LogManager` またはテスト用ロガーへログを出力する Port |
| Ports/Adapters | Port は Runtime 中核から見た I/O 抽象、Adapter は現行 Serial/Capture/Resource/Notification/Logger 実装へ接続する実装 |
| Compatibility Layer | 既存ユーザーマクロが import する `MacroBase` / `Command` / `DefaultCommand` / constants / `MacroStopException` を維持する互換層。旧コンストラクタ、旧 settings lookup、`MacroExecutor` は含めない |
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
| resource path escape | `StaticResourceIO.save_image()` / `load_image()` は `root / filename` 後の解決済みパス検証を行わない | `RESOURCE_FILE_IO.md` の path guard で root 外アクセスを拒否する必要がある |
| `cv2.imwrite` return | `StaticResourceIO.save_image()` が `cv2.imwrite()` の戻り値を検証しない | `RESOURCE_FILE_IO.md` の write policy で保存失敗を即時例外化する必要がある |
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
| static root 外アクセス | 保存・読み込み先の最終パス検証なし | `RESOURCE_FILE_IO.md` の path guard で root 配下のみ許可 |
| 画像書き込み失敗検出 | `cv2.imwrite()` 失敗を無視 | `RESOURCE_FILE_IO.md` の atomic write と `ResourceWriteError` で即時検出 |
| 既存マクロ import 互換 | `Command` / `DefaultCommand` を直接 import 可能 | 同じ import path を維持 |
| キャンセル応答 | `wait()` 指定秒数まで遅延 | 中断要求から 100 ms 未満で `CancellationToken` を確認し中断へ進む |

### 1.5 着手条件

- 現行 `Command` 抽象メソッドのメソッド名、引数、戻り値互換を維持する。
- `nyxpy.framework.core.macro.command.DefaultCommand` の import path を維持する。
- 既存の `MacroBase` ライフサイクル、`Command` / `DefaultCommand`、constants、`MacroStopException` を維持する。旧 settings lookup は維持せず、manifest / class metadata / settings なしの解決順と `exec_args` merge を新契約として固定する。
- GUI/CLI の実行組み立ては変更してよいが、GUI/CLI がマクロへ渡す `cmd` は `Command` として振る舞う。
- 既存テスト (`uv run pytest tests/unit/`) が移行前後でパスすること。
- 実機依存テストは `@pytest.mark.realdevice` を付け、通常の単体テストから分離する。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `spec/framework/rearchitecture/RUNTIME_AND_IO_PORTS.md` | 新規 | 本仕様書 |
| `src\nyxpy\framework\core\runtime\__init__.py` | 新規 | Runtime 公開 API の再 export |
| `src\nyxpy\framework\core\runtime\context.py` | 新規 | `ExecutionContext`, `RuntimeOptions` を定義 |
| `src\nyxpy\framework\core\runtime\result.py` | 新規 | `RunStatus`, `RunResult` を定義 |
| `src\nyxpy\framework\core\runtime\handle.py` | 新規 | `RunHandle` とスレッド実装を定義 |
| `src\nyxpy\framework\core\runtime\runtime.py` | 新規 | `MacroRuntime` の同期・非同期実行を実装 |
| `src\nyxpy\framework\core\runtime\builder.py` | 新規 | `MacroRuntimeBuilder` の正本。GUI/CLI 実行要求から Runtime、Ports、settings、resource scope を組み立てる |
| `src\nyxpy\framework\core\io\__init__.py` | 新規 | Port インターフェースと標準実装の再 export |
| `src\nyxpy\framework\core\io\ports.py` | 新規 | `ControllerOutputPort`, `FrameSourcePort`, `NotificationPort` を定義。Resource File I/O と Logger は各正本を参照 |
| `src\nyxpy\framework\core\io\controller.py` | 新規 | `SerialControllerOutputPort`, `DummyControllerOutputPort` を実装 |
| `src\nyxpy\framework\core\io\frame_source.py` | 新規 | `CaptureFrameSourcePort`, `DummyFrameSourcePort`, frame readiness を実装 |
| `src\nyxpy\framework\core\io\resources.py` | 新規 | `ResourceStorePort`, `RunArtifactStore`, `ResourceRef`, `MacroResourceScope`, path guard を定義・実装。settings TOML 解決は扱わない |
| `src\nyxpy\framework\core\macro\settings_resolver.py` | 新規 | `MacroSettingsResolver` を実装し、manifest / class metadata settings TOML を解決 |
| `src\nyxpy\framework\core\io\notification.py` | 新規 | `NotificationHandler` の Port adapter を実装 |
| `src\nyxpy\framework\core\macro\command.py` | 変更 | `DefaultCommand` を `ExecutionContext` と Ports へ接続する実装へ移行 |
| `src\nyxpy\framework\core\hardware\serial_comm.py` | 変更 | 既存 API は維持し、Runtime 経路では暗黙 dummy fallback を使わない。明示的な検出完了待ち API を追加 |
| `src\nyxpy\framework\core\hardware\capture.py` | 変更 | 既存 API は維持し、Runtime 経路で使う検出完了待ち、frame readiness、release join timeout を追加 |
| `src\nyxpy\framework\core\hardware\resource.py` | 変更 | `StaticResourceIO` を Resource File I/O の legacy adapter へ移行 |
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

Runtime は `MacroRegistry`、`MacroRunner` と I/O Ports の接続点に置く。`MacroFactory` は `MacroDefinition` が所有し、Runtime は別の factory facade を受け取らない。`MacroRegistry` の正配置は `src\nyxpy\framework\core\macro\registry.py` である。GUI/CLI は Runtime へ実行要求を渡し、Runtime は `DefaultCommand(context=...)` を作成して `MacroRunner` にライフサイクル実行を委譲する。`MacroExecutor` は Runtime 入口に含めず、GUI/CLI/テストの参照を解消して削除する。

```text
nyxpy.gui / nyxpy.cli
    ↓
MacroRuntimeBuilder
    ↓
MacroRuntime ── RunHandle / RunResult
    ↓
MacroRegistry / MacroDefinition.factory / MacroRunner
    ↓
DefaultCommand implements Command
    ↓
ControllerOutputPort / FrameSourcePort / ResourceStorePort / RunArtifactStore / NotificationPort / LoggerPort
    ↓
SerialComm / AsyncCaptureDevice / static resources / NotificationHandler / LogManager
```

`MacroRuntimeBuilder` の所有権は本書に置く。`CONFIGURATION_AND_RESOURCES.md` は `GlobalSettings` / `SecretsSettings` / `MacroSettingsResolver` の読み込み結果だけを定義し、`RESOURCE_FILE_IO.md` は `MacroResourceScope`、`ResourceStorePort`、`RunArtifactStore`、path guard だけを定義する。GUI/CLI は settings と resource を個別に問い合わせず、実行時は `MacroRuntimeBuilder.build()` を入口にする。

GUI/CLI の実行組み立てフローは次の順で固定する。

```text
GUI/CLI
  -> MacroRuntimeBuilder.build(request)
  -> MacroRegistry.resolve(macro_id)
  -> MacroSettingsResolver.load(definition)
  -> MacroResourceScope.from_definition(definition, project_root)
  -> ResourceStorePort / RunArtifactStore / ControllerOutputPort / FrameSourcePort / NotificationPort / LoggerPort を生成
  -> ExecutionContext を生成
  -> MacroRuntime.run(context) または MacroRuntime.start(context)
```

`MacroSettingsResolver.load()` が返す settings は `ExecutionContext.exec_args` の初期値であり、GUI/CLI から渡された実行引数が同一 key を上書きする。`MacroRuntimeBuilder` は設定ファイル探索規則や resource path guard を再実装せず、各仕様の公開 API だけを呼ぶ。

依存方向は次の制約を守る。

- `nyxpy.framework.core.runtime` は `nyxpy.gui` と `nyxpy.cli` に依存しない。
- `nyxpy.framework.core.io` は GUI イベントや Qt 型に依存しない。
- `nyxpy.framework.core.macro.command` は Port インターフェースに依存してよいが、Port 具象実装へ依存しない。
- `macros\` 配下は引き続き `nyxpy.framework.*` にだけ依存する。

### 公開 API 方針

新規公開 API は `nyxpy.framework.core.runtime` と `nyxpy.framework.core.io` に集約する。既存 `Command` API と `DefaultCommand` の import path は維持するが、`DefaultCommand` の旧コンストラクタ引数は公開互換契約から外す。

追加の別 `Command` 実装クラスは置かない。`DefaultCommand` は既存 import path を維持したまま、次の形式だけで生成できる Port 委譲実装とする。

1. 新形式: `DefaultCommand(context=execution_context)`

既存マクロは GUI/CLI 経路から生成された `Command` を受け取り、`DefaultCommand` を直接生成しない前提である。旧形式 `DefaultCommand(serial_device=..., capture_device=..., resource_io=..., protocol=..., ct=..., notification_handler=...)` は互換 shim を作らず削除する。GUI/CLI とテストは同じ移行単位で `MacroRuntimeBuilder` 経由へ移す。

### 後方互換性

既存マクロの import path と lifecycle には破壊的変更を行わない。Resource I/O、settings lookup、`DefaultCommand` 旧コンストラクタ、`Command.stop()` の即時例外送出依存など、マクロ側の移行で吸収する項目は破壊的変更を許容する。次の互換条件を受け入れ基準とする。

| 互換対象 | 方針 |
|----------|------|
| `from nyxpy.framework.core.macro.command import Command` | 維持 |
| `from nyxpy.framework.core.macro.command import DefaultCommand` | 維持 |
| `Command.press`, `hold`, `release`, `wait`, `stop`, `log`, `capture`, `save_img`, `load_img`, `keyboard`, `type`, `notify`, `touch`, `touch_down`, `touch_up`, `disable_sleep` | メソッド名、引数名、既定値を維持 |
| 既存マクロの `initialize(cmd, args)`, `run(cmd)`, `finalize(cmd)` | 維持 |
| `MacroExecutor.execute(cmd, exec_args)` | 公開互換契約から外す。例外再送出、`None` 戻り値、`macros` / `macro` 属性は保証せず、GUI/CLI/テスト移行後に削除する |
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
| `DefaultCommand.press()` の Port 委譲オーバーヘッド | 既存 `DefaultCommand.press()` 比 +1 ms 未満 |
| `FrameSourcePort.latest_frame()` のロック保持時間 | 1280x720 BGR frame copy を含め 10 ms 未満 |
| `FrameSourcePort.await_ready()` 既定タイムアウト | 3 秒 |
| デバイス検出の CLI 既定タイムアウト | 5 秒 |
| GUI 起動時の同期ブロック | 200 ms 未満。長い検出はバックグラウンド化し、完了イベントで UI 更新 |
| `DefaultCommand.wait()` キャンセル応答 | 中断要求から 100 ms 未満 |
| `RunHandle.cancel()` から `RunResult.cancelled` までの目標 | マクロが `Command` API 内にいる場合 100 ms 以下 |
| `release()` / `close()` の join timeout | 2 秒以下。超過時は警告ログを出し、結果に cleanup warning を残す |

### 並行性・スレッド安全性

- `RunHandle` は `threading.Thread` と `threading.Event` を使う。Qt 依存の worker は GUI 層の薄い adapter とし、Runtime 本体に置かない。
- `ExecutionContext` は実行中に差し替えない。不変データとして扱い、Port の内部状態だけが同期対象になる。
- `ControllerOutputPort` は `threading.Lock` で送信順序を直列化する。GUI の仮想コントローラーとマクロが同一 serial device を共有する場合も bytes の interleave を防ぐ。
- `FrameSourcePort` は最新フレームの参照更新とコピーを lock で保護する。返却値は呼び出し側が破壊しても内部キャッシュに影響しない copy とする。
- `ResourceStorePort` は assets 読み込みのパス解決を stateless に行う。outputs 保存時のディレクトリ作成、atomic write、同一ファイルへの同時書き込みは `RunArtifactStore` が per-path lock で保護する。
- `NotificationPort` は通知先ごとの例外を握りつぶさず `LoggerPort` に警告として記録する。Runtime の成功・失敗判定は通知失敗で変更しない。
- `LoggerPort` は `LogManager` の thread-safe 性に委譲する。テスト用実装は list への追記を lock で保護する。

Runtime / Port の lock policy は次の表を正とする。取得順は `FW_REARCHITECTURE_OVERVIEW.md` の全体表に従う。`MacroRunner` の lifecycle、ユーザー macro、Port I/O、ログ sink emit 中は、次の lock を保持しない。

| lock 名 | 種別 | 保護対象 | 取得順 | timeout | timeout 時の例外 | 保持してはいけない処理 | テスト名 |
|---------|------|----------|--------|---------|------------------|------------------------|----------|
| `run_start_lock` | `threading.Lock` | `MacroRuntime` 1 インスタンス内の active run、worker thread 作成、二重 start 防止 | `registry_reload_lock` の後、`run_handle_lock` の前 | 2 秒 | `RuntimeBusyError` | macro lifecycle、Port close、device detection、settings parse、ログ sink emit | `test_run_start_lock_rejects_concurrent_start` |
| `run_handle_lock` | `threading.RLock` | `RunHandle` の done flag、result 参照、cancel 要求済み flag | `run_start_lock` の後。単独取得を基本とする | 1 秒 | `RuntimeLockTimeoutError` | worker thread join、macro lifecycle、GUI callback、ログ sink emit | `test_run_handle_result_cancel_thread_safety` |
| `frame_lock` | `threading.Lock` | `FrameSourcePort` の最新 frame 参照、ready flag、copy | `run_handle_lock` の後。`sink_lock` より前 | 100 ms | `FrameReadError` | OpenCV resize / crop / grayscale、disk I/O、logger 呼び出し | `test_frame_source_lock_timeout` |

`run_start_lock` は実行開始の状態遷移だけを保護し、`MacroRunner.run()` 呼び出し前に必ず解放する。`RunHandle.result()` は完了前なら lock 内で状態だけを確認して `RuntimeError` を送出し、完了後は `RunResult` 参照を取り出してから lock を解放する。`FrameSourcePort.latest_frame()` は lock 内で frame 参照を検証して copy し、resize、crop、grayscale は lock 外の `DefaultCommand.capture()` で行う。

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
from typing import BinaryIO, Protocol, runtime_checkable

import cv2

from nyxpy.framework.core.constants import KeyCode, KeyType, SpecialKeyCode
from nyxpy.framework.core.errors import ErrorInfo, FrameworkValue
from nyxpy.framework.core.macro.base import MacroBase
from nyxpy.framework.core.logger.ports import LoggerPort
from nyxpy.framework.core.macro.command import Command
from nyxpy.framework.core.io.resources import OverwritePolicy, ResourceRef
from nyxpy.framework.core.utils.cancellation import CancellationToken


type RuntimeValue = FrameworkValue


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
    macro_id: str
    macro_name: str
    run_log_context: RunLogContext
    exec_args: Mapping[str, RuntimeValue]
    metadata: Mapping[str, RuntimeValue]
    cancellation_token: CancellationToken
    controller: ControllerOutputPort
    frame_source: FrameSourcePort
    resources: ResourceStorePort
    artifacts: RunArtifactStore
    notifications: NotificationPort
    logger: LoggerPort
    options: RuntimeOptions = field(default_factory=RuntimeOptions)


@dataclass(frozen=True)
class RunContext:
    run_id: str
    macro_id: str
    macro_name: str
    started_at: datetime
    cancellation_token: CancellationToken
    logger: LoggerPort


@dataclass(frozen=True)
class RunResult:
    run_id: str
    macro_id: str
    macro_name: str
    status: RunStatus
    started_at: datetime
    finished_at: datetime
    error: ErrorInfo | None = None
    cleanup_warnings: tuple[str, ...] = ()

    @property
    def ok(self) -> bool: ...

    @property
    def duration_seconds(self) -> float: ...


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
        runner: MacroRunner | None = None,
    ) -> None: ...

    def run(self, context: ExecutionContext) -> RunResult: ...

    def start(self, context: ExecutionContext) -> RunHandle: ...

    def shutdown(self) -> None: ...


@dataclass(frozen=True)
class RuntimeBuildRequest:
    macro_id: str
    entrypoint: str
    exec_args: Mapping[str, RuntimeValue] = field(default_factory=dict)
    allow_dummy: bool | None = None
    metadata: Mapping[str, RuntimeValue] = field(default_factory=dict)


class MacroRuntimeBuilder:
    def __init__(
        self,
        *,
        project_root: Path,
        registry: MacroRegistry,
        settings_resolver: MacroSettingsResolver,
        global_settings: GlobalSettings,
        secrets_settings: SecretsSettings,
        runtime: MacroRuntime | None = None,
    ) -> None: ...

    def build(self, request: RuntimeBuildRequest) -> ExecutionContext: ...
    def run(self, request: RuntimeBuildRequest) -> RunResult: ...
    def start(self, request: RuntimeBuildRequest) -> RunHandle: ...


class MacroRunner(ABC):
    @abstractmethod
    def run(
        self,
        macro: MacroBase,
        cmd: Command,
        exec_args: Mapping[str, RuntimeValue],
        run_context: RunContext,
    ) -> RunResult: ...
```

`ExecutionContext` の完全なフィールド一覧は本節を正とする。`RunLogContext` は `ExecutionContext.run_log_context` として保持し、Runtime builder が `run_id`、`macro_id`、`macro_name`、entrypoint、開始時刻から生成する。`LoggerPort.bind_context(context.run_log_context)` は context 付き `LoggerPort` を返すだけで、`RunLogContext` の別所有者にはならない。

`MacroRuntimeBuilder.build()` が `ExecutionContext` の唯一の組み立て入口である。`MacroRuntime` は context を生成せず、完成済み context を `run()` / `start()` で受け取る。

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


@runtime_checkable
class TouchInputCapability(Protocol):
    def touch_down(self, x: int, y: int) -> None: ...

    def touch_up(self) -> None: ...


@runtime_checkable
class SleepControlCapability(Protocol):
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
    def resolve_asset_path(self, filename: str | Path) -> ResourceRef: ...

    @abstractmethod
    def load_image(self, filename: str | Path, grayscale: bool = False) -> cv2.typing.MatLike: ...

    def close(self) -> None: ...


class RunArtifactStore(ABC):
    @abstractmethod
    def resolve_output_path(self, filename: str | Path) -> ResourceRef: ...

    @abstractmethod
    def save_image(
        self,
        filename: str | Path,
        image: cv2.typing.MatLike,
        *,
        overwrite: OverwritePolicy = OverwritePolicy.REPLACE,
        atomic: bool = True,
    ) -> ResourceRef: ...

    @abstractmethod
    def open_output(
        self,
        filename: str | Path,
        mode: str = "xb",
        *,
        overwrite: OverwritePolicy = OverwritePolicy.ERROR,
        atomic: bool = True,
    ) -> BinaryIO: ...

    def close(self) -> None: ...


class NotificationPort(ABC):
    @abstractmethod
    def publish(self, text: str, img: cv2.typing.MatLike | None = None) -> None: ...


# LoggerPort は LOGGING_FRAMEWORK.md の LoggerPort を正とし、
# Runtime 側では bind_context(), user(), technical() だけを利用する。
```

```python
class DefaultCommand(Command):
    def __init__(self, context: ExecutionContext) -> None: ...

    def press(self, *keys: KeyType, dur: float = 0.1, wait: float = 0.1) -> None: ...
    def hold(self, *keys: KeyType) -> None: ...
    def release(self, *keys: KeyType) -> None: ...
    def wait(self, wait: float) -> None: ...
    def stop(self, *, raise_immediately: bool = False) -> None: ...
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
```

### 内部設計

#### MacroRuntime 同期実行シーケンス

```text
MacroRuntime.run(context)
  ├─ context.logger.user("INFO", "macro starting", component="MacroRuntime", event="macro.started")
  ├─ context.frame_source.initialize()
  ├─ context.frame_source.await_ready(context.options.frame_ready_timeout_sec)
  │    └─ False の場合 FrameNotReadyError
  ├─ definition = registry.resolve(context.macro_id)
  ├─ macro = definition.factory.create()
  ├─ cmd = DefaultCommand(context=context)
  ├─ result = runner.run(macro, cmd, context.exec_args, run_context)
  │    ├─ macro.initialize(cmd, args)
  │    ├─ macro.run(cmd)
  │    ├─ macro.finalize(cmd)
  │    └─ RunResult を生成
  └─ controller.close(), frame_source.close(), resources.close(), artifacts.close() を finally で試行
       └─ close 失敗だけ RunResult.cleanup_warnings に追記
```

`MacroRuntime` は registry 解決、`definition.factory.create()` によるマクロ生成、`DefaultCommand(context=...)` 生成、Port close だけを担当する。Ports 準備と `ExecutionContext` 生成は `MacroRuntimeBuilder` が担当する。`MacroRunner` は現行実行順序を引き継ぎ、`finalize()` を `finally` で呼び、outcome 判定、`MacroStopException` の `RunStatus.CANCELLED` 正規化、`RunResult` 生成を担当する。GUI/CLI/テストは `MacroExecutor.execute()` を経由しない。

`RunResult` は常に `MacroRunner` が生成する。`MacroRuntime` は Runner が返した `RunResult.status`、`error`、`started_at`、`finished_at` を変更しない。Port close 失敗だけを `cleanup_warnings: tuple[str, ...]` に追記し、複数 close 失敗は発生順に全件保持する。close 失敗だけで `RunResult.status` を変更しない。

`ExecutionContext` は `Command` を保持しない。`MacroRuntimeBuilder.build()` は `exec_args` と `metadata` を `dict(...)` で shallow copy し、実行中は `Mapping[str, RuntimeValue]` として扱う。

#### RunHandle 非同期実行シーケンス

```text
MacroRuntime.start(context)
  ├─ ThreadedRunHandle を作成
  ├─ worker thread で MacroRuntime.run(context)
  ├─ cancel() は context.cancellation_token.request_cancel(reason="user cancelled", source="gui_or_cli")
  ├─ wait(timeout) は thread.join(timeout) 後、完了済みなら True、timeout なら False
  ├─ done() は完了状態を bool で返す
  └─ result() は完了済みなら RunResult、完了前なら RuntimeError
```

GUI は `RunHandle` を保持する。Qt signal が必要な場合は GUI 層で `QTimer` polling または `QThread` adapter を使い、Runtime 本体へ Qt 依存を入れない。

#### DefaultCommand の委譲規則

| Command API | 委譲先 | 補足 |
|-------------|--------|------|
| `press(*keys, dur, wait)` | `controller.press(keys)`, `wait(dur)`, `controller.release(keys)`, `wait(wait)` | 既存の press/release sequence を維持 |
| `hold(*keys)` | `controller.hold(keys)` | 送信 lock は Port 側 |
| `release(*keys)` | `controller.release(keys)` | 空 tuple は全解放 |
| `wait(wait)` | `CancellationToken` aware wait | 中断要求から 100 ms 未満で停止確認 |
| `stop(raise_immediately=False)` | `cancellation_token.request_cancel(reason="stop requested", source="macro")` | 既定では例外を送出しない。`raise_immediately=True` の場合だけ直後に `MacroCancelled` を送出。この意味論変更は移行対象である |
| `capture(crop_region, grayscale)` | `frame_source.latest_frame()` | 1280x720 resize、crop、grayscale は `DefaultCommand` で互換維持 |
| `save_img()` | `artifacts.save_image()` | outputs 保存。詳細な保存先と overwrite policy は `RESOURCE_FILE_IO.md` |
| `load_img()` | `resources.load_image()` | assets 読み込み。探索順序は `RESOURCE_FILE_IO.md` |
| `keyboard()` / `type()` | `controller.keyboard()` / `controller.type_key()` | `type(key: str | KeyCode | SpecialKeyCode)` を受け、テキスト検証は互換維持 |
| `notify()` | `notifications.publish()` | 通知失敗はログ化し、マクロ失敗にしない |
| `log()` | `logger.user()` | component は既存同様 caller class 名を既定にする。対応する技術ログ生成は `LOGGING_FRAMEWORK.md` の `LoggerPort.user()` に従う |
| `touch*()` / `disable_sleep()` | `controller` | 未対応 protocol は `NotImplementedError` |

`DefaultCommand.press()` は `controller.press(keys)`、`DefaultCommand.wait(dur)`、`controller.release(keys)`、`DefaultCommand.wait(wait)` の順に実行する。`dur <= 0` の場合は押下直後に release し、`wait <= 0` の場合は後続 wait を省略する。2 回の wait はどちらも `CancellationToken` aware wait を使うため、長い `dur` / `wait` 中でも cancellation safe point になる。

`DefaultCommand` は `context` だけを受け取る。`serial_device`、`capture_device`、`resource_io`、`protocol`、`ct`、`notification_handler`、`logger` など旧形式の具象引数を受け取った場合は `TypeError` とし、互換 shim は作らない。GUI/CLI は `MacroRuntimeBuilder` から得た context を渡す。

#### ControllerOutputPort

`ControllerOutputPort` の基本契約は `press`、`hold`、`release`、`keyboard`、`type_key`、`close` に限定する。touch 操作は `TouchInputCapability`、スリープ制御は `SleepControlCapability` を実装した Port だけが提供する。`DefaultCommand.touch*()` と `disable_sleep()` は `isinstance(port, TouchInputCapability)` / `isinstance(port, SleepControlCapability)` で capability の有無を検査し、未対応なら既存どおり `NotImplementedError` を送出する。

`SerialControllerOutputPort` は `SerialCommInterface` と `SerialProtocolInterface` を受け取り、既存 `DefaultCommand` 内の protocol build 処理を移管する。`VirtualControllerModel` も同じ Port を使うことで、マクロ実行と手動操作の送信経路を統一する。

本番では serial device 未選択時に `DummySerialComm` へ自動 fallback しない。`RuntimeOptions.allow_dummy=True` のときだけ `DummyControllerOutputPort` を構築できる。

#### FrameSourcePort

`CaptureFrameSourcePort` は現行 `AsyncCaptureDevice` または `CaptureDeviceInterface` を包む。`initialize()` 後に capture loop が最初の frame を取得した時点で internal `Event` を set し、`await_ready()` はこの Event を待つ。`latest_frame()` は readiness 未達なら `FrameNotReadyError` を送出する。

`FrameSourcePort.await_ready(timeout)` は timeout 到達時に `False` を返し、例外を送出しない。`timeout=None` は無期限待機、`timeout < 0` は `ValueError` とする。Runtime は `False` を `FrameNotReadyError(code="NYX_FRAME_NOT_READY")` に変換して `RunResult.failed` にする。

`FrameSourcePort.latest_frame()` は adapter が受け取った最新 frame の copy を返す。返却値は BGR、`uint8`、shape `(height, width, 3)` とし、サイズは capture device の native size のままにする。既存 `Command.capture()` 互換の 1280x720 resize、crop、grayscale 変換は `DefaultCommand.capture()` が担当する。

`DummyFrameSourcePort` はテストと明示 dummy 実行用であり、黒画面または指定 frame を即時 ready とする。

#### ResourceStorePort / RunArtifactStore

`ResourceStorePort` は read-only assets の読み込みを担当し、`RunArtifactStore` は writable outputs の保存を担当する。manifest または class metadata の settings source と project root 明示設定は `MacroSettingsResolver` が担当し、Resource File I/O と settings lookup を混同しない。

標準配置、path traversal 防止、atomic write、overwrite policy は `RESOURCE_FILE_IO.md` を正とする。Runtime 本仕様では `ExecutionContext` に `MacroResourceScope` と `RunArtifactStore` を注入し、`DefaultCommand.load_img()` / `save_img()` がそれらへ委譲することだけを定義する。

Port close は `controller`、`frame_source`、`resources`、`artifacts` の順に全件試行する。各 `close()` の例外は `cleanup_warnings` へ `"<port_name>: <ExceptionType>: <message>"` 形式で追加し、後続 Port の close を継続する。複数 Port が失敗した場合も全件を発生順に保持し、close 失敗だけで `RunResult.status` と `RunResult.error` は変更しない。

#### NotificationPort

`NotificationHandlerPort` は現行 `NotificationHandler` を adapter として包む。`NotificationHandler` が `None` の場合は `NoopNotificationPort` を使う。個別 notifier の失敗は `LoggerPort` に `WARNING` で記録し、マクロ本体の `RunResult` は変更しない。

#### LoggerPort

`LoggerPort` は `LOGGING_FRAMEWORK.md` の `bind_context()` / `user()` / `technical()` を正 API とする。`DefaultCommand.log()` は既存互換のため `sep` と `end` を反映し、component 未指定時は `get_caller_class_name()` 相当を使い、`logger.user()` へ渡す。旧 `log_manager.log()` 互換 adapter は作らない。

### GUI/CLI 移行後シーケンス

#### CLI

```text
main()
  ├─ argparse で引数解析
  ├─ configure_logging()
  ├─ builder = MacroRuntimeBuilder(project_root=..., registry=..., settings_resolver=..., global_settings=..., secrets_settings=...)
  ├─ request = RuntimeBuildRequest(macro_id=args.macro_name, entrypoint="cli", exec_args=parse_define_args(args.define))
  ├─ result = builder.run(request)
  ├─ result.status == SUCCESS なら exit code 0
  ├─ result.status == CANCELLED なら exit code 130
  └─ result.status == FAILED なら exit code 2
```

CLI から `serial_manager.get_active_device()` と `capture_manager.get_active_device()` を直接呼ばない。検出完了待ち、timeout、dummy 許可は `MacroRuntimeBuilder.run()` の build 手順に集約し、失敗時は `RunResult.failed` と `ErrorInfo` に変換する。Discord / Bluesky 通知設定は `SecretsSettings` を唯一の入力元とし、CLI 独自の通知設定解釈を持たない。

#### GUI

```text
MainWindow.__init__()
  ├─ builder = MacroRuntimeBuilder(project_root=..., registry=..., settings_resolver=..., global_settings=..., secrets_settings=...)
  ├─ GUI adapter がデバイス検出を background 起動し、結果 snapshot を builder 入力へ渡す
  ├─ PreviewPane は builder.frame_source_for_preview() を購読
  └─ VirtualControllerModel は builder.controller_output_for_manual_input() を保持

Run button
  ├─ request = RuntimeBuildRequest(macro_id=macro_id, entrypoint="gui", exec_args=exec_args)
  ├─ handle = builder.start(request)
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
| `runtime.wait_poll_interval_sec` | `float` | `0.05` | `DefaultCommand.wait()` がキャンセル状態を確認する周期。合格条件は中断要求から 100 ms 未満 |
| `serial_device` | `str` | `""` | GUI/CLI で選択する serial device 名 |
| `serial_protocol` | `str` | `"CH552"` | `ProtocolFactory` で解決する serial protocol 名 |
| `serial_baud` | `int | None` | `None` | 明示 baudrate。`None` は protocol 既定値 |
| `capture_device` | `str` | `""` | GUI/CLI で選択する capture device 名 |
| `resource.assets_root` | `Path | None` | `project_root / "resources"` | `ResourceStorePort` の assets root。詳細は `RESOURCE_FILE_IO.md` |
| `resource.runs_root` | `Path | None` | `project_root / "runs"` | `RunArtifactStore` の outputs root。詳細は `RESOURCE_FILE_IO.md` |
| `notification.discord.enabled` | `bool` | `False` | `SecretsSettings` の値。CLI/GUI/Runtime builder の唯一の通知設定ソース |
| `notification.bluesky.enabled` | `bool` | `False` | `SecretsSettings` の値。CLI/GUI/Runtime builder の唯一の通知設定ソース |

### エラーハンドリング

| 例外クラス | 発生条件 |
|------------|----------|
| `RuntimeConfigurationError` | Runtime builder に必要な設定が不足、または protocol/baudrate が不正 |
| `RuntimeBusyError` | 同一 `MacroRuntime` で別実行の start / run が進行中、または `run_start_lock` の取得が 2 秒以内に完了しない |
| `RuntimeLockTimeoutError` | `RunHandle` 状態 lock の取得が 1 秒以内に完了しない |
| `DeviceDetectionTimeoutError` | serial/capture 検出が timeout 内に完了しない |
| `DeviceNotFoundError` | 指定された serial/capture device が検出結果に存在しない |
| `DummyDeviceNotAllowedError` | `allow_dummy=False` で dummy device を選択しようとした |
| `FrameNotReadyError` | Runtime が `FrameSourcePort.await_ready()` の `False` を受け取った、または ready 前に `latest_frame()` が呼ばれた |
| `FrameReadError` | capture device が `None` frame / 空 frame を返した、または `frame_lock` の取得が 100 ms 以内に完了しない |
| `ResourcePathError` | Resource File I/O の許可 root 外、絶対パス、空 filename、不正型の path が指定された。詳細は `RESOURCE_FILE_IO.md` |
| `ResourceWriteError` | Resource File I/O の保存、atomic replace、OpenCV 書き込み検証に失敗した。詳細は `RESOURCE_FILE_IO.md` |
| `ResourceReadError` | Resource File I/O の assets 読み込みに失敗した。詳細は `RESOURCE_FILE_IO.md` |
| `ControllerOutputError` | serial send に失敗した |
| `MacroStopException` | `DefaultCommand.stop(raise_immediately=True)` またはキャンセル検知時に送出され、Runtime では `RunStatus.CANCELLED` に変換 |

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
| resource path escape | `RESOURCE_FILE_IO.md` の `ResourcePathGuard` が root と最終 path の `resolve()` 結果を比較する。絶対 filename と root 外 symlink を拒否する |
| `cv2.imwrite` return | `RESOURCE_FILE_IO.md` の atomic write 仕様に従い、`False`、保存後未存在、replace 失敗を `ResourceWriteError` にする |
| GUI/CLI 重複構築 | `MacroRuntimeBuilder` に protocol、serial、capture、resource、notification、logger の組み立てを集約する |
| CLI notification settings | Runtime builder が `SecretsSettings` から `NotificationPort` を構築する。CLI 独自設定や `GlobalSettings` 由来の secret 値は持たない |

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| ユニット | `test_default_command_press_delegates_to_controller_port` | `press()` が press、待機、release の順で `ControllerOutputPort` を呼ぶ |
| ユニット | `test_default_command_wait_observes_cancellation_token` | 長い wait 中に cancellation が要求されたら 100 ms 未満で `MacroStopException` へ進む |
| ユニット | `test_default_command_capture_resizes_crops_and_grayscales` | 既存 `DefaultCommand.capture()` と同じ 1280x720 resize、crop 範囲検証、grayscale 変換を行う |
| ユニット | `test_default_command_rejects_legacy_constructor_args` | 旧形式の `DefaultCommand(serial_device=..., ...)` を受け付けず、Builder 経由の context を要求する |
| ユニット | `test_runtime_success_calls_finalize_and_closes_ports` | 正常終了時に `finalize()` と各 Port の close が一度だけ呼ばれ `RunStatus.SUCCESS` になる |
| ユニット | `test_runtime_failed_preserves_error_info` | マクロ例外が `RunResult.error` に `ErrorInfo` として保持され `RunStatus.FAILED` になる |
| ユニット | `test_runtime_cancelled_result` | `RunHandle.cancel()` 後、`RunStatus.CANCELLED` になる |
| ユニット | `test_run_handle_wait_timeout_returns_false` | timeout 内に終了しない場合 `wait()` が `False` を返し、完了時は `True` を返す |
| ユニット | `test_controller_output_port_serializes_send_operations` | 複数スレッド送信で serial bytes が interleave しない |
| ユニット | `test_frame_source_await_ready_success_after_first_frame` | 初回 frame 取得後に readiness が true になる |
| ユニット | `test_frame_source_await_ready_timeout` | frame 未取得なら `FrameNotReadyError` または false を返す |
| ユニット | `test_resource_file_io_contract_is_injected_into_context` | `MacroResourceScope` と `RunArtifactStore` が `ExecutionContext` 経由で `DefaultCommand` に渡る |
| ユニット | `test_macro_settings_resolver_is_separate_from_resource_store` | settings TOML 解決が Resource File I/O に依存しないことを検証する |
| ユニット | `test_resource_file_io_path_and_write_policy` | path guard と atomic write の詳細は `RESOURCE_FILE_IO.md` のテストで検証する |
| ユニット | `test_notification_port_logs_notifier_failure` | notifier 失敗が warning log になり、例外がマクロへ伝播しない |
| 結合 | `test_cli_uses_macro_runtime_builder` | CLI が `DefaultCommand` を直接構築せず Runtime 経由で実行する |
| 結合 | `test_cli_notification_settings_come_from_secrets_settings` | CLI の Discord / Bluesky 通知設定が `SecretsSettings` だけから構築されることを検証する |
| 結合 | `test_cli_device_detection_waits_until_complete` | 非同期検出が遅れても timeout 内なら成功し、race で失敗しない |
| GUI | `test_main_window_starts_runtime_and_updates_status` | Run button が Runtime `start()` を呼び、完了時に status を更新する |
| GUI | `test_main_window_cancel_requests_run_handle_cancel` | Cancel button が `RunHandle.cancel()` を呼ぶ |
| GUI | `test_virtual_controller_uses_controller_output_port` | 仮想コントローラー操作が Port 経由で送信される |
| ハードウェア | `test_serial_controller_output_port_realdevice` | `@pytest.mark.realdevice`。実 serial device へ CH552 press/release bytes を送信できる |
| ハードウェア | `test_capture_frame_source_realdevice_ready` | `@pytest.mark.realdevice`。実 capture device が timeout 内に ready になる |
| 性能 | `test_default_command_press_overhead_perf` | fake Port で `press()` の追加 overhead が 1 ms 未満 |
| 性能 | `test_frame_source_latest_frame_copy_perf` | 1280x720 frame copy が 10 ms 未満 |

テストでは Port fake を標準化する。実 serial/capture device を使わない単体テストは `DummySerialComm` や `DummyCaptureDevice` ではなく fake Port を優先し、Runtime の責務だけを検証する。

## 6. 実装チェックリスト

- [ ] `ControllerOutputPort`, `FrameSourcePort`, `ResourceStorePort`, `RunArtifactStore`, `NotificationPort`, `LoggerPort` のシグネチャ確定
- [ ] `ExecutionContext`, `RunHandle`, `RunResult`, `RuntimeOptions` のシグネチャ確定
- [ ] `MacroRuntime` の同期実行 `run()` 実装
- [ ] `MacroRuntime` の非同期実行 `start()` と `RunHandle` 実装
- [ ] `DefaultCommand(context=...)` の Port 委譲実装
- [ ] `DefaultCommand` の import path 維持と旧コンストラクタ削除
- [ ] `SerialControllerOutputPort` 実装
- [ ] `CaptureFrameSourcePort` と frame readiness 実装
- [ ] Resource File I/O の path traversal 防止を `RESOURCE_FILE_IO.md` に従って実装
- [ ] Resource File I/O の atomic write と overwrite policy を `RESOURCE_FILE_IO.md` に従って実装
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
