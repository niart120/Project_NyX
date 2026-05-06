# フレームワーク再設計ドキュメント レビューコメント

> **対象**: `spec\framework\rearchitecture\*.md`  
> **観点**: フレームワーク仕様書テンプレート、依存方向、後方互換性、実装可能性、テスト可能性、文書間整合性

## 1. 総評

再設計の分割方針、互換ゲート、Ports/Adapters 化、GUI/CLI 移行の方向性は具体化されている。一方で、複数文書が同じ型・責務・イベント名をそれぞれ定義しており、実装時に「どの文書を正とするか」が曖昧になる箇所が残っている。

実装前に優先して直すべき点は、`MacroExecutor` の削除方針、マクロメタデータ型の整理、`ExecutionContext` / `RunResult` / `RunLogContext` の所有文書、キャンセル API、ログ event / error code、settings と Resource File I/O の責務境界である。これらは実装の分岐やテストの期待値を直接左右するため、仕様確定前に一元化が必要である。

## 2. 全体指摘

全体指摘は対応済み。残件はファイル別指摘に集約する。

## 3. ファイル別指摘

### `FW_REARCHITECTURE_OVERVIEW.md`

- **重要度**: Major
- **指摘**: Overview が多くの型を直接定義しており、各詳細仕様と重複している。特に `MacroManifest`, `MacroDescriptor`, `MacroDefinition`, `ExecutionContext`, `RunResult`, `RunHandle`, `RuntimeOptions` は詳細仕様の正本と同期が必要である。
- **修正案**: Overview はアーキテクチャ判断と公開互換契約に絞り、型の詳細は所有文書へリンクする。`MacroManifest` / `MacroDescriptor` / `MacroDefinition` は型の統合または廃止検討の結果だけを記載し、Overview 内のコード例は「抜粋」であることを明記する。

### `ARCHITECTURE_DIAGRAMS.md`

- **重要度**: Major
- **指摘**: 図は有用だが、図の正本性と更新責任が不明である。仕様本文と図がズレたときにどちらを直すべきか判断できない。
- **修正案**: 冒頭で「補助資料」と明記し、各図に対応する正本セクションへのリンクを付ける。図の表示確認、mermaid 構文確認、仕様本文との同期確認をチェックリスト化する。

### `IMPLEMENTATION_PLAN.md`

- **重要度**: Major
- **指摘**: 着手条件とフェーズ 1 の作業が混在している。`Phase 0` 相当の互換テスト追加が前提なのか、実装計画内の最初の成果物なのかが曖昧である。
- **修正案**: 「実装前提」「フェーズ 1 の成果物」を分ける。CLI 引数互換、GUI/CLI 移行、`MacroExecutor` 削除は各フェーズの完了条件に具体的なテスト名を追加する。`MacroExecutor` の非推奨判断や adapter 縮退フェーズは削除し、GUI/CLI が新 Runtime へ移行した時点で `MacroExecutor` を削除する計画へ直す。

### `RUNTIME_AND_IO_PORTS.md`

- **重要度**: Major
- **指摘**: Runtime と Port の中核仕様だが、`CommandFacade` と各 Port の責務変換、`DefaultCommand` の互換構築、frame readiness の戻り値、Port close 失敗時の扱いが不足している。
- **修正案**: `CommandFacade` の各メソッドがどの Port 呼び出しへ展開されるかを表にする。`FrameSourcePort.await_ready()` は timeout 時に `False` を返すのか例外を投げるのかを固定する。`DefaultCommand` は `context` と旧引数の同時指定時の挙動を明記する。

### `CONFIGURATION_AND_RESOURCES.md`

- **重要度**: Major
- **指摘**: `MacroSettingsResolver.resolve()` が `None` を返す条件、`load()` が空 dict を返す条件、TOML 破損時に既定値へ fallback するか実行中止するかが曖昧である。
- **修正案**: `resolve()` は「ファイルなしなら `None`、不正 path なら `ConfigurationError`」、`load()` は「`None` なら `{}`、parse/schema 不正なら `ConfigurationError`」のように明文化する。TOML 破損時は既定値 fallback しないか、fallback するならログとユーザー通知の要件を追加する。

### `RESOURCE_FILE_IO.md`

- **重要度**: Major
- **指摘**: `MacroResourceScope.assets_roots` が複数 root を持つ理由、`OverwritePolicy.UNIQUE` の拡張子扱い、atomic write の前提が不足している。
- **修正案**: legacy static root と新 assets root の併用例を示す。`sample.png` の衝突時は `sample_1.png` にする、のように拡張子保持ルールを固定する。atomic write は `tempfile.NamedTemporaryFile(dir=output_root, delete=False)` と `Path.replace()` を基本とし、別ファイルシステムは後続課題として明記する。

### `ERROR_CANCELLATION_LOGGING.md`

- **重要度**: Critical
- **指摘**: キャンセル、例外、ログ event、`finalize(cmd, outcome)` opt-in の複数論点を扱っているため、他文書との責務重複が大きい。`macro.finalize_failed` は logging catalog にも必要である。`Command.stop()` の例外送出も前提扱いされているが、停止要求と即時例外を同一視する必要があるか未検討である。
- **修正案**: 本書は「発生条件と RunResult への正規化」を正とし、event catalog は `LOGGING_FRAMEWORK.md` へ寄せる。`Command.stop()` は停止要求 API として再定義し、例外送出を必須契約にするか廃止するかを明示する。`SupportsFinalizeOutcome` は Protocol か `inspect.signature()` かを選び、既存 `finalize(cmd)` との共存手順を疑似コードで示す。

### `LOGGING_FRAMEWORK.md`

- **重要度**: Major
- **指摘**: `LoggerPort.bind_context()` の戻り値型、`UserEvent` から `TechnicalLog` を生成する規則、log retention / cleanup、legacy handler 例外隔離が不足している。
- **修正案**: `bind_context()` は `LoggerPort` を返す self-like interface か別型かを型ヒントで示す。`LoggerPort.user()` が生成する user / technical のペアについて、保持するフィールドとマスク対象を表にする。`LegacyStringSink` の例外は後続 sink へ伝播させないことをテスト方針へ追加する。

### `OBSERVABILITY_AND_GUI_CLI.md`

- **重要度**: Major
- **指摘**: GUI/CLI の Runtime builder 利用は具体的だが、CLI 引数で secret を受けた場合の `SecretsSettings` snapshot 化、終了コード、GUI cancel のスレッド境界が不足している。
- **修正案**: CLI の `--discord-webhook` などを一時 `SecretsSettings` として扱う例を追加する。`RunStatus` と CLI exit code の対応表を定義する。GUI cancel は `RunHandle.cancel()` のみ、Qt Signal は GUI 層 adapter の責務と明記する。

### `MACRO_COMPATIBILITY_AND_REGISTRY.md`

- **重要度**: Major
- **指摘**: 互換契約の内容は詳しいが、テンプレート上の `### 後方互換性` が独立していない。`MacroExecutor` のシグネチャ保証や adapter 契約に関する記述がある場合、削除方針と矛盾する。`MacroFactory` が状態を持たず毎回新インスタンスを返す契約も明確化が必要である。
- **修正案**: `### 後方互換性` を追加し、その下に `Compatibility Contract` を置く。`MacroExecutor` は互換契約に含めず削除対象として扱い、シグネチャ保証・adapter 契約・一定期間残す文言を削除する。`MacroFactory.create()` は毎回独立した `MacroBase` インスタンスを返すことを docstring とテスト名で固定する。

### `DEPRECATION_AND_MIGRATION.md`

- **重要度**: Major
- **指摘**: 廃止候補表は有用だが、廃止判断の基準と文書分割の妥当性検証が弱い。特に `MacroExecutor` を「廃止候補」や「非推奨後削除」と扱うと、存続期間や互換 shim が必要であるかのように読める。
- **修正案**: `MacroExecutor` は廃止候補表から分離し、「再設計で削除する旧実装」として扱う。非推奨警告・一定期間存続・adapter 縮退ではなく、GUI/CLI/テストの参照をなくしたうえで削除する手順を書く。その他の廃止候補は「外部利用調査」「削除可能条件」「代替 API」「参照テスト」を分けて書く。

### `TEST_STRATEGY.md`

- **重要度**: Major
- **指摘**: テスト対象は広く網羅されているが、「公開互換契約に含まれるもの / 含まれないもの」の定義が他文書に依存している。`MacroExecutor` の legacy gate が残ると削除方針と矛盾する。Fake adapter の spy 項目も、どの Port 契約を検証するかがやや抽象的である。
- **修正案**: 冒頭に互換契約表を置き、`MacroBase`, `Command`, `DefaultCommand`, constants, `MacroStopException`, settings lookup を既存マクロ互換対象として明記する。`MacroExecutor` は互換対象から明示的に除外し、legacy gate ではなく削除確認テストへ置き換える。Fake adapter は Port ごとに「記録する値」「assert する順序」「例外時の期待値」を表にする。

## 4. 実装前に完了させるべき最小修正

| 優先 | 修正内容 | 主な対象 |
|---|---|---|
| 7 | settings / resource / runtime builder の責務境界をフロー図にする | Configuration, Resource, Runtime |
| 8 | Port 契約の未定義部分を型・戻り値・例外で固定する | Runtime |
| 9 | テスト分類と性能測定方法を `TEST_STRATEGY.md` に集約する | Test Strategy |
