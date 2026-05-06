# フレームワーク再設計ドキュメント群レビューコメント

> **レビュー対象**: `spec\framework\rearchitecture\*.md`  
> **レビュー日**: 2026-05-07  
> **観点**: `framework-spec-writing` の必須構成、正本ドキュメント間の整合性、依存方向、後方互換性、シングルトン管理、スレッド安全性、テスト方針

## 1. 総評

`spec\framework\rearchitecture` 配下の 13 文書は、全体として 6 セクション構成、用語定義表、対象ファイル表、公開 API コードブロック、テスト方針表、実装チェックリストを備えている。再設計の意図である「既存マクロの import / lifecycle 互換を維持し、GUI/CLI と Runtime / Ports の責務を分離する」方針も明確である。

主な修正対象は、正本 API と概要・図版・補助文書の抜粋がずれている箇所である。実装前に正本へ寄せないと、`MacroRuntime` / `MacroRegistry` / Resource Port / `MacroExecutor` 削除方針の解釈が分かれる。

## 2. 優先度別レビューコメント

### Critical

#### C-1. `MacroRuntime` / `MacroRegistry` の公開 API が文書間で競合している

| 項目 | 内容 |
|------|------|
| 対象 | `FW_REARCHITECTURE_OVERVIEW.md`, `RUNTIME_AND_IO_PORTS.md`, `MACRO_COMPATIBILITY_AND_REGISTRY.md` |
| 該当箇所 | `FW_REARCHITECTURE_OVERVIEW.md:513-544`, `RUNTIME_AND_IO_PORTS.md:363-400`, `MACRO_COMPATIBILITY_AND_REGISTRY.md:295-317` |
| 問題 | Overview の `MacroRuntime` は `reload()` / `list_macros()` を持つが、Runtime 正本の `MacroRuntime` は `run()` / `start()` / `shutdown()` だけを持つ。Overview の `MacroRegistry.get()` / `list()` も Registry 正本の `resolve()` / `list(include_failed=False)` と一致しない。 |
| 影響 | 実装者が Overview の抜粋を API 正本として扱うと、Runtime と Registry の責務が混ざる。GUI/CLI が Runtime 経由で一覧取得するのか、Registry を直接参照するのかも曖昧になる。 |
| 修正案 | Overview から詳細シグネチャを削除し、「主要 API 名の概要」に留める。公開シグネチャは `RUNTIME_AND_IO_PORTS.md` と `MACRO_COMPATIBILITY_AND_REGISTRY.md` だけに置く。どうしても抜粋を残す場合は、正本と同じメソッド名・戻り値に揃え、抜粋であることをコードブロック直前に明記する。 |

#### C-2. `ARCHITECTURE_DIAGRAMS.md` が `MacroExecutor` の最終方針と矛盾している

| 項目 | 内容 |
|------|------|
| 対象 | `ARCHITECTURE_DIAGRAMS.md`, `DEPRECATION_AND_MIGRATION.md`, `IMPLEMENTATION_PLAN.md` |
| 該当箇所 | `ARCHITECTURE_DIAGRAMS.md:128-170`, `DEPRECATION_AND_MIGRATION.md:157-168`, `IMPLEMENTATION_PLAN.md:150-178` |
| 問題 | 図では `MacroExecutor` から `MacroRuntime` へ「旧入口は委譲」と描かれている。一方で廃止方針では `MacroExecutor` は互換 shim も作らず削除し、`ModuleNotFoundError` を確認するテストまで定義している。 |
| 影響 | 実装時に一時 adapter を作るべきか、最終的に削除するだけかが読み手によって分かれる。旧入口を残す実装が入ると、削除ゲートと矛盾する。 |
| 修正案 | 最終アーキテクチャ図から `ExecutorNode -. "旧入口は委譲" .-> Runtime` を削除する。移行途中の図として残す場合は、図タイトルを「削除前の暫定構成」に変え、Phase 11 で存在しないことを注記する。 |

### High

#### H-1. Resource Port 図で read-only assets と writable outputs が混同されている

| 項目 | 内容 |
|------|------|
| 対象 | `ARCHITECTURE_DIAGRAMS.md`, `RESOURCE_FILE_IO.md`, `RUNTIME_AND_IO_PORTS.md` |
| 該当箇所 | `ARCHITECTURE_DIAGRAMS.md:270-316`, `RESOURCE_FILE_IO.md:216-250`, `RUNTIME_AND_IO_PORTS.md:585-589` |
| 問題 | 図では `ResourceStorePort` に `resolve / save_image / load_image` がぶら下がっているが、正本では `ResourceStorePort` は assets 読み込み、`RunArtifactStore` は outputs 保存を担当する。図には `RunArtifactStore` が存在しない。 |
| 影響 | `cmd.save_img()` の保存先が assets 側に戻る誤実装を誘発する。`resources\<macro_id>\assets` と `runs\<run_id>\outputs` の分離が再設計の重要点なので、図の誤りは実装リスクが高い。 |
| 修正案 | Port layer に `RunArtifactStore` を追加し、`DefaultCommand.save_img()` は `RunArtifactStore.save_image()` へ、`DefaultCommand.load_img()` は `ResourceStorePort.load_image()` へ分岐する図に修正する。Adapter 名も `StaticResourceStorePort` ではなく正本 API に合わせる。 |

#### H-2. `ErrorInfo` / `RunResult` の抜粋が正本とずれる余地を残している

| 項目 | 内容 |
|------|------|
| 対象 | `FW_REARCHITECTURE_OVERVIEW.md`, `ERROR_CANCELLATION_LOGGING.md`, `RUNTIME_AND_IO_PORTS.md` |
| 該当箇所 | `FW_REARCHITECTURE_OVERVIEW.md:430-510`, `ERROR_CANCELLATION_LOGGING.md:304-321`, `RUNTIME_AND_IO_PORTS.md:323-338` |
| 問題 | Overview に `RunStatus`、`ErrorInfo`、`RunResult` の dataclass 風定義があるが、正本は Runtime / Error 仕様である。特に `ErrorInfo.kind: str` のような簡略化は、`ErrorKind` と error code catalog を正とする Error 仕様と表現がずれる。 |
| 影響 | 実装時に型定義を Overview から起こすと、Error 仕様の `ErrorKind`、code catalog、secret / traceback 分離が反映されない可能性がある。 |
| 修正案 | Overview の型定義は削除するか、`# 非正本の抜粋` としてフィールドを最小化する。`RunResult` は `RUNTIME_AND_IO_PORTS.md`、`ErrorInfo` / `ErrorKind` / error code は `ERROR_CANCELLATION_LOGGING.md` を参照する文に置き換える。 |

#### H-3. `SupportsFinalizeOutcome` が `MacroBase.finalize(cmd)` と同名で衝突する

| 項目 | 内容 |
|------|------|
| 対象 | `ERROR_CANCELLATION_LOGGING.md`, `FW_REARCHITECTURE_OVERVIEW.md` |
| 該当箇所 | `ERROR_CANCELLATION_LOGGING.md:261-268`, `FW_REARCHITECTURE_OVERVIEW.md:582-584` |
| 問題 | `MacroBase.finalize(cmd)` を唯一の抽象契約として維持すると明記しつつ、opt-in として `SupportsFinalizeOutcome.finalize(cmd, outcome)` を同名メソッドで定義している。Python では同じメソッド名で 2 つのシグネチャを実装できない。 |
| 影響 | 既存マクロが `finalize(cmd)` を実装しただけで Protocol 判定されるのか、`finalize(cmd, outcome)` を実装する新マクロが抽象契約を満たすのかが不明になる。Runtime 側の呼び分けも実装しにくい。 |
| 修正案 | opt-in 拡張は `finalize_with_outcome(cmd, outcome)` の別名にするか、`finalize(cmd, outcome: RunResult | None = None)` を許可する破壊的変更として明示する。既存互換を優先するなら別名メソッドが安全である。 |

#### H-4. `LogManager` / `log_manager` の「最終削除」と「互換 shim」の段階が文書ごとに読み分けづらい

| 項目 | 内容 |
|------|------|
| 対象 | `FW_REARCHITECTURE_OVERVIEW.md`, `OBSERVABILITY_AND_GUI_CLI.md`, `DEPRECATION_AND_MIGRATION.md`, `LOGGING_FRAMEWORK.md` |
| 該当箇所 | `FW_REARCHITECTURE_OVERVIEW.md:300-304`, `OBSERVABILITY_AND_GUI_CLI.md:229-231`, `DEPRECATION_AND_MIGRATION.md:176-181`, `LOGGING_FRAMEWORK.md:368-370` |
| 問題 | Overview は `log_manager` を互換 shim として段階廃止すると書く一方、Observability は `LogManager` クラスを維持しないと断定する。最終状態としては整合しているが、移行期間中に何を残せるかが 1 箇所で確認しにくい。 |
| 影響 | ロギング移行フェーズで、短期 shim の可否、削除ゲート、`reset_for_testing()` 対象の解釈がぶれる。 |
| 修正案 | `DEPRECATION_AND_MIGRATION.md` に「移行期間中だけ許可する shim」と「最終的に存在してはいけない API」を分けた表を追加し、他文書はその表へリンクする。Observability の文には「最終状態では」を補う。 |

#### H-5. `MacroDefinition` と `MacroResourceScope.from_definition()` の接続契約が弱い

| 項目 | 内容 |
|------|------|
| 対象 | `MACRO_COMPATIBILITY_AND_REGISTRY.md`, `RESOURCE_FILE_IO.md`, `CONFIGURATION_AND_RESOURCES.md` |
| 該当箇所 | `MACRO_COMPATIBILITY_AND_REGISTRY.md:270-285`, `RESOURCE_FILE_IO.md:193-205`, `CONFIGURATION_AND_RESOURCES.md:264-268` |
| 問題 | `MacroDefinition` は `id`、`macro_root`、`settings_path` を持つが、`MacroResourceScope.from_definition()` がどのフィールドを使い、どの path を assets root 候補にするかが Resource 仕様側で十分に明示されていない。 |
| 影響 | single-file macro、package macro、manifest あり macro で assets root が変わり、`cmd.load_img()` の探索順が実装者ごとに分かれる可能性がある。 |
| 修正案 | `RESOURCE_FILE_IO.md` に `from_definition()` の変換表を追加する。例: `definition.id -> macro_id`、`definition.macro_root -> package assets candidate`、`project_root\resources\<macro_id>\assets -> standard assets root`。 |

#### H-6. 実装計画の Phase と廃止候補の削除ゲートは整合しているが、正本参照が分散している

| 項目 | 内容 |
|------|------|
| 対象 | `IMPLEMENTATION_PLAN.md`, `DEPRECATION_AND_MIGRATION.md`, `TEST_STRATEGY.md` |
| 該当箇所 | `IMPLEMENTATION_PLAN.md:128-178`, `DEPRECATION_AND_MIGRATION.md:157-181`, `TEST_STRATEGY.md:278-300` |
| 問題 | 実装順、削除条件、テスト粒度が別々の表にある。内容は概ね一致しているが、ある廃止候補が「どの Phase で」「どのテストが green なら」削除できるかを 1 表で追えない。 |
| 影響 | 実装フェーズで削除が早すぎる、または削除し忘れるリスクがある。 |
| 修正案 | `IMPLEMENTATION_PLAN.md` のフェーズ別ゲートに `DEPRECATION_AND_MIGRATION.md` の候補名とテスト名を列として追加する。詳細は Deprecation 正本に置き、計画書はリンク表にする。 |

### Medium

#### M-1. `allow_dummy` の有効化経路と優先順位が不足している

| 項目 | 内容 |
|------|------|
| 対象 | `RUNTIME_AND_IO_PORTS.md`, `CONFIGURATION_AND_RESOURCES.md`, `DEPRECATION_AND_MIGRATION.md` |
| 該当箇所 | `RUNTIME_AND_IO_PORTS.md:67-75`, `RUNTIME_AND_IO_PORTS.md:573-583`, `CONFIGURATION_AND_RESOURCES.md:198-203`, `DEPRECATION_AND_MIGRATION.md:176-178` |
| 問題 | 本番既定で dummy fallback を禁止する方針は明確だが、CLI フラグ、GUI 設定、テスト fixture、`RuntimeBuildRequest.allow_dummy`、`runtime.allow_dummy` 設定の優先順位がまとまっていない。 |
| 修正案 | `RuntimeOptions.allow_dummy` の決定順を表にする。例: test fixture 明示値、CLI `--dummy-devices`、GUI 設定、settings snapshot の順で上書き可否を定義する。 |

#### M-2. 性能しきい値の測定方法はあるが、しきい値更新の責任者が未定義である

| 項目 | 内容 |
|------|------|
| 対象 | `FW_REARCHITECTURE_OVERVIEW.md`, `TEST_STRATEGY.md`, `RESOURCE_FILE_IO.md`, `LOGGING_FRAMEWORK.md` |
| 該当箇所 | `FW_REARCHITECTURE_OVERVIEW.md:266-276`, `TEST_STRATEGY.md:149-181` |
| 問題 | `TEST_STRATEGY.md` は P95、試行回数、CI 扱いを定義しているが、初回実測後に誰がどの文書へしきい値を反映するかが未定義である。 |
| 修正案 | `TEST_STRATEGY.md` に「性能しきい値更新手順」を追加する。初回測定結果を `tests\perf\` の期待値または設定定数へ反映し、仕様書の数値とテストの数値を同じ PR で更新する、という運用を明記する。 |

#### M-3. P95 の計算方法が実装者依存になっている

| 項目 | 内容 |
|------|------|
| 対象 | `TEST_STRATEGY.md` |
| 該当箇所 | `TEST_STRATEGY.md:160-181` |
| 問題 | P95 を判定値にするとあるが、サンプル数 10 / 30 のときの percentile 算出方法が未定義である。 |
| 修正案 | `sorted(samples)[ceil(n * 0.95) - 1]` など、実装で使う式を明記する。あわせて、サンプル数が 10 未満の場合は性能テストとして失敗にするか、記録用途に落とすかを決める。 |

#### M-4. `@pytest.mark.realdevice` の明示実行条件が未定義である

| 項目 | 内容 |
|------|------|
| 対象 | `TEST_STRATEGY.md`, `IMPLEMENTATION_PLAN.md` |
| 該当箇所 | `TEST_STRATEGY.md:313-325`, `IMPLEMENTATION_PLAN.md:390-402` |
| 問題 | 実機テストを通常 CI から分離する方針はあるが、実行を許可する環境変数名や skip 条件が定義されていない。 |
| 修正案 | 例として `NYX_REALDEVICE=1` を採用し、fixture がこの値とデバイス接続を確認して skip / fail を分ける、と明記する。 |

#### M-5. `SettingsStore` / `SecretsStore` のファイル I/O と snapshot のスレッド安全性が薄い

| 項目 | 内容 |
|------|------|
| 対象 | `CONFIGURATION_AND_RESOURCES.md`, `TEST_STRATEGY.md` |
| 該当箇所 | `CONFIGURATION_AND_RESOURCES.md:156-179`, `CONFIGURATION_AND_RESOURCES.md:216-244`, `TEST_STRATEGY.md:183-187` |
| 問題 | 実行中は settings snapshot を渡す方針だが、GUI 設定保存と Runtime 起動が並行した場合の `load()` / `save()` / `snapshot()` の lock、ファイル置換、SecretsSnapshot の不変性が明示されていない。 |
| 修正案 | store 内部 lock の有無、snapshot の immutable copy 化、save 中の load の扱いを記述する。秘密値は snapshot 取得後に実行 context へ直接渡さない方針と合わせてテスト名を追加する。 |

### Low

#### L-1. GUI/CLI のユーザー表示例が不足している

| 項目 | 内容 |
|------|------|
| 対象 | `OBSERVABILITY_AND_GUI_CLI.md`, `LOGGING_FRAMEWORK.md`, `ERROR_CANCELLATION_LOGGING.md` |
| 該当箇所 | `OBSERVABILITY_AND_GUI_CLI.md:214-227`, `LOGGING_FRAMEWORK.md:335-367` |
| 問題 | `ErrorInfo.message` は短文、traceback や secret を出さないという方針はあるが、OK / NG 例がない。 |
| 修正案 | デバイス未接続、settings parse 失敗、通知失敗、マクロ例外の 4 ケースについて、ユーザー表示と技術ログの例を表で追加する。 |

#### L-2. Mermaid 図の凡例が不足している

| 項目 | 内容 |
|------|------|
| 対象 | `ARCHITECTURE_DIAGRAMS.md` |
| 該当箇所 | `ARCHITECTURE_DIAGRAMS.md:101-340` |
| 問題 | `classDef` の色分けはあるが、GitHub 表示で色の意味を読めない環境がある。 |
| 修正案 | 各図の直後に、stable / runtime / port / adapter / legacy / guard などの分類と意味を表で追加する。 |

#### L-3. 文書内 path 表記の意図を補足した方がよい

| 項目 | 内容 |
|------|------|
| 対象 | 全文書 |
| 問題 | リポジトリ内ファイル参照は `spec/framework/...` と `src\nyxpy\...` が混在し、TOML / manifest の portable path では `/` を使う前提も出てくる。仕様上の混在は妥当だが、意図が明記されていない箇所では Windows path と portable path の区別が読み取りづらい。 |
| 修正案 | `MACRO_MIGRATION_GUIDE.md` または Overview に「文書内のファイル参照はリポジトリ相対、manifest / TOML 内 path は portable `/`、Windows 実行時 path は `Path` で正規化」という注記を置く。 |

## 3. 形式チェック結果

| 観点 | 結果 | コメント |
|------|------|----------|
| 必須 6 セクション | 合格 | 対象 13 文書はいずれも `## 1` から `## 6` を持つ。 |
| 用語定義表 | 合格 | 主要文書に表形式で存在する。正本参照をさらに強める余地がある。 |
| 対象ファイル表 | 合格 | 主要な実装・テスト対象が表形式で列挙されている。 |
| 公開 API コードブロック | 要修正 | コードブロック自体はあるが、概要・図版の抜粋が正本 API とずれている。 |
| 後方互換性 | 合格 | 維持対象と削除対象は明確。`MacroExecutor` の図だけ修正が必要である。 |
| シングルトン管理 | 要補足 | 最終削除と移行期間 shim の区別を表にすると実装しやすい。 |
| テスト方針 | 合格 | 種別、配置、性能、実機分離まで定義済み。実行条件と P95 算出式を補うとよい。 |

## 4. 推奨修正順

1. `MacroRuntime` / `MacroRegistry` の公開 API を正本へ一本化する。
2. `ARCHITECTURE_DIAGRAMS.md` の `MacroExecutor` 委譲図と Resource Port 図を修正する。
3. `SupportsFinalizeOutcome` の opt-in 契約を別メソッド名または明示的な互換変更として確定する。
4. `LogManager` / `log_manager` の移行期間 shim と最終削除の表を追加する。
5. `allow_dummy`、P95 算出、realdevice 実行条件、settings / secrets snapshot の並行性を補足する。
