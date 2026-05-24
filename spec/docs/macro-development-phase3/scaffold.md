# scaffold 仕様

## 1. 目的

リポジトリを clone しない利用者でも、NyX の標準配置に沿ったマクロ雛形を生成できるようにする。テンプレートは package data として `nyxfw` に同梱し、`nyx-cli scaffold` から展開する。

## 2. 現状

| 項目 | 状態 |
|------|------|
| 雛形説明 | `docs\macro-development\macro-template.md` に存在 |
| package data | 未整備 |
| CLI 生成導線 | 未整備 |
| 生成先 | 手作業で `macros\` と `resources\` を作る必要がある |

## 3. 判断

最小テンプレートだけを package data として同梱する。`examples\macros` は公開サンプルであり、利用者の雛形生成元にはしない。

## 4. 生成仕様

### 4.1 生成先

```text
macros\<macro_id>\
  macro.py
  config.py
  test_logic.py

resources\<macro_id>\
  settings.toml
  assets\
```

### 4.2 `macro.py`

`MacroBase` を継承し、`settings_path = "resource:settings.toml"` を使う。`initialize`, `run`, `finalize` を含めるが、実処理は最小のボタン入力またはログ出力に留める。

### 4.3 `config.py`

設定値と変換処理を `dataclass` または純粋関数に分離する。`Command` を import しない。

### 4.4 `test_logic.py`

`config.py` の純粋関数を検証する。実機、キャプチャデバイス、シリアルデバイスに依存しない。

### 4.5 `settings.toml`

利用者がすぐ編集できる最小設定を置く。環境非依存のパス値を書く場合は `/` を使う。

## 5. CLI 仕様との接続

```powershell
uv run nyx-cli scaffold sample_turbo
uv run nyx-cli scaffold sample_turbo --force
```

既存ファイルがある場合、既定では失敗する。`--force` 指定時だけ上書きを許可する。部分生成に失敗した場合は、作成済みファイルを報告し、成功したかのようなメッセージを出さない。

## 6. 検証仕様

```powershell
uv run nyx-cli scaffold sample_turbo
uv run ruff check --no-respect-gitignore macros\sample_turbo
uv run pytest macros\sample_turbo
```

生成物は `.gitignore` 対象の `macros\` 配下に置かれるため、Ruff では `--no-respect-gitignore` を付ける。
