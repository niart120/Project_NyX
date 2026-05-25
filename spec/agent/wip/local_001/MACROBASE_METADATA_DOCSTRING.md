# MacroBase metadata docstring 整備仕様書

> **対象モジュール**: `src/nyxpy/framework/core/macro/`
> **目的**: `MacroBase` の公開メタデータ属性を docstring と型ヒントから確認できるようにする
> **関連ドキュメント**: `docs/macro-development/macro-lifecycle.md`, `docs/api/framework.md`
> **既存ソース**: `src/nyxpy/framework/core/macro/base.py`
> **破壊的変更**: なし

## 1. 概要

### 1.1 目的

`MacroBase` のメタデータ属性を公開 API として明示し、API reference、エディタ補完、`pydoc` から最低限の使い方へ到達できる状態にする。特に `settings_path` は Markdown docs で標準例として案内しているため、基底クラス側の型ヒントと docstring に追加する。

### 1.2 用語定義

| 用語 | 定義 |
|------|------|
| MacroBase | ユーザ定義マクロの抽象基底クラス。`initialize` / `run` / `finalize` ライフサイクルを持つ。 |
| メタデータ属性 | マクロ一覧表示、検索、設定読み込みなどに使うクラス属性。 |
| settings_path | マクロごとの設定ファイルの場所を示す属性。標準例は `resource:settings.toml`。 |
| args_schema | 実行引数を `SettingsSchema` で検証するための属性。 |

### 1.3 背景・問題

`docs/macro-development/macro-lifecycle.md` は `description`, `tags`, `args_schema`, `settings_path` を `MacroBase` のメタデータとして説明している。一方で `src/nyxpy/framework/core/macro/base.py` には `settings_path` 属性がなく、API reference では `description`, `tags`, `args_schema` までしか確認できない。`EntryPointLoader` は `getattr(macro_cls, "settings_path", None)` で読み取っているため、実装上は利用可能だが公開 API としての近接説明が不足している。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
|------|------|------|
| API reference から確認できる `MacroBase` メタデータ属性 | 3 件 | 4 件 |
| `settings_path` の説明到達経路 | Markdown docs のみ | Markdown docs、docstring、型ヒント |
| Markdown docs と docstring の矛盾 | `settings_path` が docstring 側にない | 同じ属性集合を説明する |

### 1.5 着手条件

- `docs/macro-development/macro-lifecycle.md` の `settings_path` 説明を正とする。
- `MacroSettingsResolver` の `resource:` / `project:` / manifest 相対 path 制約を変更しない。
- `uv run ruff check src\nyxpy\framework\core\macro\base.py` が着手前に通ること。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
|----------|----------|----------|
| `src/nyxpy/framework/core/macro/base.py` | 変更 | `settings_path` 属性と各メタデータ属性の docstring を整備する。 |
| `docs/macro-development/macro-lifecycle.md` | 変更 | `MacroBase` docstring と同じ属性集合・説明へ揃える。 |
| `tests/unit/framework/macro/test_registry.py` | 変更 | `settings_path` が基底クラス属性として存在しても convention 検出に影響しないことを確認する。 |
| `docs/api/framework.md` | 変更なし | mkdocstrings 生成結果で `settings_path` が表示されることを確認する。 |

## 3. 設計方針

### アーキテクチャ上の位置づけ

`MacroBase` はマクロ実装者が直接継承する公開 API である。メタデータ属性の型ヒントは実行時の読み取り仕様を変えず、`EntryPointLoader` と `MacroSettingsResolver` が既に扱う値を基底クラス上で明文化する。

### 公開 API 方針

`settings_path` を `MacroBase` のクラス属性として追加する。値は `str | Path | None` とし、文字列では `resource:` / `project:` / manifest 相対 path を受け付ける現行仕様を説明する。`Path` を許可する場合はマクロ本体ディレクトリ基準または絶対パスとして扱われることも docstring に含める。

### 後方互換性

破壊的変更なし。既存マクロがクラス属性として `settings_path` を持つ場合、サブクラス属性が基底クラス属性を上書きするため挙動は変わらない。

### レイヤー構成

`MacroBase` は `Command` と `SettingsSchema` の型情報だけに依存する。`MacroSettingsResolver` や `EntryPointLoader` への逆依存は追加しない。説明上の詳細は docstring と Markdown docs に留める。

### 性能要件

| 指標 | 目標値 |
|------|--------|
| マクロ検出時の追加 I/O | 0 |
| `MacroBase` 継承時の追加処理 | 0 |

### 並行性・スレッド安全性

クラス属性と docstring の追加のみであり、スレッドモデルには影響しない。

## 4. 実装仕様

### 公開インターフェース

```python
class MacroBase(ABC):
    """NyX マクロの基底クラス。"""

    description: str = ""
    """一覧表示向けの短い説明文。"""

    tags: list[str] = []
    """検索・分類用のタグ。"""

    args_schema: SettingsSchema | None = None
    """実行引数を検証する schema。未指定の場合は raw args が渡る。"""

    settings_path: str | Path | None = None
    """マクロごとの設定ファイル path。標準例は `resource:settings.toml`。"""
```

### 設定パラメータ

| パラメータ | 型 | デフォルト | 説明 |
|------------|-----|-----------|------|
| `settings_path` | `str | Path | None` | `None` | マクロ設定ファイルの場所。`resource:` は `resources\<macro_id>`、`project:` はプロジェクトルート、接頭辞なし文字列はマクロ本体ディレクトリを基準にする。 |

### エラーハンドリング

| 例外クラス | 発生条件 |
|------------|----------|
| `ConfigurationError` | `settings_path` が空文字、`\`、絶対 POSIX path、`..` を含むなど、`MacroSettingsResolver` の portable path 制約に違反する場合。 |

### シングルトン管理

該当なし。新規 singleton は追加しない。

## 5. テスト方針

| テスト種別 | テスト名 | 検証内容 |
|------------|----------|----------|
| ユニット | `test_convention_definition_inherits_settings_path_default_none` | `MacroBase.settings_path` の既定値が convention 検出後の `MacroDefinition.settings_path` で `None` になる。 |
| ユニット | `test_convention_definition_uses_subclass_settings_path` | サブクラスで指定した `settings_path` が従来通り `MacroDefinition` へ反映される。 |
| ドキュメント | `uv run --no-sync mkdocs build --strict` | API reference に `settings_path` が表示され、Markdown docs と矛盾しない。 |

## 6. 実装チェックリスト

- [ ] `settings_path` の型を確定する。
- [ ] `MacroBase` に `settings_path` 属性を追加する。
- [ ] `MacroBase` の class docstring と属性 docstring を Google style / mkdocstrings 表示に合わせる。
- [ ] `macro-lifecycle.md` のメタデータ表を docstring と同期する。
- [ ] ユニットテストを追加・更新する。
- [ ] `uv run ruff check src\nyxpy\framework\core\macro\base.py tests\unit\framework\macro` を実行する。
- [ ] `uv run --no-sync mkdocs build --strict` を実行する。
