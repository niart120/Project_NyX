from __future__ import annotations

from pathlib import Path
from typing import Any

import tomlkit

from nyxpy.framework.core.macro.registry import MacroDefinition, MacroSettingsSource
from nyxpy.framework.core.settings.exceptions import ConfigurationError


class MacroSettingsResolver:
    def __init__(self, project_root: Path) -> None:
        self.project_root = Path(project_root).resolve()

    def resolve(self, definition: MacroDefinition) -> MacroSettingsSource | None:
        if definition.settings_path is None:
            return None

        path = definition.settings_path
        if isinstance(path, Path):
            candidate = path if path.is_absolute() else definition.macro_root / path
            return self._source(candidate, definition.macro_root, "path")

        path_text = str(path)
        self._validate_portable_path(path_text)
        if path_text.startswith("project:"):
            relative_path = path_text.removeprefix("project:")
            self._validate_portable_path(relative_path)
            return self._source(self.project_root / relative_path, self.project_root, "manifest")

        return self._source(definition.macro_root / path_text, definition.macro_root, "manifest")

    def load(self, definition: MacroDefinition) -> dict[str, Any]:
        source = self.resolve(definition)
        if source is None:
            return {}
        try:
            return dict(tomlkit.loads(source.path.read_text(encoding="utf-8")))
        except tomlkit.exceptions.ParseError as exc:
            raise ConfigurationError(
                f"Failed to parse macro settings: {source.path}",
                code="NYX_SETTINGS_PARSE_FAILED",
            ) from exc

    def _source(self, candidate: Path, root: Path, source: str) -> MacroSettingsSource:
        resolved_root = root.resolve()
        resolved_candidate = candidate.resolve(strict=False)
        try:
            resolved_candidate.relative_to(resolved_root)
        except ValueError as exc:
            raise ConfigurationError(
                f"settings path escapes allowed root: {candidate}",
                code="NYX_SETTINGS_PATH_INVALID",
            ) from exc
        return MacroSettingsSource(path=resolved_candidate, source=source)

    def _validate_portable_path(self, path_text: str) -> None:
        if not path_text or "\\" in path_text:
            raise ConfigurationError(
                f"invalid portable settings path: {path_text!r}",
                code="NYX_SETTINGS_PATH_INVALID",
            )
        path = Path(path_text)
        if path.is_absolute() or ".." in path.parts:
            raise ConfigurationError(
                f"invalid portable settings path: {path_text!r}",
                code="NYX_SETTINGS_PATH_INVALID",
            )
