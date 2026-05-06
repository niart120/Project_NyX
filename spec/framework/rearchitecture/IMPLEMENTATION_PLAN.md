# フレームワーク再設計 実装計画書

> **文書種別**: 実装計画。実装順序と完了条件を定義する。型・API・責務の正本は関連仕様書を参照する。
> **対象モジュール**: `src\nyxpy\framework\core\macro\`, `src\nyxpy\framework\core\runtime\`, `src\nyxpy\framework\core\io\`, `src\nyxpy\cli\`, `src\nyxpy\gui\`  
> **目的**: 維持対象の公開互換を固定し、マクロ側移行が必要な Resource I/O、settings、entrypoint を明示したうえで、実行中核を `MacroRuntime` / `MacroRunner` / `MacroRegistry` / `MacroFactory` へ段階移行する。
> **関連ドキュメント**: `FW_REARCHITECTURE_OVERVIEW.md`, `ARCHITECTURE_DIAGRAMS.md`, `MACRO_COMPATIBILITY_AND_REGISTRY.md`, `RUNTIME_AND_IO_PORTS.md`, `RESOURCE_FILE_IO.md`, `LOGGING_FRAMEWORK.md`, `ERROR_CANCELLATION_LOGGING.md`, `OBSERVABILITY_AND_GUI_CLI.md`, `DEPRECATION_AND_MIGRATION.md`, `TEST_STRATEGY.md`  
> **破壊的変更**: 維持する互換契約は `FW_REARCHITECTURE_OVERVIEW.md` と `MACRO_COMPATIBILITY_AND_REGISTRY.md` を参照する。破壊的変更、削除条件、代替 API、テストゲート、移行順の詳細は `DEPRECATION_AND_MIGRATION.md` を正とし、本書は実装順序へ落とし込む。

## 1. 概要

### 1.1 目的

本計画は、フレームワーク再設計仕様を実装順序と検証順序へ落とし込むための実行計画である。仕様書で定義された責務分離を一括置換せず、互換テストを先に固定してから Registry、Factory、Runner、Runtime、Ports、CLI、GUI の順に移行する。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| Compatibility Contract | 既存マクロが依存している import path、ライフサイクル、Command API、例外捕捉を維持する契約 |
| MacroBase | ユーザー定義マクロの抽象基底クラス。`initialize(cmd, args)` / `run(cmd)` / `finalize(cmd)` を維持する |
| Command | マクロから見える操作 API。`press`、`wait`、`capture`、`save_img`、`notify` などの既存メソッドを維持する |
| MacroExecutor | 既存 GUI/CLI とテストの旧入口。再設計後の公開 API・互換契約・移行 adapter には含めず削除する |
| MacroRegistry | マクロの発見、安定 ID、別名、診断、設定解決を管理し、実行インスタンスを保持しないコンポーネント |
| MacroFactory | `MacroDefinition` が所有する生成責務。実行ごとに新しい `MacroBase` インスタンスを返す |
| MacroRunner | `initialize -> run -> finalize` の順序、例外正規化、中断正規化、`RunResult` 生成を担当するコンポーネント |
| MacroRuntime | registry 解決、`definition.factory.create()`、`DefaultCommand` 生成、同期・非同期実行、リソース解放を統括する新実行中核。Ports 準備は `MacroRuntimeBuilder` が担当する |
| RunResult | 実行結果を表す値。`RunStatus`、開始・終了時刻、`ErrorInfo`、解放時警告を保持する |
| RunHandle | 非同期実行の中断要求、完了待ち、結果取得を提供するハンドル |
| ExecutionContext | 1 回の実行に必要な `run_id`、`macro_id`、`macro_name`、Ports、設定、実行引数、`CancellationToken` を束ねる値。`Command` は保持しない |
| Ports/Adapters | Runtime 中核からハードウェア、設定、通知、ログ、GUI/CLI 依存を隔離する境界 |
| DefaultCommand | 既存 import path と `Command` API を維持する実装。生成は `DefaultCommand(context=...)` に統一し、`ExecutionContext` 経由で Ports へ委譲する。旧具象引数コンストラクタは残さない |
| MacroSettingsResolver | manifest / class metadata settings を解決するコンポーネント。Resource File I/O から分離し、旧 static/cwd fallback を持たない |
| Resource File I/O | read-only assets と writable outputs の配置、path guard、atomic write、overwrite policy を扱う境界 |
| MacroResourceScope | 1 つのマクロ ID に紐づく assets root を表す値 |
| RunArtifactStore | 1 回の実行 ID に紐づく outputs root へ成果物を書き込む Port |

### 1.3 背景・問題

現行実装では、マクロ発見、実行インスタンス生成、ライフサイクル実行、デバイス・通知・ログの組み立てが `MacroExecutor`、`DefaultCommand`、CLI、GUI に分散している。`MacroExecutor` は発見時にマクロをインスタンス化するため、実行間で状態が残りやすく、ロード失敗診断やクラス名衝突の扱いも不足している。

一方、既存ユーザーマクロは `MacroBase`、`Command`、constants、`MacroStopException` に直接依存している。再設計の実装では、維持する互換契約をテストで固定し、Resource I/O、settings、entrypoint の移行を仕様と移行ガイドで明示する。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| 維持対象 import / lifecycle に起因するマクロ本体変更 | 内部改修次第で必要化する恐れがある | 0 件 |
| マクロ配置・リソース移行 | `static` と旧 discovery に依存 | 任意 `macro.toml` / class metadata / convention discovery、明示 settings source、assets root、run outputs へ移行 |
| 互換契約の検証 | 一部の executor テストと暗黙の import 維持に依存 | import、シグネチャ、Command API、明示 settings source、代表マクロロードをゲート化 |
| 実行ごとの状態分離 | reload 時に生成したインスタンスを再利用 | `definition.factory.create()` で毎回新規生成 |
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
| `spec/framework/rearchitecture/IMPLEMENTATION_PLAN.md` | 新規 | 本実装計画書 |
| `spec/framework/rearchitecture/LOGGING_FRAMEWORK.md` | 新規 | ロギング再設計の実装順序と参照先 |
| `tests\unit\framework\macro\test_import_contract.py` | 新規 | import path、公開シグネチャ、Command API、例外互換のゲートを追加 |
| `tests\unit\framework\macro\test_registry.py` | 新規 | Registry、manifest 任意採用、class metadata、convention discovery、診断、設定解決を検証 |
| `tests\unit\framework\runtime\test_macro_factory.py` | 新規 | 実行ごとの新規インスタンス生成を検証 |
| `tests\unit\framework\runtime\test_macro_runner.py` | 新規 | lifecycle、`finalize` 保証、中断、失敗、`RunResult` を検証 |
| `tests\unit\framework\runtime\test_execution_context.py` | 新規 | `ExecutionContext`、shallow copy、`Command` 非保持を検証 |
| `tests\unit\framework\runtime\test_default_command_ports.py` | 新規 | `DefaultCommand` と fake Port の委譲規則を検証 |
| `tests\unit\framework\io\test_ports.py` | 新規 | Port 契約、resource path 検証、frame readiness を検証 |
| `tests\integration\test_macro_runtime_entrypoints.py` | 新規 | GUI/CLI/テスト入口が `MacroExecutor` を経由せず Runtime を使うことを検証 |
| `tests\integration\test_migrated_macro_compat.py` | 新規 | 移行後代表マクロのロード、設定マージ、lifecycle 互換を検証 |
| `tests\integration\test_cli_runtime_adapter.py` | 新規 | CLI が Runtime 経由で実行し、終了コードへ変換することを検証 |
| `tests\gui\test_main_window_runtime_adapter.py` | 新規 | GUI が `RunHandle` と `RunResult` を UI 状態へ反映することを検証 |
| `tests\hardware\test_macro_runtime_realdevice.py` | 新規 | 実機接続時の serial/capture/runtime 実行を検証 |
| `tests\perf\test_macro_discovery_perf.py` | 新規 | registry reload と discovery の性能を検証 |
| `src\nyxpy\framework\core\macro\base.py` | 変更 | import path と lifecycle signature を維持。移動する場合も re-export を先に置く |
| `src\nyxpy\framework\core\macro\command.py` | 変更 | `Command` / `DefaultCommand` import 互換を維持し、`DefaultCommand` 内部を Ports へ段階移行。`DefaultCommand` 旧コンストラクタは削除 |
| `src\nyxpy\framework\core\macro\exceptions.py` | 変更 | `FrameworkError` 階層、`MacroCancelled`、`MacroStopException` adapter、`ErrorInfo` を定義 |
| `src\nyxpy\framework\core\macro\decorators.py` | 変更 | `@check_interrupt` を新 `CancellationToken` と `MacroCancelled` へ接続 |
| `src\nyxpy\framework\core\macro\executor.py` | 削除 | GUI/CLI/テストの参照移行後に削除。import 互換 shim は作らない |
| `src\nyxpy\framework\core\macro\registry.py` | 新規 | `MacroRegistry`、`MacroDefinition`、`MacroFactory`、診断モデルを定義 |
| `src\nyxpy\framework\core\macro\entrypoint_loader.py` | 新規 | manifest entrypoint、class metadata、convention discovery で package / single-file マクロを解決 |
| `src\nyxpy\framework\core\macro\settings_resolver.py` | 新規 | settings TOML 解決を画像リソースから分離 |
| `src\nyxpy\framework\core\runtime\__init__.py` | 新規 | Runtime 公開 API を再 export |
| `src\nyxpy\framework\core\runtime\context.py` | 新規 | `ExecutionContext`、`RunContext`、`RuntimeOptions` を定義 |
| `src\nyxpy\framework\core\runtime\result.py` | 新規 | `RunStatus`、`RunResult`、`ErrorInfo` を定義または再 export |
| `src\nyxpy\framework\core\runtime\runner.py` | 新規 | `MacroRunner` の lifecycle 実行と `RunResult` 生成を実装 |
| `src\nyxpy\framework\core\runtime\handle.py` | 新規 | `RunHandle` とスレッド実装を定義 |
| `src\nyxpy\framework\core\runtime\runtime.py` | 新規 | `MacroRuntime` の同期実行、非同期実行、リソース解放を実装 |
| `src\nyxpy\framework\core\runtime\builder.py` | 新規 | CLI/GUI 設定から Runtime と Ports を組み立てる |
| `src\nyxpy\framework\core\io\__init__.py` | 新規 | Port と adapter の再 export |
| `src\nyxpy\framework\core\io\ports.py` | 新規 | `ControllerOutputPort`、`FrameSourcePort`、`NotificationPort` を定義。Resource と Logger は各正本を参照 |
| `src\nyxpy\framework\core\io\resources.py` | 新規 | `ResourceStorePort`、`RunArtifactStore`、`ResourceRef`、`MacroResourceScope`、path guard を定義 |
| `src\nyxpy\framework\core\io\adapters.py` | 新規 | 既存 serial/capture/resource/notification への adapter を実装 |
| `src\nyxpy\framework\core\utils\cancellation.py` | 変更 | 理由、要求元、時刻、`throw_if_requested()`、即時 wait を追加 |
| `src\nyxpy\framework\core\utils\helper.py` | 変更 | `load_macro_settings()` と `parse_define_args()` を新 resolver / error へ接続 |
| `src\nyxpy\framework\core\logger\dispatcher.py` | 新規 | `LogSinkDispatcher` と sink 配信を実装 |
| `src\nyxpy\framework\core\logger\backend.py` | 新規 | 技術ログ backend と file/console 出力を実装 |
| `src\nyxpy\framework\core\logger\sanitizer.py` | 新規 | secret mask と JSON 化不能値の縮退を実装 |
| `src\nyxpy\framework\core\logger\log_manager.py` | 削除 | `LogManager` singleton と旧 `log_manager.log()` 互換 adapter は残さない |
| `src\nyxpy\framework\core\logger\events.py` | 新規 | `LogEvent`、`TechnicalLog`、`UserEvent`、`RunLogContext` を定義 |
| `src\nyxpy\framework\core\logger\ports.py` | 新規 | `LoggerPort`、`LogSink`、backend 差し替え境界を定義 |
| `src\nyxpy\framework\core\logger\sinks.py` | 新規 | file、console、test sink を実装。GUI sink は `src\nyxpy\gui\` 配下に置く |
| `src\nyxpy\framework\core\settings\global_settings.py` | 変更 | 互換 shim を分離し、`SettingsStore` / snapshot 経路へ移行 |
| `src\nyxpy\framework\core\settings\secrets_settings.py` | 変更 | 互換 shim を分離し、`SecretsStore` / secrets snapshot 経路へ移行 |
| `src\nyxpy\framework\core\api\notification_handler.py` | 変更 | 通知失敗を構造化ログへ記録し、マクロ失敗へ伝播させない |
| `src\nyxpy\framework\core\singletons.py` | 変更 | 互換 shim だけを残し、新 Runtime 経路からの参照を削除 |
| `src\nyxpy\cli\run_cli.py` | 変更 | `MacroRuntimeBuilder` と `RunResult` ベースの CLI adapter へ移行 |
| `src\nyxpy\gui\main_window.py` | 変更 | `RunHandle` / `RunResult` ベースの GUI adapter へ移行 |

## 3. 設計方針

### 3.1 実装計画の位置づけ

本書は仕様の追加定義ではなく、既存仕様を壊さずに実装する順序と検証ゲートを定義する。各フェーズは「互換テストを追加し、最小の実装単位を導入し、GUI/CLI/テストを新入口に寄せ、最後に旧実装を削除する」流れで進める。

実装前提とフェーズ 1 の成果物を分ける。実装前提は仕様確定、ベースライン確認、実機不要テストと実機テストの分離、維持対象 import / lifecycle に起因するマクロ本体変更を発生させない制約である。フェーズ 1 の成果物は、import / signature / 明示 settings source / 代表マクロロード / `MacroExecutor` 削除確認のテスト追加であり、フレームワーク本体の挙動は変更しない。

### 3.2 依存順序

| 順序 | フェーズ | 依存 |
|------|----------|------|
| 1 | ベースライン・互換テスト追加 | なし |
| 2 | Registry/Factory 導入 | フェーズ 1 |
| 3 | Runner/RunResult/Error/Cancellation 導入 | フェーズ 1、2 |
| 4 | Port Protocol / fake adapter 最小定義 | フェーズ 2、3 |
| 5 | Runtime/DefaultCommand 導入 | フェーズ 2、3、4 |
| 6 | Settings/Resource 分離 | フェーズ 2、5 |
| 6.1 | Resource File I/O 再設計 | フェーズ 5、6 |
| 7 | Logging Framework 再設計 | フェーズ 3、5、6 |
| 8 | Ports/Adapters 導入 | フェーズ 4、5、6、6.1、7 |
| 9 | CLI 移行 | フェーズ 5、7、8 |
| 10 | GUI 移行 | フェーズ 5、7、8、9 の知見 |
| 11 | MacroExecutor 削除 | フェーズ 9、10 |
| 12 | ドキュメント・移行ガイド整理 | 全フェーズ |

### 3.3 互換性ゲート

各フェーズの完了判定前に、次のゲートを満たす。

| ゲート | 判定内容 |
|--------|----------|
| Import gate | `MacroBase`、`Command`、`DefaultCommand`、`MacroStopException`、constants が既存 path から import できる。`MacroExecutor` は既存マクロ互換 API ではないため含めない |
| Signature gate | `initialize(cmd, args)`、`run(cmd)`、`finalize(cmd)`、主要 `Command` メソッドの呼び出し互換を維持する。`MacroExecutor.execute()` は互換対象に含めない |
| Lifecycle gate | 成功、失敗、中断のいずれでも `finalize(cmd)` が可能な限り 1 回呼ばれる |
| Settings gate | manifest または class metadata settings path を読み、`exec_args` が file settings より優先される。旧 static/cwd fallback は読まない |
| Builder ownership gate | GUI/CLI は settings と resource を個別解決せず、`MacroRuntimeBuilder.build()` を通して `ExecutionContext` を得る |
| Migrated macro gate | 移行後の代表マクロ fixture が manifest あり / なしの新 discovery からロードされる。具体的な対象マクロ名は `MACRO_MIGRATION_GUIDE.md` の移行対象一覧を正とする |
| MacroExecutor removal gate | `test_macro_executor_removed` と `test_gui_cli_do_not_import_macro_executor` で、旧 executor の import 互換 shim と GUI/CLI 参照が残っていないことを検証する |
| Cancellation gate | 既存 `MacroStopException` は `except MacroStopException` で捕捉でき、新中断も `RunStatus.CANCELLED` に正規化される |
| Core isolation gate | `nyxpy.framework.*` から `nyxpy.gui`、`nyxpy.cli`、個別マクロへの静的依存を追加しない |
| Migration guide gate | Resource I/O、settings、entrypoint のマクロ側変更が `MACRO_MIGRATION_GUIDE.md` に記載されている |
| Deprecation gate | `DEPRECATION_AND_MIGRATION.md` の削除条件、代替 API、互換影響、テストゲート、移行順を満たす |

#### テストゲートと廃止候補の対応

| フェーズ | 必須ゲート | 削除または無効化できる廃止候補 |
|----------|------------|--------------------------------|
| 1 ベースライン・互換テスト追加 | Import gate, Signature gate, Lifecycle gate | なし。削除対象をテストで明示するだけに留める |
| 2 Registry/Factory 導入 | Import gate, Signature gate, Core isolation gate | 恒久的な `sys.path` 変更、曖昧な class 名 alias の後勝ち上書き |
| 3 Runner/RunResult/Error/Cancellation 導入 | Lifecycle gate, Cancellation gate | `MacroExecutor.execute()` の戻り値 `None` / 例外再送出への内部依存 |
| 5 Runtime/DefaultCommand 導入 | Builder ownership gate, Cancellation gate | `DefaultCommand` 旧コンストラクタ、GUI/CLI 個別 Command 組み立ての新規追加 |
| 6 Settings/Resource 分離 | Settings gate, Migration guide gate | settings legacy fallback、`cwd` 固定の project root 解決 |
| 6.1 Resource File I/O 再設計 | Migrated macro gate, Migration guide gate | Resource I/O legacy static 互換、`StaticResourceIO` 直接利用 |
| 7 Logging Framework 再設計 | Core isolation gate, Deprecation gate | loguru 直結の `LogManager` グローバル初期化への Runtime 直接依存 |
| 9 CLI 移行 | Builder ownership gate, Deprecation gate | CLI 側の旧 `DefaultCommand` 直接構築、CLI notification settings の旧経路 |
| 10 GUI 移行 | Builder ownership gate, Cancellation gate | GUI スレッドからの `cmd.stop()` 呼び出し、旧 worker の Command 直接構築 |
| 11 MacroExecutor 削除 | MacroExecutor removal gate, existing macro gate, GUI/CLI integration | `MacroExecutor` 本体と import 互換 shim |

### 3.4 コミット分割方針

コミットは Conventional Commits 形式を使い、件名は日本語で記述する。コミット本文には、その変更が必要な理由を残す。大きなフェーズでも「テストで契約を固定するコミット」と「実装コミット」を分ける。

| 例 | 理由として本文に残す内容 |
|----|--------------------------|
| `test(framework): 既存マクロ互換契約を固定` | 再設計前に import path、シグネチャ、代表マクロロードを固定し、以後の内部置換で破壊を検出するため |
| `feat(macro): Registry と Factory を導入` | 発見時インスタンス生成をやめ、実行ごとの状態分離とロード診断を可能にするため |
| `feat(runtime): Runner と RunResult を導入` | lifecycle 実行、例外、中断、結果表現を `MacroExecutor` から分離するため |
| `feat(runtime): MacroRuntime と DefaultCommand の Port 委譲を追加` | CLI/GUI の重複構築を減らし、実行中核を単一の組み立て点へ寄せるため |
| `refactor(macro): settings 解決と Resource File I/O を分離` | settings TOML 探索と assets / outputs 保存の責務混在を解消するため |
| `feat(logger): ロギング基盤を LoggerPort と sink へ再設計` | ユーザー表示と技術ログを分離し、backend 差し替えと実行 context 追跡を可能にするため |
| `feat(io): Runtime 用 Ports と既存実装 adapter を追加` | 実機なしテストとハードウェア境界の差し替えを可能にするため |
| `refactor(cli): CLI 実行を MacroRuntime 経由へ移行` | 終了コードと通知設定を `RunResult` / secrets snapshot に統一するため |
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
| 対象ファイル | `tests\unit\framework\macro\test_import_contract.py`, `tests\integration\test_migrated_macro_compat.py`, 既存 executor / GUI reload テスト |
| 完了条件 | import gate、signature gate、explicit settings gate、migrated macro gate が自動テストで判定できる |
| テスト | `uv run pytest tests\unit\framework\macro\test_import_contract.py`, `uv run pytest tests\integration\test_migrated_macro_compat.py`, `uv run pytest tests\integration\test_macro_runtime_entrypoints.py` |
| リスク | 既存テスト配置と現行 import 形がずれ、実装前から失敗する可能性がある |
| ロールバック方針 | 本フェーズは実装を変えない。現行仕様と異なるテストだけを修正し、互換契約の弱体化はしない |

追加する主な検証は次である。

- `from nyxpy.framework.core.macro.base import MacroBase`
- `from nyxpy.framework.core.macro.command import Command, DefaultCommand`
- `from nyxpy.framework.core.macro.exceptions import MacroStopException`
- `from nyxpy.framework.core.constants import Button, Hat, LStick, RStick, KeyType`
- `Command` の既存メソッド名と主要キーワード引数
- `MacroExecutor` が新 API、互換契約、GUI/CLI/テスト入口に残っていないことの削除確認
- 明示 settings source と `exec_args` 優先マージ
- 移行後代表マクロの manifest / convention discovery ロード

### 4.2 フェーズ 2: Registry/Factory 導入

| 項目 | 内容 |
|------|------|
| 目的 | マクロ発見、ID、別名、ロード診断、settings 解決、実行ごとのインスタンス生成を `MacroExecutor` から分離する |
| 対象ファイル | `src\nyxpy\framework\core\macro\registry.py`, `entrypoint_loader.py`, `settings_resolver.py`, `utils\helper.py`, `tests\unit\framework\macro\test_registry.py`, `tests\unit\framework\runtime\test_macro_factory.py` |
| 完了条件 | manifest entrypoint または convention discovery で package / single-file マクロを `MacroDefinition` として登録でき、`definition.factory.create()` が毎回新しい `MacroBase` インスタンスを返す |
| テスト | `test_registry_loads_manifest_package_macro`, `test_registry_loads_manifest_single_file_macro`, `test_registry_rejects_missing_entrypoint`, `test_class_name_collision_requires_qualified_id`, `test_load_failure_is_reported_without_stopping_reload`, `test_execute_creates_new_instance_each_time` |
| リスク | `sys.path` 依存、相対 import、クラス名衝突、ロード失敗時の継続処理が既存挙動とずれる |
| ロールバック方針 | Registry 呼び出し側だけを旧探索経路へ戻す。`MacroExecutor` の公開 API 互換 shim は追加せず、互換テストと削除確認テストは残す |

この段階では GUI/CLI が参照する一覧取得と実行対象解決を `MacroRegistry` から行える状態にする。`MacroExecutor.reload_macros()` や `macros` facade は移行対象に含めない。

### 4.3 フェーズ 3: Runner/RunResult/Error/Cancellation 導入

| 項目 | 内容 |
|------|------|
| 目的 | lifecycle 実行、例外分類、中断正規化、`RunResult` 生成を `MacroRunner` に集約する |
| 対象ファイル | `src\nyxpy\framework\core\runtime\result.py`, `runner.py`, `context.py`, `handle.py`, `src\nyxpy\framework\core\macro\exceptions.py`, `decorators.py`, `src\nyxpy\framework\core\utils\cancellation.py`, `tests\unit\framework\runtime\test_macro_runner.py` |
| 完了条件 | 成功、失敗、中断で `RunResult` が返り、既存 `MacroStopException` と `finalize(cmd)` 互換が維持される |
| テスト | `test_runner_calls_lifecycle_in_order`, `test_runner_calls_finalize_on_error`, `test_runner_converts_macro_stop_to_cancelled`, `test_macro_cancelled_is_macro_stop_exception_compatible`, `test_command_wait_returns_immediately_on_cancel`, `test_finalize_cmd_only_remains_supported`, `test_finalize_receives_outcome_when_supported` |
| リスク | `finalize` 失敗時の優先順位、既存 `except MacroStopException`、GUI cancel の例外送出経路が崩れる |
| ロールバック方針 | Runner 呼び出し側を旧 lifecycle 実装へ戻す。`MacroExecutor.execute()` の互換契約は復活させず、例外階層は互換 adapter だけ残す |

`MacroBase.finalize(cmd)` を唯一の抽象契約として維持する。`finalize(cmd, outcome)` は opt-in 拡張に限定し、既存マクロへ実装変更を求めない。

### 4.4 フェーズ 4: Port Protocol / fake adapter 最小定義

| 項目 | 内容 |
|------|------|
| 目的 | Runtime が参照する最小 Port 契約を先に確定し、Runtime 実装中の一時抽象や後戻りを避ける |
| 対象ファイル | `src\nyxpy\framework\core\io\ports.py`, `src\nyxpy\framework\core\io\resources.py`, `src\nyxpy\framework\core\logger\ports.py`, `tests\unit\framework\io\test_ports.py`, `tests\unit\framework\io\test_fake_ports.py` |
| 完了条件 | `ControllerOutputPort`, `FrameSourcePort`, `NotificationPort`, `ResourceStorePort`, `RunArtifactStore`, `LoggerPort` の正本が確定し、fake adapter で Runtime / DefaultCommand の単体テストを組める |
| テスト | `test_fake_controller_records_order`, `test_fake_frame_source_readiness`, `test_resource_store_port_contract`, `test_logger_port_contract_uses_user_and_technical` |
| リスク | I/O 境界を細かく分けすぎて不要な抽象レイヤーを増やす |
| ロールバック方針 | Port は Runtime が直接必要とする境界だけに限定する。Command 用 facade、`LoggerPort` の io 再定義、Factory facade などの中間層は追加しない |

このフェーズでは具象 device adapter は作らない。Runtime と `DefaultCommand` の型が直接参照する Port Protocol / ABC と fake だけを定義し、具象 adapter は後続フェーズで現行実装へ接続する。

### 4.5 フェーズ 5: Runtime/DefaultCommand 導入

| 項目 | 内容 |
|------|------|
| 目的 | `MacroRuntime` を同期・非同期実行の入口にし、`DefaultCommand(context=...)` で既存 `Command` API を維持する |
| 対象ファイル | `src\nyxpy\framework\core\runtime\runtime.py`, `context.py`, `handle.py`, `builder.py`, `src\nyxpy\framework\core\macro\command.py`, `tests\support\fake_execution_context.py`, `tests\unit\framework\runtime\test_execution_context.py`, `test_default_command_ports.py`, `tests\integration\test_macro_runtime_entrypoints.py` |
| 完了条件 | `MacroRuntime.run(context)` と `start(context)` が `MacroRunner` に委譲し、GUI/CLI/テストは `MacroExecutor` を経由しない。既存 `DefaultCommand` 旧コンストラクタ利用は GUI/CLI/perf/結合テストを含めて棚卸し、テストは fake `ExecutionContext` fixture または builder 経由へ移行する |
| テスト | `test_execution_context_shallow_copies_args_and_metadata`, `test_run_handle_wait_done_result_contract`, `test_run_handle_cancel_requests_token`, `test_gui_cli_do_not_import_macro_executor`, `test_default_command_press_delegates_to_controller_port`, `test_default_command_capture_resizes_crops_and_grayscales`, `test_default_command_rejects_legacy_constructor_args`, `test_default_command_tests_use_fake_execution_context`, `test_command_stop_rejects_raise_immediately_argument` |
| リスク | `ExecutionContext` が `Command` を保持する、Runtime と Runner が lifecycle を二重実装する、Port close 失敗が本体失敗を上書きする |
| ロールバック方針 | GUI/CLI の Runtime 呼び出しだけを戻し、Runtime クラスは新 API として残す。`DefaultCommand` 旧コンストラクタは復活させず、Builder 経由の生成契約を維持する |

Runtime の責務は registry 解決、`definition.factory.create()`、`DefaultCommand(context=...)` 生成、Port close に限定する。Ports 準備と `ExecutionContext` 生成は `MacroRuntimeBuilder` が担当する。`RunResult` は Runner が生成し、Runtime は close 失敗のみ `cleanup_warnings` に追加する。

### 4.6 フェーズ 6: Settings/Resource 分離

| 項目 | 内容 |
|------|------|
| 目的 | manifest / class metadata settings 解決と画像リソース保存・読み込みを分離し、path escape と書き込み失敗を検出する |
| 対象ファイル | `src\nyxpy\framework\core\macro\settings_resolver.py`, `src\nyxpy\framework\core\utils\helper.py`, `src\nyxpy\framework\core\io\resources.py`, `src\nyxpy\framework\core\settings\global_settings.py`, `secrets_settings.py`, `tests\unit\framework\macro\test_registry.py`, `tests\unit\framework\io\test_ports.py` |
| 完了条件 | 明示 settings source と `exec_args` 優先マージが維持され、`ResourceStorePort` は settings TOML を探索しない |
| テスト | `test_macro_settings_resolver_loads_manifest_settings`, `test_macro_settings_resolver_does_not_read_legacy_static_settings`, `test_exec_args_override_file_settings`, `test_manifest_settings_path_resolution`, `test_macro_settings_resolver_is_separate_from_resource_store`, `test_resource_store_rejects_path_escape`, `test_resource_store_raises_when_imwrite_returns_false` |
| リスク | settings path と resource root の混同、既存 TOML 破損時の上書き、secret 値のログ露出 |
| ロールバック方針 | `load_macro_settings()` を `MacroSettingsResolver` 経由に限定し、旧 static/cwd fallback は戻さない。`ResourceStorePort` の導入範囲を画像入出力だけに限定する |

本フェーズ完了後、旧 settings 配置は読まない。settings が必要なマクロは `macro.toml` の `[macro].settings` または class metadata `settings_path` へ settings path を明示する。

### 4.6.1 フェーズ 6.1: Resource File I/O 再設計

| 項目 | 内容 |
|------|------|
| 目的 | read-only assets と writable outputs を分離し、`cmd.load_img()` / `cmd.save_img()` のメソッド名互換を保ったまま `MacroResourceScope` と `RunArtifactStore` へ移行する |
| 対象ファイル | `src\nyxpy\framework\core\io\resources.py`, `src\nyxpy\framework\core\hardware\resource.py`, `src\nyxpy\framework\core\macro\command.py`, `src\nyxpy\framework\core\runtime\context.py`, `src\nyxpy\framework\core\runtime\builder.py`, `tests\unit\framework\io\test_resource_file_io.py`, `tests\integration\test_resource_file_io_migration.py` |
| 完了条件 | `resources\<macro_id>\assets` を読み込み、`runs\<run_id>\outputs` へ保存できる。旧 `static\<macro_name>` 互換を残さず、path traversal 防止、atomic write、overwrite policy がテストで固定される |
| テスト | `test_resource_path_guard_rejects_parent_escape`, `test_command_load_img_uses_resource_store`, `test_command_save_img_uses_run_artifact_store`, `test_command_save_img_does_not_strip_macro_id_prefix`, `test_save_image_atomic_replace`, `test_migrated_representative_macro_save_img_outputs` |
| リスク | `static` 直下へ保存していたデバッグ画像の場所が変わる、直接 `Path(cfg.output_dir)` を使う既存マクロとの移行差分、OpenCV 書き込みと atomic replace の組み合わせ |
| ロールバック方針 | `RunArtifactStore` への標準保存は維持し、`Command` 側の呼び出しだけ段階戻しする。旧 static adapter は戻さない。path guard と書き込み失敗検出のテストは残す |

本フェーズの詳細仕様は `RESOURCE_FILE_IO.md` を正とする。`MacroSettingsResolver` は settings lookup だけを担当し、Resource File I/O は settings TOML を探索しない。

### 4.7 フェーズ 7: Logging Framework 再設計

| 項目 | 内容 |
|------|------|
| 目的 | `LOGGING_FRAMEWORK.md` に従い、`LoggerPort`、`LogEvent`、`LogSinkDispatcher`、`LogBackend`、`LogSanitizer`、`UserEvent` / `TechnicalLog` 分離、実行単位 context、test sink、ログファイル運用を実装する |
| 対象ファイル | `src\nyxpy\framework\core\logger\events.py`, `ports.py`, `dispatcher.py`, `backend.py`, `sanitizer.py`, `sinks.py`, `log_manager.py`, `src\nyxpy\framework\core\runtime\context.py`, `builder.py`, `src\nyxpy\framework\core\macro\command.py`, `src\nyxpy\gui\panes\log_pane.py`, `tests\unit\framework\logger\test_logging_framework.py`, `tests\gui\test_log_pane_user_event.py`, `tests\perf\test_logging_framework_perf.py` |
| 完了条件 | import 時の global handler 削除をなくし、Runtime 実行ログへ `run_id` / `macro_id` を付与し、GUI は `UserEvent` を表示する。`LogManager` と旧 `log_manager.log()` は内部 API とみなして完全削除し、互換 adapter は残さない。event を追加・変更する場合は先に `LOGGING_FRAMEWORK.md` の Event catalog を更新する |
| テスト | `test_logger_import_has_no_backend_side_effect`, `test_logger_port_binds_run_context`, `test_sink_exception_is_logged_and_ignored`, `test_gui_log_pane_displays_user_event_from_sink`, `test_log_handler_dispatch_thread_safety`, `test_legacy_log_manager_removed`, `test_log_manager_call_sites_removed`, `test_logging_event_catalog_is_single_source` |
| リスク | 旧 `log_manager.log()` / `add_handler()` 利用箇所、ログファイル path 変更、sink 例外の再帰記録、GUI close 時の解除漏れ |
| ロールバック方針 | `LoggerPort` と test sink は残し、backend 構成だけを差し戻す。旧文字列 handler adapter と `log_manager.log()` 互換は戻さない |

本フェーズは `ERROR_CANCELLATION_LOGGING.md` と `OBSERVABILITY_AND_GUI_CLI.md` の詳細ロギング実装を置き換える参照先である。異常・中断 event 名、sink、backend、ファイル配置、保持期間は `LOGGING_FRAMEWORK.md` を正とする。`src\nyxpy\gui\main_window.py`、`src\nyxpy\cli\run_cli.py`、`src\nyxpy\framework\core\hardware\capture.py`、通知実装、既存 logger テストは `LoggerPort` / `LogSink` / `TestLogSink` へ置換してから旧 API を削除する。

### 4.8 フェーズ 8: Ports/Adapters 導入

| 項目 | 内容 |
|------|------|
| 目的 | シリアル、キャプチャ、リソース、通知、ログを Port で抽象化し、Runtime 中核を具象デバイスから切り離す |
| 対象ファイル | `src\nyxpy\framework\core\io\ports.py`, `io\adapters.py`, `src\nyxpy\framework\core\io\resources.py`, `src\nyxpy\framework\core\macro\command.py`, `src\nyxpy\framework\core\runtime\builder.py`, `src\nyxpy\framework\core\logger\ports.py`, `src\nyxpy\framework\core\api\notification_handler.py`, `src\nyxpy\framework\core\singletons.py`, `tests\unit\framework\io\test_ports.py`, `tests\hardware\test_macro_runtime_realdevice.py` |
| 完了条件 | fake Port で Runtime が単体テスト可能であり、既存 serial/capture/resource/notification/logger 実装は adapter 経由で使える |
| テスト | `test_controller_output_port_serializes_send_operations`, `test_frame_source_await_ready_success_after_first_frame`, `test_frame_source_await_ready_timeout`, `test_notification_port_logs_notifier_failure`, `test_default_logger_emits_structured_log_with_run_context`, `test_serial_controller_output_port_realdevice`, `test_capture_frame_source_realdevice_ready` |
| リスク | 暗黙 dummy fallback の扱い変更、async detection race、frame readiness、GUI preview と Runtime 実行で capture 所有権が競合する |
| ロールバック方針 | Runtime builder の Port 経路だけを無効化する。`DefaultCommand` の旧具象依存経路は戻さない。実機 adapter は単体 fake Port テストと分けて戻せるようにする |

新 Runtime 経路では、本番実行の暗黙 dummy fallback を使わない。`allow_dummy=True` の明示時だけ dummy Port を許可する。

### 4.9 フェーズ 9: CLI 移行

| 項目 | 内容 |
|------|------|
| 目的 | CLI を `MacroRuntimeBuilder` と `RunResult` ベースへ移行し、デバイス検出、通知設定、終了コードを統一する |
| 対象ファイル | `src\nyxpy\cli\run_cli.py`, `src\nyxpy\framework\core\runtime\builder.py`, `src\nyxpy\framework\core\utils\helper.py`, `tests\integration\test_cli_runtime_adapter.py` |
| 完了条件 | CLI は `DefaultCommand` を直接構築せず、Runtime 経由で実行し、成功 0、中断 130、失敗 非 0 の終了コードを `RunResult` から決める |
| テスト | `test_cli_uses_runtime_and_run_result`, `test_cli_adapter_runs_macro_with_define_args`, `test_cli_device_detection_waits_until_complete`, `test_cli_notification_settings_come_from_secrets_store`, `test_parse_define_args_accepts_list_and_string` |
| リスク | CLI 引数互換、`-D` 解析、通知設定ソース、デバイス検出待ち、既存コマンド出力が変わる |
| ロールバック方針 | CLI adapter の呼び出しだけ旧経路へ戻す。旧 `create_command()` と `execute_macro()` の長期互換関数は残さない |

CLI は `serial_manager.get_active_device()` と `capture_manager.get_active_device()` を直接呼ばない。検出完了待ちと dummy 許可は builder に集約する。

### 4.10 フェーズ 10: GUI 移行

| 項目 | 内容 |
|------|------|
| 目的 | GUI の実行制御を `RunHandle` / `RunResult` へ移行し、GUI スレッドから `cmd.stop()` による例外送出をなくす |
| 対象ファイル | `src\nyxpy\gui\main_window.py`, GUI log pane 関連ファイル, `src\nyxpy\framework\core\logger\dispatcher.py`, `src\nyxpy\framework\core\runtime\builder.py`, `tests\gui\test_main_window_runtime_adapter.py` |
| 完了条件 | Run button は `runtime.start(context)` を呼び、Cancel button は `handle.cancel()` を呼び、完了時に `RunResult` を UI 状態へ反映する |
| テスト | `test_gui_start_uses_runtime_handle`, `test_gui_cancel_response`, `test_gui_log_pane_displays_user_event_from_sink`, `test_gui_event_is_separate_from_file_log`, `test_gui_log_sink_exception_is_logged_and_ignored` |
| リスク | Qt thread と Runtime thread の責務混在、GUI log handler の deadlock、preview capture と runtime frame source の所有権競合、終了時 cancel 待ち |
| ロールバック方針 | 既存 `WorkerThread` を Qt signal adapter として残し、Runtime 実行呼び出しだけ旧 executor 経路へ戻す |

core 層に Qt 依存を入れない。GUI は `RunResult` と GUI 表示イベントを Qt signal へ変換する adapter に徹する。

### 4.11 フェーズ 11: MacroExecutor 削除

| 項目 | 内容 |
|------|------|
| 目的 | CLI/GUI 移行後に `MacroExecutor` の参照を削除し、旧入口の互換維持・縮退・非推奨期間を作らない |
| 対象ファイル | `src\nyxpy\framework\core\macro\executor.py`, `src\nyxpy\framework\core\macro\__init__.py`, `tests\integration\test_macro_runtime_entrypoints.py`, 関連ドキュメント |
| 完了条件 | `MacroExecutor` が公開 API、互換契約、GUI/CLI/テスト入口から消えている。削除後の import 互換 shim は存在しない |
| テスト | `test_macro_executor_removed`, `test_gui_cli_do_not_import_macro_executor`, `test_import_contract_keeps_macro_base_command_contract` |
| リスク | 内部の旧テストやサンプルが `MacroExecutor.macros` や `macro` 属性に依存している可能性がある |
| ロールバック方針 | 削除 commit を戻す。互換 shim や `DeprecationWarning` 付き adapter は追加しない |

`MacroExecutor` は既存マクロ互換 API ではないため、成功時 `None`、失敗時例外再送出、`macros` / `macro` 属性の旧契約を保証しない。GUI/CLI/テストが `MacroRuntime` / `RunHandle` / `MacroRegistry` を直接使う状態を削除条件にする。
その他の廃止候補は `DEPRECATION_AND_MIGRATION.md` に従い、singleton 直接利用、暗黙 device detection、dummy fallback、`Path.cwd()` fallback、GUI/CLI 個別 Command 構築、旧 auto discovery、旧 settings lookup を個別に扱う。

### 4.12 フェーズ 12: ドキュメント・移行ガイド整理

| 項目 | 内容 |
|------|------|
| 目的 | 実装後の新 API、維持する互換契約、manifest 任意採用、class metadata、convention discovery、マクロ移行手順、CLI/GUI 移行後の運用、Mermaid 図を文書化する |
| 対象ファイル | `README.md`, `docs\`, `spec/framework/rearchitecture/*.md`, `spec/framework/rearchitecture/ARCHITECTURE_DIAGRAMS.md`, `spec/framework/rearchitecture/MACRO_MIGRATION_GUIDE.md` |
| 完了条件 | マクロ側移行が必要な範囲、新 API を使う場合の入口、削除される旧 API、実機テストの実行条件、全体 Mermaid 図の参照先が読める |
| テスト | ドキュメント変更のみなら実行テストは不要。ただしコード例を変更した場合は関連する単体テストまたは CLI smoke test を実行する |
| リスク | 仕様書と実装差分、移行が必要な範囲の不足、マクロ作者に不要な移行を求める記述 |
| ロールバック方針 | 実装に合わない文書だけを戻し、互換契約とゲート条件の記述は残す |

移行ガイドでは、Resource I/O、settings、manifest 任意採用、single-file マクロの convention discovery、曖昧な場合の明示 entrypoint、`DefaultCommand` 直接生成コードの修正を明記する。Overview から `ARCHITECTURE_DIAGRAMS.md` と `MACRO_MIGRATION_GUIDE.md` へ到達できる状態を維持し、Logging / Resource File I/O / Deprecation の別建て仕様への参照を更新する。

## 5. テスト方針

### 5.1 実行順序

| 順序 | コマンド | 目的 |
|------|----------|------|
| 1 | `uv run pytest tests\unit\` | 既存単体テストと新規中核テストの確認 |
| 2 | `uv run pytest tests\unit\framework\macro\test_import_contract.py` | 互換契約の最小ゲート |
| 3 | `uv run pytest tests\unit\framework\macro\test_registry.py tests\unit\framework\runtime\` | Registry / Factory / Runner / Runtime の確認 |
| 4 | `uv run pytest tests\unit\framework\logger\test_logging_framework.py tests\perf\test_logging_framework_perf.py` | Logging Framework 再設計の確認 |
| 5 | `uv run pytest tests\integration\test_macro_runtime_entrypoints.py tests\integration\test_migrated_macro_compat.py` | 移行後マクロと新 Runtime 入口の互換確認 |
| 6 | `uv run pytest tests\integration\test_cli_runtime_adapter.py` | CLI 移行確認 |
| 7 | `uv run pytest tests\gui\test_main_window_runtime_adapter.py tests\gui\test_log_pane_user_event.py` | GUI 移行と `UserEvent` 表示確認 |
| 8 | `uv run pytest tests\perf\test_macro_discovery_perf.py` | discovery 性能の確認 |
| 9 | `uv run pytest tests\hardware\ -m realdevice` | 実機接続時の確認。通常ゲートからは分離 |
| 10 | `uv run ruff check .` | 静的検査 |
| 11 | `uv run ruff format . --check` | フォーマット確認 |

### 5.2 フェーズ別ゲート

| フェーズ | 必須ゲート | 対応する廃止候補 | 必須テスト例 |
|----------|------------|------------------|--------------|
| 1 | Import gate、signature gate、explicit settings gate、migrated macro gate | 削除なし。廃止候補をテストで固定 | `test_import_contract_*`, `test_migrated_repository_macros_load_with_optional_manifest` |
| 2 | Registry reload、diagnostics、class name collision、new instance per run | 恒久的な `sys.path` 変更、曖昧な class 名 alias 選択 | `test_registry_reload_restores_sys_path`, `test_class_name_collision_requires_qualified_id` |
| 3 | lifecycle order、`finalize` guarantee、`RunResult`、`MacroStopException` compatibility、`safe_point_latency` | `MacroExecutor.execute()` の戻り値 / 例外再送出への内部依存、`Command.stop()` 即時例外送出 | `test_command_stop_requests_cancel_without_raising`, `test_safe_point_latency_perf` |
| 4 | Port Protocol / ABC、fake adapter、不要な中間 facade がないこと | 暗黙 dummy fallback の新規追加禁止 | `test_runtime_builder_disallows_dummy_by_default`, `test_runtime_allows_dummy_when_explicit` |
| 5 | `ExecutionContext` contract、Runtime sync/async、`RunHandle` contract、GUI/CLI の Runtime 入口 | `DefaultCommand` 旧コンストラクタ、GUI/CLI 個別 Command 組み立ての新規追加 | `test_default_command_rejects_legacy_constructor_args`, `test_default_command_tests_use_fake_execution_context` |
| 6 | settings resolver、resource path validation、write/read error normalization、secret masking | settings legacy fallback、`Path.cwd()` 固定の project root 解決 | `test_macro_settings_resolver_does_not_read_legacy_static_settings`, `test_registry_uses_explicit_project_root` |
| 6.1 | resource scope、run artifact store、static 互換削除、atomic write、path guard | Resource I/O legacy static 互換、`StaticResourceIO` 直接利用 | `test_resource_store_rejects_path_escape`, `test_command_save_and_load_image_use_resource_store` |
| 7 | logger port、sink dispatch、run context、user/technical split、legacy log API 削除 | loguru 直結の `LogManager` グローバル初期化 | `test_legacy_log_manager_removed`, `test_log_manager_call_sites_removed` |
| 8 | adapter integration、frame readiness、dummy policy、hardware boundary | `auto_register_devices()` の暗黙非同期検出 API、dummy fallback の本番既定挙動 | `test_cli_device_detection_waits_until_complete`, `test_runtime_realdevice_without_dummy_fallback` |
| 9 | CLI args compatibility、device detection wait、notification settings source、exit code | CLI 側の旧 `DefaultCommand` 直接構築、CLI notification settings の旧経路 | `test_cli_uses_runtime_and_run_result`, `test_cli_does_not_accept_notification_secret_args` |
| 10 | GUI start/cancel/finish、UserEvent display、thread boundary、window close handling | GUI スレッドからの `cmd.stop()` 呼び出し、旧 worker の Command 直接構築 | `test_main_window_uses_run_handle`, `test_main_window_cancel_does_not_raise_in_gui_thread` |
| 11 | `MacroExecutor` 削除確認、GUI/CLI の新 Runtime 入口確認 | `MacroExecutor` 本体と import 互換 shim | `test_macro_executor_removed`, `test_gui_cli_do_not_import_macro_executor` |
| 12 | 文書と実装の差分確認、コード例がある場合の該当テスト | レビューコメントで指摘された文書差分 | `rg` による必須セクション検査、関連 doc/code example test |

### 5.3 マクロ移行後の合格条件

- 代表マクロが manifest entrypoint または convention discovery から import、registry 登録、settings 解決、`initialize -> run -> finalize` 実行へ進める。
- 既存 `Command` メソッド呼び出しが `TypeError` にならない。
- 既存 `MacroStopException` を直接送出するマクロが中断として扱われる。
- manifest または class metadata settings path の settings が読み込まれ、CLI/GUI 実行引数で上書きできる。
- GUI/CLI/テストは `MacroExecutor.execute()`、`macros`、`macro` に依存しない。

### 5.4 計画書作成時の検証

本ファイル作成時は、次の確認を行う。

| コマンド | 検証内容 |
|----------|----------|
| `git diff --check` | 行末空白、混在インデント、patch として不正な空白を検出する |
| `rg "T[O]D[O]|T[B]D|x{3}|\[T[O]D[O]\]" spec\framework\rearchitecture` | 未解決 placeholder と仮テキストを検出する。一致なしを合格とする |
| `rg "^## ..."` | 必須 6 セクションが存在することを確認する。6 行が出ることを合格とする |

```powershell
git diff --check
rg "T[O]D[O]|T[B]D|x{3}|\[T[O]D[O]\]" spec\framework\rearchitecture
rg "^## (1\. 概要|2\. 対象ファイル|3\. 設計方針|4\. 実装仕様|5\. テスト方針|6\. 実装チェックリスト)\r?$" spec\framework\rearchitecture\IMPLEMENTATION_PLAN.md
```

`rg` の placeholder 検査は一致なしを合格とする。必須 6 セクション検査は 6 行が出ることを合格とする。

## 6. 実装チェックリスト

### 6.1 計画策定チェックリスト

- [x] 必読仕様を確認し、実装順序へ反映
- [x] 維持する互換契約とマクロ側移行が必要な項目を明記
- [x] `MacroExecutor` を削除対象として扱う範囲を明記
- [x] `MacroRuntime` / `MacroRunner` / `MacroRegistry` / `MacroDefinition.factory` を新実行中核として配置
- [x] 12 フェーズと 6.1 補助フェーズを実装順序として定義
- [x] 各フェーズに目的、対象ファイル、完了条件、テスト、リスク、ロールバック方針を記載
- [x] コミット分割方針を Conventional Commits 形式で記載
- [x] Commits に Why を残す方針を明記
- [x] 移行後マクロ互換を壊していないことのゲート条件を記載

### 6.2 実装チェックリスト

- [ ] フェーズ 1 の互換テストを実装
- [ ] フェーズ 2 の Registry/Factory を実装
- [ ] フェーズ 3 の Runner/RunResult/Error/Cancellation を実装
- [ ] フェーズ 4 の Port Protocol / fake adapter 最小定義を実装
- [ ] フェーズ 5 の Runtime/DefaultCommand を実装
- [ ] フェーズ 6 の Settings/Resource 分離を実装
- [ ] フェーズ 6.1 の Resource File I/O 再設計を実装
- [ ] フェーズ 7 の Logging Framework 再設計を実装し、旧 `LogManager` / `log_manager.log()` 呼び出し元と event catalog 更新ゲートを完了
- [ ] フェーズ 8 の Ports/Adapters を実装
- [ ] フェーズ 9 の CLI adapter を実装
- [ ] フェーズ 10 の GUI adapter を実装
- [ ] フェーズ 11 の `MacroExecutor` 削除を実施
- [ ] フェーズ 12 のドキュメント・移行ガイドを整理
