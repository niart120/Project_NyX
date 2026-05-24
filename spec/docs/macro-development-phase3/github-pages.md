# GitHub Pages 配信仕様

## 1. 目的

`docs\macro-development\`、`docs\user-guide\`、API reference を GitHub Pages で公開し、`README.md` と `nyxpy docs` から到達できるようにする。GitHub Wiki は使わず、docs source と build 設定を repository 内で review 可能にする。

## 2. 現状

| 項目 | 状態 |
|------|------|
| docs source | `docs\`, `docs\macro-development\`, 今後追加する `docs\user-guide\` |
| build 設定 | `mkdocs.yml` を追加済み |
| API reference | `docs\api\framework.md` を追加済み |
| deploy workflow | `.github\workflows\docs.yml` を追加済み |
| 既存 CI | `.github\workflows\test.yml` の Python CI のみ |

## 3. 判断

GitHub Pages は GitHub Actions から deploy する。pull request では build のみ実行し、`master` push または manual dispatch で deploy する。公開面はマクロ開発者向けページだけに限定せず、通常利用者向けの `docs\user-guide\` も同じ MkDocs site に追加して公開する。

## 4. workflow 仕様

| 項目 | 方針 |
|------|------|
| ファイル | `.github\workflows\docs.yml` |
| trigger | `workflow_dispatch`, `push` to `master`, `pull_request` to `master` |
| setup | `actions/checkout`, `actions/setup-python`, `astral-sh/setup-uv` |
| install | `uv sync --locked --only-group docs --no-install-project` |
| build | `uv run --no-sync mkdocs build --strict` |
| configure | `actions/configure-pages` を deploy 対象 event で実行する |
| upload | `actions/upload-pages-artifact` |
| deploy | `actions/deploy-pages`。`pull_request` では実行しない |
| permissions | workflow default は `contents: read`。deploy job だけ `pages: write`, `id-token: write` を付ける |
| environment | deploy job に `github-pages` environment と `steps.deployment.outputs.page_url` を設定する |
| concurrency | deploy job は `group: pages`, `cancel-in-progress: false` とする |

`pull_request` で deploy job を動かさない条件を workflow に明記する。fork からの pull request でも docs build だけが走り、Pages 権限や OIDC token を要求しない状態にする。

## 5. 公開 URL

初期候補:

```text
https://niart120.github.io/Project_NyX/
https://niart120.github.io/Project_NyX/macro-development/
https://niart120.github.io/Project_NyX/api/framework/
```

`docs\user-guide\` 整備後は、通常利用者向け入口として次も同じ Pages site に追加する。

```text
https://niart120.github.io/Project_NyX/user-guide/
```

repository の Pages 設定で GitHub Actions source を有効化する必要がある。workflow だけでは repository settings の変更までは完了しない。

## 6. 検証仕様

```powershell
uv sync --locked --only-group docs --no-install-project
uv run --no-sync mkdocs build --strict
```

pull request 上では build が成功することを確認する。deploy は `master` への反映後または manual dispatch で確認する。

## 7. 完了条件

- pull request では `uv run --no-sync mkdocs build --strict` だけを検証し、deploy job は skip される。
- `master` push または manual dispatch で Pages artifact が deploy される。
- deploy job は `github-pages` environment の URL を出力する。
- 公開後に `https://niart120.github.io/Project_NyX/`, `https://niart120.github.io/Project_NyX/macro-development/`, `https://niart120.github.io/Project_NyX/api/framework/` を表示できる。
- `docs\user-guide\` 追加後は同じ workflow と nav で通常利用者向けページも公開できる。
