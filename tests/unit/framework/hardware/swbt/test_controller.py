import pytest
from swbt import Button as SwbtButton

from nyxpy.framework.core.constants import Button, IMUFrame
from nyxpy.framework.core.hardware.swbt.config import resolve_controller_model
from nyxpy.framework.core.hardware.swbt.controller import SwbtControllerOutputPort
from nyxpy.framework.core.macro.exceptions import DeviceError


class RecordingSession:
    def __init__(self) -> None:
        self.applied = []
        self.neutral_calls = 0
        self.close_calls = 0
        self.apply_failures = 0
        self.neutral_failures = 0

    def apply(self, state) -> None:
        if self.apply_failures:
            self.apply_failures -= 1
            raise DeviceError("apply failed", code="TEST_APPLY_FAILED")
        self.applied.append(state)

    def neutral(self) -> None:
        self.neutral_calls += 1
        if self.neutral_failures:
            self.neutral_failures -= 1
            raise DeviceError("neutral failed", code="TEST_NEUTRAL_FAILED")

    def close(self) -> None:
        self.close_calls += 1


def port(
    session: RecordingSession | None = None,
) -> tuple[SwbtControllerOutputPort, RecordingSession]:
    actual = session or RecordingSession()
    return (
        SwbtControllerOutputPort(
            session=actual,
            model=resolve_controller_model("pro-controller"),
        ),
        actual,
    )


def test_port_press_hold_release_apply_complete_state() -> None:
    controller, session = port()

    controller.press((Button.A,))
    controller.press((Button.B,))
    controller.release((Button.A,))
    controller.hold((Button.X,))

    assert session.neutral_calls == 1
    assert session.applied[0].buttons == frozenset({SwbtButton.A})
    assert session.applied[1].buttons == frozenset({SwbtButton.A, SwbtButton.B})
    assert session.applied[2].buttons == frozenset({SwbtButton.B})
    assert session.applied[3].buttons == frozenset({SwbtButton.X})


def test_port_imu_and_release_all_use_neutral() -> None:
    controller, session = port()
    frame = IMUFrame.gyro(x=10)

    controller.imu(frame)
    controller.release()

    assert session.applied[-1].imu_frames[0].gyro_x == 10
    assert session.neutral_calls == 2


def test_port_commits_state_only_after_apply_succeeds() -> None:
    controller, session = port()
    session.apply_failures = 1

    with pytest.raises(DeviceError, match="apply failed"):
        controller.press((Button.A,))
    controller.press((Button.B,))

    assert session.applied[-1].buttons == frozenset({SwbtButton.B})


def test_port_close_sends_neutral_without_session_close() -> None:
    controller, session = port()

    controller.close()
    controller.close()

    assert session.neutral_calls == 2
    assert session.close_calls == 0

    with pytest.raises(Exception) as exc_info:
        controller.press((Button.A,))
    assert getattr(exc_info.value, "code", None) == "NYX_SWBT_PORT_CLOSED"


def test_port_close_notifies_owner_once() -> None:
    session = RecordingSession()
    closed = []
    controller = SwbtControllerOutputPort(
        session=session,
        model=resolve_controller_model("pro-controller"),
        on_close=closed.append,
    )

    controller.close()
    controller.close()

    assert closed == [controller]


def test_port_close_can_be_retried_after_neutral_failure() -> None:
    session = RecordingSession()
    closed = []
    controller = SwbtControllerOutputPort(
        session=session,
        model=resolve_controller_model("pro-controller"),
        on_close=closed.append,
    )
    session.neutral_failures = 1

    with pytest.raises(DeviceError, match="neutral failed"):
        controller.close()
    controller.close()

    assert closed == [controller]
    assert session.neutral_calls == 3


def test_port_rejects_backend_unsupported_apis() -> None:
    controller, _session = port()

    with pytest.raises(NotImplementedError, match="keyboard input"):
        controller.keyboard("A")
    with pytest.raises(NotImplementedError, match="keyboard input"):
        controller.type_key("A")
    with pytest.raises(NotImplementedError, match="touch input"):
        controller.touch_down(1, 2)
    with pytest.raises(NotImplementedError, match="sleep control"):
        controller.disable_sleep(True)
