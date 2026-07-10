from pathlib import Path

import numpy as np
import pytest

from nyxpy.framework.core.hardware.capture_source import WindowCaptureSourceConfig
from nyxpy.framework.core.hardware.device_discovery import DeviceDiscoveryResult, DeviceInfo
from nyxpy.framework.core.hardware.swbt.config import SwbtControllerConfig, resolve_controller_model
from nyxpy.framework.core.io.adapters import NoopNotificationAdapter, NotificationHandlerAdapter
from nyxpy.framework.core.io.controller_config import SerialControllerConfig
from nyxpy.framework.core.io.device_factories import (
    FrameSourcePortFactory,
    SerialControllerOutputPortFactory,
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
    def __init__(self, definition: MacroDefinition, settings: dict | None = None) -> None:
        self.definition = definition
        self.settings = settings or {}

    def resolve(self, name_or_id: str) -> MacroDefinition:
        return self.definition

    def get_settings(self, definition: MacroDefinition) -> dict:
        return dict(self.settings)


class Discovery:
    def __init__(self, *, serial_names=(), capture_names=()) -> None:
        self.serial_devices = {
            name: DeviceInfo(kind="serial", name=name, identifier=name) for name in serial_names
        }
        self.capture_devices = {
            name: DeviceInfo(kind="capture", name=name, identifier=0) for name in capture_names
        }
        self.detect_calls = 0

    @property
    def last_result(self) -> DeviceDiscoveryResult:
        return DeviceDiscoveryResult(
            serial_devices=tuple(self.serial_devices.values()),
            capture_devices=tuple(self.capture_devices.values()),
        )

    def detect(self, timeout_sec: float = 2.0) -> DeviceDiscoveryResult:
        self.detect_calls += 1
        return self.last_result

    def serial_names(self) -> list[str]:
        return list(self.serial_devices)

    def capture_names(self) -> list[str]:
        return list(self.capture_devices)


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


class RecordingSwbtFactory:
    def __init__(self) -> None:
        self.creates = []
        self.closed = False

    def create(self, *, config, allow_dummy: bool, timeout_sec: float):
        self.creates.append((config, allow_dummy, timeout_sec))
        return FakeControllerOutputPort()

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
    macro_settings = kwargs.pop("macro_settings", None)
    serial_name = kwargs.pop("serial_name", None)
    baudrate = kwargs.pop("baudrate", 9600)
    capture_name = kwargs.pop("capture_name", None)
    controller_config = kwargs.pop(
        "controller_config",
        SerialControllerConfig(device=serial_name, protocol="CH552", baudrate=baudrate),
    )
    controller_factory = SerialControllerOutputPortFactory(
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
        registry=Registry(definition(tmp_path), macro_settings),
        device_discovery=discovery,
        controller_config=controller_config,
        serial_controller_factory=controller_factory,
        frame_source_factory=frame_factory,
        capture_name=capture_name,
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


def test_runtime_builder_uses_global_command_debug_setting(tmp_path: Path) -> None:
    builder = make_builder(
        tmp_path,
        Discovery(),
        settings={"logging": {"command_debug_enabled": True}},
    )

    context = builder.build(RuntimeBuildRequest(macro_id="sample", allow_dummy=True))

    assert context.options.command_debug_enabled is True


def test_runtime_builder_allows_macro_command_debug_override(tmp_path: Path) -> None:
    builder = make_builder(
        tmp_path,
        Discovery(),
        settings={"logging": {"command_debug_enabled": False}},
        macro_settings={"logging": {"command_debug_enabled": True}},
    )

    context = builder.build(RuntimeBuildRequest(macro_id="sample", allow_dummy=True))

    assert context.options.command_debug_enabled is True


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
            controller_config=SerialControllerConfig(device=None),
            serial_manager=object(),
            capture_manager=object(),
            notification_handler=None,
            logger=FakeLoggerPort(),
        )


def test_make_controller_port_factory_selects_swbt(tmp_path: Path) -> None:
    swbt_factory = RecordingSwbtFactory()
    frame_factory = RecordingFrameFactory()
    swbt_config = SwbtControllerConfig(
        model=resolve_controller_model("pro-controller"),
        adapter="usb:0",
        key_store_path=tmp_path / ".nyxpy" / "swbt" / "pro-controller-bond.json",
        connect_timeout_sec=4.0,
    )
    builder = create_device_runtime_builder(
        project_root=tmp_path,
        registry=Registry(definition(tmp_path)),
        device_discovery=Discovery(),
        controller_config=swbt_config,
        swbt_controller_factory=swbt_factory,
        frame_source_factory=frame_factory,
        notification_handler=None,
        logger=FakeLoggerPort(),
    )

    context = builder.build(RuntimeBuildRequest(macro_id="sample"))
    builder.shutdown()

    assert isinstance(context.controller, FakeControllerOutputPort)
    assert swbt_factory.creates == [(swbt_config, False, 4.0)]
    assert swbt_factory.closed is True


def test_run_swbt_does_not_resolve_serial_protocol(monkeypatch, tmp_path: Path) -> None:
    def fail_create_protocol(_name):
        raise AssertionError("serial protocol should not be created for swbt")

    monkeypatch.setattr(
        "nyxpy.framework.core.runtime.builder.ProtocolFactory.create_protocol",
        fail_create_protocol,
    )
    swbt_config = SwbtControllerConfig(
        model=resolve_controller_model("pro-controller"),
        adapter="usb:0",
        key_store_path=tmp_path / ".nyxpy" / "swbt" / "pro-controller-bond.json",
    )
    builder = create_device_runtime_builder(
        project_root=tmp_path,
        registry=Registry(definition(tmp_path)),
        device_discovery=Discovery(),
        controller_config=swbt_config,
        swbt_controller_factory=RecordingSwbtFactory(),
        frame_source_factory=RecordingFrameFactory(),
        notification_handler=None,
        logger=FakeLoggerPort(),
    )

    builder.build(RuntimeBuildRequest(macro_id="sample"))


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
        artifact_store_factory=lambda _request, definition, run_id, artifact_dir_name: (
            FakeRunArtifactStore(
                tmp_path / "resources" / definition.id / "artifacts",
                macro_id=definition.id,
                run_id=run_id,
                artifact_dir_name=artifact_dir_name,
            )
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


def test_runtime_builder_discards_manual_controller_cache_without_closing_factory(
    tmp_path: Path,
) -> None:
    registry = Registry(definition(tmp_path))
    first_manual = FakeControllerOutputPort()
    second_manual = FakeControllerOutputPort()
    manual_controllers = iter((first_manual, second_manual))
    controller_shutdowns: list[str] = []
    builder = MacroRuntimeBuilder(
        project_root=tmp_path,
        registry=registry,
        controller_factory=lambda _request, _definition: FakeControllerOutputPort(),
        frame_source_factory=lambda _request, _definition: FakeFrameSourcePort(),
        resource_store_factory=lambda _request, definition: FakeResourceStore(
            MacroResourceScope.from_definition(definition, tmp_path)
        ),
        artifact_store_factory=lambda _request, definition, run_id, artifact_dir_name: (
            FakeRunArtifactStore(
                tmp_path / "resources" / definition.id / "artifacts",
                macro_id=definition.id,
                run_id=run_id,
                artifact_dir_name=artifact_dir_name,
            )
        ),
        notification_factory=lambda _request, _definition: FakeNotificationPort(),
        logger_factory=lambda _request, _definition: FakeLoggerPort(),
        manual_controller_factory=lambda: next(manual_controllers),
        controller_shutdown_callbacks=(lambda: controller_shutdowns.append("closed"),),
    )

    assert builder.controller_output_for_manual_input() is first_manual
    builder.discard_manual_controller(first_manual)
    assert builder.controller_output_for_manual_input() is second_manual

    assert first_manual.closed is False
    assert controller_shutdowns == []

    builder.shutdown()

    assert second_manual.closed is True
    assert controller_shutdowns == ["closed"]


def test_runtime_builder_can_transfer_manual_controller_without_closing_factory(
    tmp_path: Path,
) -> None:
    registry = Registry(definition(tmp_path))
    manual_controller = FakeControllerOutputPort()
    controller_shutdowns: list[str] = []

    previous_builder = MacroRuntimeBuilder(
        project_root=tmp_path,
        registry=registry,
        controller_factory=lambda _request, _definition: FakeControllerOutputPort(),
        frame_source_factory=lambda _request, _definition: FakeFrameSourcePort(),
        resource_store_factory=lambda _request, definition: FakeResourceStore(
            MacroResourceScope.from_definition(definition, tmp_path)
        ),
        artifact_store_factory=lambda _request, definition, run_id, artifact_dir_name: (
            FakeRunArtifactStore(
                tmp_path / "resources" / definition.id / "artifacts",
                macro_id=definition.id,
                run_id=run_id,
                artifact_dir_name=artifact_dir_name,
            )
        ),
        notification_factory=lambda _request, _definition: FakeNotificationPort(),
        logger_factory=lambda _request, _definition: FakeLoggerPort(),
        manual_controller_factory=lambda: manual_controller,
        controller_shutdown_callbacks=(lambda: controller_shutdowns.append("previous"),),
    )
    next_builder = MacroRuntimeBuilder(
        project_root=tmp_path,
        registry=registry,
        controller_factory=lambda _request, _definition: FakeControllerOutputPort(),
        frame_source_factory=lambda _request, _definition: FakeFrameSourcePort(),
        resource_store_factory=lambda _request, definition: FakeResourceStore(
            MacroResourceScope.from_definition(definition, tmp_path)
        ),
        artifact_store_factory=lambda _request, definition, run_id, artifact_dir_name: (
            FakeRunArtifactStore(
                tmp_path / "resources" / definition.id / "artifacts",
                macro_id=definition.id,
                run_id=run_id,
                artifact_dir_name=artifact_dir_name,
            )
        ),
        notification_factory=lambda _request, _definition: FakeNotificationPort(),
        logger_factory=lambda _request, _definition: FakeLoggerPort(),
    )

    assert previous_builder.controller_output_for_manual_input() is manual_controller
    controller_callbacks = previous_builder.detach_controller_shutdown_callbacks()
    next_builder.attach_manual_controller(previous_builder.detach_manual_controller())
    next_builder.extend_controller_shutdown_callbacks(controller_callbacks)
    previous_builder.shutdown()

    assert manual_controller.closed is False
    assert controller_shutdowns == []

    next_builder.shutdown()

    assert manual_controller.closed is True
    assert controller_shutdowns == ["previous"]


def test_runtime_builder_can_transfer_preview_source_without_closing_factory(
    tmp_path: Path,
) -> None:
    registry = Registry(definition(tmp_path))
    preview_source = FakeFrameSourcePort()
    frame_shutdowns: list[str] = []

    previous_builder = MacroRuntimeBuilder(
        project_root=tmp_path,
        registry=registry,
        controller_factory=lambda _request, _definition: FakeControllerOutputPort(),
        frame_source_factory=lambda _request, _definition: FakeFrameSourcePort(),
        resource_store_factory=lambda _request, definition: FakeResourceStore(
            MacroResourceScope.from_definition(definition, tmp_path)
        ),
        artifact_store_factory=lambda _request, definition, run_id, artifact_dir_name: (
            FakeRunArtifactStore(
                tmp_path / "resources" / definition.id / "artifacts",
                macro_id=definition.id,
                run_id=run_id,
                artifact_dir_name=artifact_dir_name,
            )
        ),
        notification_factory=lambda _request, _definition: FakeNotificationPort(),
        logger_factory=lambda _request, _definition: FakeLoggerPort(),
        preview_frame_source_factory=lambda: preview_source,
        frame_source_shutdown_callbacks=(lambda: frame_shutdowns.append("previous"),),
    )
    next_builder = MacroRuntimeBuilder(
        project_root=tmp_path,
        registry=registry,
        controller_factory=lambda _request, _definition: FakeControllerOutputPort(),
        frame_source_factory=lambda _request, _definition: FakeFrameSourcePort(),
        resource_store_factory=lambda _request, definition: FakeResourceStore(
            MacroResourceScope.from_definition(definition, tmp_path)
        ),
        artifact_store_factory=lambda _request, definition, run_id, artifact_dir_name: (
            FakeRunArtifactStore(
                tmp_path / "resources" / definition.id / "artifacts",
                macro_id=definition.id,
                run_id=run_id,
                artifact_dir_name=artifact_dir_name,
            )
        ),
        notification_factory=lambda _request, _definition: FakeNotificationPort(),
        logger_factory=lambda _request, _definition: FakeLoggerPort(),
    )

    assert previous_builder.frame_source_for_preview() is preview_source
    frame_callbacks = previous_builder.detach_frame_source_shutdown_callbacks()
    next_builder.attach_preview_frame_source(previous_builder.detach_preview_frame_source())
    next_builder.extend_frame_source_shutdown_callbacks(frame_callbacks)
    previous_builder.shutdown()

    assert preview_source.closed is False
    assert frame_shutdowns == []

    next_builder.shutdown()

    assert preview_source.closed is True
    assert frame_shutdowns == ["previous"]


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
        artifact_store_factory=lambda _request, definition, run_id, artifact_dir_name: (
            FakeRunArtifactStore(
                tmp_path / "resources" / definition.id / "artifacts",
                macro_id=definition.id,
                run_id=run_id,
                artifact_dir_name=artifact_dir_name,
            )
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
