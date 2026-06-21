# PyPI 公開手順書

> **対象**: Project NyX の TestPyPI / PyPI 初回公開  
> **前提仕様**: [PyPI 登録準備 作業仕様書](PYPI_REGISTRATION_PREP.md)  
> **既定配布名**: `nyxpy-fw`  
> **import package**: `nyxpy`

## 1. 目的

この手順書は、PyPI への公開経験がない状態でも、TestPyPI での事前検証から PyPI 本番公開までを抜け漏れなく実施するための運用手順である。実作業では、配布名、GitHub environment 名、PyPI / TestPyPI の pending publisher 設定値を一致させる。

## 2. 全体フロー

1. 配布名を決め、PyPI / TestPyPI の空き状況を確認する。
2. `pyproject.toml`、README、docs、仕様書内の配布名を揃える。
3. ローカル成果物を削除し、build / test / docs / metadata を確認する。
4. GitHub environment `testpypi` と `pypi` を作成する。
5. TestPyPI の pending publisher を登録する。
6. GitHub Actions から TestPyPI へ publish する。
7. TestPyPI 版を clean venv に install し、依存解決と CLI 起動を確認する。
8. PyPI の pending publisher を登録する。
9. release commit を `master` に取り込み、`v*` tag を作成する。
10. GitHub Actions から PyPI へ publish する。
11. 公開後の project page、install、CLI を確認する。

## 3. アカウント準備

| 対象 | 必須作業 | 理由 |
|------|----------|------|
| PyPI | アカウント作成、メール確認、2FA 有効化 | project 管理と公開操作の前提 |
| TestPyPI | アカウント作成、メール確認、2FA 有効化 | PyPI とは別サービスであり、アカウントと設定も別管理 |
| GitHub | `niart120/Project_NyX` の Settings を操作できる権限確認 | environment 作成と workflow 実行に必要 |

PyPI と TestPyPI は別の index である。PyPI 側で pending publisher を設定しても TestPyPI には反映されない。逆も同じである。

## 4. 配布名の確認

候補名は PyPI の正規化規則に従って比較する。`nyxpy-fw`、`nyxpy_fw`、`nyxpy.fw` は同一 project 名として扱われる。

```console
python -c "import urllib.request, urllib.error; names=['nyxpy-fw','nyxpy-app']; hosts=['https://pypi.org/pypi/{}/json','https://test.pypi.org/pypi/{}/json'];\
for name in names:\
    for host in hosts:\
        url=host.format(name);\
        try: urllib.request.urlopen(url, timeout=10); print(url, 'exists')\
        except urllib.error.HTTPError as e: print(url, e.code)"
```

`404` ならその index には未登録である。ただし、pending publisher は名前を予約しない。配布名を確定したら、TestPyPI / PyPI の pending publisher 登録と初回 publish を同日中に進める。

## 5. GitHub environment 作成手順

GitHub Actions workflow の publish job は `.github\workflows\publish.yml` で `environment.name` を参照する。PyPI 側の pending publisher に入力する environment 名と GitHub repository 側の environment 名は完全に一致させる。

### 5.1 `testpypi` environment

1. GitHub で `niart120/Project_NyX` を開く。
2. **Settings** を開く。
3. 左メニューの **Environments** を開く。
4. **New environment** を押す。
5. environment name に `testpypi` を入力し、**Configure environment** を押す。
6. TestPyPI は検証用のため、required reviewers は任意とする。
7. Deployment branches and tags は、手動検証を容易にするため初期値のままにする。
8. Environment secrets は追加しない。Trusted Publishing は API token secret を使わない。

### 5.2 `pypi` environment

1. GitHub で `niart120/Project_NyX` を開く。
2. **Settings** を開く。
3. 左メニューの **Environments** を開く。
4. **New environment** を押す。
5. environment name に `pypi` を入力し、**Configure environment** を押す。
6. **Required reviewers** を有効化し、公開承認者を設定する。
7. **Prevent self-review** を有効化できる場合は有効化する。
8. Deployment branches and tags で tag だけに制限できる場合は、`v*` tag を許可する。
9. Environment secrets は追加しない。

補足:

- workflow が存在しない environment を参照すると GitHub が environment を自動作成する場合があるが、保護ルールは空になる。公開前に手動で作成し、`pypi` には reviewer を設定する。
- `.github\workflows\publish.yml` の publish job は job level で `permissions: id-token: write` を持つ必要がある。これは PyPI が GitHub Actions の OIDC identity を検証するために必要である。

## 6. pending publisher 登録手順

project がまだ存在しない初回公開では、project sidebar ではなく account sidebar から pending publisher を追加する。

### 6.1 TestPyPI

1. `https://test.pypi.org/` にログインする。
2. account sidebar の **Publishing** を開く。
3. GitHub Actions の pending publisher 追加フォームを開く。
4. 次の値を入力する。

| 項目 | 値 |
|------|----|
| PyPI project name | `nyxpy-fw` |
| Owner | `niart120` |
| Repository name | `Project_NyX` |
| Workflow filename | `publish.yml` |
| Environment name | `testpypi` |

5. **Add** を押して pending publisher を登録する。
6. 登録後、project name、owner、repository、workflow、environment に誤字がないことを確認する。

### 6.2 PyPI

1. `https://pypi.org/` にログインする。
2. account sidebar の **Publishing** を開く。
3. GitHub Actions の pending publisher 追加フォームを開く。
4. 次の値を入力する。

| 項目 | 値 |
|------|----|
| PyPI project name | `nyxpy-fw` |
| Owner | `niart120` |
| Repository name | `Project_NyX` |
| Workflow filename | `publish.yml` |
| Environment name | `pypi` |

5. **Add** を押して pending publisher を登録する。
6. 登録後、project name、owner、repository、workflow、environment に誤字がないことを確認する。

## 7. ローカル公開前チェック

公開前に古い生成物を削除する。

```console
rm -rf build site
rm -f dist/*.whl dist/*.tar.gz
rm -rf *.egg-info src/*.egg-info
```

Windows PowerShell で実行する場合:

```powershell
Remove-Item -Recurse -Force build, site -ErrorAction SilentlyContinue
Remove-Item -Force dist\*.whl, dist\*.tar.gz -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force *.egg-info, src\*.egg-info -ErrorAction SilentlyContinue
```

検証コマンド:

```console
uv lock --check
uv run ruff check .
uv run ty check src/nyxpy --output-format concise --no-progress
uv run pytest
uv run vulture src tests examples macros --min-confidence 80
uv run --no-sync mkdocs build --strict
uv build
uvx twine check --strict dist/*
```

確認する成果物:

| 対象 | 確認内容 |
|------|----------|
| wheel metadata | `Name: nyxpy-fw`、公開版 version、requires-python |
| wheel entry points | `nyxpy`, `nyx-cli`, `nyx-gui` |
| wheel package | `nyxpy\py.typed` と `nyxpy\framework\...` |
| sdist | `.pypirc`, `.nyxpy`, `dist\`, `site\`, ローカル `macros\`, ローカル `resources\` を含まない |

## 8. TestPyPI publish

1. GitHub の **Actions** を開く。
2. **Publish Python Package** workflow を選ぶ。
3. **Run workflow** を押す。
4. branch は作業ブランチまたは publish 検証用 branch を選ぶ。
5. `target` に `testpypi` を選ぶ。
6. workflow を実行する。
7. `build` job が `uv build` と `twine check` を通過することを確認する。
8. `publish-testpypi` job が完了することを確認する。
9. TestPyPI project page で metadata、README、files、verified publisher 表示を確認する。

失敗した場合:

| 症状 | 確認箇所 |
|------|----------|
| Trusted publisher not found | TestPyPI pending publisher の owner / repository / workflow / environment |
| OIDC token を取得できない | workflow job の `permissions: id-token: write` |
| environment 待ちで止まる | GitHub environment の reviewer 設定 |
| project name mismatch | `pyproject.toml` の `[project].name` と pending publisher の project name |

## 9. TestPyPI install 確認

TestPyPI は依存ライブラリが揃っていないため、NyX の wheel だけを TestPyPI から取得し、依存は PyPI から解決する。

```console
python -m venv .venv-testpypi
.venv-testpypi\Scripts\python -m pip install --upgrade pip
.venv-testpypi\Scripts\python -m pip download --no-deps --index-url https://test.pypi.org/simple/ --dest .tmp-testpypi nyxpy-fw==0.2.0
.venv-testpypi\Scripts\python -m pip install .tmp-testpypi\nyxpy_fw-0.2.0-py3-none-any.whl
.venv-testpypi\Scripts\python -c "import nyxpy; print(nyxpy.__name__)"
.venv-testpypi\Scripts\nyxpy --help
```

POSIX shell では `.venv-testpypi\Scripts\python` を `.venv-testpypi/bin/python`、`.venv-testpypi\Scripts\nyxpy` を `.venv-testpypi/bin/nyxpy` に読み替える。

`--extra-index-url` を使う方法もあるが、依存 package 名が TestPyPI に存在する場合に TestPyPI 側 artifact を選ぶ可能性がある。初回公開の確認では `pip download --no-deps` による wheel 取得分離方式を使う。

## 10. PyPI 本番 publish

本番 publish は TestPyPI 検証後に実行する。`.github\workflows\publish.yml` は `target=pypi` の場合、`refs/tags/v*` からの実行だけを許可する。

1. release commit を `master` に取り込む。
2. annotated tag を作成する。

```console
git tag -a v0.2.0 -m "v0.2.0"
git push origin master
git push origin v0.2.0
```

3. GitHub の **Actions** を開く。
4. **Publish Python Package** workflow を選ぶ。
5. **Run workflow** を押す。
6. ref に `v0.2.0` tag を選ぶ。
7. `target` に `pypi` を選ぶ。
8. workflow を実行する。
9. GitHub environment `pypi` の approval が求められた場合は、内容を確認して承認する。
10. `publish-pypi` job が完了することを確認する。
11. PyPI project page で metadata、README、files、verified publisher 表示を確認する。

## 11. 公開後確認

clean な環境で公開版を確認する。

```console
uv tool install nyxpy-fw
nyxpy --help
nyx-cli --help
nyx-gui --help
python -c "import nyxpy; print(nyxpy.__name__)"
```

確認項目:

| 対象 | 期待値 |
|------|--------|
| PyPI project page | description、README、links、classifiers が意図通り |
| files | sdist と wheel が 1 version 分だけ存在する |
| verified publisher | GitHub repository と workflow が表示される |
| install | `uv tool install nyxpy-fw` が成功する |
| CLI | `nyxpy --help`、`nyx-cli --help`、`nyx-gui --help` が起動する |
| import | `import nyxpy` が成功する |

## 12. 失敗時の扱い

| 状況 | 対応 |
|------|------|
| TestPyPI publish 失敗 | pending publisher、environment、workflow permissions、project name を修正し、同じ version で再実行する |
| TestPyPI install 失敗 | `--no-deps` 取得方式で切り分け、依存解決と wheel 内容を分けて確認する |
| PyPI publish 失敗 | PyPI pending publisher、`pypi` environment、`v*` tag からの実行かを確認する |
| PyPI publish 後の metadata 誤り | 同じ version は再アップロードできないため、次 patch version で修正する |
| PyPI publish 後の wheel 不足 | 原因を修正し、patch version を上げて再 publish する |
| secrets 混入 | secret を即時失効し、PyPI project owner として公開停止または削除可否を判断する |

## 13. 完了条件

- `nyxpy-fw` または採用した配布名で PyPI project が作成されている
- PyPI project page に expected metadata と verified publisher が表示されている
- `uv tool install <配布名>` が成功する
- `nyxpy --help` が公開版から起動する
- `import nyxpy` が公開版から成功する
- docs / README の導入手順が公開済み配布名と一致している
