import pytest

from nyxpy.framework.core.macro.exceptions import ConfigurationError
from nyxpy.framework.core.settings.workspace import ensure_workspace, resolve_project_root


def test_resolve_project_root_prefers_explicit_root(tmp_path) -> None:
    explicit = tmp_path / "explicit"
    nested = tmp_path / "workspace" / "macros" / "sample"
    (tmp_path / "workspace" / ".nyxpy").mkdir(parents=True)
    nested.mkdir(parents=True)

    assert resolve_project_root(explicit_root=explicit, start=nested) == explicit.resolve()


def test_resolve_project_root_finds_parent_marker_without_creating_marker(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    nested = workspace / "macros" / "sample"
    (workspace / ".nyxpy").mkdir(parents=True)
    nested.mkdir(parents=True)

    assert resolve_project_root(start=nested) == workspace.resolve()
    assert not (nested / ".nyxpy").exists()


def test_resolve_project_root_rejects_unknown_workspace(tmp_path) -> None:
    with pytest.raises(ConfigurationError) as exc_info:
        resolve_project_root(start=tmp_path)

    assert exc_info.value.code == "NYX_WORKSPACE_NOT_FOUND"
    assert exc_info.value.details["start"] == str(tmp_path.resolve())


def test_resolve_project_root_allows_current_as_new(tmp_path) -> None:
    assert resolve_project_root(start=tmp_path, allow_current_as_new=True) == tmp_path.resolve()


def test_ensure_workspace_creates_expected_directories_without_static(tmp_path) -> None:
    paths = ensure_workspace(tmp_path)

    assert paths.project_root == tmp_path.resolve()
    for directory in (
        paths.config_dir,
        paths.macros_dir,
        paths.resources_dir,
        paths.snapshots_dir,
        paths.runs_dir,
        paths.logs_dir,
    ):
        assert directory.exists()
    assert (paths.macros_dir / "__init__.py").exists()
    assert not (tmp_path / "static").exists()
