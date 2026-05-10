from __future__ import annotations

import os

import pytest

from nyxpy.framework.core.constants import Button
from nyxpy.framework.core.hardware.protocol_factory import ProtocolFactory
from nyxpy.framework.core.hardware.serial_comm import SerialComm
from nyxpy.framework.core.io.adapters import SerialControllerOutputPort


def _required_env(*names: str) -> str:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    pytest.skip(f"{' or '.join(names)} is required for 3DS realdevice test")


@pytest.mark.realdevice
def test_3ds_device_button_touch() -> None:
    serial_port = _required_env("NYX_REAL_3DS_SERIAL_PORT", "NYX_REAL_SERIAL_PORT")
    baudrate = int(os.environ.get("NYX_REAL_3DS_BAUD", "115200"))
    baudrate = ProtocolFactory.resolve_baudrate("3DS", baudrate)
    serial = SerialComm(serial_port)
    protocol = ProtocolFactory.create_protocol("3DS")
    controller = SerialControllerOutputPort(serial, protocol)

    try:
        serial.open(baudrate)
    except Exception as exc:
        pytest.skip(f"3DS serial device is not available: {exc}")

    try:
        controller.press((Button.A,))
        controller.release((Button.A,))
        controller.touch_down(160, 120)
        controller.touch_up()
        controller.disable_sleep(True)
        controller.disable_sleep(False)
    finally:
        serial.close()
