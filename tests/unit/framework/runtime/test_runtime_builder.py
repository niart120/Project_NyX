from pathlib import Path

import numpy as np
import pytest

from nyxpy.framework.core.hardware.capture_source import WindowCaptureSourceConfig
from nyxpy.framework.core.hardware.device_discovery import DeviceInfo
from nyxpy.framework.core.io.adapters import NoopNotificationAdapter, NotificationHandlerAdapter
from nyxpy.framework.core.io.device_factories import (
    ControllerOutputPortFactory,
    FrameSourcePortFactory,
)
from nyxpy.framework.core.io.resources import MacroResourceScope
from nyxpy.framework.core.macro.exceptions import ConfigurationError
from nyxpy.framework.core.macro.registry import MacroDefinition
from nyxpy.framework.core.runtime.builder import MacroRuntimeBuilder, create_device_runtime_builder
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


class Discovery:
    def __init__(self, *, serial_names=(), capture_names=()) -> None:
        self.serial_devices = {
            name: DeviceInfo(kind="serial", name=name, identifier=name) for name in serial_names
        }
        self.capture_devices = {
            name: DeviceInfo(kind="capture", name=name, identifier=0) for name in capture_names
        }

    def serial_names(self) -> list[str]:
        return list(self.serial_devices)

    def capture_names(self) -> list[str]:
        return list(self.capture_devices)

    def find_serial(self, name: str, timeout_sec: float):
        return self.serial_devices.get(name)

    def find_capture(self, name: str, timeout_sec: float):
        return self.capture_devices.get(name)


class SerialDevice:
    def __init__(self, port: str) -> None:
        self.port = port
        self.opened_with = None
        self.closed = False

    def open(self, baudrate: int) -> None:
        self.opened_with = baudrate

    def send(self, data: bytes) -> None:
        pass

    def close(self) -> None:
        self.closed = True


class CaptureDevice:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.initialized = False
        self.released = False
        self.frame = np.zeros((2, 2, 3), dtype=np.uint8)

    def initialize(self) -> None:
        self.initialized = True

    def get_frame(self):
        return self.frame

    def release(self) -> None:
        self.released = True


class RecordingFrameFactory:
    def __init__(self) -> None:
        self.sources = []
        self.closed = False

    def create(self, *, source, allow_dummy: bool, timeout_sec: float):
        self.sources.append(source)
        return FakeFrameSourcePort()

    def close(self) -> None:
        self.closed = True


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


def make_builder(tmp_path: Path, discovery: Discovery, **kwargs):
    notification_handler = kwargs.pop("notification_handler", None)
    frame_source_factory = kwargs.pop("frame_source_factory", None)
    controller_factory = ControllerOutputPortFactory(
        discovery=discovery,
        protocol=object(),
        serial_factory=SerialDevice,
    )
    frame_factory = frame_source_factory or FrameSourcePortFactory(
        discovery=discovery,
        logger=FakeLoggerPort(),
        capture_factory=CaptureDevice,
    )
    return create_device_runtime_builder(
        project_root=tmp_path,
        registry=Registry(definition(tmp_path)),
        device_discovery=discovery,
        controller_output_factory=controller_factory,
        frame_source_factory=frame_factory,
        protocol=object(),
        notification_handler=notification_handler,
        logger=FakeLoggerPort(),
        **kwargs,
    )


def test_runtime_builder_disallows_dummy_by_default(tmp_path: Path) -> None:
    builder = make_builder(tmp_path, Discovery())

    with pytest.raises(ConfigurationError, match="serial device is not selected"):
        builder.build(RuntimeBuildRequest(macro_id="sample"))


def test_runtime_builder_allows_dummy_when_explicit(tmp_path: Path) -> None:
    builder = make_builder(tmp_path, Discovery())

    context = builder.build(RuntimeBuildRequest(macro_id="sample", allow_dummy=True))

    assert context.options.allow_dummy is True
    assert isinstance(context.notifications, NoopNotificationAdapter)


def test_runtime_builder_wraps_notification_handler(tmp_path: Path) -> None:
    handler = object()
    builder = make_builder(tmp_path, Discovery(), notification_handler=handler)

    context = builder.build(RuntimeBuildRequest(macro_id="sample", allow_dummy=True))

    assert isinstance(context.notifications, NotificationHandlerAdapter)
    assert context.notifications.notification_handler is handler


def test_runtime_builder_selects_requested_devices(tmp_path: Path) -> None:
    discovery = Discovery(serial_names=("COM1",), capture_names=("Camera1",))
    builder = make_builder(
        tmp_path,
        discovery,
        serial_name="COM1",
        capture_name="Camera1",
        baudrate=115200,
    )

    context = builder.build(RuntimeBuildRequest(macro_id="sample"))

    assert context.controller.serial_device.opened_with == 115200
    assert context.frame_source.capture_device.kwargs["device_index"] == 0


def test_runtime_builder_reuses_device_instances(tmp_path: Path) -> None:
    discovery = Discovery(serial_names=("COM1",), capture_names=("Camera1",))
    builder = make_builder(
        tmp_path,
        discovery,
        serial_name="COM1",
        capture_name="Camera1",
    )

    first = builder.build(RuntimeBuildRequest(macro_id="sample"))
    second = builder.build(RuntimeBuildRequest(macro_id="sample"))

    assert first.controller.serial_device is second.controller.serial_device
    assert first.frame_source.capture_device is second.frame_source.capture_device


def test_runtime_builder_passes_capture_source_config_from_settings(tmp_path: Path) -> None:
    discovery = Discovery(serial_names=("COM1",), capture_names=("Camera1",))
    frame_factory = RecordingFrameFactory()
    builder = make_builder(
        tmp_path,
        discovery,
        serial_name="COM1",
        frame_source_factory=frame_factory,
        settings={
            "capture_source_type": "window",
            "capture_window_title": "Viewer",
            "capture_window_match_mode": "contains",
            "capture_backend": "mss",
            "capture_aspect_box_enabled": True,
        },
    )

    builder.build(RuntimeBuildRequest(macro_id="sample"))

    source = frame_factory.sources[-1]
    assert isinstance(source, WindowCaptureSourceConfig)
    assert source.title_pattern == "Viewer"
    assert source.match_mode == "contains"
    assert source.transform.aspect_box_enabled is True


def test_runtime_builder_does_not_override_window_source_with_capture_name(
    tmp_path: Path,
) -> None:
    discovery = Discovery(serial_names=("COM1",), capture_names=("Camera1",))
    frame_factory = RecordingFrameFactory()
    builder = make_builder(
        tmp_path,
        discovery,
        serial_name="COM1",
        capture_name="Camera1",
        frame_source_factory=frame_factory,
        settings={
            "capture_source_type": "window",
            "capture_window_title": "Viewer",
            "capture_window_match_mode": "contains",
            "capture_backend": "mss",
        },
    )

    builder.frame_source_for_preview()
    builder.build(RuntimeBuildRequest(macro_id="sample"))

    assert all(isinstance(source, WindowCaptureSourceConfig) for source in frame_factory.sources)


def test_runtime_builder_rejects_legacy_manager_arguments(tmp_path: Path) -> None:
    with pytest.raises(TypeError):
        create_device_runtime_builder(
            project_root=tmp_path,
            registry=Registry(definition(tmp_path)),
            serial_manager=object(),
            capture_manager=object(),
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


def test_runtime_builder_does_not_cache_failed_preview_source(tmp_path: Path) -> None:
    registry = Registry(definition(tmp_path))

    class FailingFrameSourcePort(FakeFrameSourcePort):
        def initialize(self) -> None:
            raise RuntimeError("preview failed")

    first_preview_source = FailingFrameSourcePort()
    second_preview_source = FakeFrameSourcePort()
    preview_sources = iter((first_preview_source, second_preview_source))
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
        preview_frame_source_factory=lambda: next(preview_sources),
    )

    with pytest.raises(RuntimeError, match="preview failed"):
        builder.frame_source_for_preview()

    assert first_preview_source.closed is True
    assert builder.frame_source_for_preview() is second_preview_source
    assert second_preview_source.initialized is True
