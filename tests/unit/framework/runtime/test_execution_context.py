from pathlib import Path
from types import MappingProxyType

import pytest

from nyxpy.framework.core.macro.registry import MacroDefinition
from nyxpy.framework.core.runtime.builder import MacroRuntimeBuilder
from nyxpy.framework.core.runtime.context import RuntimeBuildRequest
from tests.support.fake_execution_context import make_fake_execution_context
from tests.support.fakes import (
    FakeControllerOutputPort,
    FakeFrameSourcePort,
    FakeLoggerPort,
    FakeNotificationPort,
)


class Registry:
    def __init__(self, definition: MacroDefinition, settings: dict) -> None:
        self.definition = definition
        self.settings = settings

    def resolve(self, name_or_id: str) -> MacroDefinition:
        return self.definition

    def get_settings(self, definition: MacroDefinition) -> dict:
        return dict(self.settings)


def test_execution_context_shallow_copies_args_and_metadata(tmp_path) -> None:
    nested = {"value": 1}
    exec_args = {"nested": nested}
    metadata = {"source": "test"}

    context = make_fake_execution_context(tmp_path, exec_args=exec_args, metadata=metadata)
    exec_args["added"] = "ignored"
    metadata["added"] = "ignored"
    nested["value"] = 2

    assert isinstance(context.exec_args, MappingProxyType)
    assert "added" not in context.exec_args
    assert "added" not in context.metadata
    assert context.exec_args["nested"]["value"] == 2
    with pytest.raises(TypeError):
        context.exec_args["new"] = "blocked"


def test_execution_context_does_not_hold_command(tmp_path) -> None:
    context = make_fake_execution_context(tmp_path)

    assert not hasattr(context, "command")


def test_exec_args_override_file_settings(tmp_path) -> None:
    definition = MacroDefinition(
        id="sample",
        aliases=("sample",),
        display_name="Sample",
        class_name="SampleMacro",
        module_name="tests.sample",
        macro_root=Path(__file__).parent,
        source_path=Path(__file__),
        settings_path=None,
        description="",
        tags=(),
        factory=object(),
    )
    base_context = make_fake_execution_context(tmp_path)
    builder = MacroRuntimeBuilder(
        project_root=tmp_path,
        registry=Registry(definition, {"value": "file", "keep": "file"}),
        controller_factory=lambda _request, _definition: FakeControllerOutputPort(),
        frame_source_factory=lambda _request, _definition: FakeFrameSourcePort(),
        resource_store_factory=lambda _request, _definition: base_context.resources,
        artifact_store_factory=lambda _request, _definition, _run_id: base_context.artifacts,
        notification_factory=lambda _request, _definition: FakeNotificationPort(),
        logger_factory=lambda _request, _definition: FakeLoggerPort(),
    )

    context = builder.build(
        RuntimeBuildRequest(macro_id="sample", exec_args={"value": "exec", "other": 3})
    )

    assert context.exec_args == {"value": "exec", "keep": "file", "other": 3}
