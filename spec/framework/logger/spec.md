# ロギングフレームワーク仕様書

> **対象モジュール**: `src\nyxpy\framework\core\logger\`
> **目的**: ユーザー表示イベント、技術ログ、実行ログ、GUI 表示を分離し、ログファイルの肥大化を抑制できるロギング基盤を定義する。
> **関連ドキュメント**: `spec\framework\rearchitecture\LOGGING_FRAMEWORK.md`, `spec\framework\archive\logging_design.md`, `spec\dev-journal.md`
> **既存ソース**: `src\nyxpy\framework\core\logger\`, `src\nyxpy\framework\core\macro\command.py`, `src\nyxpy\framework\core\runtime\builder.py`
> **破壊的変更**: あり。`UserEvent` を `TechnicalLog` として自動複製しない。

## 1. 概要

### 1.1 目的

ロギングフレームワークは、障害調査に使う技術ログと、マクロ利用者へ表示するユーザーイベントを別経路で扱う。ログファイルはサイズと保持期間で有界化し、頻出するコマンド詳細 DEBUG ログは設定で明示的に有効化された場合だけ出力する。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| LoggerPort | Runtime、Command、通知、設定処理から使うロギング抽象 |
| DefaultLogger | `LoggerPort` の標準実装。`UserEvent` と `TechnicalLog` を生成し、sink/backend へ配送する |
| UserEvent | GUI/CLI と実行単位ログへ残すユーザー向けイベント。traceback は持たない |
| TechnicalLog | 障害調査とフレームワーク診断に使う技術ログ。例外型と traceback を保持できる |
| LogSinkDispatcher | sink の登録、解除、レベルフィルタ、例外隔離を担当する配送器 |
| JsonlLogBackend | `framework.jsonl` へ技術ログだけを書き込む backend |
| TextFileLogSink | `nyxpy.log` へユーザーイベントと技術ログを人間向け形式で書き込む sink |
| RunJsonlFileSink | `runs\<yyyymmdd>\<run_id>.jsonl` へ実行単位のイベントを書き込む sink |
| RotationPolicy | ログファイルのサイズ上限、バックアップ数、保持日数を表す値 |
| command_debug_enabled | `DefaultCommand` が内部的に出す press/wait/capture 等の DEBUG ログを有効化する設定 |

### 1.3 背景・問題

`DefaultCommand` は `press`、`wait`、`capture` などの高頻度操作を `command.log` の DEBUG イベントとして出力していた。`DefaultLogger.user()` がユーザーイベントを技術ログへ複製していたため、これらのログは `framework.jsonl` と GUI のツールログにも流入し、長時間実行時にログファイルを圧迫していた。

既存のローテーションは現行ファイルと `.1` だけを扱う方式で、保持できる履歴数と最大容量が設定として明確ではなかった。実行単位ログにもサイズ上限がなく、長時間のマクロ実行で 1 ファイルが肥大化する余地があった。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| ユーザーイベントの技術ログ混入 | `UserEvent` を `TechnicalLog` へ自動複製 | 自動複製しない |
| コマンド詳細 DEBUG ログ | 既定で出力 | 既定で抑制 |
| メインログのローテーション | 現行 + `.1` | 現行 + `backup_count` 世代 |
| 実行単位ログのサイズ制御 | サイズ上限なし | `file_max_bytes` 到達時に世代ローテーション |
| GUI ツールログ | マクロ由来 DEBUG が表示され得る | 技術ログだけを表示 |

### 1.5 着手条件

- `LoggerPort`、`LogSinkDispatcher`、`UserEvent`、`TechnicalLog` が実装済みである。
- Runtime が `RunLogContext` を生成し、`LoggerPort.bind_context()` でマクロ実行に紐づける。
- `GlobalSettings` が `logging.*` の設定値を検証できる。
- core 層から `nyxpy.gui` へ依存しない。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `src\nyxpy\framework\core\logger\default_logger.py` | 変更 | `UserEvent` の技術ログ自動複製を廃止 |
| `src\nyxpy\framework\core\logger\rotation.py` | 新規 | ローテーションと保持期間 cleanup を共通化 |
| `src\nyxpy\framework\core\logger\backend.py` | 変更 | `JsonlLogBackend` に有界ローテーションを適用 |
| `src\nyxpy\framework\core\logger\sinks.py` | 変更 | `TextFileLogSink` と `RunJsonlFileSink` にユーザーイベント保存と有界ローテーションを追加 |
| `src\nyxpy\framework\core\logger\factory.py` | 変更 | ローテーション設定を `create_default_logging()` へ接続 |
| `src\nyxpy\framework\core\settings\global_settings.py` | 変更 | `logging.*` の設定項目を追加 |
| `src\nyxpy\framework\core\runtime\context.py` | 変更 | `RuntimeOptions.command_debug_enabled` を追加 |
| `src\nyxpy\framework\core\runtime\builder.py` | 変更 | global / macro / metadata の設定から command debug を解決 |
| `src\nyxpy\framework\core\macro\command.py` | 変更 | 組み込み DEBUG ログを `_debug_command()` 経由で制御 |
| `src\nyxpy\gui\panes\log_pane.py` | 変更 | GUI ログ初期レベルとデバッグ表示切替を扱う |
| `src\nyxpy\gui\dialogs\settings\general_tab.py` | 変更 | 外観とログの設定グループを表示 |
| `spec\dev-journal.md` | 変更 | ログ粒度見直しのバックログを記録 |
| `tests\unit\framework\logger\test_logging_framework.py` | 変更 | ユーザーイベント分離とローテーションを検証 |
| `tests\unit\framework\runtime\test_default_command_ports.py` | 変更 | command debug の既定抑制と有効化を検証 |
| `tests\unit\framework\runtime\test_runtime_builder.py` | 変更 | command debug 設定解決を検証 |
| `tests\gui\test_log_pane_user_event.py` | 変更 | マクロ由来ユーザーイベントがツールログへ混入しないことを検証 |

## 3. 設計方針

### アーキテクチャ上の位置づけ

ロギングは Runtime、Command、通知、GUI/CLI の横断機能である。core 層は `LoggerPort` と `LogSink` の抽象だけを公開し、ファイル、標準出力、GUI 表示は composition root が組み立てる。

```text
DefaultCommand / MacroRuntime / NotificationHandler
  -> LoggerPort
  -> DefaultLogger
  -> LogSinkDispatcher
     -> TextFileLogSink
     -> RunJsonlFileSink
     -> ConsoleLogSink
     -> GUI layer: GuiLogSink
  -> JsonlLogBackend
```

`JsonlLogBackend` は技術ログ専用であり、ユーザーイベントは受け取らない。ユーザーイベントをファイルへ残す責務は sink が持つ。

### 公開 API 方針

既存の `LoggerPort.user()` と `LoggerPort.technical()` のシグネチャは維持する。ローテーションの設定は `create_default_logging()` のキーワード引数と `GlobalSettings` の `logging.*` で扱う。

`DefaultCommand.log()` はマクロ作者が明示的に出すログ API として残す。`DefaultCommand` 自身が内部的に出す DEBUG ログは `_debug_command()` 経由に限定し、`RuntimeOptions.command_debug_enabled` で制御する。

### 後方互換性

`UserEvent` を技術ログへ自動複製しない点は出力内容の破壊的変更である。`framework.jsonl` をユーザーイベントの監査ログとして読んでいた呼び出し元は、`nyxpy.log` または `runs\<yyyymmdd>\<run_id>.jsonl` を参照する。

旧挙動を復元する互換 shim は追加しない。必要なイベントは `logger.technical()` と `logger.user()` の呼び分けで明示する。

### レイヤー構成

| レイヤー | 責務 | 禁止事項 |
|----------|------|----------|
| `core\macro` | マクロ向け `Command.log()` と組み込み command debug の制御 | GUI 表示やログファイル path を扱う |
| `core\runtime` | `RuntimeOptions` と `RunLogContext` の生成 | sink/backend を直接操作する |
| `core\logger` | イベント生成、配送、永続化、ローテーション | GUI widget へ依存する |
| `core\settings` | `logging.*` の検証と永続化 | ログ配送を行う |
| `nyxpy.gui` | 設定画面とログペイン表示 | core 層へ Qt 型を持ち込む |

### 性能要件

| 指標 | 目標値 |
|------|--------|
| command debug 無効時の `DefaultCommand.press()` 追加ログ数 | 0 件 |
| `JsonlLogBackend.emit_technical()` | 1 件 5 ms 未満 |
| sink 3 件への配送 | 1 件 5 ms 未満 |
| ローテーション世代数 | `backup_count` 以下 |
| 実行ログの 1 ファイルサイズ | `file_max_bytes` 到達後に次回書き込みでローテーション |

### 並行性・スレッド安全性

`LogSinkDispatcher` は sink 登録と snapshot 取得を `RLock` で保護する。各ファイル sink と backend は書き込みとローテーションを `RLock` で保護する。

この設計は同一プロセス内の複数スレッドを対象とする。複数プロセスが同じログファイルへ同時書き込みする場合の排他は未対応であり、`spec/dev-journal.md` に再検討事項として残す。

## 4. 実装仕様

### 公開インターフェース

```python
@dataclass(frozen=True)
class RotationPolicy:
    max_bytes: int = 10 * 1024 * 1024
    backup_count: int = 3
    retention_days: int = 14


def rotate_if_needed(path: Path, policy: RotationPolicy) -> None: ...


def create_default_logging(
    *,
    base_dir: Path = Path("logs"),
    console_enabled: bool = True,
    console_level: str = "INFO",
    file_level: str = "DEBUG",
    file_max_bytes: int = 10 * 1024 * 1024,
    file_backup_count: int = 3,
    file_retention_days: int = 14,
    run_retention_days: int = 30,
    mask_secret_keys: list[str] | None = None,
) -> LoggingComponents: ...


@dataclass(frozen=True)
class RuntimeOptions:
    allow_dummy: bool = False
    device_detection_timeout_sec: float = 5.0
    frame_ready_timeout_sec: float = 3.0
    release_timeout_sec: float = 2.0
    command_debug_enabled: bool = False
```

### 設定パラメータ

| パラメータ | 型 | デフォルト | 説明 |
|------------|-----|-----------|------|
| `logging.file_level` | `str` | `"DEBUG"` | ファイル sink/backend の最小ログレベル |
| `logging.gui_level` | `str` | `"INFO"` | GUI ログペインの初期表示レベル。設定画面には出さず、パネルのチェックボックスで一時変更する |
| `logging.file_max_bytes` | `int` | `10485760` | `framework.jsonl`、`nyxpy.log`、実行ログ 1 ファイルのローテーション閾値 |
| `logging.file_backup_count` | `int` | `3` | ローテーション世代数 |
| `logging.file_retention_days` | `int` | `14` | `framework.jsonl.*` と `nyxpy.log.*` の保持日数 |
| `logging.run_retention_days` | `int` | `30` | `runs\*\*.jsonl*` の保持日数 |
| `logging.command_debug_enabled` | `bool` | `false` | `DefaultCommand` の組み込み DEBUG ログを出力するか |

`logging.command_debug_enabled` は `GlobalSettings`、マクロ設定ファイル、`RuntimeBuildRequest.metadata` の順で上書きできる。マクロ設定ファイルでは次の形式を使う。

```toml
[logging]
command_debug_enabled = true
```

### エラーハンドリング

| 例外クラス | 発生条件 |
|------------|----------|
| `ValueError` | 不正なログレベルを `normalize_level()` に渡した場合 |
| `ConfigurationError` | `GlobalSettings` が `logging.*` の型または選択肢違反を検出した場合 |
| `sink.emit_failed` 技術ログ | sink の `emit_*` / `flush` / `close` が例外を送出した場合 |
| `backend.emit_failed` 技術ログ | backend の技術ログ書き込みが例外を送出した場合 |

### シングルトン管理

新規 singleton は追加しない。`LoggingComponents` は GUI/CLI の composition root が所有し、終了時に `close()` する。

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| ユニット | `test_default_logging_writes_user_events_to_user_sinks_only` | `UserEvent` が `framework.jsonl` へ複製されず、`nyxpy.log` と run JSONL へ残る |
| ユニット | `test_jsonl_backend_keeps_bounded_rotated_files` | `JsonlLogBackend` が `backup_count` を超える世代を残さない |
| ユニット | `test_run_jsonl_sink_rotates_per_run_file` | 実行単位 JSONL がサイズ閾値でローテーションする |
| ユニット | `test_default_command_suppresses_builtin_debug_logs_by_default` | command debug 無効時に組み込み DEBUG ログを出さない |
| ユニット | `test_default_command_emits_builtin_debug_logs_when_enabled` | command debug 有効時に組み込み DEBUG ログを出す |
| ユニット | `test_runtime_builder_uses_global_command_debug_setting` | global 設定から `RuntimeOptions` へ反映される |
| ユニット | `test_runtime_builder_allows_macro_command_debug_override` | マクロ設定で command debug を上書きできる |
| GUI | `test_macro_user_debug_is_not_mirrored_to_tool_log` | マクロ由来ユーザーイベントがツールログへ表示されない |
| パフォーマンス | `test_log_handler_dispatch_thread_safety` | sink 配送が既存の性能閾値内に収まる |

## 6. 実装チェックリスト

- [x] 公開 API のシグネチャ確定
- [x] ユーザーイベントと技術ログの保存先分離
- [x] ローテーション共通処理の実装
- [x] `DefaultCommand` 組み込み DEBUG ログの設定化
- [x] `GlobalSettings` への `logging.*` 追加
- [x] GUI 設定画面のログ項目整理
- [x] ユニットテスト作成・パス
- [x] GUI テスト作成・パス
- [x] 型ヒントの整合性チェック（ruff）
