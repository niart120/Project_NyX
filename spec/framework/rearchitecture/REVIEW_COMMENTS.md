# フレームワーク再設計ドキュメント群 レビューコメント

> **対象**: `spec\framework\rearchitecture\*.md`
> **レビュー日**: 2026-05-06
> **観点**: フレームワーク仕様書テンプレート準拠、正本ドキュメントの一貫性、既存 API 互換、依存方向、テスト可能性

## 総評

再設計の主要方針は、おおむね一貫している。特に `MacroBase` / `Command` / `DefaultCommand` / constants / `MacroStopException` の import と lifecycle を維持し、`MacroExecutor`、旧 settings lookup、旧 Resource I/O、暗黙 fallback を互換対象から外す境界は複数文書で明確に繰り返されている。

実装前に直すべき点は、API 互換の細部と正本ドキュメントの所有範囲である。下記 P1 は、実装者が異なる解釈でコードを書ける状態になっているため、Phase 1 着手前に修正することを推奨する。

## 優先度定義

| 優先度 | 意味 |
|--------|------|
| P1 | 実装前に修正が必要。互換性、API 仕様、責務境界に影響する |
| P2 | 仕様確定前に修正が必要。誤読やテスト漏れの原因になる |
| P3 | 表記、導線、テンプレート準拠の改善 |

## 対応状況

| ID | 状況 | 理由 |
|----|------|------|
| R-01 | 対応済み | `Command.log()` の既定 `level` は `DEBUG` に統一 |
| R-02 | 対応済み | `MACRO_COMPATIBILITY_AND_REGISTRY.md` の正本範囲を registry / metadata / `settings_path` に限定 |
| R-03 | 対応済み | `MacroExecutor` を `Compatibility Layer` から `Legacy removal target` へ移動 |
| R-04 | 対応済み | `Command.type()` は `KeyCode` / `SpecialKeyCode` 専用 API とし、`str` は受けない方針に統一 |
| R-05 | 対応済み | `RUNTIME_AND_IO_PORTS.md` の関連ドキュメントを追加 |
| R-06 | 対応済み | `MACRO_MIGRATION_GUIDE.md` に `### 4.1 公開インターフェース` を追加し、枝番を解消 |
| R-07 | 対応済み | `ERROR_CANCELLATION_LOGGING.md` に `### 設定パラメータ` と正本参照を追加 |
| R-08 | 対応済み | 仕様チェックリストと実装チェックリストをサブ見出しで分離 |
| R-09 | 対応済み | `FW_REARCHITECTURE_OVERVIEW.md` に共通のパス表記規則を追加 |

## レビューコメント

| ID | 優先度 | 対象 | コメント | 修正案 |
|----|--------|------|----------|--------|
| R-01 | P1 | `Command.log()` | `Command.log()` の既定 `level` が文書間で `DEBUG` と `INFO` に割れていた。 | `DEBUG` を正とし、仕様書と現行 `DefaultCommand.log()` の既定値を統一済み。互換テストでは `test_command_log_default_level_is_debug` で固定する。 |
| R-02 | P1 | settings lookup の正本 | `FW_REARCHITECTURE_OVERVIEW.md:103` と `CONFIGURATION_AND_RESOURCES.md:3` は settings lookup / `MacroSettingsResolver` の正本を `CONFIGURATION_AND_RESOURCES.md` としている。一方で `MACRO_COMPATIBILITY_AND_REGISTRY.md:3` は「settings lookup の正本」と書いており、所有範囲が競合している。 | `MACRO_COMPATIBILITY_AND_REGISTRY.md` の文書種別を「manifest / class metadata / convention discovery と `MacroDefinition.settings_path` の正本」に限定し、settings lookup の解決規則は `CONFIGURATION_AND_RESOURCES.md` 参照へ寄せる。Overview の正本表と同じ言い回しにする。 |
| R-03 | P1 | `ARCHITECTURE_DIAGRAMS.md` | 全体図の subgraph 名が `Compatibility Layer<br/>破壊不可 import contract` であるにもかかわらず、その中に `MacroExecutor<br/>(legacy entrypoint)` が含まれている（`ARCHITECTURE_DIAGRAMS.md:120`-`:126`）。本文では `MacroExecutor` は互換契約に含めないと明記されているため、図だけを見ると破壊不可対象に見える。 | `MacroExecutor` を `Legacy removal target` など別 subgraph へ移動し、破線で Runtime への一時委譲を示す。`Compatibility Layer` 内は `MacroBase` / `Command` / `DefaultCommand` / constants / `MacroStopException` に限定する。 |
| R-04 | P1 | `Command.type()` | `Command.type()` が `str` を受けるか、`KeyCode` / `SpecialKeyCode` 専用 API とするかが文書間で曖昧だった。 | `Command.type(key: KeyCode \| SpecialKeyCode)` を正とし、文字列入力は `Command.keyboard(text: str)` に限定する。互換テストでは `test_command_type_accepts_keycode_special_keycode_only` で固定する。 |
| R-05 | P2 | `RUNTIME_AND_IO_PORTS.md` の関連文書 | `RUNTIME_AND_IO_PORTS.md:6` の関連ドキュメントは `CONFIGURATION_AND_RESOURCES.md` と `RESOURCE_FILE_IO.md` だけだが、本文は `LOGGING_FRAMEWORK.md` の `LoggerPort` / `RunLogContext`、`ERROR_CANCELLATION_LOGGING.md` の `ErrorInfo` / `MacroCancelled`、`OBSERVABILITY_AND_GUI_CLI.md` の GUI/CLI 入口を前提にしている。 | 関連ドキュメントへ `LOGGING_FRAMEWORK.md`, `ERROR_CANCELLATION_LOGGING.md`, `OBSERVABILITY_AND_GUI_CLI.md`, `TEST_STRATEGY.md` を追加する。正本の所在は `FW_REARCHITECTURE_OVERVIEW.md:96`-`:107` と同じにする。 |
| R-06 | P2 | `MACRO_MIGRATION_GUIDE.md` | 移行ガイドは `## 4. 実装仕様` 配下に `### 公開インターフェース` がない。仕様書テンプレートのレビュー観点では「公開 API のシグネチャが Python コードブロックで記載されているか」を確認対象にしているため、自動検査や人手レビューで例外扱いが必要になる。 | `### 4.1 公開インターフェース` を追加し、「新 API の正本は各仕様、移行ガイドは呼び出し側の変更例を示す」と明記する。以降の番号を繰り下げるか、`4.1A` のような枝番を避けて通常の連番へ整理する。 |
| R-07 | P2 | `ERROR_CANCELLATION_LOGGING.md` | `SettingsStore / SecretsStore schema` の表はあるが、テンプレート上の `### 設定パラメータ` 見出しが存在しない（`ERROR_CANCELLATION_LOGGING.md:409`-`:431`）。設定仕様の正本は `CONFIGURATION_AND_RESOURCES.md` のため、ここに詳細表を置くと重複更新が必要になる。 | 本書では `### 設定パラメータ` を置いたうえで「正本は `CONFIGURATION_AND_RESOURCES.md`」とし、必要最小限の参照表にする。詳細な schema 表は設定仕様へ集約する。 |
| R-08 | P2 | checklist の意味 | `MACRO_COMPATIBILITY_AND_REGISTRY.md:498`-`:514` は「仕様確定項目」として `[x]` を使い、`TEST_STRATEGY.md:365`-`:379` や `LOGGING_FRAMEWORK.md:452`-`:474` は実装タスクとして `[ ]` を使っている。文書ごとに「実装チェックリスト」の意味が異なるため、進捗管理時に完了状態を誤読しやすい。 | `## 6. 実装チェックリスト` は実装・検証タスクに統一する。仕様執筆済み項目は `## 6.1 仕様チェックリスト` など別見出しに分ける。 |
| R-09 | P3 | ファイルパス表記 | 文書内で `src\...` と `src/...` が混在している。Markdown リンクは `/`、Windows 配置例は `\`、永続化する TOML path は `/` という方針自体は `MACRO_MIGRATION_GUIDE.md:97` で定義されているが、全体に適用されていない。 | 冒頭の Overview または Migration Guide に「Markdown リンクは `/`、Windows 配置例は `\`、設定ファイル内 path は `/`」を共通規則として置き、対象ファイル表の表記を揃える。 |

## 良い点

| 観点 | コメント |
|------|----------|
| 必須 6 セクション | 対象 13 文書はいずれも `## 1. 概要` から `## 6. 実装チェックリスト` までを持っている。 |
| 正本表 | `FW_REARCHITECTURE_OVERVIEW.md` の「1.6 仕様依存関係」は、分割仕様の読み順と更新責任を追いやすい。 |
| 互換境界 | `MacroExecutor` を互換対象から外しつつ、既存マクロの import / lifecycle を守る方針は明確である。 |
| テスト戦略 | `TEST_STRATEGY.md` は unit / integration / gui / hardware / perf の分離と `@pytest.mark.realdevice` の扱いを具体化している。 |

## 修正順の提案

1. `Command.log()` の既定 `level=DEBUG` を現行コードと互換テストへ反映する。
2. `Command.type()` の `KeyCode | SpecialKeyCode` 専用 API を互換テストで固定し、文字列入力は `Command.keyboard(text)` 側で扱う。
