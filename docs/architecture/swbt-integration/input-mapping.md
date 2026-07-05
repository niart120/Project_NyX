# 入力マッピング設計

この文書は、NyXPy の `Button`、`Hat`、`LStick`、`RStick` を swbt-python の `Button`、`Stick`、`InputState` へ変換する規則を定義します。

## 方針

- マッピングは `NyxSwbtInputMapper` に集約する。
- `SwbtControllerOutputPort` は mapper を呼び、変換規則を持たない。
- 差分操作を swbt へ連続で投げず、最終的な `InputState` を作って `apply()` する。
- `ThreeDSButton`、`TouchState`、keyboard 入力は非対応として明示的に落とす。

## Button

NyXPy の button と swbt の button は名前が近いため、明示 dict で変換します。

```python
from swbt import Button as SwbtButton
from nyxpy.framework.core.constants import Button as NyxButton


BUTTON_MAP: dict[NyxButton, SwbtButton] = {
    NyxButton.A: SwbtButton.A,
    NyxButton.B: SwbtButton.B,
    NyxButton.X: SwbtButton.X,
    NyxButton.Y: SwbtButton.Y,
    NyxButton.L: SwbtButton.L,
    NyxButton.R: SwbtButton.R,
    NyxButton.ZL: SwbtButton.ZL,
    NyxButton.ZR: SwbtButton.ZR,
    NyxButton.PLUS: SwbtButton.PLUS,
    NyxButton.MINUS: SwbtButton.MINUS,
    NyxButton.HOME: SwbtButton.HOME,
    NyxButton.CAP: SwbtButton.CAPTURE,
    NyxButton.LS: SwbtButton.LEFT_STICK,
    NyxButton.RS: SwbtButton.RIGHT_STICK,
}
```

NyXPy 側は capture button を `CAP`、stick click を `LS` / `RS` として定義しています。swbt-python 側は `CAPTURE`、`LEFT_STICK`、`RIGHT_STICK` です。自動変換ではなく明示 dict にする理由は、名前の違いと偶然一致の両方へ依存しないためです。

## Hat

`Hat` は swbt 側の D-pad button set へ変換します。斜め方向は 2 button 同時押しとして扱います。

```python
from swbt import Button as SwbtButton
from nyxpy.framework.core.constants import Hat


HAT_MAP: dict[Hat, tuple[SwbtButton, ...]] = {
    Hat.UP: (SwbtButton.DPAD_UP,),
    Hat.DOWN: (SwbtButton.DPAD_DOWN,),
    Hat.LEFT: (SwbtButton.DPAD_LEFT,),
    Hat.RIGHT: (SwbtButton.DPAD_RIGHT,),
    Hat.UPRIGHT: (SwbtButton.DPAD_UP, SwbtButton.DPAD_RIGHT),
    Hat.DOWNRIGHT: (SwbtButton.DPAD_DOWN, SwbtButton.DPAD_RIGHT),
    Hat.DOWNLEFT: (SwbtButton.DPAD_DOWN, SwbtButton.DPAD_LEFT),
    Hat.UPLEFT: (SwbtButton.DPAD_UP, SwbtButton.DPAD_LEFT),
    Hat.CENTER: (),
}

DPAD_BUTTONS = {
    SwbtButton.DPAD_UP,
    SwbtButton.DPAD_DOWN,
    SwbtButton.DPAD_LEFT,
    SwbtButton.DPAD_RIGHT,
}
```

`press(Hat.CENTER)` は D-pad 全解除として扱うか、no-op として扱うかを決める必要があります。既存 serial protocol では `Hat.CENTER` を状態へ入れると方向入力が中央に戻るため、swbt backend でも D-pad 全解除に寄せます。

| 操作 | 扱い |
|---|---|
| `press(Hat.UP)` | D-pad button を全解除してから `DPAD_UP` を追加 |
| `hold(Hat.UP)` | state 初期化後に `DPAD_UP` を追加 |
| `release(Hat.UP)` | D-pad button を全解除 |
| `press(Hat.CENTER)` | D-pad button を全解除 |
| `hold(Hat.CENTER)` | state 初期化後、D-pad は空 |
| `release(Hat.CENTER)` | D-pad button を全解除 |

## Stick

swbt の `Stick.raw()` は `0..4095` の raw 値を受けます。NyXPy の `LStick` / `RStick` が `0..255` の座標を持つ前提では、次の変換を使います。

```python
from swbt import Stick as SwbtStick


def stick_8bit_to_12bit(value: int) -> int:
    if not 0 <= value <= 255:
        raise ValueError(f"stick value out of range: {value}")
    return round(value * 4095 / 255)


def to_swbt_stick(x: int, y: int, *, invert_y: bool = False) -> SwbtStick:
    raw_y = 255 - y if invert_y else y
    return SwbtStick.raw(
        x=stick_8bit_to_12bit(x),
        y=stick_8bit_to_12bit(raw_y),
    )
```

Y 軸の向きは実機で確認します。既存マクロ資産を壊さないため、`controller.swbt.invert_stick_y` を設定として持たせます。既定値は `false` です。

## add_to_state

```python
from nyxpy.framework.core.constants import Button, Hat, LStick, RStick, ThreeDSButton, TouchState


class NyxSwbtInputMapper:
    def __init__(self, *, invert_stick_y: bool = False) -> None:
        self._invert_stick_y = invert_stick_y

    def add_to_state(self, state: NyxSwbtState, keys: tuple[KeyType, ...]) -> None:
        for key in keys:
            match key:
                case Button():
                    state.buttons.add(BUTTON_MAP[key])
                case Hat():
                    self._set_hat(state, key)
                case LStick():
                    state.left_stick = to_swbt_stick(
                        key.x,
                        key.y,
                        invert_y=self._invert_stick_y,
                    )
                case RStick():
                    state.right_stick = to_swbt_stick(
                        key.x,
                        key.y,
                        invert_y=self._invert_stick_y,
                    )
                case ThreeDSButton() | TouchState():
                    raise UnsupportedSwbtInputError(f"swbt backend does not support {key!r}")
                case _:
                    raise UnsupportedSwbtInputError(f"unsupported key for swbt backend: {key!r}")

    def _set_hat(self, state: NyxSwbtState, hat: Hat) -> None:
        state.buttons.difference_update(DPAD_BUTTONS)
        state.buttons.update(HAT_MAP[hat])
```

## remove_from_state

```python
class NyxSwbtInputMapper:
    ...

    def remove_from_state(self, state: NyxSwbtState, keys: tuple[KeyType, ...]) -> None:
        for key in keys:
            match key:
                case Button():
                    state.buttons.discard(BUTTON_MAP[key])
                case Hat():
                    state.buttons.difference_update(DPAD_BUTTONS)
                case LStick():
                    state.left_stick = SwbtStick.center()
                case RStick():
                    state.right_stick = SwbtStick.center()
                case ThreeDSButton() | TouchState():
                    raise UnsupportedSwbtInputError(f"swbt backend does not support {key!r}")
                case _:
                    raise UnsupportedSwbtInputError(f"unsupported key for swbt backend: {key!r}")
```

## complete state

```python
from swbt import InputState


class NyxSwbtInputMapper:
    ...

    def to_input_state(self, state: NyxSwbtState) -> InputState:
        return (
            InputState.neutral()
            .with_buttons(state.buttons)
            .with_sticks(
                left_stick=state.left_stick,
                right_stick=state.right_stick,
            )
        )
```

`InputState` は immutable な完全入力状態です。button と stick を同一 HID report に入れたい場合は、複数の state update API を分けて呼ばず、`InputState` を作って `apply()` します。

## unsupported feature

swbt backend では次を非対応にします。

| NyXPy 入力 | 理由 |
|---|---|
| `keyboard(text)` | NX Pro Controller 相当の gamepad 入力であり、keyboard text input ではない |
| `type_key(key)` | 同上 |
| `ThreeDSButton` | 対象が異なる |
| `TouchState` / `touch_down` / `touch_up` | NX Pro Controller 相当入力には touch surface がない |
| `disable_sleep` | serial protocol 固有の追加 command であり swbt public API にない |
| IMU | NyXPy 側の公開 `Command` API に motion 入力がないため初期連携対象外 |

将来 IMU を扱う場合は、`Command` へ直接追加するのではなく、NyXPy の controller 抽象として motion 入力の port 契約を先に設計します。
