import pytest

from nyxpy.framework.core.constants import Button
from nyxpy.framework.core.hardware.protocol import (
    CH552SerialProtocol,
    PokeConSerialProtocol,
    UnsupportedKeyError,
)


@pytest.mark.parametrize("protocol_type", [CH552SerialProtocol, PokeConSerialProtocol])
@pytest.mark.parametrize(
    "method_name",
    ["build_press_command", "build_hold_command", "build_release_command"],
)
@pytest.mark.parametrize("button", [Button.SL, Button.SR])
def test_serial_switch_protocols_reject_joycon_side_buttons(
    protocol_type: type[CH552SerialProtocol] | type[PokeConSerialProtocol],
    method_name: str,
    button: Button,
) -> None:
    protocol = protocol_type()

    with pytest.raises(UnsupportedKeyError, match=rf"does not support Button\.{button.name}"):
        getattr(protocol, method_name)((button,))
