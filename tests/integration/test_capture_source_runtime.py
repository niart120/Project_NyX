from pathlib import Path

import numpy as np
import pytest

from nyxpy.framework.core.hardware.capture_source import PonkanCaptureSourceConfig
from nyxpy.framework.core.io.controller_config import SerialControllerConfig
from nyxpy.framework.core.macro.command import DefaultCommand
from nyxpy.framework.core.macro.exceptions import ConfigurationError
from nyxpy.framework.core.macro.registry import MacroDefinition
from nyxpy.framework.core.runtime.builder import create_device_runtime_builder
from nyxpy.framework.core.runtime.context import RuntimeBuildRequest
from tests.support.fakes import (
    FakeControllerOutputPort,
    FakeFrameSourcePort,
    FakeLoggerPort,
)


class Registry:
    def __init__(self, definition: MacroDefinition) -> None:
        self.definition = definition

    def resolve(self, name_or_id: str) -> MacroDefinition:
        return self.definition

    def get_settings(self, definition: MacroDefinition) -> dict:
        return {}


class ControllerFactory:
    def create(self, *, name, baudrate, allow_dummy, timeout_sec):
        return FakeControllerOutputPort()

    def close(self) -> None:
        pass


class FrameFactory:
    def __init__(self) -> None:
        self.sources = []

    def create(self, *, source, allow_dummy, timeout_sec):
        self.sources.append(source)
        return FakeFrameSourcePort()

    def close(self) -> None:
        pass


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


def test_runtime_builder_rejects_removed_screen_region_source(tmp_path: Path) -> None:
    frame_factory = FrameFactory()
    with pytest.raises(ConfigurationError, match="invalid capture source type"):
        create_device_runtime_builder(
            project_root=tmp_path,
            registry=Registry(definition(tmp_path)),
            controller_config=SerialControllerConfig(device=None),
            notification_handler=None,
            logger=FakeLoggerPort(),
            serial_controller_factory=ControllerFactory(),
            frame_source_factory=frame_factory,
            settings={
                "capture_source_type": "screen_region",
                "capture_aspect_box_enabled": True,
            },
        )


def test_runtime_uses_ponkan_capture_frame_source(tmp_path: Path) -> None:
    frame = np.zeros((480, 854, 3), dtype=np.uint8)

    class PonkanFrameFactory:
        def __init__(self) -> None:
            self.sources = []

        def create(self, *, source, allow_dummy, timeout_sec):
            self.sources.append(source)
            return FakeFrameSourcePort(frame)

        def close(self) -> None:
            pass

    frame_factory = PonkanFrameFactory()
    builder = create_device_runtime_builder(
        project_root=tmp_path,
        registry=Registry(definition(tmp_path)),
        controller_config=SerialControllerConfig(device=None),
        notification_handler=None,
        logger=FakeLoggerPort(),
        serial_controller_factory=ControllerFactory(),
        frame_source_factory=frame_factory,
        settings={
            "capture_source_type": "capture",
            "capture_provider": "ponkan",
            "capture_device_profile": "n3dsxl",
            "ponkan_backend": "d3xx",
        },
    )

    context = builder.build(RuntimeBuildRequest(macro_id="sample"))
    context.frame_source.initialize()
    captured = DefaultCommand(context=context).capture()

    assert isinstance(frame_factory.sources[-1], PonkanCaptureSourceConfig)
    assert frame_factory.sources[-1].ponkan_backend == "d3xx"
    assert captured.shape == (720, 1280, 3)
