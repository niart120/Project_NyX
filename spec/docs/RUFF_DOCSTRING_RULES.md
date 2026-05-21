# Ruff docstring ルール適用方針

> **文書種別**: 運用方針。Ruff の pydocstyle `Dxxx` 系ルールを NyX に段階適用するための判断基準と作業順序を定義する。
> **対象領域**: `pyproject.toml`, `src\nyxpy\`, `examples\macros\`, `macros\`, `tests\`, `examples\tests\`
> **目的**: docstring を公開 API と AI agent の参照情報として育てつつ、薄い説明や日本語句読点との衝突を避ける。
> **関連ドキュメント**: `spec/docs/MACRO_DEVELOPMENT_DOCUMENTATION_PLAN.md`, `docs/macro-development/README.md`

## 1. 基本方針

Docstring は、コードから分かる実装手順ではなく、利用者や AI agent が API の責務、入力、戻り値、例外、制約を判断するための近接仕様として扱う。

Ruff の `Dxxx` 系ルールは一括適用しない。対象を次の単位に分け、既存違反を解消してから `select` に追加する。

| 対象 | 扱い |
|------|------|
| `src\nyxpy\` | 原則として適用対象。公開 API と内部 API の境界を明確にする。 |
| `examples\macros\` | 適用対象。サンプルは利用者と AI agent の参照実装として扱う。 |
| `macros\` | 適用対象。ローカル作業用だが pytest 対象であり、マクロ実装の品質基準に合わせる。 |
| `tests\` | 原則として欠落 docstring ルールの対象外。テスト名と assertion を仕様として読む。 |
| `examples\tests\` | 原則として欠落 docstring ルールの対象外。サンプルの仕様はテスト名で表す。 |

## 2. 現在の適用状況

`pyproject.toml` では Google convention を使い、次のルールを有効にする。

| ルール | 状態 | 判断 |
|--------|------|------|
| `D100` | 有効 | module docstring を要求する。`tests\` と `examples\tests\` は除外する。 |
| `D103` | 有効 | public function docstring を要求する。`tests\` と `examples\tests\` は除外する。 |
| `D104` | 有効 | package docstring を要求する。 |
| `D105` | 有効 | magic method docstring を要求する。 |
| `D2` | 有効 | 空行構造を揃える。 |
| `D3` | 有効 | docstring の引用符・エスケープ構造を揃える。 |
| `D403` | 有効 | 先頭語の大文字化。英語識別子を先頭に置く場合は日本語として自然な文に直す。 |
| `D417` | 有効 | Google style の `Args:` と実引数を揃える。 |

`D415` は有効にしない。Ruff は日本語の `。` を終端句読点として扱わないため、説明として正しい日本語 docstring に不要な修正を強制する。

## 3. D101 / D107 の判断

### 3.1 D101: public class docstring

`D101` は次の候補として扱う。class docstring は `pydoc`、エディタ補完、AI agent の読解に効くため、`src\nyxpy\` と `examples\macros\` では価値が高い。

ただし、単純に「クラス名を日本語化しただけ」の docstring を増やすと保守負債になる。適用時は次を最低基準にする。

| class 種別 | 書く内容 |
|------------|----------|
| public API | 何を表すか、どの層から使うか、主要な制約 |
| dataclass / value object | 値の単位、座標系、範囲、immutable かどうか |
| Protocol / Port | 呼び出し元と実装側の責務境界 |
| Adapter / Factory | 何を何へ接続・生成するか |
| Qt widget | GUI 上の役割と主要 signal / 表示対象 |
| サンプルマクロ class | ゲーム内で何を自動化するか、依存する資材や設定 |

`tests\` と `examples\tests\` は原則として `D101` の対象外にする。テスト用 helper class に薄い説明を追加するより、テスト名と fixture 名を読みやすく保つ方が有用である。

### 3.2 D107: public `__init__` docstring

`D107` は `D101` より後に扱う。理由は、constructor の説明を class docstring と `Args:` のどちらへ寄せるかを先に統一しないと、同じ情報を class と `__init__` の両方に重複させやすいためである。

基本方針は次の通り。

| 対象 | 方針 |
|------|------|
| dataclass | class docstring で値の意味を説明し、生成時引数と同じ field は `__init__` docstring を薄くしない。 |
| 明示的な `__init__` を持つ public class | side effect、外部 resource、所有権、例外がある場合に `__init__` docstring を書く。 |
| Adapter / Port 実装 | 注入される依存と lifecycle を `__init__` または class docstring に明記する。 |
| Qt widget | parent、signal 接続、保持する service を必要に応じて説明する。 |
| tests | 対象外。 |

`D107` を有効にする場合は、まず `D101` を適用して class の責務を固める。その後、明示的な `__init__` のうち class docstring だけでは不足するものに絞って説明を追加する。

## 4. 残ルールの扱い

| ルール | 方針 |
|--------|------|
| `D102` | 重要だが重い。逃げずに扱うが、method 単位の公開 API 境界を決めてから段階適用する。GUI event handler や Qt override に薄い docstring を強制しない設計が必要。 |
| `D107` | `D101` 後に適用する。constructor 情報の重複を避ける。 |
| `D415` | 日本語句読点との衝突が解消されるまで未適用。 |

## 5. 推奨作業順序

1. `D101` を `src\nyxpy\`, `examples\macros\`, `macros\` に適用する。`tests\` と `examples\tests\` は `per-file-ignores` に追加する。
2. `D101` の追加 docstring が class の責務を説明しているかをレビューする。
3. `D107` の残件を、明示的な `__init__` が外部 resource、side effect、依存注入、例外を持つものに分類する。
4. `D107` を適用する。dataclass の単純 field 説明は class docstring 側に寄せる。
5. `D102` の対象を framework public API、macro author public API、GUI internal、test helper に分類し、段階適用する。

## 6. 検証

Docstring ルールを追加する変更では、最低限次を実行する。

```powershell
uv run ruff format .
uv run ruff check .
uv run pytest tests macros examples/tests -m "not realdevice" -q
git diff --check
```

`uv run ruff check . --select D1 --statistics` で残る違反数を記録し、未適用ルールが意図したものだけであることを確認する。
