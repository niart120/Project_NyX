from __future__ import annotations

import os
from pathlib import Path

import cv2
import numpy as np
import pytest

from nyxpy.framework.core.io.resources import (
    DefaultResourcePathGuard,
    LocalResourceStore,
    LocalRunArtifactStore,
    MacroResourceScope,
    OverwritePolicy,
    ResourceAlreadyExistsError,
    ResourceConfigurationError,
    ResourceNotFoundError,
    ResourcePathError,
    ResourceReadError,
    ResourceSource,
    ResourceWriteError,
)
from nyxpy.framework.core.macro.registry import MacroDefinition


class Factory:
    def create(self):
        raise NotImplementedError


def make_definition(tmp_path: Path, macro_id: str = "sample") -> MacroDefinition:
    macro_root = tmp_path / "macros" / macro_id
    macro_root.mkdir(parents=True)
    return MacroDefinition(
        id=macro_id,
        aliases=(macro_id,),
        display_name="Sample",
        class_name="SampleMacro",
        module_name=f"macros.{macro_id}.macro",
        macro_root=macro_root,
        source_path=macro_root / "macro.py",
        settings_path=None,
        description="",
        tags=(),
        factory=Factory(),
    )


def write_image(path: Path) -> np.ndarray:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = np.full((4, 4, 3), 127, dtype=np.uint8)
    assert cv2.imwrite(str(path), image)
    return image


def test_macro_resource_scope_from_definition(tmp_path: Path) -> None:
    definition = make_definition(tmp_path, "sample")

    scope = MacroResourceScope.from_definition(definition, tmp_path)

    assert scope.macro_id == "sample"
    assert scope.assets_roots == (
        tmp_path.resolve() / "resources" / "sample" / "assets",
        definition.macro_root.resolve() / "assets",
    )


@pytest.mark.parametrize(
    "name", ["..\\escape.png", "nested/../escape.png", "C:\\x.png", "/x.png", "CON"]
)
def test_resource_path_guard_rejects_unsafe_paths(tmp_path: Path, name: str) -> None:
    guard = DefaultResourcePathGuard()

    with pytest.raises(ResourcePathError):
        guard.resolve_under_root(tmp_path, name)


def test_resource_path_guard_rejects_symlink_escape(tmp_path: Path) -> None:
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    outside_file = outside / "image.png"
    outside_file.write_bytes(b"not an image")
    link_path = root / "link.png"
    try:
        os.symlink(outside_file, link_path)
    except OSError as exc:
        pytest.skip(f"symlink creation is not available: {exc}")

    with pytest.raises(ResourcePathError):
        DefaultResourcePathGuard().resolve_under_root(root, "link.png")


def test_local_resource_store_prefers_standard_assets(tmp_path: Path) -> None:
    definition = make_definition(tmp_path, "sample")
    scope = MacroResourceScope.from_definition(definition, tmp_path)
    standard = tmp_path / "resources" / "sample" / "assets" / "icon.png"
    package = definition.macro_root / "assets" / "icon.png"
    write_image(standard)
    write_image(package)

    ref = LocalResourceStore(scope).resolve_asset_path("icon.png")

    assert ref.source is ResourceSource.STANDARD_ASSETS
    assert ref.path == standard.resolve()


def test_local_resource_store_falls_back_to_macro_package_assets(tmp_path: Path) -> None:
    definition = make_definition(tmp_path, "sample")
    scope = MacroResourceScope.from_definition(definition, tmp_path)
    package = definition.macro_root / "assets" / "icon.png"
    write_image(package)

    ref = LocalResourceStore(scope).resolve_asset_path("icon.png")

    assert ref.source is ResourceSource.MACRO_PACKAGE
    assert ref.path == package.resolve()


def test_local_resource_store_reports_missing_and_corrupt_images(tmp_path: Path) -> None:
    definition = make_definition(tmp_path, "sample")
    scope = MacroResourceScope.from_definition(definition, tmp_path)
    store = LocalResourceStore(scope)

    with pytest.raises(ResourceNotFoundError):
        store.resolve_asset_path("missing.png")

    corrupt = tmp_path / "resources" / "sample" / "assets" / "corrupt.png"
    corrupt.parent.mkdir(parents=True)
    corrupt.write_text("not an image")
    with pytest.raises(ResourceReadError):
        store.load_image("corrupt.png")


def test_local_run_artifact_store_saves_outputs_without_stripping_macro_prefix(
    tmp_path: Path,
) -> None:
    store = LocalRunArtifactStore(
        tmp_path / "runs" / "run-1" / "outputs", macro_id="sample", run_id="run-1"
    )
    image = np.zeros((2, 2, 3), dtype=np.uint8)

    ref = store.save_image("sample/img/out.png", image)

    assert ref.relative_path == Path("sample") / "img" / "out.png"
    assert ref.path.exists()
    assert (
        ref.path
        == (tmp_path / "runs" / "run-1" / "outputs" / "sample" / "img" / "out.png").resolve()
    )


def test_local_run_artifact_store_reports_imwrite_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = LocalRunArtifactStore(tmp_path / "outputs", macro_id="sample", run_id="run-1")
    image = np.zeros((2, 2, 3), dtype=np.uint8)
    monkeypatch.setattr(cv2, "imwrite", lambda *_args, **_kwargs: False)

    with pytest.raises(ResourceWriteError):
        store.save_image("out.png", image)


def test_local_run_artifact_store_overwrite_policies(tmp_path: Path) -> None:
    store = LocalRunArtifactStore(tmp_path / "outputs", macro_id="sample", run_id="run-1")
    image = np.zeros((2, 2, 3), dtype=np.uint8)
    store.save_image("out.png", image)

    with pytest.raises(ResourceAlreadyExistsError):
        store.save_image("out.png", image, overwrite=OverwritePolicy.ERROR)

    ref = store.save_image("out.png", image, overwrite=OverwritePolicy.UNIQUE)

    assert ref.relative_path == Path("out_1.png")
    assert ref.path.exists()


def test_local_run_artifact_store_open_output_atomic(tmp_path: Path) -> None:
    store = LocalRunArtifactStore(tmp_path / "outputs", macro_id="sample", run_id="run-1")

    with store.open_output("data.bin", mode="wb", atomic=True) as file:
        file.write(b"payload")

    assert (tmp_path / "outputs" / "data.bin").read_bytes() == b"payload"
    assert not list((tmp_path / "outputs").glob(".data.*"))

    with pytest.raises(ResourceAlreadyExistsError):
        store.open_output("data.bin", mode="xb", atomic=True)


def test_local_run_artifact_store_rejects_text_and_atomic_append(tmp_path: Path) -> None:
    store = LocalRunArtifactStore(tmp_path / "outputs", macro_id="sample", run_id="run-1")

    with pytest.raises(ResourceConfigurationError):
        store.open_output("data.txt", mode="w")
    with pytest.raises(ResourceConfigurationError):
        store.open_output("data.bin", mode="ab", atomic=True)


def test_local_run_artifact_store_open_output_replace_non_atomic(tmp_path: Path) -> None:
    store = LocalRunArtifactStore(tmp_path / "outputs", macro_id="sample", run_id="run-1")
    output = tmp_path / "outputs" / "data.bin"
    output.parent.mkdir()
    output.write_bytes(b"old")

    with store.open_output(
        "data.bin",
        mode="xb",
        overwrite=OverwritePolicy.REPLACE,
        atomic=False,
    ) as file:
        file.write(b"new")

    assert output.read_bytes() == b"new"
