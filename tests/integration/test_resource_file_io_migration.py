from __future__ import annotations

from pathlib import Path

import numpy as np

from examples.macros.sample_turbo_a_macro import SampleTurboAMacro
from nyxpy.framework.core.io.resources import (
    LocalResourceStore,
    LocalRunArtifactStore,
    MacroResourceScope,
)
from nyxpy.framework.core.macro.base import MacroBase
from nyxpy.framework.core.macro.command import Command
from nyxpy.framework.core.macro.registry import MacroDefinition
from nyxpy.framework.core.runtime.builder import MacroRuntimeBuilder
from nyxpy.framework.core.runtime.context import RuntimeBuildRequest
from nyxpy.framework.core.runtime.result import RunStatus
from tests.support.fakes import (
    FakeControllerOutputPort,
    FakeFrameSourcePort,
    FakeLoggerPort,
    FakeNotificationPort,
)


class SavingMacro(MacroBase):
    def initialize(self, cmd: Command, args: dict) -> None:
        pass

    def run(self, cmd: Command) -> None:
        image = np.zeros((2, 2, 3), dtype=np.uint8)
        cmd.save_artifact_img("sample/img/out.png", image)

    def finalize(self, cmd: Command) -> None:
        pass


class Factory:
    def __init__(self, macro_cls: type[MacroBase] = SavingMacro) -> None:
        self.macro_cls = macro_cls

    def create(self) -> MacroBase:
        return self.macro_cls()


class Registry:
    def __init__(self, definition: MacroDefinition) -> None:
        self.definition = definition

    def resolve(self, name_or_id: str) -> MacroDefinition:
        return self.definition

    def get_settings(self, definition: MacroDefinition) -> dict:
        return {}


def make_definition(
    tmp_path: Path,
    *,
    macro_id: str = "sample",
    class_name: str = "SavingMacro",
    factory: Factory | None = None,
) -> MacroDefinition:
    macro_root = tmp_path / "macros" / macro_id
    macro_root.mkdir(parents=True)
    return MacroDefinition(
        id=macro_id,
        aliases=(macro_id,),
        display_name="Sample",
        class_name=class_name,
        module_name=f"macros.{macro_id}.macro",
        macro_root=macro_root,
        source_path=macro_root / "macro.py",
        settings_path=None,
        description="",
        tags=(),
        factory=factory or Factory(),
    )


def make_builder(tmp_path: Path, definition: MacroDefinition) -> MacroRuntimeBuilder:
    builder = MacroRuntimeBuilder(
        project_root=tmp_path,
        registry=Registry(definition),
        controller_factory=lambda _request, _definition: FakeControllerOutputPort(),
        frame_source_factory=lambda _request, _definition: FakeFrameSourcePort(),
        resource_store_factory=lambda _request, macro_definition: LocalResourceStore(
            MacroResourceScope.from_definition(macro_definition, tmp_path)
        ),
        artifact_store_factory=lambda _request, macro_definition, run_id, artifact_dir_name: (
            LocalRunArtifactStore(
                MacroResourceScope.from_definition(macro_definition, tmp_path).artifacts_root,
                macro_id=macro_definition.id,
                run_id=run_id,
                artifact_dir_name=artifact_dir_name,
            )
        ),
        notification_factory=lambda _request, _definition: FakeNotificationPort(),
        logger_factory=lambda _request, _definition: FakeLoggerPort(),
    )
    return builder


def test_runtime_saves_command_images_to_resource_artifacts(tmp_path: Path) -> None:
    builder = make_builder(tmp_path, make_definition(tmp_path))

    result = builder.run(RuntimeBuildRequest(macro_id="sample", entrypoint="test"))

    assert result.status is RunStatus.SUCCESS
    assert result.artifacts
    assert (
        tmp_path / "resources" / "sample" / "artifacts" / result.artifacts[0].relative_path
    ).exists()


def test_sample_turbo_macro_saves_capture_to_resource_artifacts_without_prefix_stripping(
    tmp_path: Path,
) -> None:
    definition = make_definition(
        tmp_path,
        macro_id="sample_turbo_a_macro",
        class_name="SampleTurboAMacro",
        factory=Factory(SampleTurboAMacro),
    )
    builder = make_builder(tmp_path, definition)

    result = builder.run(
        RuntimeBuildRequest(
            macro_id="sample_turbo_a_macro",
            entrypoint="test",
            exec_args={
                "count": 1,
                "press_dur": 0,
                "wait_dur": 0,
                "capture_after": True,
                "capture_name": "sample_turbo_a_macro/img/result.png",
            },
        )
    )

    assert result.status is RunStatus.SUCCESS
    assert result.artifacts
    assert (
        tmp_path
        / "resources"
        / "sample_turbo_a_macro"
        / "artifacts"
        / result.artifacts[0].relative_path
    ).exists()
    assert result.artifacts[0].relative_path.parts[-3:] == (
        "sample_turbo_a_macro",
        "img",
        "result.png",
    )
