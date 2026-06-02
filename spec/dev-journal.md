# Dev Journal

実装中の設計上の気づき・疑問・バックログ送りタスクの記録。

## 2026-05-19: tool 環境で実行するマクロ固有依存の宣言方法

### 現状

`uv tool install nyxpy-fw` で CLI/GUI を導入した場合、tool の隔離環境には NyX と NyX の依存だけが入り、`macros\` から import されるマクロ固有の外部依存は自動では入らない。

### 観察

マクロが追加ライブラリを必要とする場合、利用者が `uv tool install --with ...` などで依存を入れる必要があるが、現時点では `macro.toml` などにその依存を宣言する規約がない。

### 方針

今回のドキュメント整理では宣言形式を決めず、将来 `macro.toml` の metadata、専用 dependencies セクション、または別ファイルに寄せるかを検討する。

## 2026-05-22: D102 docstring ルールの適用整理

### 現状

`pyproject.toml` では D100/D101/D103/D104/D105/D107 と D2/D3/D403/D417 を有効化済みだが、public method docstring の `D102` は未適用である。

### 観察

`D102` は framework public API、macro author 向け API、GUI event handler、Qt override を同時に対象にするため、薄い docstring を増やさないための分類が必要になる。

### 方針

次の docstring ルール拡充では `src\nyxpy\` と `examples\macros\` の public method を分類し、Qt override や signal handler の扱いを決めてから D102 を段階適用する。
