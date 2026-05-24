# API reference 生成仕様

## 1. 目的

`docs\macro-development\` の手順書から、公開 API の詳細へ到達できる API reference を生成する。API reference は docstring と型ヒントを入力にし、Markdown に同じ引数説明を手書きで重複させない。

## 2. 現状

| 項目 | 状態 |
|------|------|
| 手順書 | `docs\macro-development\*.md` に存在 |
| API reference | `docs\api\framework.md` に入口を作成済み |
| docs generator | `mkdocs.yml` に MkDocs + mkdocstrings 構成を追加済み |
| docs dependency group | `pyproject.toml` の `docs` group に `mkdocs`, `mkdocstrings[python]` を追加済み |
| local build | `uv run mkdocs build --strict` が成功する |

## 3. 判断

MkDocs + mkdocstrings を採用する。Markdown 中心の既存 docs と相性がよく、API reference だけを Python docstring / type hints から生成できるためである。

## 4. 構成仕様

| ファイル | 内容 |
|----------|------|
| `mkdocs.yml` | site name、nav、plugins、theme、mkdocstrings handler |
| `docs\api\framework.md` | framework API reference の入口 |
| `docs\macro-development\README.md` | API reference へのリンク |
| `pyproject.toml` | docs dependency group |

docs dependency group:

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
| `nyxpy.framework.core.io.resources` | resources / outputs の探索と保存 |

## 6. 検証仕様

```powershell
uv sync --locked --only-group docs --no-install-project
uv run --no-sync mkdocs build --strict
```

`mkdocs build --strict` は warning を失敗として扱う。API reference 生成は mkdocstrings / griffe の静的解析を前提にし、PaddleOCR、OpenCV、PySide6 などの重い runtime dependency の import 実行に依存させない。`mkdocs.yml` の `paths: [src]` から source を解析するため、docs CI では project install を省略する。

## 7. 完了条件

- `uv run mkdocs build --strict` が成功する。
- docs CI で `uv sync --locked --only-group docs --no-install-project` 後に build できる。
- `docs\api\framework.md` で `MacroBase`, `Command`, constants, imgproc, resources の docstring / 型ヒントが表示される。
- API reference の対象 module path が実体と一致している。
