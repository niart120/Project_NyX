# Dev Journal

実装中の設計上の気づき・疑問・バックログ送りタスクの記録。

## 2026-05-17: コマンド詳細ログの出力量とログ分類の見直し

### 現状

`src/nyxpy/framework/core/macro/command.py` の組み込みDEBUGログが `command.log` として出力され、`logs/framework.jsonl(.1)` と `logs/nyxpy.log(.1)` では `Capture successful`、`Capturing screen...`、`Waiting for 0.017 seconds` が多数を占めていた。

### 観察

`src/nyxpy/framework/core/logger/default_logger.py` でユーザーイベントを技術ログへ複製していたため、GUIのツールログにもマクロ由来のDEBUGログが混入し、ログファイルの肥大化にもつながっていた。

### 方針

ユーザーイベントと技術ログの保存先を分離し、コマンド詳細DEBUGログは `logging.command_debug_enabled` で制御する。ログとして何を残すかの粒度、長時間実行時のキャプチャ・待機ログの要否、複数プロセス同時書き込み時のローテーション安全性は別途見直す。
