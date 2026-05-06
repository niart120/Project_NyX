# 廃止候補と移行方針 仕様書

> **対象モジュール**: `src\nyxpy\framework\core\macro\`, `src\nyxpy\framework\core\runtime\`, `src\nyxpy\framework\core\io\`, `src\nyxpy\framework\core\hardware\`, `src\nyxpy\framework\core\logger\`, `src\nyxpy\cli\`, `src\nyxpy\gui\`
> **目的**: フレームワーク再設計仕様の分割粒度を確認し、既存マクロ互換の外側で削除・廃止できる実装責務と移行順を定義する。  
> **関連ドキュメント**: `FW_REARCHITECTURE_OVERVIEW.md`, `MACRO_COMPATIBILITY_AND_REGISTRY.md`, `RUNTIME_AND_IO_PORTS.md`, `ERROR_CANCELLATION_LOGGING.md`, `CONFIGURATION_AND_RESOURCES.md`, `OBSERVABILITY_AND_GUI_CLI.md`, `TEST_STRATEGY.md`, `IMPLEMENTATION_PLAN.md`  
> **破壊的変更**: 既存マクロ向けにはなし。`MacroBase`、`Command`、`DefaultCommand`、constants、`MacroStopException`、`static\<macro_name>\settings.toml` 互換は削除対象に含めない。

## 1. 概要

### 1.1 目的

フレームワーク再設計仕様の分割を、責務境界、実装順、テストゲートの観点でレビューする。あわせて、既存マクロの互換契約に含まれない旧実装・暗黙挙動・配置を廃止候補として整理し、削除条件、代替 API、互換影響、テストゲート、移行順を固定する。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| Compatibility Contract | 既存マクロが依存する import path、ライフサイクル、Command API、settings lookup、例外互換を維持する契約 |
| 廃止候補 | 互換契約の外側にあり、代替 API とテストゲートが成立した後に削除または非推奨化できる実装・挙動 |
| 削除条件 | 対象を削除しても既存マクロ互換を壊さず、新 GUI/CLI 入口の受け入れ条件を満たすための必須条件 |
| 代替 API | 廃止候補の呼び出し元が移行する先の API、Port、Adapter、Builder、設定項目 |
| テストゲート | 削除判断前後に必ず通す自動テストまたは検証コマンド |
| 移行順 | 互換テスト追加、代替 API 実装、呼び出し元置換、旧経路削除までの実施順 |
| MacroExecutor | 旧 GUI/CLI/テスト入口。残す場合は `MacroRuntime` へ委譲する一時 adapter とし、既存マクロ互換契約には含めない |
| MacroRuntimeBuilder | GUI/CLI/Legacy 入口から Runtime、Ports、設定 snapshot、通知、ログを組み立てる adapter |
| Ports/Adapters | Runtime 中核からハードウェア、リソース、通知、ログ、GUI/CLI 依存を分離する抽象境界と接続実装 |
| DeprecationWarning | 非推奨 API の呼び出し元へ移行を促す Python 標準警告。既存マクロ互換対象には即時削除を行わない |

### 1.3 背景・問題

再設計仕様は Overview、互換と Registry、Runtime と I/O Ports、異常系、設定とリソース、可観測性、テスト戦略、実装計画に分割されている。分割後も、旧入口の扱い、暗黙 dummy、非同期検出、`Path.cwd()` 起点、singleton 直接利用など、複数仕様へまたがる廃止判断が残っている。

既存マクロ互換を維持するため、廃止対象を公開互換契約から明確に外し、代替経路とテストゲートを先に固定する必要がある。特に `MacroExecutor` や `singletons.py` は「ファイルや import path を即削除する対象」ではなく、「新 Runtime 経路で直接責務を持たせない対象」として扱う。

GUI / CLI は既存マクロ互換契約の外側にあるため、破壊的変更を許容する。旧 GUI / CLI 入口、旧 helper、旧 adapter を温存して二重実装を増やすより、新 Runtime 入口へ直接移行し、受け入れテストで同等のユーザー操作が成立した時点で旧経路を削除する。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| 廃止判断の所在 | Overview、個別仕様、実装計画に分散 | 本書で候補、条件、代替、順序を一元化 |
| 仕様分割レビュー | 個別仕様の責務はあるが横断レビューがない | 妥当、分割、統合、境界曖昧を表で確認可能 |
| 既存マクロ破壊 | 廃止候補と互換契約の境界が曖昧 | 既存マクロ変更 0 件を削除条件に含める |
| GUI/CLI 重複廃止 | 入口ごとの `DefaultCommand` 構築が残る | 新 Runtime 入口へ直接移行し、旧構築 helper と中間 adapter を残さない |
| 暗黙挙動の削除 | dummy fallback、非同期検出、`cwd` fallback が残る | 明示設定と非推奨警告を経由して削除判断 |

### 1.5 着手条件

- `MACRO_COMPATIBILITY_AND_REGISTRY.md` の Compatibility Contract を既存マクロ互換の正とする。
- `RUNTIME_AND_IO_PORTS.md` の Runtime / Ports / `allow_dummy` / 検出完了待ち方針を代替 API の正とする。
- `ERROR_CANCELLATION_LOGGING.md` と `OBSERVABILITY_AND_GUI_CLI.md` の `RunResult`、構造化ログ、GUI/CLI 入口方針を廃止判断の前提にする。
- `IMPLEMENTATION_PLAN.md` のフェーズ順を移行順の基準にする。
- 廃止候補の実装削除は、互換テストと既存マクロ結合テストが通るまで行わない。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `spec\framework\rearchitecture\DEPRECATION_AND_MIGRATION.md` | 新規 | 仕様分割レビュー、廃止候補、削除条件、代替 API、互換影響、テストゲート、移行順を定義 |
| `spec\framework\rearchitecture\FW_REARCHITECTURE_OVERVIEW.md` | 変更 | 本書への参照と廃止候補の方針を追加 |
| `spec\framework\rearchitecture\IMPLEMENTATION_PLAN.md` | 変更 | 本書への参照とフェーズ 9 の廃止判断方針を補強 |
| `src\nyxpy\framework\core\macro\executor.py` | 変更または削除 | `MacroExecutor` を残す場合は Runtime adapter に縮退し、不要なら削除判断 |
| `src\nyxpy\framework\core\singletons.py` | 変更 | 直接利用を Runtime builder / Port adapter へ寄せ、互換 singleton の責務を限定 |
| `src\nyxpy\framework\core\hardware\resource.py` | 変更 | `StaticResourceIO` を `ResourceStorePort` 互換 adapter へ縮退 |
| `src\nyxpy\framework\core\io\resource_store.py` | 新規 | `StaticResourceStorePort` と path guard を正配置として実装 |
| `src\nyxpy\framework\core\runtime\builder.py` | 新規 | GUI/CLI/Legacy 入口の組み立てを集約 |
| `src\nyxpy\cli\run_cli.py` | 変更 | 個別 `DefaultCommand` 構築を Runtime builder 利用へ移行 |
| `src\nyxpy\gui\main_window.py` | 変更 | `RunHandle` / `RunResult` 経由の実行制御へ移行 |
| `tests\unit\framework\macro\test_legacy_imports.py` | 新規 | import / signature 互換ゲート |
| `tests\integration\test_existing_macros_compat.py` | 新規 | 既存マクロ変更なしの互換ゲート |
| `tests\integration\test_macro_runtime_entrypoints.py` | 新規 | GUI/CLI が `MacroExecutor` を経由せず `MacroRuntime` を使うことを検証 |

## 3. 設計方針

### 3.1 仕様分割レビュー

| 区分 | 対象仕様 | 判断 | 理由 |
|------|----------|------|------|
| 現在の分割で妥当 | `MACRO_COMPATIBILITY_AND_REGISTRY.md` | 維持 | 既存マクロの互換契約、Registry、Factory、legacy loader、settings lookup が同じ意思決定単位である |
| 現在の分割で妥当 | `RUNTIME_AND_IO_PORTS.md` | 維持 | Runtime、CommandFacade、Port、dummy policy、device readiness は実行組み立ての一貫した責務である |
| 現在の分割で妥当 | `ERROR_CANCELLATION_LOGGING.md` | 維持 | 例外階層、`RunResult`、キャンセル、ログ event 発行契約を扱う。sink、backend、保持期間などロギング基盤詳細は `LOGGING_FRAMEWORK.md` を正とする |
| 現在の分割で妥当 | `CONFIGURATION_AND_RESOURCES.md` | 維持 | settings schema、Secrets、MacroSettingsResolver を扱う。assets / outputs の配置、path guard、atomic write は `RESOURCE_FILE_IO.md` を正とする |
| 現在の分割で妥当 | `OBSERVABILITY_AND_GUI_CLI.md` | 維持 | GUI/CLI 入口、ユーザー表示、技術ログ、通知 secret の統一は上位 adapter の観点でまとまっている |
| 現在の分割で妥当 | `TEST_STRATEGY.md` | 維持 | 再設計全体のゲート順序とテスト配置を横断的に定義している |
| 現在の分割で妥当 | `IMPLEMENTATION_PLAN.md` | 維持 | 個別仕様をフェーズ順へ落とし込む計画書であり、仕様そのものから分けるのが妥当である |
| さらに分けるべきもの | 廃止候補と移行ガイド | 本書として分離 | 廃止判断は Runtime、Registry、設定、GUI/CLI、ログを横断し、個別仕様へ置くと重複する |
| さらに分けるべきもの | Device discovery と capture ownership | 将来の補助仕様化を許可 | `auto_register_devices()`、frame readiness、GUI preview、Runtime 実行時の所有権が複数仕様にまたがる |
| さらに分けるべきもの | LoggerPort と LogManager V2 | `LOGGING_FRAMEWORK.md` として分離済み | `LogManager` の API 変更、GUI handler、loguru adapter、sink、ログ保持は影響が広く、異常系・GUI/CLI 入口仕様から分けて読む必要がある |
| 統合してもよいもの | `CONFIGURATION_AND_RESOURCES.md` の settings schema と `ERROR_CANCELLATION_LOGGING.md` の settings validation | 現状は維持 | schema と例外正規化は重なるが、前者は永続化境界、後者は異常系表現であり、今は分けた方が追跡しやすい |
| 統合してもよいもの | `OBSERVABILITY_AND_GUI_CLI.md` と `ERROR_CANCELLATION_LOGGING.md` のログ event 発行 | 現状は維持 | 両仕様は `LOGGING_FRAMEWORK.md` の `UserEvent` / `TechnicalLog` を参照し、sink や backend を再定義しないことで矛盾を避ける |
| 境界が曖昧 | `MacroSettingsResolver` | 境界注記を維持 | Registry、Configuration、Runtime builder のすべてから参照される。正配置は `core\macro\settings_resolver.py`、画像 I/O とは分離する |
| 境界が曖昧 | `singletons.py` | 本書で廃止範囲を限定 | singleton ファイル自体は互換で残すが、GUI/CLI/Command からの直接 manager 利用は廃止候補である |
| 境界が曖昧 | `StaticResourceIO` | `ResourceStorePort` へ責務移管 | import 互換 adapter として残すか、hardware 配下から切り離すかを廃止候補として扱う |

### 3.2 廃止判断の原則

廃止候補は、既存マクロ互換契約の内側と外側を分けて扱う。`MacroBase`、`Command`、`DefaultCommand`、constants、`MacroStopException`、`static\<macro_name>\settings.toml` lookup は削除対象にしない。GUI / CLI、内部 helper、旧 executor、旧 singleton 参照、暗黙挙動は互換契約の外側であるため、代替 Runtime 経路と受け入れテストが成立した時点で破壊的に置換してよい。

中途半端な互換資材は作らない。旧 API を残すのは、既存マクロが直接 import する場合、または同一リリース内の段階実装で一時的に必要な場合に限定する。GUI / CLI 向けには長期 adapter、互換 wrapper、旧新二重実装を残さず、移行 commit 内で呼び出し元を新 API へ寄せる。

### 3.3 レイヤー構成

| レイヤー | 維持するもの | 廃止候補にできるもの |
|----------|--------------|----------------------|
| 既存マクロ互換 | `MacroBase`, `Command`, `DefaultCommand`, constants, `MacroStopException`, legacy settings lookup | なし |
| Legacy adapter | 既存マクロが直接 import する API のみ。`MacroExecutor` は同一リリース内の一時移行に限る | `MacroExecutor` 恒久残置、lifecycle 二重実装、発見時インスタンス保持、`Path.cwd()` 固定探索 |
| Runtime / Ports | `MacroRuntime`, `MacroRunner`, `RunHandle`, `RunResult`, `ExecutionContext`, Port interfaces | GUI/CLI の個別 `DefaultCommand` 組み立て、旧 `create_command()` helper |
| Device adapter | 明示検出、ready 待ち、`allow_dummy` | `auto_register_devices()` 直後の暗黙参照、dummy 本番既定 |
| Settings / Resources | `MacroSettingsResolver`, `ResourceStorePort`, `SecretsSettings` | `StaticResourceIO` の settings 解決、hardware 配下への恒久配置 |
| Logger | `LoggerPort`, 構造化ログ、GUI 表示イベント | loguru 直結のグローバル初期化依存 |

### 3.4 後方互換性

削除前に次を満たす。

- 既存マクロの import path、Command API、lifecycle、settings lookup を変更しない。
- CLI/GUI は `MacroRuntimeBuilder` と `RunResult` へ直接移行済みであり、`DefaultCommand` を個別に組み立てない。
- `MacroExecutor` を削除する場合、既存マクロ互換テストが通り、GUI/CLI/テストコードが `MacroExecutor` を参照しない。
- GUI/CLI 内部 API、旧 helper、旧 worker、旧 settings 適用経路には長期の `DeprecationWarning` 期間を設けない。
- `Path.cwd()` fallback、暗黙 dummy fallback、legacy loader は、既存マクロ互換に必要な範囲だけ警告付きで残し、GUI/CLI 入口からは削除する。
- 実機なしの通常テストは fake Port で通り、実機テストは `@pytest.mark.realdevice` へ分離されている。

### 3.5 並行性・スレッド安全性

廃止候補の削除は、並行実行時の状態共有を減らす方向で行う。`MacroRegistry.reload()` と実行開始のロック、`RunHandle.cancel()` の冪等性、`FrameSourcePort.await_ready()`、`LogManager` handler snapshot、settings snapshot は廃止判断の前提である。グローバル manager 直接利用を削ることで、テスト間状態汚染と GUI/CLI 間の競合を減らす。

## 4. 実装仕様

### 4.1 公開インターフェース

本書は廃止判断を記録する仕様であり、Runtime の正 API は各個別仕様を参照する。廃止候補を実装計画へ落とし込む際は、次のモデルで候補を管理できる。

```python
from dataclasses import dataclass
from enum import StrEnum


class DeprecationStatus(StrEnum):
    CANDIDATE = "candidate"
    DEPRECATED = "deprecated"
    ADAPTER_ONLY = "adapter_only"
    REMOVED = "removed"


@dataclass(frozen=True)
class DeprecationCandidate:
    name: str
    removal_condition: str
    replacement_api: str
    compatibility_impact: str
    test_gate: str
    migration_order: str
    status: DeprecationStatus = DeprecationStatus.CANDIDATE
```

### 4.2 廃止候補一覧

| 候補 | 削除条件 | 代替 API | 互換影響 | テストゲート | 移行順 |
|------|----------|----------|----------|--------------|--------|
| `MacroExecutor` | CLI/GUI/テストコードが `MacroRuntime` へ移行し、既存マクロ互換テストが通る。`MacroExecutor` が lifecycle、`RunResult`、Ports 準備を二重実装していない | `MacroRuntime`, `MacroRegistry`, `MacroFactory`, `MacroRunner`, `RunHandle` | 既存マクロへの影響なし。旧 GUI/CLI/内部テストの破壊的変更は許容する | import gate, existing macro gate, `test_cli_uses_macro_runtime`, `test_gui_uses_run_handle` | 互換テスト追加 → GUI/CLI を Runtime へ直接移行 → 内部テスト更新 → `MacroExecutor` 削除またはテスト専用 fixture 化 |
| `singletons.py` のグローバル manager 直接利用 | Runtime builder と Port adapter が manager を受け取り、GUI/CLI/Command が `serial_manager` / `capture_manager` を直接参照しない | `MacroRuntimeBuilder`, `ControllerOutputPort`, `FrameSourcePort`, `create_default_runtime()` | 既存マクロへの影響なし。GUI/CLI の設定適用経路は破壊的変更を許容する | `test_cli_uses_macro_runtime_builder`, `test_main_window_starts_runtime_and_updates_status`, `reset_for_testing` 関連テスト | 直接参照箇所を洗い出し → builder 経由へ置換 → 旧 GUI/CLI 参照を削除 → 新規直接利用を禁止 |
| `auto_register_devices()` の暗黙非同期検出 API | serial/capture 検出が `detect(timeout_sec)` または `DeviceDiscoveryResult` で完了、失敗、タイムアウトを返す | `SerialManager.detect(timeout_sec)`, `CaptureManager.detect(timeout_sec)`, `MacroRuntimeBuilder.detect_devices()` | CLI/GUI の検出表示は変更されるが、既存マクロには影響なし | `test_cli_device_detection_waits_until_complete`, `test_frame_source_await_ready_success_after_first_frame`, hardware detection test | 明示検出 API 追加 → CLI/GUI builder へ移行 → 旧 GUI/CLI 参照を同時削除 |
| dummy fallback の本番既定挙動 | `runtime.allow_dummy=False` が既定になり、テストと明示 dry-run だけが dummy Port を選べる | `RuntimeOptions.allow_dummy`, `DummyControllerOutputPort`, `DummyFrameSourcePort` | 実機未接続を成功扱いしていた CLI/GUI 操作は失敗表示に変わる。既存マクロのコード変更は不要 | `test_runtime_builder_disallows_dummy_by_default`, `test_runtime_allows_dummy_when_explicit`, hardware smoke test | 設定項目追加 → builder で明示判定 → GUI/CLI 表示更新 → 暗黙 fallback を新 Runtime 経路から削除 |
| `StaticResourceIO` の hardware 配下配置 | `StaticResourceStorePort` が path guard、画像書き込み検証、画像読み込み検証を提供し、`StaticResourceIO` が adapter だけになる | `ResourceStorePort`, `StaticResourceStorePort`, `ResourcePathGuard` | `Command.save_img()` / `load_img()` は維持。`StaticResourceIO` 直接 import 利用者だけ警告対象 | `test_resource_store_rejects_path_escape`, `test_resource_store_raises_when_imwrite_returns_false`, `test_command_save_and_load_image_use_resource_store` | Port 実装追加 → `Command` を Port 経由へ移行 → `StaticResourceIO` を adapter 化 → 配置変更または re-export 判断 |
| GUI/CLI 個別 Command 組み立て | CLI と GUI が `DefaultCommand` を直接構築せず、Runtime builder から context を作る | `MacroRuntimeBuilder.from_cli_args()`, `MacroRuntimeBuilder.from_settings()`, `CommandFacade` | 既存マクロへの影響なし。CLI/GUI の内部構築とテストは破壊的変更を許容する | `test_cli_uses_macro_runtime_builder`, `test_main_window_uses_run_handle`, `test_cli_uses_run_result_exit_code` | Runtime builder 実装 → CLI 移行 commit で旧 `create_command()` を削除 → GUI 移行 commit で旧 worker/command 構築を削除 |
| loguru 直結の `LogManager` グローバル初期化 | `LoggerPort` と `LogManager` factory があり、Runtime は `log_manager` グローバルへ直接依存しない | `LoggerPort`, `LogManagerPort`, `create_log_manager()`, `LogManager.add_gui_handler()` | `Command.log()` は維持。保存ログ形式と GUI 表示イベントは変わる | `test_log_manager_emits_structured_log_with_run_context`, `test_gui_handler_exception_is_logged_and_ignored`, `test_technical_log_masks_secrets` | 構造化ログ API 追加 → Port adapter 追加 → GUI handler 分離 → 直接 global 初期化を adapter 内へ限定 |
| `Path.cwd()` 固定の project root 解決 | `project_root` が Runtime builder / Registry / SettingsResolver へ明示され、`cwd` は非推奨 fallback だけになる | `MacroRegistry(project_root=...)`, `MacroSettingsResolver(project_root)`, `MacroRuntimeBuilder(project_root=...)` | `cwd` 前提の外部起動方法は警告対象。既存マクロの settings lookup は維持 | `test_registry_uses_explicit_project_root`, `test_macro_settings_resolver_legacy_static_settings`, existing macro gate | 明示 root 引数追加 → GUI/CLI 起点で渡す → fallback に警告 → 固定 `Path.cwd()` を削除 |
| 恒久的な `sys.path` 変更 | legacy import が context manager で一時追加され、load 後に復元される | `LegacyMacroAdapter` の scoped import path 管理 | 相対 import を使う legacy macro は維持。グローバルな import 汚染だけ削減 | `test_registry_reload_restores_sys_path`, `test_existing_repository_macros_load_without_changes` | scoped loader 実装 → reload テスト追加 → 恒久 append を削除 |
| 曖昧な class 名 alias 選択 | 衝突時に `AmbiguousMacroError` と候補 ID を返し、後勝ち上書きを行わない | `Qualified Macro ID`, `MacroDescriptor.id`, `MacroRegistry.resolve()` | class 名だけで選んでいた外部コードは修正が必要。既存マクロ本体は変更不要 | `test_class_name_collision_requires_qualified_id`, `test_class_name_alias_is_available_when_unique` | ID 生成追加 → 一意 alias 維持 → 衝突時診断追加 → 後勝ち上書きを削除 |
| `ResourceStorePort` による settings TOML 探索 | `MacroSettingsResolver` が settings を解決し、ResourceStore は画像 I/O だけを扱う | `MacroSettingsResolver.resolve()`, `MacroSettingsResolver.load()` | `static\<macro_name>\settings.toml` 互換は維持。責務混在だけ削除 | `test_macro_settings_resolver_is_separate_from_resource_store`, `test_existing_macro_settings_compat` | settings resolver 実装 → helper 委譲 → ResourceStore から settings 探索を排除 |
| GUI スレッドからの `cmd.stop()` 呼び出し | GUI cancel が `RunHandle.cancel()` または `request_cancel()` だけを呼び、GUI スレッドで例外を送出しない | `RunHandle.cancel()`, `CancellationToken.request_cancel()` | GUI 内部挙動の変更。既存マクロの `Command.stop()` は維持 | `test_main_window_cancel_calls_handle_cancel`, `test_main_window_cancel_does_not_raise_in_gui_thread`, cancel latency test | RunHandle 導入 → GUI cancel 移行 → GUI からの直接 `cmd.stop()` を削除 |

### 4.3 設定パラメータ

| パラメータ | 型 | デフォルト | 説明 |
|------------|-----|-----------|------|
| `runtime.allow_dummy` | `bool` | `False` | 本番 Runtime で dummy Port を許可するか |
| `runtime.device_detection_timeout_sec` | `float` | `5.0` | 明示デバイス検出の最大待機秒数 |
| `runtime.frame_ready_timeout_sec` | `float` | `3.0` | 初回フレーム readiness の最大待機秒数 |
| `compatibility.cwd_fallback_enabled` | `bool` | `True` | 非推奨期間中に `Path.cwd()` fallback を許可するか |
| `compatibility.warn_deprecated_legacy_entry` | `bool` | `True` | 既存マクロ互換に必要な legacy entry / 旧 API 利用時だけ非推奨警告を出すか |

### 4.4 エラーハンドリング

| 例外クラス | 発生条件 |
|------------|----------|
| `DeprecationWarning` | 既存マクロ互換のため一時維持する旧 API、`cwd` fallback、legacy loader、`StaticResourceIO` 直接利用など、移行先がある非推奨経路を利用した |
| `ConfigurationError` | `allow_dummy=False` で dummy を選択、明示 project root 不正、通知 secret の入力元違反 |
| `DeviceDetectionTimeoutError` | 明示検出 API が timeout 内に完了しない |
| `AmbiguousMacroError` | class 名 alias が複数 descriptor に一致した |
| `ResourcePathError` | `ResourceStorePort` が static root 外参照を拒否した |

非推奨警告は既存マクロ実行を止めない。`DeprecationWarning` 付き adapter として維持する対象は、既存マクロ互換または外部マクロ作者が直接 import し得る API に限定する。GUI / CLI 内部経路、旧 worker、旧 helper、旧 settings 適用処理は警告期間を置かず、新 Runtime 入口へ置換した commit 内で削除する。

### 4.5 シングルトン管理

`singletons.py` の既存 `serial_manager`、`capture_manager`、`global_settings`、`secrets_settings`、`log_manager` は互換のため維持する。ただし新 Runtime 経路では、GUI/CLI/Command がこれらを直接参照せず、`MacroRuntimeBuilder` と Port adapter が必要な lifetime で受け取る。`MacroRuntime`、`MacroRegistry`、`MacroSettingsResolver`、`ResourceStorePort`、`RunHandle` はシングルトンにしない。

`reset_for_testing()` は既存 singleton の再生成に加え、追加した handler、device discovery 状態、Runtime/Port 関連状態を初期化できるようにする。

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| ユニット | `test_deprecation_candidates_do_not_include_compat_contract` | 廃止候補が `MacroBase` / `Command` / `DefaultCommand` / constants / `MacroStopException` を削除対象にしていない |
| ユニット | `test_no_gui_cli_reference_to_macro_executor` | GUI/CLI が `MacroExecutor` を経由せず Runtime を直接利用する |
| ユニット | `test_runtime_builder_disallows_dummy_by_default` | 本番既定で dummy Port が選択されない |
| ユニット | `test_runtime_allows_dummy_when_explicit` | `allow_dummy=True` の明示時だけ dummy Port を使える |
| ユニット | `test_cli_device_detection_waits_until_complete` | CLI が非同期検出直後の不完全な一覧を参照しない |
| ユニット | `test_registry_uses_explicit_project_root` | `Path.cwd()` 固定ではなく明示 project root を使う |
| ユニット | `test_registry_reload_restores_sys_path` | legacy loader が `sys.path` を恒久変更しない |
| ユニット | `test_resource_store_rejects_path_escape` | root 外リソース参照を拒否する |
| ユニット | `test_log_manager_port_avoids_global_runtime_dependency` | Runtime が `LogManager` グローバルへ直接依存しない |
| 結合 | `test_existing_repository_macros_load_without_changes` | 代表既存マクロが変更なしでロードされる |
| 結合 | `test_existing_macro_settings_compat` | `static\<macro_name>\settings.toml` が互換解決される |
| 結合 | `test_cli_uses_macro_runtime_builder` | CLI が `DefaultCommand` を直接構築せず Runtime builder を使う |
| GUI | `test_main_window_uses_run_handle` | GUI が `RunHandle` で開始、完了、中断を扱う |
| GUI | `test_main_window_cancel_does_not_raise_in_gui_thread` | GUI cancel が呼び出し元スレッドで例外を送出しない |
| ハードウェア | `test_runtime_realdevice_without_dummy_fallback` | `@pytest.mark.realdevice`。実機実行で dummy fallback を使わない |
| パフォーマンス | `test_registry_reload_100_macros_perf` | 廃止候補整理後も 100 件 reload が目標時間内に完了する |

廃止判断前の最小ゲートは次の通りである。

```powershell
uv run pytest tests\unit\framework\macro\test_legacy_imports.py
uv run pytest tests\integration\test_existing_macros_compat.py
uv run pytest tests\integration\test_macro_runtime_legacy_executor.py
uv run pytest tests\integration\test_cli_runtime_adapter.py
uv run pytest tests\gui\test_main_window_runtime_adapter.py
uv run ruff check .
```

本書作成時の文書検証は次を使う。

```powershell
git diff --check
rg "T[O]D[O]|T[B]D|x{3}|\[T[O]D[O]\]" spec\framework\rearchitecture
rg "^## (1\. 概要|2\. 対象ファイル|3\. 設計方針|4\. 実装仕様|5\. テスト方針|6\. 実装チェックリスト)\r?$" spec\framework\rearchitecture\DEPRECATION_AND_MIGRATION.md
```

## 6. 実装チェックリスト

- [x] 仕様分割レビューを記載
- [x] 現在の分割で妥当な仕様を整理
- [x] さらに分けるべき仕様を整理
- [x] 統合してもよい仕様を整理
- [x] 境界が曖昧な仕様を整理
- [x] 既存マクロ互換契約を廃止対象から除外
- [x] `MacroExecutor` の廃止条件、代替 API、互換影響、テストゲート、移行順を記載
- [x] `singletons.py` の直接利用廃止方針を記載
- [x] `auto_register_devices()` の暗黙非同期検出 API 廃止方針を記載
- [x] dummy fallback の本番既定挙動廃止方針を記載
- [x] `StaticResourceIO` の配置と adapter 化方針を記載
- [x] GUI/CLI 個別 Command 組み立て廃止方針を記載
- [x] `LogManager` グローバル初期化依存の縮退方針を記載
- [x] `Path.cwd()` 固定 project root 解決の廃止方針を記載
- [x] 追加の廃止候補を整理
- [x] テストゲートと文書検証コマンドを記載
