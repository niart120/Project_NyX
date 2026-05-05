import pytest

from nyxpy.framework.core.constants import (
    Button,
    Hat,
    LStick,
    RStick,
    ThreeDSButton,
    TouchState,
)
from nyxpy.framework.core.hardware.protocol import (
    ThreeDSSerialProtocol,
    UnsupportedKeyError,
)
from nyxpy.framework.core.hardware.protocol_factory import ProtocolFactory


@pytest.fixture
def protocol():
    return ThreeDSSerialProtocol()


NEUTRAL_FRAME = bytes(
    [0xA1, 0x00, 0x00, 0xA2, 0x80, 0x80, 0xA4, 0x00, 0x00, 0xB2, 0x00, 0x00, 0x00, 0x00]
)


def test_3ds_press_single_button(protocol):
    assert protocol.build_press_command((Button.A,)) == bytes(
        [0xA1, 0x10, 0x00, 0xA2, 0x80, 0x80, 0xA4, 0x00, 0x00, 0xB2, 0x00, 0x00, 0x00, 0x00]
    )


def test_3ds_press_multiple_buttons(protocol):
    assert protocol.build_press_command((Button.A, Button.B, Hat.UP, Button.MINUS)) == bytes(
        [0xA1, 0x38, 0x10, 0xA2, 0x80, 0x80, 0xA4, 0x00, 0x00, 0xB2, 0x00, 0x00, 0x00, 0x00]
    )


def test_3ds_press_diagonal_hat(protocol):
    assert protocol.build_press_command((Hat.UPRIGHT,))[:3] == bytes([0xA1, 0x0C, 0x00])


def test_3ds_release_specific_button(protocol):
    protocol.build_press_command((Button.A, Button.B, Hat.UP))

    assert protocol.build_release_command((Button.A,)) == bytes(
        [0xA1, 0x28, 0x00, 0xA2, 0x80, 0x80, 0xA4, 0x00, 0x00, 0xB2, 0x00, 0x00, 0x00, 0x00]
    )


def test_3ds_release_all(protocol):
    protocol.build_press_command((Button.A, LStick.RIGHT, RStick.UP, TouchState.down(320, 240)))

    assert protocol.build_release_command(()) == NEUTRAL_FRAME


@pytest.mark.parametrize(
    ("stick", "expected"),
    [
        (LStick.CENTER, bytes([0xA2, 0x80, 0x80])),
        (LStick.LEFT, bytes([0xA2, 0x7E, 0x80])),
        (LStick.RIGHT, bytes([0xA2, 0xFA, 0x80])),
        (LStick.UP, bytes([0xA2, 0x80, 0x7E])),
        (LStick.DOWN, bytes([0xA2, 0x80, 0xFA])),
    ],
)
def test_3ds_slide_pad_presets(protocol, stick, expected):
    assert protocol.build_press_command((stick,))[3:6] == expected


@pytest.mark.parametrize(
    ("stick", "expected"),
    [
        (RStick.CENTER, bytes([0xA4, 0x00, 0x00])),
        (RStick.LEFT, bytes([0xA4, 0x80, 0x00])),
        (RStick.RIGHT, bytes([0xA4, 0x7F, 0x00])),
        (RStick.UP, bytes([0xA4, 0x00, 0x80])),
        (RStick.DOWN, bytes([0xA4, 0x00, 0x7F])),
    ],
)
def test_3ds_c_stick_presets(protocol, stick, expected):
    assert protocol.build_press_command((stick,))[6:9] == expected


def test_3ds_mixed_input_fixed_frame(protocol):
    assert protocol.build_press_command(
        (Button.A, Hat.UP, LStick.RIGHT, RStick.UP, TouchState.down(320, 240))
    ) == bytes([0xA1, 0x18, 0x00, 0xA2, 0xFA, 0x80, 0xA4, 0x00, 0x80, 0xB2, 0x01, 0x01, 0x40, 0xF0])


def test_3ds_touch_state_keytype(protocol):
    assert protocol.build_press_command((TouchState.down(320, 240),)) == bytes(
        [0xA1, 0x00, 0x00, 0xA2, 0x80, 0x80, 0xA4, 0x00, 0x00, 0xB2, 0x01, 0x01, 0x40, 0xF0]
    )


def test_3ds_touch_state_release(protocol):
    protocol.build_press_command((Button.A, TouchState.down(320, 240)))

    assert protocol.build_release_command((TouchState.down(320, 240),)) == bytes(
        [0xA1, 0x10, 0x00, 0xA2, 0x80, 0x80, 0xA4, 0x00, 0x00, 0xB2, 0x00, 0x00, 0x00, 0x00]
    )


def test_3ds_touch_down(protocol):
    assert protocol.build_touch_down_command(320, 240) == bytes(
        [0xA1, 0x00, 0x00, 0xA2, 0x80, 0x80, 0xA4, 0x00, 0x00, 0xB2, 0x01, 0x01, 0x40, 0xF0]
    )


def test_3ds_touch_up(protocol):
    protocol.build_touch_down_command(320, 240)

    assert protocol.build_touch_up_command() == NEUTRAL_FRAME


@pytest.mark.parametrize(("x", "y"), [(-1, 0), (321, 0), (0, -1), (0, 241)])
def test_3ds_touch_out_of_range(protocol, x, y):
    with pytest.raises(ValueError):
        protocol.build_touch_down_command(x, y)


def test_3ds_disable_sleep(protocol):
    assert protocol.build_disable_sleep_command(True) == bytes([0xFC, 0x01])
    assert protocol.build_disable_sleep_command(False) == bytes([0xFC, 0x00])


def test_3ds_touch_calibration_commands(protocol):
    assert protocol.build_touch_calibration_write_command(1, 2, 3, 4) == bytes([0xB3, 1, 2, 3, 4])
    assert protocol.build_touch_calibration_write_command(1, 2, 3, 4, factory=True) == bytes(
        [0xB6, 1, 2, 3, 4]
    )
    assert protocol.build_touch_calibration_read_command() == bytes([0xB4])
    assert protocol.build_touch_calibration_factory_reset_command() == bytes([0xB5])


def test_3ds_unsupported_key(protocol):
    with pytest.raises(UnsupportedKeyError):
        protocol.build_press_command((Button.CAP,))


def test_3ds_power_button(protocol):
    assert protocol.build_press_command((ThreeDSButton.POWER,))[:3] == bytes([0xA1, 0x00, 0x20])


def test_protocol_factory_creates_3ds():
    assert isinstance(ProtocolFactory.create_protocol("3DS"), ThreeDSSerialProtocol)


def test_protocol_factory_accepts_3ds_aliases():
    assert isinstance(ProtocolFactory.create_protocol("ThreeDS"), ThreeDSSerialProtocol)
    assert isinstance(ProtocolFactory.create_protocol("Nintendo3DS"), ThreeDSSerialProtocol)


def test_protocol_factory_3ds_default_baudrate():
    assert ProtocolFactory.get_default_baudrate("3DS") == 115200


def test_protocol_factory_rejects_unsupported_baudrate():
    with pytest.raises(ValueError, match="Unsupported baudrate"):
        ProtocolFactory.resolve_baudrate("3DS", 38400)
