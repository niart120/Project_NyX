# フレームワーク再設計ドキュメント群レビューコメント

> **対象**: `spec\framework\rearchitecture\*.md`  
> **作成日**: 2026-05-07  
> **目的**: 再設計仕様群を実装前に読み合わせるため、修正すべき論点を別ファイルに集約する。
> **対応状況**: 2026-05-07 の判断に基づき、RC-001〜RC-018 の反映方針を各正本ドキュメントへ適用済み。本ファイルの個別コメントは初回レビュー時点の記録として残す。

## 1. 総評

13 文書はいずれも、フレームワーク仕様書の基本構成である「概要」「対象ファイル」「設計方針」「実装仕様」「テスト方針」「実装チェックリスト」を備えている。構成面の大きな欠落はない。

実装前に優先して解消すべき論点は、Runtime build request と secrets の受け渡し、core 層と GUI/CLI composition root の責務境界、Port 抽象の正本管理である。これらは実装者ごとに解釈が分かれると、依存方向違反、秘密値漏洩、重複 API 定義につながる。

## 2. 優先度別コメント

### 2.1 重大

#### RC-001: `RuntimeBuildRequest.secrets` の有無が文書間で矛盾している

- **対象**: `RUNTIME_AND_IO_PORTS.md:369-392`, `OBSERVABILITY_AND_GUI_CLI.md:184-193`
- **問題**: `OBSERVABILITY_AND_GUI_CLI.md` は CLI/GUI adapter が `RuntimeBuildRequest.secrets` へ secrets snapshot を渡す前提で記述している。一方、`RUNTIME_AND_IO_PORTS.md` の `RuntimeBuildRequest` には `secrets` フィールドがなく、`MacroRuntimeBuilder.__init__()` が `secrets: SecretsSnapshot` を受け取る定義である。
- **影響**: CLI 引数由来の通知 secret を request 単位で渡すのか、builder lifetime で固定するのかが不明になる。CLI の一時 secrets snapshot を安全に扱う実装位置が分かれ、通常設定やログ context へ平文が混入するリスクがある。
- **修正案**: 正本である `RUNTIME_AND_IO_PORTS.md` に合わせてどちらかへ統一する。実行ごとに CLI/GUI 由来の一時 secret を扱うなら `RuntimeBuildRequest` に `secrets: SecretsSnapshot | None = None` を追加し、builder 保持の secrets と request secrets の優先順位を明記する。builder lifetime で固定するなら `OBSERVABILITY_AND_GUI_CLI.md` の `RuntimeBuildRequest.secrets` 表記を削除し、CLI adapter が builder 生成前に一時 `SecretsSnapshot` を作る流れへ書き換える。

#### RC-002: core runtime builder が GUI/CLI 用 logger 構成を担当するように読める

- **対象**: `LOGGING_FRAMEWORK.md:75-82`, `LOGGING_FRAMEWORK.md:289-291`, `OBSERVABILITY_AND_GUI_CLI.md:195-197`
- **問題**: `LOGGING_FRAMEWORK.md` の対象ファイル表では `src\nyxpy\framework\core\runtime\builder.py` が「CLI/GUI 用の logger 構成」を担当すると書かれている。一方、同文書の初期化方針では GUI/CLI composition root が `LogBackend`、`LogSinkDispatcher`、`LogSanitizer`、`DefaultLogger` を明示生成するとしている。
- **影響**: `core\runtime\builder.py` が GUI/CLI 用 sink や presenter の知識を持つ実装になり、`nyxpy.framework.* -> nyxpy.gui` / `nyxpy.cli` 依存禁止に抵触する可能性がある。
- **修正案**: 対象ファイル表の `runtime\builder.py` の説明を「`LoggerPort` を受け取り `ExecutionContext` へ注入する」に変更する。GUI/CLI 用 logger 構成は `src\nyxpy\cli\run_cli.py` と GUI composition root 側の責務として明記し、core 層は `LoggerPort` Protocol だけに依存する、と統一する。

#### RC-003: 秘密値の一時 snapshot とログ sanitizing の境界が実装 API として不足している

- **対象**: `CONFIGURATION_AND_RESOURCES.md:165-172`, `CONFIGURATION_AND_RESOURCES.md:248-262`, `OBSERVABILITY_AND_GUI_CLI.md:184-193`
- **問題**: `SecretsStore.get_secret()` と `snapshot_masked()` は定義されているが、CLI/GUI が作る一時 secrets snapshot の型、mask 済み snapshot と平文取得 API の使い分け、`RunResult.error.message` や `TechnicalLog.extra` へ渡す前の sanitizing 手順が文書横断でまとまっていない。
- **影響**: 通知 adapter 初期化の過程で secret を `exec_args`、通常 settings、metadata、log extra に複製する実装が混入しても、仕様上どこで検出するかが曖昧になる。
- **修正案**: `CONFIGURATION_AND_RESOURCES.md` に「secret boundary contract」を追加する。少なくとも、平文 secret を読める呼び出し元、mask 済み snapshot の用途、`RuntimeBuildRequest` / `MacroRuntimeBuilder` が受け付ける secret 入力、`ConfigurationError` にする禁止経路、ログ出力前に必ず通す sanitizer を表で定義する。

### 2.2 中

#### RC-004: Port 抽象を増やす範囲が Overview と個別仕様で一致していない

- **対象**: `FW_REARCHITECTURE_OVERVIEW.md:255-263`, `RESOURCE_FILE_IO.md:216-230`, `RUNTIME_AND_IO_PORTS.md:457-500`, `LOGGING_FRAMEWORK.md:236-259`
- **問題**: Overview は「追加抽象が必要な境界は `SettingsPort`、`ClockPort`、`RuntimeThreadPort` に限定する」としているが、個別仕様では `ResourceStorePort`、`RunArtifactStore`、`NotificationPort`、`LoggerPort` などの Port 抽象を定義している。
- **影響**: 実装者が Overview を優先すると個別仕様の Port を作らず、個別仕様を優先すると Overview の抽象制限と矛盾する。抽象の追加判断がレビュー不能になる。
- **修正案**: Overview の記述を「Overview で追加可否を判断する Port」と「個別仕様で正本定義済みの Port」に分ける。例: `LoggerPort` は `LOGGING_FRAMEWORK.md`、`ResourceStorePort` / `RunArtifactStore` は `RESOURCE_FILE_IO.md`、`NotificationPort` は `RUNTIME_AND_IO_PORTS.md` を正本とする。

#### RC-005: ResourceStorePort / RunArtifactStore が複数文書で公開 API として重複定義されている

- **対象**: `FW_REARCHITECTURE_OVERVIEW.md:41-50`, `RESOURCE_FILE_IO.md:216-230`, `RUNTIME_AND_IO_PORTS.md:457-491`
- **問題**: Overview は `MacroResourceScope` / `ResourceStorePort` / `RunArtifactStore` / `ResourcePathGuard` の正本を `RESOURCE_FILE_IO.md` と定義しているが、`RUNTIME_AND_IO_PORTS.md` でも同じ Port のメソッドシグネチャを公開 API として再掲している。
- **影響**: 片方の引数名、戻り値、既定値だけが変更されると、どちらを実装すべきか分からなくなる。特に `filename` / `name` の引数名差分は signature 互換テストの対象にすると破綻しやすい。
- **修正案**: `RUNTIME_AND_IO_PORTS.md` は Resource Port の詳細シグネチャを削り、`RESOURCE_FILE_IO.md` への参照と Runtime が呼ぶメソッド名だけに留める。再掲が必要なら「抜粋であり正本ではない」と明記し、引数名も正本と完全一致させる。

#### RC-006: `FrameSourcePort.await_ready()` の既定 timeout の所有者が曖昧である

- **対象**: `RUNTIME_AND_IO_PORTS.md:200-210`, `RUNTIME_AND_IO_PORTS.md:271-276`, `RUNTIME_AND_IO_PORTS.md:443-449`
- **問題**: 性能要件と `RuntimeOptions` は frame ready timeout を 3 秒としているが、`FrameSourcePort.await_ready(timeout: float | None = None)` は `None` を既定値にしている。`None` の場合に Port が 3 秒を使うのか、Runtime builder が必ず `RuntimeOptions.frame_ready_timeout_sec` を渡すのかが未定義である。
- **影響**: Port 実装ごとに無限待ち、即時失敗、独自既定値が混在し、GUI/CLI 起動時のブロック時間やテスト期待値がずれる。
- **修正案**: timeout の所有者を Runtime に固定し、`MacroRuntimeBuilder` または `MacroRuntime` が `context.options.frame_ready_timeout_sec` を必ず `await_ready()` に渡す、と明記する。Port 側の `None` は「adapter 固有の既定値を使わず、Runtime から渡された値だけを受ける」または「無限待ち禁止」と定義する。

#### RC-007: 通知失敗時の例外・ログ境界が `NotificationPort` 仕様として薄い

- **対象**: `RUNTIME_AND_IO_PORTS.md:580-588`, `RUNTIME_AND_IO_PORTS.md:618-620`, `LOGGING_FRAMEWORK.md:348-363`
- **問題**: 通知失敗はマクロ失敗にしない方針はあるが、`NotificationPort.publish()` が内部で捕捉する例外の範囲、`NYX_NOTIFICATION_FAILED` の log extra、`notification.failed` UserEvent の有無、複数 notifier の一部失敗時の集約方法が未定義である。
- **影響**: 通知失敗を完全に握りつぶす実装と、warning log に十分な診断情報を残す実装が混在する。障害調査時に通知先種別や mask 済み原因を追跡できない。
- **修正案**: `NotificationError` / `NotificationConfigError` を定義するか、内部例外を `TechnicalLog(event="notification.failed", code="NYX_NOTIFICATION_FAILED")` に正規化する規則を追加する。`RunResult.status` は変更しないが、warning log と `cleanup_warnings` へ入れるかどうかを明記する。

#### RC-008: atomic write 失敗時の cleanup 手順が不足している

- **対象**: `RESOURCE_FILE_IO.md:303-309`
- **問題**: `cv2.imwrite()` が `False` を返す、一時ファイルが存在しない、replace 後に最終ファイルが存在しない場合は `ResourceWriteError` とする方針はあるが、一時ファイル作成失敗、`Path.replace()` 失敗、ディスク満杯、権限不足時の cleanup 責務が明記されていない。
- **影響**: 失敗後に一時ファイルが残り、再実行時の UNIQUE 採番やディスク使用量に影響する。テストでも「例外を送出する」以外の後始末を検証できない。
- **修正案**: atomic write の手順に `try/finally` 相当の cleanup 規則を追加する。`imwrite` 失敗、replace 失敗、最終ファイル検証失敗の各ケースで temp path を削除し、削除失敗は `ResourceWriteError.details["cleanup_error"]` へ残す、と定義する。

#### RC-009: macro entrypoint load 失敗時の診断粒度が不足している

- **対象**: `MACRO_COMPATIBILITY_AND_REGISTRY.md:421-441`
- **問題**: entrypoint 解決失敗は `MacroLoadError` に集約されるが、manifest parse、module import、class not found、複数候補、`MacroBase` 未継承、circular import、`sys.path` 復元失敗を区別する診断形式がない。
- **影響**: GUI/CLI のマクロ一覧でロード不能マクロを表示する際、ユーザーが manifest を直すべきか import を直すべきか判断できない。
- **修正案**: `MacroRegistry.diagnostics` の要素型を明示する。例: `macro_id`, `entrypoint`, `error_type`, `message`, `source_path`, `traceback_path | None` を持つ `MacroLoadDiagnostic` を定義し、GUI/CLI は `error_type` に応じて短い表示文言を出す。

#### RC-010: クラス名衝突時の GUI/CLI 表示仕様が不足している

- **対象**: `MACRO_COMPATIBILITY_AND_REGISTRY.md:157-166`
- **問題**: `class_name` 衝突時に `AmbiguousMacroError` を送出し候補 ID を含める方針はあるが、GUI の一覧表示や CLI の `list` 表示で、衝突候補をどの ID で選ばせるかが定義されていない。
- **影響**: 例外メッセージでは候補 ID が分かっても、通常の一覧画面で同じ表示名が並び、ユーザーが正しいマクロを選択できない。
- **修正案**: 一覧表示では `display_name [ID: macro_id]` を基本形にし、衝突時は `class_name` ではなく `MacroDefinition.id` を選択キーとして表示する、と明記する。CLI のエラーメッセージ例も追加する。

#### RC-011: `Command.wait()` の cancel-aware wait 実装条件が抽象的である

- **対象**: `RUNTIME_AND_IO_PORTS.md:200-210`, `RUNTIME_AND_IO_PORTS.md:580-588`, `ERROR_CANCELLATION_LOGGING.md:55-63`
- **問題**: `Command.wait()` / `DefaultCommand.press()` 中の待機は 100 ms 未満で cancellation safe point に到達する必要があるが、実装方法として `threading.Event.wait()` を使うのか、poll interval を何 ms 以下にするのかが定義されていない。
- **影響**: `time.sleep(wait)` をそのまま使う実装でも仕様を読んだだけでは誤りと判断しにくい。性能テストが失敗してから実装を直すことになる。
- **修正案**: `cancellation_aware_wait(duration, token, poll_interval=0.05)` の擬似コードを追加し、長い `dur` / `wait` は 50 ms 以下の単位で中断確認する、と明記する。

#### RC-012: 100 ms のキャンセル測定範囲が文書ごとに異なる

- **対象**: `ERROR_CANCELLATION_LOGGING.md:55-63`, `OBSERVABILITY_AND_GUI_CLI.md:121-128`, `TEST_STRATEGY.md:175-180`
- **問題**: `ERROR_CANCELLATION_LOGGING.md` は `CancellationToken` 発火から `MacroCancelled` 送出まで、`OBSERVABILITY_AND_GUI_CLI.md` は GUI cancel ボタンから中断要求発火まで、`TEST_STRATEGY.md` は `RunHandle.cancel()` から `RunResult.cancelled` までを 100 ms 系の指標として扱っている。
- **影響**: 同じ「100 ms」が異なる区間を指すため、実装側とテスト側の期待値がずれる。特に safe point 外の処理を含むかどうかで結果が変わる。
- **修正案**: 3 区間を別指標として命名する。例: `cancel_request_latency`、`safe_point_latency`、`cancel_result_latency`。`TEST_STRATEGY.md` の性能表にも同じ名称を使う。

#### RC-013: `MacroExecutor` 削除確認テストの期待内容が不足している

- **対象**: `TEST_STRATEGY.md:97-103`, `DEPRECATION_AND_MIGRATION.md:159-167`, `DEPRECATION_AND_MIGRATION.md:233-240`
- **問題**: `test_macro_executor_removed` と `test_gui_cli_do_not_import_macro_executor` が挙がっているが、何をもって削除確認とするかが書かれていない。import path が存在しないことを確認するのか、GUI/CLI の import trace に含まれないことを確認するのかが曖昧である。
- **影響**: 互換 shim を残したままでもテストが通る、または import 失敗をテスト失敗として扱うなど、削除方針とテスト実装が食い違う。
- **修正案**: `test_macro_executor_removed` は `nyxpy.framework.core.macro.executor` の import が `ModuleNotFoundError` になること、`test_gui_cli_do_not_import_macro_executor` は GUI/CLI entrypoint の import graph に `MacroExecutor` が含まれないこと、と期待結果を明記する。

#### RC-014: signature 互換テストで戻り値注釈をどこまで固定するかが曖昧である

- **対象**: `TEST_STRATEGY.md:263-268`
- **問題**: `Command` の戻り値注釈は「厳密固定しすぎず、呼び出し互換を優先」とあるが、戻り値が `None` から `ResourceRef` や `int` に変わる変更を許容するのかが分からない。
- **影響**: 既存マクロが戻り値を使っていなくても、公開 API としての型契約が揺れる。型チェックやドキュメント生成でも差分検知ができない。
- **修正案**: 互換対象 API については戻り値注釈も固定する。ただし内部抽象や新 API は固定対象外、と分ける。既存 `Command` メソッドは `inspect.signature()` に加えて `return_annotation` を検証する方針へ修正する。

#### RC-015: ログ sink lock timeout 時の stderr 出力に秘密値マスク規則がない

- **対象**: `LOGGING_FRAMEWORK.md:307-315`
- **問題**: `sink_lock` timeout 時は fallback stderr へ出すとあるが、stderr へ出す内容が `LogSanitizer` を通るか、secret / path / payload をどこまで削るかが未定義である。
- **影響**: ログ基盤の障害時こそ通常の sink 経路を通れないため、未マスクの例外メッセージや通知 URL が標準エラーへ出る可能性がある。
- **修正案**: fallback stderr は固定文言、event code、mask 済み component、例外型だけに限定する。元例外 message を出す場合も `LogSanitizer.mask_text()` 相当を通す、と明記する。

### 2.3 軽微

#### RC-016: `IMPLEMENTATION_PLAN.md` のフェーズ番号 `6A` は機械処理しにくい

- **対象**: `IMPLEMENTATION_PLAN.md:128-144`
- **問題**: 依存順序表で `6A` が使われている。人間には読めるが、進捗表や CI ラベル、issue 分割で数値順に並べる場合に扱いづらい。
- **影響**: 実装順序の自動集計やチェックリスト化で `6A` が `6` と `7` の間に並ばない可能性がある。
- **修正案**: `6.1` または独立した `7` に採番し直し、後続フェーズ番号を更新する。採番を変えない場合は「順序キー」と「表示名」を別列にする。

#### RC-017: 代表マクロの定義が複数文書で暗黙的である

- **対象**: `DEPRECATION_AND_MIGRATION.md:159-167`, `MACRO_MIGRATION_GUIDE.md:300-314`, `TEST_STRATEGY.md:269-279`
- **問題**: `test_migrated_repository_macros_load_with_optional_manifest` や `test_migrated_frlg_id_rng_save_img_outputs` など代表マクロ前提のテスト名があるが、どのマクロを代表として採用するか、採用理由、移行完了条件の一覧がない。
- **影響**: テスト作成時に対象マクロが担当者判断になり、移行漏れや過剰なマクロ修正が起きやすい。
- **修正案**: `MACRO_MIGRATION_GUIDE.md` に「移行対象代表マクロ」表を追加する。列は `macro_id`、採用理由、必要な移行項目、必須テスト、対象外理由を推奨する。

#### RC-018: Mermaid 図の HTML escape とリンク追跡性を確認したい

- **対象**: `ARCHITECTURE_DIAGRAMS.md:101-118`
- **問題**: Mermaid 図内に `&lt;name&gt;` など HTML escape がある。GitHub Markdown 上で意図通り表示されるか、図から詳細仕様へ戻るリンクが十分かは文書だけでは確認しづらい。
- **影響**: レビュー時に図と正本仕様の対応が追いにくい。描画崩れがあるとアーキテクチャ理解の入口が弱くなる。
- **修正案**: 図ごとに参照先の正本仕様リンクを追加する。可能であれば Mermaid の描画確認を CI または手動チェックリストに含める。

## 3. 実装前に決めるべき横断事項

| 論点 | 決める内容 | 推奨する正本 |
|------|------------|--------------|
| secrets の lifetime | builder 固定か request 単位か | `RUNTIME_AND_IO_PORTS.md` |
| GUI/CLI composition root | core builder が受け取るものと adapter 側で生成するもの | `OBSERVABILITY_AND_GUI_CLI.md` |
| Resource Port API | `ResourceStorePort` / `RunArtifactStore` の唯一のシグネチャ | `RESOURCE_FILE_IO.md` |
| cancel latency | 100 ms 指標の測定開始点と終了点 | `TEST_STRATEGY.md` |
| logging fallback | logger 初期化失敗と sink timeout の失敗扱い | `LOGGING_FRAMEWORK.md` |

