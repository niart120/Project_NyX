# rearchitecture 仕様書群レビューコメント

> **レビュー対象**: `spec\framework\rearchitecture\*.md` の 13 文書
> **レビュー観点**: framework-spec-writing 形式要件、文書間整合性、互換・廃止方針、実装順序、テストゲート

## 総評

対象文書はいずれも `## 1. 概要` から `## 6. 実装チェックリスト` までの 6 セクションを備え、用語定義・期待効果・対象ファイル・テスト方針も表形式で整理されている。未確定プレースホルダも検出されなかった。

主なリスクは形式ではなく、複数文書で同じ判断を再記述している箇所のずれである。特に破壊的変更、`LogManager` 廃止、`Command.stop()` の意味論、テストファイル名は実装前に揃える必要がある。

## 指摘一覧

| ID | 重要度 | 分類 | 要約 |
|----|--------|------|------|
| R-001 | 高 | 互換・廃止 | 破壊的変更の範囲が文書ごとに微妙に異なる |
| R-002 | 高 | 互換・移行 | `LogManager` / `log_manager.log()` の即削除方針が公開面の扱いとして未整理 |
| R-003 | 高 | 互換・実装 | `Command.stop()` の意味論について「挙動を保つ」と「即時例外を送出しない」が併存する |
| R-004 | 高 | 互換・実装 | `DefaultCommand` 旧コンストラクタ削除の影響範囲がテスト・内部利用まで落ちていない |
| R-005 | 中 | API 表現 | `RunResult.cancelled` と `RunStatus.CANCELLED` の表記が混在する |
| R-006 | 中 | 図版・命名 | 図版で `NotificationHandlerPort` が Port 名のように見える |
| R-007 | 中 | ログ仕様 | event catalog の正本と発行タイミング表の役割が重複気味である |
| R-008 | 中 | テスト計画 | テストファイル名が文書間で一致していない |

## 詳細コメント

### R-001 破壊的変更の範囲が文書ごとに微妙に異なる

**重要度**: 高
**対象**: `FW_REARCHITECTURE_OVERVIEW.md:8`, `IMPLEMENTATION_PLAN.md:7`, `TEST_STRATEGY.md:7`, `DEPRECATION_AND_MIGRATION.md:7`, `RESOURCE_FILE_IO.md:7`, `LOGGING_FRAMEWORK.md:7`, `OBSERVABILITY_AND_GUI_CLI.md:6`

各文書のヘッダで破壊的変更を個別に列挙しているが、対象語が揃っていない。例として Overview は `legacy loader` を挙げ、Implementation Plan / Test Strategy は `旧 auto discovery`、`MacroExecutor`、`GUI/CLI 内部入口`、`singleton 直接利用`、`暗黙 fallback` まで列挙している。Resource / Logging / Observability は各領域に限定した破壊的変更を書いている。

このままだと、実装者が「全体方針」と「領域別方針」のどちらを削除判断の正本にするか迷う。`DEPRECATION_AND_MIGRATION.md` は削除対象・廃止候補の正本と明記しているため、各文書のヘッダは詳細列挙をやめ、次のように役割を分けるとよい。

| 文書 | 推奨する役割 |
|------|--------------|
| `FW_REARCHITECTURE_OVERVIEW.md` | 維持する互換契約と、破壊的変更の大分類だけを書く |
| `DEPRECATION_AND_MIGRATION.md` | 削除対象、代替 API、削除条件、テストゲートの正本にする |
| その他の個別仕様 | 「本領域で影響する破壊的変更は該当 ID を参照」の形で参照に寄せる |

### R-002 `LogManager` / `log_manager.log()` の即削除方針が公開面の扱いとして未整理

**重要度**: 高
**対象**: `README.md:19`, `LOGGING_FRAMEWORK.md:112-116`, `LOGGING_FRAMEWORK.md:368-370`, `IMPLEMENTATION_PLAN.md:307-318`, `ERROR_CANCELLATION_LOGGING.md:509-511`

README は `LogManager` を主要機能として記載している。一方で Logging 仕様は旧 `log_manager` グローバル、`LogManager.log()`、旧 handler API を互換維持対象に含めず、`LegacyStringSink` や互換 adapter も作らない方針である。Implementation Plan もフェーズ 7 の完了条件として `LogManager` と旧 `log_manager.log()` 互換 adapter を残さないとしている。

この方針自体はあり得るが、現在の文書では `LogManager` が公開 API なのか内部実装なのかの判定が足りない。既存コードにも `log_manager.log()` の呼び出し、`LogManager` の単体テスト、GUI / CLI の handler 利用が残っているため、削除前に呼び出し元置換ゲートを明記した方が安全である。

修正案:

1. `LOGGING_FRAMEWORK.md` に「旧 API の公開性判定」を追加し、`LogManager` を公開 API とみなすか内部 API とみなすかを明記する。
2. 公開 API とみなす場合は、`warnings.warn(..., DeprecationWarning)` を出す短期 shim を 1 段階だけ置くか、即削除する理由と対象リリースを明記する。
3. 内部 API とみなす場合でも、`src\nyxpy\gui\main_window.py`、`src\nyxpy\cli\run_cli.py`、`src\nyxpy\framework\core\hardware\capture.py`、通知実装、既存 logger テストの置換完了をフェーズ 7 の完了条件に含める。

### R-003 `Command.stop()` の意味論について「挙動を保つ」と「即時例外を送出しない」が併存する

**重要度**: 高
**対象**: `FW_REARCHITECTURE_OVERVIEW.md:38`, `FW_REARCHITECTURE_OVERVIEW.md:215`, `FW_REARCHITECTURE_OVERVIEW.md:279`, `ERROR_CANCELLATION_LOGGING.md:71`, `ERROR_CANCELLATION_LOGGING.md:384-392`, `MACRO_MIGRATION_GUIDE.md:266-280`, `RUNTIME_AND_IO_PORTS.md:179`, `RUNTIME_AND_IO_PORTS.md:554`

多くの箇所では、再設計後の `Command.stop()` は停止要求だけを登録し、即時 `MacroStopException` を送出しないと定義している。一方で Overview の並行性節に「中断は `CancellationToken` を経由し、既存 `cmd.stop()` の挙動を保つ」とあり、旧挙動を維持するように読める。

これはマクロ移行時の判断に直結する。旧 `cmd.stop()` を例外送出として使っていたマクロは、safe point へ寄せる必要があるため、「メソッド名は維持するが意味論は破壊的変更」と明確に統一するべきである。

修正案:

- `FW_REARCHITECTURE_OVERVIEW.md:279` の「既存 `cmd.stop()` の挙動を保つ」を「既存 `cmd.stop()` の呼び出し可能性は保つが、即時例外送出の意味論は維持しない」に変更する。
- `Command.stop()` に関する受け入れテストを `ERROR_CANCELLATION_LOGGING.md` のテスト名に合わせ、`test_command_stop_requests_cancel_without_raising` と `test_command_stop_rejects_raise_immediately_argument` を正本として扱う。

### R-004 `DefaultCommand` 旧コンストラクタ削除の影響範囲がテスト・内部利用まで落ちていない

**重要度**: 高
**対象**: `FW_REARCHITECTURE_OVERVIEW.md:22`, `RUNTIME_AND_IO_PORTS.md:169-175`, `IMPLEMENTATION_PLAN.md:86`, `IMPLEMENTATION_PLAN.md:268-279`, `MACRO_MIGRATION_GUIDE.md:121-125`

`DefaultCommand` の import path は維持しつつ、旧コンストラクタ引数は受け付けず `DefaultCommand(context=execution_context)` のみにする方針である。Migration Guide では通常マクロは `DefaultCommand` を直接生成しないと説明しているが、現行テストと GUI / CLI / perf には旧コンストラクタ利用がある。

この削除は妥当でも、実装計画上は「ユーザーマクロには影響しない」だけでは足りない。内部テスト、GUI/CLI、性能計測、既存結合テストの移行順が明示されないと、フェーズ 5 で広範囲の失敗が同時に出る。

修正案:

| 追加すべき観点 | 内容 |
|----------------|------|
| 旧コンストラクタ利用棚卸し | `tests\unit\command\test_default_command.py`、`tests\perf\test_command_perf.py`、`tests\integration\test_dummy_macro_integration.py`、GUI / CLI の構築箇所を対象に含める |
| 置換順 | fake `ExecutionContext` fixture を先に作り、`DefaultCommand(context=...)` へテストを段階移行する |
| 失敗検出 | `test_default_command_old_constructor_removed` または既存の `test_command_stop_rejects_raise_immediately_argument` と同じ層で、旧引数を受け付けないことを明示する |
| 移行ガイド | マクロ作者向けだけでなく、テスト・adapter 作者向けに `ExecutionContext` の最小 fixture 例を追加する |

### R-005 `RunResult.cancelled` と `RunStatus.CANCELLED` の表記が混在する

**重要度**: 中
**対象**: `RUNTIME_AND_IO_PORTS.md:211`, `RUNTIME_AND_IO_PORTS.md:323-338`, `TEST_STRATEGY.md:176-177`, `TEST_STRATEGY.md:261`, `ERROR_CANCELLATION_LOGGING.md:382`

`RunResult` の公開インターフェースでは `status: RunStatus`、`ok`、`duration_seconds` だけが定義されている。一方で性能要件やテスト方針には `RunResult.cancelled`、`cancelled result` という表現がある。

単なる説明語としては読めるが、実装者が `RunResult.cancelled` プロパティを追加すべきか、`result.status == RunStatus.CANCELLED` のみを使うべきか判断しづらい。

修正案:

- `RunResult.cancelled` プロパティを公開 API に追加しないなら、全文書で `result.status == RunStatus.CANCELLED` に統一する。
- 追加するなら `RUNTIME_AND_IO_PORTS.md` の `RunResult` dataclass に `cancelled` property を明示し、`TEST_STRATEGY.md` の判定式もそれに揃える。

### R-006 図版で `NotificationHandlerPort` が Port 名のように見える

**重要度**: 中
**対象**: `ARCHITECTURE_DIAGRAMS.md:146`, `ARCHITECTURE_DIAGRAMS.md:154`, `ARCHITECTURE_DIAGRAMS.md:274`, `ARCHITECTURE_DIAGRAMS.md:286`, `ARCHITECTURE_DIAGRAMS.md:317-328`

本文仕様では Runtime が依存する抽象は `NotificationPort` である。一方、図版では adapter 側に `NotificationHandlerPort` / `NoopNotificationPort` が出てくる。`NotificationHandlerPort` は抽象 Port の別名にも adapter 名にも見えるため、Port と Adapter の境界がぼやける。

修正案:

- 抽象は `NotificationPort` に統一する。
- 具象 adapter は `NotificationHandlerAdapter`、`NoopNotificationAdapter` のように `Adapter` 接尾辞へ寄せる。
- 図の凡例で「Port は Protocol / ABC、Adapter は現行実装への接続」と明記する。

### R-007 event catalog の正本と発行タイミング表の役割が重複気味である

**重要度**: 中
**対象**: `LOGGING_FRAMEWORK.md:351-366`, `ERROR_CANCELLATION_LOGGING.md:481-492`

Logging 仕様は Event catalog を正本とし、他仕様は event の発行タイミングだけを定義すると明記している。Error / Cancellation 仕様も同じ event 名を発行タイミング表で列挙しており、現時点では一致している。ただし今後 event 名を追加・変更する際に、どちらかだけ更新されるリスクがある。

修正案:

- `ERROR_CANCELLATION_LOGGING.md` の表は event 名を再定義せず、`LOGGING_FRAMEWORK.md` の event catalog の ID を参照する形にする。
- 追加 event は必ず `LOGGING_FRAMEWORK.md` の catalog に先に足す、というルールを `IMPLEMENTATION_PLAN.md` のフェーズ 7 完了条件に含める。

### R-008 テストファイル名が文書間で一致していない

**重要度**: 中
**対象**: `TEST_STRATEGY.md:70`, `IMPLEMENTATION_PLAN.md:80`, `IMPLEMENTATION_PLAN.md:212-214`, `IMPLEMENTATION_PLAN.md:299`, `RESOURCE_FILE_IO.md:70`, `DEPRECATION_AND_MIGRATION.md:71`

同じ意図のテストファイル名が文書間で揺れている。

| 対象 | 表記 A | 表記 B |
|------|--------|--------|
| 移行後マクロ互換テスト | `tests\integration\test_migrated_macro_compat.py` | `tests\integration\test_migrated_macros_compat.py` |
| Resource File I/O 結合テスト | `tests\integration\test_resource_file_io_migration.py` | `tests\integration\test_resource_file_io_compat.py` |

実装時にどちらのファイル名で作るか迷うため、`TEST_STRATEGY.md` を正本にするか、`IMPLEMENTATION_PLAN.md` を正本にするか決めて統一するべきである。テスト名はコマンド例にも使われているため、ファイル名を変える場合は実行コマンドも同時に更新する。

## 優先修正順

| 順位 | 対象 |
|------|------|
| 1 | R-001, R-003: 互換・破壊的変更の意味を先に固定する |
| 2 | R-002, R-004: 削除対象の呼び出し元移行ゲートを実装計画へ反映する |
| 3 | R-005, R-008: API 表記とテスト名を統一し、実装時の迷いを減らす |
| 4 | R-006, R-007: 図版とログ event の正本関係を整理する |
