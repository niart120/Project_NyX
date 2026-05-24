# マクロのライフサイクル

マクロは `MacroBase` を継承し、`initialize()`, `run()`, `finalize()` の 3 つのメソッドで処理を分けます。各メソッドには `Command` が渡されます。コントローラー操作、待機、キャプチャ、ログ、通知は `Command` 経由で実行します。

## クラス定義

```python
from nyxpy.framework.core.constants import Button
from nyxpy.framework.core.macro.base import MacroBase
from nyxpy.framework.core.macro.command import Command


class SampleMacro(MacroBase):
    description = "Aボタンを指定回数だけ押すサンプル"
    tags = ["sample", "button"]
    settings_path = "resource:settings.toml"

    def initialize(self, cmd: Command, args: dict) -> None:
        self.count = int(args.get("count", 10))
        if self.count <= 0:
            raise ValueError("count must be greater than 0")

    def run(self, cmd: Command) -> None:
        for _ in range(self.count):
            cmd.press(Button.A, dur=0.06, wait=0.08)

    def finalize(self, cmd: Command) -> None:
        cmd.release()
```

## メタデータ

| 属性 | 役割 |
|------|------|
| `description` | GUI や一覧表示に使う説明文です。 |
| `tags` | 検索・分類用のタグです。 |
| `args_schema` | 実行引数を `SettingsSchema` で検証する場合に指定します。 |
| `settings_path` | マクロごとの設定ファイルを読む場合に指定します。標準は `resource:settings.toml` です。 |

`args_schema` がない場合、`initialize(cmd, args)` には実行時に渡された辞書がそのまま渡ります。`args_schema` が `SettingsSchema` の場合は、`MacroRunner` が `SettingsSchema.validate()` を通した辞書を `initialize()` へ渡します。型変換や必須項目の扱いを schema に寄せるか、`config.py` 側で行うかはマクロごとに決めます。

## initialize(cmd, args)

実行前の初期化を行います。設定値の読み取り、画像資材の読み込み、カウンタの初期化などをここで行います。長いゲーム操作は `initialize()` ではなく `run()` に置きます。

```python
def initialize(self, cmd: Command, args: dict) -> None:
    self._cfg = SampleConfig.from_args(args)
    self._template = cmd.load_img(self._cfg.template_path)
```

## run(cmd)

マクロの本処理を実行します。ボタン入力、待機、キャプチャ、画像判定、通知は `Command` を使います。`cmd.capture()` はフレーム未準備時に `FrameNotReadyError` を送出します。フレーム未準備を通常分岐として扱う場合は `cmd.try_capture()` を使います。

```python
frame = cmd.try_capture()
if frame is None:
    cmd.log("capture failed", level="WARNING")
    return
cmd.save_img("snapshot.png", frame)
```

## finalize(cmd)

終了時の後片付けを行います。押しっぱなしのボタン解除、最後のログ出力、外部資源の解放などを置きます。`run()` が失敗した場合でも呼ばれるため、`finalize()` は何度呼ばれても安全な処理にします。

```python
def finalize(self, cmd: Command) -> None:
    cmd.release()
```

## 状態の持ち方

インスタンス変数には設定値と最小限の実行状態だけを持たせます。乱数計算、画像判定、設定変換は関数へ分離し、`Command` なしで単体テストできるようにします。
