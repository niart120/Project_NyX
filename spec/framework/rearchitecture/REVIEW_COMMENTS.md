# フレームワーク再設計ドキュメント レビューコメント

> **対象**: `spec\framework\rearchitecture\*.md`  
> **観点**: `framework-spec-writing` の必須構成、公開 API の一貫性、依存方向、後方互換性、スレッド安全性、テストゲート、移行可能性

## 1. 総評

再設計ドキュメント群は、Runtime / Port / Registry / Resource I/O / Logging / GUI・CLI adapter の責務分割を一通り網羅している。特に、既存マクロが import する `MacroBase` / `Command` / constants を維持する方針、framework core から GUI・CLI へ静的依存しない方針、実機テストを `@pytest.mark.realdevice` で分離する方針は複数文書で一貫している。

一方で、複数文書にまたがる型定義と移行ゲートに不整合がある。実装前に正本ドキュメントを決めないと、同じ概念を別型で実装したり、未決の挙動を別文書で確定済みとして扱ったりするリスクが高い。

## 2. Critical

### C-01 概要の未決事項と詳細仕様の確定記述が衝突している

- **対象**: `FW_REARCHITECTURE_OVERVIEW.md:278-285`, `ERROR_CANCELLATION_LOGGING.md:376-384`, `DEPRECATION_AND_MIGRATION.md:165`
- **問題**: Overview では `DefaultCommand.stop()` の例外送出、`MacroDefinition` の class 参照保持、singleton の runtime 登録が未決である。一方で、詳細仕様では `Command.stop(raise_immediately=False)` を既定にし、即時例外送出を廃止候補として扱っている。
- **影響**: 実装者が Overview と詳細仕様のどちらを正とするか判断できない。キャンセル互換の挙動は既存マクロの破壊範囲に直結する。
- **修正案**: `FW_REARCHITECTURE_OVERVIEW.md` の未決事項を「確定済み」「実装前ゲート」「設計保留」に分ける。`DefaultCommand.stop()` は詳細仕様どおりに確定するか、詳細仕様側を未決扱いへ戻す。

### C-02 テストゲートと削除タイミングの対応表が不足している

- **対象**: `TEST_STRATEGY.md:81-91`, `DEPRECATION_AND_MIGRATION.md:158-183`, `IMPLEMENTATION_PLAN.md:139-156`
- **問題**: テスト戦略は段階的なテスト層を定義し、廃止方針は削除条件を定義しているが、「どのテストゲートを通過したら、どの廃止候補を削除できるか」の対応がない。
- **影響**: `MacroExecutor`、legacy static fallback、`DefaultCommand` 旧コンストラクタなどを削除するタイミングを実装者が判断できない。
- **修正案**: `IMPLEMENTATION_PLAN.md` に「フェーズ × テストゲート × 削除可能な廃止候補」の対応表を追加する。削除可否は `import gate`、`existing macro gate`、`migrated macro gate`、GUI/CLI integration、hardware smoke のどれを通過条件にするか明記する。

## 3. High

### H-01 GUI adapter の `RunHandle.wait()` 呼び出しが UI ブロックに見える

- **対象**: `FW_REARCHITECTURE_OVERVIEW.md:262-264`, `FW_REARCHITECTURE_OVERVIEW.md:568-583`
- **問題**: 3.7 では「GUI は `RunHandle` を直接 UI スレッドから待たない」とあるが、4.2.4 の図では `GUI Adapter -> handle.wait(timeout)` と書かれている。
- **影響**: GUI adapter が UI スレッドで `wait()` してよいように読める。Qt のイベントループ停止や cancel 応答遅延につながる。
- **修正案**: 4.2.4 に「`handle.wait()` は worker thread 内で呼ぶ。UI スレッドでは `done()` の非同期通知または Qt Signal に変換する」と追記する。

### H-02 Runtime の設定表に複数の設定所有者が混在している

- **対象**: `RUNTIME_AND_IO_PORTS.md:674-690`, `DEPRECATION_AND_MIGRATION.md:185-192`, `CONFIGURATION_AND_RESOURCES.md:259-261`
- **問題**: `runtime.*`、`serial_*`、`capture_device`、`resource.*`、`notification.*` が同じ設定表に並んでいるが、`RuntimeOptions` / `GlobalSettings` / `SecretsSettings` / Resource I/O のどれが所有する値か明示されていない。
- **影響**: `notification.*` を Runtime 設定として実装する、または `resource.*` を settings 仕様と Resource I/O 仕様の両方で持つなど、設定保存先の分裂が起きる。
- **修正案**: 設定表に「所有者」列を追加する。例: `runtime.allow_dummy` は `RuntimeOptions`、`notification.discord.enabled` は `SecretsSettings snapshot`、`resource.assets_root` は `Resource I/O builder input` と明記する。

### H-03 `reset_for_testing()` の初期化対象が文書間で曖昧である

- **対象**: `RUNTIME_AND_IO_PORTS.md:712-716`, `CONFIGURATION_AND_RESOURCES.md:259-261`, `DEPRECATION_AND_MIGRATION.md:205-209`
- **問題**: 既存 singleton を維持しつつ Runtime / Port 関連状態も初期化すると書かれているが、具体的な初期化対象が列挙されていない。
- **影響**: テスト間で device discovery cache、GUI sink、Runtime handle、settings snapshot が残る可能性がある。
- **修正案**: `reset_for_testing()` の対象一覧を 1 か所に集約する。最低限、`serial_manager`、`capture_manager`、`global_settings`、`secrets_settings`、device discovery cache、LogManager sink、Runtime/Port の一時状態を「初期化する / しない」に分類する。

### H-04 代表マクロ名を実装ゲートへ直接埋め込んでいる

- **対象**: `IMPLEMENTATION_PLAN.md:155`, `IMPLEMENTATION_PLAN.md:284`
- **問題**: `frlg_id_rng`、`frlg_initial_seed`、`frlg_gorgeous_resort`、`frlg_wild_rng` などの具体名が gate 条件やテスト名に直接埋め込まれている。
- **影響**: マクロ名変更や移行順変更で実装計画が陳腐化する。移行前のマクロを gate 条件にすると、実装初期段階で gate を満たせない。
- **修正案**: 実装計画では「代表マクロ fixture」「移行済み代表マクロ」の条件を抽象化し、具体名は `MACRO_MIGRATION_GUIDE.md` の対象マクロ一覧に寄せる。

### H-05 通知 secret の移行経路が不足している

- **対象**: `OBSERVABILITY_AND_GUI_CLI.md:181-183`, `RUNTIME_AND_IO_PORTS.md:727-728`, `CONFIGURATION_AND_RESOURCES.md:249-257`
- **問題**: 通知 secret は `SecretsSettings` だけから読む方針だが、既存 GUI/CLI の入力、CLI 引数、既存 settings ファイルから `SecretsSettings snapshot` へ変換する責務が明確でない。
- **影響**: secret が `GlobalSettings`、ログ context、CLI args の平文保持に残る可能性がある。
- **修正案**: `OBSERVABILITY_AND_GUI_CLI.md` に secret 入力のデータフローを追加する。例: `CLI args -> RuntimeBuildRequest -> SecretsSettings snapshot -> NotificationPort`。GUI の secret 入力・保存・マスク責務も同じ表で固定する。

### H-06 `MacroStopException` の互換 constructor が未定義である

- **対象**: `ERROR_CANCELLATION_LOGGING.md:190-193`, `ERROR_CANCELLATION_LOGGING.md:340-342`
- **問題**: `MacroStopException.__init__(*args, **kwargs)` は旧呼び出しを受ける形だが、`args[0]`、`kind`、`code`、`component`、`recoverable` の既定値が定義されていない。
- **影響**: 既存マクロが `raise MacroStopException("message")` した場合の `ErrorInfo` が実装者ごとに変わる。
- **修正案**: 旧形式の解釈を明記する。例: `args[0]` を message、`kind=ErrorKind.CANCELLED`、`code="NYX_MACRO_CANCELLED"`、`component="MacroStopException"`、`recoverable=False` とする。

### H-07 GUI/CLI adapter の責務分割をテスト単位へ落とし込めていない

- **対象**: `OBSERVABILITY_AND_GUI_CLI.md:106-115`, `OBSERVABILITY_AND_GUI_CLI.md:185-202`, `TEST_STRATEGY.md:287-289`
- **問題**: GUI adapter、CLI adapter、Runtime、Logger の禁止事項はあるが、テスト単位でどこまでを adapter と見なすかが曖昧である。`GuiLogSink` の Qt Signal emit と LogPane 表示更新の境界がテスト名から読み取れない。
- **影響**: core 層のテストに Qt 依存が混入する、または GUI 表示テストが adapter 単体テストに寄りすぎる。
- **修正案**: `TEST_STRATEGY.md` に「GUI テスト粒度」を追加する。`GuiLogSink` unit test、pytest-qt による queued connection test、LogPane 表示更新 test を分ける。

## 4. Medium

### M-01 `cleanup_warnings` の文字列形式が後続処理に弱い

- **対象**: `RUNTIME_AND_IO_PORTS.md:618`, `RUNTIME_AND_IO_PORTS.md:325-326`
- **問題**: Port close 失敗を `"<port_name>: <ExceptionType>: <message>"` の文字列で保持する設計である。
- **影響**: message に `:` が含まれると機械的な解析が難しい。GUI/CLI 表示やログ構造化の際に再パースが必要になる。
- **修正案**: `CleanupWarning` dataclass、または `tuple[Mapping[str, str], ...]` として `port`、`exception_type`、`message` を分離して保持する。表示層で文字列化する。

### M-02 `finalize` signature inspection のキャッシュ方針がない

- **対象**: `ERROR_CANCELLATION_LOGGING.md:386-390`
- **問題**: `SupportsFinalizeOutcome` または signature inspection による opt-in 拡張が定義されているが、inspection 結果をどこで保持するかがない。
- **影響**: 実行ごとに `inspect.signature()` を呼ぶ実装になりやすく、マクロ数や短時間実行が多い場合に余計な負荷が出る。
- **修正案**: `MacroDefinition` または `MacroFactory` が `finalize_accepts_outcome: bool` を保持し、Registry reload 時に 1 回だけ判定する。

### M-03 Resource I/O の複数 assets root と出力先の関係を明示するとよい

- **対象**: `RESOURCE_FILE_IO.md:103-107`, `RESOURCE_FILE_IO.md:157`, `RESOURCE_FILE_IO.md:191-201`
- **問題**: `MacroResourceScope.assets_roots` は複数 root を許可し、`RunArtifactStore` は単一 output root を持つ。読み込みと保存の分離は書かれているが、「assets を上書き保存しない」制約が `Command.save_img()` の観点で目立ちにくい。
- **影響**: 既存マクロ移行時に、読み込んだ assets root へ同名ファイルを書き戻す設計だと誤解される。
- **修正案**: `save_img()` / `open_output()` は常に `RunArtifactStore` 配下へ保存し、assets root へは書き込まないことを公開 API 方針か互換性セクションへ再掲する。

### M-04 `project:` path の区切り文字ルールが不足している

- **対象**: `MACRO_COMPATIBILITY_AND_REGISTRY.md:126-132`, `CONFIGURATION_AND_RESOURCES.md:272-278`
- **問題**: `project:` prefix の相対 path を扱うが、TOML 内で Windows の `\` と portable な `/` のどちらを許可するかが明記されていない。
- **影響**: Windows では `project:resources\foo`、他環境では `project:resources/foo` のように表記が分裂する。
- **修正案**: TOML 内の path は `/` のみ許可する、または parser が `\` を拒否して診断を出す、と明記する。Windows 実ファイルパスへの変換は実装側で行う。

### M-05 移行ガイドの before / after 例が不足している

- **対象**: `MACRO_MIGRATION_GUIDE.md:101-159`, `MACRO_MIGRATION_GUIDE.md:269`
- **問題**: manifest 追加や legacy static fallback 廃止の方針はあるが、settings、assets、outputs、`DefaultCommand` 直接生成テストの移行例が不足している。
- **影響**: マクロ作者やテスト修正担当者が、どのコードをどう置き換えるべきか判断しにくい。
- **修正案**: `settings.toml` の移動、`cmd.load_img()` / `cmd.save_img()` の path 変更、`RunArtifactStore.open_output()` の利用、`DefaultCommand(context=...)` へのテスト移行について before / after を追加する。

### M-06 実装チェックリストと仕様確定チェックリストが混在している

- **対象**: `RUNTIME_AND_IO_PORTS.md:762-788`, `MACRO_COMPATIBILITY_AND_REGISTRY.md:494-508`, `LOGGING_FRAMEWORK.md:430-450`
- **問題**: チェックリストに「シグネチャ確定」と「GUI/CLI 移行」「テスト作成・パス」が同じ粒度で並んでいる。
- **影響**: 仕様レビュー完了条件と実装完了条件を混同しやすい。
- **修正案**: 各仕様書では「仕様確定チェックリスト」に限定し、実装タスクは `IMPLEMENTATION_PLAN.md` へ寄せる。どうしても残す場合は「仕様確定」「実装」「検証」の小見出しで分ける。

## 5. Low

### L-01 文書検証コマンドの目的を補足するとよい

- **対象**: `DEPRECATION_AND_MIGRATION.md:246-250`, `IMPLEMENTATION_PLAN.md:417-421`
- **問題**: `git diff --check` や placeholder 検出コマンドがあるが、何を品質ゲートとして見るかの説明が薄い。
- **修正案**: 各コマンドの直後に「行末空白検出」「未解決 placeholder 検出」「必須セクション確認」などの検証目的を追記する。

## 6. 対応順の提案

1. `DefaultCommand.stop()`、singleton、`MacroDefinition` class 参照保持の未決事項を確定し、Overview と詳細仕様を同期する。
2. テストゲートと廃止候補の対応表を追加し、削除タイミングを実装計画に固定する。
3. GUI/CLI adapter、secret 入力、settings 所有者、Resource I/O の責務境界を表で補強する。
4. 移行ガイドに before / after 例を追加し、既存マクロ・既存テストの移行作業を実行可能な粒度にする。
