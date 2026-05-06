# フレームワーク再設計ドキュメント レビューコメント

> **対象**: `spec\framework\rearchitecture\*.md`  
> **観点**: フレームワーク仕様書テンプレート、依存方向、後方互換性、実装可能性、テスト可能性、文書間整合性

## 1. 総評

再設計の分割方針、互換ゲート、Ports/Adapters 化、GUI/CLI 移行の方向性は具体化されている。一方で、複数文書が同じ型・責務・イベント名をそれぞれ定義しており、実装時に「どの文書を正とするか」が曖昧になる箇所が残っている。

実装前に優先して直すべき点は、`MacroExecutor` の削除方針、マクロメタデータ型の整理、`ExecutionContext` / `RunResult` / `RunLogContext` の所有文書、キャンセル API、ログ event / error code、settings と Resource File I/O の責務境界である。これらは実装の分岐やテストの期待値を直接左右するため、仕様確定前に一元化が必要である。

## 2. 全体指摘

### RC-001: 文書種別とテンプレート準拠状態が混在している

- **重要度**: Critical
- **対象**: `FW_REARCHITECTURE_OVERVIEW.md`, `ARCHITECTURE_DIAGRAMS.md`, `IMPLEMENTATION_PLAN.md`, `MACRO_COMPATIBILITY_AND_REGISTRY.md`
- **位置**:
  - `ARCHITECTURE_DIAGRAMS.md` 全体
  - `IMPLEMENTATION_PLAN.md` 全体
  - `MACRO_COMPATIBILITY_AND_REGISTRY.md` `### Compatibility Contract`
- **指摘**: フレームワーク仕様書テンプレートは「概要 / 対象ファイル / 設計方針 / 実装仕様 / テスト方針 / 実装チェックリスト」を必須としているが、再設計ディレクトリには仕様書、実装計画、図解補助文書が混在している。`MACRO_COMPATIBILITY_AND_REGISTRY.md` では `### 後方互換性` が独立せず `### Compatibility Contract` に寄っており、レビュー観点上の検索性が落ちる。
- **修正案**: 各ファイルの冒頭に「仕様書」「補助資料」「実装計画」の文書種別を明記する。仕様書として扱うファイルは必須 6 セクションへ揃え、補助資料である場合は「本書は `FW_REARCHITECTURE_OVERVIEW.md` の補助資料であり、実装仕様の正は参照先」と明記する。

### RC-002: 正とする文書の所有権が不足している

- **重要度**: Critical
- **対象**: 全体
- **位置**: 各ファイルの関連ドキュメント、用語定義、実装仕様
- **指摘**: `RunResult`, `ExecutionContext`, `RunLogContext`, `ConfigurationError`, logging event 名、`MacroExecutor`, `MacroManifest`, `MacroDescriptor`, `MacroDefinition`, `MacroSettingsResolver` が複数文書で説明されている。相互参照は多いが、型定義・責務・テスト期待値の正本がどれか不明である。
- **修正案**: `FW_REARCHITECTURE_OVERVIEW.md` に「仕様依存関係」表を追加する。各概念について「所有文書」「参照元」「変更時に同期すべき文書」を定義する。

例:

| 概念 | 正とする文書 | 参照元 |
|---|---|---|
| `MacroRegistry` / マクロメタデータ型 | `MACRO_COMPATIBILITY_AND_REGISTRY.md` | Overview, Implementation Plan, Test Strategy |
| `ExecutionContext` / `RunResult` / `RunHandle` | `RUNTIME_AND_IO_PORTS.md` または `ERROR_CANCELLATION_LOGGING.md` のどちらかに統一 | Logging, Observability, Test Strategy |
| logging event 名 / sink 契約 | `LOGGING_FRAMEWORK.md` | Error/Cancellation, Observability |
| settings lookup | `CONFIGURATION_AND_RESOURCES.md` | Resource File I/O, Runtime |

### RC-003: `MacroExecutor` は削除方針へ統一する

- **重要度**: Critical
- **対象**: `FW_REARCHITECTURE_OVERVIEW.md`, `RUNTIME_AND_IO_PORTS.md`, `ERROR_CANCELLATION_LOGGING.md`, `MACRO_COMPATIBILITY_AND_REGISTRY.md`, `IMPLEMENTATION_PLAN.md`, `TEST_STRATEGY.md`
- **位置**:
  - `FW_REARCHITECTURE_OVERVIEW.md` `MacroExecutor は既存マクロ互換 API ではない`
  - `RUNTIME_AND_IO_PORTS.md` `MacroExecutor.execute(cmd, exec_args)`
  - `ERROR_CANCELLATION_LOGGING.md` `旧 MacroExecutor.execute() を残す場合は戻り値 None を維持`
  - `IMPLEMENTATION_PLAN.md` `フェーズ 10: MacroExecutor 廃止判断または adapter 縮退`
- **指摘**: `MacroExecutor` は既存マクロ互換 API ではないと書かれている一方で、「残す場合」「一時 adapter」「戻り値 `None` と例外再送出を維持」「非推奨期間」など、存続を前提に読める表現が複数残っている。これにより、実装者が `MacroExecutor` の互換維持や縮退 adapter 実装に工数を使う余地が生まれる。
- **修正案**: `MacroExecutor` は削除方針へ統一し、互換維持・一定期間存続・adapter 縮退・非推奨期間の文言を削除する。最低限、以下を明記する。
  - `MacroExecutor` は再設計後の公開 API・既存マクロ互換契約・移行 adapter のいずれにも含めない。
  - GUI/CLI/テストは `MacroRuntime` / `RunHandle` / `MacroRegistry` を直接使う構成へ移行する。
  - `MacroExecutor.execute()` の戻り値 `None`、例外再送出、`macros` / `macro` 属性などの旧契約は保証しない。
  - `DEPRECATION_AND_MIGRATION.md` では `MacroExecutor` を「廃止候補」ではなく「削除対象」とし、削除後に残す import 互換 shim も作らない方針を明記する。
  - テスト方針から `legacy executor gate` を削除し、代わりに `test_macro_executor_removed` や `test_gui_cli_do_not_import_macro_executor` のような削除確認テストを置く。

### RC-004: `MacroDescriptor` / `MacroDefinition` / `MacroManifest` は統合・廃止を検討する

- **重要度**: Major
- **対象**: `FW_REARCHITECTURE_OVERVIEW.md`, `MACRO_COMPATIBILITY_AND_REGISTRY.md`, `IMPLEMENTATION_PLAN.md`
- **位置**:
  - `FW_REARCHITECTURE_OVERVIEW.md` `MacroDescriptor` / `MacroDefinition`
  - `MACRO_COMPATIBILITY_AND_REGISTRY.md` `### Manifest 仕様`
  - `IMPLEMENTATION_PLAN.md` `MacroFactory | MacroDescriptor または MacroDefinition`
- **指摘**: `MacroManifest`, `MacroDescriptor`, `MacroDefinition` はいずれもマクロの識別子、表示名、entrypoint、settings path など近い情報を扱う。責務差分が小さいまま複数型を導入すると、変換処理、同期漏れ、テスト対象が増える。`MacroFactory` が `MacroDescriptor` と `MacroDefinition` のどちらを受け取るかも文書により揺れている。
- **修正案**: まず「本当に複数型が必要か」を検討し、不要なら 1 つの `MacroDefinition` に統合する。分離する場合でも、各型の存在理由と廃止できない理由を明記する。
  - 推奨案: `MacroDefinition` を唯一のマクロメタデータ型にし、manifest ファイルは `MacroDefinition` を生成する入力形式として扱う。`MacroManifest` は永続化フォーマット名に留め、Python クラスとしての独立定義を避ける。
  - 代替案: 内部専用の `MacroDescriptor` と公開用 `MacroDefinition` を分ける場合、変換方向を `MacroDescriptor -> MacroDefinition` の一方向に限定し、`MacroFactory` は内部型だけを受け取る。
  - どちらの案でも、`MacroFactory.create()` が受け取る型を 1 つに固定し、`MacroManifest` / `MacroDescriptor` / `MacroDefinition` の三者が同じデータを重複保持しないようにする。

### RC-005: `ExecutionContext`, `RunLogContext`, `RunResult` の所有責務が重複している

- **重要度**: Critical
- **対象**: `FW_REARCHITECTURE_OVERVIEW.md`, `RUNTIME_AND_IO_PORTS.md`, `ERROR_CANCELLATION_LOGGING.md`, `LOGGING_FRAMEWORK.md`, `OBSERVABILITY_AND_GUI_CLI.md`
- **位置**:
  - `FW_REARCHITECTURE_OVERVIEW.md` `ExecutionContext は Command を保持しない`
  - `RUNTIME_AND_IO_PORTS.md` `RunResult`
  - `ERROR_CANCELLATION_LOGGING.md` `RunResult と失敗情報`
  - `LOGGING_FRAMEWORK.md` `ExecutionContext は LoggerPort.bind_context(...) の戻り値を保持`
- **指摘**: `ExecutionContext` が何を保持するか、`RunLogContext` を誰が生成・保持するか、`RunResult` を Runner と Runtime のどちらが所有するかが文書間で分散している。特に close 失敗時の `cleanup_warnings` 追記責務は実装上の分岐点になる。
- **修正案**: 1 文書に `ExecutionContext` の完全なフィールド一覧を置く。`RunResult` は `MacroRunner` が生成し、`MacroRuntime` は Port close 失敗だけを `cleanup_warnings` へ追記する、というルールを正本に記載する。`RunLogContext` は `ExecutionContext.run_log_context` として保持するのか、`LoggerPort.bind_context()` の戻り値だけを保持するのかを選ぶ。

### RC-006: キャンセル API が外部操作とマクロ内部操作で混ざっている

- **重要度**: Critical
- **対象**: `ERROR_CANCELLATION_LOGGING.md`, `OBSERVABILITY_AND_GUI_CLI.md`, `RUNTIME_AND_IO_PORTS.md`, `TEST_STRATEGY.md`
- **位置**:
  - `ERROR_CANCELLATION_LOGGING.md` `GUI cancel は Command.request_cancel(...)`
  - `OBSERVABILITY_AND_GUI_CLI.md` `GUI cancel は RunHandle.cancel() のみ`
  - `RUNTIME_AND_IO_PORTS.md` `RunHandle.cancel() から RunResult.cancelled`
- **指摘**: GUI/CLI の外部キャンセルを `RunHandle.cancel()` で表す箇所と、`Command.request_cancel()` で表す箇所がある。加えて、`Command.stop()` が例外送出を維持する前提で書かれているが、停止要求が `CancellationToken` / `RunHandle` 経由で伝播するなら、`stop()` 自体が例外を投げる必要があるかは再検討が必要である。
- **修正案**: API を 3 層に分けて定義する。
  - 外部操作: GUI/CLI は `RunHandle.cancel()` のみを呼ぶ。
  - Runtime 内部: `RunHandle.cancel()` が `CancellationToken.request_cancel()` を呼ぶ。
  - マクロ内部: `Command.stop()` は停止要求を登録する API とし、例外送出は必須契約にしない。即時脱出が必要な箇所は `CancellationToken.check_cancelled()` や `Command.wait()` などの中断チェック点で扱う。
  - 既存実装が `Command.stop()` の例外に依存しているかを調査し、依存が小さい場合は例外送出を廃止する。依存が残る場合でも、例外送出は `stop(raise_immediately=True)` のような明示 opt-in に限定する。

### RC-007: logging event 名と error code が一元管理されていない

- **重要度**: Critical
- **対象**: `ERROR_CANCELLATION_LOGGING.md`, `LOGGING_FRAMEWORK.md`, `OBSERVABILITY_AND_GUI_CLI.md`, `CONFIGURATION_AND_RESOURCES.md`
- **位置**:
  - `ERROR_CANCELLATION_LOGGING.md` `macro.finalize_failed`
  - `LOGGING_FRAMEWORK.md` `macro.finished`, `macro.cancelled`, `macro.failed`
  - `OBSERVABILITY_AND_GUI_CLI.md` `ConfigurationError`
- **指摘**: `macro.finalize_failed` は Error/Cancellation 側で定義され、`macro.finished` などは Logging 側で定義されている。`ConfigurationError` も複数文書に現れるが、error code の体系と発生元が統一されていない。
- **修正案**: `LOGGING_FRAMEWORK.md` に event catalog を置き、`ERROR_CANCELLATION_LOGGING.md` は発行タイミングだけを書く。error code は `ERROR_CANCELLATION_LOGGING.md` か `CONFIGURATION_AND_RESOURCES.md` のどちらかに表を置き、全仕様から参照する。

### RC-008: GUI と core の境界で `GuiLogSink` の配置が曖昧である

- **重要度**: Major
- **対象**: `LOGGING_FRAMEWORK.md`, `OBSERVABILITY_AND_GUI_CLI.md`
- **位置**:
  - `LOGGING_FRAMEWORK.md` `GuiLogSink`
  - `OBSERVABILITY_AND_GUI_CLI.md` `core 層は Qt 型へ依存しない`
- **指摘**: core 層が Qt 型へ依存しない方針は明確だが、`GuiLogSink` が core の sink 実装なのか、GUI 層の adapter なのかが読み取りにくい。callback 登録・配信・Qt Signal emit のスレッドも未定義である。
- **修正案**: `GuiLogSink` は `src\nyxpy\gui\` 配下に置く `LogSink` 実装であり、core は `LogSink` Protocol / ABC だけを知る、と明記する。配信スレッド、例外時の sink 隔離、Qt Signal への変換タイミングをシーケンス図にする。

### RC-009: settings lookup と Resource File I/O の責務境界は明記されているが、Builder の所有権が曖昧である

- **重要度**: Major
- **対象**: `CONFIGURATION_AND_RESOURCES.md`, `RESOURCE_FILE_IO.md`, `RUNTIME_AND_IO_PORTS.md`, `IMPLEMENTATION_PLAN.md`
- **位置**:
  - `RESOURCE_FILE_IO.md` `Resource Store は settings ファイルを探索しない`
  - `CONFIGURATION_AND_RESOURCES.md` `MacroSettingsResolver`
  - `RUNTIME_AND_IO_PORTS.md` `runtime builder`
- **指摘**: settings lookup は `MacroSettingsResolver`、画像・成果物 I/O は Resource File I/O という方向は正しい。ただし `src\nyxpy\framework\core\runtime\builder.py` をどの仕様が所有するか、GUI/CLI が settings をどこへ問い合わせるかが明確でない。
- **修正案**: `MacroRuntimeBuilder` の正本を `RUNTIME_AND_IO_PORTS.md` に置く。`CONFIGURATION_AND_RESOURCES.md` は settings の読み込み結果を提供するだけ、`RESOURCE_FILE_IO.md` は `MacroResourceScope` と Store だけを提供する、と分ける。GUI/CLI の settings 解決フローを以下の順に固定する。

```text
GUI/CLI
  -> MacroRegistry.resolve(macro_id)
  -> MacroSettingsResolver.load(descriptor)
  -> MacroResourceScope.from_descriptor(descriptor)
  -> MacroRuntimeBuilder.build(...)
```

### RC-010: Port インターフェースの未定義部分が実装分岐を生む

- **重要度**: Major
- **対象**: `RUNTIME_AND_IO_PORTS.md`, `TEST_STRATEGY.md`
- **位置**:
  - `ControllerOutputPort`
  - `FrameSourcePort.await_ready()`
  - `DefaultCommand(CommandFacade)`
  - `Port close / cleanup_warnings`
- **指摘**: `ControllerOutputPort.press()` は `dur` / `wait` を持たないが、`CommandFacade.press()` は互換のために `dur` / `wait` を持つ。変換責務が `CommandFacade` にあることは推測できるが、実装手順が不足している。`DefaultCommand(context=..., serial_device=...)` の両指定時の優先度、`FrameSourcePort.latest_frame()` の返却サイズ、close 失敗時の warning 蓄積ルールも不足している。
- **修正案**: `RUNTIME_AND_IO_PORTS.md` の内部設計に以下を追加する。
  - `CommandFacade.press()` は `controller.press -> wait(dur) -> controller.release -> wait(wait)` に変換する。
  - `context` 指定時は旧引数を無視するのか、例外にするのかを決める。
  - `FrameSourcePort.await_ready()` の timeout 時戻り値と例外送出有無を固定する。
  - 複数 Port close 失敗は `cleanup_warnings: tuple[str, ...]` に全件保持し、`RunResult.status` は変えない。

### RC-011: スレッド安全性とロック戦略が設計方針止まりである

- **重要度**: Major
- **対象**: `FW_REARCHITECTURE_OVERVIEW.md`, `RUNTIME_AND_IO_PORTS.md`, `MACRO_COMPATIBILITY_AND_REGISTRY.md`, `TEST_STRATEGY.md`
- **位置**:
  - `MacroRegistry.reload()` と run の排他
  - `RunHandle.cancel()` と `result()`
  - `FrameSourcePort.latest_frame()`
  - logging sink snapshot
- **指摘**: 排他が必要な箇所は列挙されているが、使用する lock、取得順、timeout、deadlock 検出、実行開始済みマクロへの影響が定義されていない。
- **修正案**: lock policy を表にする。例: `registry_reload_lock`, `run_start_lock`, `frame_lock`, `sink_lock` について、保護対象、取得順、timeout、timeout 例外、テスト名を記載する。

### RC-012: 性能目標はあるが測定方法が不足している

- **重要度**: Major
- **対象**: `FW_REARCHITECTURE_OVERVIEW.md`, `RUNTIME_AND_IO_PORTS.md`, `ERROR_CANCELLATION_LOGGING.md`, `RESOURCE_FILE_IO.md`, `OBSERVABILITY_AND_GUI_CLI.md`
- **位置**:
  - `Command` 追加待機時間
  - `RunHandle.cancel()` から `RunResult.cancelled`
  - `GUI` 状態更新 500 ms
  - path guard 解決
  - frame readiness
- **指摘**: 「50 ms 周期」「100 ms 以下」「500 ms 未満」「2 ms 未満」などの値はあるが、測定点、測定環境、許容誤差、CI で失敗させるか警告にするかが未定義である。
- **修正案**: `TEST_STRATEGY.md` に測定ルールを追加する。`time.perf_counter()` の wall clock、試行回数、P95 判定、CI での扱い、実機不要の性能テストと実機必須テストの切り分けを明記する。

### RC-013: テスト種別と配置ルールの粒度が不足している

- **重要度**: Major
- **対象**: `TEST_STRATEGY.md`, 各仕様書の `## 5. テスト方針`
- **位置**:
  - `tests\gui\`
  - `tests\integration\`
  - `tests\perf\`
  - `@pytest.mark.realdevice`
- **指摘**: GUI 統合、CLI 統合、性能、実機の分類が文書ごとに異なる。性能テストが必ず実機を使うとは限らず、GUI テストは `tests\gui\` と `tests\integration\` の境界が必要である。
- **修正案**: `TEST_STRATEGY.md` に配置ルールを固定し、各仕様のテスト表はその分類だけを使う。

| 種別 | 配置 | マーカー | 用途 |
|---|---|---|---|
| ユニット | `tests\unit\` | なし | 単一コンポーネント、実機不要 |
| 結合 | `tests\integration\` | なし | CLI 入口、Runtime + fake Ports など |
| GUI | `tests\gui\` | なし | pytest-qt を使う GUI adapter / widget |
| 性能 | `tests\perf\` | `@pytest.mark.perf` | 実機不要の時間要件 |
| ハードウェア | `tests\hardware\` | `@pytest.mark.realdevice` | 実機必須 |

### RC-014: 「破壊的変更なし」の表現が強すぎる

- **重要度**: Major
- **対象**: 複数文書のヘッダ
- **位置**: `> **破壊的変更**: なし`
- **指摘**: 既存マクロの import/signature 互換を維持する方針は妥当である。ただし settings path、成果物保存先、GUI/CLI 内部入口、`MacroExecutor`、singleton 直接利用、dummy fallback などは変更を含むため、「破壊的変更なし」とだけ書くと実装者が削除対象や移行対象を見落としやすい。
- **修正案**: 「既存ユーザーマクロの公開互換契約に対する破壊的変更なし。ただし `MacroExecutor`、GUI/CLI 内部入口、singleton 直接利用、暗黙 fallback は互換維持せず削除または新 API へ置換する」と表現を分ける。

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
| 1 | 正とする文書の所有権表を追加する | Overview |
| 2 | `MacroExecutor` を削除方針へ統一し、互換維持・adapter・非推奨期間の文言を削除する | Deprecation, Implementation Plan, Test Strategy |
| 3 | `MacroManifest` / `MacroDescriptor` / `MacroDefinition` の統合または廃止を決める | Macro Compatibility, Overview |
| 4 | `ExecutionContext` / `RunResult` / `RunLogContext` の単一定義を決める | Runtime, Error/Cancellation, Logging |
| 5 | GUI/CLI cancel API を `RunHandle.cancel()` に統一し、`Command.stop()` の例外送出要否を再検討する | Error/Cancellation, Observability, Runtime |
| 6 | logging event catalog と error code catalog を作る | Logging, Error/Cancellation |
| 7 | settings / resource / runtime builder の責務境界をフロー図にする | Configuration, Resource, Runtime |
| 8 | Port 契約の未定義部分を型・戻り値・例外で固定する | Runtime |
| 9 | テスト分類と性能測定方法を `TEST_STRATEGY.md` に集約する | Test Strategy |
