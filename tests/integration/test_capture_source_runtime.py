from pathlib import Path

from nyxpy.framework.core.hardware.capture_source import ScreenRegionCaptureSourceConfig
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


def test_runtime_builder_passes_screen_region_capture_source_config(tmp_path: Path) -> None:
    frame_factory = FrameFactory()
    builder = create_device_runtime_builder(
        project_root=tmp_path,
        registry=Registry(definition(tmp_path)),
        protocol=object(),
        notification_handler=None,
        logger=FakeLoggerPort(),
        controller_output_factory=ControllerFactory(),
        frame_source_factory=frame_factory,
        settings={
            "capture_source_type": "screen_region",
            "capture_region": {"left": 10, "top": 20, "width": 600, "height": 720},
            "capture_aspect_box_enabled": True,
        },
    )

    builder.build(RuntimeBuildRequest(macro_id="sample"))

    source = frame_factory.sources[-1]
    assert isinstance(source, ScreenRegionCaptureSourceConfig)
    assert source.region.left == 10
    assert source.region.width == 600
    assert source.transform.aspect_box_enabled is True
