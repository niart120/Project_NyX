# scaffold 仕様

## 1. 目的

リポジトリを clone しない利用者でも、NyX の標準配置に沿ったマクロ雛形を生成できるようにする。workspace 初期化が作る `macros\` / `resources\` と、特定の `macro_id` 用ファイル生成の責務を分ける。

## 2. 現状

| 項目 | 状態 |
|------|------|
| 雛形説明 | `docs\macro-development\macro-template.md` に存在 |
| workspace 初期化 | `ensure_workspace()` が `.nyxpy`, `macros`, `resources`, `snapshots`, `runs`, `logs` を作成済み |
| package data | 未整備 |
| macro 個別生成 | 未整備 |
| CLI 生成導線 | 未整備。`nyxpy create <macro_id>` を主導線にする |
| 生成先 | 手作業で `macros\<macro_id>` と `resources\<macro_id>` を作る必要がある |

## 3. 判断

`ensure_workspace()` は workspace root と共通ディレクトリを作る責務に留める。scaffold は `macro_id` を受け取り、既存 workspace の `macros\<macro_id>` と `resources\<macro_id>` に最小ファイルを生成する独立サービスとして設計する。

最小テンプレートだけを package data として同梱する。`examples\macros` は公開サンプルであり、利用者の雛形生成元にはしない。

`uv tool install nyxfw` 後の主導線は `nyxpy ...` とし、macro 個別生成は `nyxpy create <macro_id>` から呼ぶ。`nyx-cli` は実行系 alias として扱い、scaffold の主導線にはしない。`nyxpy new` は多義的なため使わない。

`nyxpy init` は通常、workspace 初期化後にサンプルマクロ `sample_macro` も生成する。空の workspace だけを作る場合は `nyxpy init --blank` を使う。`nyxpy create <macro_id>` は workspace が存在しない場合に失敗し、先に `nyxpy init` を実行するよう案内する。

## 4. 生成サービス仕様

### 4.1 責務

| 責務 | 内容 |
|------|------|
| workspace 確認 | `.nyxpy` を持つ workspace root を解決する。存在しない場合は `nyxpy init` を促す |
| macro_id 検証 | Python package 名として扱える小文字スネークケースだけを許可する |
| ファイル生成 | template を `macro_id` と class 名に展開し、標準配置へ書き込む |
| 衝突検出 | 既存ファイルがある場合は既定で失敗し、明示オプション指定時だけ上書きする |
| 結果返却 | 作成ファイル、skip、衝突ファイルを呼び出し元が表示できる構造で返す |

### 4.2 生成先

`ensure_workspace()` によって `macros\` と `resources\` は作成済みである前提にする。ただし、未作成の場合でも scaffold 側で親ディレクトリ作成まで行ってよい。

```text
macros\<macro_id>\
  macro.py
  config.py
  test_logic.py

resources\<macro_id>\
  settings.toml
  assets\
```

### 4.3 `macro.py`

`MacroBase` を継承し、`settings_path = "resource:settings.toml"` を使う。`initialize`, `run`, `finalize` を含めるが、実処理は最小のボタン入力またはログ出力に留める。

### 4.4 `config.py`

設定値と変換処理を `dataclass` または純粋関数に分離する。`Command` を import しない。

### 4.5 `test_logic.py`

`config.py` の純粋関数を検証する。実機、キャプチャデバイス、シリアルデバイスに依存しない。

### 4.6 `settings.toml`

利用者がすぐ編集できる最小設定を置く。環境非依存のパス値を書く場合は `/` を使う。

## 5. CLI / 初期化導線との接続

| command | 役割 |
|---------|------|
| `nyxpy init` | workspace を作成し、サンプルマクロ `sample_macro` を同時生成する |
| `nyxpy init --blank` | `.nyxpy`, `macros`, `resources`, `snapshots`, `runs`, `logs` だけを作成する |
| `nyxpy create <macro_id>` | 既存 workspace に macro 個別 scaffold を生成する |

どの入口から呼ぶ場合も、生成本体は同じサービスを使う。既存ファイルがある場合、既定では失敗する。`--force` 相当の明示指定時だけ上書きを許可する。部分生成に失敗した場合は、作成済みファイルを報告し、成功したかのようなメッセージを出さない。

## 6. 検証仕様

```powershell
nyxpy init --blank
nyxpy create sample_turbo
uv run ruff check --no-respect-gitignore macros\sample_turbo
uv run pytest macros\sample_turbo
```

生成物は `.gitignore` 対象の `macros\` 配下に置かれるため、Ruff では `--no-respect-gitignore` を付ける。
