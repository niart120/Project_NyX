# `nyx-cli` 導線仕様

## 1. 目的

`uv tool install nyxfw` または `uv add nyxfw` 後に、利用者が CLI からマクロ開発 docs と scaffold に到達できるようにする。ハードウェアが必要なマクロ実行と、ハードウェア不要の情報提供 command を分離する。

## 2. 現状

| 項目 | 状態 |
|------|------|
| CLI parser | positional `macro_name` を必須にする |
| 必須 option | `--serial`, `--capture` |
| docs 表示 | なし |
| scaffold | なし |

## 3. 判断

Phase 3 で CLI 導線を実装する場合は subcommand 化する。現行形式を維持する互換 shim は必須としない。

## 4. command 仕様

| command | 役割 | 主な option |
|---------|------|-------------|
| `nyx-cli run <macro_name>` | マクロ実行 | `--serial`, `--capture`, `--protocol`, `--baud`, `--define`, `--silence`, `--verbose` |
| `nyx-cli docs` | docs URL とローカル参照方法を表示 | `--json` を将来候補にするが初期実装では不要 |
| `nyx-cli scaffold <macro_id>` | 標準配置に雛形を生成 | `--force`, `--root` |

## 5. `docs` 出力仕様

標準出力へ次を出す。ブラウザの自動起動は行わない。

```text
Macro development docs: https://niart120.github.io/Project_NyX/macro-development/
Agent brief: https://niart120.github.io/Project_NyX/macro-development/agent-brief/
API reference: https://niart120.github.io/Project_NyX/api/framework/
Local API help: python -m pydoc nyxpy.framework.core.macro.command
```

## 6. `scaffold` 出力仕様

成功時は作成した root とファイル一覧を出す。既存ファイルがあり `--force` がない場合は非 0 exit code とし、どのファイルが衝突したかを表示する。

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
uv run nyx-cli scaffold sample_turbo
uv run nyx-cli run sample_turbo --serial COM3 --capture "Capture Device"
```

`docs` と `scaffold` は `--serial` と `--capture` なしで動作する。`run` はハードウェア引数を要求する。
