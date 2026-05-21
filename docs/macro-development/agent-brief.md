# NyX マクロ実装エージェント向け要点

この文書は、AI エージェントに NyX マクロの新規作成・修正を依頼するときに渡す要点です。詳細資料は Phase 2 で追加予定です。現時点で不足する API 詳細は、現行コード、docstring、`examples\macros`、`examples\tests` で確認してください。`spec\framework\rearchitecture` は移行元の参考資料であり、公開契約の正本として扱いません。

## 前提

- 現在の PyPI 配布パッケージは未公開です。将来の配布名は `nyxfw`、インポート名は `nyxpy` です。
- 実装者のマクロ本体は `macros\<macro_id>`、設定・画像資材は `resources\<macro_id>` に置きます。
- `examples\macros` と `examples\resources` は参照用サンプルの置き場であり、利用者の配置先ではありません。
- PowerShell コマンドを使います。bash / sh 前提のコマンドは書きません。

## 必ず守る制約

- マクロは `nyxpy.framework.*` と同じマクロ配下、または共有部品だけに依存させます。
- `macros\xxx` から `macros\yyy` を直接インポートしません。
- 副作用のない処理は純粋関数へ分離し、`Command` なしでテストできるようにします。
- コントローラー操作、待機、キャプチャ、画像入出力、通知、ログは `Command` 経由で行います。
- `cmd.capture()` はフレームがない場合に `None` を返します。画像処理・保存・shape 参照の前に必ず確認します。
- `settings_path` の標準例は `settings_path = "resource:settings.toml"`。
- `resource:` / `project:` / マニフェスト相対パスなど、環境に依存しないパス表記では `/` を使います。例: `assets/template.png`。
- 旧 `static\<macro_name>` 配置は標準探索されません。

## 公開 API の基本インポート

```python
from nyxpy.framework.core.constants import Button, Hat, LStick, RStick
from nyxpy.framework.core.macro.base import MacroBase
from nyxpy.framework.core.macro.command import Command
from nyxpy.framework.core.macro.exceptions import MacroStopException
```

3DS 向け補助:

```python
from nyxpy.framework.core.constants import (
    THREEDS_HD_BOTTOM_SCREEN,
    TouchPoint,
    ThreeDSButton,
    TouchState,
)
```

画像処理:

```python
from nyxpy.framework.core.imgproc import ImageProcessor, OCRProcessor, contains_template, find_template
```

## 最小構成の例

```python
from nyxpy.framework.core.constants import Button
from nyxpy.framework.core.macro.base import MacroBase
from nyxpy.framework.core.macro.command import Command


class SampleMacro(MacroBase):
    description = "短い説明"
    tags = ["sample"]
    settings_path = "resource:settings.toml"

    def initialize(self, cmd: Command, args: dict) -> None:
        self.count = int(args.get("count", 10))
        if self.count <= 0:
            raise ValueError("count must be greater than 0")

    def run(self, cmd: Command) -> None:
        for _ in range(self.count):
            cmd.press(Button.A, dur=0.06, wait=0.08)

        frame = cmd.capture()
        if frame is None:
            cmd.log("capture failed", level="WARNING")
            return
        cmd.save_img("sample_result.png", frame)

    def finalize(self, cmd: Command) -> None:
        cmd.release()
```

## 配置と検出

自動検出される配置:

```text
macros\<macro_id>.py
macros\<macro_id>\macro.py
```

`macro.py` または `__init__.py` のどちらか一方に、そのファイルで定義した `MacroBase` 派生クラスを 1 つだけ置きます。`macro.py` と `__init__.py` の両方に置くとエントリーポイントが曖昧になり、読み込みに失敗します。インポートした基底クラスや他モジュールのクラスは検出候補に数えられません。

複数のエントリーポイント、単一ファイルのマニフェスト、明示的なメタデータが必要な場合だけ `macro.toml` を使います。

```toml
[macro]
id = "sample_macro"
entrypoint = "macros.sample_macro.macro:SampleMacro"
settings = "resource:settings.toml"
```

## 設定・資材・出力

```text
resources\<macro_id>\
  settings.toml
  assets\
    template.png
```

- `settings_path = "resource:settings.toml"` は `resources\<macro_id>\settings.toml` を読みます。
- `cmd.load_img("template.png")` は `resources\<macro_id>\assets\template.png` を優先し、次にマクロパッケージ内の `assets` を探します。
- `cmd.save_img("debug/frame.png", frame)` と `cmd.artifacts.open_output(...)` は実行ごとの出力へ保存します。
- `cmd.load_img()` / `cmd.save_img()` のファイル名は、リソース起点の相対パスにします。

## Command の主な用途

| API | 用途 |
|-----|------|
| `cmd.press(Button.A, dur=0.1, wait=0.1)` | 押下、解放、待機 |
| `cmd.hold(...)`, `cmd.release(...)` | 押しっぱなしと解放 |
| `cmd.wait(sec)` | 中断要求を確認しながら待機 |
| `cmd.capture(crop_region=None, grayscale=False)` | 1280x720 にリサイズしたキャプチャ取得。失敗時は `None` |
| `cmd.load_img(name)`, `cmd.save_img(name, image)` | 資材の読み込み、実行ごとの出力への画像保存 |
| `cmd.keyboard(text)`, `cmd.type(key)` | キーボード入力 |
| `cmd.notify(text, img=None)` | 外部通知 |
| `cmd.log(message, level="INFO")` | ユーザ向けログ |
| `cmd.touch(...)`, `cmd.touch_down(...)`, `cmd.touch_up(...)` | 3DS touch 対応プロトコル用 |
| `cmd.disable_sleep(enabled=True)` | 対応プロトコルのスリープ制御 |

## テスト方針

- 副作用のない計算・判定・設定変換は通常の pytest で単体テストします。
- 実機が必要なテストには `@pytest.mark.realdevice` を付けます。
- pytest は `tests`, `macros`, `examples\tests` を収集します。
- 公開サンプルのテストは `examples\tests` に置きます。

```powershell
uv run ruff format .
uv run ruff check .
uv run pytest tests macros examples/tests
```

実機なしで確認する場合:

```powershell
uv run pytest tests macros examples/tests -m "not realdevice"
```

## 完了前チェック

- `macros\<macro_id>` と `resources\<macro_id>` の対応が取れている。
- `settings_path = "resource:settings.toml"` と `resources\<macro_id>\settings.toml` が一致している。
- `cmd.capture()` の戻り値 `None` を処理している。
- `finalize()` で必要な `cmd.release()` や後片付けを行っている。
- ロジック関数の単体テストを追加している。
- `uv run ruff check .` と該当 pytest が通る。

