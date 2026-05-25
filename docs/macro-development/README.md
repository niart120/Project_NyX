# マクロ開発者向けドキュメント

NyX でマクロを実装する人と、マクロ実装を担当する AI エージェント向けの案内です。PyPI 配布名は `nyxfw`、Python のインポート名は `nyxpy` です。配布パッケージは公開準備中のため、現時点で動作確認する場合はこのリポジトリをクローンして `uv sync` した環境を使います。

## 関連文書

| 文書 | 用途 |
|------|------|
| [agent-brief.md](agent-brief.md) | AI エージェントに渡す要点。配置、依存、公開 API、検証コマンドをまとめます。 |
| [macro-template.md](macro-template.md) | `macros/<macro_id>` と `resources/<macro_id>` に置く雛形、任意の `macro.toml`、完了前確認。 |
| [macro-layout.md](macro-layout.md) | `macros/`, `resources/` の使い分けと依存方向。 |
| [macro-lifecycle.md](macro-lifecycle.md) | `MacroBase` のメタデータ、`initialize`, `run`, `finalize` の責務。 |
| [command-api.md](command-api.md) | `Command` の操作 API、待機、キャプチャ、画像入出力、通知、ログ。 |
| [settings-and-resources.md](settings-and-resources.md) | `settings_path`, `resource:`, 画像資材、実行ごとの出力。 |
| [manifest.md](manifest.md) | `macro.toml` が必要な場面、entrypoint、metadata。 |
| [testing.md](testing.md) | 単体テスト、実機テスト、検証コマンド。 |
| [nintendo-3ds.md](nintendo-3ds.md) | 3DS 向け座標、touch、sleep control。 |
| [image-processing.md](image-processing.md) | テンプレートマッチング、OCR、前処理。 |
| [API reference](../api/framework.md) | `MacroBase`, `Command`, constants, imgproc, resources の docstring / 型ヒントから生成する参照文書。 |

## 推奨配置

実装者が編集するマクロ本体と資材は、リポジトリ直下のローカル作業領域に置きます。

```text
macros/<macro_id>/
  macro.py
  config.py              # 任意。設定値や純粋ロジックを分離する場合に使う
  test_logic.py          # 任意。Command に依存しないロジックの単体テスト

resources/<macro_id>/
  settings.toml
  assets/
    template.png
```

## workspace 初期化と雛形生成

公開後の主導線は `uv tool install nyxfw` で `nyxpy` を導入し、workspace 内で次のコマンドを使う形です。

```console
nyxpy init --blank
nyxpy create sample_turbo
```

リポジトリから実行する場合は `uv run` を付けます。

```console
uv run nyxpy init --blank
uv run nyxpy create sample_turbo
```

`nyxpy init` は `sample_macro` も生成します。空の workspace だけを作る場合は `--blank` を使います。`nyxpy create <macro_id>` は既存 workspace の `macros/<macro_id>` と `resources/<macro_id>` に雛形を生成します。

## 最小構成の例

`macros/sample_turbo/macro.py`:

```python
from nyxpy.framework.core.constants import Button
from nyxpy.framework.core.macro.base import MacroBase
from nyxpy.framework.core.macro.command import Command


class SampleTurboMacro(MacroBase):
    description = "Aボタンを指定回数だけ押すサンプル"
    tags = ["sample", "button"]
    settings_path = "resource:settings.toml"

    def initialize(self, cmd: Command, args: dict) -> None:
        self.count = int(args.get("count", 10))
        if self.count <= 0:
            raise ValueError("count must be greater than 0")

    def run(self, cmd: Command) -> None:
        for index in range(1, self.count + 1):
            cmd.press(Button.A, dur=0.06, wait=0.08)
            if index % 5 == 0:
                cmd.log(f"progress: {index}/{self.count}", level="INFO")

        frame = cmd.capture()
        cmd.save_img("sample_turbo_result.png", frame)

    def finalize(self, cmd: Command) -> None:
        cmd.release()
```

`settings_path = "resource:settings.toml"` は `resources/sample_turbo/settings.toml` を参照します。`cmd.capture()` はフレーム未準備時に `FrameNotReadyError` を送出します。

## 自動検出の条件

軽量マクロは、次のどちらかに `MacroBase` 派生クラスを 1 つだけ置くと自動検出されます。

- `macros/<macro_id>.py`
- `macros/<macro_id>/macro.py`

`macros/<macro_id>/__init__.py` にも `MacroBase` 派生クラスを置く場合、`macro.py` と両方に置くとエントリーポイントが曖昧になり、読み込みに失敗します。複数のエントリーポイント、明示的なメタデータ、設定ファイル指定が必要な場合だけ `macro.toml` を使います。

## 実装時の制約

- マクロは `nyxpy.framework.*` と、同じマクロ配下または共有部品だけへ依存させます。
- `macros/xxx` から `macros/yyy` を直接インポートしません。複数マクロで使う処理は共有部品へ切り出します。
- コントローラー操作、待機、キャプチャ、通知、ログは `Command` 経由に集約します。
- 乱数計算、画像判定、設定変換などの副作用がない処理は関数へ分離し、`Command` なしで単体テストできるようにします。
- `macro.toml` や設定ファイルに保存する環境に依存しないパス表記では `/` を使います。設定値には `assets/template.png` のように書きます。

## 検証コマンド

```console
uv run ruff format .
uv run ruff check .
uv run ty check src/nyxpy --output-format concise --no-progress
uv run pytest tests macros
```

実機が必要なテストは `@pytest.mark.realdevice` を付けます。実機なしで走らせる場合は次を使います。

```console
uv run pytest tests macros -m "not realdevice"
```
