# 廃止候補と移行方針 仕様書

> **文書種別**: 仕様書。既存マクロ互換契約の外側にある削除対象、廃止候補、移行順の正本である。
> **対象モジュール**: `src\nyxpy\framework\core\macro\`, `src\nyxpy\framework\core\runtime\`, `src\nyxpy\framework\core\io\`, `src\nyxpy\framework\core\hardware\`, `src\nyxpy\framework\core\logger\`, `src\nyxpy\cli\`, `src\nyxpy\gui\`
> **目的**: フレームワーク再設計仕様の分割粒度を確認し、既存マクロ互換の外側で削除・廃止できる実装責務と移行順を定義する。  
> **関連ドキュメント**: `FW_REARCHITECTURE_OVERVIEW.md`, `MACRO_COMPATIBILITY_AND_REGISTRY.md`, `RUNTIME_AND_IO_PORTS.md`, `ERROR_CANCELLATION_LOGGING.md`, `CONFIGURATION_AND_RESOURCES.md`, `OBSERVABILITY_AND_GUI_CLI.md`, `TEST_STRATEGY.md`, `IMPLEMENTATION_PLAN.md`  
> **破壊的変更**: 本書を破壊的変更、削除条件、代替 API、テストゲート、移行順の正本とする。`MacroBase` / `Command` / `DefaultCommand` / constants / `MacroStopException` の import と lifecycle は維持し、互換契約外の旧実装は本書の条件に従って削除する。

## 1. 概要

### 1.1 目的

フレームワーク再設計仕様の分割を、責務境界、実装順、テストゲートの観点でレビューする。あわせて、既存マクロの互換契約に含まれない旧実装・暗黙挙動・配置を廃止候補として整理し、削除条件、代替 API、互換影響、テストゲート、移行順を固定する。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| Compatibility Contract | 既存マクロが依存する import path、ライフサイクル、Command API、例外互換を維持する契約。旧 settings lookup は含めない |
| 廃止候補 | 互換契約の外側にあり、代替 API とテストゲートが成立した後に削除または非推奨化できる実装・挙動 |
| 削除条件 | 対象を削除しても維持対象の import / lifecycle 互換を壊さず、新 GUI/CLI 入口と移行後マクロの受け入れ条件を満たすための必須条件 |
| 代替 API | 廃止候補の呼び出し元が移行する先の API、Port、Adapter、Builder、設定項目 |
| テストゲート | 削除判断前後に必ず通す自動テストまたは検証コマンド |
| 移行順 | 互換テスト追加、代替 API 実装、呼び出し元置換、旧経路削除までの実施順 |
| MacroExecutor | 旧 GUI/CLI/テスト入口。再設計で削除する旧実装であり、既存マクロ互換契約、移行 adapter、import shim には含めない |
| MacroRuntimeBuilder | GUI/CLI 入口から Runtime、Ports、設定 snapshot、通知、ログを組み立てる adapter |
| Ports/Adapters | Runtime 中核からハードウェア、リソース、通知、ログ、GUI/CLI 依存を分離する抽象境界と接続実装 |
| DeprecationWarning | 非推奨 API の呼び出し元へ移行を促す Python 標準警告。長期互換 shim の維持には使わない |

### 1.3 背景・問題

再設計仕様は Overview、互換と Registry、Runtime と I/O Ports、異常系、設定とリソース、可観測性、テスト戦略、実装計画に分割されている。分割後も、旧入口の扱い、暗黙 dummy、非同期検出、`Path.cwd()` 起点、singleton 直接利用など、複数仕様へまたがる廃止判断が残っている。

維持する import / lifecycle 互換と、マクロ側移行を要求する項目を分ける必要がある。特に `MacroExecutor` は再設計で削除する旧実装として扱い、GUI/CLI/テストの参照を解消した後に import shim を作らず削除する。

GUI / CLI は既存マクロ互換契約の外側にあるため、破壊的変更を許容する。旧 GUI / CLI 入口、旧 helper、旧 adapter を温存して二重実装を増やすより、新 Runtime 入口へ直接移行し、受け入れテストで同等のユーザー操作が成立した時点で旧経路を削除する。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| 廃止判断の所在 | Overview、個別仕様、実装計画に分散 | 本書で候補、条件、代替、順序を一元化 |
| 仕様分割レビュー | 個別仕様の責務はあるが横断レビューがない | 妥当、分割、統合、境界曖昧を表で確認可能 |
| 既存マクロ破壊 | 廃止候補と互換契約の境界が曖昧 | 移行ガイドに従うマクロ変更を削除条件に含める |
| GUI/CLI 重複廃止 | 入口ごとの `DefaultCommand` 構築が残る | 新 Runtime 入口へ直接移行し、旧構築 helper と中間 adapter を残さない |
| 暗黙挙動の削除 | dummy fallback、非同期検出、`cwd` fallback が残る | 明示設定へ寄せ、長期 fallback を残さない |

### 1.5 着手条件

- `MACRO_COMPATIBILITY_AND_REGISTRY.md` の Compatibility Contract を既存マクロ互換の正とする。
- `RUNTIME_AND_IO_PORTS.md` の Runtime / Ports / `allow_dummy` / 検出完了待ち方針を代替 API の正とする。
- `RUNTIME_AND_IO_PORTS.md` の `RunResult`、`ERROR_CANCELLATION_LOGGING.md` の例外正規化、`OBSERVABILITY_AND_GUI_CLI.md` の GUI/CLI 入口方針を廃止判断の前提にする。
- `IMPLEMENTATION_PLAN.md` のフェーズ順を移行順の基準にする。
- 廃止候補の実装削除は、互換テストと既存マクロ結合テストが通るまで行わない。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `spec/framework/rearchitecture/DEPRECATION_AND_MIGRATION.md` | 新規 | 仕様分割レビュー、廃止候補、削除条件、代替 API、互換影響、テストゲート、移行順を定義 |
| `spec/framework/rearchitecture/FW_REARCHITECTURE_OVERVIEW.md` | 変更 | 本書への参照と廃止候補の方針を追加 |
| `spec/framework/rearchitecture/IMPLEMENTATION_PLAN.md` | 変更 | 本書への参照とフェーズ 9 の廃止判断方針を補強 |
| `src\nyxpy\framework\core\macro\executor.py` | 削除 | GUI/CLI/テストの参照移行後に `MacroExecutor` を削除する |
| `src\nyxpy\framework\core\singletons.py` | 変更 | 互換 shim だけを残し、新 Runtime 経路からの直接参照を削除 |
| `src\nyxpy\framework\core\hardware\resource.py` | 変更 | `StaticResourceIO` 直接利用を削除または非公開化し、Resource Store へ置換 |
| `src\nyxpy\framework\core\io\resources.py` | 新規 | `ResourceStorePort`, `RunArtifactStore`, `ResourceRef`, `MacroResourceScope`, path guard を正配置として実装 |
| `src\nyxpy\framework\core\runtime\builder.py` | 新規 | GUI/CLI 入口の組み立てを集約 |
| `src\nyxpy\cli\run_cli.py` | 変更 | 個別 `DefaultCommand` 構築を Runtime builder 利用へ移行 |
| `src\nyxpy\gui\main_window.py` | 変更 | `RunHandle` / `RunResult` 経由の実行制御へ移行 |
| `tests\unit\framework\macro\test_import_contract.py` | 新規 | import / signature 互換ゲート |
| `tests\integration\test_migrated_macro_compat.py` | 新規 | 移行後マクロの互換ゲート |
| `tests\integration\test_macro_runtime_entrypoints.py` | 新規 | GUI/CLI が `MacroExecutor` を経由せず `MacroRuntime` を使うことを検証 |

## 3. 設計方針

### 3.1 仕様分割レビュー

| 区分 | 対象仕様 | 判断 | 理由 |
|------|----------|------|------|
| 現在の分割で妥当 | `MACRO_COMPATIBILITY_AND_REGISTRY.md` | 維持 | 既存マクロの import / lifecycle 互換契約、Registry、`MacroDefinition.factory`、entrypoint loader、manifest 任意採用、class metadata が同じ意思決定単位である |
| 現在の分割で妥当 | `RUNTIME_AND_IO_PORTS.md` | 維持 | Runtime、`DefaultCommand(context=...)`、Port、dummy policy、device readiness は実行組み立ての一貫した責務である |
| 現在の分割で妥当 | `ERROR_CANCELLATION_LOGGING.md` | 維持 | 例外階層、キャンセル、`RunResult` への正規化、ログ event 発行契約を扱う。`RunResult` 本体は `RUNTIME_AND_IO_PORTS.md`、sink、backend、保持期間などロギング基盤詳細は `LOGGING_FRAMEWORK.md` を正とする |
| 現在の分割で妥当 | `CONFIGURATION_AND_RESOURCES.md` | 維持 | settings schema、Secrets、MacroSettingsResolver を扱う。assets / outputs の配置、path guard、atomic write は `RESOURCE_FILE_IO.md` を正とする |
| 現在の分割で妥当 | `OBSERVABILITY_AND_GUI_CLI.md` | 維持 | GUI/CLI 入口、ユーザー表示、技術ログ、通知 secret の統一は上位 adapter の観点でまとまっている |
| 現在の分割で妥当 | `TEST_STRATEGY.md` | 維持 | 再設計全体のゲート順序とテスト配置を横断的に定義している |
| 現在の分割で妥当 | `IMPLEMENTATION_PLAN.md` | 維持 | 個別仕様をフェーズ順へ落とし込む計画書であり、仕様そのものから分けるのが妥当である |
| さらに分けるべきもの | 廃止候補と移行ガイド | 本書として分離 | 廃止判断は Runtime、Registry、設定、GUI/CLI、ログを横断し、個別仕様へ置くと重複する |
| さらに分けるべきもの | Device discovery と capture ownership | 将来の補助仕様化を許可 | `auto_register_devices()`、frame readiness、GUI preview、Runtime 実行時の所有権が複数仕様にまたがる |
| さらに分けるべきもの | LoggerPort と logging components | `LOGGING_FRAMEWORK.md` として分離済み | 現行 `LogManager` の削除、GUI sink、loguru backend、ログ保持は影響が広く、異常系・GUI/CLI 入口仕様から分けて読む必要がある |
| 統合してもよいもの | `CONFIGURATION_AND_RESOURCES.md` の settings schema と `ERROR_CANCELLATION_LOGGING.md` の settings validation | 現状は維持 | schema と例外正規化は重なるが、前者は永続化境界、後者は異常系表現であり、今は分けた方が追跡しやすい |
| 統合してもよいもの | `OBSERVABILITY_AND_GUI_CLI.md` と `ERROR_CANCELLATION_LOGGING.md` のログ event 発行 | 現状は維持 | 両仕様は `LOGGING_FRAMEWORK.md` の `UserEvent` / `TechnicalLog` を参照し、sink や backend を再定義しないことで矛盾を避ける |
| 境界が曖昧 | `MacroSettingsResolver` | 境界注記を維持 | Registry、Configuration、Runtime builder のすべてから参照される。正配置は `core\macro\settings_resolver.py`、画像 I/O とは分離する |
| 境界が曖昧 | `singletons.py` | 本書で廃止範囲を限定 | singleton ファイル自体は互換で残すが、GUI/CLI/Command からの直接 manager 利用は廃止候補である |
| 境界が曖昧 | `StaticResourceIO` | `ResourceStorePort` へ責務移管 | 互換 adapter を残さず、直接利用を移行対象として扱う |

### 3.2 廃止判断の原則

廃止候補は、維持対象の import / lifecycle 互換と、マクロ側移行を要求する項目を分けて扱う。`MacroBase`、`Command`、`DefaultCommand`、constants、`MacroStopException` は削除対象にしない。Resource I/O、settings lookup、旧 auto discovery、`DefaultCommand` 旧コンストラクタ、GUI / CLI、内部 helper、旧 executor、旧 singleton 参照、暗黙挙動は代替 Runtime 経路と受け入れテストが成立した時点で破壊的に置換してよい。

中途半端な互換資材は作らない。旧 API を残すのは、既存マクロが直接 import する場合、または同一リリース内の段階実装で一時的に必要な場合に限定する。GUI / CLI 向けには長期 adapter、互換 wrapper、旧新二重実装を残さず、移行 commit 内で呼び出し元を新 API へ寄せる。

### 3.3 レイヤー構成

| レイヤー | 維持するもの | 廃止候補にできるもの |
|----------|--------------|----------------------|
| 既存マクロ互換 | `MacroBase`, `Command`, `DefaultCommand`, constants, `MacroStopException` | Resource/settings/entrypoint の旧互換、`DefaultCommand` 旧コンストラクタ、`Command.stop()` の即時例外送出依存 |
| Entrypoint loader | manifest entrypoint、class metadata、convention discovery で package / single-file を解決 | lifecycle 二重実装、発見時インスタンス保持、`Path.cwd()` 固定探索 |
| Runtime / Ports | `MacroRuntime`, `MacroRunner`, `RunHandle`, `RunResult`, `ExecutionContext`, Port interfaces | GUI/CLI の個別 `DefaultCommand` 組み立て、旧 `create_command()` helper、余分な Command facade |
| Device adapter | 明示検出、ready 待ち、`allow_dummy` | `auto_register_devices()` 直後の暗黙参照、dummy 本番既定 |
| Settings / Resources | `MacroSettingsResolver`, `ResourceStorePort`, `SecretsStore` | `StaticResourceIO` の settings 解決、hardware 配下への恒久配置 |
| Logger | `LoggerPort`, 構造化ログ、GUI 表示イベント | loguru 直結のグローバル初期化依存 |

### 3.4 後方互換性

削除前に次を満たす。

- 既存マクロの import path、Command API、lifecycle を変更しない。
- CLI/GUI は `MacroRuntimeBuilder` と `RunResult` へ直接移行済みであり、`DefaultCommand` を個別に組み立てない。
- `MacroExecutor` は、既存マクロ互換テストが通り、GUI/CLI/テストコードが参照しない状態になったら削除する。非推奨警告、一定期間存続、import 互換 shim は作らない。
- GUI/CLI 内部 API、旧 helper、旧 worker、旧 settings 適用経路には長期の `DeprecationWarning` 期間を設けない。
- `Path.cwd()` fallback、暗黙 dummy fallback、旧 auto discovery は残さない。軽量マクロは新しい convention discovery で扱う。
- 実機なしの通常テストは fake Port で通り、実機テストは `@pytest.mark.realdevice` へ分離されている。

### 3.5 並行性・スレッド安全性

廃止候補の削除は、並行実行時の状態共有を減らす方向で行う。`MacroRegistry.reload()` と実行開始のロック、`RunHandle.cancel()` の冪等性、`FrameSourcePort.await_ready()`、`LogSinkDispatcher` の sink snapshot、settings snapshot は廃止判断の前提である。グローバル manager 直接利用を削ることで、テスト間状態汚染と GUI/CLI 間の競合を減らす。

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

### 4.2 再設計で削除する旧実装

| 対象 | 削除条件 | 代替 API | 互換影響 | テストゲート | 移行順 |
|------|----------|----------|----------|--------------|--------|
| `MacroExecutor` | CLI/GUI/テストコードが `MacroRuntime` / `MacroRegistry` / `RunHandle` へ移行し、既存マクロ互換テストが通る | `MacroRuntime`, `MacroRegistry`, `MacroFactory`, `MacroRunner`, `RunHandle` | 既存マクロへの影響なし。旧 GUI/CLI/内部テストの破壊的変更は許容する | import gate, existing macro gate, `test_macro_executor_removed`, `test_gui_cli_entrypoints_do_not_import_macro_executor` | 互換テスト追加 → GUI/CLI を Runtime へ直接移行 → 内部テスト更新 → `MacroExecutor` 削除 |
| Resource I/O legacy static 互換 | 移行ガイドに従い既存 assets / outputs を `resources\<macro_id>\assets` と `runs\<run_id>\outputs` へ移行する | `ResourceStorePort`, `RunArtifactStore`, `ResourceRef` | マクロ側の path 指定修正が必要 | `test_runtime_saves_command_images_to_run_outputs`, `test_local_run_artifact_store_saves_outputs_without_stripping_macro_prefix` | 移行ガイド作成 → 代表マクロ更新 → legacy static read/write 経路削除 |
| settings legacy fallback | 既存 settings を manifest または class metadata settings path へ移行する | `MacroSettingsResolver`, `macro.toml [macro].settings`, `MacroBase.settings_path` | マクロ側の settings 配置修正が必要。manifest は高度機能が必要な場合だけ追加 | `test_settings_static_lookup_is_not_supported`, `test_file_settings_and_exec_args_are_merged_with_exec_args_precedence` | 移行ガイド作成 → 代表マクロ更新 → static/cwd fallback 削除 |
| `DefaultCommand` 旧コンストラクタ | GUI/CLI/テスト/perf が `MacroRuntimeBuilder` または fake `ExecutionContext` fixture から得た context を渡す | `DefaultCommand(context=...)`, `tests\support\fake_execution_context.py` | 既存マクロへの影響なし。`DefaultCommand` 直接生成コードは修正が必要 | `test_default_command_rejects_legacy_constructor_args`, `test_cli_uses_runtime_and_run_result`, `test_execution_context_does_not_hold_command` | 旧コンストラクタ利用棚卸し → fake context fixture 追加 → Builder 経由へ移行 → 旧コンストラクタ引数削除 |
| `Command.stop()` の即時例外送出 | 即時例外送出を廃止し、互換引数を提供しない | `Command.stop()`, `CancellationToken.throw_if_requested()` | `cmd.stop()` 呼び出し直後に例外が出る前提のマクロは修正が必要 | `test_command_stop_requests_cancel_without_raising`, `test_command_stop_rejects_raise_immediately_argument` | 移行ガイド追記 → 代表マクロ確認 → 即時例外経路を削除 |

`MacroExecutor` には非推奨期間を設けない。削除後に `nyxpy.framework.core.macro.executor` の import 互換 shim も作らない。
`test_macro_executor_removed` は `nyxpy.framework.core.macro.executor` の import が `ModuleNotFoundError` になることを確認する。`test_gui_cli_entrypoints_do_not_import_macro_executor` は GUI/CLI entrypoint の import graph に `MacroExecutor` が含まれないことを確認する。

Resource I/O legacy static 互換と settings legacy fallback の代表マクロは `MACRO_MIGRATION_GUIDE.md` の「移行対象代表マクロ」表を正とする。本書では代表マクロ名を重複管理せず、削除条件とテストゲートだけを扱う。

#### 4.2.1 移行期間 shim と最終削除 API

移行期間に一時 shim を置く場合でも、最終状態で残してよい API と残してはいけない API を分ける。shim は次の削除条件を満たすまでの短期措置であり、新 Runtime 経路から参照してはならない。

| 対象 | 移行期間の扱い | 最終状態 | 削除条件 |
|------|----------------|----------|----------|
| `MacroExecutor` / `nyxpy.framework.core.macro.executor` | shim 不可。新 API、互換契約、移行 adapter に含めない | module import は `ModuleNotFoundError` | `test_macro_executor_removed`, `test_gui_cli_entrypoints_do_not_import_macro_executor` が green |
| `LogManager` クラス / `log_manager` module global | 旧呼び出し元置換中だけ内部 shim を許可。ただし Runtime / Command / GUI/CLI 新経路から参照しない | 削除。互換 shim も残さない | `test_legacy_log_manager_removed`, `test_log_manager_call_sites_removed` が green |
| `singletons.py` の `serial_manager` / `capture_manager` / settings globals | 旧 GUI/CLI 経路が残る間だけ互換 shim として保持可 | 新 Runtime 経路から直接参照しない。必要ならテスト用 reset だけを残す | `test_new_runtime_does_not_import_singletons` と GUI/CLI 移行テストが green |
| `reset_for_testing()` | shim が残る間は既存 singleton 状態の初期化に使う | Runtime / Port 実体は fixture lifetime で破棄し、`reset_for_testing()` は旧 shim 初期化だけに限定 | 旧 singleton shim 削除時に対象を空にするか、関数自体の削除を別途判断 |
| `StaticResourceIO` 直接利用 | 旧呼び出し元置換中だけ内部 adapter の参照元として許可 | 公開互換 shim は残さない | Resource I/O 移行テストと `test_command_save_and_load_image_use_resource_store` が green |
| `load_macro_settings()` 旧 fallback | shim 不可。`MacroSettingsResolver` へ接続する場合も `static` / `cwd` fallback は復活させない | 旧 fallback 削除 | `test_macro_settings_resolver_does_not_read_legacy_static_settings` が green |

### 4.3 廃止候補一覧

| 候補 | 削除条件 | 代替 API | 互換影響 | テストゲート | 移行順 |
|------|----------|----------|----------|--------------|--------|
| `singletons.py` のグローバル manager 直接利用 | GUI/CLI/Command/Runtime が `serial_manager` / `capture_manager` / `log_manager` / `global_settings` / `secrets_settings` を直接参照しない | `MacroRuntimeBuilder`, `ControllerOutputPort`, `FrameSourcePort`, `DeviceDiscoveryService`, `SettingsStore`, `SecretsStore`, `LoggerPort` | 既存マクロへの影響なし。GUI/CLI の設定適用経路は破壊的変更を許容する | `test_cli_uses_runtime_and_run_result`, `test_main_window_uses_run_handle`, `reset_for_testing` 関連テスト | 直接参照箇所を洗い出し → composition root 経由へ置換 → 旧 GUI/CLI 参照を削除 → 新規直接利用を禁止 |
| `auto_register_devices()` の暗黙非同期検出 API | serial/capture 検出が `detect(timeout_sec)` または `DeviceDiscoveryResult` で完了、失敗、タイムアウトを返す | `DeviceDiscoveryService.detect(timeout_sec)`, `ControllerOutputPortFactory`, `FrameSourcePortFactory`, `MacroRuntimeBuilder.detect_devices()` | CLI/GUI の検出表示は変更されるが、既存マクロには影響なし | `test_cli_device_detection_waits_until_complete`, `test_frame_source_await_ready_success_after_first_frame`, hardware detection test | 明示検出 API 追加 → CLI/GUI builder へ移行 → 旧 GUI/CLI 参照を同時削除 |
| dummy fallback の本番既定挙動 | `runtime.allow_dummy=False` が既定になり、テストと明示 dry-run だけが dummy Port を選べる | `RuntimeOptions.allow_dummy`, `DummyControllerOutputPort`, `DummyFrameSourcePort` | 実機未接続を成功扱いしていた CLI/GUI 操作は失敗表示に変わる。既存マクロのコード変更は不要 | `test_runtime_builder_disallows_dummy_by_default`, `test_runtime_allows_dummy_when_explicit`, hardware smoke test | 設定項目追加 → builder で明示判定 → GUI/CLI 表示更新 → 暗黙 fallback を新 Runtime 経路から削除 |
| `StaticResourceIO` の直接利用 | Resource I/O を Port 化し、`StaticResourceIO` 互換 adapter を作らない | `ResourceStorePort`, `RunArtifactStore`, `ResourcePathGuard` (`core\io\resources.py`) | `StaticResourceIO` 直接 import 利用者は修正が必要 | `test_resource_store_rejects_path_escape`, `test_resource_store_raises_when_imwrite_returns_false`, `test_command_save_and_load_image_use_resource_store` | Port 実装追加 → `Command` を Port 経由へ移行 → `StaticResourceIO` 参照を削除 |
| GUI/CLI 個別 Command 組み立て | CLI と GUI が `DefaultCommand` を直接構築せず、Runtime builder から context を作る | `RuntimeBuildRequest`, `MacroRuntimeBuilder.build()`, `MacroRuntimeBuilder.run()`, `MacroRuntimeBuilder.start()`, `DefaultCommand(context=...)` | 既存マクロへの影響なし。CLI/GUI の内部構築とテストは破壊的変更を許容する | `test_cli_uses_runtime_and_run_result`, `test_main_window_uses_run_handle`, `test_main_window_cancel_calls_handle_cancel` | Runtime builder 実装 → CLI 移行 commit で旧 `create_command()` を削除 → GUI 移行 commit で旧 worker/command 構築を削除 |
| loguru 直結の `LogManager` グローバル初期化 | `LogManager` クラスと `log_manager` グローバルを内部 API とみなして完全削除し、Runtime は composition root から `LoggerPort` を受け取る | `LoggerPort`, `DefaultLogger`, `LogSinkDispatcher`, `LogBackend`, `LogSanitizer` | `Command.log()` は維持。保存ログ形式と GUI 表示イベントは変わる。`LogManager` / `log_manager.log()` の互換 shim は作らない | `test_default_logger_emits_structured_log_with_run_context`, `test_gui_sink_exception_is_logged_and_ignored`, `test_technical_log_masks_secrets`, `test_legacy_log_manager_removed`, `test_log_manager_call_sites_removed` | 構造化ログ API 追加 → dispatcher/backend/sanitizer 分離 → `src\nyxpy\gui\main_window.py`、`src\nyxpy\cli\run_cli.py`、`src\nyxpy\framework\core\hardware\capture.py`、通知実装、既存 logger テストを置換 → GUI sink 分離 → `LogManager` と module global を削除 |
| `Path.cwd()` 固定の project root 解決 | `project_root` が Runtime builder / Registry / SettingsResolver へ明示され、`cwd` fallback を持たない | `MacroRegistry(project_root=...)`, `MacroSettingsResolver(project_root)`, `MacroRuntimeBuilder(project_root=...)` | `cwd` 前提の外部起動方法は修正が必要 | `test_registry_uses_explicit_project_root`, `test_macro_settings_resolver_does_not_read_legacy_static_settings` | 明示 root 引数追加 → GUI/CLI 起点で渡す → 固定 `Path.cwd()` と fallback を削除 |
| 恒久的な `sys.path` 変更 | entrypoint import が必要な範囲だけ context manager で一時追加され、load 後に復元される | `EntryPointLoader` の scoped import path 管理 | manifest entrypoint または convention discovery で package / single-file とも実行可能 | `test_registry_reload_restores_sys_path`, `test_migrated_repository_macros_load_with_optional_manifest` | scoped loader 実装 → reload テスト追加 → 恒久 append を削除 |
| 曖昧な class 名 alias 選択 | 衝突時に `AmbiguousMacroError` と候補 ID を返し、後勝ち上書きを行わない | `Qualified Macro ID`, `MacroDefinition.id`, `MacroRegistry.resolve()` | class 名だけで選んでいた外部コードは修正が必要。既存マクロ本体は変更不要 | `test_class_name_collision_requires_qualified_id`, `test_class_name_alias_is_available_when_unique` | ID 生成追加 → 一意 alias 維持 → 衝突時診断追加 → 後勝ち上書きを削除 |
| `ResourceStorePort` による settings TOML 探索 | `MacroSettingsResolver` が settings を解決し、ResourceStore は画像 I/O だけを扱う | `MacroSettingsResolver.resolve()`, `MacroSettingsResolver.load()` | `static\<macro_name>\settings.toml` 互換は削除 | `test_settings_static_lookup_is_not_supported`, `test_file_settings_and_exec_args_are_merged_with_exec_args_precedence` | settings resolver 実装 → ResourceStore から settings 探索を排除 |
| GUI スレッドからの `cmd.stop()` 呼び出し | GUI cancel が `RunHandle.cancel()` または `request_cancel()` だけを呼び、GUI スレッドで例外を送出しない | `RunHandle.cancel()`, `CancellationToken.request_cancel()` | GUI 内部挙動の変更。既存マクロの `Command.stop()` は維持 | `test_main_window_cancel_calls_handle_cancel`, `test_main_window_poll_updates_status_from_run_result` | RunHandle 導入 → GUI cancel 移行 → GUI からの直接 `cmd.stop()` を削除 |

`runtime.allow_dummy` の優先順位と明示経路は `RUNTIME_AND_IO_PORTS.md` の `allow_dummy` 決定表を正とする。本書では暗黙 fallback の削除条件だけを扱う。

### 4.4 設定パラメータ

| パラメータ | 型 | デフォルト | 所有者 | 説明 |
|------------|-----|-----------|--------|------|
| `runtime.allow_dummy` | `bool` | `False` | `RuntimeOptions` | 本番 Runtime で dummy Port を許可するか |
| `runtime.device_detection_timeout_sec` | `float` | `5.0` | `RuntimeOptions` | 明示デバイス検出の最大待機秒数 |
| `runtime.frame_ready_timeout_sec` | `float` | `3.0` | `RuntimeOptions` | 初回フレーム readiness の最大待機秒数 |
| `migration.require_manifest_for_ambiguous_entrypoint` | `bool` | `True` | `MacroRegistry` | convention discovery が曖昧な場合に manifest entrypoint を要求するか |

### 4.5 エラーハンドリング

| 例外クラス | 発生条件 |
|------------|----------|
| `DeprecationWarning` | 実装時に一時 shim を置く場合に限り、移行先がある非推奨経路を利用した |
| `ConfigurationError` | `allow_dummy=False` で dummy を選択、明示 project root 不正、通知 secret の入力元違反 |
| `DeviceDetectionTimeoutError` | 明示検出 API が timeout 内に完了しない |
| `AmbiguousMacroError` | class 名 alias が複数 `MacroDefinition` に一致した |
| `ResourcePathError` | `ResourceStorePort` が static root 外参照を拒否した |

Resource I/O、settings lookup、旧 auto discovery、`DefaultCommand` 旧コンストラクタは、互換 shim を長期維持しない。必要な場合でも移行作業中の短期 shim に限定し、最終仕様では削除する。GUI / CLI 内部経路、旧 worker、旧 helper、旧 settings 適用処理は警告期間を置かず、新 Runtime 入口へ置換した commit 内で削除する。

### 4.6 シングルトン管理

`singletons.py` の既存 `serial_manager`、`capture_manager`、`global_settings`、`secrets_settings`、`log_manager` は互換 shim として段階廃止する。新 Runtime 経路では GUI/CLI/Command/Runtime がこれらを直接参照せず、GUI / CLI composition root が `MacroRuntimeBuilder`、Port factory、device discovery、settings/secrets store、logging components を必要な lifetime で生成する。`MacroRuntimeBuilder`、`MacroRuntime`、`MacroRegistry`、`MacroSettingsResolver`、`ResourceStorePort`、`RunHandle`、Port 実体はシングルトンにしない。

`reset_for_testing()` は shim が残る間だけ既存 singleton の再生成、GUI sink snapshot、device discovery cache、settings snapshot を初期化できるようにする。`MacroRuntime`、`RunHandle`、Port 実体はシングルトンにせず、テスト fixture が実行ごとに生成・破棄する。

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| ユニット | `test_deprecation_candidates_do_not_include_compat_contract` | 廃止候補が `MacroBase` / `Command` / `DefaultCommand` / constants / `MacroStopException` を削除対象にしていない |
| ユニット | `test_no_gui_cli_reference_to_macro_executor` | GUI/CLI が `MacroExecutor` を経由せず Runtime を直接利用する |
| ユニット | `test_runtime_builder_disallows_dummy_by_default` | 本番既定で dummy Port が選択されない |
| ユニット | `test_runtime_allows_dummy_when_explicit` | `allow_dummy=True` の明示時だけ dummy Port を使える |
| ユニット | `test_cli_device_detection_waits_until_complete` | CLI が非同期検出直後の不完全な一覧を参照しない |
| ユニット | `test_registry_uses_explicit_project_root` | `Path.cwd()` 固定ではなく明示 project root を使う |
| ユニット | `test_registry_reload_restores_sys_path` | entrypoint loader が `sys.path` を恒久変更しない |
| ユニット | `test_resource_store_rejects_path_escape` | root 外リソース参照を拒否する |
| ユニット | `test_logger_port_avoids_global_runtime_dependency` | Runtime が `log_manager` グローバルへ直接依存しない |
| 結合 | `test_migrated_repository_macros_load_with_optional_manifest` | 移行後の代表マクロが manifest あり / なしの両方でロードされる |
| 結合 | `test_file_settings_and_exec_args_are_merged_with_exec_args_precedence` | settings と実行引数が Runtime builder で merge され、実行引数が優先される |
| 結合 | `test_cli_uses_runtime_and_run_result` | CLI が `DefaultCommand` を直接構築せず Runtime builder を使い、`RunResult` から終了コードを決める |
| GUI | `test_main_window_uses_run_handle` | GUI が `RunHandle` で開始、完了、中断を扱う |
| GUI | `test_main_window_cancel_does_not_raise_in_gui_thread` | GUI cancel が呼び出し元スレッドで例外を送出しない |
| ハードウェア | `test_runtime_realdevice_without_dummy_fallback` | `@pytest.mark.realdevice`。実機実行で dummy fallback を使わない |
| 性能 | `test_registry_reload_100_macros_perf` | 廃止候補整理後も 100 件 reload が目標時間内に完了する |

廃止判断前の最小ゲートは次の通りである。

```powershell
uv run pytest tests\unit\framework\macro\test_import_contract.py
uv run pytest tests\integration\test_migrated_macro_compat.py
uv run pytest tests\integration\test_macro_runtime_entrypoints.py
uv run pytest tests\integration\test_cli_runtime_adapter.py
uv run pytest tests\gui\test_main_window.py tests\gui\test_log_pane_user_event.py
uv run ruff check .
```

本書作成時の文書検証は次を使う。

| コマンド | 検証内容 |
|----------|----------|
| `git diff --check` | 行末空白、混在インデント、patch として不正な空白を検出する |
| `rg "T[O]D[O]|T[B]D|x{3}|\[T[O]D[O]\]" spec\framework\rearchitecture` | 未解決 placeholder と仮テキストを検出する。一致なしを合格とする |
| `rg "^## ..."` | 必須 6 セクションが存在することを確認する。6 行が出ることを合格とする |

```powershell
git diff --check
rg "T[O]D[O]|T[B]D|x{3}|\[T[O]D[O]\]" spec\framework\rearchitecture
rg "^## (1\. 概要|2\. 対象ファイル|3\. 設計方針|4\. 実装仕様|5\. テスト方針|6\. 実装チェックリスト)\r?$" spec\framework\rearchitecture\DEPRECATION_AND_MIGRATION.md
```

## 6. 実装チェックリスト

本書は廃止判断を固定する仕様である。実装タスクと検証タスクは `IMPLEMENTATION_PLAN.md` のフェーズ別チェックリストを正とする。

### 6.1 仕様チェックリスト

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
- [x] `StaticResourceIO` 直接利用の削除方針を記載
- [x] GUI/CLI 個別 Command 組み立て廃止方針を記載
- [x] `LogManager` グローバル初期化依存の縮退方針を記載
- [x] `Path.cwd()` 固定 project root 解決の廃止方針を記載
- [x] 追加の廃止候補を整理
- [x] テストゲートと文書検証コマンドを記載
