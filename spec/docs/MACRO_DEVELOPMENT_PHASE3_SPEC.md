# マクロ開発者向けドキュメント Phase 3 仕様書

> **文書種別**: Phase 3 詳細仕様。`MACRO_DEVELOPMENT_DOCUMENTATION_PLAN.md` の「パッケージから到達できる情報を増やす」作業を、実装単位へ分解する。
> **対象領域**: `pyproject.toml`, `src\nyxpy\`, `src\nyxpy\cli\`, `docs\macro-development\`, `.github\workflows\`
> **前提**: PyPI 配布名は `nyxfw`、import package 名は `nyxpy` とする。公開 docs は GitHub Pages に統一し、GitHub Wiki は使わない。

## 1. 概要

### 1.1 目的

Phase 3 では、利用者がリポジトリを clone しない状態でも、インストール済みパッケージ、CLI、公開 docs、型情報からマクロ開発に必要な情報へ到達できる状態を作る。Phase 1 / Phase 2 で作成した Markdown docs と公開 API の docstring / 型ヒントを、配布パッケージとドキュメントサイトへ接続する。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| package metadata | `pyproject.toml` の `[project]` に記述する配布名、version、description、authors、license、dependencies、scripts などの情報 |
| PEP 561 | Python package が型情報を配布するための標準。inline type hints を公開する package は `py.typed` を同梱する |
| package data | Python module 以外に wheel / sdist へ同梱するテンプレート、静的ファイル、設定例など |
| scaffold | 新規マクロ用のディレクトリ、`macro.py`、`settings.toml`、必要最小限のテストを生成する導線 |
| API reference | docstring と型ヒントから生成する class / function / method の参照文書 |
| docs URL | GitHub Pages で公開するマクロ開発者向けドキュメントの入口 URL |
| trusted publishing | PyPI API token を repository secret に置かず、GitHub Actions と PyPI の信頼関係で publish する方式 |

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `spec\docs\MACRO_DEVELOPMENT_PHASE3_SPEC.md` | 新規 | Phase 3 の詳細仕様と判断基準 |
| `spec\docs\macro-development-phase3\pep561.md` | 新規 | `py.typed` と型情報公開方針 |
| `spec\docs\macro-development-phase3\type-check-hardening.md` | 新規 | `ty` 型検査厳格化の段階計画 |
| `spec\docs\macro-development-phase3\package-publish.md` | 新規 | `nyxfw` package metadata と publish 手順 |
| `spec\docs\macro-development-phase3\scaffold.md` | 新規 | package data とマクロ雛形生成方針 |
| `spec\docs\macro-development-phase3\cli-guidance.md` | 新規 | `nyx-cli` の docs / scaffold 導線 |
| `spec\docs\macro-development-phase3\api-reference-generation.md` | 新規 | MkDocs + mkdocstrings による API reference 生成 |
| `spec\docs\macro-development-phase3\github-pages.md` | 新規 | GitHub Pages 配信 workflow 方針 |
| `spec\docs\MACRO_DEVELOPMENT_DOCUMENTATION_PLAN.md` | 変更 | Phase 3 詳細仕様への参照を追加 |
| `src\nyxpy\py.typed` | 新規 | PEP 561 marker を追加 |
| `pyproject.toml` | 変更 | 配布名、package metadata、package data、docs 用 dependency group を整備 |
| `src\nyxpy\cli\run_cli.py` | 変更 | `docs` / `scaffold` 導線または subcommand 構成を追加 |
| `src\nyxpy\templates\macro\` | 新規 | package data として同梱するマクロ雛形 |
| `docs\macro-development\README.md` | 変更 | CLI 導線、公開 docs、scaffold 方針を追記 |
| `docs\api\*.md` | 新規 | mkdocstrings で API reference を生成する入口 |
| `mkdocs.yml` | 新規 | MkDocs / mkdocstrings のサイト構成 |
| `.github\workflows\docs.yml` | 新規 | GitHub Pages 向け docs build / deploy workflow |

## 3. 設計方針

### 3.1 到達経路を複数持つ

マクロ実装者は、次のどれかから情報を読む。Phase 3 では各経路の最低限の入口を用意する。

| 到達経路 | 利用場面 | Phase 3 の対応 |
|----------|----------|----------------|
| 型情報 | エディタ補完、型検査、AI agent の静的解析 | `src\nyxpy\py.typed` を追加し、公開 API の型ヒントを配布対象にする |
| package metadata | `uv add nyxfw`, PyPI project page, dependency resolver | `[project]` を `nyxfw` 配布に合わせる |
| CLI | `uv tool install nyxfw` 後の最初の入口 | `nyx-cli docs` と `nyx-cli scaffold` を検討する |
| package data | clone なしで雛形を生成する | 最小テンプレートだけを wheel に同梱する |
| GitHub Pages | 詳細手順と API reference を読む | MkDocs + mkdocstrings で生成する |

### 3.2 Markdown と docstring の責務を分ける

Markdown docs は配置、手順、判断基準、作例を扱う。API reference は docstring と型ヒントから生成し、引数、戻り値、例外、単位の再定義を Markdown に増やさない。

### 3.3 package data は最小限にする

wheel に同梱するのは、新規マクロを始めるためのテンプレートに限定する。`examples\macros` 全体、画像資材、大きいサンプル、テストデータは package data に含めない。サンプルは公開 docs から参照する。

### 3.4 CLI は実行と情報提供を分離する

現行 `nyx-cli` は positional `macro_name` と `--serial` / `--capture` を要求するため、docs 表示や scaffold のようなハードウェア不要操作と相性が悪い。Phase 3 で CLI 導線を実装する場合は、subcommand 化して `run` と情報提供系 command を分離する。

```powershell
uv run nyx-cli run sample_turbo --serial COM3 --capture "Capture Device"
uv run nyx-cli docs
uv run nyx-cli scaffold sample_turbo
```

後方互換性はこの repository のアルファ版ポリシーでは必須ではない。旧形式を残す場合は互換 shim ではなく、現行 UX として必要な理由を明記する。

## 4. 作業仕様

個別の検討内容は次の文書を正とする。この章では実装順を判断するための要約だけを置く。

| 作業 | 詳細仕様 |
|------|----------|
| PEP 561 対応 | `spec\docs\macro-development-phase3\pep561.md` |
| `ty` 型検査厳格化 | `spec\docs\macro-development-phase3\type-check-hardening.md` |
| package metadata / publish | `spec\docs\macro-development-phase3\package-publish.md` |
| scaffold | `spec\docs\macro-development-phase3\scaffold.md` |
| CLI 導線 | `spec\docs\macro-development-phase3\cli-guidance.md` |
| API reference 生成 | `spec\docs\macro-development-phase3\api-reference-generation.md` |
| GitHub Pages 配信 | `spec\docs\macro-development-phase3\github-pages.md` |

### 4.1 PEP 561 対応方針

#### 現状

`src\nyxpy\py.typed` は存在しない。公開 API には型ヒントがあるが、インストール済み package を型検査器が typed package として扱う根拠が不足している。

#### 判断

`src\nyxpy\py.typed` を追加する。NyX は inline type hints を公開する package として扱い、stub package は作らない。

#### 実装内容

| 作業 | 内容 |
|------|------|
| marker 追加 | 空ファイル `src\nyxpy\py.typed` を追加する |
| wheel 同梱確認 | `uv build` 後に wheel 内へ `nyxpy\py.typed` が含まれることを確認する |
| 型公開範囲 | `nyxpy.framework.*` を主対象にし、GUI / CLI の内部実装は公開 API として約束しない |

#### 完了条件

- `uv build` で wheel が作成できる
- wheel 内に `nyxpy\py.typed` が含まれる
- 型ヒントの誤りを見つけた場合は、Phase 2 の docstring / 型ヒント整備対象へ戻して修正する

### 4.2 package metadata / publish 手順

#### 現状

`pyproject.toml` の `[project]` は `name = "project-nyx"` であり、計画済みの PyPI 配布名 `nyxfw` と一致していない。publish workflow は未整備である。

#### 判断

Phase 3 では `nyxfw` として公開できる metadata を整える。実際の publish は、build artifact と手順の確認後に別判断とする。

#### 実装内容

| 項目 | 方針 |
|------|------|
| name | `nyxfw` に変更する |
| import package | `nyxpy` のまま維持する |
| version | 初回 publish 前に `0.1.0` のまま出すか、release 方針に合わせて変更する |
| description | 「Nintendo Switch automation framework」だけでなく、macro framework / CLI / GUI の用途が分かる文へ更新する |
| license | 現行の MIT 表記を維持しつつ、build backend が警告する場合は PEP 639 形式へ寄せる |
| readme | `README.md` を PyPI project page の入口にする |
| scripts | `nyx-cli`, `nyx-gui` を維持する |
| publish | GitHub Actions trusted publishing を第一候補にする。ローカル `.pypirc` や repository secret の API token には依存しない |

#### publish 手順案

```powershell
uv build
uvx twine check dist\*
```

GitHub Actions から publish する場合は、PyPI 側で trusted publisher を設定した後、tag または manual dispatch で publish workflow を実行する。初回は TestPyPI で package name、metadata、console scripts、wheel 内容を確認してから PyPI へ出す。

#### 完了条件

- `uv build` が成功する
- `uvx twine check dist\*` が成功する
- wheel metadata の Name が `nyxfw` になっている
- `nyx-cli` / `nyx-gui` の console script が wheel metadata に含まれる

### 4.3 scaffold 方針

#### 現状

`docs\macro-development\macro-template.md` には雛形説明があるが、package からファイルとして生成する導線はない。利用者が clone しない場合、テンプレートを手作業で転記する必要がある。

#### 判断

Phase 3 では、最小テンプレートを package data として同梱する方針を採る。`examples\macros` は参照用サンプルであり、scaffold の生成元にはしない。

#### 生成対象

```text
macros\<macro_id>\
  macro.py
  config.py
  test_logic.py

resources\<macro_id>\
  settings.toml
  assets\
```

#### テンプレートの制約

| 制約 | 内容 |
|------|------|
| import | `nyxpy.framework.*` と同一 package 内だけを使う |
| settings | `settings_path = "resource:settings.toml"` を標準形にする |
| resources | 画像資材は `resources\<macro_id>\assets` を使う |
| テスト | `Command` に依存しない純粋関数の単体テストを含める |
| 上書き | 既存ファイルがある場合は既定で失敗し、明示オプションでのみ上書きする |

#### 完了条件

- package data から scaffold を生成できる
- 生成後に `uv run ruff check --no-respect-gitignore macros\<macro_id>` が通る
- 生成後に `uv run pytest macros\<macro_id>` が通る

### 4.4 `nyx-cli` 導線案

#### 現状

`nyx-cli` はマクロ実行専用で、`macro_name`、`--serial`、`--capture` が必須である。docs URL 表示や scaffold 生成のようなハードウェア不要操作を追加しにくい。

#### 判断

CLI 導線を実装する場合は subcommand 構成へ移行する。

| command | 役割 | ハードウェア要否 |
|---------|------|------------------|
| `nyx-cli run <macro_name>` | マクロを実行する | 必要 |
| `nyx-cli docs` | 公開 docs URL、agent brief、pydoc 参照方法を表示する | 不要 |
| `nyx-cli scaffold <macro_id>` | `macros\` と `resources\` に雛形を生成する | 不要 |

#### `docs` 出力内容

`nyx-cli docs` はブラウザを自動起動しない。CLI では URL とローカル参照方法を標準出力へ出す。

```text
Macro development docs: https://niart120.github.io/Project_NyX/macro-development/
Agent brief: https://niart120.github.io/Project_NyX/macro-development/agent-brief/
Local API help: python -m pydoc nyxpy.framework.core.macro.command
```

#### 完了条件

- `uv run nyx-cli docs` が serial / capture なしで成功する
- `uv run nyx-cli scaffold sample_turbo` が新規ファイルを生成する
- `uv run nyx-cli run sample_turbo --serial COM3 --capture "Capture Device"` で実行機能に到達できる

### 4.5 MkDocs + mkdocstrings 検証方針

#### 現状

`docs\macro-development\` は Markdown として存在するが、サイト生成設定はない。API reference は手書き Markdown ではなく docstring / 型ヒントから生成する方針である。

#### 判断

MkDocs + mkdocstrings を第一候補にする。Markdown 中心の既存 docs と相性がよく、API reference だけを docstring から差し込めるためである。

#### 実装内容

| ファイル | 内容 |
|----------|------|
| `mkdocs.yml` | site name、nav、theme、plugins、mkdocstrings handler 設定 |
| `docs\api\framework.md` | `nyxpy.framework` 配下の API reference 入口 |
| `docs\macro-development\README.md` | API reference へのリンク追加 |
| `pyproject.toml` | docs dependency group に `mkdocs`, `mkdocstrings[python]` を追加 |

#### API reference の初期対象

| 対象 | 理由 |
|------|------|
| `nyxpy.framework.core.macro.base.MacroBase` | マクロ実装の起点 |
| `nyxpy.framework.core.macro.command.Command` | マクロから呼ぶ副作用 API |
| `nyxpy.framework.core.constants` | Button / stick / 3DS 定数 |
| `nyxpy.framework.core.imgproc` | 画像処理 API |

#### 完了条件

- `uv run mkdocs build --strict` が成功する
- API reference が docstring / 型ヒントを表示する
- heavy dependency の import 実行に依存せず docs build できる

### 4.6 GitHub Pages 配信方針

#### 現状

`.github\workflows\test.yml` は Python CI のみであり、docs build / deploy workflow はない。

#### 判断

GitHub Pages へ生成 docs を配信する workflow を追加する。公開先は repository Pages とし、Wiki は使わない。

#### workflow 方針

| 項目 | 方針 |
|------|------|
| trigger | `workflow_dispatch` と `master` push |
| build | `uv sync --locked --group docs` 後に `uv run mkdocs build --strict` |
| deploy | `actions/configure-pages`, `actions/upload-pages-artifact`, `actions/deploy-pages` を使う |
| pull request | deploy せず build のみ確認する |
| permission | `pages: write`, `id-token: write` を deploy job に限定する |

#### 完了条件

- pull request で docs build が検証される
- `master` push または manual dispatch で Pages artifact を deploy できる
- README / `nyx-cli docs` から公開 URL へ到達できる

## 5. 検証方針

### 5.1 推奨実装順

`package-publish` は最終公開準備として最後に回す。それ以外は、下流が参照する成果物を先に固める順で進める。

| 順番 | 作業 | 理由 | 主な完了条件 |
|------|------|------|--------------|
| 1 | PEP 561 対応 | 最小差分で型情報の公開境界を決められる。以後の API reference と package build の前提になる | `src\nyxpy\py.typed` が wheel に含まれる |
| 2 | `ty` 型検査厳格化 | `py.typed` で公開する型ヒントの妥当性を先に上げる。API reference と publish 前の品質ゲートになる | 公開 API bundle の `ty check` が 0 diagnostics |
| 3 | API reference 生成 | 公開 API の docstring / 型ヒントを docs へ接続する。GitHub Pages workflow は生成対象が固まってから追加する | `uv run mkdocs build --strict` が通る |
| 4 | GitHub Pages 配信 | `nyx-cli docs` と README から参照する公開 URL を確定する | pull request で docs build、`master` / manual dispatch で deploy 可能 |
| 5 | scaffold template | CLI scaffold の入力になる package data を先に作る。`examples\` を生成元にしない方針を実装へ落とす | template から `macros\` / `resources\` の標準配置を生成できる |
| 6 | `nyx-cli` 導線 | docs URL と scaffold template が揃ってから、`docs` / `scaffold` / `run` の subcommand を配線する | `nyx-cli docs` と `nyx-cli scaffold` がハードウェア引数なしで動く |
| 7 | macro-development docs の導線更新 | 実装済みの URL、CLI command、scaffold 仕様に合わせて利用者向け文書を更新する | `docs\macro-development\README.md` から API reference / scaffold / 公開 docs へ到達できる |
| 8 | package-publish | すべての package contents と docs 導線が揃った後、`nyxfw` として metadata / build / publish 手順を確定する | `uv build`, `uvx twine check dist\*`, wheel contents 確認が通る |

この順番にすると、CLI や publish 手順が未確定の URL / template / API reference を先取りして実装する状態を避けられる。`package-publish` で `pyproject.toml` を触る前に docs dependency group や package data 設定が必要になる場合は、その最小差分だけ各作業で入れ、配布名・publish workflow・TestPyPI 手順の確定は最後に残す。

| テスト種別 | コマンド | 検証内容 |
|------------|----------|----------|
| lint | `uv run ruff check .` | Python 変更と docstring 規約に違反しないこと |
| local macro lint | `uv run ruff check --no-respect-gitignore macros\<macro_id>` | scaffold 生成先が `.gitignore` 対象でも lint できること |
| format | `uv run ruff format .` | Python 変更が formatter 済みであること |
| unit / integration | `uv run pytest tests/unit tests/integration` | CLI / framework の既存挙動を壊していないこと |
| type check baseline | `uv run ty check src\nyxpy --output-format concise --no-progress` | PEP 561 公開後に利用者へ見える型ヒントの診断を確認する。現時点では baseline 取得用であり、CI gate にはしない |
| package build | `uv build` | sdist / wheel を作成できること |
| metadata check | `uvx twine check dist\*` | PyPI metadata が妥当であること |
| wheel contents | `$wheel = Get-ChildItem dist\*.whl \| Select-Object -First 1; python -m zipfile --list $wheel.FullName` | `nyxpy\py.typed` と scaffold template が含まれること |
| docs build | `uv run mkdocs build --strict` | Markdown docs と API reference を生成できること |
| CLI docs | `uv run nyx-cli docs` | ハードウェア引数なしで docs URL を表示できること |
| CLI scaffold | `uv run nyx-cli scaffold sample_turbo` | 既定配置へ雛形を生成できること |

## 6. 実装チェックリスト

- [x] Phase 3 詳細仕様を作成する
- [x] Phase 3 の推奨実装順を整理する
- [x] `src\nyxpy\py.typed` を追加する
- [x] `ty` を開発依存に追加し、型検査 baseline を確認する
- [x] `ty` 型検査厳格化仕様を追加する
- [x] MkDocs + mkdocstrings の構成を追加する
- [ ] GitHub Pages workflow を追加する
- [ ] scaffold template を package data として追加する
- [ ] `nyx-cli docs` の導線を追加する
- [ ] `nyx-cli scaffold` の導線を追加する
- [ ] `docs\macro-development\README.md` から公開 docs / API reference / scaffold 導線へリンクする
- [ ] `nyxfw` 向け package metadata を整備する
- [ ] package build と metadata check を通す
- [x] Phase 3 の実装順を `MACRO_DEVELOPMENT_DOCUMENTATION_PLAN.md` に反映する
