# フレームワーク再設計 実装計画書

> **文書種別**: 実装計画。実装順序と完了条件を定義する。型・API・責務の正本は関連仕様書を参照する。
> **対象モジュール**: `src\nyxpy\framework\core\macro\`, `src\nyxpy\framework\core\runtime\`, `src\nyxpy\framework\core\io\`, `src\nyxpy\cli\`, `src\nyxpy\gui\`  
> **目的**: 既存ユーザーマクロのソース変更を不要にしたまま、実行中核を `MacroRuntime` / `MacroRunner` / `MacroRegistry` / `MacroFactory` へ段階移行する。  
> **関連ドキュメント**: `FW_REARCHITECTURE_OVERVIEW.md`, `ARCHITECTURE_DIAGRAMS.md`, `MACRO_COMPATIBILITY_AND_REGISTRY.md`, `RUNTIME_AND_IO_PORTS.md`, `RESOURCE_FILE_IO.md`, `LOGGING_FRAMEWORK.md`, `ERROR_CANCELLATION_LOGGING.md`, `OBSERVABILITY_AND_GUI_CLI.md`, `DEPRECATION_AND_MIGRATION.md`, `TEST_STRATEGY.md`  
> **破壊的変更**: 既存ユーザーマクロの公開互換契約に対してはなし。`MacroExecutor`、GUI/CLI 内部入口、singleton 直接利用、暗黙 fallback は互換維持対象に含めず、新 API へ置換または削除する。

## 1. 概要

### 1.1 目的

本計画は、フレームワーク再設計仕様を実装順序と検証順序へ落とし込むための実行計画である。仕様書で定義された責務分離を一括置換せず、互換テストを先に固定してから Registry、Factory、Runner、Runtime、Ports、CLI、GUI の順に移行する。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| Compatibility Contract | 既存マクロが依存している import path、ライフサイクル、Command API、設定読み込み、例外捕捉を維持する契約 |
| MacroBase | ユーザー定義マクロの抽象基底クラス。`initialize(cmd, args)` / `run(cmd)` / `finalize(cmd)` を維持する |
| Command | マクロから見える操作 API。`press`、`wait`、`capture`、`save_img`、`notify` などの既存メソッドを維持する |
| DefaultCommand | 既存 import path と旧コンストラクタ互換を持つ `Command` 実装。移行後は `CommandFacade` または Ports へ委譲する |
| MacroExecutor | 既存 GUI/CLI とテストの旧入口。再設計後の公開 API・互換契約・移行 adapter には含めず削除する |
| MacroRegistry | マクロの発見、安定 ID、別名、診断、設定解決を管理し、実行インスタンスを保持しないコンポーネント |
| MacroFactory | `MacroDefinition` から実行ごとに新しい `MacroBase` インスタンスを生成するコンポーネント |
| MacroRunner | `initialize -> run -> finalize` の順序、例外正規化、中断正規化、`RunResult` 生成を担当するコンポーネント |
| MacroRuntime | registry 解決、factory 呼び出し、Ports 準備、`Command` 生成、同期・非同期実行、リソース解放を統括する新実行中核 |
| RunResult | 実行結果を表す値。`RunStatus`、開始・終了時刻、`ErrorInfo`、解放時警告を保持する |
| RunHandle | 非同期実行の中断要求、完了待ち、結果取得を提供するハンドル |
| ExecutionContext | 1 回の実行に必要な `run_id`、`macro_name`、Ports、設定、実行引数、`CancellationToken` を束ねる値。`Command` は保持しない |
| Ports/Adapters | Runtime 中核からハードウェア、設定、通知、ログ、GUI/CLI 依存を隔離する境界 |
| CommandFacade | 既存 `Command` API を Ports へ委譲する実装 |
| MacroSettingsResolver | manifest settings と `static\<macro_name>\settings.toml` 互換を解決するコンポーネント。Resource File I/O から分離する |
| Resource File I/O | read-only assets と writable outputs の配置、path guard、atomic write、overwrite policy を扱う境界 |
| MacroResourceScope | 1 つのマクロ ID に紐づく assets root と legacy static root を表す値 |
| RunArtifactStore | 1 回の実行 ID に紐づく outputs root へ成果物を書き込む Port |

### 1.3 背景・問題

現行実装では、マクロ発見、実行インスタンス生成、ライフサイクル実行、デバイス・通知・ログの組み立てが `MacroExecutor`、`DefaultCommand`、CLI、GUI に分散している。`MacroExecutor` は発見時にマクロをインスタンス化するため、実行間で状態が残りやすく、ロード失敗診断やクラス名衝突の扱いも不足している。

一方、既存ユーザーマクロは `MacroBase`、`Command`、constants、`MacroStopException`、`static\<macro_name>\settings.toml` に直接依存している。再設計の実装では、内部構造より先に互換契約をテストで固定し、既存マクロのソース変更を要求しないことを最優先にする。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| 既存ユーザーマクロのソース変更 | 内部改修次第で必要化する恐れがある | 0 件 |
| 互換契約の検証 | 一部の executor テストと暗黙の import 維持に依存 | import、シグネチャ、Command API、設定読み込み、代表マクロロードをゲート化 |
| 実行ごとの状態分離 | reload 時に生成したインスタンスを再利用 | `MacroFactory.create()` で毎回新規生成 |
| GUI/CLI の Command 構築 | CLI と GUI に重複 | `MacroRuntimeBuilder` と Ports/Adapters に集約 |
| 実行結果の表現 | 例外とログ文字列に依存 | `RunResult` / `ErrorInfo` / `RunHandle` で表現 |
| キャンセル応答 | `wait()` 中に停止確認が遅れる | `CancellationToken` aware wait で即応性を検証 |
| 実機不要テスト | singleton と具象デバイス依存の影響を受ける | fake Port と dummy 実装で Runtime 中核を検証 |

### 1.5 着手条件

- `FW_REARCHITECTURE_OVERVIEW.md`、`ARCHITECTURE_DIAGRAMS.md`、`MACRO_COMPATIBILITY_AND_REGISTRY.md`、`RUNTIME_AND_IO_PORTS.md`、`RESOURCE_FILE_IO.md`、`LOGGING_FRAMEWORK.md`、`ERROR_CANCELLATION_LOGGING.md`、`OBSERVABILITY_AND_GUI_CLI.md`、`DEPRECATION_AND_MIGRATION.md` の方針を実装の正とする。
- 既存マクロの `MacroBase` / `Command` / constants / `MacroStopException` import path を変更しない。
- 既存マクロの `initialize(cmd, args)` / `run(cmd)` / `finalize(cmd)` を変更しない。
- 既存 `Command` メソッド名、主要キーワード引数、`DefaultCommand` import path を変更しない。
- 実装前に `uv run pytest tests\unit\` のベースラインを確認する。
- 実機依存テストは `@pytest.mark.realdevice` で通常テストから分離する。
- `MacroExecutor` は既存マクロ互換 API ではない。旧 GUI/CLI/テストの参照を新 Runtime 入口へ移行し、import 互換 shim を作らず削除する。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `spec\framework\rearchitecture\IMPLEMENTATION_PLAN.md` | 新規 | 本実装計画書 |
| `spec\framework\rearchitecture\LOGGING_FRAMEWORK.md` | 新規 | ロギング再設計の実装順序と参照先 |
| `tests\unit\framework\macro\test_legacy_imports.py` | 新規 | import path、公開シグネチャ、Command API、例外互換のゲートを追加 |
| `tests\unit\framework\macro\test_registry.py` | 新規 | Registry、manifest、legacy loader、診断、設定解決を検証 |
| `tests\unit\framework\runtime\test_macro_factory.py` | 新規 | 実行ごとの新規インスタンス生成を検証 |
| `tests\unit\framework\runtime\test_macro_runner.py` | 新規 | lifecycle、`finalize` 保証、中断、失敗、`RunResult` を検証 |
| `tests\unit\framework\runtime\test_execution_context.py` | 新規 | `ExecutionContext`、shallow copy、`Command` 非保持を検証 |
| `tests\unit\framework\runtime\test_command_facade.py` | 新規 | `CommandFacade` と fake Port の委譲規則を検証 |
| `tests\unit\framework\io\test_ports.py` | 新規 | Port 契約、resource path 検証、frame readiness を検証 |
| `tests\integration\test_macro_runtime_entrypoints.py` | 新規 | GUI/CLI/テスト入口が `MacroExecutor` を経由せず Runtime を使うことを検証 |
| `tests\integration\test_existing_macros_compat.py` | 新規 | 代表マクロのロード、設定マージ、lifecycle 互換を検証 |
| `tests\integration\test_cli_runtime_adapter.py` | 新規 | CLI が Runtime 経由で実行し、終了コードへ変換することを検証 |
| `tests\gui\test_main_window_runtime_adapter.py` | 新規 | GUI が `RunHandle` と `RunResult` を UI 状態へ反映することを検証 |
| `tests\hardware\test_macro_runtime_realdevice.py` | 新規 | 実機接続時の serial/capture/runtime 実行を検証 |
| `tests\perf\test_macro_discovery_perf.py` | 新規 | registry reload と discovery の性能を検証 |
| `src\nyxpy\framework\core\macro\base.py` | 変更 | import path と lifecycle signature を維持。移動する場合も re-export を先に置く |
| `src\nyxpy\framework\core\macro\command.py` | 変更 | `Command` / `DefaultCommand` 互換を維持し、内部を `CommandFacade` / Ports へ段階移行 |
| `src\nyxpy\framework\core\macro\exceptions.py` | 変更 | `FrameworkError` 階層、`MacroCancelled`、`MacroStopException` adapter、`ErrorInfo` を定義 |
| `src\nyxpy\framework\core\macro\decorators.py` | 変更 | `@check_interrupt` を新 `CancellationToken` と `MacroCancelled` へ接続 |
| `src\nyxpy\framework\core\macro\executor.py` | 削除 | GUI/CLI/テストの参照移行後に削除。import 互換 shim は作らない |
| `src\nyxpy\framework\core\macro\registry.py` | 新規 | `MacroRegistry`、`MacroDefinition`、`MacroFactory`、診断モデルを定義 |
| `src\nyxpy\framework\core\macro\legacy_adapter.py` | 新規 | legacy package、legacy single file、manifest opt-in の探索を担当 |
| `src\nyxpy\framework\core\macro\settings_resolver.py` | 新規 | settings TOML 解決を画像リソースから分離 |
| `src\nyxpy\framework\core\runtime\__init__.py` | 新規 | Runtime 公開 API を再 export |
| `src\nyxpy\framework\core\runtime\context.py` | 新規 | `ExecutionContext`、`RunContext`、`RuntimeOptions` を定義 |
| `src\nyxpy\framework\core\runtime\result.py` | 新規 | `RunStatus`、`RunResult`、`ErrorInfo` を定義または再 export |
| `src\nyxpy\framework\core\runtime\runner.py` | 新規 | `MacroRunner` の lifecycle 実行と `RunResult` 生成を実装 |
| `src\nyxpy\framework\core\runtime\handle.py` | 新規 | `RunHandle` とスレッド実装を定義 |
| `src\nyxpy\framework\core\runtime\runtime.py` | 新規 | `MacroRuntime` の同期実行、非同期実行、リソース解放を実装 |
| `src\nyxpy\framework\core\runtime\builder.py` | 新規 | CLI/GUI 設定から Runtime と Ports を組み立てる |
| `src\nyxpy\framework\core\io\__init__.py` | 新規 | Port と adapter の再 export |
| `src\nyxpy\framework\core\io\ports.py` | 新規 | `ControllerOutputPort`、`FrameSourcePort`、`ResourceStorePort`、`NotificationPort`、`LoggerPort` を定義 |
| `src\nyxpy\framework\core\io\adapters.py` | 新規 | 既存 serial/capture/resource/notification/logger への adapter を実装 |
| `src\nyxpy\framework\core\utils\cancellation.py` | 変更 | 理由、要求元、時刻、`throw_if_requested()`、即時 wait を追加 |
| `src\nyxpy\framework\core\utils\helper.py` | 変更 | `load_macro_settings()` と `parse_define_args()` を新 resolver / error へ接続 |
| `src\nyxpy\framework\core\logger\log_manager.py` | 変更 | `LOGGING_FRAMEWORK.md` に従い `LoggerPort`、sink、実行 context、互換 adapter を実装 |
| `src\nyxpy\framework\core\logger\events.py` | 新規 | `LogEvent`、`TechnicalLog`、`UserEvent`、`RunLogContext` を定義 |
| `src\nyxpy\framework\core\logger\ports.py` | 新規 | `LoggerPort`、`LogSink`、backend 差し替え境界を定義 |
| `src\nyxpy\framework\core\logger\sinks.py` | 新規 | file、console、GUI、test sink を実装 |
| `src\nyxpy\framework\core\settings\global_settings.py` | 変更 | schema 検証と Runtime 設定項目を整理 |
| `src\nyxpy\framework\core\settings\secrets_settings.py` | 変更 | 通知設定の唯一の入力元と secret マスクを整理 |
| `src\nyxpy\framework\core\api\notification_handler.py` | 変更 | 通知失敗を構造化ログへ記録し、マクロ失敗へ伝播させない |
| `src\nyxpy\framework\core\singletons.py` | 変更 | 既存 singleton を維持し、Runtime/Port 関連状態のリセット点を整理 |
| `src\nyxpy\cli\run_cli.py` | 変更 | `MacroRuntimeBuilder` と `RunResult` ベースの CLI adapter へ移行 |
| `src\nyxpy\gui\main_window.py` | 変更 | `RunHandle` / `RunResult` ベースの GUI adapter へ移行 |

## 3. 設計方針

### 3.1 実装計画の位置づけ

本書は仕様の追加定義ではなく、既存仕様を壊さずに実装する順序と検証ゲートを定義する。各フェーズは「互換テストを追加し、最小の実装単位を導入し、GUI/CLI/テストを新入口に寄せ、最後に旧実装を削除する」流れで進める。

### 3.2 依存順序

| 順序 | フェーズ | 依存 |
|------|----------|------|
| 1 | ベースライン・互換テスト追加 | なし |
| 2 | Registry/Factory 導入 | フェーズ 1 |
| 3 | Runner/RunResult/Error/Cancellation 導入 | フェーズ 1、2 |
| 4 | Runtime/CommandFacade 導入 | フェーズ 2、3 |
| 5 | Settings/Resource 分離 | フェーズ 2、4 |
| 5A | Resource File I/O 再設計 | フェーズ 4、5 |
| 6 | Logging Framework 再設計 | フェーズ 3、4、5 |
| 7 | Ports/Adapters 導入 | フェーズ 4、5、5A、6 |
| 8 | CLI 移行 | フェーズ 4、6、7 |
| 9 | GUI 移行 | フェーズ 4、6、7、8 の知見 |
| 10 | MacroExecutor 削除 | フェーズ 8、9 |
| 11 | ドキュメント・移行ガイド整理 | 全フェーズ |

### 3.3 互換性ゲート

各フェーズの完了判定前に、次のゲートを満たす。

| ゲート | 判定内容 |
|--------|----------|
| Import gate | `MacroBase`、`Command`、`DefaultCommand`、`MacroStopException`、constants が既存 path から import できる。`MacroExecutor` は既存マクロ互換 API ではないため含めない |
| Signature gate | `initialize(cmd, args)`、`run(cmd)`、`finalize(cmd)`、主要 `Command` メソッドの呼び出し互換を維持する。`MacroExecutor.execute()` は互換対象に含めない |
| Lifecycle gate | 成功、失敗、中断のいずれでも `finalize(cmd)` が可能な限り 1 回呼ばれる |
| Settings gate | `static\<macro_name>\settings.toml` を読み、`exec_args` が file settings より優先される |
| Existing macro gate | 代表マクロ `frlg_id_rng`、`frlg_initial_seed`、`frlg_gorgeous_resort`、`frlg_wild_rng` がソース変更なしでロードされる |
| MacroExecutor removal gate | `test_macro_executor_removed` と `test_gui_cli_do_not_import_macro_executor` で、旧 executor の import 互換 shim と GUI/CLI 参照が残っていないことを検証する |
| Cancellation gate | 既存 `MacroStopException` は `except MacroStopException` で捕捉でき、新中断も `RunStatus.CANCELLED` に正規化される |
| Core isolation gate | `nyxpy.framework.*` から `nyxpy.gui`、`nyxpy.cli`、個別マクロへの静的依存を追加しない |
| No macro edit gate | `macros\` 配下の既存ユーザーマクロを互換維持目的で編集しない |
| Deprecation gate | `DEPRECATION_AND_MIGRATION.md` の削除条件、代替 API、互換影響、テストゲート、移行順を満たす |

### 3.4 コミット分割方針

コミットは Conventional Commits 形式を使い、件名は日本語で記述する。コミット本文には、その変更が必要な理由を残す。大きなフェーズでも「テストで契約を固定するコミット」と「実装コミット」を分ける。

| 例 | 理由として本文に残す内容 |
|----|--------------------------|
| `test(framework): 既存マクロ互換契約を固定` | 再設計前に import path、シグネチャ、代表マクロロードを固定し、以後の内部置換で破壊を検出するため |
| `feat(macro): Registry と Factory を導入` | 発見時インスタンス生成をやめ、実行ごとの状態分離とロード診断を可能にするため |
| `feat(runtime): Runner と RunResult を導入` | lifecycle 実行、例外、中断、結果表現を `MacroExecutor` から分離するため |
| `feat(runtime): MacroRuntime と CommandFacade を追加` | CLI/GUI の重複構築を減らし、実行中核を単一の組み立て点へ寄せるため |
| `refactor(macro): settings 解決と Resource File I/O を分離` | settings TOML 探索と assets / outputs 保存の責務混在を解消するため |
| `feat(logger): ロギング基盤を LoggerPort と sink へ再設計` | ユーザー表示と技術ログを分離し、backend 差し替えと実行 context 追跡を可能にするため |
| `feat(io): Runtime 用 Ports と既存実装 adapter を追加` | 実機なしテストとハードウェア境界の差し替えを可能にするため |
| `refactor(cli): CLI 実行を MacroRuntime 経由へ移行` | 終了コードと通知設定を `RunResult` / `SecretsSettings` に統一するため |
| `refactor(gui): GUI 実行を RunHandle 経由へ移行` | GUI スレッドから例外を送出せず、完了・中断・失敗を構造化結果で扱うため |
| `refactor(macro): MacroExecutor を削除` | GUI/CLI/テストを新 Runtime 入口へ統一し、旧入口の二重実装と互換 shim を残さないため |
| `docs(framework): 再設計の移行ガイドを整理` | マクロ作者と保守者が新旧方式の境界を確認できるようにするため |

### 3.5 ロールバック原則

- 互換ゲートが落ちた場合は、そのフェーズの実装コミットを戻し、テスト追加コミットは残す。
- `DefaultCommand`、CLI、GUI は旧経路へ戻せるよう、移行直後は adapter 分岐を小さく保つ。`MacroExecutor` は削除対象であり、復旧が必要な場合は実装コミット単位で戻す。
- Registry/Factory は旧 `MacroExecutor` の探索処理へ戻せるよう、既存 API の戻り値と例外形式を先に保持する。
- Ports/Adapters は具象実装の移管前に fake Port で契約を固定し、問題時は `DefaultCommand` の旧依存保持へ戻す。
- GUI/CLI 移行は中核 Runtime の単体テストが通ることを前提にし、UI 変更と Runtime 変更を同じコミットに混ぜない。

## 4. 実装仕様

### 4.1 フェーズ 1: ベースライン・互換テスト追加

| 項目 | 内容 |
|------|------|
| 目的 | 内部再設計前に、既存ユーザーマクロが依存する公開面をテストで固定する |
| 対象ファイル | `tests\unit\framework\macro\test_legacy_imports.py`, `tests\integration\test_existing_macros_compat.py`, 既存 executor / GUI reload テスト |
| 完了条件 | import gate、signature gate、settings gate、existing macro gate が自動テストで判定できる |
| テスト | `uv run pytest tests\unit\framework\macro\test_legacy_imports.py`, `uv run pytest tests\integration\test_existing_macros_compat.py`, `uv run pytest tests\unit\executor\test_executor.py` |
| リスク | 既存テスト配置と現行 import 形がずれ、実装前から失敗する可能性がある |
| ロールバック方針 | 本フェーズは実装を変えない。現行仕様と異なるテストだけを修正し、互換契約の弱体化はしない |

追加する主な検証は次である。

- `from nyxpy.framework.core.macro.base import MacroBase`
- `from nyxpy.framework.core.macro.command import Command, DefaultCommand`
- `from nyxpy.framework.core.macro.exceptions import MacroStopException`
- `from nyxpy.framework.core.constants import Button, Hat, LStick, RStick, KeyType`
- `Command` の既存メソッド名と主要キーワード引数
- `MacroExecutor` が新 API、互換契約、GUI/CLI/テスト入口に残っていないことの削除確認
- `static\<macro_name>\settings.toml` と `exec_args` 優先マージ
- 代表マクロのソース変更なしロード

### 4.2 フェーズ 2: Registry/Factory 導入

| 項目 | 内容 |
|------|------|
| 目的 | マクロ発見、ID、別名、ロード診断、settings 解決、実行ごとのインスタンス生成を `MacroExecutor` から分離する |
| 対象ファイル | `src\nyxpy\framework\core\macro\registry.py`, `legacy_adapter.py`, `settings_resolver.py`, `executor.py`, `utils\helper.py`, `tests\unit\framework\macro\test_registry.py`, `tests\unit\framework\runtime\test_macro_factory.py` |
| 完了条件 | legacy package、legacy single file、manifest opt-in を `MacroDefinition` として登録でき、`MacroFactory.create()` が毎回新しい `MacroBase` インスタンスを返す |
| テスト | `test_registry_loads_legacy_package_macro`, `test_registry_loads_legacy_single_file_macro`, `test_registry_loads_manifest_macro`, `test_class_name_collision_requires_qualified_id`, `test_load_failure_is_reported_without_stopping_reload`, `test_execute_creates_new_instance_each_time` |
| リスク | `cwd` / `sys.path` 依存、相対 import、クラス名衝突、ロード失敗時の継続処理が既存挙動とずれる |
| ロールバック方針 | `MacroExecutor` の公開 API は旧実装に戻し、追加した Registry は未使用状態で残せる形にする。互換テストは残す |

この段階では GUI/CLI が参照する一覧取得と実行対象解決を `MacroRegistry` から行える状態にする。`MacroExecutor.reload_macros()` や `macros` facade は移行対象に含めない。

### 4.3 フェーズ 3: Runner/RunResult/Error/Cancellation 導入

| 項目 | 内容 |
|------|------|
| 目的 | lifecycle 実行、例外分類、中断正規化、`RunResult` 生成を `MacroRunner` に集約する |
| 対象ファイル | `src\nyxpy\framework\core\runtime\result.py`, `runner.py`, `context.py`, `handle.py`, `src\nyxpy\framework\core\macro\exceptions.py`, `decorators.py`, `src\nyxpy\framework\core\utils\cancellation.py`, `tests\unit\framework\runtime\test_macro_runner.py` |
| 完了条件 | 成功、失敗、中断で `RunResult` が返り、既存 `MacroStopException` と `finalize(cmd)` 互換が維持される |
| テスト | `test_runner_calls_lifecycle_in_order`, `test_runner_calls_finalize_on_error`, `test_runner_converts_macro_stop_to_cancelled`, `test_macro_cancelled_is_macro_stop_exception_compatible`, `test_command_wait_returns_immediately_on_cancel`, `test_finalize_cmd_only_remains_supported`, `test_finalize_receives_outcome_when_supported` |
| リスク | `finalize` 失敗時の優先順位、既存 `except MacroStopException`、GUI cancel の例外送出経路が崩れる |
| ロールバック方針 | `MacroExecutor.execute()` の旧 lifecycle 実装を維持したまま Runner を未接続に戻す。例外階層は互換 adapter だけ残す |

`MacroBase.finalize(cmd)` を唯一の抽象契約として維持する。`finalize(cmd, outcome)` は opt-in 拡張に限定し、既存マクロへ実装変更を求めない。

### 4.4 フェーズ 4: Runtime/CommandFacade 導入

| 項目 | 内容 |
|------|------|
| 目的 | `MacroRuntime` を同期・非同期実行の組み立て点にし、`CommandFacade` で既存 `Command` API を維持する |
| 対象ファイル | `src\nyxpy\framework\core\runtime\runtime.py`, `context.py`, `handle.py`, `builder.py`, `src\nyxpy\framework\core\macro\command.py`, `src\nyxpy\framework\core\macro\executor.py`, `tests\unit\framework\runtime\test_execution_context.py`, `test_command_facade.py`, `tests\integration\test_macro_runtime_entrypoints.py` |
| 完了条件 | `MacroRuntime.run(context)` と `start(context)` が `MacroRunner` に委譲し、GUI/CLI/テストは `MacroExecutor` を経由しない |
| テスト | `test_execution_context_shallow_copies_args_and_metadata`, `test_run_handle_wait_done_result_contract`, `test_run_handle_cancel_requests_token`, `test_gui_cli_do_not_import_macro_executor`, `test_command_facade_press_delegates_to_controller_port`, `test_command_facade_capture_resizes_crops_and_grayscales` |
| リスク | `ExecutionContext` が `Command` を保持する、Runtime と Runner が lifecycle を二重実装する、Port close 失敗が本体失敗を上書きする |
| ロールバック方針 | GUI/CLI の Runtime 呼び出しだけを戻し、Runtime クラスは新 API として残す。`DefaultCommand` は旧コンストラクタ経路を優先する |

Runtime の責務は registry 解決、factory 呼び出し、Ports 準備、`CommandFacade` 生成、Port close に限定する。`RunResult` は Runner が生成し、Runtime は close 失敗のみ `cleanup_warnings` に追加する。

### 4.5 フェーズ 5: Settings/Resource 分離

| 項目 | 内容 |
|------|------|
| 目的 | `static\<macro_name>\settings.toml` 解決と画像リソース保存・読み込みを分離し、path escape と書き込み失敗を検出する |
| 対象ファイル | `src\nyxpy\framework\core\macro\settings_resolver.py`, `src\nyxpy\framework\core\utils\helper.py`, `src\nyxpy\framework\core\io\ports.py`, `io\adapters.py`, `src\nyxpy\framework\core\settings\global_settings.py`, `secrets_settings.py`, `tests\unit\framework\macro\test_registry.py`, `tests\unit\framework\io\test_ports.py` |
| 完了条件 | manifest settings、legacy settings、`exec_args` 優先マージが維持され、`ResourceStorePort` は settings TOML を探索しない |
| テスト | `test_settings_legacy_package_lookup`, `test_settings_legacy_single_file_lookup`, `test_exec_args_override_file_settings`, `test_manifest_settings_path_resolution`, `test_macro_settings_resolver_is_separate_from_resource_store`, `test_resource_store_rejects_path_escape`, `test_resource_store_raises_when_imwrite_returns_false` |
| リスク | settings path と resource root の混同、`cwd` fallback の早期削除、既存 TOML 破損時の上書き、secret 値のログ露出 |
| ロールバック方針 | `load_macro_settings()` を旧解決へ戻し、`ResourceStorePort` の導入範囲を画像入出力だけに限定する |

本フェーズ完了後も旧 settings 配置は読む。非推奨警告を出す場合でも、既存マクロの実行を止めない。

### 4.5A フェーズ 5A: Resource File I/O 再設計

| 項目 | 内容 |
|------|------|
| 目的 | read-only assets と writable outputs を分離し、`cmd.load_img()` / `cmd.save_img()` 互換を保ったまま `MacroResourceScope` と `RunArtifactStore` へ移行する |
| 対象ファイル | `src\nyxpy\framework\core\io\resources.py`, `src\nyxpy\framework\core\hardware\resource.py`, `src\nyxpy\framework\core\macro\command.py`, `src\nyxpy\framework\core\runtime\context.py`, `src\nyxpy\framework\core\runtime\builder.py`, `tests\unit\framework\io\test_resource_file_io.py`, `tests\integration\test_resource_file_io_compat.py` |
| 完了条件 | `resources\<macro_id>\assets` を読み込み、`runs\<run_id>\outputs` へ保存できる。legacy `static\<macro_name>` 互換、path traversal 防止、atomic write、overwrite policy がテストで固定される |
| テスト | `test_resource_path_guard_rejects_parent_escape`, `test_command_load_img_uses_resource_store`, `test_command_save_img_uses_run_artifact_store`, `test_command_save_img_legacy_static_write`, `test_save_image_atomic_replace`, `test_existing_frlg_id_rng_save_img_compat` |
| リスク | `static` 直下へ保存していたデバッグ画像の場所が変わる、直接 `Path(cfg.output_dir)` を使う既存マクロとの移行差分、OpenCV 書き込みと atomic replace の組み合わせ |
| ロールバック方針 | `StaticResourceIO` の legacy static adapter を既定に戻し、`RunArtifactStore` への標準保存を opt-in にする。path guard と書き込み失敗検出のテストは残す |

本フェーズの詳細仕様は `RESOURCE_FILE_IO.md` を正とする。`MacroSettingsResolver` は settings lookup だけを担当し、Resource File I/O は settings TOML を探索しない。

### 4.6 フェーズ 6: Logging Framework 再設計

| 項目 | 内容 |
|------|------|
| 目的 | `LOGGING_FRAMEWORK.md` に従い、`LoggerPort`、`LogEvent`、`LogSink`、`UserEvent` / `TechnicalLog` 分離、実行単位 context、test sink、ログファイル運用を実装する |
| 対象ファイル | `src\nyxpy\framework\core\logger\events.py`, `ports.py`, `sinks.py`, `log_manager.py`, `src\nyxpy\framework\core\runtime\context.py`, `builder.py`, `src\nyxpy\framework\core\macro\command.py`, `src\nyxpy\gui\panes\log_pane.py`, `tests\unit\framework\logger\test_logging_framework.py`, `tests\gui\test_log_pane_user_event.py`, `tests\perf\test_logging_framework_perf.py` |
| 完了条件 | import 時の global handler 削除をなくし、既存 `log_manager.log()` 互換を保ち、Runtime 実行ログへ `run_id` / `macro_id` を付与し、GUI は `UserEvent` を表示する |
| テスト | `test_log_manager_import_has_no_backend_side_effect`, `test_legacy_log_api_emits_technical_log`, `test_logger_port_binds_run_context`, `test_sink_exception_is_logged_and_ignored`, `test_log_pane_receives_user_event`, `test_logging_sink_dispatch_perf` |
| リスク | loguru 互換、旧 `add_handler()` 利用箇所、ログファイル path 変更、sink 例外の再帰記録、GUI close 時の解除漏れ |
| ロールバック方針 | `LoggerPort` と test sink は残し、既定 backend を旧 `LogManager` adapter へ戻す。GUI は旧文字列 handler adapter へ一時的に戻せるようにする |

本フェーズは `ERROR_CANCELLATION_LOGGING.md` と `OBSERVABILITY_AND_GUI_CLI.md` の詳細ロギング実装を置き換える参照先である。異常・中断 event 名は既存仕様に従い、sink、backend、ファイル配置、保持期間は `LOGGING_FRAMEWORK.md` を正とする。

### 4.7 フェーズ 7: Ports/Adapters 導入

| 項目 | 内容 |
|------|------|
| 目的 | シリアル、キャプチャ、リソース、通知、ログを Port で抽象化し、Runtime 中核を具象デバイスから切り離す |
| 対象ファイル | `src\nyxpy\framework\core\io\ports.py`, `io\adapters.py`, `src\nyxpy\framework\core\macro\command.py`, `src\nyxpy\framework\core\runtime\builder.py`, `src\nyxpy\framework\core\logger\log_manager.py`, `src\nyxpy\framework\core\api\notification_handler.py`, `src\nyxpy\framework\core\singletons.py`, `tests\unit\framework\io\test_ports.py`, `tests\hardware\test_macro_runtime_realdevice.py` |
| 完了条件 | fake Port で Runtime が単体テスト可能であり、既存 serial/capture/resource/notification/logger 実装は adapter 経由で使える |
| テスト | `test_controller_output_port_serializes_send_operations`, `test_frame_source_await_ready_success_after_first_frame`, `test_frame_source_await_ready_timeout`, `test_notification_port_logs_notifier_failure`, `test_log_manager_emits_structured_log_with_run_context`, `test_serial_controller_output_port_realdevice`, `test_capture_frame_source_realdevice_ready` |
| リスク | 暗黙 dummy fallback の扱い変更、async detection race、frame readiness、GUI preview と Runtime 実行で capture 所有権が競合する |
| ロールバック方針 | `DefaultCommand` の旧具象依存経路を残し、Runtime builder の Port 経路だけを無効化する。実機 adapter は単体 fake Port テストと分けて戻せるようにする |

新 Runtime 経路では、本番実行の暗黙 dummy fallback を使わない。`allow_dummy=True` の明示時だけ dummy Port を許可する。

### 4.8 フェーズ 8: CLI 移行

| 項目 | 内容 |
|------|------|
| 目的 | CLI を `MacroRuntimeBuilder` と `RunResult` ベースへ移行し、デバイス検出、通知設定、終了コードを統一する |
| 対象ファイル | `src\nyxpy\cli\run_cli.py`, `src\nyxpy\framework\core\runtime\builder.py`, `src\nyxpy\framework\core\utils\helper.py`, `tests\integration\test_cli_runtime_adapter.py` |
| 完了条件 | CLI は `DefaultCommand` を直接構築せず、Runtime 経由で実行し、成功 0、中断 130、失敗 非 0 の終了コードを `RunResult` から決める |
| テスト | `test_cli_uses_macro_runtime_builder`, `test_cli_adapter_runs_macro_with_define_args`, `test_cli_device_detection_waits_until_complete`, `test_cli_notification_settings_come_from_secrets_settings`, `test_cli_uses_run_result_exit_code`, `test_parse_define_args_accepts_list_and_string` |
| リスク | CLI 引数互換、`-D` 解析、通知設定ソース、デバイス検出待ち、既存コマンド出力が変わる |
| ロールバック方針 | 旧 `create_command()` と `execute_macro()` を互換関数として残し、CLI adapter の呼び出しだけ旧経路へ戻す |

CLI は `serial_manager.get_active_device()` と `capture_manager.get_active_device()` を直接呼ばない。検出完了待ちと dummy 許可は builder に集約する。

### 4.9 フェーズ 9: GUI 移行

| 項目 | 内容 |
|------|------|
| 目的 | GUI の実行制御を `RunHandle` / `RunResult` へ移行し、GUI スレッドから `cmd.stop()` による例外送出をなくす |
| 対象ファイル | `src\nyxpy\gui\main_window.py`, GUI log pane 関連ファイル, `src\nyxpy\framework\core\logger\log_manager.py`, `src\nyxpy\framework\core\runtime\builder.py`, `tests\gui\test_main_window_runtime_adapter.py` |
| 完了条件 | Run button は `runtime.start(context)` を呼び、Cancel button は `handle.cancel()` を呼び、完了時に `RunResult` を UI 状態へ反映する |
| テスト | `test_main_window_starts_runtime_and_updates_status`, `test_main_window_cancel_requests_run_handle_cancel`, `test_main_window_cancel_does_not_raise_in_gui_thread`, `test_main_window_runtime_adapter_updates_running_state`, `test_log_manager_gui_event_is_separate_from_file_log`, `test_gui_log_handler_exception_is_logged_and_ignored` |
| リスク | Qt thread と Runtime thread の責務混在、GUI log handler の deadlock、preview capture と runtime frame source の所有権競合、終了時 cancel 待ち |
| ロールバック方針 | 既存 `WorkerThread` を Qt signal adapter として残し、Runtime 実行呼び出しだけ旧 executor 経路へ戻す |

core 層に Qt 依存を入れない。GUI は `RunResult` と GUI 表示イベントを Qt signal へ変換する adapter に徹する。

### 4.10 フェーズ 10: MacroExecutor 削除

| 項目 | 内容 |
|------|------|
| 目的 | CLI/GUI 移行後に `MacroExecutor` の参照を削除し、旧入口の互換維持・縮退・非推奨期間を作らない |
| 対象ファイル | `src\nyxpy\framework\core\macro\executor.py`, `src\nyxpy\framework\core\macro\__init__.py`, `tests\integration\test_macro_runtime_entrypoints.py`, 関連ドキュメント |
| 完了条件 | `MacroExecutor` が公開 API、互換契約、GUI/CLI/テスト入口から消えている。削除後の import 互換 shim は存在しない |
| テスト | `test_macro_executor_removed`, `test_gui_cli_do_not_import_macro_executor`, `test_legacy_imports_keep_macro_base_command_contract` |
| リスク | 既存外部コードが `MacroExecutor.macros` や `macro` 属性に依存している可能性がある |
| ロールバック方針 | 削除 commit を戻す。互換 shim や `DeprecationWarning` 付き adapter は追加しない |

`MacroExecutor` は既存マクロ互換 API ではないため、成功時 `None`、失敗時例外再送出、`macros` / `macro` 属性の旧契約を保証しない。GUI/CLI/テストが `MacroRuntime` / `RunHandle` / `MacroRegistry` を直接使う状態を削除条件にする。
その他の廃止候補は `DEPRECATION_AND_MIGRATION.md` に従い、singleton 直接利用、暗黙 device detection、dummy fallback、`Path.cwd()` fallback、GUI/CLI 個別 Command 構築を個別に扱う。

### 4.11 フェーズ 11: ドキュメント・移行ガイド整理

| 項目 | 内容 |
|------|------|
| 目的 | 実装後の新旧 API、互換契約、manifest opt-in、CLI/GUI 移行後の運用、Mermaid 図を文書化する |
| 対象ファイル | `README.md`, `docs\`, `spec\framework\rearchitecture\*.md`, `spec\framework\rearchitecture\ARCHITECTURE_DIAGRAMS.md`, 必要に応じてマクロ作者向け移行ガイド |
| 完了条件 | 既存マクロは変更不要であること、新 API を使う場合の入口、旧 API の非推奨範囲、実機テストの実行条件、全体 Mermaid 図の参照先が読める |
| テスト | ドキュメント変更のみなら実行テストは不要。ただしコード例を変更した場合は関連する単体テストまたは CLI smoke test を実行する |
| リスク | 仕様書と実装差分、旧方式削除と誤読される表現、マクロ作者に不要な移行を求める記述 |
| ロールバック方針 | 実装に合わない文書だけを戻し、互換契約とゲート条件の記述は残す |

移行ガイドでは、既存マクロは変更不要、新 manifest は opt-in、旧 settings fallback は維持、Runtime API は新規フレームワーク利用者向けであることを明記する。Overview から `ARCHITECTURE_DIAGRAMS.md` の全体図へ到達できる状態を維持し、Logging / Resource File I/O / Deprecation の別建て仕様への参照を更新する。

## 5. テスト方針

### 5.1 実行順序

| 順序 | コマンド | 目的 |
|------|----------|------|
| 1 | `uv run pytest tests\unit\` | 既存単体テストと新規中核テストの確認 |
| 2 | `uv run pytest tests\unit\framework\macro\test_legacy_imports.py` | 互換契約の最小ゲート |
| 3 | `uv run pytest tests\unit\framework\macro\test_registry.py tests\unit\framework\runtime\` | Registry / Factory / Runner / Runtime の確認 |
| 4 | `uv run pytest tests\unit\framework\logger\test_logging_framework.py tests\perf\test_logging_framework_perf.py` | Logging Framework 再設計の確認 |
| 5 | `uv run pytest tests\integration\test_macro_runtime_entrypoints.py tests\integration\test_existing_macros_compat.py` | 既存マクロと新 Runtime 入口の互換確認 |
| 6 | `uv run pytest tests\integration\test_cli_runtime_adapter.py` | CLI 移行確認 |
| 7 | `uv run pytest tests\gui\test_main_window_runtime_adapter.py tests\gui\test_log_pane_user_event.py` | GUI 移行と `UserEvent` 表示確認 |
| 8 | `uv run pytest tests\perf\test_macro_discovery_perf.py` | discovery 性能の確認 |
| 9 | `uv run pytest tests\hardware\ -m realdevice` | 実機接続時の確認。通常ゲートからは分離 |
| 10 | `uv run ruff check .` | 静的検査 |
| 11 | `uv run ruff format . --check` | フォーマット確認 |

### 5.2 フェーズ別ゲート

| フェーズ | 必須ゲート |
|----------|------------|
| 1 | Import gate、signature gate、settings gate、existing macro gate |
| 2 | Registry reload、diagnostics、class name collision、new instance per run |
| 3 | lifecycle order、`finalize` guarantee、`RunResult`、`MacroStopException` compatibility、cancel latency |
| 4 | `ExecutionContext` contract、Runtime sync/async、`RunHandle` contract、GUI/CLI の Runtime 入口 |
| 5 | settings resolver、resource path validation、write/read error normalization、secret masking |
| 5A | resource scope、run artifact store、legacy static compatibility、atomic write、path guard |
| 6 | logger port、sink dispatch、run context、user/technical split、legacy log compatibility |
| 7 | fake Port unit tests、adapter integration、frame readiness、dummy policy、logger adapter |
| 8 | CLI args compatibility、device detection wait、notification settings source、exit code |
| 9 | GUI start/cancel/finish、UserEvent display、thread boundary、window close handling |
| 10 | `MacroExecutor` 削除確認、GUI/CLI の新 Runtime 入口確認 |
| 11 | 文書と実装の差分確認、コード例がある場合の該当テスト |

### 5.3 既存マクロ互換の合格条件

- `macros\` 配下の既存マクロを互換維持目的で編集していない。
- 代表マクロがソース変更なしで import、registry 登録、settings 解決、`initialize -> run -> finalize` 実行へ進める。
- 既存 `Command` メソッド呼び出しが `TypeError` にならない。
- 既存 `MacroStopException` を直接送出するマクロが中断として扱われる。
- 既存 `static\<macro_name>\settings.toml` が読み込まれ、CLI/GUI 実行引数で上書きできる。
- GUI/CLI/テストは `MacroExecutor.execute()`、`macros`、`macro` に依存しない。

### 5.4 計画書作成時の検証

本ファイル作成時は、次の確認を行う。

```powershell
git diff --check
rg "T[O]D[O]|T[B]D|x{3}|\[T[O]D[O]\]" spec\framework\rearchitecture
rg "^## (1\. 概要|2\. 対象ファイル|3\. 設計方針|4\. 実装仕様|5\. テスト方針|6\. 実装チェックリスト)\r?$" spec\framework\rearchitecture\IMPLEMENTATION_PLAN.md
```

`rg` の placeholder 検査は一致なしを合格とする。必須 6 セクション検査は 6 行が出ることを合格とする。

## 6. 実装チェックリスト

- [x] 必読仕様を確認し、実装順序へ反映
- [x] 既存ユーザーマクロのソース変更不要を最優先制約として明記
- [x] `MacroExecutor` を削除対象として扱う範囲を明記
- [x] `MacroRuntime` / `MacroRunner` / `MacroRegistry` / `MacroFactory` を新実行中核として配置
- [x] 11 フェーズと 5A 補助フェーズを実装順序として定義
- [x] 各フェーズに目的、対象ファイル、完了条件、テスト、リスク、ロールバック方針を記載
- [x] コミット分割方針を Conventional Commits 形式で記載
- [x] Commits に Why を残す方針を明記
- [x] 既存マクロ互換を壊していないことのゲート条件を記載
- [ ] フェーズ 1 の互換テストを実装
- [ ] フェーズ 2 の Registry/Factory を実装
- [ ] フェーズ 3 の Runner/RunResult/Error/Cancellation を実装
- [ ] フェーズ 4 の Runtime/CommandFacade を実装
- [ ] フェーズ 5 の Settings/Resource 分離を実装
- [ ] フェーズ 5A の Resource File I/O 再設計を実装
- [ ] フェーズ 6 の Logging Framework 再設計を実装
- [ ] フェーズ 7 の Ports/Adapters を実装
- [ ] フェーズ 8 の CLI adapter を実装
- [ ] フェーズ 9 の GUI adapter を実装
- [ ] フェーズ 10 の `MacroExecutor` 縮退判断を実施
- [ ] フェーズ 11 のドキュメント・移行ガイドを整理
