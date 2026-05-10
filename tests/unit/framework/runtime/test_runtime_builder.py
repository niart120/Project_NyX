from pathlib import Path

import pytest

from nyxpy.framework.core.io.adapters import NoopNotificationAdapter, NotificationHandlerAdapter
from nyxpy.framework.core.io.resources import MacroResourceScope
from nyxpy.framework.core.macro.exceptions import ConfigurationError
from nyxpy.framework.core.macro.registry import MacroDefinition
from nyxpy.framework.core.runtime.builder import (
    DUMMY_DEVICE_NAME,
    MacroRuntimeBuilder,
    create_legacy_runtime_builder,
)
from nyxpy.framework.core.runtime.context import RuntimeBuildRequest
from tests.support.fakes import (
    FakeControllerOutputPort,
    FakeFrameSourcePort,
    FakeLoggerPort,
    FakeNotificationPort,
    FakeResourceStore,
    FakeRunArtifactStore,
)


class Registry:
    def __init__(self, definition: MacroDefinition) -> None:
        self.definition = definition

    def resolve(self, name_or_id: str) -> MacroDefinition:
        return self.definition

    def get_settings(self, definition: MacroDefinition) -> dict:
        return {}


class Device:
    pass


class DeviceManager:
    def __init__(self, devices: dict[str, Device]) -> None:
        self.devices = devices
        self.active_device = None
        self.auto_register_calls = 0
        self.set_active_calls = []
        self.get_active_calls = 0

    def auto_register_devices(self) -> None:
        self.auto_register_calls += 1

    def list_devices(self) -> list[str]:
        return list(self.devices)

    def set_active(self, name: str, baudrate: int | None = None) -> None:
        self.set_active_calls.append((name, baudrate))
        self.active_device = self.devices[name]

    def get_active_device(self):
        self.get_active_calls += 1
        self.active_device = self.devices[DUMMY_DEVICE_NAME]
        return self.active_device


class CaptureDeviceManager(DeviceManager):
    def set_active(self, name: str) -> None:
        self.set_active_calls.append((name, None))
        self.active_device = self.devices[name]


def definition(tmp_path: Path) -> MacroDefinition:
    return MacroDefinition(
        id="sample",
        aliases=("sample",),
        display_name="Sample",
        class_name="SampleMacro",
        module_name="tests.sample",
        macro_root=tmp_path,
        source_path=tmp_path / "macro.py",
        settings_path=None,
        description="",
        tags=(),
        factory=object(),
    )


def make_builder(
    tmp_path: Path,
    serial_manager: DeviceManager,
    capture_manager: CaptureDeviceManager,
    **kwargs,
):
    notification_handler = kwargs.pop("notification_handler", None)
    return create_legacy_runtime_builder(
        project_root=tmp_path,
        registry=Registry(definition(tmp_path)),
        serial_manager=serial_manager,
        capture_manager=capture_manager,
        protocol=object(),
        notification_handler=notification_handler,
        logger=FakeLoggerPort(),
        **kwargs,
    )


def test_runtime_builder_disallows_dummy_by_default(tmp_path: Path) -> None:
    serial = DeviceManager({DUMMY_DEVICE_NAME: Device()})
    capture = CaptureDeviceManager({DUMMY_DEVICE_NAME: Device()})
    builder = make_builder(tmp_path, serial, capture)

    with pytest.raises(ConfigurationError, match="serial device is not selected"):
        builder.build(RuntimeBuildRequest(macro_id="sample"))

    assert serial.get_active_calls == 0
    assert serial.active_device is None


def test_runtime_builder_allows_dummy_when_explicit(tmp_path: Path) -> None:
    serial = DeviceManager({DUMMY_DEVICE_NAME: Device()})
    capture = CaptureDeviceManager({DUMMY_DEVICE_NAME: Device()})
    builder = make_builder(tmp_path, serial, capture)

    context = builder.build(RuntimeBuildRequest(macro_id="sample", allow_dummy=True))

    assert context.options.allow_dummy is True
    assert serial.active_device is serial.devices[DUMMY_DEVICE_NAME]
    assert capture.active_device is capture.devices[DUMMY_DEVICE_NAME]
    assert isinstance(context.notifications, NoopNotificationAdapter)


def test_runtime_builder_wraps_notification_handler(tmp_path: Path) -> None:
    serial = DeviceManager({DUMMY_DEVICE_NAME: Device()})
    capture = CaptureDeviceManager({DUMMY_DEVICE_NAME: Device()})
    handler = object()
    builder = make_builder(tmp_path, serial, capture, notification_handler=handler)

    context = builder.build(RuntimeBuildRequest(macro_id="sample", allow_dummy=True))

    assert isinstance(context.notifications, NotificationHandlerAdapter)
    assert context.notifications.notification_handler is handler


def test_runtime_builder_selects_requested_devices(tmp_path: Path) -> None:
    serial = DeviceManager({"COM1": Device()})
    capture = CaptureDeviceManager({"Camera1": Device()})
    builder = make_builder(
        tmp_path,
        serial,
        capture,
        serial_name="COM1",
        capture_name="Camera1",
        baudrate=115200,
    )

    builder.build(RuntimeBuildRequest(macro_id="sample"))

    assert serial.set_active_calls == [("COM1", 115200)]
    assert capture.set_active_calls == [("Camera1", None)]


def test_runtime_builder_does_not_reselect_already_active_devices(tmp_path: Path) -> None:
    serial_device = Device()
    capture_device = Device()
    serial = DeviceManager({"COM1": serial_device})
    capture = CaptureDeviceManager({"Camera1": capture_device})
    serial.active_device = serial_device
    capture.active_device = capture_device
    builder = make_builder(
        tmp_path,
        serial,
        capture,
        serial_name="COM1",
        capture_name="Camera1",
    )

    builder.build(RuntimeBuildRequest(macro_id="sample"))

    assert serial.auto_register_calls == 0
    assert capture.auto_register_calls == 0
    assert serial.set_active_calls == []
    assert capture.set_active_calls == []


def test_runtime_builder_rejects_mixed_direct_and_managed_devices(tmp_path: Path) -> None:
    serial = DeviceManager({"COM1": Device()})
    capture = CaptureDeviceManager({"Camera1": Device()})

    with pytest.raises(ConfigurationError, match="cannot be mixed"):
        create_legacy_runtime_builder(
            project_root=tmp_path,
            registry=Registry(definition(tmp_path)),
            serial_manager=serial,
            capture_manager=capture,
            serial_device=Device(),
            capture_device=Device(),
            protocol=object(),
            notification_handler=None,
            logger=FakeLoggerPort(),
        )


def test_runtime_builder_exposes_and_shutdowns_gui_lifetime_ports(tmp_path: Path) -> None:
    registry = Registry(definition(tmp_path))
    preview_source = FakeFrameSourcePort()
    manual_controller = FakeControllerOutputPort()
    builder = MacroRuntimeBuilder(
        project_root=tmp_path,
        registry=registry,
        controller_factory=lambda _request, _definition: FakeControllerOutputPort(),
        frame_source_factory=lambda _request, _definition: FakeFrameSourcePort(),
        resource_store_factory=lambda _request, definition: FakeResourceStore(
            MacroResourceScope.from_definition(definition, tmp_path)
        ),
        artifact_store_factory=lambda _request, definition, run_id: FakeRunArtifactStore(
            tmp_path / "runs" / run_id / "outputs",
            macro_id=definition.id,
            run_id=run_id,
        ),
        notification_factory=lambda _request, _definition: FakeNotificationPort(),
        logger_factory=lambda _request, _definition: FakeLoggerPort(),
        preview_frame_source_factory=lambda: preview_source,
        manual_controller_factory=lambda: manual_controller,
    )

    assert builder.frame_source_for_preview() is preview_source
    assert builder.frame_source_for_preview() is preview_source
    assert builder.controller_output_for_manual_input() is manual_controller

    builder.shutdown()

    assert preview_source.closed is True
    assert manual_controller.closed is True
