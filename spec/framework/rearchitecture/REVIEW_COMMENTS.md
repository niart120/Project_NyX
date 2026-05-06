# フレームワーク再設計ドキュメント群 レビューコメント

## レビュー対象

`spec\framework\rearchitecture` 配下の再設計ドキュメント 13 件を対象に、仕様書フォーマット、文書間整合性、実装可能性、後方互換性、テスト方針の観点でレビューした。

対象ドキュメント:

| ファイル | 位置づけ |
|----------|----------|
| `FW_REARCHITECTURE_OVERVIEW.md` | 再設計全体方針 |
| `ARCHITECTURE_DIAGRAMS.md` | アーキテクチャ図 |
| `MACRO_COMPATIBILITY_AND_REGISTRY.md` | マクロ互換性、Registry |
| `RUNTIME_AND_IO_PORTS.md` | Runtime、Ports、Builder |
| `ERROR_CANCELLATION_LOGGING.md` | 例外、キャンセル、ErrorInfo |
| `LOGGING_FRAMEWORK.md` | ロギング基盤 |
| `CONFIGURATION_AND_RESOURCES.md` | settings 境界 |
| `RESOURCE_FILE_IO.md` | Resource File I/O |
| `OBSERVABILITY_AND_GUI_CLI.md` | GUI/CLI 入口、表示 |
| `DEPRECATION_AND_MIGRATION.md` | 廃止候補、移行方針 |
| `MACRO_MIGRATION_GUIDE.md` | マクロ移行手順 |
| `TEST_STRATEGY.md` | テスト戦略 |
| `IMPLEMENTATION_PLAN.md` | 実装計画 |

## 総評

各ドキュメントは必須 6 セクションをおおむね満たしており、Runtime、Registry、Resource I/O、Logging、GUI/CLI、テスト戦略を分割して管理する方針も妥当である。特に「既存マクロが依存する import / lifecycle を維持し、GUI/CLI と内部実装は Runtime へ寄せる」という軸は一貫している。

ただし、互換契約と移行対象の境界、`Command.stop()` の振る舞い、`MacroRuntime` と `MacroFactory` の責務、`LoggerPort` の正 API、Resource I/O の配置名に不整合がある。現状のまま実装へ進むと、テストがどの契約を固定すべきか曖昧になり、互換維持対象を誤って破壊するリスクが高い。以下の P0 / P1 を先に解消してから実装フェーズへ進むべきである。

## 採否・反映結果

本節はレビュー後の判断結果である。以降の「指摘一覧」はレビュー時点の問題記録として残し、最終方針はこの表を優先する。

| ID | 採否 | 最終方針 | 主な反映先 |
|----|------|----------|------------|
| P0-1 | 採用 | 旧 settings lookup は互換契約から外し、manifest settings path と `exec_args` merge を新契約として固定する。 | `FW_REARCHITECTURE_OVERVIEW.md`, `DEPRECATION_AND_MIGRATION.md`, `RUNTIME_AND_IO_PORTS.md` |
| P0-2 | 採用 | 「既存マクロ変更 0 件」は import / lifecycle 互換に起因するマクロ本体変更へ限定し、配置・settings・resources の移行は別指標にする。 | `IMPLEMENTATION_PLAN.md`, `TEST_STRATEGY.md`, `OBSERVABILITY_AND_GUI_CLI.md` |
| P0-3 | 案 2 採用 | `Command.stop()` は協調キャンセル優先へ変更する。即時脱出が必要な利用箇所は `stop(raise_immediately=True)` へ移行する。 | `ERROR_CANCELLATION_LOGGING.md`, `RUNTIME_AND_IO_PORTS.md`, `MACRO_MIGRATION_GUIDE.md`, `TEST_STRATEGY.md` |
| P0-4 | 再整理して採用 | `MacroDefinition` が factory を所有し、Runtime は `definition.factory.create()` を呼ぶ。Runtime に別 factory facade を持たせない。 | `MACRO_COMPATIBILITY_AND_REGISTRY.md`, `RUNTIME_AND_IO_PORTS.md`, `FW_REARCHITECTURE_OVERVIEW.md`, `ARCHITECTURE_DIAGRAMS.md` |
| P0-5 | 方針変更して採用 | `LOGGING_FRAMEWORK.md` を正とし、旧 `log_manager.log()` / handler API / 互換 adapter は残さない。呼び出し元を新 API へ置換する。 | `LOGGING_FRAMEWORK.md`, `RUNTIME_AND_IO_PORTS.md`, `IMPLEMENTATION_PLAN.md`, `OBSERVABILITY_AND_GUI_CLI.md` |
| P1-1 | 採用 | Error code catalog を `NYX_*` code へ統一し、詳細仕様は catalog を参照する。 | `ERROR_CANCELLATION_LOGGING.md`, `CONFIGURATION_AND_RESOURCES.md`, `RUNTIME_AND_IO_PORTS.md` |
| P1-2 | 採用 | キャンセル応答の合格条件は 100 ms 未満に統一する。`wait_poll_interval_sec = 0.05` は内部ポーリング値として扱う。 | `ERROR_CANCELLATION_LOGGING.md`, `RUNTIME_AND_IO_PORTS.md`, `TEST_STRATEGY.md` |
| P1-3 | 採用 | Resource I/O の正配置を `src\nyxpy\framework\core\io\resources.py` に統一する。 | `RESOURCE_FILE_IO.md`, `RUNTIME_AND_IO_PORTS.md`, `DEPRECATION_AND_MIGRATION.md`, `IMPLEMENTATION_PLAN.md` |
| P1-4 | 再検査付きで採用 | Runtime 実装前に Port Protocol / fake adapter の最小定義を置く。ただし Command facade、io 側 LoggerPort 再定義、Factory facade などの中間層は追加しない。 | `IMPLEMENTATION_PLAN.md`, `RUNTIME_AND_IO_PORTS.md`, `TEST_STRATEGY.md` |
| P1-5 | 採用 | 新規単体テスト配置は `tests\unit\framework\...` へ統一する。 | `TEST_STRATEGY.md`, `CONFIGURATION_AND_RESOURCES.md`, `MACRO_COMPATIBILITY_AND_REGISTRY.md` |
| P1-6 | 不採用 | 現時点で外部利用者はいない前提とし、`MacroExecutor` 外部向けドキュメンテーションは追加しない。削除前の内部参照解消だけを確認する。 | `DEPRECATION_AND_MIGRATION.md`, `IMPLEMENTATION_PLAN.md`, `TEST_STRATEGY.md` |
| P2-1 | 採用 | Markdown 相対リンクと portable path は `/`、PowerShell コマンドと Windows 配置例は `\` とする。 | 全 rearchitecture 文書 |
| P2-2 | 採用 | Overview の `Command` API 抜粋に `touch_down()` / `touch_up()` を含める。 | `FW_REARCHITECTURE_OVERVIEW.md` |

## 指摘一覧

### P0-1. settings lookup が互換契約なのか移行対象なのか矛盾している

**対象箇所**

- `FW_REARCHITECTURE_OVERVIEW.md` 8, 14, 74-77, 198-203, 213
- `DEPRECATION_AND_MIGRATION.md` 19, 98, 162-164
- `CONFIGURATION_AND_RESOURCES.md` 47-49, 92-95
- `MACRO_MIGRATION_GUIDE.md` 63-73, 218-227

**内容**

Overview と Deprecation では、`settings lookup` が互換契約に含まれるように読める記述が残っている。一方で、Configuration、Resource、Migration Guide では `static\<macro_name>\settings.toml` と `Path.cwd()` fallback を維持せず、manifest settings path へ移行すると定義している。

このままでは Phase 0 の import/signature 互換テストで旧 settings lookup を固定すべきなのか、移行後 settings だけを固定すべきなのか判断できない。

**修正案**

互換契約から `既存 settings lookup` を明示的に外す。Overview の Phase 0 にある `settings lookup の契約を固定` は `manifest settings path と exec_args merge の契約を固定` に置き換える。Deprecation の `Compatibility Contract` 定義も、settings lookup を含めず、`Resource/settings/entrypoint は移行対象` と統一する。

### P0-2. 「既存ユーザーマクロのソース変更 0 件」と移行ガイドの要求が衝突している

**対象箇所**

- `IMPLEMENTATION_PLAN.md` 44-55, 56-64, 388-395
- `TEST_STRATEGY.md` 48-55, 264-267
- `RESOURCE_FILE_IO.md` 31-35, 48-55
- `MACRO_MIGRATION_GUIDE.md` 49-59, 168-182, 216-227

**内容**

Implementation Plan は期待効果として「既存ユーザーマクロのソース変更 0 件」を掲げているが、Migration Guide は各マクロへの `macro.toml` 追加、settings 移動、assets 移動、`cmd.load_img()` / `cmd.save_img()` の path 修正、`DefaultCommand` 直接生成の削除を要求している。Resource File I/O でも代表マクロの保存先や直接 `Path` 保存の修正を要求している。

`TEST_STRATEGY.md` の「既存マクロ本体を編集しない」も、移行後 repository macro をロードする方針と衝突している。

**修正案**

互換性を次の 2 種類に分けて明記する。

| 区分 | 変更可否 | 固定するもの |
|------|----------|--------------|
| Framework import/lifecycle 互換 | マクロ本体の `MacroBase` / `Command` 呼び出し形は変更不要 | import path、lifecycle、Command method name、`MacroStopException` |
| マクロ配置・リソース移行 | repository macro と利用者マクロの配置修正が必要 | `macro.toml`、manifest settings、assets root、run outputs |

Implementation Plan の「既存ユーザーマクロのソース変更 0 件」は、「維持対象 import / lifecycle に起因するソース変更 0 件」などに狭める。Migration Guide の作業は「配置・設定・リソース移行」として別の成功指標にする。

### P0-3. `Command.stop()` の既存挙動を破壊する設計になっている

**対象箇所**

- `src\nyxpy\framework\core\macro\command.py` 255-258
- `RUNTIME_AND_IO_PORTS.md` 516-517, 587-589, 599
- `ERROR_CANCELLATION_LOGGING.md` 370-378
- `TEST_STRATEGY.md` 316-318

**内容**

現行 `DefaultCommand.stop()` は `ct.request_stop()` の直後に `MacroStopException` を送出する。再設計仕様では `Command.stop(raise_immediately=False)` を追加し、既定では例外を送出しない方針になっている。

これは既存マクロが `cmd.stop()` を「即時脱出」として使っている場合に破壊的変更になる。仕様上は import / lifecycle / Command API を維持するとしているため、メソッド名だけでなく主要な実行時意味論も互換テストで固定する必要がある。

**修正案**

どちらを採用するか明示する。

1. 既存互換を優先する場合: `Command.stop()` は引き続き即時に `MacroStopException` を送出し、新 API として `request_cancel()` または `stop(raise_immediately=False)` を別名で追加する。
2. 協調キャンセルを優先する場合: `cmd.stop()` の挙動変更を破壊的変更として Migration Guide に載せ、代表マクロとテストの修正対象に入れる。

現行の互換方針から判断すると、案 1 の方が文書全体の主張と整合する。

### P0-4. `MacroRuntime` と `MacroFactory` の責務・シグネチャが一致していない

**対象箇所**

- `MACRO_COMPATIBILITY_AND_REGISTRY.md` 249-258, 261-273, 285-304, 340-351
- `RUNTIME_AND_IO_PORTS.md` 358-367, 540-560
- `IMPLEMENTATION_PLAN.md` 235-247

**内容**

`MACRO_COMPATIBILITY_AND_REGISTRY.md` では `MacroDefinition.factory: MacroFactory` を持ち、`MacroFactory.create(self) -> MacroBase` と定義している。一方、`RUNTIME_AND_IO_PORTS.md` の同期実行シーケンスでは `definition = registry.resolve(context.macro_id)` の後に `macro = factory.create(definition)` としており、`MacroRuntime.__init__()` も `factory: MacroFactory | None` を受け取る。

つまり、Factory が `MacroDefinition` ごとに保持されるのか、Runtime が共有 Factory に `MacroDefinition` を渡すのかが不明である。

**修正案**

どちらかに統一する。

| 案 | API | 評価 |
|----|-----|------|
| Definition 所有型 | `definition.factory.create()` | `MacroDefinition` と entrypoint loader の責務が明確。現行 `MACRO_COMPATIBILITY_AND_REGISTRY.md` と整合する |
| 共有 Factory 型 | `factory.create(definition)` | Runtime 側で生成ポリシーを差し替えやすい。`MacroFactory` Protocol のシグネチャ変更が必要 |

現状の Registry 仕様に合わせるなら、Runtime シーケンスを `macro = definition.factory.create()` に修正し、`MacroRuntime.__init__()` から `factory` 引数を外すか、既定生成ポリシーではなくテスト用 override として意味を再定義する。

### P0-5. `LoggerPort` の正 API が文書間で分裂している

**対象箇所**

- `LOGGING_FRAMEWORK.md` 233-256, 277-297
- `RUNTIME_AND_IO_PORTS.md` 503-506, 580-595, 631-633
- `TEST_STRATEGY.md` 240-245, 276-282
- `OBSERVABILITY_AND_GUI_CLI.md` 185-191

**内容**

Logging Framework は `LoggerPort.bind_context()`, `technical()`, `user()` を正 API としている。一方、Runtime と Test Strategy は `LoggerPort.log(level, message, component)` を前提にしている。Runtime の `CommandFacade.log()` も `logger.log()` へ委譲する設計で、`UserEvent` / `TechnicalLog` の分離が反映されていない。

このままでは Runtime 実装者が `LoggerPort` をどの形で実装すべきか判断できず、GUI/CLI 表示イベントと技術ログの分離が崩れる。

**修正案**

`LOGGING_FRAMEWORK.md` を正とするなら、`RUNTIME_AND_IO_PORTS.md` の `LoggerPort` 定義を削除し、`from nyxpy.framework.core.logger.ports import LoggerPort` を参照する。`CommandFacade.log()` の委譲先は `logger.user(...)` とし、必要な対応 technical log は Logging Framework 側の「user は要約 TechnicalLog も生成する」規則に任せる。旧 `log_manager.log()` は `LogManager` の互換 adapter として閉じ込める。

### P1-1. Error code catalog と Runtime 例外名・コードが対応していない

**対象箇所**

- `ERROR_CANCELLATION_LOGGING.md` 335-356
- `RUNTIME_AND_IO_PORTS.md` 613, 699-717
- `CONFIGURATION_AND_RESOURCES.md` 244-250
- `OBSERVABILITY_AND_GUI_CLI.md` 208-217

**内容**

Error code catalog は `NYX_FRAME_NOT_READY` などの安定コードを正本として定義している。一方、Runtime では `FrameNotReadyError(code="runtime.frame.not_ready")` と別系統のコード例が出ている。Runtime の `RuntimeConfigurationError`, `DeviceDetectionTimeoutError`, `DummyDeviceNotAllowedError` なども、`FrameworkError` 階層・`ErrorKind`・`NYX_*` code への対応表がない。

**修正案**

`ERROR_CANCELLATION_LOGGING.md` に Runtime / Config / Resource / GUI/CLI で使う全 error code を集約し、各詳細仕様はその code を参照するだけにする。Runtime 側の例は `FrameNotReadyError(code="NYX_FRAME_NOT_READY")` に修正する。例外クラスごとに `kind` と code を対応付ける表を追加する。

### P1-2. キャンセル応答の目標値が 50 ms と 100 ms で揺れている

**対象箇所**

- `FW_REARCHITECTURE_OVERVIEW.md` 77, 258
- `RUNTIME_AND_IO_PORTS.md` 587, 689, 741-743
- `ERROR_CANCELLATION_LOGGING.md` 60, 363-369
- `TEST_STRATEGY.md` 45, 249-253

**内容**

Runtime では `wait_poll_interval_sec = 0.05` と 50 ms 周期を目標にしている。一方、Error/Cancellation と Test Strategy は 100 ms をキャンセル応答上限としている。実装上は「poll interval 50 ms、外部観測上限 100 ms」のように両立可能だが、現状の記述ではどちらが合格条件か不明である。

**修正案**

`RuntimeOptions.wait_poll_interval_sec = 0.05` を内部ポーリング周期、`test.cancel_latency_limit_sec = 0.1` をテスト上限として明記する。テスト方針では「通常は 100 ms 未満、内部 safe point は 50 ms 以下の周期で確認」と表現を統一する。

### P1-3. Resource I/O の正配置ファイル名が揺れている

**対象箇所**

- `RESOURCE_FILE_IO.md` 65
- `RUNTIME_AND_IO_PORTS.md` 256, 461-495
- `DEPRECATION_AND_MIGRATION.md` 66
- `IMPLEMENTATION_PLAN.md` 252-267

**内容**

Resource I/O の実装先として、`src\nyxpy\framework\core\io\resources.py`、`src\nyxpy\framework\core\io\resource_store.py`、`src\nyxpy\framework\core\io\ports.py`、`io\adapters.py` が混在している。どれが抽象、どれが具象 adapter、どれが re-export なのか未確定である。

**修正案**

正配置を 1 つに決める。例:

| ファイル | 役割 |
|----------|------|
| `core\io\resources.py` | `ResourceRef`, `MacroResourceScope`, `ResourceStorePort`, `RunArtifactStore`, `ResourcePathGuard` |
| `core\io\adapters.py` | filesystem 実装、OpenCV write 実装 |
| `core\io\__init__.py` | public re-export |

この方針に合わせて Deprecation と Implementation Plan の対象ファイルを更新する。

### P1-4. Runtime 実装フェーズが必要な抽象・Ports より先に来ている

**対象箇所**

- `IMPLEMENTATION_PLAN.md` 235-270, 371-386
- `RUNTIME_AND_IO_PORTS.md` 278-293, 410-412, 540-560
- `RESOURCE_FILE_IO.md` 214-248

**内容**

Implementation Plan では Phase 4 で Runtime/CommandFacade を導入し、Phase 5/5A で Settings/Resource、Phase 7 で Ports/Adapters を導入する構成になっている。しかし `ExecutionContext` は Phase 4 時点で `ControllerOutputPort`, `FrameSourcePort`, `ResourceStorePort`, `RunArtifactStore`, `NotificationPort`, `LoggerPort` を必須フィールドとして持つ。

抽象 Port が未定義のまま Runtime を実装するか、一時型を作って後で置き換える計画になりやすい。

**修正案**

Phase 4 の前に「Port Protocol / ABC と fake adapter の最小定義」を置く。具象 adapter は後続 Phase でよいが、`ExecutionContext` の型が参照する抽象は Runtime 導入前に確定させる。

### P1-5. テスト配置パスが文書間で統一されていない

**対象箇所**

- `MACRO_COMPATIBILITY_AND_REGISTRY.md` 75-78
- `TEST_STRATEGY.md` 60-74, 140-145
- `IMPLEMENTATION_PLAN.md` 72-84, 360-369
- 現行コード: `tests\unit\command\`, `tests\unit\executor\`, `tests\gui\`, `tests\integration\`

**内容**

新規テストの配置が `tests\unit\macro\...` と `tests\unit\framework\macro\...` で揺れている。現行テストは `tests\unit\command\` や `tests\unit\executor\` に存在するため、既存テストを移動するのか、新階層へ追加するのかが不明である。

**修正案**

再設計後のテスト配置を `TEST_STRATEGY.md` に正本として定義し、他文書はそれを参照する。既存テストを移動する場合は移動対象を Implementation Plan に明記する。移動しない場合は、既存階層と新規 `tests\unit\framework\...` 階層の棲み分けを記述する。

### P1-6. `MacroExecutor` を非公開扱いで即削除する判断は、外部利用者への影響説明が不足している

**対象箇所**

- `FW_REARCHITECTURE_OVERVIEW.md` 180-205, 222
- `DEPRECATION_AND_MIGRATION.md` 157-166
- `TEST_STRATEGY.md` 112, 316-319
- 現行コード: `src\nyxpy\cli\run_cli.py`, `src\nyxpy\gui\main_window.py`, `tests\unit\executor\test_executor.py`

**内容**

文書群は `MacroExecutor` を既存マクロ互換契約から外し、非推奨期間や import shim なしで削除する方針で統一している。方針自体は一貫しているが、`MacroExecutor` は `nyxpy.framework.core.macro.executor` に存在する core 層クラスであり、GUI/CLI と既存テストが直接 import している。外部スクリプトが使っている可能性を「互換対象外」とする根拠が不足している。

**修正案**

`MacroExecutor` を「アプリ内部 API」として扱う根拠を明記する。公開パッケージとして配布している場合は、リリースノートまたは Migration Guide に「外部自動化コードは `MacroRuntime` へ移行」と書く。即削除を維持するなら、削除前の grep 対象に `samples\`, `docs\`, `README.md` も含める。

### P2-1. Markdown 内の相対リンクとパス区切りを統一した方がよい

**対象箇所**

- `FW_REARCHITECTURE_OVERVIEW.md` 6
- `MACRO_COMPATIBILITY_AND_REGISTRY.md` 4-7
- `RESOURCE_FILE_IO.md` 88-112
- `MACRO_MIGRATION_GUIDE.md` 83-89, 101-107

**内容**

同じ文書群内で `spec\framework\...` と `spec/framework/...`、TOML 内の `project:resources/frlg_id_rng/settings.toml` と本文の `resources\frlg_id_rng\...` が混在している。Windows の実行例は backslash でよいが、Markdown の相対リンクや manifest 内のパス表記は、読み手や GitHub 表示で解釈がずれやすい。

**修正案**

次の基準を置く。

| 用途 | 推奨表記 |
|------|----------|
| PowerShell コマンド、Windows 実パス例 | `\` |
| Markdown 相対リンク | `/` |
| TOML manifest の portable path | `/` |
| 文書内の Windows 配置例 | `\` を使う場合は「Windows 表記例」と明記 |

### P2-2. Overview の Command API 抜粋が現行公開面を一部省略している

**対象箇所**

- `FW_REARCHITECTURE_OVERVIEW.md` 43-47, 318-388
- `MACRO_COMPATIBILITY_AND_REGISTRY.md` 318-338
- `src\nyxpy\framework\core\macro\command.py` 23-165

**内容**

Overview の現行事実では `Command` の公開メソッドとして `touch_down()` / `touch_up()` が抜けている箇所がある。後続のコードブロックや Test Strategy では含まれているため致命的ではないが、Overview を入口に読むと互換対象を過小評価する。

**修正案**

Overview の現行事実と互換表に `touch_down()` / `touch_up()` を含める。正 API は `MACRO_COMPATIBILITY_AND_REGISTRY.md` の一覧と一致させる。

## フォーマット観点の確認結果

| 観点 | 結果 | コメント |
|------|------|----------|
| 必須 6 セクション | 概ね満たしている | 13 件すべてで `1. 概要` から `6. 実装チェックリスト` まで存在する |
| 用語定義 | 概ね表形式 | 用語の意味が文書ごとに少し揺れるため、正本を持つ用語は「正本は X」と追記するとよい |
| 公開 API | 記載あり | Runtime、Logger、Resource の API は文書間で差分があるため P0/P1 を優先して修正する |
| 後方互換性 | 記載あり | settings lookup、`Command.stop()`、マクロ移行作業の扱いを再整理する必要がある |
| テスト方針 | 記載あり | テスト配置パスと移行前/移行後 fixture の境界を統一する必要がある |
| 設計原則 | 概ね反映 | GUI/CLI 逆依存禁止、Port 抽象、singletons 限定、スレッド安全性は明記されている |

## 修正優先度

1. P0-1 から P0-5 を先に修正し、互換契約・Runtime API・Logger API の正本を確定する。
2. P1-1 から P1-5 を修正し、実装フェーズ、error code、Resource 配置、テスト配置を固定する。
3. P1-6 と P2 を修正し、外部利用者向けの移行説明と読みやすさを整える。

この順で直すと、Phase 1 の互換テストが「何を守るテストか」を明確にでき、以降の Runtime / Port / GUI / CLI 実装が文書間の解釈差に引きずられにくくなる。
