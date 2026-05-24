# API reference 生成仕様

## 1. 目的

`docs\macro-development\` の手順書から、公開 API の詳細へ到達できる API reference を生成する。API reference は docstring と型ヒントを入力にし、Markdown に同じ引数説明を手書きで重複させない。

## 2. 現状

| 項目 | 状態 |
|------|------|
| 手順書 | `docs\macro-development\*.md` に存在 |
| API reference | 未整備 |
| docs generator | 未整備 |
| 候補 | MkDocs + mkdocstrings |

## 3. 判断

MkDocs + mkdocstrings を第一候補にする。Markdown 中心の既存 docs と相性がよく、API reference だけを Python docstring / type hints から生成できるためである。

## 4. 構成仕様

| ファイル | 内容 |
|----------|------|
| `mkdocs.yml` | site name、nav、plugins、theme、mkdocstrings handler |
| `docs\api\framework.md` | framework API reference の入口 |
| `docs\macro-development\README.md` | API reference へのリンク |
| `pyproject.toml` | docs dependency group |

docs dependency group の候補:

```toml
[dependency-groups]
docs = [
    "mkdocs>=1.6",
    "mkdocstrings[python]>=0.29",
]
```

## 5. 初期 API 対象

| 対象 | 理由 |
|------|------|
| `nyxpy.framework.core.macro.base.MacroBase` | マクロ class の基底 |
| `nyxpy.framework.core.macro.command.Command` | 入力、待機、capture、ログ、通知、画像入出力の入口 |
| `nyxpy.framework.core.constants` | Button、stick、3DS 座標定数 |
| `nyxpy.framework.core.imgproc` | テンプレートマッチング、OCR、前処理 |
| `nyxpy.framework.core.resources` | resources / outputs の探索と保存 |

## 6. 検証仕様

```powershell
uv sync --locked --group docs
uv run mkdocs build --strict
```

`mkdocs build --strict` は warning を失敗として扱う。API reference 生成が heavy dependency の import 実行に依存して失敗する場合は、mkdocstrings / griffe の静的解析設定で回避する。
