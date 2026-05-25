# Ruff docstring ルール

> **文書種別**: 運用ルール。NyX の docstring 記述と Ruff pydocstyle `Dxxx` 系ルールの扱いを定義する。
> **対象領域**: `pyproject.toml`, `src\nyxpy\`, `examples\macros\`, `macros\`, `tests\`, `examples\tests\`
> **目的**: docstring を公開 API と AI agent の参照情報として保ち、薄い説明や日本語句読点との衝突を避ける。
> **関連ドキュメント**: `spec/docs/MACRO_DEVELOPMENT_DOCUMENTATION_PLAN.md`, `docs/macro-development/README.md`

## 1. Docstring の位置付け

Docstring は、利用者や AI agent が API の責務、入力、戻り値、例外、制約を判断するための近接仕様として扱う。コードを読めば分かる実装手順や名前の言い換えは書かない。

次の情報を優先して書く。

| 対象 | 書く内容 |
|------|----------|
| module / package | その単位が提供する責務と主な利用層 |
| public class | 何を表すか、どの層から使うか、主要な制約 |
| public function / method | 入力、戻り値、例外、副作用 |
| `__init__` | 注入依存、外部 resource、初期化時の副作用 |
| magic method | 通常の method と異なる意味付けや返す表現 |

## 2. 対象範囲

| 領域 | 扱い |
|------|------|
| `src\nyxpy\` | 適用対象。公開 API と内部 API の境界を docstring で補う。 |
| `examples\macros\` | 適用対象。利用者と AI agent が参照するサンプル実装として扱う。 |
| `macros\` | 適用対象。ローカル作業用だが pytest 対象であり、マクロ実装の品質基準に合わせる。 |
| `tests\` | 欠落 docstring ルールの対象外。テスト名、fixture 名、assertion を仕様として読む。 |
| `examples\tests\` | 欠落 docstring ルールの対象外。サンプルの仕様はテスト名で表す。 |

`macros\` は `.gitignore` の対象であるため、通常の `ruff format .` と `ruff check .` には含まれない。ローカルマクロを公開サンプルへ移す前の確認では、次のように `--no-respect-gitignore` を付けて明示的に対象化する。

```powershell
uv run ruff format macros --no-respect-gitignore
uv run ruff check macros --no-respect-gitignore
```

## 3. Ruff 設定

`pyproject.toml` では Google convention を使う。現在有効な docstring ルールは次の通り。

| ルール | 目的 | 対象外 |
|--------|------|--------|
| `D100` | module の責務を明示する。 | `tests\`, `examples\tests\`, `conftest.py` |
| `D101` | public class の責務を明示する。 | `tests\`, `examples\tests\` |
| `D103` | public function の責務を明示する。 | `tests\`, `examples\tests\` |
| `D104` | package の責務を明示する。 | なし |
| `D105` | magic method の意図を明示する。 | なし |
| `D107` | constructor 固有の依存・副作用を明示する。 | `tests\`, `examples\tests\` |
| `D2` | docstring の空行構造を揃える。 | なし |
| `D3` | docstring の引用符・エスケープ構造を揃える。 | なし |
| `D402` | function docstring の先頭行に signature を重複させない。 | なし |
| `D403` | Google convention として先頭語の大文字化を揃える。 | なし |
| `D405` | section header の先頭大文字化を揃える。 | なし |
| `D406` | section header 直後の改行を揃える。 | なし |
| `D407` | section underline の有無を揃える。 | なし |
| `D408` | section 名直後の underline を揃える。 | なし |
| `D409` | section underline の長さを揃える。 | なし |
| `D410` | section 後の空行を揃える。 | なし |
| `D411` | section 前の空行を揃える。 | なし |
| `D412` | section header と本文の間に余分な空行を置かない。 | なし |
| `D413` | 最後の section 後に空行を置く。 | なし |
| `D414` | 空の section を残さない。 | なし |
| `D417` | Google style の `Args:` と実引数を揃える。 | なし |
| `D418` | `@overload` の個別定義に docstring を置かない。 | なし |
| `D419` | 空の docstring を残さない。 | なし |

`D415` は有効にしない。Ruff は日本語の `。` を終端句読点として扱わないため、説明として正しい日本語 docstring に不要な修正を強制する。

Ruff / pydocstyle は `docstring_style = "google"` のとき、`Args:`, `Returns:`, `Raises:` などの Google style section が現れた場合の構造を検査する。reStructuredText style の `:param name:` / `:return:` / `:raises:` を Google style 違反として検出するルールはない。そのため、API reference を mkdocstrings の Google style で生成する公開 API では、Ruff だけに頼らず `:param` / `:return` / `:raises` の残存を検索して確認する。

Ruff formatter の docstring 対応は、`format.docstring-code-format` による docstring 内コード例の整形に限られる。NyX では有効化し、doctest、Markdown、reStructuredText の Python コード例を通常の formatter と同じ方針で整形する。JSON や TOML など Python 以外のコードブロックには言語名を明示し、未指定 fenced code block が Python として整形されないようにする。

Google style の section header、section 前後の空行、空 section は formatter では整形しない。Ruff formatter の設定項目にも section 構造を整形する項目はないため、`D405` から `D414` までは lint 側で扱う。

## 4. 記述ルール

Docstring は一文で足りる場合は一文でよい。複数の引数、戻り値、例外を説明する場合は Google style の `Args:`, `Returns:`, `Raises:` を使う。

避けるべき記述は次の通り。

```python
class MacroRunner:
    """マクロ runner。"""
```

この説明では、class 名から分かる情報しか増えない。次のように責務と結果を明示する。

```python
class MacroRunner:
    """`MacroBase` の lifecycle を同期実行し、実行結果へ変換します。"""
```

## 5. 検証

Docstring ルールを追加または変更する場合は、最低限次を実行する。

```powershell
uv run ruff format .
uv run ruff check .
uv run pytest tests macros examples/tests -m "not realdevice" -q
git diff --check
```

ローカルマクロを公開サンプルへ移す前には、`.gitignore` 対象の `macros\` も明示的に確認する。

```powershell
uv run ruff format macros --no-respect-gitignore
uv run ruff check macros --no-respect-gitignore
```

未適用の `Dxxx` 系ルールを確認する場合は、次を実行する。

```powershell
uv run ruff check . --select D --statistics
```
