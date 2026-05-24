# GitHub Pages 配信仕様

## 1. 目的

`docs\macro-development\` と API reference を GitHub Pages で公開し、`README.md` と `nyx-cli docs` から到達できるようにする。GitHub Wiki は使わず、docs source と build 設定を repository 内で review 可能にする。

## 2. 現状

| 項目 | 状態 |
|------|------|
| docs source | `docs\macro-development\` |
| build 設定 | 未整備 |
| deploy workflow | 未整備 |
| 既存 CI | `.github\workflows\test.yml` の Python CI のみ |

## 3. 判断

GitHub Pages は GitHub Actions から deploy する。pull request では build のみ実行し、`master` push または manual dispatch で deploy する。

## 4. workflow 仕様

| 項目 | 方針 |
|------|------|
| ファイル | `.github\workflows\docs.yml` |
| trigger | `workflow_dispatch`, `push` to `master`, `pull_request` to `master` |
| setup | `actions/checkout`, `actions/setup-python`, `astral-sh/setup-uv` |
| install | `uv sync --locked --group docs` |
| build | `uv run mkdocs build --strict` |
| upload | `actions/upload-pages-artifact` |
| deploy | `actions/deploy-pages` |
| permissions | deploy job に `pages: write` と `id-token: write` を付ける |

## 5. 公開 URL

初期候補:

```text
https://niart120.github.io/Project_NyX/
https://niart120.github.io/Project_NyX/macro-development/
https://niart120.github.io/Project_NyX/api/framework/
```

repository の Pages 設定で GitHub Actions source を有効化する必要がある。workflow だけでは repository settings の変更までは完了しない。

## 6. 検証仕様

```powershell
uv run mkdocs build --strict
```

pull request 上では build が成功することを確認する。deploy は `master` への反映後または manual dispatch で確認する。
