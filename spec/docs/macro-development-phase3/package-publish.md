# package metadata / publish 手順仕様

## 1. 目的

PyPI 配布名 `nyxfw` と import package 名 `nyxpy` の構成で、build 可能な package metadata と publish 手順を整える。初回 publish は別判断にし、Phase 3 では公開可能な成果物を作れる状態までを対象にする。

## 2. 現状

| 項目 | 状態 |
|------|------|
| `[project].name` | `project-nyx` |
| import package | `nyxpy` |
| console scripts | `nyx-cli`, `nyx-gui` |
| build backend | hatchling |
| publish workflow | 未配置 |
| ローカル publish 設定 | repository 内に `.pypirc` が存在するが、Phase 3 の publish 手順では依存しない |

## 3. 判断

`pyproject.toml` の配布名を `nyxfw` に寄せる。publish は GitHub Actions trusted publishing を第一候補とし、PyPI API token やローカル `.pypirc` に依存しない。

## 4. metadata 仕様

| 項目 | 方針 |
|------|------|
| name | `nyxfw` |
| version | 初回公開時点の release 判断に合わせる。現状は `0.1.0` を候補とする |
| description | マクロ開発 framework、CLI、GUI を含む用途が分かる短文にする |
| authors | 現行値を維持する |
| license | MIT を維持する。build warning が出る場合は PEP 639 形式へ寄せる |
| readme | `README.md` |
| requires-python | 現行の `>=3.12,<3.14` を維持する |
| scripts | `nyx-cli`, `nyx-gui` を維持する |

## 5. build / publish 手順

ローカル検証:

```powershell
uv build
uvx twine check dist\*
```

TestPyPI 検証:

1. PyPI 側で trusted publisher を設定する。
2. GitHub Actions の manual dispatch で TestPyPI へ publish する。
3. 別環境で `uv add --index-url https://test.pypi.org/simple/ nyxfw` を試す。
4. `python -c "import nyxpy"` と `nyx-cli --help` を確認する。

本番 PyPI publish は、TestPyPI で package name、metadata、wheel contents、console scripts を確認した後に実行する。

## 6. 完了条件

| 条件 | 確認方法 |
|------|----------|
| wheel / sdist が生成できる | `uv build` |
| metadata が PyPI に受理可能 | `uvx twine check dist\*` |
| wheel の Name が `nyxfw` | wheel の `METADATA` を確認 |
| import package が `nyxpy` | built wheel を一時環境へ install して `import nyxpy` |
| console scripts が含まれる | wheel の `entry_points.txt` を確認 |
