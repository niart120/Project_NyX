"""NyX controller 入力から swbt InputState への mapper。"""

from __future__ import annotations

from dataclasses import dataclass, field

from nyxpy.framework.core.constants import (
    Button,
    Hat,
    IMUFrame,
    KeyType,
    LStick,
    RStick,
)
from nyxpy.framework.core.hardware.swbt.config import SwbtControllerModel
from nyxpy.framework.core.hardware.swbt.errors import (
    imu_frame_count_invalid,
    swbt_input_invalid,
    swbt_input_unsupported,
)


def _neutral_imu_frames() -> tuple[IMUFrame, IMUFrame, IMUFrame]:
    frame = IMUFrame.neutral()
    return (frame, frame, frame)


@dataclass(frozen=True, slots=True)
class NyxSwbtState:
    """SwbtControllerOutputPort が保持する NyX 側入力状態。"""

    buttons: frozenset[Button] = field(default_factory=frozenset)
    dpad_buttons: frozenset[object] = field(default_factory=frozenset)
    left_stick: LStick | None = None
    right_stick: RStick | None = None
    imu_frames: tuple[IMUFrame, IMUFrame, IMUFrame] = field(default_factory=_neutral_imu_frames)

    @classmethod
    def neutral(cls) -> NyxSwbtState:
        """全入力を neutral にした状態を返す。"""
        return cls()


class NyxSwbtInputMapper:
    """NyX の入力 model を swbt の入力 model へ変換する。"""

    def __init__(self, model: SwbtControllerModel) -> None:
        """Controller model と capabilities を保持する。"""
        self.model = model

    def press(self, state: NyxSwbtState, keys: tuple[KeyType, ...]) -> NyxSwbtState:
        """既存状態へ keys を追加または反映する。"""
        next_state = state
        for key in keys:
            next_state = self._press_one(next_state, key)
        return next_state

    def hold(self, keys: tuple[KeyType, ...]) -> NyxSwbtState:
        """既存状態を破棄して keys のみを保持する。"""
        return self.press(NyxSwbtState.neutral(), keys)

    def release(self, state: NyxSwbtState, keys: tuple[KeyType, ...] = ()) -> NyxSwbtState:
        """状態から keys を解除する。keys が空なら全入力を neutral にする。"""
        if not keys:
            return NyxSwbtState.neutral()
        next_state = state
        for key in keys:
            next_state = self._release_one(next_state, key)
        return next_state

    def set_imu(self, state: NyxSwbtState, frames: tuple[IMUFrame, ...]) -> NyxSwbtState:
        """IMU frame だけを置き換える。"""
        return NyxSwbtState(
            buttons=state.buttons,
            dpad_buttons=state.dpad_buttons,
            left_stick=state.left_stick,
            right_stick=state.right_stick,
            imu_frames=normalize_imu_frames(frames),
        )

    def to_input_state(self, state: NyxSwbtState):
        """NyX 側状態を swbt.InputState に変換する。"""
        from swbt import InputState

        buttons = {_swbt_button(button) for button in state.buttons}
        buttons.update(state.dpad_buttons)
        input_state = InputState.neutral().with_buttons(buttons)
        input_state = input_state.with_sticks(
            left_stick=_swbt_stick(state.left_stick),
            right_stick=_swbt_stick(state.right_stick),
        )
        return input_state.with_imu(*(_swbt_imu_frame(frame) for frame in state.imu_frames))

    def _press_one(self, state: NyxSwbtState, key: KeyType) -> NyxSwbtState:
        if isinstance(key, Button):
            self._require_button(key)
            return NyxSwbtState(
                buttons=state.buttons | {key},
                dpad_buttons=state.dpad_buttons,
                left_stick=state.left_stick,
                right_stick=state.right_stick,
                imu_frames=state.imu_frames,
            )
        if isinstance(key, Hat):
            return NyxSwbtState(
                buttons=state.buttons,
                dpad_buttons=_swbt_dpad_buttons(key),
                left_stick=state.left_stick,
                right_stick=state.right_stick,
                imu_frames=state.imu_frames,
            )
        if isinstance(key, LStick):
            self._require_left_stick()
            return NyxSwbtState(
                buttons=state.buttons,
                dpad_buttons=state.dpad_buttons,
                left_stick=key,
                right_stick=state.right_stick,
                imu_frames=state.imu_frames,
            )
        if isinstance(key, RStick):
            self._require_right_stick()
            return NyxSwbtState(
                buttons=state.buttons,
                dpad_buttons=state.dpad_buttons,
                left_stick=state.left_stick,
                right_stick=key,
                imu_frames=state.imu_frames,
            )
        raise swbt_input_unsupported(f"swbt backend does not support input: {type(key).__name__}")

    def _release_one(self, state: NyxSwbtState, key: KeyType) -> NyxSwbtState:
        if isinstance(key, Button):
            return NyxSwbtState(
                buttons=state.buttons - {key},
                dpad_buttons=state.dpad_buttons,
                left_stick=state.left_stick,
                right_stick=state.right_stick,
                imu_frames=state.imu_frames,
            )
        if isinstance(key, Hat):
            return NyxSwbtState(
                buttons=state.buttons,
                dpad_buttons=frozenset(),
                left_stick=state.left_stick,
                right_stick=state.right_stick,
                imu_frames=state.imu_frames,
            )
        if isinstance(key, LStick):
            return NyxSwbtState(
                buttons=state.buttons,
                dpad_buttons=state.dpad_buttons,
                left_stick=None,
                right_stick=state.right_stick,
                imu_frames=state.imu_frames,
            )
        if isinstance(key, RStick):
            return NyxSwbtState(
                buttons=state.buttons,
                dpad_buttons=state.dpad_buttons,
                left_stick=state.left_stick,
                right_stick=None,
                imu_frames=state.imu_frames,
            )
        raise swbt_input_unsupported(f"swbt backend does not support input: {type(key).__name__}")

    def _require_button(self, button: Button) -> None:
        if button not in self.model.capabilities.buttons:
            raise swbt_input_unsupported(
                f"{self.model.display_name} does not support button {button.name}"
            )

    def _require_left_stick(self) -> None:
        if not self.model.capabilities.left_stick:
            raise swbt_input_unsupported(f"{self.model.display_name} does not support left stick")

    def _require_right_stick(self) -> None:
        if not self.model.capabilities.right_stick:
            raise swbt_input_unsupported(f"{self.model.display_name} does not support right stick")


def normalize_imu_frames(frames: tuple[IMUFrame, ...]) -> tuple[IMUFrame, IMUFrame, IMUFrame]:
    """Swbt の規則に合わせて IMU frame 数を 3 frame に正規化する。"""
    if len(frames) == 1:
        return (frames[0], frames[0], frames[0])
    if len(frames) == 3:
        return (frames[0], frames[1], frames[2])
    raise imu_frame_count_invalid(len(frames))


def _swbt_button(button: Button):
    from swbt import Button as SwbtButton

    mapping = {
        Button.A: SwbtButton.A,
        Button.B: SwbtButton.B,
        Button.X: SwbtButton.X,
        Button.Y: SwbtButton.Y,
        Button.L: SwbtButton.L,
        Button.R: SwbtButton.R,
        Button.ZL: SwbtButton.ZL,
        Button.ZR: SwbtButton.ZR,
        Button.PLUS: SwbtButton.PLUS,
        Button.MINUS: SwbtButton.MINUS,
        Button.HOME: SwbtButton.HOME,
        Button.CAP: SwbtButton.CAPTURE,
        Button.LS: SwbtButton.LEFT_STICK,
        Button.RS: SwbtButton.RIGHT_STICK,
    }
    try:
        return mapping[button]
    except KeyError as exc:
        raise swbt_input_invalid(f"unsupported NyX button: {button}") from exc


def _swbt_dpad_buttons(hat: Hat) -> frozenset[object]:
    from swbt import Button as SwbtButton

    mapping = {
        Hat.UP: (SwbtButton.DPAD_UP,),
        Hat.UPRIGHT: (SwbtButton.DPAD_UP, SwbtButton.DPAD_RIGHT),
        Hat.RIGHT: (SwbtButton.DPAD_RIGHT,),
        Hat.DOWNRIGHT: (SwbtButton.DPAD_DOWN, SwbtButton.DPAD_RIGHT),
        Hat.DOWN: (SwbtButton.DPAD_DOWN,),
        Hat.DOWNLEFT: (SwbtButton.DPAD_DOWN, SwbtButton.DPAD_LEFT),
        Hat.LEFT: (SwbtButton.DPAD_LEFT,),
        Hat.UPLEFT: (SwbtButton.DPAD_UP, SwbtButton.DPAD_LEFT),
        Hat.CENTER: (),
    }
    return frozenset(mapping[hat])


def _swbt_stick(stick: LStick | RStick | None):
    from swbt import Stick

    if stick is None:
        return Stick.center()
    return Stick.raw(x=stick.x, y=stick.y)


def _swbt_imu_frame(frame: IMUFrame):
    from swbt import IMUFrame as SwbtIMUFrame

    return SwbtIMUFrame.raw(accel=frame.accelerometer, gyro=frame.gyroscope)
