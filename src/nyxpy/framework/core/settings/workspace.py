from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from nyxpy.framework.core.macro.exceptions import ConfigurationError


@dataclass(frozen=True)
class WorkspacePaths:
    project_root: Path
    config_dir: Path
    macros_dir: Path
    resources_dir: Path
    snapshots_dir: Path
    runs_dir: Path
    logs_dir: Path


def resolve_project_root(
    *,
    explicit_root: Path | None = None,
    start: Path | None = None,
    allow_current_as_new: bool = False,
) -> Path:
    """Resolve the NyX project root without creating settings files."""
    if explicit_root is not None:
        return Path(explicit_root).resolve(strict=False)

    start_path = Path.cwd() if start is None else Path(start)
    start_path = start_path.resolve(strict=False)
    search_root = start_path if start_path.is_dir() else start_path.parent

    for candidate in (search_root, *search_root.parents):
        if (candidate / ".nyxpy").is_dir():
            return candidate

    if allow_current_as_new:
        return search_root

    raise ConfigurationError(
        "NyX workspace not found. Run `nyxpy init` in the project root.",
        code="NYX_WORKSPACE_NOT_FOUND",
        component="Workspace",
        details={
            "start": str(start_path),
            "explicit_root": False,
        },
    )


def ensure_workspace(project_root: Path) -> WorkspacePaths:
    """Create workspace directories and return canonical paths."""
    root = Path(project_root).resolve(strict=False)
    paths = WorkspacePaths(
        project_root=root,
        config_dir=root / ".nyxpy",
        macros_dir=root / "macros",
        resources_dir=root / "resources",
        snapshots_dir=root / "snapshots",
        runs_dir=root / "runs",
        logs_dir=root / "logs",
    )

    root.mkdir(parents=True, exist_ok=True)
    macros_dir_existed = paths.macros_dir.exists()
    for directory in (
        paths.config_dir,
        paths.macros_dir,
        paths.resources_dir,
        paths.snapshots_dir,
        paths.runs_dir,
        paths.logs_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    init_file = paths.macros_dir / "__init__.py"
    if not macros_dir_existed and not init_file.exists():
        init_file.write_text("", encoding="utf-8")

    return paths
