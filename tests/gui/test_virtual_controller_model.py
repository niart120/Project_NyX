from pathlib import Path

from nyxpy.framework.core.constants import Button, Hat
from nyxpy.gui.models.virtual_controller_model import VirtualControllerModel
from tests.support.fakes import (
    FakeControllerOutputPort,
    FakeFullCapabilityController,
    FakeLoggerPort,
)


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


def test_set_controller_replaces_controller_output_port() -> None:
    first = FakeControllerOutputPort()
    second = FakeControllerOutputPort()
    model = VirtualControllerModel(logger=FakeLoggerPort(), controller=first)

    model.set_controller(second)
    model.button_press(Button.X)

    assert first.events == []
    assert second.events == [("press", (Button.X,))]


def test_virtual_controller_model_reports_touch_support() -> None:
    model = VirtualControllerModel(logger=FakeLoggerPort(), controller=FakeControllerOutputPort())
    assert not model.supports_touch_input()

    model.set_controller(FakeFullCapabilityController())

    assert model.supports_touch_input()


def test_virtual_controller_model_sends_touch_events() -> None:
    controller = FakeFullCapabilityController()
    model = VirtualControllerModel(logger=FakeLoggerPort(), controller=controller)

    model.touch_down(10, 20)
    model.touch_move(11, 21)
    model.touch_up()

    assert controller.events == [
        ("touch_down", (10, 20)),
        ("touch_down", (11, 21)),
        ("touch_up", None),
    ]


def test_virtual_controller_model_ignores_touch_when_unsupported() -> None:
    controller = FakeControllerOutputPort()
    model = VirtualControllerModel(logger=FakeLoggerPort(), controller=controller)

    model.touch_down(10, 20)
    model.touch_up()

    assert controller.events == []


def test_virtual_controller_model_has_no_event_bus_dependency() -> None:
    source = (Path("src") / "nyxpy" / "gui" / "models" / "virtual_controller_model.py").read_text(
        encoding="utf-8"
    )

    assert "EventBus" not in source
    assert "EventType" not in source
    assert "serial_device" not in source
