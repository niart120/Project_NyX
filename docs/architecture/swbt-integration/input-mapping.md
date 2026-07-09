# 入力 mapping

`NyxSwbtInputMapper` は Project_NyX の controller 入力 model を swbt input model へ変換する。

実装 module は `nyxpy.framework.core.hardware.swbt.mapper` である。

## 原則

- GUI と macro は swbt の `Button` / `Stick` / `IMUFrame` を直接使わない。
- `SwbtControllerOutputPort` は mapper を呼び、変換規則を持たない。
- `SwbtControllerSession` は `InputState` を受け取り、入力内容を解釈しない。
- 非対応 input は silent no-op にしない。

## state

```python
@dataclass
class NyxSwbtState:
    buttons: set[SwbtButton]
    left_stick: SwbtStick
    right_stick: SwbtStick
    imu_frames: tuple[SwbtIMUFrame, SwbtIMUFrame, SwbtIMUFrame]
```

この state は `SwbtControllerOutputPort` の内部状態である。GUI manual input 専用の state ではない。

## Button

Project_NyX `Button` を swbt `Button` へ変換する。

| NyX | swbt |
|---|---|
| `Button.A` | `swbt.Button.A` |
| `Button.B` | `swbt.Button.B` |
| `Button.X` | `swbt.Button.X` |
| `Button.Y` | `swbt.Button.Y` |
| `Button.L` | `swbt.Button.L` |
| `Button.R` | `swbt.Button.R` |
| `Button.ZL` | `swbt.Button.ZL` |
| `Button.ZR` | `swbt.Button.ZR` |
| `Button.PLUS` | `swbt.Button.PLUS` |
| `Button.MINUS` | `swbt.Button.MINUS` |
| `Button.HOME` | `swbt.Button.HOME` |
| `Button.CAPTURE` | `swbt.Button.CAPTURE` |
| `Button.LCLICK` | `swbt.Button.LEFT_STICK` |
| `Button.RCLICK` | `swbt.Button.RIGHT_STICK` |

Project_NyX 側に backend 固有ではないが swbt が扱えない button がある場合は `NYX_SWBT_INPUT_UNSUPPORTED` にする。

## Hat

D-pad は button set として扱う。

| NyX `Hat` | swbt buttons |
|---|---|
| `UP` | `DPAD_UP` |
| `DOWN` | `DPAD_DOWN` |
| `LEFT` | `DPAD_LEFT` |
| `RIGHT` | `DPAD_RIGHT` |
| `UPLEFT` | `DPAD_UP`, `DPAD_LEFT` |
| `UPRIGHT` | `DPAD_UP`, `DPAD_RIGHT` |
| `DOWNLEFT` | `DPAD_DOWN`, `DPAD_LEFT` |
| `DOWNRIGHT` | `DPAD_DOWN`, `DPAD_RIGHT` |
| `CENTER` | no D-pad button |

`VirtualControllerModel` は `CENTER` に戻ると previous direction を release する。swbt port 側は release に従って state を更新する。

## Stick

NyX の `LStick(angle, strength)` / `RStick(angle, strength)` を swbt `Stick` に変換する。

```python
def to_stick(angle: float, strength: float) -> SwbtStick:
    # angle/strength -> normalized x/y -> swbt.Stick.normalized(...)
    ...
```

`strength` は `0.0..1.0` に clamp する。中央は `Stick.center()` を使う。

| NyX | swbt |
|---|---|
| `LStick.CENTER` | `Stick.center()` |
| `RStick.CENTER` | `Stick.center()` |
| `LStick(angle, strength)` | left stick `Stick.normalized(...)` |
| `RStick(angle, strength)` | right stick `Stick.normalized(...)` |

Joy-Con L は right stick を持たない。Joy-Con R は left stick を持たない。mapper は `SwbtControllerModel.capabilities` を見て拒否する。

## IMU

NyX の `IMUFrame` を swbt `IMUFrame` へ変換する。

```python
from nyxpy.framework.core.constants import IMUFrame as NyxIMUFrame
from swbt import IMUFrame as SwbtIMUFrame


def to_imu_frame(frame: NyxIMUFrame) -> SwbtIMUFrame:
    return SwbtIMUFrame.raw(
        accel=frame.accelerometer,
        gyro=frame.gyroscope,
    )
```

1 frame が渡された場合は 3 frame に複製する。3 frame が渡された場合は順に使う。それ以外は `NYX_IMU_FRAME_COUNT_INVALID` にする。

```python
def normalize_imu_frames(frames: tuple[NyxIMUFrame, ...]) -> tuple[SwbtIMUFrame, SwbtIMUFrame, SwbtIMUFrame]:
    if len(frames) == 1:
        converted = to_imu_frame(frames[0])
        return (converted, converted, converted)
    if len(frames) == 3:
        return tuple(to_imu_frame(frame) for frame in frames)  # type: ignore[return-value]
    raise InvalidSwbtInputError(
        "imu input requires 1 or 3 frames",
        code="NYX_IMU_FRAME_COUNT_INVALID",
    )
```

GUI manual input からこの変換を呼ぶ導線は作らない。

## to_input_state

```python
def to_input_state(self, state: NyxSwbtState) -> InputState:
    return (
        InputState.neutral()
        .with_buttons(state.buttons)
        .with_sticks(
            left_stick=state.left_stick,
            right_stick=state.right_stick,
        )
        .with_imu(*state.imu_frames)
    )
```

button、stick、IMU を同一 report に入れる必要がある場合は、port が完全 state を作って `apply(state)` する。

## Unsupported input

| case | error |
|---|---|
| Joy-Con L で right stick | `NYX_SWBT_INPUT_UNSUPPORTED` |
| Joy-Con R で left stick | `NYX_SWBT_INPUT_UNSUPPORTED` |
| unsupported button | `NYX_SWBT_INPUT_UNSUPPORTED` |
| touch input | `NotImplementedError` |
| keyboard input | `NotImplementedError` |
| invalid IMU frame count | `NYX_IMU_FRAME_COUNT_INVALID` |
