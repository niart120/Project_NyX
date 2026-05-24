# `nyx-cli` 導線仕様

## 1. 目的

`uv tool install nyxfw` または `uv add nyxfw` 後に、利用者が CLI からマクロ開発 docs に到達できるようにする。ハードウェアが必要なマクロ実行と、ハードウェア不要の情報提供 command を分離する。scaffold は生成サービスを先に作り、CLI 入口は `nyx-cli` 固定にしない。

## 2. 現状

| 項目 | 状態 |
|------|------|
| CLI parser | positional `macro_name` を必須にする |
| 必須 option | `--serial`, `--capture` |
| docs 表示 | なし |
| workspace 初期化 | `python -m nyxpy init` が `.nyxpy`, `macros`, `resources`, `snapshots`, `runs`, `logs` を作成する |
| scaffold | macro 個別生成サービスは未整備 |

## 3. 判断

Phase 3 で `nyx-cli` にハードウェア不要 command を追加する場合は subcommand 化する。現行形式を維持する互換 shim は必須としない。

ただし scaffold は `nyx-cli scaffold` に直結させない。`nyx-cli` は現状マクロ実行用の console script であり、workspace 初期化は `python -m nyxpy init` 側に存在する。scaffold はまず共通生成サービスとして実装し、公開入口は `python -m nyxpy init --macro <macro_id>`、`python -m nyxpy macro new <macro_id>`、将来の統合 console script のいずれが自然かを選ぶ。

## 4. command 仕様

| command | 役割 | 主な option |
|---------|------|-------------|
| `nyx-cli run <macro_name>` | マクロ実行 | `--serial`, `--capture`, `--protocol`, `--baud`, `--define`, `--silence`, `--verbose` |
| `nyx-cli docs` | docs URL とローカル参照方法を表示 | `--json` を将来候補にするが初期実装では不要 |

scaffold の入口候補:

| command | 役割 | 評価 |
|---------|------|------|
| `python -m nyxpy init --macro <macro_id>` | workspace 初期化後に macro 雛形を生成する | 既存 `init` と接続しやすい |
| `python -m nyxpy macro new <macro_id>` | macro 管理 command として雛形を生成する | 将来の `macro list` / `macro validate` と並べやすい |
| `nyx-cli scaffold <macro_id>` | `nyx-cli` に雛形生成を追加する | 短いが、マクロ実行専用 CLI の責務が広がる |

## 5. `docs` 出力仕様

標準出力へ次を出す。ブラウザの自動起動は行わない。

```text
Macro development docs: https://niart120.github.io/Project_NyX/macro-development/
Agent brief: https://niart120.github.io/Project_NyX/macro-development/agent-brief/
API reference: https://niart120.github.io/Project_NyX/api/framework/
Local API help: python -m pydoc nyxpy.framework.core.macro.command
```

## 6. scaffold 出力仕様

どの CLI 入口を採用しても、成功時は作成した root とファイル一覧を出す。既存ファイルがあり `--force` 相当の明示指定がない場合は非 0 exit code とし、どのファイルが衝突したかを表示する。

```text
Created macro scaffold: sample_turbo
  macros\sample_turbo\macro.py
  macros\sample_turbo\config.py
  macros\sample_turbo\test_logic.py
  resources\sample_turbo\settings.toml
```

## 7. 検証仕様

```powershell
uv run nyx-cli docs
python -m nyxpy macro new sample_turbo
uv run nyx-cli run sample_turbo --serial COM3 --capture "Capture Device"
```

`docs` と scaffold 入口は `--serial` と `--capture` なしで動作する。`run` はハードウェア引数を要求する。scaffold 入口を `python -m nyxpy macro new` 以外に決めた場合は、検証コマンドだけを実装に合わせて差し替える。
