# マクロのテスト

NyX の pytest 設定は、`tests`, `macros`, `examples\tests` を収集します。マクロ固有の計算・判定・設定変換は `Command` から分離し、通常の単体テストで確認します。

## 配置

| 対象 | 配置 |
|------|------|
| フレームワーク本体 | `tests\unit`, `tests\integration`, `tests\hardware`, `tests\perf` |
| ローカル作業中のマクロ | `macros\<macro_id>\test_*.py` |
| 公開サンプル | `examples\tests\unit\macros\test_<macro_id>.py` |
| 公開サンプルの性能確認 | `examples\tests\perf\test_<macro_id>_perf.py` |

## 純粋ロジックのテスト

`Command` を必要としない処理を先に分離します。

```python
def test_sample_config_from_args() -> None:
    cfg = SampleConfig.from_args({"count": "3"})

    assert cfg.count == 3
```

既存サンプルでは、`examples\tests\unit\macros` がこの方針で設定変換、乱数計算、画像判定をテストしています。新しい mock 用の公開 helper はまだ用意していないため、`Command` の複雑な偽装を前提にしたテスト設計にはしません。

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
uv run pytest tests macros examples/tests -m "not realdevice"
```

## よく使う検証コマンド

```powershell
uv run ruff format .
uv run ruff check .
uv run pytest tests macros examples/tests
```

`macros\` は Git 管理外の作業場所なので、Ruff の通常探索では `.gitignore` により対象外になります。公開サンプルとして `examples\macros` へ移す前に、次のコマンドでローカルマクロも確認します。

```powershell
uv run ruff format macros --no-respect-gitignore
uv run ruff check macros --no-respect-gitignore
```

公開サンプルだけ確認する場合:

```powershell
uv run pytest examples/tests
```

