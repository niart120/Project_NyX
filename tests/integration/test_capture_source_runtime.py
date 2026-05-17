from pathlib import Path

import pytest

from nyxpy.framework.core.macro.exceptions import ConfigurationError
from nyxpy.framework.core.macro.registry import MacroDefinition
from nyxpy.framework.core.runtime.builder import create_device_runtime_builder
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
            protocol=object(),
            notification_handler=None,
            logger=FakeLoggerPort(),
            controller_output_factory=ControllerFactory(),
            frame_source_factory=frame_factory,
            settings={
                "capture_source_type": "screen_region",
                "capture_aspect_box_enabled": True,
            },
        )
