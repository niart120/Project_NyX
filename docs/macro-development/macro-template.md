# マクロ雛形

この雛形は、ローカル作業用の `macros\<macro_id>` と `resources\<macro_id>` にマクロを作るための最小構成です。公開サンプルとして見せる段階になったら、同じ構成を `examples\macros` / `examples\resources` / `examples\tests` に整理して移します。

## ディレクトリ

```text
macros\sample_macro\
  macro.py
  config.py
  test_config.py

resources\sample_macro\
  settings.toml
  assets\
    template.png
```

`macro.toml` は必須ではありません。`macros\sample_macro\macro.py` に `MacroBase` 派生クラスを 1 つだけ置く場合、自動検出されます。

## macro.py

```python
from nyxpy.framework.core.constants import Button
from nyxpy.framework.core.macro.base import MacroBase
from nyxpy.framework.core.macro.command import Command

from .config import SampleConfig


class SampleMacro(MacroBase):
    description = "Aボタンを指定回数だけ押すサンプル"
    tags = ["sample", "button"]
    settings_path = "resource:settings.toml"

    def initialize(self, cmd: Command, args: dict) -> None:
        self._cfg = SampleConfig.from_args(args)
        cmd.log(
            f"SampleMacro initialized: count={self._cfg.count}, "
            f"press_seconds={self._cfg.press_seconds}",
            level="INFO",
        )

    def run(self, cmd: Command) -> None:
        for index in range(1, self._cfg.count + 1):
            cmd.press(Button.A, dur=self._cfg.press_seconds, wait=self._cfg.wait_seconds)
            if index % 5 == 0:
                cmd.log(f"progress: {index}/{self._cfg.count}", level="INFO")

        if self._cfg.capture_after:
            frame = cmd.capture()
            if frame is None:
                cmd.log("capture failed", level="WARNING")
                return
            cmd.save_img(self._cfg.capture_name, frame)

    def finalize(self, cmd: Command) -> None:
        cmd.release()
```

## config.py

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class SampleConfig:
    count: int
    press_seconds: float
    wait_seconds: float
    capture_after: bool
    capture_name: str

    @classmethod
    def from_args(cls, args: dict) -> "SampleConfig":
        cfg = cls(
            count=int(args.get("count", 10)),
            press_seconds=float(args.get("press_seconds", 0.06)),
            wait_seconds=float(args.get("wait_seconds", 0.08)),
            capture_after=bool(args.get("capture_after", True)),
            capture_name=str(args.get("capture_name", "sample_result.png")),
        )
        if cfg.count <= 0:
            raise ValueError("count must be greater than 0")
        if cfg.press_seconds < 0 or cfg.wait_seconds < 0:
            raise ValueError("press_seconds and wait_seconds must be non-negative")
        if not cfg.capture_name:
            raise ValueError("capture_name must not be empty")
        return cfg
```

## test_config.py

```python
import pytest

from .config import SampleConfig


def test_sample_config_from_args() -> None:
    cfg = SampleConfig.from_args({"count": "3", "capture_name": "debug/result.png"})

    assert cfg.count == 3
    assert cfg.capture_name == "debug/result.png"


def test_sample_config_rejects_non_positive_count() -> None:
    with pytest.raises(ValueError, match="count"):
        SampleConfig.from_args({"count": 0})
```

## resources\sample_macro\settings.toml

```toml
count = 10
press_seconds = 0.06
wait_seconds = 0.08
capture_after = true
capture_name = "sample_result.png"
```

設定ファイルにパスを書く場合は `/` を使います。

```toml
template_path = "assets/template.png"
```

## 任意: macro.toml

次のいずれかに当てはまる場合だけ `macros\sample_macro\macro.toml` を追加します。

- エントリーポイントを明示したい。
- 複数のエントリーポイントを持つ構成から 1 つを選びたい。
- マニフェスト側にメタデータや設定ファイルのパスを集約したい。

```toml
[macro]
id = "sample_macro"
entrypoint = "macros.sample_macro.macro:SampleMacro"
display_name = "Sample Macro"
description = "Aボタンを指定回数だけ押すサンプル"
tags = ["sample", "button"]
settings = "resource:settings.toml"
```

`macro.toml` の移植可能パスも `/` を使います。`settings = "resource:settings.toml"` は `resources\sample_macro\settings.toml` を参照します。

## 完了前確認

- [ ] `macro.py` または `__init__.py` のどちらか一方に、そのファイルで定義した `MacroBase` 派生クラスが 1 つだけある。
- [ ] `settings_path = "resource:settings.toml"` と `resources\<macro_id>\settings.toml` が一致している。
- [ ] 画像資材は `resources\<macro_id>\assets` に置いている。
- [ ] `cmd.capture()` の戻り値 `None` を処理している。
- [ ] `finalize()` で必要な `cmd.release()` を呼んでいる。
- [ ] 副作用のない設定変換・判定ロジックをテストしている。
- [ ] 移植可能パスに `\` や絶対パスを書いていない。
- [ ] 次のコマンドで確認している。

```powershell
uv run ruff format .
uv run ruff check .
uv run pytest tests macros examples/tests
```

