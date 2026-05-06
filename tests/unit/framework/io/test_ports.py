from pathlib import Path

import pytest

from nyxpy.framework.core.constants import Button, KeyCode
from nyxpy.framework.core.io.ports import SleepControlCapability, TouchInputCapability
from nyxpy.framework.core.io.resources import (
    DefaultResourcePathGuard,
    MacroResourceScope,
    ResourcePathError,
)
from tests.support.fakes import FakeControllerOutputPort, FakeFullCapabilityController


def test_controller_output_port_contract_records_basic_operations() -> None:
    controller = FakeControllerOutputPort()

    controller.press((Button.A,))
    controller.hold((Button.B,))
    controller.release()
    controller.keyboard("Hello")
    controller.type_key(KeyCode("A"))
    controller.close()

    assert controller.events == [
        ("press", (Button.A,)),
        ("hold", (Button.B,)),
        ("release", ()),
        ("keyboard", "Hello"),
        ("type_key", KeyCode("A")),
        ("close", None),
    ]


def test_optional_controller_capabilities_are_runtime_checkable() -> None:
    base = FakeControllerOutputPort()
    full = FakeFullCapabilityController()

    assert not isinstance(base, TouchInputCapability)
    assert not isinstance(base, SleepControlCapability)
    assert isinstance(full, TouchInputCapability)
    assert isinstance(full, SleepControlCapability)


def test_resource_path_guard_accepts_windows_relative_path(tmp_path: Path) -> None:
    guard = DefaultResourcePathGuard()

    missing_root = tmp_path / "missing"
    result = guard.resolve_under_root(missing_root, "images\\result.png")

    assert result == missing_root.resolve(strict=False) / "images" / "result.png"
    assert not missing_root.exists()


@pytest.mark.parametrize("name", ["", ".", "../escape.png", "/rooted.png", "\\rooted.png"])
def test_resource_path_guard_rejects_invalid_paths(tmp_path: Path, name: str) -> None:
    with pytest.raises(ResourcePathError):
        DefaultResourcePathGuard().resolve_under_root(tmp_path, name)


@pytest.mark.parametrize(
    "name", ["C:drive-relative.png", "C:\\absolute.png", "\\\\server\\share\\x.png"]
)
def test_resource_path_guard_rejects_windows_drive_and_unc(tmp_path: Path, name: str) -> None:
    with pytest.raises(ResourcePathError):
        DefaultResourcePathGuard().resolve_under_root(tmp_path, name)


def test_macro_resource_scope_candidate_asset_paths_keep_lookup_order(tmp_path: Path) -> None:
    standard_assets = tmp_path / "resources" / "sample" / "assets"
    package_assets = tmp_path / "macros" / "sample" / "assets"
    scope = MacroResourceScope(
        project_root=tmp_path,
        macro_id="sample",
        macro_root=tmp_path / "macros" / "sample",
        assets_roots=(standard_assets, package_assets),
    )

    assert scope.candidate_asset_paths("template.png") == (
        standard_assets.resolve() / "template.png",
        package_assets.resolve() / "template.png",
    )
