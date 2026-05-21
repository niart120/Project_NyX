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

## 2. 適用済みルール

`pyproject.toml` では Google convention を使い、次のルールを有効にする。

| ルール | 目的 | 対象外 |
|--------|------|--------|
| `D100` | module の責務を明示する。 | `tests\`, `examples\tests\`, `conftest.py` |
| `D101` | public class の責務境界を明示する。 | `tests\`, `examples\tests\` |
| `D103` | public function の責務を明示する。 | `tests\`, `examples\tests\` |
| `D104` | package の責務を明示する。 | なし |
| `D105` | magic method の意図を明示する。 | なし |
| `D107` | constructor 固有の依存・副作用を明示する。 | `tests\`, `examples\tests\` |
| `D2` | docstring の空行構造を揃える。 | なし |
| `D3` | docstring の引用符・エスケープ構造を揃える。 | なし |
| `D403` | 先頭語の大文字化を揃える。 | なし |
| `D417` | Google style の `Args:` と実引数を揃える。 | なし |

`D415` は有効にしない。Ruff は日本語の `。` を終端句読点として扱わないため、説明として正しい日本語 docstring に不要な修正を強制する。

## 3. D101 / D107 適用方針

D101 と D107 は、`src\nyxpy\`, `examples\macros\`, `macros\` を clean にする前提で扱う。class と constructor の情報をどこへ置くかを先に決め、違反を解消してから `select` に追加する。

### 3.1 最終状態

最終状態は次の通りにする。

| 領域 | D101 | D107 |
|------|------|------|
| `src\nyxpy\` | 適用する。 | 適用する。 |
| `examples\macros\` | 適用する。 | 適用する。 |
| `macros\` | 適用する。 | 適用する。 |
| `tests\` | 原則対象外。 | 対象外。 |
| `examples\tests\` | 原則対象外。 | 対象外。 |

テスト用 helper class では、class docstring を強制するより、テスト名、fixture 名、assertion を読みやすく保つことを優先する。

### 3.2 D101 の役割

D101 は class の責務境界を決めるためのルールである。class docstring には、利用者がその class を選ぶ理由と、誤用しやすい制約を書く。

| class 種別 | 書く内容 |
|------------|----------|
| public API | 何を表すか、どの層から使うか、主要な制約 |
| dataclass / value object | 値の単位、座標系、範囲、immutable かどうか |
| Protocol / Port | 呼び出し元と実装側の責務境界 |
| Adapter / Factory | 何を何へ接続・生成するか |
| Qt widget | GUI 上の役割と主要 signal / 表示対象 |
| サンプルマクロ class | ゲーム内で何を自動化するか、依存する資材や設定 |

避けるべき docstring は次の通り。

```python
class MacroRunner:
    """マクロ runner。"""
```

この説明では、class 名から分かる情報しか増えない。次のように、責務境界と呼び出し元を明示する。

```python
class MacroRunner:
    """`MacroBase` の lifecycle を同期実行し、実行結果へ変換します。"""
```

### 3.3 D107 の役割

D107 は constructor 固有の情報を書くためのルールである。D101 と同じ責務説明を繰り返さない。class 全体の責務は class docstring、生成時の依存・副作用・例外は `__init__` docstring に置く。

| 対象 | 方針 |
|------|------|
| dataclass | field の単純説明を `__init__` に重複させない。値の意味は class docstring に寄せる。 |
| 明示的な `__init__` | 注入依存、外部 resource、side effect、例外、所有権を説明する。 |
| Adapter / Factory | 生成・接続する対象、遅延初期化の有無、close/release の責務を説明する。 |
| Qt widget | 親 widget、signal 接続、保持する service、UI 初期化の副作用を説明する。 |
| サンプルマクロ | 設定・画像資材・実機前提など、生成時に利用者が気にする前提を書く。 |

D107 対応時に constructor の説明が不要に見える class は、class 自体が public である必要があるかも確認する。private 化できるなら `_ClassName` へ寄せ、public API 面を減らす選択肢も持つ。

### 3.4 作業単位

D101 と D107 は同じ設計判断を共有するが、同じコミットに詰め込まない。推奨する作業単位は次の通り。

1. `tests\` と `examples\tests\` の除外方針を `pyproject.toml` に入れる。
2. D101 を `examples\macros\` と macro author 向け公開 API から適用する。
3. D101 を framework core と GUI へ広げる。GUI の内部 widget は「画面上の役割」を中心に書く。
4. D107 を明示的な `__init__` へ適用する。class docstring と重複した文は書かない。
5. D101 / D107 の両方が clean になった時点で `select` に追加する。

## 4. 他の未適用ルールの扱い

| ルール | 方針 |
|--------|------|
| `D102` | 重要だが重い。逃げずに扱うが、method 単位の公開 API 境界を決めてから段階適用する。GUI event handler や Qt override に薄い docstring を強制しない設計が必要。 |
| `D415` | 日本語句読点との衝突が解消されるまで未適用。 |

## 5. 推奨作業順序

1. D101 / D107 を上記方針で cleanup する。
2. D102 の対象を framework public API、macro author public API、GUI internal、test helper に分類する。
3. D102 を段階適用する。Qt override や signal handler には、必要に応じて per-file ignore か private 化を使う。
4. D415 は Ruff が日本語句点を扱えるようになるか、別の整形方針を決めるまで保留する。

## 6. 検証

Docstring ルールを追加する変更では、最低限次を実行する。

```powershell
uv run ruff format .
uv run ruff check .
uv run pytest tests macros examples/tests -m "not realdevice" -q
git diff --check
```

`uv run ruff check . --select D1 --statistics` で残る違反数を記録し、未適用ルールが意図したものだけであることを確認する。
