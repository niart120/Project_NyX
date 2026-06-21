---
name: pypi-release
description: "Project NyX の PyPI release を計画・実行する workflow skill。USE WHEN: ユーザが PyPI / TestPyPI への公開、バージョン更新、release PR、v* tag、GitHub Actions publish、公開後 smoke check、release 手順の確認を依頼したとき。"
---

# PyPI Release

Project NyX (`nyxpy-fw`, import package `nyxpy`) の release preflight、version bump PR、GitHub Actions Trusted Publishing、post-publish smoke check を進める。
手元の `twine upload` は使わない。`.github/workflows/publish.yml` を使い、production PyPI は `v*` tag ref から `workflow_dispatch` の `target=pypi` で publish する。tag push だけでは publish されない。

## Inputs

| 入力 | 扱い |
| ---- | ---- |
| `version` | 明示されたらその version を候補にする。未指定なら latest tag と未リリース commit から提案する。 |
| `releaseType` | `patch` / `minor` / `major`。未指定なら変更内容から提案する。 |
| `includeTestPyPI` | 明示された場合のみ TestPyPI workflow を通す。高リスク変更では実行を提案する。 |
| `createGitHubRelease` | 既定で提案する。不要と明示されたら final report だけにする。 |
| `realDeviceSmoke` | 実機 smoke は、ユーザの明示承認と機材準備がない限り実行しない。 |

## Preconditions

- `git status --short` が clean であること。
- GitHub remote と default branch を確認できること。
- `spec/agent/complete/local_015/PYPI_PUBLICATION_RUNBOOK.md` と `.github/workflows/publish.yml` が存在すること。
- PyPI / TestPyPI の Trusted Publisher が project / owner / repository / workflow / environment に一致していること。
  - project: `nyxpy-fw`
  - owner / repository: `niart120/Project_NyX`
  - workflow: `publish.yml`
  - environment: `testpypi` または `pypi`
- production tag push と `target=pypi` workflow 実行は、current turn で明示確認を得てから行うこと。

## Preflight

1. `git branch --show-current` と `git status --short --branch` を確認する。
2. default branch と `origin/<default>` を確認し、release PR 作成時は `release/vX.Y.Z` branch を使う。
3. `git fetch --tags origin` で tag を更新する。
4. `git tag --list "v*" --sort=-version:refname` と `git log --oneline --no-merges <latest-tag>..HEAD` で未リリース差分を読む。
5. `pyproject.toml`、`uv.lock`、README、docs、`spec/agent/complete/local_015/PYPI_PUBLICATION_RUNBOOK.md` の package name / version / Python support / entry points / optional extras の drift を確認する。
6. PyPI の version-specific JSON endpoint で候補 version が未公開であることを確認する。
7. release tag が local / remote に存在しないことを確認する。
8. `.github/workflows/publish.yml` が `target=pypi` を `refs/tags/v*` に制限し、publish job に `id-token: write` を持つことを確認する。

## Version Policy

| 条件 | 既定の release type |
| ---- | ------------------- |
| docs、metadata、bug fix、dependency constraint cleanup | `patch` |
| 後方互換の public API / CLI / GUI / macro API 追加 | `minor` |
| import package、public API、CLI、設定、dependency surface の破壊的変更 | `major` または pre-1.0 の explicit version |

Project NyX はアルファ版だが、破壊的変更を含む release では release plan に対象範囲と移行不要の理由を書く。
`feat` commit があるのに `patch` を選ぶ場合、理由を release plan に書く。
`BREAKING CHANGE` または `!` 付き commit があるのに `minor` 以下を選ぶ場合、中断して user に確認する。

## Release PR

1. `release/vX.Y.Z` branch を作る。
2. `pyproject.toml` の project version を更新する。
3. `uv lock` で `uv.lock` を同期する。
4. README、docs、`spec/agent/complete/local_015/PYPI_PUBLICATION_RUNBOOK.md` の例、release note draft、必要な docs を更新する。
5. stale distribution artifact を削除し、local gates を実行する。`dist/.gitignore` は残し、過去 version の wheel / sdist は削除する。

```console
uv sync --dev
uv lock --check
uv run ruff format --check .
uv run ruff check .
uv run ty check src/nyxpy --output-format concise --no-progress
uv run pytest
uv run vulture src tests examples macros --min-confidence 80
uv run --no-sync mkdocs build --strict
Remove-Item -Force dist\nyxpy_fw-*.whl, dist\nyxpy_fw-*.tar.gz -ErrorAction SilentlyContinue
uv build
uvx twine check --strict dist\nyxpy_fw-X.Y.Z-py3-none-any.whl dist\nyxpy_fw-X.Y.Z.tar.gz
git diff --check
```

6. wheel / sdist content を candidate version 固定で確認する。`next(Path("dist").glob("*.whl"))` のような曖昧な選択は、古い artifact を誤検査するため使わない。
   - wheel: `nyxpy/__main__.py`、`nyxpy/py.typed`、`nyxpy/framework/`、entry points `nyxpy` / `nyx-cli` / `nyx-gui` を含むこと。
   - sdist: `.pypirc`、`.nyxpy`、`dist/`、`site/`、ローカル作業用 `macros/`、ローカル作業用 `resources/` を含まないこと。
7. PR 作成、merge、default branch 同期、branch cleanup は `pr-merge-cleanup` に委譲する。

## TestPyPI

- TestPyPI は `Publish Python Package` workflow の `workflow_dispatch` path で、`target=testpypi` を指定して実行する。
- TestPyPI を実行しても production PyPI は更新されない。
- TestPyPI の dependency resolution は本番 PyPI と完全には一致しない。NyX の wheel だけを TestPyPI から `--no-deps` で取得し、依存は PyPI から解決する手順を優先する。
- 具体的な Windows 手順は `spec/agent/complete/local_015/PYPI_PUBLICATION_RUNBOOK.md` の「TestPyPI install 確認」に従う。

## Production Publish

1. release PR が merge 済みで、local default branch が `origin/<default>` と同期していることを確認する。
2. candidate version が PyPI に未公開で、`vX.Y.Z` tag が存在しないことを再確認する。
3. production publish の明示意図が current turn にない場合、tag push 前に user に確認する。
4. annotated tag を作成して push する。

```console
git tag -a vX.Y.Z -m "vX.Y.Z"
git push origin vX.Y.Z
```

5. `Publish Python Package` workflow を `vX.Y.Z` ref から `target=pypi` で手動実行する。
6. workflow run を確認する。build failure と publish failure を分けて読む。
7. build と `twine check` が通った後の `requests.exceptions.ChunkedEncodingError` など attestation / network 系 failure は、metadata 変更ではなく failed job rerun 候補として扱う。

## Post-Publish

1. version-specific endpoint を確認する。

```text
https://pypi.org/pypi/nyxpy-fw/X.Y.Z/json
```

2. version-pinned smoke check を行う。

```console
uvx --from nyxpy-fw==X.Y.Z python -c "import importlib.metadata, nyxpy; print(importlib.metadata.version('nyxpy-fw')); print(nyxpy.__name__)"
uvx --from nyxpy-fw==X.Y.Z nyxpy --help
uvx --from nyxpy-fw==X.Y.Z nyx-cli --help
```

3. optional dependency に触れた release では、該当 extra を version-pinned で確認する。

```console
uvx --from "nyxpy-fw[windows]==X.Y.Z" python -c "import importlib.metadata; print(importlib.metadata.version('nyxpy-fw'))"
uvx --from "nyxpy-fw[ponkan]==X.Y.Z" python -c "import importlib.metadata; print(importlib.metadata.version('nyxpy-fw'))"
```

4. GUI 起動や実機 smoke が必要な場合は、ユーザの明示承認を得てから実行する。
5. GitHub Release を作る場合は、version、tag、PR、merge commit、PyPI URL、workflow run、local gates、smoke 結果、known limitations を含める。

## Stop Conditions

- dirty worktree がある。
- default branch が `origin/<default>` と同期していない。
- candidate version が PyPI に既に存在する。
- local または remote に release tag が既に存在する。
- `pyproject.toml`、`uv.lock`、README、docs、publication runbook の metadata が矛盾している。
- publish workflow が `target=pypi` の tag 制約または `id-token: write` を満たしていない。
- local gate、CI、publish workflow が失敗している。
- production tag push または `target=pypi` workflow 実行の明示意図がない。
- GUI / 実機 smoke が必要だが、ユーザ承認や機材準備がない。

## Report

最終報告には次を含める。

```text
- version:
- release type:
- release branch / PR:
- tag:
- merge commit:
- TestPyPI:
- PyPI URL:
- publish workflow run:
- local gates:
- post-publish smoke:
- GitHub Release:
- GUI / real device: used | not used | not run with reason
- follow-up:
```
