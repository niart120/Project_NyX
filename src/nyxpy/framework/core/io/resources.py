from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import BinaryIO, Protocol

import cv2

from nyxpy.framework.core.macro.exceptions import ResourceError


class ResourceKind(StrEnum):
    ASSET = "asset"
    OUTPUT = "output"


class ResourceSource(StrEnum):
    STANDARD_ASSETS = "standard_assets"
    MACRO_PACKAGE = "macro_package"
    PACKAGE_RESOURCE = "package_resource"
    RUN_OUTPUTS = "run_outputs"


class OverwritePolicy(StrEnum):
    ERROR = "error"
    REPLACE = "replace"
    UNIQUE = "unique"


class ResourcePathError(ResourceError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="NYX_RESOURCE_PATH_INVALID", component="ResourcePathGuard")


class ResourceNotFoundError(ResourceError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="NYX_RESOURCE_READ_FAILED", component="ResourceStorePort")


class ResourceReadError(ResourceError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="NYX_RESOURCE_READ_FAILED", component="ResourceStorePort")


class ResourceWriteError(ResourceError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="NYX_RESOURCE_WRITE_FAILED", component="RunArtifactStore")


class ResourceAlreadyExistsError(ResourceWriteError):
    pass


class ResourceConfigurationError(ResourceError):
    def __init__(self, message: str) -> None:
        super().__init__(
            message,
            code="NYX_RESOURCE_PATH_INVALID",
            component="ResourceConfiguration",
        )


@dataclass(frozen=True)
class MacroResourceScope:
    project_root: Path
    macro_id: str
    macro_root: Path | None
    assets_roots: tuple[Path, ...]

    def candidate_asset_paths(
        self, name: str | Path, guard: ResourcePathGuard | None = None
    ) -> tuple[Path, ...]:
        path_guard = guard or DefaultResourcePathGuard()
        return tuple(path_guard.resolve_under_root(root, name) for root in self.assets_roots)


@dataclass(frozen=True)
class ResourceRef:
    kind: ResourceKind
    source: ResourceSource
    path: Path
    relative_path: Path
    macro_id: str
    run_id: str | None = None


class ResourcePathGuard(Protocol):
    def resolve_under_root(self, root: Path, name: str | Path) -> Path: ...


class DefaultResourcePathGuard:
    def resolve_under_root(self, root: Path, name: str | Path) -> Path:
        root_path = Path(root)
        root_resolved = root_path.resolve(strict=False)
        name_text = str(name)
        if not name_text or name_text in {".", ""}:
            raise ResourcePathError("resource path is empty")
        if name_text.startswith("\\\\") or name_text.startswith(("\\", "/")):
            raise ResourcePathError("resource path must be relative")
        if len(name_text) >= 2 and name_text[1] == ":":
            raise ResourcePathError("resource path must not contain a drive")

        parts = tuple(part for part in name_text.replace("\\", "/").split("/") if part)
        if not parts or any(part == ".." for part in parts):
            raise ResourcePathError("resource path must not escape the resource root")

        relative_path = Path(*parts)
        if relative_path.is_absolute():
            raise ResourcePathError("resource path must be relative")

        candidate = (root_resolved / relative_path).resolve(strict=False)
        try:
            candidate.relative_to(root_resolved)
        except ValueError as exc:
            raise ResourcePathError("resource path escapes the resource root") from exc
        return candidate


class ResourceStorePort(ABC):
    @abstractmethod
    def resolve_asset_path(self, name: str | Path) -> ResourceRef: ...

    @abstractmethod
    def load_image(self, name: str | Path, grayscale: bool = False) -> cv2.typing.MatLike: ...

    def close(self) -> None:
        pass


class RunArtifactStore(ABC):
    @abstractmethod
    def resolve_output_path(self, name: str | Path) -> ResourceRef: ...

    @abstractmethod
    def save_image(
        self,
        name: str | Path,
        image: cv2.typing.MatLike,
        *,
        overwrite: OverwritePolicy = OverwritePolicy.REPLACE,
        atomic: bool = True,
    ) -> ResourceRef: ...

    @abstractmethod
    def open_output(
        self,
        name: str | Path,
        mode: str = "xb",
        *,
        overwrite: OverwritePolicy = OverwritePolicy.ERROR,
        atomic: bool = True,
    ) -> BinaryIO: ...

    def close(self) -> None:
        pass
