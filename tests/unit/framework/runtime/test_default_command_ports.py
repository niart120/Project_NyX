import numpy as np
import pytest

from nyxpy.framework.core.constants import Button, KeyCode
from nyxpy.framework.core.macro.command import DefaultCommand
from nyxpy.framework.core.macro.exceptions import MacroCancelled
from tests.support.fake_execution_context import make_fake_execution_context
from tests.support.fakes import (
    FakeControllerOutputPort,
    FakeFullCapabilityController,
    FakeNotificationPort,
)


def test_default_command_rejects_legacy_constructor_args() -> None:
    with pytest.raises(TypeError):
        DefaultCommand(serial_device=object())


def test_command_stop_rejects_raise_immediately_argument(tmp_path) -> None:
    cmd = DefaultCommand(context=make_fake_execution_context(tmp_path))

    with pytest.raises(TypeError):
        cmd.stop(raise_immediately=True)


def test_default_command_press_delegates_to_controller_port(tmp_path) -> None:
    controller = FakeControllerOutputPort()
    cmd = DefaultCommand(context=make_fake_execution_context(tmp_path, controller=controller))

    cmd.press(Button.A, dur=0, wait=0)

    assert controller.events == [("press", (Button.A,)), ("release", (Button.A,))]


def test_default_command_capture_resizes_crops_and_grayscales(tmp_path) -> None:
    frame = np.ones((360, 640, 3), dtype=np.uint8) * 255
    context = make_fake_execution_context(tmp_path)
    context.frame_source.frame = frame
    context.frame_source.initialize()
    cmd = DefaultCommand(context=context)

    result = cmd.capture(crop_region=(10, 20, 30, 40), grayscale=True)

    assert result.shape == (40, 30)
    assert result.dtype == frame.dtype


def test_default_command_resources_and_artifacts_delegate_to_ports(tmp_path) -> None:
    context = make_fake_execution_context(tmp_path)
    image = np.ones((1, 1, 3), dtype=np.uint8)
    asset_path = context.resources.scope.candidate_asset_paths("template.png")[0]
    context.resources.images[asset_path] = image
    cmd = DefaultCommand(context=context)

    loaded = cmd.load_img("template.png")
    cmd.save_img("out.png", image)

    assert np.array_equal(loaded, image)
    assert (
        context.artifacts.saved_images[context.artifacts.resolve_output_path("out.png").path][
            0, 0, 0
        ]
        == 1
    )


def test_default_command_keyboard_type_notify_and_log_delegate_to_ports(tmp_path) -> None:
    controller = FakeControllerOutputPort()
    context = make_fake_execution_context(tmp_path, controller=controller)
    notifier = FakeNotificationPort()
    object.__setattr__(context, "notifications", notifier)
    cmd = DefaultCommand(context=context)

    cmd.keyboard("Hi")
    cmd.type(KeyCode("A"))
    cmd.notify("message")
    cmd.log("visible", level="INFO")

    assert ("keyboard", "Hi") in controller.events
    assert ("type_key", KeyCode("A")) in controller.events
    assert notifier.calls == [("message", None)]
    assert context.logger.user_events[-1].message == "visible"


def test_default_command_notify_logs_and_swallows_failures(tmp_path) -> None:
    class FailingNotification(FakeNotificationPort):
        def publish(self, text, img=None) -> None:
            raise RuntimeError("notify failed")

    context = make_fake_execution_context(tmp_path)
    object.__setattr__(context, "notifications", FailingNotification())
    cmd = DefaultCommand(context=context)

    cmd.notify("message")

    assert context.logger.technical_logs[-1].event.event == "notification.failed"


def test_default_command_touch_and_sleep_capabilities(tmp_path) -> None:
    controller = FakeFullCapabilityController()
    cmd = DefaultCommand(context=make_fake_execution_context(tmp_path, controller=controller))

    cmd.touch(1, 2, dur=0, wait=0)
    cmd.disable_sleep(True)

    assert ("touch_down", (1, 2)) in controller.events
    assert ("touch_up", None) in controller.events
    assert ("disable_sleep", True) in controller.events


def test_default_command_unsupported_capabilities_raise(tmp_path) -> None:
    cmd = DefaultCommand(context=make_fake_execution_context(tmp_path))

    with pytest.raises(NotImplementedError):
        cmd.touch_down(1, 2)
    with pytest.raises(NotImplementedError):
        cmd.disable_sleep(True)


def test_default_command_wait_raises_after_cancel(tmp_path) -> None:
    context = make_fake_execution_context(tmp_path)
    context.cancellation_token.request_cancel(reason="test", source="test")
    cmd = DefaultCommand(context=context)

    with pytest.raises(MacroCancelled):
        cmd.wait(1.0)
