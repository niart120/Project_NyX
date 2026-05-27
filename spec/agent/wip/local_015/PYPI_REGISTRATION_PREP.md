# PyPI 登録準備 作業仕様書

> **目的**: Project NyX を PyPI / TestPyPI へ初回登録する前に、配布資材のクリーンアップ、最終検証、配布名の再判定、公開手順を固定する。  
> **作業ブランチ**: `docs/pypi-registration-prep-spec`  
> **別紙**: [PyPI 公開手順書](PYPI_PUBLICATION_RUNBOOK.md)  
> **関連仕様**: `spec\docs\macro-development-phase3\package-publish.md`, `spec\docs\MACRO_DEVELOPMENT_PHASE3_SPEC.md`

## 1. 概要

### 1.1 目的

PyPI 初回公開は配布名、成果物内容、metadata、Trusted Publishing 設定を後から戻しにくい作業である。この仕様書では、公開直前に実施する確認項目と実手順を分離し、TestPyPI で検証してから PyPI 本番へ進む。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| 配布名 | PyPI 上の project 名。新候補は `nyxpy-fw` / `nyxpy-app` |
| 正規化名 | PyPI の比較用名称。大文字小文字を区別せず、`.`, `_`, `-` の連続を `-` に畳み込む |
| import package | Python で import する package 名。現行は `nyxpy` |
| Trusted Publishing | PyPI / TestPyPI 側に GitHub Actions workflow を登録し、API token なしで公開する方式 |
| pending publisher | PyPI / TestPyPI 側で初回 publish 前に登録する Trusted Publishing の予約設定 |
| GitHub environment | workflow job の実行前に reviewer 承認や branch / tag 制限をかける GitHub Actions の設定 |
| sdist | source distribution。`uv build` で生成する `.tar.gz` |
| wheel | built distribution。`uv build` で生成する `.whl` |
| 公開資材 | PyPI にアップロードする sdist / wheel と、PyPI project page で参照される metadata / README |

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `pyproject.toml` | 変更 | 配布名、version、description、requires-python、classifiers、dependencies、scripts、URLs を更新する |
| `README.md` | 変更 | PyPI project page に表示される導入導線と注意事項を更新する |
| `.github\workflows\publish.yml` | 変更 | TestPyPI / PyPI の Trusted Publishing workflow と本番 publish 制約を確認する |
| `.github\workflows\test.yml` | 変更 | Python 3.14 を許容する場合だけ CI matrix を追加する |
| `.github\workflows\docs.yml` | 変更なし | 公開 docs の strict build を確認する |
| `docs\` | 変更 | `uv tool install <配布名>`、`nyxpy ...`、alias の説明を更新する |
| `spec\docs\` | 変更 | Phase 3 仕様に残る旧配布名を、確定した配布名へ更新する |
| `src\nyxpy\py.typed` | 変更なし | wheel に型情報 marker が含まれることを確認する |
| `dist\` | 削除 | 古い sdist / wheel を削除してから再生成する。`dist\.gitignore` は保持する |
| `.pypirc` | 削除候補 | Trusted Publishing に使わないローカル設定。中身を公開せず、Git 管理対象にしない |
| `build\`, `*.egg-info`, `src\*.egg-info`, `site\` | 削除 | 古い build / docs 生成物が混入しないよう削除する |
| `spec\agent\wip\local_015\PYPI_REGISTRATION_PREP.md` | 新規 | 本作業仕様書 |
| `spec\agent\wip\local_015\PYPI_PUBLICATION_RUNBOOK.md` | 新規 | PyPI / TestPyPI / GitHub environment の手順書 |

## 3. 設計方針

### 3.1 公開方針

初回登録は次の順序で進める。

1. ローカルの古い成果物と不要な公開資材を削除する。
2. 配布名を公開直前に再判定し、確定後は PyPI 本番公開まで変更しない。
3. ローカルで build、metadata、wheel / sdist 内容、CLI entry point、docs、型検査、テストを確認する。
4. TestPyPI と GitHub environment を準備し、GitHub Actions から TestPyPI へ publish する。
5. TestPyPI から NyX の wheel だけを取得し、依存は PyPI から解決して動作確認する。
6. PyPI と GitHub environment を準備し、`v*` tag から本番 publish する。
7. 公開後に `uv tool install <配布名>` と project page 表示を確認する。

詳細なクリック手順、入力値、失敗時の切り分けは別紙 `PYPI_PUBLICATION_RUNBOOK.md` に集約する。

### 3.2 配布名の再々考

現行の `pyproject.toml` は配布名 `nyxpy-fw`、import package 名 `nyxpy` である。2026-05-27 時点の確認では、`nyxpy-fw`、`nyxpy-app`、`nyxfw` は PyPI / TestPyPI とも未登録である。`nyxpy-fw` と `nyxpy_fw` は PyPI の正規化により同一名として扱われる。

| 候補 | 判定 | 理由 |
|------|------|------|
| `nyxpy-fw` | 第一候補 | import package `nyxpy` との関係が分かりやすく、framework 依存として導入する用途にも合う |
| `nyxpy-app` | 第二候補 | GUI / CLI アプリとしての導入名には合うが、マクロ開発者が `nyxpy.framework.*` を依存として使う説明にはやや弱い |
| `nyxfw` | 旧候補 | 短いが、`nyxpy` との対応が分かりにくい。以前の docs では採用済みだったが、公開前に `nyxpy-fw` へ寄せる |
| `nyxpy` | 不採用 | PyPI で既存 project が使用中。import package 名としてのみ維持する |
| `project-nyx` | 不採用 | TestPyPI で既存 project があり、公開パッケージ名としてリポジトリ内向きに見える |

最終判断の既定は `nyxpy-fw` とする。`nyxpy-app` を採用する場合は、PyPI package を「マクロ開発 framework」ではなく「NyX GUI / CLI アプリ」として前面に出す判断を明示する。配布名を変更する場合は TestPyPI publish 前に限り、`pyproject.toml`、README、docs、仕様書、検証コマンドを同一変更で更新する。PyPI 本番へ一度公開した後は、同名 project を継続し、名前変更ではなく metadata / docs で説明を補う。

### 3.3 Python 3.14 対応方針

Python 3.14 を package metadata 上で許容するには、NyX 本体のテストだけでなく、必須依存が 3.14 で解決できることが必要である。2026-05-27 時点の PyPI metadata では、`pyside6`、`opencv-python`、`numpy`、`pillow` などは 3.14 対応の見込みがある。一方で、現行制約の `paddlepaddle>=3.2.2,<3.3.0` は 3.2.2 に cp313 wheel はあるが cp314 wheel が見当たらず、最新版 3.3.1 でも cp314 wheel が確認できない。

初回 PyPI 公開では `requires-python = ">=3.12,<3.14"` を維持する。3.14 対応は、次の条件を満たした後に `>=3.12,<3.15` へ広げる。

| 条件 | 確認内容 |
|------|----------|
| 依存解決 | Python 3.14 環境で `uv sync` または package install が成功する |
| OCR 依存 | `paddlepaddle` / `paddleocr` が 3.14 で install できる。または OCR を optional dependency に分離する |
| CI | Python 3.14 を CI matrix に追加し、ruff / ty / pytest が通る |
| metadata | `Programming Language :: Python :: 3.14` classifier を追加する |
| 実機依存 | GUI / capture / OCR の起動確認で 3.14 固有の問題がない |

3.14 を早く許容したい場合の現実的な手は、OCR 系依存を optional extra に分離し、core / CLI scaffold は 3.14 対応、OCR macro 実行は 3.12 / 3.13 推奨と分けることである。この分離は公開 API と install 導線に影響するため、初回公開直前の小変更では扱わない。

### 3.4 クリーンアップ方針

公開対象に入れてよいものと、入れてはいけないものを明示する。

| 区分 | 方針 |
|------|------|
| wheel | `src\nyxpy\` 配下、`py.typed`、CLI entry point、package 内 template を含める |
| sdist | build に必要な最小限の tracked files を含める。ローカル作業用 `macros\`, `resources\`, `.nyxpy`, `.pypirc`, `dist\`, `site\` は含めない |
| ローカル成果物 | publish 前に削除してから再生成する |
| secrets | `.pypirc`、token、個人環境の設定を commit / sdist / wheel に含めない |
| docs | GitHub Pages を公開 docs とし、GitHub Wiki は使わない |

## 4. 実装仕様

### 4.1 事前クリーンアップ

次の資材を publish 前に削除または退避する。`dist\.gitignore` は保持する。

| 対象 | 処理 | 確認方法 |
|------|------|----------|
| `dist\*.whl`, `dist\*.tar.gz` | 削除してから `uv build` で再生成 | 生成時刻と version を確認 |
| `build\` | 削除 | ディレクトリが存在しないこと |
| `*.egg-info`, `src\*.egg-info` | 削除 | ディレクトリが存在しないこと |
| `site\` | 削除 | docs build 後に再生成されること |
| `.pypirc` | Trusted Publishing へ移行するため不要。必要なら repository 外へ退避 | `git status --short` に出ないこと |
| `.nyxpy\`, ローカル `macros\`, ローカル `resources\` | sdist / wheel に含まれないことを確認 | archive contents を確認 |

### 4.2 metadata 最終確認

| 項目 | 期待値 |
|------|--------|
| `[project].name` | `nyxpy-fw` を既定候補とする。`nyxpy-app` 採用時は全 docs と command 例を同時更新する |
| `[project].version` | 初回 publish 版。現行候補は `0.1.0` |
| `[project].description` | macro API、CLI、GUI を含む用途が分かる短文 |
| `[project].readme` | `README.md` |
| `[project].requires-python` | 初回公開は `>=3.12,<3.14` を維持する |
| `[project].license` | MIT。build warning が残る場合は PEP 639 形式へ更新する |
| `[project].classifiers` | Alpha、Python 3.12 / 3.13、Typed package を反映。3.14 classifier は CI 追加後に限る |
| `[project.scripts]` | `nyxpy` を主導線、`nyx-cli` / `nyx-gui` を alias として維持 |
| `[project.urls]` | Repository、Documentation、Issues を含める |
| optional dependencies | Windows 固有依存を `windows` extra と platform marker で分離 |

### 4.3 ローカル検証

公開前に次のコマンドを実行する。

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

補足:

- `macros\` は Git 管理外でも pytest 対象である。Ruff をローカルマクロへ直接かける必要がある場合は `--no-respect-gitignore` を使う。
- `uv build` の前に古い `dist\*.whl` と `dist\*.tar.gz` を削除する。
- `uvx twine check --strict dist/*` が shell の glob 展開で失敗する場合は、環境に合わせて `dist\*` で再実行する。

### 4.4 archive 内容確認

`uv build` 後に wheel / sdist の中身を確認する。

| 確認対象 | 期待値 |
|----------|--------|
| wheel metadata | `Name: nyxpy-fw`, `Version: 0.1.0` または公開版 version |
| wheel package | `nyxpy\__main__.py`, `nyxpy\py.typed`, `nyxpy\framework\...` を含む |
| wheel entry points | `nyxpy`, `nyx-cli`, `nyx-gui` を含む |
| sdist | build に必要な tracked files を含む |
| sdist 除外 | `.pypirc`, `.nyxpy`, `dist\`, `site\`, ローカル作業用 `macros\`, `resources\` を含まない |

### 4.5 TestPyPI の依存解決

TestPyPI だけを index にすると、NyX の依存ライブラリが TestPyPI に存在せず解決できない。動作確認では、NyX の配布物だけを TestPyPI から取得し、依存は PyPI から解決する。

第一候補は `--no-deps` で TestPyPI から wheel を取得し、その wheel を通常の PyPI index で install する方法である。これにより、依存名が TestPyPI 側に存在した場合の混入も避けられる。

```console
python -m venv .venv-testpypi
.venv-testpypi\Scripts\python -m pip install --upgrade pip
.venv-testpypi\Scripts\python -m pip download --no-deps --index-url https://test.pypi.org/simple/ --dest .tmp-testpypi nyxpy-fw==0.1.0
.venv-testpypi\Scripts\python -m pip install .tmp-testpypi\nyxpy_fw-0.1.0-py3-none-any.whl
.venv-testpypi\Scripts\python -c "import nyxpy; print(nyxpy.__name__)"
.venv-testpypi\Scripts\nyxpy --help
```

代替手順として、TestPyPI を主 index、PyPI を追加 index にする方法も使える。

```console
.venv-testpypi\Scripts\python -m pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ nyxpy-fw==0.1.0
```

ただし、この方法は依存 package 名が TestPyPI に存在する場合に TestPyPI 側の artifact を選ぶ可能性があるため、初回公開の確認では wheel 取得分離方式を優先する。POSIX shell では `.venv-testpypi\Scripts\python` を `.venv-testpypi/bin/python`、`.venv-testpypi\Scripts\nyxpy` を `.venv-testpypi/bin/nyxpy` に読み替える。

### 4.6 TestPyPI / PyPI publish 手順

publish の詳細手順は [PyPI 公開手順書](PYPI_PUBLICATION_RUNBOOK.md) に従う。本仕様書では判断と完了条件だけを保持する。

| target | 実行前条件 | 実行方法 |
|--------|------------|----------|
| TestPyPI | TestPyPI pending publisher と GitHub environment `testpypi` を作成済み | `Publish Python Package` workflow を `target=testpypi` で手動実行 |
| PyPI | TestPyPI 検証完了、PyPI pending publisher と GitHub environment `pypi` を作成済み、`v*` tag 作成済み | `Publish Python Package` workflow を `target=pypi` で tag から手動実行 |

### 4.7 Trusted Publishing の手動手続き

Trusted Publishing は workflow だけでは完結しない。repository owner 側で次の手続きが必要である。

| 場所 | 手続き | 備考 |
|------|--------|------|
| TestPyPI | account sidebar の `Publishing` から pending publisher を追加する | TestPyPI と PyPI は別管理 |
| PyPI | account sidebar の `Publishing` から pending publisher を追加する | 本番 publish 前に実施する |
| GitHub repository | environment `testpypi` / `pypi` を作成する | workflow の `environment.name` と PyPI 側の environment を一致させる |
| GitHub repository | `pypi` environment に required reviewers を設定する | 本番 publish の誤実行を防ぐ |
| GitHub Actions workflow | publish job に `permissions: id-token: write` があることを確認する | OIDC token 発行に必要 |
| PyPI / TestPyPI account | 2FA と verified email を確認する | project 管理の前提として整える |

pending publisher は project 名を予約しない。登録後、初回 publish 前に別ユーザが同名 project を作成した場合、その pending publisher は無効になる。配布名を決めたら、pending publisher 登録から TestPyPI / PyPI publish までを同日中に進める。

### 4.8 ロールバック方針

PyPI 本番 publish 後は同じ version の再アップロードができない。失敗時の対応は次の順序とする。

| 状況 | 対応 |
|------|------|
| README / metadata の軽微な誤り | 次 version で修正する |
| wheel 内容の不足 | 原因を修正し、patch version を上げて再 publish する |
| 配布名の誤り | 本番 publish 前なら中止して改名する。本番 publish 後は原則として同名 project を継続する |
| secrets 混入 | 該当 secret を失効し、project owner として公開停止または削除可否を PyPI 側で判断する |

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| lock | `uv lock --check` | lockfile が `pyproject.toml` と一致していること |
| lint | `uv run ruff check .` | Python コードと import 整列が規約に沿うこと |
| type | `uv run ty check src/nyxpy --output-format concise --no-progress` | 公開 package の型検査が通ること |
| unit / integration | `uv run pytest` | 既存テストが通ること |
| dead code | `uv run vulture src tests examples macros --min-confidence 80` | 未使用コード候補を確認し、リリース阻害要因を残さないこと |
| docs | `uv run --no-sync mkdocs build --strict` | GitHub Pages 用 docs が strict build できること |
| package build | `uv build` | sdist / wheel を生成できること |
| metadata | `uvx twine check --strict dist/*` | PyPI が受理可能な metadata であること |
| archive inspection | wheel / sdist 内容確認 | `py.typed`、entry point、不要資材の混入有無を確認する |
| TestPyPI install | clean venv install | TestPyPI 版の wheel と PyPI 上の依存で `import nyxpy` と `nyxpy --help` が動くこと |
| PyPI install | clean tool install | 本番公開版を `uv tool install nyxpy-fw` で導入できること |
| Python 3.14 gate | 3.14 CI / install 確認 | `requires-python` を広げる場合だけ実施し、依存解決とテスト通過を確認する |

## 6. 実装チェックリスト

- [x] `dist\*.whl`, `dist\*.tar.gz`, `build\`, `*.egg-info`, `src\*.egg-info`, `site\` を削除する
- [x] `.pypirc` を publish 手順から外し、Git 管理対象や archive に含まれないことを確認する
- [x] 配布名を `nyxpy-fw` に最終決定する
- [x] `pyproject.toml` の `name`、metadata、dependencies、scripts、URLs を確定名に更新する
- [ ] Python 3.14 は初回公開対象外とし、`requires-python = ">=3.12,<3.14"` を維持する
- [x] README と docs の install 導線が `uv tool install <配布名>` と `nyxpy ...` に揃っていることを確認する
- [x] `uv lock --check` を実行する
- [x] `uv run ruff check .` を実行する
- [x] `uv run ty check src/nyxpy --output-format concise --no-progress` を実行する
- [x] `uv run pytest` を実行する
- [x] `uv run vulture src tests examples macros --min-confidence 80` を実行する
- [x] `uv run --no-sync mkdocs build --strict` を実行する
- [x] `uv build` を実行する
- [x] `uvx twine check --strict dist/*` を実行する
- [x] wheel / sdist 内容を確認する
- [x] TestPyPI account sidebar で pending publisher を登録する
- [x] GitHub environment `testpypi` を確認または作成する
- [x] `target=testpypi` で publish workflow を実行する
- [ ] TestPyPI から `--no-deps` で wheel を取得し、依存は PyPI から install して動作確認する
- [ ] PyPI account sidebar で pending publisher を登録する
- [x] GitHub environment `pypi` を確認または作成し、required reviewers を設定する
- [ ] release commit と `v0.1.0` tag を作成する
- [ ] `target=pypi` で publish workflow を `v*` tag から実行する
- [ ] PyPI project page と `uv tool install <配布名>` を確認する
