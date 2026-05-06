# フレームワーク再設計テスト戦略 仕様書

> **文書種別**: 仕様書。再設計全体のテスト分類、配置、性能測定、互換ゲートの正本である。
> **対象モジュール**: `tests\unit\`, `tests\integration\`, `tests\gui\`, `tests\hardware\`, `tests\perf\`, `src\nyxpy\framework\core\`  
> **目的**: フレームワーク再設計を既存マクロ変更なしで進めるため、互換、Runtime 分割、Port adapter、GUI/CLI、実機、性能、スレッド安全性、キャンセル応答の検証方針を定義する。  
> **関連ドキュメント**: `spec\framework\rearchitecture\FW_REARCHITECTURE_OVERVIEW.md`, `spec\framework\rearchitecture\MACRO_COMPATIBILITY_AND_REGISTRY.md`, `spec\framework\rearchitecture\RUNTIME_AND_IO_PORTS.md`, `spec\framework\rearchitecture\ERROR_CANCELLATION_LOGGING.md`, `spec\framework\rearchitecture\CONFIGURATION_AND_RESOURCES.md`, `spec\framework\rearchitecture\OBSERVABILITY_AND_GUI_CLI.md`  
> **破壊的変更**: 既存ユーザーマクロの公開互換契約に対してはなし。`MacroExecutor`、GUI/CLI 内部入口、singleton 直接利用、暗黙 fallback は互換維持対象に含めず、削除確認テストで検証する。

## 1. 概要

### 1.1 目的

フレームワーク内部を抜本改修しても既存マクロが変更なしで動くことを、テストで先に固定する。Registry、Factory、Runner、Runtime、Ports、GUI/CLI adapter を段階別に検証し、実機依存テストは `@pytest.mark.realdevice` で通常テストから分離する。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| import 互換テスト | 既存マクロが利用する import path が削除・移動されていないことを検証するテスト |
| signature 互換テスト | `MacroBase` lifecycle、`Command` API の呼び出しシグネチャを検証するテスト。`MacroExecutor` は既存マクロ互換 API ではなく、削除確認テストで不在を検証する |
| 既存マクロ fixture | リポジトリ内の代表マクロ、または同等構造を `tmp_path` に複製した互換検証用 fixture |
| MacroRegistry | マクロ発見、識別、ロード診断、`MacroDefinition` 一覧を担当するコンポーネント |
| MacroFactory | 実行ごとに新しい `MacroBase` インスタンスを生成するコンポーネント |
| MacroRunner | `initialize -> run -> finalize` と例外・中断・結果変換を担当するコンポーネント |
| MacroRuntime | Registry / Factory / Runner / Ports を統合して同期・非同期実行を提供する中核 |
| Port fake adapter | 実デバイスや外部サービスを使わず、Port 契約を検証するための fake 実装 |
| GUI/CLI integration | GUI/CLI 入口が `MacroRuntime` と `RunResult` を使うことを検証する結合テスト |
| hardware tests | 実機接続が必要なテスト。必ず `@pytest.mark.realdevice` を付ける |
| 性能検証 | reload 時間、ログ配信、設定検証、キャンセル応答などの時間要件を測るテスト |
| スレッド安全性検証 | handler lock、CancellationToken、RunHandle、settings snapshot の競合を検出するテスト |

### 1.3 背景・問題

既存仕様は個別機能のテスト方針を持つが、再設計全体のゲート順序、互換テストの優先度、代表マクロ fixture、Port fake adapter、GUI/CLI integration、性能・スレッド安全性・キャンセル応答を横断する戦略が分散している。内部の抜本改修を許可するには、公開互換を先に固定し、実装差し替えの失敗を早期に検出できるテスト構造が必要である。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| 既存マクロ変更検出 | 手動確認に寄りやすい | import/signature/fixture テストで自動検出 |
| Runtime 分割の安全性 | `MacroExecutor` 中心の結合確認に偏る | Registry/Factory/Runner/Runtime を単体と結合で検証 |
| 実機なし検証 | singleton や具象デバイスに依存しやすい | Port fake adapter で通常テストを完結 |
| GUI/CLI 回帰検出 | 入口ごとの手動確認に依存 | GUI/CLI integration で Runtime 入口化を検証 |
| 実機テスト混入 | 通常テストで失敗し得る | `@pytest.mark.realdevice` に分離 |
| キャンセル応答 | 体感確認になりやすい | 50 ms から 100 ms の目標をテストで測定 |
| スレッド安全性 | handler 例外や lock 競合が未検出 | 並行テストで deadlock と競合を検出 |

### 1.5 着手条件

- 既存マクロ本体を編集しない。
- 代表マクロの import、settings、lifecycle を互換対象として選定する。
- 実機不要の通常テストは fake adapter と `tmp_path` を使い、リポジトリの `macros\` と `static\` を破壊しない。
- `tests\hardware\` 配下、または実機を必要とするテストには `@pytest.mark.realdevice` を付ける。
- 実装の各段階で `uv run pytest tests\unit\` を通す。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `spec\framework\rearchitecture\TEST_STRATEGY.md` | 新規 | 本仕様書 |
| `tests\unit\macro\test_import_contract.py` | 新規 | import path と公開シグネチャの互換を検証 |
| `tests\fixtures\macros\legacy_package\macro.py` | 新規 | legacy package 形式マクロ fixture |
| `tests\fixtures\macros\legacy_single_file.py` | 新規 | single file 形式マクロ fixture |
| `tests\fixtures\static\legacy_package\settings.toml` | 新規 | legacy settings fixture |
| `tests\unit\macro\test_registry.py` | 新規 | `MacroRegistry` と `MacroFactory` の単体テスト |
| `tests\unit\runtime\test_runner.py` | 新規 | `MacroRunner` の lifecycle、例外、中断、finalize を検証 |
| `tests\unit\runtime\test_runtime.py` | 新規 | `MacroRuntime` と `RunHandle` の単体テスト |
| `tests\unit\io\test_fake_ports.py` | 新規 | Port 契約を fake adapter で検証 |
| `tests\integration\test_existing_macro_compat.py` | 新規 | 既存マクロ fixture と repository macro の互換検証 |
| `tests\integration\test_runtime_end_to_end.py` | 新規 | Registry/Factory/Runner/Runtime/Ports の結合検証 |
| `tests\integration\test_cli_runtime_entry.py` | 新規 | CLI 入口が Runtime と `RunResult` を使うことを検証 |
| `tests\gui\test_runtime_entry.py` | 新規 | GUI 入口が `RunHandle` と GUI 表示イベントを使うことを検証 |
| `tests\hardware\test_runtime_realdevice.py` | 新規 | `@pytest.mark.realdevice` 付き実機 Runtime 検証 |
| `tests\perf\test_runtime_perf.py` | 新規 | reload、ログ配信、キャンセル応答の性能検証 |

## 3. 設計方針

### アーキテクチャ上の位置づけ

テストは外側の GUI/CLI から始めず、公開互換、純粋ロジック、Port 境界、Runtime 結合、GUI/CLI integration、実機、性能の順に積む。これにより、内部改修でどの境界が壊れたかを最小単位で特定できる。

```text
compat contract
  -> Registry / Factory
  -> Runner
  -> Runtime
  -> Port fake adapter
  -> GUI / CLI integration
  -> hardware / perf / thread-safety
```

### 公開 API 方針

import/signature 互換テストは最初の保護線である。既存ユーザーマクロ互換契約は次の表で固定する。

| 区分 | 対象 | テスト方針 |
|------|------|------------|
| 互換対象 | `MacroBase` import path と `initialize(cmd, args)` / `run(cmd)` / `finalize(cmd)` | import と `inspect.signature()` で固定 |
| 互換対象 | `Command` / `DefaultCommand` import path、既存 Command method names、主要 keyword args | import、signature、fake Port 委譲で固定 |
| 互換対象 | constants import、`MacroStopException`、`static\<macro_name>\settings.toml` lookup | import、例外捕捉、settings fixture で固定 |
| 互換対象外 | `MacroExecutor`、GUI/CLI 内部入口、singleton 直接利用、暗黙 dummy fallback | 削除確認テストと新 Runtime 入口テストで固定 |

次の import path とシグネチャは個別テストで固定する。

| 対象 | 互換条件 |
|------|----------|
| `nyxpy.framework.core.macro.base.MacroBase` | import でき、`initialize(self, cmd, args)`, `run(self, cmd)`, `finalize(self, cmd)` を持つ |
| `nyxpy.framework.core.macro.command.Command` | 既存 `press`, `hold`, `release`, `wait`, `stop`, `log`, `capture`, `save_img`, `load_img`, `keyboard`, `type`, `notify`, `touch`, `touch_down`, `touch_up`, `disable_sleep` を持つ |
| `nyxpy.framework.core.macro.command.DefaultCommand` | import path を維持し、既存コンストラクタ互換を持つ |
| `nyxpy.framework.core.constants` | `Button`, `Hat`, `LStick`, `RStick`, `KeyType` を import できる |

`MacroExecutor` は公開互換契約から明示的に除外する。テストは成功時 `None`、失敗時例外再送出、`macros` / `macro` 属性を保証せず、`test_macro_executor_removed` と `test_gui_cli_do_not_import_macro_executor` で削除状態を確認する。

### 後方互換性

既存マクロ fixture はフレームワーク公開面だけに依存し、マクロ側へ新 API を要求しない。`static\<macro_name>\settings.toml`、`Command.log()`、`Command.save_img()`、`MacroStopException`、`finalize(cmd)` は互換対象に含める。

リポジトリ内の既存マクロを直接実行する結合テストでは、実ファイルを変更しない。必要な場合は `tmp_path` にコピーし、`monkeypatch.syspath_prepend()` と明示 `project_root` で探索させる。

### レイヤー構成

| テスト層 | 主対象 | 使う依存 | 禁止する依存 |
|----------|--------|----------|--------------|
| 互換単体 | import path、signature | introspection、最小 dummy | 実機、GUI |
| Registry 単体 | discovery、diagnostic、alias | `tmp_path` macro fixture | repository macro 破壊 |
| Runner 単体 | lifecycle、finalize、例外、中断 | fake `Command`、fake logger | device manager singleton |
| Runtime 単体 | context、RunHandle、result | fake Ports、fake registry | GUI/CLI |
| Port 単体 | controller/frame/resource/notification/logger 契約 | fake adapter、monkeypatch | 実シリアル、実通知 |
| 結合 | Runtime end-to-end、既存マクロ互換 | repository macro またはコピー | secret 平文ログ |
| GUI/CLI | 入口 adapter、表示、終了コード | pytest-qt、subprocess 相当 | 実機必須前提 |
| hardware | 実デバイス I/O | 実機、`@pytest.mark.realdevice` | 通常テストへの混入 |
| perf/thread | 時間要件、deadlock、競合 | fake adapter、短時間 stress | 長時間・非決定的検証 |

### テスト配置ルール

再設計仕様のテスト種別は次の分類だけを使う。各仕様書の `## 5. テスト方針` では、この表の種別名と配置を参照する。テンプレート由来の `パフォーマンス` 表記は `性能` と同義だが、新規追記では `性能` に統一する。

| 種別 | 配置 | マーカー | 用途 |
|------|------|----------|------|
| ユニット | `tests\unit\` | なし | 単一コンポーネント、純粋ロジック、fake adapter、実機不要 |
| 結合 | `tests\integration\` | なし | Runtime + fake Ports、CLI entrypoint、複数コンポーネント接続 |
| GUI | `tests\gui\` | なし | pytest-qt を使う GUI adapter / widget / Qt Signal |
| 性能 | `tests\perf\` | `@pytest.mark.perf` | 実機不要の時間要件、fake adapter で決定的に測る処理 |
| ハードウェア | `tests\hardware\` | `@pytest.mark.realdevice` | serial / capture / 実通知など実機・外部環境が必要な確認 |

CLI entrypoint は Qt を使わないため `tests\integration\` に置く。GUI adapter が Runtime を呼ぶだけのテストでも、pytest-qt、widget、Qt Signal、QTimer を使う場合は `tests\gui\` に置く。性能テストは実機を使わず、実機の速度を測る必要がある場合は `tests\hardware\` の記録テストとして分離する。

### 性能要件

| 指標 | 目標値 |
|------|--------|
| 100 件 dummy macro の registry reload | 1 秒未満 |
| `MacroFactory.create()` | 1 回 5 ms 未満 |
| `Command.wait()` キャンセル応答 | token 発火後 100 ms 以内 |
| GUI handler 10 件への event 配信 | 1 event 10 ms 未満 |
| `SettingsSchema` 100 キー検証 | 50 ms 未満 |
| `ResourcePathGuard.resolve()` | 1 path 2 ms 未満 |

#### 性能測定ルール

性能テストは `tests\perf\` に置き、`@pytest.mark.perf` を付ける。実機やネットワークを使う測定は `tests\hardware\` に置き、`@pytest.mark.realdevice` を付ける。実機必須の測定値は smoke / 記録用途とし、通常 CI の失敗条件にしない。

| 項目 | ルール |
|------|--------|
| 時計 | `time.perf_counter()` の wall clock を使う |
| warmup | 対象処理を 1 回以上実行して import / 初期化コストを除外する |
| 試行回数 | fast path は 30 回、I/O を含む処理は 10 回を標準にする |
| 判定値 | P95 をしきい値と比較する。単発上振れでは失敗させない |
| 許容誤差 | fake adapter の通常 CI ではしきい値の 20% までを許容する |
| CI 扱い | 実機不要の `tests\perf\` は CI で fail 条件にする。`@pytest.mark.realdevice` は CI 既定では skip する |
| 測定対象外 | import 初回、pytest fixture 作成、実ファイルの大量コピー、ネットワーク通知、GUI 描画待ちは対象値から外す |

| 測定対象 | 開始点 | 終了点 | 配置 | fail 条件 |
|----------|--------|--------|------|-----------|
| `Command.wait()` cancel latency | 別 thread で `RunHandle.cancel()` または token 発火 | `Command.wait()` が `MacroCancelled` または cancelled result へ到達 | `tests\perf\` | P95 が 100 ms 超 |
| `RunHandle.cancel()` から `RunResult.cancelled` | `RunHandle.cancel()` 呼び出し直前 | `handle.result().status == CANCELLED` | `tests\perf\` | P95 が 100 ms 超。ただし macro が safe point 外にいるケースは別テスト |
| GUI 状態更新 | cancel button click または `UserEvent` emit | pytest-qt で対象 widget state / LogPane 行を観測 | `tests\gui\` | 500 ms 超 |
| path guard | `ResourcePathGuard.resolve()` 呼び出し直前 | `ResourceRef` 返却または expected error | `tests\perf\` | P95 が 2 ms 超 |
| frame readiness | fake frame source の `initialize()` 直後 | `await_ready()` が `True` を返す | `tests\perf\` | P95 が設定値超。実キャプチャは `tests\hardware\` で記録 |

### 並行性・スレッド安全性

`CancellationToken` は複数スレッドから `request_cancel()` されても idempotent であることを検証する。`RunHandle.cancel()` と `result()` は race しやすいため、完了前 `result()` の例外、完了後の安定結果、複数 cancel の安全性をテストする。

`LogManager` は handler snapshot を lock 外で呼ぶため、handler が登録解除を行っても deadlock しないことを検証する。settings は snapshot を実行 context へ渡し、実行中の設定変更が進行中 context を破壊しないことを検証する。

## 4. 実装仕様

### 公開インターフェース

```python
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class MacroFixture:
    macro_id: str
    macro_root: Path
    settings_path: Path | None = None
    expected_aliases: tuple[str, ...] = ()


@dataclass
class FakeControllerOutputPort:
    sent: list[tuple[str, tuple[Any, ...]]] = field(default_factory=list)

    def press(self, keys: tuple[Any, ...]) -> None: ...
    def hold(self, keys: tuple[Any, ...]) -> None: ...
    def release(self, keys: tuple[Any, ...] = ()) -> None: ...
    def keyboard(self, text: str) -> None: ...
    def type_key(self, key: Any) -> None: ...
    def close(self) -> None: ...


@dataclass
class FakeFrameSourcePort:
    ready: bool = True

    def initialize(self) -> None: ...
    def await_ready(self, timeout: float | None = None) -> bool: ...
    def latest_frame(self) -> Any: ...
    def close(self) -> None: ...


@dataclass
class FakeNotificationPort:
    messages: list[str] = field(default_factory=list)

    def publish(self, text: str, img: Any | None = None) -> None: ...


@dataclass
class FakeLoggerPort:
    records: list[Mapping[str, Any]] = field(default_factory=list)

    def log(self, level: str, message: str, component: str | None = None, **extra: Any) -> None: ...
```

### 設定パラメータ

| パラメータ | 型 | デフォルト | 説明 |
|------------|-----|-----------|------|
| `test.registry_macro_count` | `int` | `100` | perf で生成する dummy macro 数 |
| `test.cancel_latency_limit_sec` | `float` | `0.1` | キャンセル応答の上限秒数 |
| `test.gui_event_dispatch_limit_sec` | `float` | `0.01` | GUI event 1 件配信の上限秒数 |
| `test.device_detection_timeout_sec` | `float` | `5.0` | hardware test の検出待ち |
| `test.use_repository_macros` | `bool` | `True` | 結合テストで repository macro を読み込むか |
| `pytest.mark.realdevice` | marker | なし | 実機必須テストに必ず付与する |

### 内部設計

#### import/signature 互換テスト

`inspect.signature()` で既存公開 API の引数名と既定値を検証する。抽象クラスの内部実装は問わず、既存マクロが import して呼べる表面を固定する。`Command` の戻り値注釈は厳密固定しすぎず、呼び出し互換を優先する。

#### 既存マクロ fixture による互換検証

fixture は package 形式、single file 形式、manifest opt-in、壊れた macro、settings あり、settings なしを含める。repository macro 互換テストは代表マクロをロードし、マクロ本体を編集せずに `MacroDefinition` 生成、settings 解決、`initialize -> run -> finalize` の最小 dry-run を検証する。

#### Registry / Factory / Runner / Runtime

Registry はロード診断と alias 解決を単体で検証する。Factory は毎回新しいインスタンスを返すことを検証する。Runner は fake `Command` を使い、成功、例外、中断、finalize 失敗、`finalize(cmd, outcome)` opt-in を検証する。Runtime は fake Ports で context 生成、同期実行、非同期実行、Port close、`cleanup_warnings` を検証する。

#### Ports の fake adapter テスト

Port fake adapter は「テストを通すだけの mock」ではなく、契約違反を検出する spy として使う。controller は送信順序、frame source は readiness、resource store は path guard と OpenCV 戻り値、notification は secret 非露出、logger は `run_id` / `macro_id` を検証する。

| fake adapter | 記録する値 | assert する順序 | 例外時の期待値 |
|--------------|------------|-----------------|----------------|
| `FakeControllerOutputPort` | `press` / `hold` / `release` / `keyboard` / `type_key` の呼び出しと key tuple | `CommandFacade.press()` が press → wait(dur) → release → wait(wait) の順に展開される | 送信例外は `DeviceError` / `ErrorInfo.kind=device` に正規化 |
| `FakeFrameSourcePort` | `initialize`、`await_ready(timeout)`、`latest_frame()`、返却 frame copy | Runtime は initialize → await_ready → macro lifecycle の順に呼ぶ | readiness timeout は `FrameNotReadyError`、read 失敗は `FrameReadError` |
| `FakeResourceStorePort` / `FakeRunArtifactStore` | 解決した相対 path、保存先 `ResourceRef`、overwrite policy | `load_img()` は assets、`save_img()` は artifacts へ委譲 | path escape は `ResourcePathError`、write 失敗は `ResourceWriteError` |
| `FakeNotificationPort` | 通知本文、添付有無、secret mask 済み metadata | マクロ本体の成功・失敗判定とは独立して呼ぶ | 通知失敗は warning log だけで `RunResult.status` を変えない |
| `FakeLoggerPort` / `TestLogSink` | event、level、`run_id`、`macro_id`、mask 済み extra | user / technical event が同一 context で記録される | sink 例外は `sink.emit_failed` に変換し後続 sink 継続 |

#### GUI/CLI integration

CLI は subprocess 相当または `main(args)` 直接呼び出しで、Runtime builder 使用、`RunResult` 由来の終了コード、`SecretsSettings` 由来の通知設定を検証する。GUI は pytest-qt を使い、実行開始で `RunHandle` を保持し、cancel ボタンで `RunHandle.cancel()` を呼び、`UserEvent` を `LogPane` に表示することを検証する。

#### hardware / perf / thread-safety

hardware tests は `tests\hardware\` に置き、全テストに `@pytest.mark.realdevice` を付ける。perf は fake adapter だけで決定的に測り、ネットワークや実機を前提にしない。thread-safety は短時間の複数スレッド stress と timeout を使い、deadlock を失敗として検出する。

lock policy テストは `FW_REARCHITECTURE_OVERVIEW.md` の取得順と、各詳細仕様の lock 表を正とする。テストは lock を意図的に保持する fake / barrier を使い、timeout 例外、逆順取得禁止、lock 解放後に callback / sink emit が呼ばれることを検証する。deadlock 検出はテストごとに 2 秒以内の timeout を置き、timeout した thread が残った場合は `pytest.fail` にする。

### エラーハンドリング

| 例外クラス | 発生条件 |
|------------|----------|
| `AssertionError` | 互換契約、結果、呼び出し順序、性能目標に違反 |
| `pytest.fail` | deadlock timeout、thread 未終了、想定外の実機前提混入 |
| `pytest.skip` | `@pytest.mark.realdevice` 付きで実機が未接続、または明示環境変数がない |
| `ConfigurationError` | テスト対象の設定不備が正しく検出されることを期待するケース |
| `RuntimeBusyError` | 同一 Runtime の二重 start が正しく拒否されることを期待するケース |
| `RuntimeLockTimeoutError` | `RunHandle` の状態 lock timeout を期待するケース |
| `ResourceError` | fake resource store で path や画像読み書き失敗を期待するケース |

テストが secret を扱う場合、値は固定のダミー文字列にし、ログ出力に平文がないことを検証する。

### シングルトン管理

各テストは `reset_for_testing()` を fixture で呼び、`global_settings`、`secrets_settings`、`log_manager`、device manager の状態を初期化する。Runtime、Registry、Port fake はテストごとに生成し、グローバル共有しない。

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| ユニット | `test_macro_base_import_contract` | `MacroBase` の import path と lifecycle signature を検証する |
| ユニット | `test_command_import_and_method_contract` | `Command` と `DefaultCommand` の import、既存メソッド、主要引数を検証する |
| ユニット | `test_macro_executor_removed` | `MacroExecutor` の import 互換 shim が残っていないことを検証する |
| ユニット | `test_constants_import_contract` | `Button`, `Hat`, `LStick`, `RStick`, `KeyType` を import できる |
| ユニット | `test_registry_loads_fixture_macros` | package / single file fixture を `MacroDefinition` 化する |
| ユニット | `test_registry_collects_load_diagnostics` | 壊れた fixture が reload 全体を止めず診断に残る |
| ユニット | `test_factory_creates_new_instance_each_run` | 実行ごとに `MacroBase` インスタンスが共有されない |
| ユニット | `test_runner_lifecycle_success_order` | `initialize -> run -> finalize` の順序を検証する |
| ユニット | `test_runner_normalizes_macro_stop_exception` | 既存 `MacroStopException` を cancelled result にする |
| ユニット | `test_runner_preserves_finalize_failure_details` | finalize 失敗が元エラー情報を失わせない |
| ユニット | `test_runtime_run_with_fake_ports_success` | fake Ports で同期実行が成功する |
| ユニット | `test_runtime_handle_cancel_is_thread_safe` | 複数 cancel と完了待ちが安全に動く |
| ユニット | `test_registry_reload_swaps_snapshot_atomically` | `registry_reload_lock` が definitions / diagnostics を中途半端に見せない |
| ユニット | `test_run_start_lock_rejects_concurrent_start` | 同一 `MacroRuntime` の二重 start が `RuntimeBusyError` になる |
| ユニット | `test_frame_source_lock_timeout` | `frame_lock` timeout が `FrameReadError` として表面化する |
| ユニット | `test_log_manager_sink_snapshot_lock_order` | `sink_lock` 内で sink emit せず、snapshot 後に lock 外配信する |
| ユニット | `test_lock_policy_no_deadlock_under_stress` | registry / runtime / frame / sink の短時間並行操作で deadlock しない |
| ユニット | `test_command_facade_press_expands_to_port_sequence` | `press(dur, wait)` が press、cancel-aware wait、release、cancel-aware wait に展開される |
| ユニット | `test_default_command_rejects_context_and_legacy_args` | `context` と旧具象引数の同時指定が `RuntimeConfigurationError` になる |
| ユニット | `test_frame_source_latest_frame_contract` | `latest_frame()` が BGR `uint8` の native size copy を返し、resize は `CommandFacade.capture()` 側で行う |
| ユニット | `test_runtime_collects_all_port_close_warnings` | 複数 Port close 失敗を `cleanup_warnings` に全件保持し、status を変えない |
| ユニット | `test_fake_frame_source_readiness_failure` | readiness 未達を Runtime が失敗にする |
| ユニット | `test_fake_resource_store_path_escape` | fake resource で root 外参照を拒否する |
| ユニット | `test_fake_notification_does_not_expose_secret` | 通知 secret がログに平文で出ない |
| 結合 | `test_existing_repository_macros_load_without_changes` | 代表既存マクロが変更なしでロードされる |
| 結合 | `test_existing_macro_settings_compat` | `static\<macro_name>\settings.toml` が互換解決される |
| 結合 | `test_runtime_end_to_end_with_fixture_macro` | Registry/Factory/Runner/Runtime/Ports を通した実行が成功する |
| 結合 | `test_cli_uses_runtime_and_run_result` | CLI が Runtime 入口と `RunResult` 終了コードを使う |
| GUI | `test_gui_start_uses_runtime_handle` | GUI 実行開始が `RunHandle` を保持する |
| GUI | `test_gui_cancel_response` | GUI cancel が token を 100 ms 以内に発火させる |
| GUI | `test_gui_log_pane_receives_display_event` | `UserEvent` が GUI 表示に反映される |
| ハードウェア | `test_realdevice_controller_output_port` | `@pytest.mark.realdevice`。実シリアル送信 Port を検証する |
| ハードウェア | `test_realdevice_frame_source_port` | `@pytest.mark.realdevice`。実キャプチャ frame readiness を検証する |
| ハードウェア | `test_realdevice_runtime_smoke` | `@pytest.mark.realdevice`。最小マクロを Runtime 経由で実行する |
| 性能 | `test_registry_reload_100_macros_perf` | 100 件 reload が 1 秒未満で完了する |
| 性能 | `test_cancel_latency_perf` | `Command.wait()` 中の cancel 応答が 100 ms 以内 |
| 性能 | `test_log_handler_dispatch_thread_safety` | handler 登録解除と配信で deadlock しない |
| 性能 | `test_settings_schema_validation_perf` | 100 キー schema 検証が 50 ms 未満 |

## 6. 実装チェックリスト

- [ ] import/signature 互換テストを最初に追加
- [ ] 既存マクロ fixture を package / single file / settings ありで用意
- [ ] repository macro を変更なしでロードする結合テストを追加
- [ ] Registry / Factory の単体テストを追加
- [ ] Runner の lifecycle、例外、中断、finalize テストを追加
- [ ] Runtime の同期実行、非同期実行、`RunHandle` テストを追加
- [ ] Ports の fake adapter テストを追加
- [ ] GUI/CLI integration テストを追加
- [ ] hardware tests へ `@pytest.mark.realdevice` を付与
- [ ] 性能検証を `tests\perf\` に分離
- [ ] スレッド安全性とキャンセル応答の検証を追加
- [ ] `uv run pytest tests\unit\` を段階ごとに実行
