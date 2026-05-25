# マクロのテスト

NyX の通常の pytest 設定は、`tests` と `macros` を収集します。マクロ固有の計算・判定・設定変換は `Command` から分離し、通常の単体テストで確認します。

## 配置

| 対象 | 配置 |
|------|------|
| フレームワーク本体 | `tests\unit`, `tests\integration`, `tests\hardware`, `tests\perf` |
| ローカル作業中のマクロ | `macros\<macro_id>\test_*.py` |

## 純粋ロジックのテスト

`Command` を必要としない処理を先に分離します。

```python
def test_sample_config_from_args() -> None:
    cfg = SampleConfig.from_args({"count": "3"})

    assert cfg.count == 3
```

新しい mock 用の公開 helper はまだ用意していないため、`Command` の複雑な偽装を前提にしたテスト設計にはしません。

## 実機テスト

キャプチャデバイスやシリアルデバイスが必要なテストには `@pytest.mark.realdevice` を付けます。

```python
import pytest


@pytest.mark.realdevice
def test_macro_with_real_device() -> None:
    ...
```

実機なしで確認する場合:

```powershell
uv run pytest tests macros -m "not realdevice"
```

## よく使う検証コマンド

```powershell
uv run ruff format .
uv run ruff check .
uv run pytest tests macros
```

`macros\` は Git 管理外の作業場所なので、Ruff の通常探索では `.gitignore` により対象外になります。ローカルマクロを明示的に確認する場合は次のコマンドを使います。

```powershell
uv run ruff format macros --no-respect-gitignore
uv run ruff check macros --no-respect-gitignore
```

リポジトリ内の参考実装をメンテナが確認する場合は、`examples\tests` を明示します。

```powershell
uv run pytest examples/tests
```
