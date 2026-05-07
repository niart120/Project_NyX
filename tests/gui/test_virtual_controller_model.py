import pytest

from nyxpy.framework.core.constants import Button, Hat
from nyxpy.gui.events import EventBus, EventType
from nyxpy.gui.models.virtual_controller_model import VirtualControllerModel
from tests.support.fakes import FakeControllerOutputPort, FakeLoggerPort


@pytest.fixture(autouse=True)
def reset_event_bus():
    EventBus._instance = None
    yield
    EventBus._instance = None


def test_button_operations_use_controller_output_port() -> None:
    controller = FakeControllerOutputPort()
    model = VirtualControllerModel(logger=FakeLoggerPort(), controller=controller)

    model.button_press(Button.A)
    model.button_release(Button.A)

    assert controller.events == [
        ("press", (Button.A,)),
        ("release", (Button.A,)),
    ]


def test_hat_center_releases_previous_direction() -> None:
    controller = FakeControllerOutputPort()
    model = VirtualControllerModel(logger=FakeLoggerPort(), controller=controller)

    model.set_hat_direction(Hat.UP)
    model.set_hat_direction(Hat.CENTER)

    assert controller.events == [
        ("press", (Hat.UP,)),
        ("release", (Hat.UP,)),
    ]


def test_missing_controller_is_noop() -> None:
    model = VirtualControllerModel(logger=FakeLoggerPort(), controller=None)

    model.button_press(Button.B)
    model.button_release(Button.B)

    assert model.pressed_buttons == set()


def test_serial_device_event_replaces_controller_port() -> None:
    class SerialDevice:
        def __init__(self) -> None:
            self.sent: list[bytes] = []

        def send(self, data: bytes) -> None:
            self.sent.append(data)

    class Protocol:
        def build_press_command(self, keys):
            return b"press:" + b",".join(key.name.encode() for key in keys)

        def build_release_command(self, keys=()):
            return b"release:" + b",".join(key.name.encode() for key in keys)

    serial = SerialDevice()
    model = VirtualControllerModel(logger=FakeLoggerPort(), protocol=Protocol())

    EventBus.get_instance().publish(EventType.SERIAL_DEVICE_CHANGED, {"device": serial})
    model.button_press(Button.X)

    assert serial.sent == [b"press:X"]
