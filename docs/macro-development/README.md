# マクロ開発者向けドキュメント

NyX でマクロを実装する人と、マクロ実装を担当する AI エージェント向けの案内です。現時点の配布パッケージは未公開です。将来の PyPI 配布名は `nyxfw`、Python のインポート名は `nyxpy` としますが、現在はこのリポジトリをクローンして `uv sync` した環境を前提にします。

## 関連文書

| 文書 | 用途 |
|------|------|
| [agent-brief.md](agent-brief.md) | AI エージェントに渡す要点。配置、依存、公開 API、検証コマンドをまとめます。 |
| [macro-template.md](macro-template.md) | `macros\<macro_id>` と `resources\<macro_id>` に置く雛形、任意の `macro.toml`、完了前確認。 |

詳細資料は Phase 2 で追加します。予定している文書は `macro-layout.md`, `macro-lifecycle.md`, `command-api.md`, `settings-and-resources.md`, `manifest.md`, `testing.md`, `nintendo-3ds.md`, `image-processing.md` です。

## 推奨配置

実装者が編集するマクロ本体と資材は、リポジトリ直下のローカル作業領域に置きます。

```text
macros\<macro_id>\
  macro.py
  config.py              # 任意。設定値や純粋ロジックを分離する場合に使う
  test_logic.py          # 任意。Command に依存しないロジックの単体テスト

resources\<macro_id>\
  settings.toml
  assets\
    template.png
```

`examples\macros` と `examples\resources` は参照用サンプルの置き場です。利用者のマクロ配置先ではありません。完成したサンプルを公開するときだけ、実装済みマクロを `examples\` 配下へコピーして、対応する `examples\tests` を追加します。

## 最小構成の例

`macros\sample_turbo\macro.py`:

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
        if frame is not None:
            cmd.save_img("sample_turbo_result.png", frame)

    def finalize(self, cmd: Command) -> None:
        cmd.release()
```

`settings_path = "resource:settings.toml"` は `resources\sample_turbo\settings.toml` を参照します。`cmd.capture()` はキャプチャフレームがない場合に `None` を返すため、画像処理や保存の前に必ず確認します。

## 自動検出の条件

軽量マクロは、次のどちらかに `MacroBase` 派生クラスを 1 つだけ置くと自動検出されます。

- `macros\<macro_id>.py`
- `macros\<macro_id>\macro.py`

`macros\<macro_id>\__init__.py` にも `MacroBase` 派生クラスを置く場合、`macro.py` と両方に置くとエントリーポイントが曖昧になり、読み込みに失敗します。複数のエントリーポイント、明示的なメタデータ、設定ファイル指定が必要な場合だけ `macro.toml` を使います。

## 実装時の制約

- マクロは `nyxpy.framework.*` と、同じマクロ配下または共有部品だけへ依存させます。
- `macros\xxx` から `macros\yyy` を直接インポートしません。複数マクロで使う処理は共有部品へ切り出します。
- コントローラー操作、待機、キャプチャ、通知、ログは `Command` 経由に集約します。
- 乱数計算、画像判定、設定変換などの副作用がない処理は関数へ分離し、`Command` なしで単体テストできるようにします。
- `macro.toml` や設定ファイルに保存する環境に依存しないパス表記では `/` を使います。Windows のファイル表示例では `\` を使ってよいですが、設定値には `assets/template.png` のように書きます。

## 検証コマンド

```powershell
uv run ruff format .
uv run ruff check .
uv run pytest tests macros examples/tests
```

実機が必要なテストは `@pytest.mark.realdevice` を付けます。実機なしで走らせる場合は次を使います。

```powershell
uv run pytest tests macros examples/tests -m "not realdevice"
```

## サンプル一覧

| サンプル | 実装内容 |
|----------|------------|
| `examples\macros\sample_turbo_a_macro.py` | ボタン入力、ログ、キャプチャ保存、通知の最小例 |
| `examples\macros\nsmb_sort_or_splode` | 3DS touch、テンプレートマッチング、`settings_path = "resource:settings.toml"` |
| `examples\macros\frlg_initial_seed` | OCR、CSV 出力、認識ロジック分離、実行ごとの出力への保存 |
| `examples\macros\frlg_id_rng` | キーボード配列、ソフトリセット補助、フレーム走査 |

