# `nyxpy` 導線仕様

## 1. 目的

`uv tool install nyxfw` 後に、利用者が `nyxpy ...` から GUI 起動、マクロ実行、workspace 初期化、マクロ生成、docs 表示へ到達できるようにする。`nyx-gui` と `nyx-cli` は主導線ではなく alias として扱う。

## 2. 現状

| 項目 | 状態 |
|------|------|
| CLI parser | `nyxpy` が `init`, `create`, `run`, `docs`, `gui` を持つ |
| 必須 option | `--serial`, `--capture` |
| docs 表示 | `nyxpy docs` を追加済み |
| workspace 初期化 | `nyxpy init` が `.nyxpy`, `macros`, `resources`, `snapshots`, `runs`, `logs` を作成する |
| scaffold | `nyxpy create <macro_id>` を追加済み |

## 3. 判断

Phase 3 では `nyxpy` console script を追加し、`python -m nyxpy` と同じ parser を使う。主導線は `nyxpy ...` に統一する。

`nyx-cli` は `nyxpy run` の alias、`nyx-gui` は `nyxpy gui` の alias として扱う。アルファ版ポリシーにより破壊的変更は許容するため、旧 `nyx-cli <macro_name> --serial ... --capture ...` 形式の互換 shim は必須ではない。

scaffold は `nyxpy create <macro_id>` を主導線にする。`nyxpy new` は多義的なため使わない。`nyxpy init` は通常サンプルマクロを同時生成し、空 workspace が必要な場合だけ `nyxpy init --blank` を使う。

## 4. command 仕様

| command | 役割 | 主な option |
|---------|------|-------------|
| `nyxpy init` | workspace とサンプルマクロを作成 | `--blank`, `--force` |
| `nyxpy create <macro_id>` | 既存 workspace に macro 雛形を生成 | `--force`, `--root` |
| `nyxpy run <macro_name>` | マクロ実行 | `--serial`, `--capture`, `--protocol`, `--baud`, `--define`, `--silence`, `--verbose` |
| `nyxpy docs` | docs URL とローカル参照方法を表示 | `--json` を将来候補にするが初期実装では不要 |
| `nyxpy gui` | GUI 起動 | 初期実装では追加 option なし |

alias:

| alias | 対応先 |
|-------|--------|
| `nyx-cli` | `nyxpy run` |
| `nyx-gui` | `nyxpy gui` |

## 5. `docs` 出力仕様

標準出力へ次を出す。ブラウザの自動起動は行わない。

```text
User guide: https://niart120.github.io/Project_NyX/user-guide/
Macro development docs: https://niart120.github.io/Project_NyX/macro-development/
Agent brief: https://niart120.github.io/Project_NyX/macro-development/agent-brief/
API reference: https://niart120.github.io/Project_NyX/api/framework/
Local API help: python -m pydoc nyxpy.framework.core.macro.command
```

## 6. scaffold 出力仕様

成功時は作成した root とファイル一覧を出す。既存ファイルがあり `--force` がない場合は非 0 exit code とし、どのファイルが衝突したかを表示する。

```text
Created macro scaffold: sample_turbo
  created: macros\sample_turbo\__init__.py
  created: macros\sample_turbo\macro.py
  created: macros\sample_turbo\config.py
  created: macros\sample_turbo\test_logic.py
  created: resources\sample_turbo\settings.toml
```

## 7. 検証仕様

```powershell
nyxpy init --blank
nyxpy create sample_turbo
nyxpy docs
nyxpy run sample_turbo --serial COM3 --capture "Capture Device"
nyxpy gui
nyx-cli sample_turbo --serial COM3 --capture "Capture Device"
nyx-gui
```

`init`, `create`, `docs`, `gui` は `--serial` と `--capture` なしで動作する。`run` と `nyx-cli` alias はハードウェア引数を要求する。
