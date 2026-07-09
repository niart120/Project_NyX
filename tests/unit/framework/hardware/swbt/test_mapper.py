import pytest
from swbt import Button as SwbtButton
from swbt import Stick as SwbtStick

from nyxpy.framework.core.constants import Button, Hat, IMUFrame, LStick, RStick
from nyxpy.framework.core.hardware.swbt.config import resolve_controller_model
from nyxpy.framework.core.hardware.swbt.mapper import (
    NyxSwbtInputMapper,
    NyxSwbtState,
    normalize_imu_frames,
)


def mapper(controller_type: str = "pro-controller") -> NyxSwbtInputMapper:
    return NyxSwbtInputMapper(resolve_controller_model(controller_type))


def test_mapper_maps_buttons_with_current_nyx_names() -> None:
    state = mapper().hold((Button.A, Button.CAP, Button.LS, Button.RS))
    input_state = mapper().to_input_state(state)

    assert input_state.buttons == frozenset(
        {
            SwbtButton.A,
            SwbtButton.CAPTURE,
            SwbtButton.LEFT_STICK,
            SwbtButton.RIGHT_STICK,
        }
    )


def test_mapper_replaces_dpad_direction() -> None:
    m = mapper()
    state = m.press(NyxSwbtState.neutral(), (Hat.UPRIGHT,))
    state = m.press(state, (Hat.LEFT,))

    input_state = m.to_input_state(state)

    assert input_state.buttons == frozenset({SwbtButton.DPAD_LEFT})


def test_mapper_converts_stick_xy_and_rejects_joycon_missing_stick() -> None:
    m = mapper()
    state = m.hold(
        (
            LStick.UP,
            RStick.DOWN,
        )
    )
    input_state = m.to_input_state(state)

    assert input_state.left_stick == SwbtStick.raw(x=LStick.UP.x, y=LStick.UP.y)
    assert input_state.right_stick == SwbtStick.raw(x=RStick.DOWN.x, y=RStick.DOWN.y)

    with pytest.raises(Exception) as left_error:
        mapper("joy-con-r").hold((LStick.UP,))
    assert getattr(left_error.value, "code", None) == "NYX_SWBT_INPUT_UNSUPPORTED"

    with pytest.raises(Exception) as right_error:
        mapper("joy-con-l").hold((RStick.UP,))
    assert getattr(right_error.value, "code", None) == "NYX_SWBT_INPUT_UNSUPPORTED"


def test_mapper_normalizes_imu_one_or_three_frames() -> None:
    frame = IMUFrame.gyro(x=100)
    first = IMUFrame.accel(x=1)
    second = IMUFrame.accel(y=2)
    third = IMUFrame.accel(z=3)

    assert normalize_imu_frames((frame,)) == (frame, frame, frame)
    assert normalize_imu_frames((first, second, third)) == (first, second, third)

    state = mapper().set_imu(NyxSwbtState.neutral(), (frame,))
    input_state = mapper().to_input_state(state)

    assert [sample.gyro_x for sample in input_state.imu_frames] == [100, 100, 100]

    with pytest.raises(Exception) as exc_info:
        normalize_imu_frames((first, second))
    assert getattr(exc_info.value, "code", None) == "NYX_IMU_FRAME_COUNT_INVALID"
