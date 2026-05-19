# Dev Journal

実装中の設計上の気づき・疑問・バックログ送りタスクの記録。

## 2026-05-17: コマンド詳細ログの出力量とログ分類の見直し

### 現状

`src/nyxpy/framework/core/macro/command.py` の組み込みDEBUGログが `command.log` として出力され、`logs/framework.jsonl(.1)` と `logs/nyxpy.log(.1)` では `Capture successful`、`Capturing screen...`、`Waiting for 0.017 seconds` が多数を占めていた。

### 観察

`src/nyxpy/framework/core/logger/default_logger.py` でユーザーイベントを技術ログへ複製していたため、GUIのツールログにもマクロ由来のDEBUGログが混入し、ログファイルの肥大化にもつながっていた。

### 方針

ユーザーイベントと技術ログの保存先を分離し、コマンド詳細DEBUGログは `logging.command_debug_enabled` で制御する。ログとして何を残すかの粒度、長時間実行時のキャプチャ・待機ログの要否、複数プロセス同時書き込み時のローテーション安全性は別途見直す。

## 2026-05-17: マクロ一覧表示の階層化と検索切替

### 現状

`src/nyxpy/gui/panes/macro_browser.py` のマクロ一覧はテーブル表示で、今回のGUI追補ではマクロ名 1 カラムへ縮約する。

### 観察

マクロ数が増えると単純なテーブルでは配置場所やタグの関係が見えにくく、タグ列を削るだけでは探索性が下がる。

### 方針

将来のGUI改修で VS Code のファイルエクスプローラーのような階層ツリー表示を追加し、Explorer / Search の表示切替と、Search 時のタグ名・マクロ名検索を検討する。

## 2026-05-19: tool 環境で実行するマクロ固有依存の宣言方法

### 現状

`uv tool install nyxpy` で CLI/GUI を導入した場合、tool の隔離環境には NyX と NyX の依存だけが入り、`macros\` から import されるマクロ固有の外部依存は自動では入らない。

### 観察

マクロが追加ライブラリを必要とする場合、利用者が `uv tool install --with ...` などで依存を入れる必要があるが、現時点では `macro.toml` などにその依存を宣言する規約がない。

### 方針

今回のドキュメント整理では宣言形式を決めず、将来 `macro.toml` の metadata、専用 dependencies セクション、または別ファイルに寄せるかを検討する。
