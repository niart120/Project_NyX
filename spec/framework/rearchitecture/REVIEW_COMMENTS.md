# フレームワーク再設計ドキュメント レビューコメント

> **対象**: `spec\framework\rearchitecture\*.md`
> **レビュー日**: 2026-05-07
> **レビュー方針**: 再設計仕様群を、仕様書テンプレート準拠、文書間整合性、後方互換性、依存方向、テスト可能性、実装時リスクの観点で確認した。
> **状態**: 問題欄はレビュー時点の内容を保持し、修正提案は採用方針に合わせて更新済みである。

## 1. サマリ

Critical は確認されなかった。各文書は 6 セクション構成、用語定義、対象ファイル、実装仕様、テスト方針、チェックリストを持っており、仕様書としての骨格は揃っている。

実装前に解消すべき Major 指摘は、例外仕様、settings path 型、macro root 決定、通知失敗の責務境界、テスト名の正本化、`Command.stop()` の互換影響である。これらは実装者が異なる解釈でコードを書いた場合に、テスト不一致、移行漏れ、エラー表示の不整合を起こす可能性が高い。

| 重大度 | 件数 |
|--------|------|
| Critical | 0 |
| Major | 7 |
| Minor | 3 |
| Suggestion | 2 |

## 2. Major

### RC-001: `DefaultCommand` 旧コンストラクタ拒否時の例外が文書間で不一致

**対象**

- `RUNTIME_AND_IO_PORTS.md:591`
- `TEST_STRATEGY.md:346`
- `RUNTIME_AND_IO_PORTS.md:696`

**問題**

`RUNTIME_AND_IO_PORTS.md` は、`DefaultCommand` が旧形式の具象引数を受け取った場合に `TypeError` とすると定義している。一方、`TEST_STRATEGY.md` の `test_default_command_rejects_legacy_constructor_args` は `RuntimeConfigurationError` になることを期待している。`RuntimeConfigurationError` 自体は Runtime builder の設定不足や protocol / baudrate 不正として定義されており、コンストラクタ引数のシグネチャ拒否と責務がずれている。

**影響**

実装者が `TypeError` を選ぶか `RuntimeConfigurationError` を選ぶかでテストが割れる。移行ガイド上も、直接生成コードの修正対象を「Python のシグネチャ違反」として扱うのか、「Runtime 設定エラー」として扱うのかが不明確になる。

**修正提案**

例外を 1 つに統一する。推奨は `TypeError` である。理由は、旧具象引数は新 API の構成エラーではなく、`DefaultCommand.__init__(context: ExecutionContext)` のシグネチャ違反だからである。`TEST_STRATEGY.md` の期待値を `TypeError` に合わせ、`RuntimeConfigurationError` は builder の入力検証に限定する。

### RC-002: `MacroDefinition.settings_path` の型が portable path 仕様と矛盾している

**対象**

- `MACRO_COMPATIBILITY_AND_REGISTRY.md:132`
- `MACRO_COMPATIBILITY_AND_REGISTRY.md:267-279`
- `CONFIGURATION_AND_RESOURCES.md:175-184`
- `MACRO_MIGRATION_GUIDE.md:172-184`

**問題**

manifest と class metadata に永続化する settings path は、`project:resources/frlg_id_rng/settings.toml` のような portable path 文字列であり、Windows 環境でも `/` のみを使い、`\` は入力エラーとする仕様である。一方、`MacroDefinition.settings_path` は `Path | None` と定義されている。

`Path` 化した時点で、入力が `project:` prefix 付きだったのか、manifest 相対だったのか、class metadata 相対だったのかを失いやすい。特に `project:` は OS の実ファイルパスではなく、resolver が解釈すべき論理 prefix である。

**影響**

`MacroSettingsResolver` が「未解決の設定指定」と「解決済み実ファイルパス」を同じ型で扱うことになる。入力診断、エラーメッセージ、移行ガイドの例、テスト fixture がずれやすい。

**修正提案**

追加フィールドを増やさず、`MacroDefinition.settings_path` を `Path | str | None` にする。`Path` は解決済み path、`str` は `project:` prefix または portable relative path を含む未解決指定として扱い、実ファイル path 化は `MacroSettingsResolver` だけが行う。解決後の path は `MacroSettingsSource.path` に保持する。

### RC-003: class metadata の相対 settings path に対する `macro root` 決定方法が不足している

**対象**

- `MACRO_COMPATIBILITY_AND_REGISTRY.md:128-129`
- `MACRO_COMPATIBILITY_AND_REGISTRY.md:267-279`
- `CONFIGURATION_AND_RESOURCES.md:228-234`
- `MACRO_MIGRATION_GUIDE.md:186`

**問題**

class metadata `settings_path` に通常の相対パスを指定した場合は macro root 相対とすると定義されている。しかし `MacroDefinition` の公開フィールドには `macro_root` がなく、`source_path` と `manifest_path` だけがある。package macro、single-file macro、manifest あり、manifest なし convention discovery のそれぞれで macro root をどこにするかが明文化されていない。

**影響**

`settings_path = "settings.toml"` のような指定を実装したとき、`source_path.parent`、package directory、manifest directory、`macros_dir` 直下のどれを起点にするかが実装者依存になる。代表マクロの移行時に、GUI/CLI とテストで別の settings を読むリスクがある。

**修正提案**

`MacroDefinition` に `macro_root: Path` を追加し、生成規則を表で定義する。例: manifest ありは `manifest_path.parent`、package convention は package directory、single-file convention は file parent。`MacroSettingsResolver` は相対指定を `definition.macro_root` だけから解決する。

### RC-004: `NotificationPort` の失敗処理が「例外送出」と「警告ログのみ」のどちらか不明確

**対象**

- `RUNTIME_AND_IO_PORTS.md:220`
- `RUNTIME_AND_IO_PORTS.md:619-621`
- `ERROR_CANCELLATION_LOGGING.md:340`
- `TEST_STRATEGY.md:286`

**問題**

`RUNTIME_AND_IO_PORTS.md` は `NotificationPort` が通知先ごとの例外を握りつぶさず `LoggerPort` に警告として記録すると述べる。一方、同じ文書の `NotificationPort` 詳細では、個別 notifier の失敗は `WARNING` で記録し、マクロ本体の `RunResult` は変更しないとする。`ERROR_CANCELLATION_LOGGING.md` には `NYX_NOTIFICATION_FAILED` が error code として定義されている。

このため、`NotificationPort.publish()` が例外を送出するのか、送出せず警告ログだけを残すのか、送出する場合に誰が `RunResult` へ反映しないよう握るのかが曖昧である。

**影響**

通知失敗時の GUI/CLI 表示、`RunResult.error`、構造化ログ、テスト fake の期待動作が一致しない。通知先の障害でマクロ成功が失敗扱いになる実装と、完全にログだけで終わる実装が混在し得る。

**修正提案**

責務を明文化する。`NotificationPort.publish()` は個別 notifier 失敗を捕捉し、`NYX_NOTIFICATION_FAILED` を持つ `TechnicalLog` / warning `UserEvent` を発行し、例外は再送出しない。`RunResult.status` は変更しない。例外再送出用の明示オプションは定義しない。

### RC-005: 実装計画とテスト戦略でテスト名が一致していない

**対象**

- `IMPLEMENTATION_PLAN.md:315`
- `IMPLEMENTATION_PLAN.md:341`
- `IMPLEMENTATION_PLAN.md:354`
- `TEST_STRATEGY.md:355-356`
- `TEST_STRATEGY.md:364`

**問題**

`IMPLEMENTATION_PLAN.md` は CLI のテストとして `test_cli_uses_macro_runtime_builder`、`test_cli_uses_run_result_exit_code` などを列挙している。一方、`TEST_STRATEGY.md` では `test_cli_uses_runtime_and_run_result` が正のように見える。GUI でも `test_main_window_starts_runtime_and_updates_status` と `test_gui_start_uses_runtime_handle` が並存している。logging でも `test_logging_sink_dispatch_perf` と `test_log_handler_dispatch_thread_safety` が別名で記載されている。

**影響**

実装者がどのテストを追加すべきか判断しにくい。チェックリストを `[x]` にしても、テスト戦略側の名前と一致しないため、進捗確認や grep による完了確認が機能しない。

**修正提案**

`TEST_STRATEGY.md` をテスト名の正本にするか、`IMPLEMENTATION_PLAN.md` の各フェーズ表を正本にするかを決める。推奨は `TEST_STRATEGY.md` に「正本テスト ID / 実ファイル / フェーズ / 仕様参照」の表を作り、`IMPLEMENTATION_PLAN.md` はその ID を参照する方式である。

### RC-006: `Command.stop()` の互換影響が互換ポリシー表だけでは読み違えやすい

**対象**

- `FW_REARCHITECTURE_OVERVIEW.md:213-218`
- `FW_REARCHITECTURE_OVERVIEW.md:233`
- `ERROR_CANCELLATION_LOGGING.md:349-364`
- `DEPRECATION_AND_MIGRATION.md:165`
- 現行実装 `src\nyxpy\framework\core\macro\command.py:255-258`

**問題**

互換ポリシー表では `Command` 公開メソッドを永久維持に含めているが、`Command.stop()` は即時 `MacroStopException` 送出から、キャンセル要求登録だけを行う協調キャンセルへ意味論が変わる。`DEPRECATION_AND_MIGRATION.md` ではこの変更を削除対象として明記しているため、方針自体は存在するが、overview の互換表だけを読むと「メソッド名だけ維持し、即時例外送出は維持しない」という境界が見えにくい。

**影響**

既存マクロが `cmd.stop()` の直後に例外で脱出する前提で書かれている場合、協調キャンセル化後に後続処理が走る。移行対象マクロの洗い出しが漏れると、実行結果や cleanup 順序が変わる。

**修正提案**

`FW_REARCHITECTURE_OVERVIEW.md` の互換ポリシー表に「`Command.stop()` はメソッド名と呼び出し可能性のみ維持。即時例外送出は維持しない」と明記する。`MACRO_MIGRATION_GUIDE.md` には `cmd.stop(); return` または `raise MacroStopException` 相当から新 safe point へ移す具体例を追加する。

### RC-007: Runtime 系例外の正本が `ERROR_CANCELLATION_LOGGING.md` と分散している

**対象**

- `RUNTIME_AND_IO_PORTS.md:692-706`
- `ERROR_CANCELLATION_LOGGING.md:320-342`
- `TEST_STRATEGY.md:314-315`

**問題**

`RuntimeBusyError`、`RuntimeLockTimeoutError`、`FrameNotReadyError`、`FrameReadError` などは `RUNTIME_AND_IO_PORTS.md` のエラーハンドリング表で定義されている。一方、エラー階層と error code catalog の正本は `ERROR_CANCELLATION_LOGGING.md` に見えるが、同文書にはこれらの例外クラス名が掲載されていない。

**影響**

実装時に、Runtime 系例外が `FrameworkError` 階層に属するのか、どの `ErrorKind` と `code` を持つのか、GUI/CLI の終了コードや表示分類にどう変換されるのかが分散する。テストで例外クラスを直接期待するケースと、`RunResult.error.code` を期待するケースがずれやすい。

**修正提案**

例外クラス階層の正本を 1 か所に寄せる。推奨は `ERROR_CANCELLATION_LOGGING.md` に Runtime 系例外を追加し、`RUNTIME_AND_IO_PORTS.md` は発生条件だけを書く方式である。少なくとも各 Runtime 例外に `ErrorKind`、error code、`FrameworkError` 継承有無を表で明記する。

## 3. Minor

### RC-008: `ErrorInfo.traceback` と `logging.include_traceback` の接続規則が不足している

**対象**

- `ERROR_CANCELLATION_LOGGING.md:303-314`
- `LOGGING_FRAMEWORK.md:217-221`
- `LOGGING_FRAMEWORK.md:390-405`

**問題**

`ErrorInfo.traceback` は DEBUG ログ用で GUI 表示には出さないと定義されている。`LOGGING_FRAMEWORK.md` には `TechnicalLog.include_traceback` と `logging.include_traceback` がある。しかし、`ErrorInfo` から `TechnicalLog` へ変換する時点で、設定値をどこで参照し、`ErrorInfo.traceback` を保持するのか削るのかが明確でない。

**影響**

GUI には出さないという方針は明確だが、構造化ログへ保存するかどうかが実装者依存になる。失敗調査に必要な traceback が欠落する、または設定で無効化したのに JSONL に残る可能性がある。

**修正提案**

`MacroRunner` は `ErrorInfo.traceback` を生成するが、`LoggerPort` / `LogBackend` が `logging.include_traceback` を見て永続化有無を決める、など責務を 1 つに固定する。

### RC-009: `RuntimeOptions.wait_poll_interval_sec` の利用箇所が曖昧

**対象**

- `RUNTIME_AND_IO_PORTS.md:271-278`
- `ERROR_CANCELLATION_LOGGING.md:349-354`
- `TEST_STRATEGY.md:176`

**問題**

`RuntimeOptions` に `wait_poll_interval_sec = 0.05` があるが、`Command.wait(seconds)` の仕様は `ct.wait(seconds)` を呼ぶとだけ記述している。`CancellationToken.wait()` が `threading.Event.wait()` 相当なら poll interval は不要であり、polling loop を想定しているなら実装手順が不足している。

**影響**

100 ms 未満の cancel latency をどの設定で担保するのかが分かりにくい。テストは `wait_poll_interval_sec` を検証するのか、`Event.wait()` の即時復帰を検証するのかで期待が変わる。

**修正提案**

`wait_poll_interval_sec` を削除する。`CancellationToken.wait(seconds)` は `threading.Event.wait()` 相当として中断要求で即時復帰するため、polling interval は持たせない。

### RC-010: Resource path guard の Windows 固有ケースが不足している

**対象**

- `RESOURCE_FILE_IO.md:268-282`
- `CONFIGURATION_AND_RESOURCES.md:236`

**問題**

`resolve_under_root()` の手順は、空 path、絶対 path、`..`、root 外 symlink を拒否する方針を示している。一方で、Windows の drive-relative path、UNC path、予約名、区切り文字混在、`Path` と `str` の扱い差をどの順で正規化するかは未定義である。

**影響**

実装者が `Path(name)` に任せるだけにすると、OS 依存の解釈差が path guard に入り込む。settings path では `\` を入力エラーとする方針があるが、Resource File I/O では resource name と OS path の境界が明確でない。

**修正提案**

Resource File I/O の実行時 path 引数は Windows path を許容する。drive、UNC、予約名、区切り文字正規化の疑似コードとテストケースを追加し、root 外参照は path guard で拒否する。

## 4. Suggestion

### RC-011: 実装計画の用語定義に `DefaultCommand` が重複している

**対象**

- `IMPLEMENTATION_PLAN.md:22`
- `IMPLEMENTATION_PLAN.md:32`

**問題**

`DefaultCommand` が用語定義表に 2 回登場している。内容は大きく矛盾していないが、片方は import path と生成方式、もう片方は Ports 委譲実装に触れている。

**修正提案**

1 行に統合し、「既存 import path を維持する `Command` 実装。生成は `DefaultCommand(context=...)` に統一し、`ExecutionContext` 経由で Ports へ委譲する」とする。

### RC-012: ファイルパス表記の規約を文書群内で統一するとよい

**対象**

- `IMPLEMENTATION_PLAN.md:71-88`
- `MACRO_COMPATIBILITY_AND_REGISTRY.md:132`
- `MACRO_MIGRATION_GUIDE.md:160-186`

**問題**

同じ文書群の中で、Markdown 参照は `/`、Windows 表記例は `\`、portable settings path は `/` という複数の表記が混在している。意図的な使い分けはあるが、どの文脈でどの表記を使うかを明示する規約がない。

**修正提案**

overview または migration guide に短い規約を追加する。例: 「文書リンクと portable manifest/settings path は `/`、Windows 実ファイルパス例は `\`、Python コード内の path join は `Path` を使う」。これにより `project:resources/...` と `resources\...` の意味差が読み取りやすくなる。

## 5. 優先対応順

1. RC-001、RC-005、RC-007 を先に直し、テスト実装時の期待値を固定する。
2. RC-002、RC-003、RC-010 を直し、settings / resource path 解決の型と境界を固定する。
3. RC-004、RC-008、RC-009 を直し、実行結果、ログ、キャンセルの実装責務を固定する。
4. RC-006、RC-011、RC-012 を直し、移行ガイドと読みやすさを改善する。
